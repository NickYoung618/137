#!/usr/bin/env python3
"""Evaluate static and dynamic repeatability from repeated sample images.

The program detects geometry features from images using a LabelMe reference
annotation, then calculates:

- static repeatability: variation of repeated captures at the same position;
- dynamic repeatability: variation of the position means after position changes.

No annotated images are saved. Outputs are numeric CSV/JSON reports only.

Typical single-sample data layout:

    sample_1/
      sample_1_label.json
      reference.bmp
      pos_1/*.bmp
      pos_2/*.bmp
      pos_3/*.bmp

Run once per sample, using that sample's own annotation file.

Or provide a single-sample manifest CSV with columns:

    position,image

Optional columns: sample,repeat. The image path may be absolute or relative to
the manifest file.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
from PIL import Image, ImageDraw, ImageFont


# Circle "roles" are derived from the annotation's geometry, not from label
# strings. The largest annotated circle is the outer anchor (used for global
# scale + as a ratio prior for everything else); the smallest is the inner
# hole (detected via the dark-bore detector); the rest are middle rings
# anchored to the outer by their annotation radius ratio. This makes the
# pipeline label-agnostic so any one-shot LabelMe annotation works regardless
# of whether the operator uses ψ, φ, Φ, ⌀, M, etc.
ROLE_OUTER = "outer"
ROLE_INNER = "inner"
ROLE_MIDDLE = "middle"

IMAGE_SUFFIXES = {".bmp", ".png", ".jpg", ".jpeg", ".tif", ".tiff"}
DEFAULT_OUTPUT_DIR = "repeatability_output"
DEFAULT_ROTATION_LOCK_GATE_DEG = 0.0
MIDDLE_RADIAL_SEARCH_WIDTH_PX = 14
MIDDLE_RADIAL_MIN_POINTS = 180
MIDDLE_RADIAL_MAX_RESIDUAL_PX = 4.0
MIDDLE_TEMPLATE_DEVIATION_GATE_REF_PX = 6.0
MIDDLE_TEMPLATE_OFFSET_TRIGGER_PX = 7.5
MIDDLE_TEMPLATE_LOW_SCORE_TRIGGER = 0.35
POSITION_CLUSTER_WINDOW_REF_PX = 3.0
POSITION_CLUSTER_OUTLIER_GATE_REF_PX = 3.0
POSITION_CLUSTER_ENABLE_RANGE_REF_PX = 3.0
POSITION_CLUSTER_MIN_FRACTION = 0.4
D46_RADIAL_TEMPLATE_HALF_WIDTH_PX = 56
D46_RADIAL_SEARCH_RANGE_PX = 32
D46_RADIAL_MIN_NCC_SCORE = 0.55
D46_POSITION_CLUSTER_WINDOW_REF_PX = 0.75
D46_POSITION_CLUSTER_OUTLIER_GATE_REF_PX = 0.75
D46_POSITION_CLUSTER_ENABLE_RANGE_REF_PX = 1.5
D46_POSITION_CLUSTER_MIN_FRACTION = 0.45
LINE20_POSITION_CLUSTER_WINDOW_REF_PX = 0.75
LINE20_POSITION_CLUSTER_OUTLIER_GATE_REF_PX = 0.75
LINE20_POSITION_CLUSTER_ENABLE_RANGE_REF_PX = 0.8
LINE20_POSITION_CLUSTER_MIN_FRACTION = 0.5


@dataclass(frozen=True)
class ImageRecord:
    sample: str
    position: str
    image_path: Path
    repeat_index: int


@dataclass
class ShapeModel:
    label: str
    shape_type: str
    points: list[list[float]]
    is_circle: bool
    circle: tuple[float, float, float] | None = None
    middle_template: np.ndarray | None = None
    middle_angles: np.ndarray | None = None


@dataclass
class ReferenceModel:
    annotation: dict
    reference_path: Path
    reference_gray: np.ndarray
    reference_grad: np.ndarray
    shapes: list[ShapeModel]
    alignment_center: tuple[float, float]
    alignment_inner_radius: float
    alignment_outer_radius: float
    # Annotation-derived radius ratios relative to the outer anchor, used to
    # pin middle rings to the already-detected outer ring instead of relying
    # on the global similarity transform's scale alone. The outer ring has the
    # most reliable lock; concentric rings inherit its accuracy.
    radius_ratio_to_outer: dict[str, float] | None = None
    # Geometric-role labels (label-agnostic dispatch). The largest annotated
    # circle is the outer anchor; the smallest is the inner hole; everything
    # else is a middle ring. These let the rest of the pipeline ignore label
    # strings and treat any labeling convention uniformly.
    outer_label: str | None = None
    inner_label: str | None = None


def circle_role(ref_model: "ReferenceModel", label: str) -> str:
    if ref_model.outer_label is not None and label == ref_model.outer_label:
        return ROLE_OUTER
    if ref_model.inner_label is not None and label == ref_model.inner_label:
        return ROLE_INNER
    return ROLE_MIDDLE


@dataclass(frozen=True)
class SimilarityTransform:
    reference_center: tuple[float, float]
    target_center: tuple[float, float]
    scale: float
    rotation: float
    method: str

    def apply_point(self, point: tuple[float, float]) -> tuple[float, float]:
        x, y = point
        rx = x - self.reference_center[0]
        ry = y - self.reference_center[1]
        cos_t = math.cos(self.rotation)
        sin_t = math.sin(self.rotation)
        return (
            self.target_center[0] + self.scale * (cos_t * rx - sin_t * ry),
            self.target_center[1] + self.scale * (sin_t * rx + cos_t * ry),
        )

    def inverse_point(self, point: tuple[float, float]) -> tuple[float, float]:
        x, y = point
        tx = (x - self.target_center[0]) / self.scale
        ty = (y - self.target_center[1]) / self.scale
        cos_t = math.cos(self.rotation)
        sin_t = math.sin(self.rotation)
        return (
            self.reference_center[0] + cos_t * tx + sin_t * ty,
            self.reference_center[1] - sin_t * tx + cos_t * ty,
        )

    def apply_radius(self, radius: float) -> float:
        return radius * self.scale

    def inverse_radius(self, radius: float) -> float:
        return radius / self.scale

    def apply_angle(self, angle: float) -> float:
        return angle + self.rotation


@dataclass(frozen=True)
class PreparedTransform:
    transform: SimilarityTransform
    raw_rotation: float
    rotation_median: float | None
    rotation_correction: float
    rotation_locked: bool


@dataclass(frozen=True)
class CircleCandidate:
    circle: tuple[float, float, float]
    point_count: int
    median_residual: float


@dataclass(frozen=True)
class TemplateCandidate:
    circle: tuple[float, float, float]
    target_radius: float
    best_score: float
    best_offset: float
    anchored_radius: float | None
    used_anchor_fallback: bool


def normalize_angle(angle: float) -> float:
    return (angle + math.pi) % (2.0 * math.pi) - math.pi


def angle_delta(angle: float, reference: float) -> float:
    return normalize_angle(angle - reference)


def circular_median(angles: list[float]) -> float:
    if not angles:
        return 0.0
    anchor = angles[0]
    unwrapped = [anchor + angle_delta(angle, anchor) for angle in angles]
    return normalize_angle(float(statistics.median(unwrapped)))


def replace_transform_rotation(transform: SimilarityTransform, rotation: float, note: str) -> SimilarityTransform:
    return SimilarityTransform(
        transform.reference_center,
        transform.target_center,
        transform.scale,
        rotation,
        f"{transform.method}, {note}",
    )


def is_d46_label(label: str) -> bool:
    normalized = label.strip().lower().replace(" ", "")
    return normalized in {"46", "d46", "d-46", "φ46", "ψ46", "ø46"}


def is_line20_label(label: str) -> bool:
    normalized = label.strip().lower().replace(" ", "").replace("_", "").replace("-", "")
    return normalized in {"20", "label20", "l20", "length20"}


def read_labelme(path: Path) -> dict:
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "utf-8", "gbk", "gb18030"):
        try:
            return json.loads(raw.decode(encoding))
        except UnicodeDecodeError:
            continue
    return json.loads(raw.decode("latin1"))


def load_gray(path: Path) -> np.ndarray:
    return np.asarray(Image.open(path).convert("L"))


DEFAULT_SMOOTH_SIGMA = 1.0


def gaussian_blur(arr: np.ndarray, sigma: float = DEFAULT_SMOOTH_SIGMA) -> np.ndarray:
    """Edge-padded separable Gaussian blur. Returns float64.

    Subpixel edge detection is sensitive to per-pixel noise. Pre-smoothing
    converts a step edge into a clean ramp whose derivative profile fits a
    parabola well, which is what `parabolic_peak` exploits downstream.
    """
    src = arr.astype(np.float64, copy=False)
    if sigma <= 0:
        return src.copy() if src is arr else src
    radius = max(1, int(math.ceil(3.0 * sigma)))
    x = np.arange(-radius, radius + 1, dtype=np.float64)
    kernel = np.exp(-(x * x) / (2.0 * sigma * sigma))
    kernel /= kernel.sum()
    padded = np.pad(src, ((0, 0), (radius, radius)), mode="edge")
    horiz = np.zeros_like(src)
    for i, w in enumerate(kernel):
        horiz += padded[:, i:i + src.shape[1]] * w
    padded = np.pad(horiz, ((radius, radius), (0, 0)), mode="edge")
    out = np.zeros_like(src)
    for i, w in enumerate(kernel):
        out += padded[i:i + src.shape[0], :] * w
    return out


def gradient_magnitude(gray: np.ndarray) -> np.ndarray:
    arr = gray.astype(np.float64)
    gx = np.zeros_like(arr)
    gy = np.zeros_like(arr)
    gx[:, 1:-1] = arr[:, 2:] - arr[:, :-2]
    gy[1:-1, :] = arr[2:, :] - arr[:-2, :]
    return np.hypot(gx, gy)


def normalize_for_match(patch: np.ndarray) -> np.ndarray | None:
    patch = patch.astype(np.float64)
    patch = patch - float(patch.mean())
    norm = float(np.sqrt(np.sum(patch * patch)))
    if norm < 1e-6:
        return None
    return patch / norm


def ncc_score(a: np.ndarray, b: np.ndarray) -> float:
    aa = normalize_for_match(a)
    bb = normalize_for_match(b)
    if aa is None or bb is None:
        return -1.0
    return float(np.sum(aa * bb))


def fit_circle(points: Iterable[Iterable[float]]) -> tuple[float, float, float]:
    pts = np.asarray(list(points), dtype=np.float64)
    if len(pts) < 3:
        raise ValueError("At least three points are required to fit a circle")
    x = pts[:, 0]
    y = pts[:, 1]
    a = np.column_stack([x, y, np.ones_like(x)])
    b = -(x * x + y * y)
    d, e, f = np.linalg.lstsq(a, b, rcond=None)[0]
    cx = -d / 2.0
    cy = -e / 2.0
    radius = math.sqrt(max(0.0, cx * cx + cy * cy - f))
    return cx, cy, radius


def geometric_circle_fit(
    points: np.ndarray,
    init: tuple[float, float, float],
    max_iter: int = 30,
) -> tuple[float, float, float]:
    """Refine a circle fit by minimizing point-to-circle geometric distance.

    Algebraic (Kasa) fits like `fit_circle` are biased — the residual they
    minimize weights points further from the circle more heavily, which pulls
    the radius slightly inward. Gauss-Newton on the geometric residual
    (sqrt distance - r) is unbiased and converges in a handful of iterations
    when seeded with the algebraic estimate.
    """
    pts = np.asarray(points, dtype=np.float64)
    cx, cy, r = init
    if len(pts) < 3:
        return cx, cy, r
    n = float(len(pts))
    for _ in range(max_iter):
        dx = pts[:, 0] - cx
        dy = pts[:, 1] - cy
        di = np.hypot(dx, dy)
        if (di < 1e-9).any():
            break
        ux = dx / di
        uy = dy / di
        residual = di - r
        sum_ux2 = float(np.dot(ux, ux))
        sum_uy2 = float(np.dot(uy, uy))
        sum_uxuy = float(np.dot(ux, uy))
        sum_ux = float(np.sum(ux))
        sum_uy = float(np.sum(uy))
        h = np.array([
            [sum_ux2, sum_uxuy, sum_ux],
            [sum_uxuy, sum_uy2, sum_uy],
            [sum_ux, sum_uy, n],
        ])
        g = np.array([
            float(np.dot(ux, residual)),
            float(np.dot(uy, residual)),
            float(np.sum(residual)),
        ])
        try:
            delta = np.linalg.solve(h, g)
        except np.linalg.LinAlgError:
            break
        cx += float(delta[0])
        cy += float(delta[1])
        r += float(delta[2])
        if abs(delta[0]) + abs(delta[1]) + abs(delta[2]) < 1e-9:
            break
    return cx, cy, r


def robust_fit_circle(points: list[tuple[float, float]], fallback: tuple[float, float, float]) -> tuple[float, float, float]:
    if len(points) < 8:
        return fallback
    pts = np.asarray(points, dtype=np.float64)
    for _ in range(8):
        cx, cy, radius = fit_circle(pts)
        residual = np.abs(np.hypot(pts[:, 0] - cx, pts[:, 1] - cy) - radius)
        median = float(np.median(residual))
        mad = float(np.median(np.abs(residual - median))) + 1e-6
        gate = max(6.0, median + 3.0 * 1.4826 * mad)
        keep = residual <= gate
        if int(np.count_nonzero(keep)) < 8 or int(np.count_nonzero(keep)) == len(pts):
            break
        pts = pts[keep]
    cx, cy, radius = fit_circle(pts)
    return geometric_circle_fit(pts, (cx, cy, radius))


def circular_residual(points: list[list[float]], circle: tuple[float, float, float]) -> float:
    cx, cy, radius = circle
    pts = np.asarray(points, dtype=np.float64)
    return float(np.median(np.abs(np.hypot(pts[:, 0] - cx, pts[:, 1] - cy) - radius)))


def is_circular_shape(label: str, shape_type: str, points: list[list[float]]) -> bool:
    # Geometry-only test: any traced linestrip with ≥8 points whose residual
    # to a fitted circle is under 25 px is treated as a ring annotation.
    # This is label-agnostic so the pipeline works with any naming convention.
    if shape_type != "linestrip" or len(points) < 8:
        return False
    try:
        return circular_residual(points, fit_circle(points)) < 25.0
    except ValueError:
        return False


def bilinear_sample(gray: np.ndarray, xs: np.ndarray, ys: np.ndarray) -> np.ndarray:
    height, width = gray.shape
    x0 = np.floor(xs).astype(np.int64)
    y0 = np.floor(ys).astype(np.int64)
    x1 = x0 + 1
    y1 = y0 + 1
    valid = (x0 >= 0) & (y0 >= 0) & (x1 < width) & (y1 < height)
    out = np.full(xs.shape, np.nan, dtype=np.float64)

    xv = xs[valid]
    yv = ys[valid]
    x0v = x0[valid]
    y0v = y0[valid]
    x1v = x1[valid]
    y1v = y1[valid]
    dx = xv - x0v
    dy = yv - y0v
    out[valid] = (
        gray[y0v, x0v] * (1.0 - dx) * (1.0 - dy)
        + gray[y0v, x1v] * dx * (1.0 - dy)
        + gray[y1v, x0v] * (1.0 - dx) * dy
        + gray[y1v, x1v] * dx * dy
    )
    return out


def smooth_1d(values: np.ndarray, window: int = 11) -> np.ndarray:
    if len(values) < window:
        return values
    kernel = np.ones(window, dtype=np.float64) / float(window)
    return np.convolve(values, kernel, mode="same")


def sample_radial(gray: np.ndarray, cx: float, cy: float, angle: float, radius: float, half_width: int) -> tuple[np.ndarray, np.ndarray]:
    """Bilinear-sampled radial intensity profile.

    Previous integer-pixel indexing (`np.rint(...).astype(np.int64)`) quantized
    the ray to whole-pixel positions, so even after parabolic peak fitting the
    detected radius could not get below ~0.5 px noise floor. Bilinear sampling
    closes that gap.
    """
    height, width = gray.shape
    r_start = max(3, int(round(radius - half_width)))
    r_end = min(int(math.hypot(width, height)), int(round(radius + half_width)))
    radii = np.arange(r_start, r_end + 1, dtype=np.float64)
    xs = cx + radii * math.cos(angle)
    ys = cy + radii * math.sin(angle)
    valid = (xs >= 0.0) & (xs < width - 1.0) & (ys >= 0.0) & (ys < height - 1.0)
    if not np.any(valid):
        return radii[:0], radii[:0]
    profile = bilinear_sample(gray, xs[valid], ys[valid])
    return radii[valid], profile


def radial_polarity(reference_gray: np.ndarray, center: tuple[float, float], radius: float, angles: np.ndarray) -> float:
    cx, cy = center
    values = []
    for angle in angles[:: max(1, len(angles) // 24)]:
        radii, profile = sample_radial(reference_gray, cx, cy, float(angle), radius, 14)
        if len(radii) < 10:
            continue
        below = profile[radii < radius - 2]
        above = profile[radii > radius + 2]
        if len(below) and len(above):
            values.append(float(np.mean(above) - np.mean(below)))
    if not values:
        return 0.0
    return float(np.median(values))


def radial_edge_at_angle(
    target_gray: np.ndarray,
    center: tuple[float, float],
    angle: float,
    radius: float,
    polarity: float,
    search_width: int,
) -> tuple[float, float] | None:
    cx, cy = center
    radii, profile = sample_radial(target_gray, cx, cy, angle, radius, search_width)
    if len(radii) < 20:
        return None
    profile = smooth_1d(profile)
    derivative = np.diff(profile)
    if polarity > 2.0:
        score = derivative
    elif polarity < -2.0:
        score = -derivative
    else:
        score = np.abs(derivative)
    idx = int(np.argmax(score))
    if float(score[idx]) < 2.0:
        return None
    delta = parabolic_peak(score.tolist(), idx)
    step = float(radii[1] - radii[0]) if len(radii) >= 2 else 1.0
    detected_radius = float((radii[idx] + radii[idx + 1]) / 2.0 + delta * step)
    return cx + detected_radius * math.cos(angle), cy + detected_radius * math.sin(angle)


def inner_hole_edge_point(
    target_gray: np.ndarray,
    center: tuple[float, float],
    angle: float,
    predicted_radius: float,
) -> tuple[float, float] | None:
    """Find the first stable black-to-bright boundary of the inner hole.

    The innermost circle is close to several machined grooves. The strongest
    edge is often not the hole boundary, so this detector scans from the dark
    hole outward and locks onto the first meaningful intensity crossing.
    """
    radii, profile = sample_radial(target_gray, center[0], center[1], angle, predicted_radius + 20.0, 90)
    if len(radii) < 40:
        return None
    profile = smooth_1d(profile, 9)
    keep = (radii >= predicted_radius - 15.0) & (radii <= predicted_radius + 75.0)
    rr = radii[keep]
    values = profile[keep]
    if len(rr) < 20:
        return None

    inner_count = max(5, len(values) // 5)
    dark_level = float(np.percentile(values[:inner_count], 20))
    bright_level = float(np.percentile(values, 90))
    if bright_level - dark_level < 15.0:
        return None

    threshold = dark_level + 0.32 * (bright_level - dark_level)
    crossings = np.where(values >= threshold)[0]
    if len(crossings) == 0:
        return None
    crossing = int(crossings[0])

    derivative = np.diff(values)
    lo = max(0, crossing - 5)
    hi = min(len(derivative), crossing + 8)
    if hi <= lo:
        return None
    edge_idx = lo + int(np.argmax(derivative[lo:hi]))
    if derivative[edge_idx] < 2.0:
        return None

    delta = parabolic_peak(derivative.tolist(), edge_idx)
    step = float(rr[1] - rr[0]) if len(rr) >= 2 else 1.0
    edge_radius = float((rr[edge_idx] + rr[min(edge_idx + 1, len(rr) - 1)]) / 2.0 + delta * step)
    return center[0] + edge_radius * math.cos(angle), center[1] + edge_radius * math.sin(angle)


def outer_boundary_edge_point(
    target_gray: np.ndarray,
    center: tuple[float, float],
    angle: float,
    predicted_radius: float,
) -> tuple[float, float] | None:
    """Find the outermost material-to-background boundary on a radial ray.

    Outer-circle detection should not pick the strongest edge in the search
    band: nearby machined grooves can be much stronger than the real outside
    boundary. Instead, use the dark background outside the part as context and
    choose the outermost bright-to-dark crossing.
    """
    radii, profile = sample_radial(target_gray, center[0], center[1], angle, predicted_radius, 90)
    if len(radii) < 45:
        return None
    values = smooth_1d(profile, 9)

    outer_count = max(8, len(values) // 5)
    dark_level = float(np.percentile(values[-outer_count:], 30))
    bright_level = float(np.percentile(values, 85))
    if bright_level - dark_level < 12.0:
        return None

    threshold = dark_level + 0.45 * (bright_level - dark_level)
    above = values >= threshold
    crossings = np.where(above[:-1] & ~above[1:])[0]
    if len(crossings) == 0:
        return None

    crossing = int(crossings[-1])
    derivative = np.diff(values)
    lo = max(0, crossing - 5)
    hi = min(len(derivative), crossing + 8)
    if hi <= lo:
        return None
    score = -derivative
    edge_idx = lo + int(np.argmax(score[lo:hi]))
    if score[edge_idx] < 2.0:
        return None

    delta = parabolic_peak(score.tolist(), edge_idx)
    step = float(radii[1] - radii[0]) if len(radii) >= 2 else 1.0
    edge_radius = float((radii[edge_idx] + radii[min(edge_idx + 1, len(radii) - 1)]) / 2.0 + delta * step)
    return center[0] + edge_radius * math.cos(angle), center[1] + edge_radius * math.sin(angle)


def detect_inner_hole_circle(model: ShapeModel, target_gray: np.ndarray, transform: SimilarityTransform) -> tuple[float, float, float]:
    circle, _ = detect_inner_hole_circle_with_quality(model, target_gray, transform)
    return circle


def detect_inner_hole_circle_with_quality(
    model: ShapeModel,
    target_gray: np.ndarray,
    transform: SimilarityTransform,
) -> tuple[tuple[float, float, float], dict[str, object]]:
    assert model.circle is not None
    predicted_center = transform.apply_point((model.circle[0], model.circle[1]))
    predicted_radius = transform.apply_radius(model.circle[2])
    points: list[tuple[float, float]] = []
    for angle in np.linspace(0.0, 2.0 * math.pi, 720, endpoint=False):
        point = inner_hole_edge_point(target_gray, predicted_center, float(angle), predicted_radius)
        if point is not None:
            points.append(point)
    fallback = (predicted_center[0], predicted_center[1], predicted_radius)
    circle = robust_fit_circle(points, fallback)
    valid = len(points) >= 8
    quality: dict[str, object] = {
        "detect.source": "inner_edge_fit" if valid else "inner_edge_fallback",
        "quality.measurement_valid": 1.0 if valid else 0.0,
        "quality.edge_point_count": float(len(points)),
        "quality.anomaly_flag": 0.0 if valid else 1.0,
        "quality.anomaly_reason": "" if valid else "inner_edge_insufficient_points",
    }
    return circle, quality


def dense_angles_from_points(points: list[list[float]], circle: tuple[float, float, float], count: int = 180) -> np.ndarray:
    pts = np.asarray(points, dtype=np.float64)
    angles = np.unwrap(np.arctan2(pts[:, 1] - circle[1], pts[:, 0] - circle[0]))
    start = float(np.min(angles))
    end = float(np.max(angles))
    if abs(end - start) < 1e-6:
        return angles
    return np.linspace(start, end, max(count, len(points)))


def template_half_width(role: str) -> int:
    # Outer/inner boundaries are near several machined ring edges. A wider
    # radial template captures the local edge context, not just a single edge.
    # Outer rings live near multiple grooves, so they need the widest window;
    # the inner hole has a single sharp edge plus chamfer.
    if role == ROLE_OUTER:
        return 86
    if role == ROLE_INNER:
        return 72
    return 48  # middle


def template_search_range(role: str, scale: float) -> int:
    base = {ROLE_OUTER: 70, ROLE_INNER: 58, ROLE_MIDDLE: 38}.get(role, 32)
    return max(18, int(round(base * max(scale, 0.5))))


def template_allowed_correction(role: str, scale: float) -> int:
    # The same sample is being measured repeatedly. After global center/scale
    # alignment, the true residual radius correction should be small. Larger
    # jumps usually mean the local detector locked onto a neighboring groove.
    base = {ROLE_OUTER: 14, ROLE_INNER: 5, ROLE_MIDDLE: 14}.get(role, 18)
    return max(4, int(round(base * max(scale, 0.5))))


def radial_derivative_template(
    gray: np.ndarray,
    center: tuple[float, float],
    radius: float,
    angles: np.ndarray,
    half_width: int,
) -> np.ndarray:
    offsets = np.arange(-half_width, half_width + 1, dtype=np.float64)
    angle_grid, radius_grid = np.meshgrid(angles, radius + offsets, indexing="ij")
    xs = center[0] + radius_grid * np.cos(angle_grid)
    ys = center[1] + radius_grid * np.sin(angle_grid)
    profiles = bilinear_sample(gray.astype(np.float64), xs, ys)
    if np.isnan(profiles).any():
        fill = float(np.nanmean(profiles)) if not np.isnan(profiles).all() else 0.0
        profiles = np.nan_to_num(profiles, nan=fill)
    profiles = np.apply_along_axis(smooth_1d, 1, profiles, 7)
    return np.diff(profiles, axis=1)


def radial_template_ncc_at_radius(
    reference_template: np.ndarray,
    target_gray: np.ndarray,
    center: tuple[float, float],
    radius: float,
    angles: np.ndarray,
    half_width: int,
) -> float:
    target_template = radial_derivative_template(target_gray, center, radius, angles, half_width)
    return ncc_score(reference_template, target_template)


def parabolic_peak(scores: list[float], index: int) -> float:
    if index <= 0 or index >= len(scores) - 1:
        return 0.0
    left = scores[index - 1]
    center = scores[index]
    right = scores[index + 1]
    denom = left - 2.0 * center + right
    if abs(denom) < 1e-9:
        return 0.0
    return float(np.clip(0.5 * (left - right) / denom, -0.5, 0.5))


def phase_correlation_shift(reference: np.ndarray, target: np.ndarray, downsample: int = 8) -> tuple[float, float, float]:
    height, width = reference.shape
    small_size = (max(16, width // downsample), max(16, height // downsample))
    # PIL has no native float64 mode; cast to float32 ('F' mode) first.
    ref_pil = Image.fromarray(np.asarray(reference, dtype=np.float32))
    tgt_pil = Image.fromarray(np.asarray(target, dtype=np.float32))
    ref_small = np.asarray(ref_pil.resize(small_size, Image.Resampling.BILINEAR), dtype=np.float64)
    tgt_small = np.asarray(tgt_pil.resize(small_size, Image.Resampling.BILINEAR), dtype=np.float64)

    ref_grad = gradient_magnitude(ref_small)
    tgt_grad = gradient_magnitude(tgt_small)
    window = np.outer(np.hanning(ref_grad.shape[0]), np.hanning(ref_grad.shape[1]))
    ref_grad = (ref_grad - ref_grad.mean()) / (ref_grad.std() + 1e-6) * window
    tgt_grad = (tgt_grad - tgt_grad.mean()) / (tgt_grad.std() + 1e-6) * window

    ref_fft = np.fft.fft2(ref_grad)
    tgt_fft = np.fft.fft2(tgt_grad)
    cross_power = tgt_fft * np.conj(ref_fft)
    cross_power /= np.abs(cross_power) + 1e-9
    corr = np.fft.ifft2(cross_power).real
    peak_y, peak_x = np.unravel_index(int(np.argmax(corr)), corr.shape)
    if peak_x > corr.shape[1] // 2:
        peak_x -= corr.shape[1]
    if peak_y > corr.shape[0] // 2:
        peak_y -= corr.shape[0]
    return float(peak_x * downsample), float(peak_y * downsample), float(corr.max())


def object_bbox_center(gray: np.ndarray, threshold: int = 35) -> tuple[float, float]:
    ys, xs = np.where(gray > threshold)
    if len(xs) == 0:
        return float(gray.shape[1]) / 2.0, float(gray.shape[0]) / 2.0
    return float(xs.min() + xs.max()) / 2.0, float(ys.min() + ys.max()) / 2.0


def object_bbox(gray: np.ndarray, threshold: int = 35) -> tuple[float, float, float, float]:
    ys, xs = np.where(gray > threshold)
    if len(xs) == 0:
        return 0.0, 0.0, float(gray.shape[1] - 1), float(gray.shape[0] - 1)
    return float(xs.min()), float(ys.min()), float(xs.max()), float(ys.max())


def estimate_bbox_scale(reference: np.ndarray, target: np.ndarray) -> float:
    rx1, ry1, rx2, ry2 = object_bbox(reference)
    tx1, ty1, tx2, ty2 = object_bbox(target)
    ref_w = max(1.0, rx2 - rx1)
    ref_h = max(1.0, ry2 - ry1)
    tgt_w = max(1.0, tx2 - tx1)
    tgt_h = max(1.0, ty2 - ty1)
    return float(np.median([tgt_w / ref_w, tgt_h / ref_h]))


def estimate_global_shift(reference: np.ndarray, target: np.ndarray) -> tuple[float, float, str]:
    dx, dy, score = phase_correlation_shift(reference, target)
    if score >= 0.2:
        return dx, dy, f"phase-correlation score={score:.3f}"
    ref_center = object_bbox_center(reference)
    tgt_center = object_bbox_center(target)
    return tgt_center[0] - ref_center[0], tgt_center[1] - ref_center[1], f"bbox fallback, phase score={score:.3f}"


def detect_alignment_circle(
    target_gray: np.ndarray,
    center: tuple[float, float],
    radius: float,
    polarity: float,
) -> tuple[float, float, float]:
    angles = np.linspace(0.0, 2.0 * math.pi, 720, endpoint=False)
    search_width = int(max(80, min(260, radius * 0.14)))
    points: list[tuple[float, float]] = []
    for angle in angles:
        point = radial_edge_at_angle(target_gray, center, float(angle), radius, polarity, search_width)
        if point is not None:
            points.append(point)
    return robust_fit_circle(points, (center[0], center[1], radius))


def annular_angular_signature(
    gray: np.ndarray,
    center: tuple[float, float],
    inner_radius: float,
    outer_radius: float,
    angle_count: int = 720,
    radial_count: int = 180,
) -> np.ndarray:
    grad = gradient_magnitude(gray)
    angles = np.linspace(0.0, 2.0 * math.pi, angle_count, endpoint=False)
    radii = np.linspace(inner_radius, outer_radius, radial_count)
    angle_grid, radius_grid = np.meshgrid(angles, radii, indexing="ij")
    xs = center[0] + radius_grid * np.cos(angle_grid)
    ys = center[1] + radius_grid * np.sin(angle_grid)
    values = bilinear_sample(grad, xs, ys)
    if np.isnan(values).any():
        fill = float(np.nanmean(values)) if not np.isnan(values).all() else 0.0
        values = np.nan_to_num(values, nan=fill)
    signature = np.percentile(values, 75, axis=1)
    signature = signature - float(np.mean(signature))
    std = float(np.std(signature))
    if std > 1e-6:
        signature = signature / std
    return signature


def estimate_rotation_by_signature(
    reference_gray: np.ndarray,
    target_gray: np.ndarray,
    reference_center: tuple[float, float],
    target_center: tuple[float, float],
    reference_inner_radius: float,
    reference_outer_radius: float,
    scale: float,
) -> tuple[float, float]:
    ref_inner = max(10.0, reference_inner_radius * 0.92)
    ref_outer = reference_outer_radius * 1.03
    tgt_inner = max(10.0, ref_inner * scale)
    tgt_outer = ref_outer * scale
    ref_sig = annular_angular_signature(reference_gray, reference_center, ref_inner, ref_outer)
    tgt_sig = annular_angular_signature(target_gray, target_center, tgt_inner, tgt_outer)
    corr = np.fft.ifft(np.fft.fft(tgt_sig) * np.conj(np.fft.fft(ref_sig))).real
    peak = int(np.argmax(corr))
    if peak > len(corr) // 2:
        peak -= len(corr)
    wrapped_index = peak % len(corr)
    sub = parabolic_peak(corr.tolist(), wrapped_index)
    rotation = 2.0 * math.pi * (peak + sub) / float(len(corr))
    score = float(np.max(corr) / (np.linalg.norm(ref_sig) * np.linalg.norm(tgt_sig) + 1e-9))
    return rotation, score


def polar_resample(
    gray: np.ndarray,
    center: tuple[float, float],
    r_min: float,
    r_max: float,
    n_radii: int,
    n_angles: int,
) -> np.ndarray:
    """Resample `gray` into polar coordinates around `center`.

    Returned array has shape (n_radii, n_angles): radius along axis 0, angle
    along axis 1. Out-of-frame samples are filled with the array mean.
    """
    radii = np.linspace(r_min, r_max, n_radii)
    angles = np.linspace(0.0, 2.0 * math.pi, n_angles, endpoint=False)
    rg, ag = np.meshgrid(radii, angles, indexing="ij")
    xs = center[0] + rg * np.cos(ag)
    ys = center[1] + rg * np.sin(ag)
    polar = bilinear_sample(gray, xs, ys)
    if np.isnan(polar).any():
        fill = float(np.nanmean(polar)) if not np.isnan(polar).all() else 0.0
        polar = np.nan_to_num(polar, nan=fill)
    return polar


def find_outer_notch_angle(
    gray: np.ndarray,
    center: tuple[float, float],
    outer_radius: float,
    n_angles: int = 1440,
) -> tuple[float, float, float] | None:
    """Locate the outer-edge notch (dark sector) angular center.

    Returns (center_radian, half_width_radian, prominence). The annular shell is
    sampled just inside the outer radius, the deepest contiguous dip is taken
    as the notch, and the dip center is refined by a brightness-weighted
    centroid. Returns None when no clear dip exists.
    """
    height, width = gray.shape
    angles = np.linspace(0.0, 2.0 * math.pi, n_angles, endpoint=False)
    r_inner = max(10.0, outer_radius - 30.0)
    sample_radii = np.linspace(r_inner, outer_radius, 10)
    profile = np.full(n_angles, np.nan, dtype=np.float64)
    for i, angle in enumerate(angles):
        xs = center[0] + sample_radii * math.cos(angle)
        ys = center[1] + sample_radii * math.sin(angle)
        if not ((xs >= 0) & (xs < width - 1) & (ys >= 0) & (ys < height - 1)).all():
            continue
        profile[i] = float(bilinear_sample(gray, xs, ys).mean())
    valid = ~np.isnan(profile)
    if int(np.count_nonzero(valid)) < n_angles // 2:
        return None
    smoothed = profile.copy()
    fill_value = float(np.nanmedian(profile))
    smoothed[~valid] = fill_value
    smoothed = np.convolve(smoothed, np.ones(7) / 7.0, mode="same")
    median_val = float(np.median(smoothed))
    mad = float(np.median(np.abs(smoothed - median_val))) + 1e-6
    threshold = median_val - 3.0 * 1.4826 * mad
    if (median_val - smoothed.min()) < 12.0:
        return None
    is_dark = smoothed < threshold
    # Find longest contiguous dark run, allowing wrap-around.
    if not is_dark.any():
        return None
    doubled = np.concatenate([is_dark, is_dark])
    best_start = best_len = 0
    cur_start = -1
    for i in range(len(doubled)):
        if doubled[i]:
            if cur_start < 0:
                cur_start = i
            run = i - cur_start + 1
            if run > best_len:
                best_len = run
                best_start = cur_start
        else:
            cur_start = -1
    if best_len > n_angles:
        best_len = n_angles
    indices = [(best_start + k) % n_angles for k in range(best_len)]
    weights = np.maximum(0.0, threshold - smoothed[indices])
    if weights.sum() <= 1e-6:
        return None
    raw_angles = angles[indices]
    base_angle = raw_angles[0]
    delta = ((raw_angles - base_angle + math.pi) % (2.0 * math.pi)) - math.pi
    centroid_delta = float(np.sum(delta * weights) / np.sum(weights))
    notch_angle = (base_angle + centroid_delta) % (2.0 * math.pi)
    half_width = (best_len * (2.0 * math.pi / n_angles)) / 2.0
    prominence = float(median_val - smoothed[indices].min())
    return notch_angle, half_width, prominence


def estimate_rotation_by_notch(
    reference_gray: np.ndarray,
    target_gray: np.ndarray,
    reference_center: tuple[float, float],
    target_center: tuple[float, float],
    reference_outer_radius: float,
    scale: float,
) -> tuple[float, float] | None:
    """Refine rotation by aligning the outer-edge notch on both images.

    The polar-correlation rotation can drift a few degrees on cross-individual
    samples where text/surface markings differ. The notch is the most stable
    angular landmark on every part, so a notch-only refinement provides a
    second opinion. Returns (rotation, prominence_score) or None.
    """
    ref_notch = find_outer_notch_angle(reference_gray, reference_center, reference_outer_radius)
    tgt_notch = find_outer_notch_angle(target_gray, target_center, reference_outer_radius * scale)
    if ref_notch is None or tgt_notch is None:
        return None
    ref_angle, _, ref_prom = ref_notch
    tgt_angle, _, tgt_prom = tgt_notch
    rotation = (tgt_angle - ref_angle + math.pi) % (2.0 * math.pi) - math.pi
    return rotation, min(ref_prom, tgt_prom)


def estimate_rotation_by_polar(
    reference_gray: np.ndarray,
    target_gray: np.ndarray,
    reference_center: tuple[float, float],
    target_center: tuple[float, float],
    reference_inner_radius: float,
    reference_outer_radius: float,
    scale: float,
    n_angles: int = 720,
    n_radii: int = 240,
) -> tuple[float, float]:
    """Estimate rotation by 2D phase-correlation in the polar-resampled annulus.

    The earlier `estimate_rotation_by_signature` collapses the polar image to a
    single 1D angular signature (75th-percentile gradient per angle). When the
    asymmetric features (notch, engraved text) are weak relative to the
    rotationally-symmetric ring grooves, that 1D correlation locks onto the
    near-zero shift that aligns the rings, even when the true rotation is
    large. Per-radius phase correlation in polar coordinates preserves the
    radial structure, and phase normalization on each (radius, frequency) bin
    suppresses the ring-symmetric component. The notch then dominates the
    summed angular peak.
    """
    r_min = max(10.0, reference_inner_radius * 0.92)
    r_max = reference_outer_radius * 1.03
    ref_polar = polar_resample(reference_gray, reference_center, r_min, r_max, n_radii, n_angles)
    tgt_polar = polar_resample(target_gray, target_center, r_min * scale, r_max * scale, n_radii, n_angles)

    ref_grad = gradient_magnitude(ref_polar)
    tgt_grad = gradient_magnitude(tgt_polar)

    # Hanning along radial axis only — the angular axis is cyclic so windowing
    # would corrupt the wrap-around correlation.
    window = np.hanning(n_radii)[:, None]
    ref_w = (ref_grad - float(ref_grad.mean())) * window
    tgt_w = (tgt_grad - float(tgt_grad.mean())) * window

    ref_fft = np.fft.fft2(ref_w)
    tgt_fft = np.fft.fft2(tgt_w)
    cross = tgt_fft * np.conj(ref_fft)
    cross /= np.abs(cross) + 1e-9
    corr = np.fft.ifft2(cross).real

    # Sum over radial shifts: at the correct angular shift, the notch's signal
    # adds coherently across the small radial slack; at wrong angular shifts,
    # the per-radius noise floors average down.
    corr_1d = corr.sum(axis=0)
    peak = int(np.argmax(corr_1d))
    if peak > n_angles // 2:
        peak -= n_angles
    sub = parabolic_peak(corr_1d.tolist(), peak % n_angles)
    rotation = 2.0 * math.pi * (peak + sub) / float(n_angles)
    # Score: peak prominence in std units (>3 means clearly above noise floor).
    score = float((corr_1d.max() - corr_1d.mean()) / (corr_1d.std() + 1e-9))
    return rotation, score


def estimate_global_transform(ref_model: ReferenceModel, target_gray: np.ndarray) -> SimilarityTransform:
    coarse_center = object_bbox_center(target_gray)
    coarse_scale = estimate_bbox_scale(ref_model.reference_gray, target_gray)
    coarse_outer = ref_model.alignment_outer_radius * coarse_scale

    outer = detect_alignment_circle(target_gray, coarse_center, coarse_outer, polarity=-1.0)
    outer_scale = outer[2] / ref_model.alignment_outer_radius

    # Re-detect inner using the outer-derived center and the careful bore-edge
    # detector. The generic radial_edge scan can latch onto a nearby chamfer
    # rim on cross-individual samples (~21 px center bias on s2). The
    # inner_hole_edge_point detector locks onto the dark-to-bright bore boundary
    # specifically, giving a concentric inner that matches the outer.
    predicted_inner_radius = ref_model.alignment_inner_radius * outer_scale
    inner_points: list[tuple[float, float]] = []
    for angle in np.linspace(0.0, 2.0 * math.pi, 720, endpoint=False):
        point = inner_hole_edge_point(target_gray, (outer[0], outer[1]), float(angle), predicted_inner_radius)
        if point is not None:
            inner_points.append(point)
    inner = robust_fit_circle(inner_points, (outer[0], outer[1], predicted_inner_radius))
    inner_scale = inner[2] / ref_model.alignment_inner_radius
    scales = [coarse_scale, outer_scale]
    centers = [(outer[0], outer[1])]
    # The inner hole has many nearby high-contrast grooves. Use it for global
    # alignment only when it agrees with the coarse/outer scale; otherwise it is
    # detected later with its own local model.
    if abs(inner_scale - coarse_scale) / max(coarse_scale, 1e-6) < 0.04:
        scales.append(inner_scale)
        centers.append((inner[0], inner[1]))
    target_center = (float(np.mean([c[0] for c in centers])), float(np.mean([c[1] for c in centers])))
    scale = float(np.median(scales))

    rotation, rotation_score = estimate_rotation_by_polar(
        ref_model.reference_gray,
        target_gray,
        ref_model.alignment_center,
        target_center,
        ref_model.alignment_inner_radius,
        ref_model.alignment_outer_radius,
        scale,
    )
    notch_method = ""
    # Cross-individual surface markings differ, so the polar correlation peak
    # can drift a few degrees (rotation_score below ~6 in practice). The notch
    # is a deterministic geometric feature on every part, so we use it to
    # validate and, when polar confidence is low, override the rotation.
    notch_estimate = estimate_rotation_by_notch(
        ref_model.reference_gray,
        target_gray,
        ref_model.alignment_center,
        target_center,
        ref_model.alignment_outer_radius,
        scale,
    )
    if notch_estimate is not None:
        notch_rotation, notch_prom = notch_estimate
        delta_deg = math.degrees(((notch_rotation - rotation + math.pi) % (2.0 * math.pi)) - math.pi)
        if rotation_score < 6.0 and notch_prom > 12.0:
            rotation = notch_rotation
            notch_method = f", notch_override(Δ={delta_deg:+.2f}deg, prom={notch_prom:.1f})"
        else:
            notch_method = f", notch_check(Δ={delta_deg:+.2f}deg, prom={notch_prom:.1f})"
    method = (
        f"circle-alignment center=({target_center[0]:.3f},{target_center[1]:.3f}), "
        f"scale={scale:.8f}, rotation={math.degrees(rotation):.5f}deg, "
        f"rotation_score={rotation_score:.3f}{notch_method}"
    )
    return SimilarityTransform(ref_model.alignment_center, target_center, scale, rotation, method)


def bbox_from_points(points: list[list[float]], margin: int, shape: tuple[int, int]) -> tuple[int, int, int, int]:
    height, width = shape
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    x1 = max(0, int(math.floor(min(xs) - margin)))
    y1 = max(0, int(math.floor(min(ys) - margin)))
    x2 = min(width, int(math.ceil(max(xs) + margin)) + 1)
    y2 = min(height, int(math.ceil(max(ys) + margin)) + 1)
    return x1, y1, x2, y2


def crop_valid(arr: np.ndarray, x1: int, y1: int, x2: int, y2: int) -> np.ndarray | None:
    height, width = arr.shape
    if x1 < 0 or y1 < 0 or x2 > width or y2 > height or x2 <= x1 or y2 <= y1:
        return None
    return arr[y1:y2, x1:x2]


def downsample_patch(patch: np.ndarray, factor: int) -> np.ndarray:
    if factor <= 1:
        return patch
    return patch[::factor, ::factor]


def refine_shape_shift(
    ref_grad: np.ndarray,
    tgt_grad: np.ndarray,
    points: list[list[float]],
    global_shift: tuple[float, float],
    margin: int = 70,
    search_radius: int = 28,
) -> tuple[float, float, float]:
    x1, y1, x2, y2 = bbox_from_points(points, margin, ref_grad.shape)
    ref_patch = crop_valid(ref_grad, x1, y1, x2, y2)
    if ref_patch is None:
        return global_shift[0], global_shift[1], -1.0

    max_side = max(ref_patch.shape)
    factor = max(1, int(math.ceil(max_side / 240.0)))
    ref_small = downsample_patch(ref_patch, factor)
    step = max(1, factor)
    base_dx = int(round(global_shift[0]))
    base_dy = int(round(global_shift[1]))
    best = (base_dx, base_dy, -1.0)

    for pass_radius, pass_step in ((search_radius, step), (max(step, 3), 1)):
        current_dx, current_dy, _ = best
        for dy in range(current_dy - pass_radius, current_dy + pass_radius + 1, pass_step):
            for dx in range(current_dx - pass_radius, current_dx + pass_radius + 1, pass_step):
                tgt_patch = crop_valid(tgt_grad, x1 + dx, y1 + dy, x2 + dx, y2 + dy)
                if tgt_patch is None:
                    continue
                score = ncc_score(ref_small, downsample_patch(tgt_patch, factor))
                if score > best[2]:
                    best = (dx, dy, score)
    return float(best[0]), float(best[1]), float(best[2])


def refine_point_by_template(
    ref_grad: np.ndarray,
    tgt_grad: np.ndarray,
    reference_point: tuple[float, float],
    predicted_point: tuple[float, float],
    patch_radius: int = 24,
    search_radius: int = 18,
) -> tuple[float, float]:
    rx, ry = reference_point
    px, py = predicted_point
    rcx = int(round(rx))
    rcy = int(round(ry))
    ref_patch = crop_valid(ref_grad, rcx - patch_radius, rcy - patch_radius, rcx + patch_radius + 1, rcy + patch_radius + 1)
    if ref_patch is None:
        return predicted_point

    best = (int(round(px)), int(round(py)), -1.0)
    for cy in range(int(round(py)) - search_radius, int(round(py)) + search_radius + 1):
        for cx in range(int(round(px)) - search_radius, int(round(px)) + search_radius + 1):
            tgt_patch = crop_valid(tgt_grad, cx - patch_radius, cy - patch_radius, cx + patch_radius + 1, cy + patch_radius + 1)
            if tgt_patch is None:
                continue
            score = ncc_score(ref_patch, tgt_patch)
            if score > best[2]:
                best = (cx, cy, score)
    if best[2] < 0.35:
        return predicted_point
    return float(best[0]), float(best[1])


def refine_short_line(
    target_grad: np.ndarray,
    p1: tuple[float, float],
    p2: tuple[float, float],
    lateral_search: int = 12,
) -> tuple[tuple[float, float], tuple[float, float]] | None:
    # Short annotation lines (≤ ~80 px) trace an edge whose true longitudinal
    # extent is ambiguous — the annotator stops the click somewhere along a
    # much longer real edge. Independent per-endpoint NCC + edge snapping
    # then jiggles each end ±10 px and inflates length / angle 6σ.
    #
    # Treat the line as "direction + lateral offset": keep the predicted
    # longitudinal positions (their stability comes from the global similarity
    # transform), and only snap the line perpendicular to the actual edge by
    # finding the lateral offset that maximizes total gradient along the line.
    p1a = np.asarray(p1, dtype=np.float64)
    p2a = np.asarray(p2, dtype=np.float64)
    line_vec = p2a - p1a
    L = float(np.linalg.norm(line_vec))
    if L < 4.0:
        return None
    t = line_vec / L
    n = np.array([-t[1], t[0]])

    along_count = max(12, int(round(L)) + 1)
    along = np.linspace(0.0, L, along_count)
    across = np.arange(-lateral_search, lateral_search + 1, dtype=np.float64)
    A, C = np.meshgrid(along, across, indexing="ij")
    xs = p1a[0] + A * t[0] + C * n[0]
    ys = p1a[1] + A * t[1] + C * n[1]
    grad_grid = bilinear_sample(target_grad, xs, ys)
    if np.isnan(grad_grid).all():
        return None
    grad_grid = np.nan_to_num(grad_grid, nan=0.0)

    cross_sum = grad_grid.sum(axis=0)
    cross_sum = smooth_1d(cross_sum, window=3)
    peak_idx = int(np.argmax(cross_sum))
    if peak_idx <= 0 or peak_idx >= len(cross_sum) - 1:
        return None
    median_level = float(np.median(cross_sum))
    if cross_sum[peak_idx] < max(1.4 * median_level, median_level + 5.0):
        return None

    delta = parabolic_peak(cross_sum.tolist(), peak_idx)
    step = float(across[1] - across[0])
    lateral_offset = float(across[peak_idx]) + delta * step
    p1_new = p1a + lateral_offset * n
    p2_new = p2a + lateral_offset * n
    return (float(p1_new[0]), float(p1_new[1])), (float(p2_new[0]), float(p2_new[1]))


def radial_derivative_profile_fixed(
    gray: np.ndarray,
    center: tuple[float, float],
    angle: float,
    radius: float,
    half_width: int,
) -> np.ndarray | None:
    offsets = np.arange(-half_width, half_width + 1, dtype=np.float64)
    radii = radius + offsets
    xs = center[0] + radii * math.cos(angle)
    ys = center[1] + radii * math.sin(angle)
    profile = bilinear_sample(gray, xs, ys)
    if np.isnan(profile).all():
        return None
    if np.isnan(profile).any():
        profile = np.nan_to_num(profile, nan=float(np.nanmedian(profile)))
    profile = smooth_1d(profile, 7)
    return np.diff(profile)


def refine_d46_radial_line(
    model: ShapeModel,
    ref_model: ReferenceModel,
    target_gray: np.ndarray,
    transform: SimilarityTransform,
    is_center_anchor: list[bool],
) -> tuple[list[tuple[float, float]], dict[str, object]] | None:
    if not is_d46_label(model.label):
        return None
    if model.shape_type != "line" or len(model.points) != 2 or sum(is_center_anchor) != 1:
        return None

    endpoint_index = 0 if not is_center_anchor[0] else 1
    center_index = 1 - endpoint_index
    ref_center = np.asarray(ref_model.alignment_center, dtype=np.float64)
    ref_endpoint = np.asarray(model.points[endpoint_index], dtype=np.float64)
    ref_vec = ref_endpoint - ref_center
    ref_radius = float(np.linalg.norm(ref_vec))
    if ref_radius < 100.0:
        return None
    ref_angle = math.atan2(float(ref_vec[1]), float(ref_vec[0]))
    target_center = transform.target_center
    target_angle = ref_angle + transform.rotation
    predicted_radius = ref_radius * transform.scale

    ref_profile = radial_derivative_profile_fixed(
        ref_model.reference_gray,
        (float(ref_center[0]), float(ref_center[1])),
        ref_angle,
        ref_radius,
        D46_RADIAL_TEMPLATE_HALF_WIDTH_PX,
    )
    if ref_profile is None:
        return None

    offsets = list(range(-D46_RADIAL_SEARCH_RANGE_PX, D46_RADIAL_SEARCH_RANGE_PX + 1))
    scores: list[float] = []
    for offset in offsets:
        target_profile = radial_derivative_profile_fixed(
            target_gray,
            target_center,
            target_angle,
            predicted_radius + offset,
            D46_RADIAL_TEMPLATE_HALF_WIDTH_PX,
        )
        if target_profile is None or len(target_profile) != len(ref_profile):
            scores.append(-1.0)
            continue
        scores.append(ncc_score(ref_profile, target_profile))

    best_index = int(np.argmax(scores))
    best_score = float(scores[best_index])
    quality: dict[str, object] = {
        "detect.source": "d46_radial_ncc",
        "quality.d46_reference_radius_ref_px": ref_radius,
        "quality.d46_predicted_radius_px": predicted_radius,
        "quality.d46_ncc_score": best_score,
        "quality.d46_radial_offset_px": offsets[best_index],
        "quality.anomaly_flag": 0.0,
        "quality.anomaly_reason": "",
        "quality.measurement_valid": 1.0,
    }
    if best_score < D46_RADIAL_MIN_NCC_SCORE:
        quality["detect.source"] = "d46_transform_fallback"
        quality["quality.anomaly_flag"] = 1.0
        quality["quality.anomaly_reason"] = "d46_radial_low_score"
        quality["quality.measurement_valid"] = 0.0
        detected_radius = predicted_radius
    else:
        subpixel = parabolic_peak(scores, best_index)
        detected_radius = predicted_radius + float(offsets[best_index]) + subpixel
        quality["quality.d46_radial_offset_px"] = float(offsets[best_index]) + subpixel

    endpoint = (
        target_center[0] + detected_radius * math.cos(target_angle),
        target_center[1] + detected_radius * math.sin(target_angle),
    )
    center_point = target_center
    points = [center_point, center_point]
    points[endpoint_index] = endpoint
    points[center_index] = center_point
    return points, quality


def snap_to_nearby_edge(tgt_grad: np.ndarray, point: tuple[float, float], radius: int = 16) -> tuple[float, float]:
    x, y = point
    x1 = max(0, int(round(x - radius)))
    y1 = max(0, int(round(y - radius)))
    x2 = min(tgt_grad.shape[1], int(round(x + radius + 1)))
    y2 = min(tgt_grad.shape[0], int(round(y + radius + 1)))
    roi = tgt_grad[y1:y2, x1:x2]
    if roi.size == 0:
        return point
    threshold = max(12.0, float(np.percentile(roi, 92)))
    yy, xx = np.where(roi >= threshold)
    if len(xx) == 0:
        return point
    xs = xx + x1
    ys = yy + y1
    dist = (xs - x) * (xs - x) + (ys - y) * (ys - y)
    best = int(np.argmin(dist))
    return float(xs[best]), float(ys[best])


def build_reference_model(annotation_path: Path) -> ReferenceModel:
    annotation = read_labelme(annotation_path)
    reference_path = annotation_path.parent / annotation.get("imagePath", "1 (1).bmp")
    # Smooth once; everything downstream (gradient, sample_radial, NCC) reads
    # the smoothed copy so the noise model is consistent across the pipeline.
    reference_raw = load_gray(reference_path)
    reference_gray = gaussian_blur(reference_raw)
    reference_grad = gradient_magnitude(reference_gray)

    # First pass: parse shapes and fit circles. Templates are built in a
    # second pass below, after we know which circle is outer/inner/middle.
    models: list[ShapeModel] = []
    for shape in annotation.get("shapes", []):
        label = str(shape.get("label", "unnamed"))
        shape_type = str(shape.get("shape_type", "polygon"))
        points = [[float(x), float(y)] for x, y in shape.get("points", [])]
        circle_flag = is_circular_shape(label, shape_type, points)
        if circle_flag:
            pts_arr = np.asarray(points, dtype=np.float64)
            circle = geometric_circle_fit(pts_arr, fit_circle(pts_arr))
        else:
            circle = None
        models.append(ShapeModel(label=label, shape_type=shape_type, points=points, is_circle=circle_flag, circle=circle))

    # Discover roles by geometry: largest circle = outer anchor, smallest =
    # inner hole, the rest are middle rings. This is label-agnostic so the
    # operator's naming convention (ψ, φ, Φ, ⌀, M, plain numeric, …) does
    # not matter.
    circle_models = [m for m in models if m.is_circle and m.circle is not None]
    if len(circle_models) < 2:
        raise ValueError("The annotation must contain at least two circular shapes for cross-position alignment")
    circle_models_sorted = sorted(circle_models, key=lambda m: m.circle[2])
    inner_model = circle_models_sorted[0]
    outer_model = circle_models_sorted[-1]
    inner_circle = inner_model.circle
    outer_circle = outer_model.circle
    outer_label = outer_model.label
    inner_label = inner_model.label
    alignment_center = ((outer_circle[0] + inner_circle[0]) / 2.0, (outer_circle[1] + inner_circle[1]) / 2.0)

    # Second pass: build NCC templates for outer + every middle ring (skip the
    # inner hole — it is detected by the bore-edge detector, not NCC).
    for model in circle_models:
        if model.label == inner_label:
            continue
        role = ROLE_OUTER if model.label == outer_label else ROLE_MIDDLE
        circle = model.circle
        angles = dense_angles_from_points(model.points, circle)
        model.middle_angles = angles
        half_width = template_half_width(role)
        model.middle_template = radial_derivative_template(
            reference_gray, (circle[0], circle[1]), circle[2], angles, half_width
        )

    radius_ratio_to_outer = {
        m.label: m.circle[2] / outer_circle[2]
        for m in circle_models
        if outer_circle[2] > 0
    }

    return ReferenceModel(
        annotation=annotation,
        reference_path=reference_path,
        reference_gray=reference_gray,
        reference_grad=reference_grad,
        shapes=models,
        alignment_center=alignment_center,
        alignment_inner_radius=inner_circle[2],
        alignment_outer_radius=outer_circle[2],
        radius_ratio_to_outer=radius_ratio_to_outer,
        outer_label=outer_label,
        inner_label=inner_label,
    )


def _anchored_target_radius(
    model: ShapeModel,
    transform: SimilarityTransform,
    ref_model: ReferenceModel | None,
    detected: dict[str, tuple[float, float, float]] | None,
) -> float | None:
    # Prior radius pinned to the already-detected outer ring. Concentric
    # machined rings hold their ratio across captures, so anchoring middle
    # rings to the outer is far less noisy than reapplying the global
    # similarity transform — that one inherits any error in the global scale
    # estimate. The outer ring itself is identified by geometry (largest
    # annotated circle), not by a hard-coded label.
    if ref_model is None or detected is None or ref_model.radius_ratio_to_outer is None:
        return None
    if ref_model.outer_label is None:
        return None
    outer = detected.get(ref_model.outer_label)
    if outer is None:
        return None
    ratio = ref_model.radius_ratio_to_outer.get(model.label)
    if ratio is None:
        return None
    return outer[2] * ratio


def detect_outer_anchor_circle(
    model: ShapeModel,
    target_gray: np.ndarray,
    transform: SimilarityTransform,
) -> tuple[float, float, float]:
    circle, _ = detect_outer_anchor_circle_with_quality(model, target_gray, transform)
    return circle


def detect_outer_anchor_circle_with_quality(
    model: ShapeModel,
    target_gray: np.ndarray,
    transform: SimilarityTransform,
) -> tuple[tuple[float, float, float], dict[str, object]]:
    """Detect the outer anchor from a full-circle edge fit.

    The outer circle is the most important radius because every middle ring is
    anchored to it. A previous version reused the same local NCC template logic
    as the middle rings. That template is built only from the manually annotated
    arc, so on sample_2/pos_2 it can lock onto a neighboring edge and push the
    radius to the allowed correction limit. The outer boundary is visible around
    most of the part, so a 720-ray full-circle edge fit is the more stable
    detector here.
    """
    assert model.circle is not None
    predicted_center = transform.apply_point((model.circle[0], model.circle[1]))
    predicted_radius = transform.apply_radius(model.circle[2])
    angles = np.linspace(0.0, 2.0 * math.pi, 720, endpoint=False)
    points: list[tuple[float, float]] = []
    for angle in angles:
        point = outer_boundary_edge_point(target_gray, predicted_center, float(angle), predicted_radius)
        if point is not None:
            points.append(point)
    detected = robust_fit_circle(points, (predicted_center[0], predicted_center[1], predicted_radius))
    finite = all(math.isfinite(value) for value in detected) and detected[2] > 0
    valid = len(points) >= 8 and finite
    if not finite:
        detected = (predicted_center[0], predicted_center[1], predicted_radius)
    quality: dict[str, object] = {
        "detect.source": "outer_boundary_fit" if valid else "outer_boundary_fallback",
        "quality.measurement_valid": 1.0 if valid else 0.0,
        "quality.edge_point_count": float(len(points)),
        "quality.anomaly_flag": 0.0 if valid else 1.0,
        "quality.anomaly_reason": "" if valid else "outer_boundary_insufficient_points",
    }
    return detected, quality


def detect_outer_template_anchor_for_middle(
    model: ShapeModel,
    ref_model: ReferenceModel,
    target_gray: np.ndarray,
    transform: SimilarityTransform,
) -> tuple[float, float, float]:
    """Return the legacy outer template result used only as middle-ring prior.

    Middle rings were tuned against the previous outer-template anchor. Keep
    that anchor for the ratio prior so improving the reported outer radius does
    not unexpectedly move ψ86/ψ80/M78.
    """
    return detect_template_locked_circle(model, target_gray, transform, ref_model, None, role=ROLE_OUTER)


def detect_middle_radial_candidate(
    model: ShapeModel,
    ref_model: ReferenceModel,
    target_gray: np.ndarray,
    transform: SimilarityTransform,
) -> CircleCandidate | None:
    """Full-circle radial edge candidate for middle rings.

    This candidate is intentionally conservative. It starts from the global
    transform radius instead of the older template/outer-anchor result, samples
    the whole circumference, and only returns a result when enough rays agree
    on one clean circle. The caller keeps the legacy template result unless the
    template is clearly drifting away from the annotation-scale prediction.
    """
    assert model.circle is not None
    target_center = transform.apply_point((model.circle[0], model.circle[1]))
    target_radius = transform.apply_radius(model.circle[2])
    angles = np.linspace(0.0, 2.0 * math.pi, 720, endpoint=False)
    polarity = radial_polarity(
        ref_model.reference_gray,
        (model.circle[0], model.circle[1]),
        model.circle[2],
        angles,
    )
    search_width = max(5, int(round(MIDDLE_RADIAL_SEARCH_WIDTH_PX * max(transform.scale, 0.5))))
    points: list[tuple[float, float]] = []
    for angle in angles:
        point = radial_edge_at_angle(target_gray, target_center, float(angle), target_radius, polarity, search_width)
        if point is not None:
            points.append(point)
    if len(points) < MIDDLE_RADIAL_MIN_POINTS:
        return None
    detected = robust_fit_circle(points, (target_center[0], target_center[1], target_radius))
    residual = circular_residual([[x, y] for x, y in points], detected)
    if residual > MIDDLE_RADIAL_MAX_RESIDUAL_PX:
        return None
    return CircleCandidate(detected, len(points), residual)


def detect_template_locked_circle_candidate(
    model: ShapeModel,
    target_gray: np.ndarray,
    transform: SimilarityTransform,
    ref_model: ReferenceModel | None = None,
    detected: dict[str, tuple[float, float, float]] | None = None,
    role: str = ROLE_MIDDLE,
) -> TemplateCandidate:
    assert model.circle is not None
    target_center = transform.apply_point((model.circle[0], model.circle[1]))
    transform_radius = transform.apply_radius(model.circle[2])
    # Only middle rings get a ratio-anchored prior. The outer ring is detected
    # by full-circle fitting in `detect_outer_anchor_circle`, not by this local
    # NCC template path.
    anchored_radius = _anchored_target_radius(model, transform, ref_model, detected) if role == ROLE_MIDDLE else None
    target_radius = anchored_radius if anchored_radius is not None else transform_radius
    if model.middle_template is None or model.middle_angles is None:
        return TemplateCandidate(
            (target_center[0], target_center[1], target_radius),
            target_radius,
            -1.0,
            0.0,
            anchored_radius,
            False,
        )

    half_width = template_half_width(role)
    search_range = template_search_range(role, transform.scale)
    allowed_correction = template_allowed_correction(role, transform.scale)
    # When we have a ratio prior anchored to an already-locked outer, the
    # residual correction is sub-pixel in steady state. Tightening the
    # correction window keeps a neighboring-groove NCC peak from being
    # selected even if it sits within the looser ±14 px default.
    if anchored_radius is not None:
        allowed_correction = min(allowed_correction, 8)
        search_range = min(search_range, 24)
    scores: list[float] = []
    offsets = list(range(-search_range, search_range + 1))
    target_angles = model.middle_angles + transform.rotation
    for offset in offsets:
        scores.append(
            radial_template_ncc_at_radius(
                model.middle_template,
                target_gray,
                target_center,
                target_radius + offset,
                target_angles,
                half_width,
            )
        )
    best_index = int(np.argmax(scores))
    allowed_indices = [idx for idx, offset in enumerate(offsets) if abs(offset) <= allowed_correction]
    if allowed_indices:
        best_index = max(allowed_indices, key=lambda idx: scores[idx])
    best_offset = offsets[best_index] + parabolic_peak(scores, best_index)
    best_offset = float(np.clip(best_offset, -allowed_correction, allowed_correction))
    # Quality gate: when the best in-band score is weak, the template is not
    # actually matching this ring and any offset is noise. Trust the anchored
    # prior instead. Only applied when an anchor exists (i.e. middle rings).
    if anchored_radius is not None and scores[best_index] < 0.35:
        return TemplateCandidate(
            (target_center[0], target_center[1], anchored_radius),
            target_radius,
            scores[best_index],
            0.0,
            anchored_radius,
            True,
        )
    return TemplateCandidate(
        (target_center[0], target_center[1], target_radius + best_offset),
        target_radius,
        scores[best_index],
        best_offset,
        anchored_radius,
        False,
    )


def detect_template_locked_circle(
    model: ShapeModel,
    target_gray: np.ndarray,
    transform: SimilarityTransform,
    ref_model: ReferenceModel | None = None,
    detected: dict[str, tuple[float, float, float]] | None = None,
    role: str = ROLE_MIDDLE,
) -> tuple[float, float, float]:
    return detect_template_locked_circle_candidate(model, target_gray, transform, ref_model, detected, role).circle


def detect_circle_with_quality(
    model: ShapeModel,
    ref_model: ReferenceModel,
    target_gray: np.ndarray,
    transform: SimilarityTransform,
    detected: dict[str, tuple[float, float, float]] | None = None,
) -> tuple[tuple[float, float, float], dict[str, object]]:
    # Dispatch is by geometric role, not by label string. The smallest annotated
    # circle is the inner hole (uses the bore-edge detector); everything else
    # is a ring detected by template NCC, with middle rings additionally
    # anchored to the already-detected outer ring's radius.
    assert model.circle is not None
    role = circle_role(ref_model, model.label)
    if role == ROLE_INNER:
        return detect_inner_hole_circle_with_quality(model, target_gray, transform)
    if role == ROLE_OUTER:
        return detect_outer_anchor_circle_with_quality(model, target_gray, transform)

    template = detect_template_locked_circle_candidate(model, target_gray, transform, ref_model, detected, role=role)
    template_circle = template.circle
    template_radius_ref = transform.inverse_radius(template_circle[2])
    target_radius_ref = transform.inverse_radius(template.target_radius)
    expected_radius_ref = model.circle[2]
    template_deviation = abs(template_radius_ref - expected_radius_ref)
    template_prior_deviation = abs(template_radius_ref - target_radius_ref)
    radial_needed = (
        abs(template.best_offset) >= MIDDLE_TEMPLATE_OFFSET_TRIGGER_PX
        or (template.used_anchor_fallback and template.best_score < MIDDLE_TEMPLATE_LOW_SCORE_TRIGGER)
    )
    quality: dict[str, object] = {
        "detect.source": "template",
        "quality.expected_radius_ref_px": expected_radius_ref,
        "quality.target_radius_ref_px": target_radius_ref,
        "quality.template_radius_ref_px": template_radius_ref,
        "quality.template_deviation_ref_px": template_deviation,
        "quality.template_prior_deviation_ref_px": template_prior_deviation,
        "quality.template_score": template.best_score,
        "quality.template_offset_px": template.best_offset,
        "quality.template_used_anchor_fallback": 1.0 if template.used_anchor_fallback else 0.0,
        "quality.measurement_valid": 0.0 if template.used_anchor_fallback else 1.0,
        "quality.low_confidence_flag": 1.0 if radial_needed else 0.0,
        "quality.radial_triggered": 0.0,
        "quality.radial_available": 0.0,
        "quality.radial_point_count": 0.0,
        "quality.radial_residual_px": "",
        "quality.radial_radius_ref_px": "",
        "quality.radial_deviation_ref_px": "",
        "quality.radial_prior_deviation_ref_px": "",
        "quality.anomaly_flag": 1.0 if template.used_anchor_fallback else 0.0,
        "quality.anomaly_reason": "template_anchor_fallback" if template.used_anchor_fallback else "",
    }
    if not radial_needed:
        return template_circle, quality

    quality["quality.radial_triggered"] = 1.0
    radial_candidate = detect_middle_radial_candidate(model, ref_model, target_gray, transform)
    if radial_candidate is None:
        return template_circle, quality

    radial_radius_ref = transform.inverse_radius(radial_candidate.circle[2])
    radial_deviation = abs(radial_radius_ref - expected_radius_ref)
    radial_prior_deviation = abs(radial_radius_ref - target_radius_ref)
    quality.update({
        "quality.radial_available": 1.0,
        "quality.radial_point_count": float(radial_candidate.point_count),
        "quality.radial_residual_px": radial_candidate.median_residual,
        "quality.radial_radius_ref_px": radial_radius_ref,
        "quality.radial_deviation_ref_px": radial_deviation,
        "quality.radial_prior_deviation_ref_px": radial_prior_deviation,
    })

    # Keep the tuned template path for normal images. Switch only when the
    # template has moved to the edge of its allowed local correction window and
    # the full-circle edge fit is clearly closer to the same radius prior. This
    # avoids treating a real sample-to-sample radius difference as an anomaly.
    if (
        template_prior_deviation > MIDDLE_TEMPLATE_DEVIATION_GATE_REF_PX
        and radial_prior_deviation + 1.0 < template_prior_deviation
    ):
        quality["detect.source"] = "radial"
        quality["quality.measurement_valid"] = 1.0
        quality["quality.anomaly_flag"] = 0.0
        quality["quality.anomaly_reason"] = ""
        return radial_candidate.circle, quality
    return template_circle, quality


def detect_circle(
    model: ShapeModel,
    ref_model: ReferenceModel,
    target_gray: np.ndarray,
    transform: SimilarityTransform,
    detected: dict[str, tuple[float, float, float]] | None = None,
) -> tuple[float, float, float]:
    circle, _ = detect_circle_with_quality(model, ref_model, target_gray, transform, detected)
    return circle


def detect_non_circle_points_with_quality(
    model: ShapeModel,
    ref_model: ReferenceModel,
    target_gray: np.ndarray,
    target_grad: np.ndarray,
    transform: SimilarityTransform,
) -> tuple[list[tuple[float, float]], dict[str, object]]:
    if not model.points:
        return [], {}

    # Endpoints that the annotator intended as "the disk center". Manual
    # clicks are imprecise (the "46" radial dimension's inner endpoint sits
    # 97 px away from center in the labelme file), but any endpoint well
    # inside the inner hole can only mean the center. Anchor it to the
    # detected target center, and skip the NCC + edge-snap refinement
    # because the inner hole has no usable gradient feature.
    center_anchor_radius = ref_model.alignment_inner_radius * 0.2
    rcx, rcy = ref_model.alignment_center
    is_center_anchor = [
        math.hypot(x - rcx, y - rcy) < center_anchor_radius for x, y in model.points
    ]

    transformed: list[tuple[float, float]] = []
    for (x, y), anchor in zip(model.points, is_center_anchor):
        if anchor:
            transformed.append(transform.target_center)
        else:
            transformed.append(transform.apply_point((x, y)))

    if model.shape_type == "line":
        d46_refined = refine_d46_radial_line(model, ref_model, target_gray, transform, is_center_anchor)
        if d46_refined is not None:
            return d46_refined

        # Short lines (≤ 80 px): the annotation marks an edge whose true
        # endpoints are ambiguous, so per-endpoint NCC + snap is unstable.
        # Use a coupled refinement that only fixes the lateral offset.
        if (
            len(transformed) == 2
            and not any(is_center_anchor)
            and math.hypot(
                transformed[1][0] - transformed[0][0],
                transformed[1][1] - transformed[0][1],
            )
            <= 80.0
        ):
            refined_pair = refine_short_line(target_grad, transformed[0], transformed[1])
            if refined_pair is not None:
                return list(refined_pair), {
                    "detect.source": "short_line_lateral_edge",
                    "quality.measurement_valid": 1.0,
                    "quality.anomaly_flag": 0.0,
                    "quality.anomaly_reason": "",
                }
            return list(transformed), {
                "detect.source": "short_line_transform_fallback",
                "quality.measurement_valid": 0.0,
                "quality.anomaly_flag": 1.0,
                "quality.anomaly_reason": "short_line_lateral_edge_not_found",
            }
        refined: list[tuple[float, float]] = []
        for ref_point, predicted, anchor in zip(model.points, transformed, is_center_anchor):
            if anchor:
                refined.append(predicted)
                continue
            matched = refine_point_by_template(ref_model.reference_grad, target_grad, tuple(ref_point), predicted)
            refined.append(snap_to_nearby_edge(target_grad, matched, radius=24))
        return refined, {
            "detect.source": "line_endpoint_template_edge",
            "quality.measurement_valid": 1.0,
            "quality.anomaly_flag": 0.0,
            "quality.anomaly_reason": "",
        }

    if model.shape_type == "linestrip" and len(model.points) <= 6:
        return [
            predicted if anchor else refine_point_by_template(ref_model.reference_grad, target_grad, tuple(ref), predicted)
            for ref, predicted, anchor in zip(model.points, transformed, is_center_anchor)
        ], {
            "detect.source": "linestrip_template",
            "quality.measurement_valid": 1.0,
            "quality.anomaly_flag": 0.0,
            "quality.anomaly_reason": "",
        }

    return transformed, {}


def detect_non_circle_points(
    model: ShapeModel,
    ref_model: ReferenceModel,
    target_grad: np.ndarray,
    transform: SimilarityTransform,
) -> list[tuple[float, float]]:
    points, _ = detect_non_circle_points_with_quality(
        model,
        ref_model,
        ref_model.reference_gray,
        target_grad,
        transform,
    )
    return points


def polygon_area(points: list[tuple[float, float]]) -> float:
    if len(points) < 3:
        return 0.0
    area = 0.0
    for idx, (x1, y1) in enumerate(points):
        x2, y2 = points[(idx + 1) % len(points)]
        area += x1 * y2 - x2 * y1
    return abs(area) / 2.0


def line_metrics(points: list[tuple[float, float]]) -> dict[str, float]:
    if len(points) < 2:
        return {}
    x1, y1 = points[0]
    x2, y2 = points[-1]
    return {
        "x1": x1,
        "y1": y1,
        "x2": x2,
        "y2": y2,
        "length": math.hypot(x2 - x1, y2 - y1),
        "angle_deg": math.degrees(math.atan2(y2 - y1, x2 - x1)),
    }


def polygon_metrics(points: list[tuple[float, float]]) -> dict[str, float]:
    if not points:
        return {}
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return {
        "centroid_x": float(np.mean(xs)),
        "centroid_y": float(np.mean(ys)),
        "bbox_width": max(xs) - min(xs),
        "bbox_height": max(ys) - min(ys),
        "area": polygon_area(points),
    }


def load_detection_gray(image_path: Path) -> np.ndarray:
    return gaussian_blur(load_gray(image_path))


def load_visual_font(size: int) -> ImageFont.ImageFont:
    for path in (
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ):
        try:
            return ImageFont.truetype(path, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def quality_measurement_valid(quality: dict[str, object]) -> bool:
    value = quality.get("quality.measurement_valid")
    if value in (None, ""):
        return True
    try:
        return float(value) > 0.5
    except (TypeError, ValueError):
        return True


def draw_text_label(
    draw: ImageDraw.ImageDraw,
    xy: tuple[float, float],
    text: str,
    font: ImageFont.ImageFont,
    fill: tuple[int, int, int, int],
) -> None:
    x, y = xy
    lines = text.splitlines()
    boxes = [draw.textbbox((0, 0), line, font=font) for line in lines]
    width = max((box[2] - box[0] for box in boxes), default=0)
    line_height = max((box[3] - box[1] for box in boxes), default=12) + 6
    pad = 8
    draw.rectangle(
        [x, y, x + width + 2 * pad, y + line_height * len(lines) + 2 * pad],
        fill=(0, 0, 0, 170),
    )
    for idx, line in enumerate(lines):
        draw.text((x + pad, y + pad + idx * line_height), line, font=font, fill=fill)


def draw_center_cross(
    draw: ImageDraw.ImageDraw,
    center: tuple[float, float],
    color: tuple[int, int, int, int],
    size: int,
    width: int,
) -> None:
    x, y = center
    draw.line([(x - size, y), (x + size, y)], fill=color, width=width)
    draw.line([(x, y - size), (x, y + size)], fill=color, width=width)


def visualization_color(model: ShapeModel, ref_model: ReferenceModel, valid: bool) -> tuple[int, int, int, int]:
    if not valid:
        return 255, 50, 50, 235
    if model.is_circle:
        role = circle_role(ref_model, model.label)
        if role == ROLE_OUTER:
            return 50, 190, 255, 230
        if role == ROLE_INNER:
            return 255, 80, 210, 230
        return 90, 235, 120, 230
    return 255, 210, 50, 230


def visualize_detection(
    ref_model: ReferenceModel,
    image_path: Path,
    output_path: Path,
    pixel_size: float = 1.0,
) -> tuple[Path, int]:
    target_raw = load_gray(image_path)
    target_gray = gaussian_blur(target_raw)
    target_grad = gradient_magnitude(target_gray)
    transform = estimate_global_transform(ref_model, target_gray)

    base = Image.open(image_path).convert("RGB")
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    font = load_visual_font(max(24, base.width // 190))
    small_font = load_visual_font(max(18, base.width // 260))
    width = max(3, base.width // 900)
    label_offset = max(12, base.width // 260)
    invalid_count = 0

    detected_circles: dict[str, tuple[float, float, float]] = {}
    outer_label = ref_model.outer_label
    ordered_shapes = sorted(
        ref_model.shapes,
        key=lambda s: 0 if (s.is_circle and outer_label is not None and s.label == outer_label) else 1,
    )

    for model in ordered_shapes:
        if model.is_circle:
            role = circle_role(ref_model, model.label)
            if role == ROLE_OUTER:
                anchor_circle = detect_outer_template_anchor_for_middle(model, ref_model, target_gray, transform)
                circle, quality = detect_outer_anchor_circle_with_quality(model, target_gray, transform)
                detected_circles[model.label] = anchor_circle
            else:
                circle, quality = detect_circle_with_quality(model, ref_model, target_gray, transform, detected_circles)
                detected_circles[model.label] = circle
            valid = quality_measurement_valid(quality)
            invalid_count += 0 if valid else 1
            color = visualization_color(model, ref_model, valid)
            cx, cy, radius = circle
            draw.ellipse([cx - radius, cy - radius, cx + radius, cy + radius], outline=color, width=width)
            draw_center_cross(draw, (cx, cy), color, max(8, width * 3), max(2, width // 2))
            radius_ref = transform.inverse_radius(radius)
            value = radius_ref * pixel_size if pixel_size != 1.0 else radius_ref
            unit = "unit" if pixel_size != 1.0 else "ref_px"
            reason = str(quality.get("quality.anomaly_reason") or "")
            label = f"{model.label} r={value:.3f} {unit}"
            if not valid:
                label += f"\ninvalid: {reason or quality.get('detect.source', '')}"
            draw_text_label(draw, (cx + radius + label_offset, cy - label_offset), label, small_font, color)
            continue

        points, quality = detect_non_circle_points_with_quality(model, ref_model, target_gray, target_grad, transform)
        if not points:
            continue
        valid = quality_measurement_valid(quality)
        invalid_count += 0 if valid else 1
        color = visualization_color(model, ref_model, valid)
        if model.shape_type == "polygon" and len(points) >= 3:
            draw.line(points + [points[0]], fill=color, width=width)
            centroid = (float(np.mean([p[0] for p in points])), float(np.mean([p[1] for p in points])))
            metric_text = f"{model.label}"
        else:
            draw.line(points, fill=color, width=width)
            for point in points:
                draw.ellipse(
                    [point[0] - width * 2, point[1] - width * 2, point[0] + width * 2, point[1] + width * 2],
                    fill=color,
                )
            centroid = points[0]
            ref_points = [transform.inverse_point(point) for point in points]
            metrics = line_metrics(ref_points)
            if "length" in metrics:
                length = metrics["length"] * pixel_size if pixel_size != 1.0 else metrics["length"]
                unit = "unit" if pixel_size != 1.0 else "ref_px"
                metric_text = f"{model.label} L={length:.3f} {unit}"
            else:
                metric_text = f"{model.label}"
        reason = str(quality.get("quality.anomaly_reason") or "")
        if not valid:
            metric_text += f"\ninvalid: {reason or quality.get('detect.source', '')}"
        draw_text_label(draw, (centroid[0] + label_offset, centroid[1] + label_offset), metric_text, small_font, color)

    header_lines = [
        f"image: {image_path.name}",
        "mode: raw detection visualization",
        f"scale: {transform.scale:.8f}",
        f"rotation: {math.degrees(transform.rotation):.5f} deg",
        f"invalid features: {invalid_count}",
    ]
    draw_text_label(draw, (24, 24), "\n".join(header_lines), font, (255, 255, 255, 245))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    Image.alpha_composite(base.convert("RGBA"), overlay).convert("RGB").save(output_path)
    return output_path, invalid_count


def prepare_position_locked_transforms(
    ref_model: ReferenceModel,
    records: list[ImageRecord],
    gate_deg: float,
) -> dict[Path, PreparedTransform]:
    prepared: dict[Path, PreparedTransform] = {}
    grouped: dict[tuple[str, str], list[float]] = {}
    for record in records:
        target_gray = load_detection_gray(record.image_path)
        transform = estimate_global_transform(ref_model, target_gray)
        prepared[record.image_path] = PreparedTransform(
            transform=transform,
            raw_rotation=transform.rotation,
            rotation_median=None,
            rotation_correction=0.0,
            rotation_locked=False,
        )
        grouped.setdefault((record.sample, record.position), []).append(transform.rotation)

    medians = {
        key: circular_median(angles)
        for key, angles in grouped.items()
        if len(angles) >= 3
    }
    if gate_deg <= 0.0:
        return prepared

    gate_rad = math.radians(gate_deg)
    corrected: dict[Path, PreparedTransform] = {}
    for record in records:
        item = prepared[record.image_path]
        median_rotation = medians.get((record.sample, record.position))
        if median_rotation is None:
            corrected[record.image_path] = item
            continue
        correction = angle_delta(median_rotation, item.raw_rotation)
        locked = abs(correction) > gate_rad
        transform = item.transform
        if locked:
            note = (
                "position_rotation_lock("
                f"raw={math.degrees(item.raw_rotation):.5f}deg, "
                f"median={math.degrees(median_rotation):.5f}deg, "
                f"correction={math.degrees(correction):+.5f}deg)"
            )
            transform = replace_transform_rotation(transform, median_rotation, note)
        corrected[record.image_path] = PreparedTransform(
            transform=transform,
            raw_rotation=item.raw_rotation,
            rotation_median=median_rotation,
            rotation_correction=correction if locked else 0.0,
            rotation_locked=locked,
        )
    return corrected


def detect_measurements(
    ref_model: ReferenceModel,
    image_path: Path,
    pixel_size: float,
    prepared_transform: PreparedTransform | None = None,
) -> tuple[dict[str, float], str]:
    target_raw = load_gray(image_path)
    target_gray = gaussian_blur(target_raw)
    target_grad = gradient_magnitude(target_gray)
    transform = prepared_transform.transform if prepared_transform is not None else estimate_global_transform(ref_model, target_gray)

    metrics: dict[str, float] = {
        "transform.target_center_x_px": transform.target_center[0],
        "transform.target_center_y_px": transform.target_center[1],
        "transform.scale": transform.scale,
        "transform.rotation_deg": math.degrees(transform.rotation),
    }
    if prepared_transform is not None:
        metrics["transform.raw_rotation_deg"] = math.degrees(prepared_transform.raw_rotation)
        metrics["transform.position_median_rotation_deg"] = (
            math.degrees(prepared_transform.rotation_median)
            if prepared_transform.rotation_median is not None
            else math.degrees(prepared_transform.raw_rotation)
        )
        metrics["transform.rotation_correction_deg"] = math.degrees(prepared_transform.rotation_correction)
        metrics["transform.rotation_locked"] = 1.0 if prepared_transform.rotation_locked else 0.0
    detected_circles: dict[str, tuple[float, float, float]] = {}
    # Detect the outer anchor first regardless of JSON shape order so later
    # middle-ring detections can pin their priors to it. The outer anchor is
    # identified by geometric role, not by a hard-coded label string.
    outer_label = ref_model.outer_label
    ordered_shapes = sorted(
        ref_model.shapes,
        key=lambda s: 0 if (s.is_circle and outer_label is not None and s.label == outer_label) else 1,
    )
    for model in ordered_shapes:
        prefix = model.label
        if model.is_circle:
            role = circle_role(ref_model, model.label)
            if role == ROLE_OUTER:
                # Report the robust full-boundary outer circle, but keep the
                # legacy template result as the middle-ring ratio anchor to
                # avoid changing already-tuned ψ86/ψ80/M78 behavior.
                anchor_circle = detect_outer_template_anchor_for_middle(model, ref_model, target_gray, transform)
                (cx, cy, radius), quality = detect_outer_anchor_circle_with_quality(model, target_gray, transform)
                for name, value in quality.items():
                    metrics[f"{prefix}.{name}"] = value
                detected_circles[model.label] = anchor_circle
            else:
                (cx, cy, radius), quality = detect_circle_with_quality(
                    model, ref_model, target_gray, transform, detected_circles
                )
                for name, value in quality.items():
                    metrics[f"{prefix}.{name}"] = value
                detected_circles[model.label] = (cx, cy, radius)
            cx_ref, cy_ref = transform.inverse_point((cx, cy))
            radius_ref = transform.inverse_radius(radius)
            metrics[f"{prefix}.cx_px"] = cx
            metrics[f"{prefix}.cy_px"] = cy
            metrics[f"{prefix}.radius_px"] = radius
            metrics[f"{prefix}.diameter_px"] = 2.0 * radius
            metrics[f"{prefix}.cx_ref_px"] = cx_ref
            metrics[f"{prefix}.cy_ref_px"] = cy_ref
            metrics[f"{prefix}.radius_ref_px"] = radius_ref
            metrics[f"{prefix}.diameter_ref_px"] = 2.0 * radius_ref
            if pixel_size != 1.0:
                metrics[f"{prefix}.radius_ref_unit"] = radius_ref * pixel_size
                metrics[f"{prefix}.diameter_ref_unit"] = 2.0 * radius_ref * pixel_size
            continue

        points, quality = detect_non_circle_points_with_quality(model, ref_model, target_gray, target_grad, transform)
        for name, value in quality.items():
            metrics[f"{prefix}.{name}"] = value
        ref_points = [transform.inverse_point(point) for point in points]
        if model.shape_type == "line" or (model.shape_type == "linestrip" and len(points) <= 6):
            for name, value in line_metrics(points).items():
                metrics[f"{prefix}.{name}_px" if name not in {"angle_deg"} else f"{prefix}.{name}"] = value
            ref_line = line_metrics(ref_points)
            for name, value in ref_line.items():
                if name == "angle_deg":
                    metrics[f"{prefix}.angle_ref_deg"] = value
                else:
                    metrics[f"{prefix}.{name}_ref_px"] = value
            if pixel_size != 1.0 and len(ref_points) >= 2:
                metrics[f"{prefix}.length_ref_unit"] = ref_line["length"] * pixel_size
        elif model.shape_type == "polygon":
            for name, value in polygon_metrics(points).items():
                metrics[f"{prefix}.{name}_px"] = value
            ref_poly = polygon_metrics(ref_points)
            for name, value in ref_poly.items():
                metrics[f"{prefix}.{name}_ref_px"] = value
            if pixel_size != 1.0:
                metrics[f"{prefix}.bbox_width_ref_unit"] = ref_poly["bbox_width"] * pixel_size
                metrics[f"{prefix}.bbox_height_ref_unit"] = ref_poly["bbox_height"] * pixel_size
                metrics[f"{prefix}.area_ref_unit2"] = ref_poly["area"] * pixel_size * pixel_size

    return metrics, transform.method


def principal_cluster(values: list[float], window: float) -> tuple[float, float, float, int] | None:
    if not values:
        return None
    ordered = sorted(values)
    best_start = 0
    best_end = 1
    for start in range(len(ordered)):
        end = start
        while end < len(ordered) and ordered[end] - ordered[start] <= window:
            end += 1
        current_count = end - start
        best_count = best_end - best_start
        current_width = ordered[end - 1] - ordered[start]
        best_width = ordered[best_end - 1] - ordered[best_start]
        if current_count > best_count or (current_count == best_count and current_width < best_width):
            best_start = start
            best_end = end
    cluster_values = ordered[best_start:best_end]
    return (
        float(statistics.median(cluster_values)),
        cluster_values[0],
        cluster_values[-1],
        len(cluster_values),
    )


def append_reason(existing: object, reason: str) -> str:
    text = str(existing or "")
    if not text:
        return reason
    if reason in text.split(";"):
        return text
    return f"{text};{reason}"


def read_float(row: dict[str, object], key: str) -> float | None:
    value = row.get(key)
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def update_circle_radius_metrics(row: dict[str, object], label: str, radius_ref: float, pixel_size: float) -> None:
    scale = read_float(row, "transform.scale") or 1.0
    radius_px = radius_ref * scale
    row[f"{label}.radius_ref_px"] = radius_ref
    row[f"{label}.diameter_ref_px"] = 2.0 * radius_ref
    row[f"{label}.radius_px"] = radius_px
    row[f"{label}.diameter_px"] = 2.0 * radius_px
    if pixel_size != 1.0:
        row[f"{label}.radius_ref_unit"] = radius_ref * pixel_size
        row[f"{label}.diameter_ref_unit"] = 2.0 * radius_ref * pixel_size


def stabilize_middle_circle_position_clusters(
    ref_model: ReferenceModel,
    rows: list[dict[str, object]],
    pixel_size: float,
) -> None:
    """Suppress position-local ring-edge jumps without hiding the decision.

    A repeated set at one position should land on one radius cluster. When the
    local template jumps to a neighboring groove, the result forms a secondary
    plateau. We mark the row as anomalous and replace only those outliers with
    the position's principal cluster center, keeping the flag in measurements
    and in detection_anomalies.csv.
    """
    middle_labels = [
        model.label
        for model in ref_model.shapes
        if model.is_circle and circle_role(ref_model, model.label) == ROLE_MIDDLE
    ]
    groups: dict[tuple[str, str], list[dict[str, object]]] = {}
    for row in rows:
        groups.setdefault((str(row["sample"]), str(row["position"])), []).append(row)

    for label in middle_labels:
        metric = f"{label}.radius_ref_px"
        for group_rows in groups.values():
            values = [value for row in group_rows if (value := read_float(row, metric)) is not None]
            if len(values) < 5:
                continue
            full_range = max(values) - min(values)
            cluster = principal_cluster(values, POSITION_CLUSTER_WINDOW_REF_PX)
            if cluster is None:
                continue
            center, cluster_min, cluster_max, cluster_count = cluster
            min_count = max(3, int(math.ceil(len(values) * POSITION_CLUSTER_MIN_FRACTION)))
            for row in group_rows:
                value = read_float(row, metric)
                if value is None:
                    continue
                deviation = abs(value - center)
                row[f"{label}.quality.position_cluster_center_ref_px"] = center
                row[f"{label}.quality.position_cluster_min_ref_px"] = cluster_min
                row[f"{label}.quality.position_cluster_max_ref_px"] = cluster_max
                row[f"{label}.quality.position_cluster_count"] = float(cluster_count)
                row[f"{label}.quality.position_cluster_deviation_ref_px"] = deviation
                row[f"{label}.quality.position_cluster_locked"] = 0.0

                if full_range <= POSITION_CLUSTER_ENABLE_RANGE_REF_PX:
                    continue
                if cluster_count < min_count:
                    continue
                if deviation <= POSITION_CLUSTER_OUTLIER_GATE_REF_PX:
                    continue

                # Prefer a physically detected alternate candidate when it is
                # closer to the principal cluster. If none is available, lock
                # the radius to the cluster center and keep the anomaly flag.
                best_radius = value
                best_source = str(row.get(f"{label}.detect.source") or "current")
                candidates: list[tuple[str, float]] = [("current", value)]
                template_radius = read_float(row, f"{label}.quality.template_radius_ref_px")
                radial_radius = read_float(row, f"{label}.quality.radial_radius_ref_px")
                if template_radius is not None:
                    candidates.append(("template", template_radius))
                if radial_radius is not None:
                    candidates.append(("radial", radial_radius))
                for source, candidate in candidates:
                    if abs(candidate - center) < abs(best_radius - center):
                        best_source = source
                        best_radius = candidate

                if abs(best_radius - center) > POSITION_CLUSTER_OUTLIER_GATE_REF_PX:
                    best_source = "position_cluster"
                    best_radius = center

                update_circle_radius_metrics(row, label, best_radius, pixel_size)
                row[f"{label}.detect.source"] = best_source
                row[f"{label}.quality.position_cluster_locked"] = 1.0
                row[f"{label}.quality.anomaly_flag"] = 1.0
                row[f"{label}.quality.anomaly_reason"] = append_reason(
                    row.get(f"{label}.quality.anomaly_reason"),
                    "position_cluster_outlier",
                )


def update_d46_endpoint_metrics(row: dict[str, object], length_ref: float) -> None:
    scale = read_float(row, "transform.scale") or 1.0
    x1 = read_float(row, "46.x1_ref_px")
    y1 = read_float(row, "46.y1_ref_px")
    x2 = read_float(row, "46.x2_ref_px")
    y2 = read_float(row, "46.y2_ref_px")
    tx1 = read_float(row, "46.x1_px")
    ty1 = read_float(row, "46.y1_px")
    tx2 = read_float(row, "46.x2_px")
    ty2 = read_float(row, "46.y2_px")
    if None in (x1, y1, x2, y2, tx1, ty1, tx2, ty2):
        row["46.length_ref_px"] = length_ref
        row["46.length_px"] = length_ref * scale
        return

    ref_points = [(x1, y1), (x2, y2)]
    target_points = [(tx1, ty1), (tx2, ty2)]
    # Current d46 annotation uses point 2 as the center anchor and point 1 as
    # the edge endpoint. Keep that order so downstream reports remain stable.
    center_index = 1
    endpoint_index = 0

    center_ref = np.asarray(ref_points[center_index], dtype=np.float64)
    endpoint_ref = np.asarray(ref_points[endpoint_index], dtype=np.float64)
    ref_vec = endpoint_ref - center_ref
    ref_len = float(np.linalg.norm(ref_vec))
    if ref_len > 1e-6:
        endpoint_ref = center_ref + ref_vec / ref_len * length_ref
        ref_points[endpoint_index] = (float(endpoint_ref[0]), float(endpoint_ref[1]))

    center_target = np.asarray(target_points[center_index], dtype=np.float64)
    endpoint_target = np.asarray(target_points[endpoint_index], dtype=np.float64)
    target_vec = endpoint_target - center_target
    target_len = float(np.linalg.norm(target_vec))
    if target_len > 1e-6:
        endpoint_target = center_target + target_vec / target_len * (length_ref * scale)
        target_points[endpoint_index] = (float(endpoint_target[0]), float(endpoint_target[1]))

    row["46.x1_ref_px"], row["46.y1_ref_px"] = ref_points[0]
    row["46.x2_ref_px"], row["46.y2_ref_px"] = ref_points[1]
    row["46.x1_px"], row["46.y1_px"] = target_points[0]
    row["46.x2_px"], row["46.y2_px"] = target_points[1]
    row["46.length_ref_px"] = length_ref
    row["46.length_px"] = length_ref * scale
    row["46.angle_ref_deg"] = math.degrees(math.atan2(
        ref_points[1][1] - ref_points[0][1],
        ref_points[1][0] - ref_points[0][0],
    ))
    row["46.angle_deg"] = math.degrees(math.atan2(
        target_points[1][1] - target_points[0][1],
        target_points[1][0] - target_points[0][0],
    ))


def update_line_length_metrics(row: dict[str, object], label: str, length_ref: float, pixel_size: float) -> None:
    scale = read_float(row, "transform.scale") or 1.0
    prefix = f"{label}."
    x1 = read_float(row, f"{prefix}x1_ref_px")
    y1 = read_float(row, f"{prefix}y1_ref_px")
    x2 = read_float(row, f"{prefix}x2_ref_px")
    y2 = read_float(row, f"{prefix}y2_ref_px")
    tx1 = read_float(row, f"{prefix}x1_px")
    ty1 = read_float(row, f"{prefix}y1_px")
    tx2 = read_float(row, f"{prefix}x2_px")
    ty2 = read_float(row, f"{prefix}y2_px")

    row[f"{prefix}length_ref_px"] = length_ref
    row[f"{prefix}length_px"] = length_ref * scale
    if pixel_size != 1.0:
        row[f"{prefix}length_ref_unit"] = length_ref * pixel_size

    if None in (x1, y1, x2, y2):
        return

    ref_mid = np.array([(x1 + x2) * 0.5, (y1 + y2) * 0.5], dtype=np.float64)
    ref_vec = np.array([x2 - x1, y2 - y1], dtype=np.float64)
    ref_len = float(np.linalg.norm(ref_vec))
    if ref_len > 1e-6:
        ref_unit = ref_vec / ref_len
        half_vec = ref_unit * (length_ref * 0.5)
        ref_p1 = ref_mid - half_vec
        ref_p2 = ref_mid + half_vec
        row[f"{prefix}x1_ref_px"] = float(ref_p1[0])
        row[f"{prefix}y1_ref_px"] = float(ref_p1[1])
        row[f"{prefix}x2_ref_px"] = float(ref_p2[0])
        row[f"{prefix}y2_ref_px"] = float(ref_p2[1])
        row[f"{prefix}angle_ref_deg"] = math.degrees(math.atan2(float(ref_unit[1]), float(ref_unit[0])))

    if None in (tx1, ty1, tx2, ty2):
        return

    target_mid = np.array([(tx1 + tx2) * 0.5, (ty1 + ty2) * 0.5], dtype=np.float64)
    target_vec = np.array([tx2 - tx1, ty2 - ty1], dtype=np.float64)
    target_len = float(np.linalg.norm(target_vec))
    if target_len <= 1e-6:
        return
    target_unit = target_vec / target_len
    half_target_vec = target_unit * (length_ref * scale * 0.5)
    target_p1 = target_mid - half_target_vec
    target_p2 = target_mid + half_target_vec
    row[f"{prefix}x1_px"] = float(target_p1[0])
    row[f"{prefix}y1_px"] = float(target_p1[1])
    row[f"{prefix}x2_px"] = float(target_p2[0])
    row[f"{prefix}y2_px"] = float(target_p2[1])
    row[f"{prefix}angle_deg"] = math.degrees(math.atan2(float(target_unit[1]), float(target_unit[0])))


def stabilize_line20_position_clusters(
    ref_model: ReferenceModel,
    rows: list[dict[str, object]],
    pixel_size: float,
) -> None:
    labels = [
        model.label
        for model in ref_model.shapes
        if model.shape_type == "line" and is_line20_label(model.label)
    ]
    if not labels:
        return

    groups: dict[tuple[str, str], list[dict[str, object]]] = {}
    for row in rows:
        groups.setdefault((str(row["sample"]), str(row["position"])), []).append(row)

    for label in labels:
        metric = f"{label}.length_ref_px"
        for group_rows in groups.values():
            values = [value for row in group_rows if (value := read_float(row, metric)) is not None]
            if len(values) < 5:
                continue
            full_range = max(values) - min(values)
            cluster = principal_cluster(values, LINE20_POSITION_CLUSTER_WINDOW_REF_PX)
            if cluster is None:
                continue
            center, cluster_min, cluster_max, cluster_count = cluster
            min_count = max(3, int(math.ceil(len(values) * LINE20_POSITION_CLUSTER_MIN_FRACTION)))
            for row in group_rows:
                value = read_float(row, metric)
                if value is None:
                    continue
                deviation = abs(value - center)
                row[f"{label}.quality.position_cluster_center_ref_px"] = center
                row[f"{label}.quality.position_cluster_min_ref_px"] = cluster_min
                row[f"{label}.quality.position_cluster_max_ref_px"] = cluster_max
                row[f"{label}.quality.position_cluster_count"] = float(cluster_count)
                row[f"{label}.quality.position_cluster_deviation_ref_px"] = deviation
                row[f"{label}.quality.position_cluster_locked"] = 0.0

                if full_range <= LINE20_POSITION_CLUSTER_ENABLE_RANGE_REF_PX:
                    continue
                if cluster_count < min_count:
                    continue
                if deviation <= LINE20_POSITION_CLUSTER_OUTLIER_GATE_REF_PX:
                    continue

                update_line_length_metrics(row, label, center, pixel_size)
                row[f"{label}.detect.source"] = "line20_position_cluster"
                row[f"{label}.quality.position_cluster_locked"] = 1.0
                row[f"{label}.quality.anomaly_flag"] = 1.0
                row[f"{label}.quality.anomaly_reason"] = append_reason(
                    row.get(f"{label}.quality.anomaly_reason"),
                    "line20_position_cluster_outlier",
                )


def stabilize_d46_position_clusters(rows: list[dict[str, object]]) -> None:
    metric = "46.length_ref_px"
    groups: dict[tuple[str, str], list[dict[str, object]]] = {}
    for row in rows:
        if read_float(row, metric) is not None:
            groups.setdefault((str(row["sample"]), str(row["position"])), []).append(row)

    for group_rows in groups.values():
        values = [value for row in group_rows if (value := read_float(row, metric)) is not None]
        if len(values) < 5:
            continue
        full_range = max(values) - min(values)
        cluster = principal_cluster(values, D46_POSITION_CLUSTER_WINDOW_REF_PX)
        if cluster is None:
            continue
        center, cluster_min, cluster_max, cluster_count = cluster
        min_count = max(3, int(math.ceil(len(values) * D46_POSITION_CLUSTER_MIN_FRACTION)))
        for row in group_rows:
            value = read_float(row, metric)
            if value is None:
                continue
            deviation = abs(value - center)
            row["46.quality.position_cluster_center_ref_px"] = center
            row["46.quality.position_cluster_min_ref_px"] = cluster_min
            row["46.quality.position_cluster_max_ref_px"] = cluster_max
            row["46.quality.position_cluster_count"] = float(cluster_count)
            row["46.quality.position_cluster_deviation_ref_px"] = deviation
            row["46.quality.position_cluster_locked"] = 0.0
            if full_range <= D46_POSITION_CLUSTER_ENABLE_RANGE_REF_PX:
                continue
            if cluster_count < min_count:
                continue
            if deviation <= D46_POSITION_CLUSTER_OUTLIER_GATE_REF_PX:
                continue

            update_d46_endpoint_metrics(row, center)
            row["46.detect.source"] = "d46_position_cluster"
            row["46.quality.position_cluster_locked"] = 1.0
            row["46.quality.anomaly_flag"] = 1.0
            row["46.quality.anomaly_reason"] = append_reason(
                row.get("46.quality.anomaly_reason"),
                "d46_position_cluster_outlier",
            )


def detection_anomaly_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    anomalies: list[dict[str, object]] = []
    for row in rows:
        for key, value in row.items():
            if not key.endswith(".quality.anomaly_flag"):
                continue
            try:
                is_anomaly = float(value) > 0.5
            except (TypeError, ValueError):
                is_anomaly = False
            if not is_anomaly:
                continue
            label = key[: -len(".quality.anomaly_flag")]
            anomalies.append({
                "sample": row.get("sample"),
                "position": row.get("position"),
                "repeat": row.get("repeat"),
                "image": row.get("image"),
                "feature": label,
                "source": row.get(f"{label}.detect.source"),
                "reason": row.get(f"{label}.quality.anomaly_reason"),
                "measurement_valid": row.get(f"{label}.quality.measurement_valid"),
                "radius_ref_px": row.get(f"{label}.radius_ref_px"),
                "length_ref_px": row.get(f"{label}.length_ref_px"),
                "template_radius_ref_px": row.get(f"{label}.quality.template_radius_ref_px"),
                "radial_radius_ref_px": row.get(f"{label}.quality.radial_radius_ref_px"),
                "position_cluster_center_ref_px": row.get(f"{label}.quality.position_cluster_center_ref_px"),
                "position_cluster_deviation_ref_px": row.get(f"{label}.quality.position_cluster_deviation_ref_px"),
                "position_cluster_locked": row.get(f"{label}.quality.position_cluster_locked"),
            })
    return anomalies


def write_anomalies_csv(path: Path, rows: list[dict[str, object]]) -> None:
    fieldnames = [
        "sample",
        "position",
        "repeat",
        "image",
        "feature",
        "source",
        "reason",
        "measurement_valid",
        "radius_ref_px",
        "length_ref_px",
        "template_radius_ref_px",
        "radial_radius_ref_px",
        "position_cluster_center_ref_px",
        "position_cluster_deviation_ref_px",
        "position_cluster_locked",
    ]
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def should_skip_image(path: Path, reference_image_name: str) -> bool:
    name = path.name
    if name == reference_image_name:
        return True
    if any(token in name for token in ["_detected", "_circles", "_check", "_thumb", "_overlay"]):
        return True
    return path.suffix.lower() not in IMAGE_SUFFIXES


def infer_sample_name(root: Path, sample_name: str | None) -> str:
    if sample_name:
        return sample_name
    resolved = root.resolve()
    if resolved.name:
        return resolved.name
    return "sample_1"


def discover_records(root: Path, reference_image_name: str, sample_name: str) -> list[ImageRecord]:
    """Discover images for one sample.

    Preferred layout is root/pos_1/*.bmp, root/pos_2/*.bmp, root/pos_3/*.bmp.
    A flat root with images is accepted as one position for quick reproduction.
    """
    if not root.exists():
        raise FileNotFoundError(f"Sample root does not exist: {root}")

    position_records: list[ImageRecord] = []
    for position_dir in sorted([p for p in root.iterdir() if p.is_dir()]):
        images = sorted(p for p in position_dir.iterdir() if p.is_file() and not should_skip_image(p, reference_image_name))
        if not images:
            continue
        for idx, image in enumerate(images, start=1):
            position_records.append(ImageRecord(sample_name, position_dir.name, image, idx))
    if position_records:
        return position_records

    flat_images = sorted(p for p in root.iterdir() if p.is_file() and not should_skip_image(p, reference_image_name))
    return [ImageRecord(sample_name, "position_1", image, idx) for idx, image in enumerate(flat_images, start=1)]


def load_manifest(manifest_path: Path, sample_name: str) -> list[ImageRecord]:
    records: list[ImageRecord] = []
    base = manifest_path.parent
    with manifest_path.open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        required = {"position", "image"}
        if not required.issubset(set(reader.fieldnames or [])):
            raise ValueError("Manifest must contain columns: position,image. Optional columns: sample,repeat")
        counters: dict[tuple[str, str], int] = {}
        for row in reader:
            sample = row.get("sample", "").strip() or sample_name
            position = row["position"].strip()
            image = Path(row["image"].strip())
            if not image.is_absolute():
                image = base / image
            key = (sample, position)
            counters[key] = counters.get(key, 0) + 1
            repeat_index = int(row.get("repeat") or counters[key])
            records.append(ImageRecord(sample, position, image, repeat_index))
    return records


def write_measurements_csv(path: Path, rows: list[dict[str, object]]) -> None:
    fieldnames: list[str] = ["sample", "position", "repeat", "image", "shift_method"]
    metric_names = sorted({key for row in rows for key in row.keys() if key not in fieldnames})
    fieldnames.extend(metric_names)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def measurement_feature_for_metric(metric: str) -> str | None:
    if ".quality." in metric or ".detect." in metric:
        return None
    if metric.startswith("transform.") or metric.startswith("global_shift"):
        return None
    if "." not in metric:
        return None
    return metric.split(".", 1)[0]


def metric_is_valid_for_row(row: dict[str, object], metric: str) -> bool:
    feature = measurement_feature_for_metric(metric)
    if feature is None:
        return True
    value = row.get(f"{feature}.quality.measurement_valid")
    if value in (None, ""):
        return True
    try:
        return float(value) > 0.5
    except (TypeError, ValueError):
        return True


def values_for(rows: list[dict[str, object]], metric: str) -> list[float]:
    values = []
    for row in rows:
        if not metric_is_valid_for_row(row, metric):
            continue
        value = row.get(metric)
        if value in (None, ""):
            continue
        try:
            values.append(float(value))
        except (TypeError, ValueError):
            continue
    return values


def summarize_values(values: list[float]) -> dict[str, float | int | None]:
    if not values:
        return {
            "n": 0,
            "mean": None,
            "std": None,
            "range": None,
            "repeatability_range": None,
            "min": None,
            "max": None,
            "six_sigma": None,
        }
    std = statistics.stdev(values) if len(values) >= 2 else 0.0
    value_range = max(values) - min(values)
    return {
        "n": len(values),
        "mean": statistics.fmean(values),
        "std": std,
        "range": value_range,
        "repeatability_range": value_range,
        "min": min(values),
        "max": max(values),
        "six_sigma": 6.0 * std,
    }


def is_dynamic_comparable_metric(metric: str) -> bool:
    if ".quality." in metric or ".detect." in metric:
        return False
    if metric.startswith("transform.") or metric.startswith("global_shift"):
        return False
    if "_ref_px" in metric or "_ref_unit" in metric or "_ref_unit2" in metric:
        return True
    if metric.endswith(".angle_ref_deg"):
        return True
    # Unit metrics are physical values and are comparable across positions when
    # pixel size is calibrated. Keep this fallback for user-added metrics.
    if metric.endswith("_unit") or metric.endswith("_unit2"):
        return True
    return False


def is_repeatability_metric(metric: str) -> bool:
    return ".quality." not in metric and ".detect." not in metric


def compute_repeatability(rows: list[dict[str, object]]) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    identity = {"sample", "position", "repeat", "image", "shift_method"}
    metrics = sorted({key for row in rows for key in row.keys() if key not in identity and is_repeatability_metric(key)})
    dynamic_metrics = [metric for metric in metrics if is_dynamic_comparable_metric(metric)]
    static_rows: list[dict[str, object]] = []
    dynamic_rows: list[dict[str, object]] = []

    samples = sorted({str(row["sample"]) for row in rows})
    for sample in samples:
        sample_rows = [row for row in rows if row["sample"] == sample]
        positions = sorted({str(row["position"]) for row in sample_rows})
        for metric in metrics:
            position_means = []
            for position in positions:
                group_rows = [row for row in sample_rows if row["position"] == position]
                stats = summarize_values(values_for(group_rows, metric))
                static_rows.append({
                    "sample": sample,
                    "position": position,
                    "metric": metric,
                    **stats,
                    "type": "static_same_position",
                })
                if stats["n"] and stats["mean"] is not None:
                    position_means.append(float(stats["mean"]))

            if metric not in dynamic_metrics:
                continue
            dyn_stats = summarize_values(position_means)
            dynamic_rows.append({
                "sample": sample,
                "position_count": len(position_means),
                "metric": metric,
                **dyn_stats,
                "type": "dynamic_position_means",
            })
    return static_rows, dynamic_rows


def write_summary_csv(path: Path, rows: list[dict[str, object]]) -> None:
    fieldnames = [
        "type",
        "sample",
        "position",
        "position_count",
        "metric",
        "n",
        "mean",
        "std",
        "range",
        "repeatability_range",
        "min",
        "max",
        "six_sigma",
    ]
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_report_json(
    path: Path,
    measurement_rows: list[dict[str, object]],
    static_rows: list[dict[str, object]],
    dynamic_rows: list[dict[str, object]],
    warnings: list[str],
    measurement_mode: str = "raw_detection",
) -> None:
    report = {
        "measurement_mode": measurement_mode,
        "invalid_measurement_policy": "feature metrics with quality.measurement_valid=0 are kept in measurements.csv for traceability but skipped by repeatability summaries",
        "warnings": warnings,
        "image_count": len(measurement_rows),
        "static_repeatability": static_rows,
        "dynamic_repeatability": dynamic_rows,
    }
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


def build_warnings(records: list[ImageRecord]) -> list[str]:
    warnings = []
    groups: dict[tuple[str, str], int] = {}
    sample_positions: dict[str, set[str]] = {}
    for record in records:
        groups[(record.sample, record.position)] = groups.get((record.sample, record.position), 0) + 1
        sample_positions.setdefault(record.sample, set()).add(record.position)
    for (sample, position), count in sorted(groups.items()):
        if count < 20:
            warnings.append(f"{sample}/{position} has {count} images; static repeatability target is 20 images.")
    for sample, positions in sorted(sample_positions.items()):
        if len(positions) < 3:
            warnings.append(f"{sample} has {len(positions)} position(s); dynamic repeatability target is 3 positions.")
    return warnings


def build_invalid_measurement_warnings(rows: list[dict[str, object]]) -> list[str]:
    counts: dict[str, int] = {}
    for row in rows:
        for key, value in row.items():
            if not key.endswith(".quality.measurement_valid"):
                continue
            try:
                valid = float(value) > 0.5
            except (TypeError, ValueError):
                valid = True
            if valid:
                continue
            feature = key[: -len(".quality.measurement_valid")]
            counts[feature] = counts.get(feature, 0) + 1
    return [
        f"{feature} has {count} invalid fallback/low-confidence measurement(s); repeatability summaries skip those values."
        for feature, count in sorted(counts.items())
    ]


def create_manifest_template(path: Path) -> None:
    rows = []
    for position_idx in range(1, 4):
        for repeat_idx in range(1, 21):
            rows.append({
                "position": f"pos_{position_idx}",
                "repeat": repeat_idx,
                "image": f"pos_{position_idx}/{repeat_idx:02d}.bmp",
            })
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=["position", "repeat", "image"])
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate static and dynamic repeatability for one sample")
    parser.add_argument("--annotation", default="1 (1).json", help="This sample's reference LabelMe JSON")
    parser.add_argument("--root", default=".", help="Single-sample root. Expected layout: root/pos_1/*.bmp, root/pos_2/*.bmp, root/pos_3/*.bmp")
    parser.add_argument("--sample-name", help="Sample name written to reports. Defaults to the root directory name")
    parser.add_argument("--manifest", help="Single-sample CSV with columns position,image[,repeat]. sample is optional")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR, help="Directory for numeric reports")
    parser.add_argument("--pixel-size", type=float, default=1.0, help="Physical size per pixel. Default keeps pixel units")
    parser.add_argument("--visualize-image", help="Run raw detection on one image and save an annotated overlay PNG")
    parser.add_argument("--visualize-output", help="Output path for --visualize-image. Defaults to output-dir/<image_stem>_detected.png")
    parser.add_argument(
        "--rotation-lock-gate-deg",
        type=float,
        default=DEFAULT_ROTATION_LOCK_GATE_DEG,
        help="Per-position rotation outlier gate in degrees. Default 0 disables median rotation locking.",
    )
    parser.add_argument(
        "--write-corrected-reports",
        action="store_true",
        help="Also write corrected_* reports with legacy position-cluster stabilization. Standard reports remain raw.",
    )
    parser.add_argument("--create-manifest-template", action="store_true", help="Create repeatability_manifest_template.csv and exit")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.create_manifest_template:
        out = Path("repeatability_manifest_template.csv")
        create_manifest_template(out)
        print(f"created {out}")
        return

    annotation_path = Path(args.annotation)
    ref_model = build_reference_model(annotation_path)
    output_dir = Path(args.output_dir)
    if args.visualize_image:
        image_path = Path(args.visualize_image)
        if args.visualize_output:
            visualize_output = Path(args.visualize_output)
        else:
            visualize_output = output_dir / f"{image_path.stem}_detected.png"
        out, invalid_count = visualize_detection(ref_model, image_path, visualize_output, args.pixel_size)
        print(f"visualization -> {out}")
        print(f"invalid features -> {invalid_count}")
        return

    sample_name = infer_sample_name(Path(args.root), args.sample_name)
    records = load_manifest(Path(args.manifest), sample_name) if args.manifest else discover_records(Path(args.root), ref_model.reference_path.name, sample_name)
    if not records:
        raise SystemExit(
            "No input images found. For one sample, use root/pos_1/*.bmp, "
            "root/pos_2/*.bmp, root/pos_3/*.bmp, or provide --manifest."
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    measurement_rows: list[dict[str, object]] = []
    print(f"sample      -> {sample_name}")
    print(f"annotation  -> {annotation_path}")
    print(f"reference   -> {ref_model.reference_path}")
    print(f"image count -> {len(records)}")
    print("pre-align   -> estimating per-image transforms")
    prepared_transforms = prepare_position_locked_transforms(ref_model, records, args.rotation_lock_gate_deg)
    locked_count = sum(1 for item in prepared_transforms.values() if item.rotation_locked)
    print(
        "rotation   -> "
        f"{locked_count} image(s) locked by position median "
        f"(gate={args.rotation_lock_gate_deg:.3f} deg)"
    )

    for index, record in enumerate(records, start=1):
        metrics, shift_method = detect_measurements(
            ref_model,
            record.image_path,
            args.pixel_size,
            prepared_transforms.get(record.image_path),
        )
        row: dict[str, object] = {
            "sample": record.sample,
            "position": record.position,
            "repeat": record.repeat_index,
            "image": str(record.image_path),
            "shift_method": shift_method,
        }
        row.update(metrics)
        measurement_rows.append(row)
        print(f"[{index}/{len(records)}] {record.sample}/{record.position}/{record.repeat_index}: {record.image_path.name}")

    anomaly_rows = detection_anomaly_rows(measurement_rows)
    static_rows, dynamic_rows = compute_repeatability(measurement_rows)
    warnings = build_warnings(records)
    warnings.extend(build_invalid_measurement_warnings(measurement_rows))

    write_measurements_csv(output_dir / "measurements.csv", measurement_rows)
    write_anomalies_csv(output_dir / "detection_anomalies.csv", anomaly_rows)
    write_summary_csv(output_dir / "static_repeatability.csv", static_rows)
    write_summary_csv(output_dir / "dynamic_repeatability.csv", dynamic_rows)
    write_report_json(
        output_dir / "repeatability_report.json",
        measurement_rows,
        static_rows,
        dynamic_rows,
        warnings,
        measurement_mode="raw_detection",
    )

    if args.write_corrected_reports:
        corrected_rows = [dict(row) for row in measurement_rows]
        stabilize_middle_circle_position_clusters(ref_model, corrected_rows, args.pixel_size)
        stabilize_line20_position_clusters(ref_model, corrected_rows, args.pixel_size)
        stabilize_d46_position_clusters(corrected_rows)
        corrected_anomaly_rows = detection_anomaly_rows(corrected_rows)
        corrected_static_rows, corrected_dynamic_rows = compute_repeatability(corrected_rows)
        corrected_warnings = warnings + [
            "corrected_* reports apply legacy position-cluster stabilization and are not raw measurement reports."
        ]
        write_measurements_csv(output_dir / "corrected_measurements.csv", corrected_rows)
        write_anomalies_csv(output_dir / "corrected_detection_anomalies.csv", corrected_anomaly_rows)
        write_summary_csv(output_dir / "corrected_static_repeatability.csv", corrected_static_rows)
        write_summary_csv(output_dir / "corrected_dynamic_repeatability.csv", corrected_dynamic_rows)
        write_report_json(
            output_dir / "corrected_repeatability_report.json",
            corrected_rows,
            corrected_static_rows,
            corrected_dynamic_rows,
            corrected_warnings,
            measurement_mode="corrected_position_cluster_stabilized",
        )

    print(f"measurements -> {output_dir / 'measurements.csv'}")
    print(f"anomalies    -> {output_dir / 'detection_anomalies.csv'}")
    print(f"static      -> {output_dir / 'static_repeatability.csv'}")
    print(f"dynamic     -> {output_dir / 'dynamic_repeatability.csv'}")
    print(f"json report -> {output_dir / 'repeatability_report.json'}")
    if args.write_corrected_reports:
        print(f"corrected measurements -> {output_dir / 'corrected_measurements.csv'}")
        print(f"corrected anomalies    -> {output_dir / 'corrected_detection_anomalies.csv'}")
        print(f"corrected static      -> {output_dir / 'corrected_static_repeatability.csv'}")
        print(f"corrected dynamic     -> {output_dir / 'corrected_dynamic_repeatability.csv'}")
        print(f"corrected json report -> {output_dir / 'corrected_repeatability_report.json'}")
    for warning in warnings:
        print(f"warning: {warning}")


if __name__ == "__main__":
    main()
