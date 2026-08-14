#!/usr/bin/env python3
"""Extract per-image geometric measurements from one LabelMe reference (v6).

Pipeline
--------
1. Build a reference model from the single annotated image. Each shape is
   classified by geometry (label-agnostic): closed circle, open arc, straight
   line, or named point. The reference picks two preferred anchors (smallest
   closed circle + farthest closed circle from it) but **all** closed circles
   are kept as anchor candidates for runtime expansion.
2. For each target image, estimate alignment using anchor circles refined
   from a phase-correlation prior. Default alignment is translation+scale.
   Use ``--rotation`` to enable similarity (4DoF, includes rotation) when
   3+ anchors are available; with only 2 anchors, anchor detection noise
   can leak into a fake ~0.3° rotation that hurts line measurements. Falls
   back to translation only when only a single anchor is visible.

   v5 adds **anchor pool expansion**: after the initial alignment with the
   preferred anchors, every other labeled closed circle is re-tested with
   the wide anchor-mode search; any that succeed are added to the anchor
   set and the alignment is re-solved. This is the fix for positions
   (e.g. pos_3 in the user's full data) where one preferred anchor leaves
   the frame but other closed circles (e.g. ψ3) are still visible — those
   features used to cascade into all-NaN; with v5 they recover normally.
3. Detect each shape in the aligned target with a per-kind subpixel
   detector. v4/v5 keep the v3 radial-derivative template lock for arcs
   but reject template offsets that saturate the search window. The
   annotated p1/p2 center points are detected from the corresponding real
   circles and used to anchor the 7.7 and 12 dimension lines. The 0.8 and
   3.2 dimension vectors use dedicated feature-coupled detectors: 0.8 finds
   both dimension-end boundaries, and 3.2 uses the detected M2 centre plus
   the detected lower boundary. Annotated line endpoints are priors/search
   axes only, not reported measurement endpoints. v6 gives dimension 7 its
   confirmed semantics: the two annotation endpoints are independent boundary
   priors. Around each endpoint the detector searches along the dimension axis
   (the local boundary normal), fits the actual boundary from a transverse
   strip, intersects it with the dimension axis, and reports the distance
   between the two detected feature points.
4. Each detected measurement is back-transformed into the reference frame
   so coordinates are directly comparable across captures, positions and
   samples.
5. v6 writes raw per-image detector values by default. No group-level
   median replacement is applied, so each CSV value must come from the
   current image's actual detected features. Failed/out-of-frame values
   remain NaN for coverage diagnostics.

Quality columns
---------------
Per-shape ``.quality.*`` columns surface why a measurement is what it is:
edge-point counts and fit residuals for arcs/circles; both boundary point
counts, residuals, edge scores, offsets and parallelism for dimension 7;
``upstream`` markers for dependent lines; and an ``endpoint_snap_px`` for
d12 telling how far the chosen near-end is from the anchored point.

Output is a CSV with one row per image: alignment metadata followed by
the measurements of every shape, all expressed in reference-frame pixels
(circle/arc: cx, cy, r; line: x1, y1, x2, y2, length). The confirmed
``ψ12.2``/damaged-source equivalent is a 77-point LabelMe ``linestrip``
fitted as a circle and additionally emits ``Phi12_2_diameter_px = 2*r``.

Layout for the input directory tree:

    --input-dir/
        s1/pos1/*.bmp
        s1/pos2/*.bmp
        ...
        s2/pos3/*.bmp

Flat files named like `s1_pos1.bmp` are also accepted for quick checks.
The (sample, position) is inferred from the parent directory names; the
repeat index is the sort order of files inside a position folder/group.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import re
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from PIL import Image


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

IMAGE_SUFFIXES = {".bmp", ".png", ".jpg", ".jpeg", ".tif", ".tiff"}
SKIP_LABELS: set[str] = set()
# The received LabelMe JSON permanently contains U+FFFD replacement characters
# for three diameter symbols. Normalize only the known, reviewed labels so the
# output schema is stable across Mac and Linux.
LABEL_ALIASES = {
    "��2": "Phi2",
    "��3": "Phi3",
    "��12.2": "Phi12.2",
    "ψ12.2": "Phi12.2",
    "Ψ12.2": "Phi12.2",
}
DIAMETER_FEATURES = {"Phi12_2"}
DEFAULT_SMOOTH_SIGMA = 1.0
CLOSED_ARC_DEG = 340.0
CIRCLE_RESIDUAL_PX = 25.0
ANCHOR_MAX_PIXELS = 220.0
DEFAULT_SEARCH_WIDTH = 22
ANCHOR_SEARCH_MULT = 2
EDGE_SCORE_FLOOR = 2.0
RADIUS_REJECT_FRAC = 0.30
CENTER_REJECT_MULT = 3.0
ARC_VISIBILITY_MIN_FRACTION = 0.30
LINE_VISIBILITY_MIN_FRACTION = 0.40
NON_ANCHOR_SEARCH_WIDTH = 14
NON_ANCHOR_PRIOR_SIGMA = 4.0
TEMPLATE_HALF_WIDTH = 34
TEMPLATE_SEARCH_WIDTH = 14
TEMPLATE_EDGE_SEARCH_WIDTH = 7
TEMPLATE_EDGE_PRIOR_SIGMA = 2.0
TEMPLATE_SCORE_FLOOR = 0.08
TEMPLATE_OFFSET_SATURATION_FRAC = 0.85   # |offset| above this fraction of the
                                         # search window is treated as a
                                         # template "fly-away" and ignored.
ARC_ABS_RADIUS_REJECT_REF_PX = 6.0
POINT_ANCHOR_MAX_DISTANCE_REF_PX = 12.0
D12_ENDPOINT_SNAP_WARN_PX = 20.0         # |min(d1,d2)| above this means the
                                         # anchored point sits well off the
                                         # detected line — flag for review.
MIN_ANCHOR_BASELINE_REF_PX = 30.0        # require this much separation between
                                         # 2 anchors before solving rotation;
                                         # otherwise drop to translation+scale.
RAW_DETECTED_LINE_LABELS = {"0.8", "3.2"}
DIMENSION_ENDPOINT_STRIP_HALF_WIDTH = 16
DIMENSION_ENDPOINT_SEARCH_WINDOW = 42
DIMENSION_ENDPOINT_PRIOR_SIGMA = 4.0
DIMENSION_ENDPOINT_MIN_EDGE_SCORE = 6.0
D7_BOUNDARY_STRIP_HALF_WIDTH = 36
D7_BOUNDARY_STRIP_SAMPLES = 31
D7_BOUNDARY_SEARCH_WINDOW = 42
D7_BOUNDARY_PRIOR_SIGMA = 8.0
D7_BOUNDARY_MIN_EDGE_SCORE = 4.0
D7_BOUNDARY_MIN_POINTS = 12
D7_BOUNDARY_MAX_RESIDUAL_PX = 3.0
D7_BOUNDARY_MIN_AXIS_COSINE = math.cos(math.radians(35.0))
CONTRAST_LOW_PERCENTILE = 1.0
CONTRAST_HIGH_PERCENTILE = 99.0


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ShapeModel:
    index: int
    label: str
    sanitized: str
    kind: str  # 'circle' | 'arc' | 'line' | 'point'
    points: list[tuple[float, float]]
    # circle / arc
    circle: tuple[float, float, float] | None = None
    angle_start: float | None = None
    angle_end: float | None = None
    polarity: float = 0.0
    template_angles: np.ndarray | None = None
    radial_template: np.ndarray | None = None
    # line
    line_p1: tuple[float, float] | None = None
    line_p2: tuple[float, float] | None = None
    line_polarity: float = 0.0
    endpoint_polarities: tuple[float, float] | None = None
    # point
    point: tuple[float, float] | None = None
    # output schema
    columns: list[str] = field(default_factory=list)
    quality_columns: list[str] = field(default_factory=list)
    source_shape_type: str = ""
    reference_fit_residual_px: float = float("nan")
    emits_diameter_px: bool = False


@dataclass
class CircleArcDetection:
    circle: tuple[float, float, float]
    point_count: int
    median_residual: float
    template_score: float = float("nan")
    template_offset: float = float("nan")
    template_saturated: bool = False


@dataclass
class BoundaryDetection:
    """One independently fitted dimension boundary in target-image pixels."""

    feature_point: tuple[float, float]
    line: tuple[float, float, float]
    point_count: int
    median_residual_px: float
    median_edge_score: float
    offset_px: float


@dataclass
class ReferenceModel:
    annotation: dict
    image_path: Path
    gray: np.ndarray
    shapes: list[ShapeModel]
    anchor_indices: list[int]


@dataclass
class Extraction:
    transform_dx: float
    transform_dy: float
    transform_scale: float
    transform_theta_deg: float
    align_method: str
    measurements: dict[str, object]


# ---------------------------------------------------------------------------
# IO
# ---------------------------------------------------------------------------

def read_labelme(path: Path) -> dict:
    raw = path.read_bytes()
    for enc in ("utf-8-sig", "utf-8", "gbk", "gb18030"):
        try:
            return json.loads(raw.decode(enc))
        except UnicodeDecodeError:
            continue
    return json.loads(raw.decode("latin1"))


def gaussian_blur(arr: np.ndarray, sigma: float = DEFAULT_SMOOTH_SIGMA) -> np.ndarray:
    src = arr.astype(np.float64, copy=False)
    if sigma <= 0:
        return src.copy()
    radius = max(1, int(math.ceil(3.0 * sigma)))
    x = np.arange(-radius, radius + 1, dtype=np.float64)
    kernel = np.exp(-(x * x) / (2.0 * sigma * sigma))
    kernel /= float(kernel.sum())

    padded = np.pad(src, ((0, 0), (radius, radius)), mode="edge")
    horiz = np.zeros_like(src)
    for i, weight in enumerate(kernel):
        horiz += padded[:, i:i + src.shape[1]] * weight

    padded = np.pad(horiz, ((radius, radius), (0, 0)), mode="edge")
    out = np.zeros_like(src)
    for i, weight in enumerate(kernel):
        out += padded[i:i + src.shape[0], :] * weight
    return out


def load_gray(path: Path, smooth_sigma: float = DEFAULT_SMOOTH_SIGMA) -> np.ndarray:
    gray = np.asarray(Image.open(path).convert("L"))
    return gaussian_blur(gray, smooth_sigma)


def contrast_stretch(gray: np.ndarray,
                     low_pct: float = CONTRAST_LOW_PERCENTILE,
                     high_pct: float = CONTRAST_HIGH_PERCENTILE) -> np.ndarray:
    """Normalize exposure/contrast for edge localization only."""
    src = gray.astype(np.float64, copy=False)
    finite = src[np.isfinite(src)]
    if finite.size == 0:
        return src.copy()
    lo, hi = np.percentile(finite, [low_pct, high_pct])
    if not math.isfinite(lo) or not math.isfinite(hi) or hi - lo < 1e-6:
        return src.copy()
    return np.clip((src - lo) * (255.0 / (hi - lo)), 0.0, 255.0)


# ---------------------------------------------------------------------------
# Numeric primitives
# ---------------------------------------------------------------------------

def gradient_magnitude(gray: np.ndarray) -> np.ndarray:
    a = gray.astype(np.float64)
    gx = np.zeros_like(a)
    gy = np.zeros_like(a)
    gx[:, 1:-1] = a[:, 2:] - a[:, :-2]
    gy[1:-1, :] = a[2:, :] - a[:-2, :]
    return np.hypot(gx, gy)


def bilinear_sample(gray: np.ndarray, xs: np.ndarray, ys: np.ndarray) -> np.ndarray:
    h, w = gray.shape
    x0 = np.floor(xs).astype(np.int64)
    y0 = np.floor(ys).astype(np.int64)
    x1 = x0 + 1
    y1 = y0 + 1
    valid = (x0 >= 0) & (y0 >= 0) & (x1 < w) & (y1 < h)
    out = np.full(xs.shape, np.nan, dtype=np.float64)
    xv, yv = xs[valid], ys[valid]
    x0v, y0v, x1v, y1v = x0[valid], y0[valid], x1[valid], y1[valid]
    dx = xv - x0v
    dy = yv - y0v
    out[valid] = (
        gray[y0v, x0v] * (1 - dx) * (1 - dy)
        + gray[y0v, x1v] * dx * (1 - dy)
        + gray[y1v, x0v] * (1 - dx) * dy
        + gray[y1v, x1v] * dx * dy
    )
    return out


def smooth_1d(values: np.ndarray, window: int = 11) -> np.ndarray:
    if len(values) < window:
        return values
    k = np.ones(window, dtype=np.float64) / float(window)
    return np.convolve(values, k, mode="same")


def normalize_for_match(patch: np.ndarray) -> np.ndarray | None:
    patch = patch.astype(np.float64, copy=False)
    patch = patch - float(np.nanmean(patch))
    patch = np.nan_to_num(patch, nan=0.0)
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


def parabolic_peak(scores: list[float], idx: int) -> float:
    if idx <= 0 or idx >= len(scores) - 1:
        return 0.0
    L, C, R = scores[idx - 1], scores[idx], scores[idx + 1]
    den = L - 2.0 * C + R
    if abs(den) < 1e-9:
        return 0.0
    return float(np.clip(0.5 * (L - R) / den, -0.5, 0.5))


def fit_circle_kasa(points) -> tuple[float, float, float]:
    pts = np.asarray(points, dtype=np.float64)
    if len(pts) < 3:
        raise ValueError("need >=3 points")
    x, y = pts[:, 0], pts[:, 1]
    A = np.column_stack([x, y, np.ones_like(x)])
    b = -(x * x + y * y)
    d, e, f = np.linalg.lstsq(A, b, rcond=None)[0]
    cx, cy = -d / 2.0, -e / 2.0
    r = math.sqrt(max(0.0, cx * cx + cy * cy - f))
    return cx, cy, r


def geometric_circle_fit(points: np.ndarray, init: tuple[float, float, float],
                         max_iter: int = 30) -> tuple[float, float, float]:
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
        ux, uy = dx / di, dy / di
        res = di - r
        H = np.array([
            [float(ux @ ux), float(ux @ uy), float(ux.sum())],
            [float(ux @ uy), float(uy @ uy), float(uy.sum())],
            [float(ux.sum()), float(uy.sum()), n],
        ])
        g = np.array([float(ux @ res), float(uy @ res), float(res.sum())])
        try:
            delta = np.linalg.solve(H, g)
        except np.linalg.LinAlgError:
            break
        cx += float(delta[0])
        cy += float(delta[1])
        r += float(delta[2])
        if abs(delta).sum() < 1e-9:
            break
    return cx, cy, r


def robust_fit_circle(points, fallback) -> tuple[float, float, float]:
    if len(points) < 8:
        return fallback
    pts = np.asarray(points, dtype=np.float64)
    for _ in range(8):
        try:
            cx, cy, r = fit_circle_kasa(pts)
        except (ValueError, np.linalg.LinAlgError):
            return fallback
        res = np.abs(np.hypot(pts[:, 0] - cx, pts[:, 1] - cy) - r)
        med = float(np.median(res))
        mad = float(np.median(np.abs(res - med))) + 1e-6
        gate = max(6.0, med + 3.0 * 1.4826 * mad)
        keep = res <= gate
        kept = int(keep.sum())
        if kept < 8 or kept == len(pts):
            break
        pts = pts[keep]
    try:
        cx, cy, r = fit_circle_kasa(pts)
    except (ValueError, np.linalg.LinAlgError):
        return fallback
    return geometric_circle_fit(pts, (cx, cy, r))


def circular_residual(points, circle) -> float:
    cx, cy, r = circle
    pts = np.asarray(points, dtype=np.float64)
    return float(np.median(np.abs(np.hypot(pts[:, 0] - cx, pts[:, 1] - cy) - r)))


def angle_extents(points, circle) -> tuple[float, float, float]:
    cx, cy, _ = circle
    pts = np.asarray(points, dtype=np.float64)
    angles = np.unwrap(np.arctan2(pts[:, 1] - cy, pts[:, 0] - cx))
    return float(angles.min()), float(angles.max()), float(angles.max() - angles.min())


def dense_arc_angles(angle_start: float, angle_end: float, radius: float,
                     min_count: int = 80, max_count: int = 360) -> np.ndarray:
    extent = max(0.05, abs(angle_end - angle_start))
    count = int(np.clip(radius * extent / 3.0, min_count, max_count))
    return np.linspace(angle_start, angle_end, count, dtype=np.float64)


def fit_line_total_least_squares(points) -> tuple[float, float, float]:
    pts = np.asarray(points, dtype=np.float64)
    centroid = pts.mean(axis=0)
    centered = pts - centroid
    _, _, vh = np.linalg.svd(centered, full_matrices=False)
    direction = vh[0]
    nx, ny = -direction[1], direction[0]
    norm = math.hypot(nx, ny)
    if norm < 1e-9:
        return 1.0, 0.0, -float(centroid[0])
    nx, ny = nx / norm, ny / norm
    c = -(nx * centroid[0] + ny * centroid[1])
    return nx, ny, c


def project_onto_line(point, line) -> tuple[float, float]:
    a, b, c = line
    x, y = point
    d = a * x + b * y + c
    return float(x - a * d), float(y - b * d)


def robust_fit_line(points: list[tuple[float, float]], min_points: int
                    ) -> tuple[tuple[float, float, float], np.ndarray] | None:
    """Fit a line while rejecting texture points far from the local boundary."""
    pts = np.asarray(points, dtype=np.float64)
    if len(pts) < min_points:
        return None
    for _ in range(5):
        line = fit_line_total_least_squares(pts)
        a, b, c = line
        residuals = np.abs(a * pts[:, 0] + b * pts[:, 1] + c)
        median = float(np.median(residuals))
        mad = float(np.median(np.abs(residuals - median))) + 1e-6
        gate = max(1.25, median + 3.0 * 1.4826 * mad)
        keep = residuals <= gate
        if int(keep.sum()) < min_points or bool(keep.all()):
            break
        pts = pts[keep]
    if len(pts) < min_points:
        return None
    return fit_line_total_least_squares(pts), pts


def line_axis_intersection(line: tuple[float, float, float],
                           origin: tuple[float, float],
                           axis: tuple[float, float]
                           ) -> tuple[tuple[float, float], float] | None:
    """Intersect a fitted boundary with an axis; return point and signed offset."""
    a, b, c = line
    ux, uy = axis
    denominator = a * ux + b * uy
    if abs(denominator) < 1e-6:
        return None
    offset = -(a * origin[0] + b * origin[1] + c) / denominator
    return (
        (float(origin[0] + offset * ux), float(origin[1] + offset * uy)),
        float(offset),
    )


# ---------------------------------------------------------------------------
# Phase correlation (translation only)
# ---------------------------------------------------------------------------

def phase_correlation_shift(reference: np.ndarray, target: np.ndarray,
                             downsample: int = 8) -> tuple[float, float, float]:
    h, w = reference.shape
    sw = max(16, w // downsample)
    sh = max(16, h // downsample)
    rp = Image.fromarray(reference.astype(np.float32))
    tp = Image.fromarray(target.astype(np.float32))
    rs = np.asarray(rp.resize((sw, sh), Image.Resampling.BILINEAR), dtype=np.float64)
    ts = np.asarray(tp.resize((sw, sh), Image.Resampling.BILINEAR), dtype=np.float64)
    rg = gradient_magnitude(rs)
    tg = gradient_magnitude(ts)
    win = np.outer(np.hanning(rg.shape[0]), np.hanning(rg.shape[1]))
    rg = (rg - rg.mean()) / (rg.std() + 1e-6) * win
    tg = (tg - tg.mean()) / (tg.std() + 1e-6) * win
    cp = np.fft.fft2(tg) * np.conj(np.fft.fft2(rg))
    cp /= np.abs(cp) + 1e-9
    corr = np.fft.ifft2(cp).real
    py, px = np.unravel_index(int(np.argmax(corr)), corr.shape)
    if px > corr.shape[1] // 2:
        px -= corr.shape[1]
    if py > corr.shape[0] // 2:
        py -= corr.shape[0]
    return float(px * downsample), float(py * downsample), float(corr.max())


# ---------------------------------------------------------------------------
# Similarity transform (translation + scale + rotation)
# ---------------------------------------------------------------------------

def make_rotation(theta: float) -> np.ndarray:
    c, s = math.cos(theta), math.sin(theta)
    return np.array([[c, -s], [s, c]], dtype=np.float64)


def forward_xy(x: float, y: float, dx: float, dy: float, scale: float,
               theta: float) -> tuple[float, float]:
    c, s = math.cos(theta), math.sin(theta)
    nx = scale * (c * x - s * y) + dx
    ny = scale * (s * x + c * y) + dy
    return float(nx), float(ny)


def inverse_xy(x: float, y: float, dx: float, dy: float, scale: float,
               theta: float) -> tuple[float, float]:
    c, s = math.cos(theta), math.sin(theta)
    px = (x - dx) / scale
    py = (y - dy) / scale
    rx = c * px + s * py
    ry = -s * px + c * py
    return float(rx), float(ry)


def solve_similarity(ref_pts, tgt_pts,
                     allow_rotation: bool = True
                     ) -> tuple[float, float, float, float]:
    """Closed-form similarity (Umeyama) fit.

    Returns (dx, dy, scale, theta) such that ``tgt = scale * R(theta) @ ref + (dx, dy)``.
    With ``allow_rotation=False`` falls back to translation+scale only.
    With one anchor, returns translation only.
    """
    R = np.asarray(ref_pts, dtype=np.float64)
    T = np.asarray(tgt_pts, dtype=np.float64)
    n = len(R)
    if n == 0:
        raise ValueError("need at least one anchor")
    if n == 1:
        return float(T[0, 0] - R[0, 0]), float(T[0, 1] - R[0, 1]), 1.0, 0.0

    mu_R = R.mean(axis=0)
    mu_T = T.mean(axis=0)
    R_c = R - mu_R
    T_c = T - mu_T
    sum_R_sq = float((R_c * R_c).sum())  # Σ |r_i - mean|²
    var_R = sum_R_sq / n                  # Umeyama's σ_R²

    def _translation_scale_only() -> tuple[float, float, float, float]:
        # Least-squares scale s minimizing |T_c - s * R_c|²:
        #   s = (R_c · T_c) / (R_c · R_c)
        num = float((R_c * T_c).sum())
        scale_v = num / sum_R_sq if sum_R_sq > 1e-9 else 1.0
        if scale_v <= 0:
            scale_v = 1.0
        offset = mu_T - scale_v * mu_R
        return float(offset[0]), float(offset[1]), float(scale_v), 0.0

    if not allow_rotation or n < 2:
        return _translation_scale_only()

    # Reject ill-conditioned 2-anchor cases (anchors basically on top of one
    # another) — rotation is undetermined in that limit.
    baseline = float(np.linalg.norm(R[1] - R[0])) if n == 2 else math.sqrt(var_R)
    if baseline < MIN_ANCHOR_BASELINE_REF_PX:
        return _translation_scale_only()

    Sigma = T_c.T @ R_c / n
    U, D, Vt = np.linalg.svd(Sigma)
    S = np.eye(2)
    if np.linalg.det(U) * np.linalg.det(Vt) < 0:
        S[1, 1] = -1.0
    Rot = U @ S @ Vt
    if var_R < 1e-9:
        scale = 1.0
    else:
        scale = float(np.trace(np.diag(D) @ S) / var_R)
    if scale <= 0:
        scale = 1.0
        Rot = np.eye(2)
    t = mu_T - scale * (Rot @ mu_R)
    theta = float(math.atan2(Rot[1, 0], Rot[0, 0]))
    return float(t[0]), float(t[1]), float(scale), theta


# ---------------------------------------------------------------------------
# Edge detectors
# ---------------------------------------------------------------------------

def sample_radial(gray: np.ndarray, cx: float, cy: float, angle: float,
                  radius: float, half_width: int) -> tuple[np.ndarray, np.ndarray]:
    h, w = gray.shape
    r0 = max(3, int(round(radius - half_width)))
    r1 = min(int(math.hypot(w, h)), int(round(radius + half_width)))
    radii = np.arange(r0, r1 + 1, dtype=np.float64)
    xs = cx + radii * math.cos(angle)
    ys = cy + radii * math.sin(angle)
    valid = (xs >= 0) & (xs < w - 1) & (ys >= 0) & (ys < h - 1)
    if not valid.any():
        return radii[:0], radii[:0]
    return radii[valid], bilinear_sample(gray, xs[valid], ys[valid])


def radial_derivative_template(gray: np.ndarray, center: tuple[float, float],
                               radius: float, angles: np.ndarray,
                               half_width: int = TEMPLATE_HALF_WIDTH) -> np.ndarray:
    offsets = np.arange(-half_width, half_width + 1, dtype=np.float64)
    angle_grid, offset_grid = np.meshgrid(angles, offsets, indexing="ij")
    radii = radius + offset_grid
    xs = center[0] + radii * np.cos(angle_grid)
    ys = center[1] + radii * np.sin(angle_grid)
    profiles = bilinear_sample(gray, xs, ys)
    if np.isnan(profiles).any():
        fill = float(np.nanmean(profiles)) if not np.isnan(profiles).all() else 0.0
        profiles = np.nan_to_num(profiles, nan=fill)
    profiles = np.apply_along_axis(smooth_1d, 1, profiles, 7)
    return np.diff(profiles, axis=1)


def template_offset_match(reference_template: np.ndarray, target: np.ndarray,
                          center: tuple[float, float], radius: float,
                          angles: np.ndarray,
                          half_width: int = TEMPLATE_HALF_WIDTH,
                          search_width: int = TEMPLATE_SEARCH_WIDTH) -> tuple[float, float]:
    offsets = np.arange(-search_width, search_width + 1, dtype=np.float64)
    scores: list[float] = []
    for offset in offsets:
        tgt_template = radial_derivative_template(target, center, radius + float(offset), angles, half_width)
        score = ncc_score(reference_template, tgt_template)
        score -= 0.015 * (abs(float(offset)) / max(1.0, search_width))
        scores.append(score)
    best_idx = int(np.argmax(scores))
    delta = parabolic_peak(scores, best_idx)
    offset = float(offsets[best_idx] + delta)
    return offset, float(scores[best_idx])


def radial_polarity(ref_gray: np.ndarray, center: tuple[float, float], radius: float,
                    n_samples: int = 24) -> float:
    cx, cy = center
    deltas = []
    for ang in np.linspace(0.0, 2.0 * math.pi, n_samples, endpoint=False):
        radii, prof = sample_radial(ref_gray, cx, cy, float(ang), radius, 14)
        if len(radii) < 10:
            continue
        below = prof[radii < radius - 2]
        above = prof[radii > radius + 2]
        if len(below) and len(above):
            deltas.append(float(np.mean(above) - np.mean(below)))
    if not deltas:
        return 0.0
    return float(np.median(deltas))


def radial_edge_at_angle(target: np.ndarray, center: tuple[float, float], angle: float,
                         radius: float, polarity: float, search_width: int,
                         prior_sigma: float | None = None) -> tuple[float, float] | None:
    cx, cy = center
    radii, profile = sample_radial(target, cx, cy, angle, radius, search_width)
    if len(radii) < 20:
        return None
    profile = smooth_1d(profile, 9)
    deriv = np.diff(profile)
    if polarity > EDGE_SCORE_FLOOR:
        score = deriv
    elif polarity < -EDGE_SCORE_FLOOR:
        score = -deriv
    else:
        score = np.abs(deriv)
    if prior_sigma is not None and prior_sigma > 0:
        midradii = (radii[:-1] + radii[1:]) / 2.0
        weight = np.exp(-((midradii - radius) ** 2) / (2.0 * prior_sigma * prior_sigma))
        score = score * weight
    idx = int(np.argmax(score))
    if float(score[idx]) < EDGE_SCORE_FLOOR:
        return None
    delta = parabolic_peak(score.tolist(), idx)
    step = float(radii[1] - radii[0]) if len(radii) >= 2 else 1.0
    rd = float((radii[idx] + radii[idx + 1]) / 2.0 + delta * step)
    return cx + rd * math.cos(angle), cy + rd * math.sin(angle)


def perpendicular_edge_along_line(target: np.ndarray, center_pt: tuple[float, float],
                                  normal: tuple[float, float], polarity: float,
                                  search_width: int) -> tuple[float, float] | None:
    cx, cy = center_pt
    nx, ny = normal
    offsets = np.arange(-search_width, search_width + 1, dtype=np.float64)
    xs = cx + offsets * nx
    ys = cy + offsets * ny
    profile = bilinear_sample(target, xs, ys)
    if np.isnan(profile).any():
        return None
    profile = smooth_1d(profile, 7)
    deriv = np.diff(profile)
    if polarity > EDGE_SCORE_FLOOR:
        score = deriv
    elif polarity < -EDGE_SCORE_FLOOR:
        score = -deriv
    else:
        score = np.abs(deriv)
    idx = int(np.argmax(score))
    if float(score[idx]) < EDGE_SCORE_FLOOR:
        return None
    delta = parabolic_peak(score.tolist(), idx)
    off = (offsets[idx] + offsets[idx + 1]) / 2.0 + delta
    return cx + off * nx, cy + off * ny


def dimension_endpoint_polarity(ref_gray: np.ndarray,
                                p1: tuple[float, float],
                                p2: tuple[float, float],
                                endpoint: str) -> float:
    """Estimate the expected signed contrast across one dimension boundary.

    The dimension axis is the normal-search direction. Multiple profiles are
    sampled along the boundary tangent so one scratch cannot set the polarity.
    """
    dx, dy = p2[0] - p1[0], p2[1] - p1[1]
    length = math.hypot(dx, dy)
    if length < 1e-6:
        return 0.0
    ux, uy = dx / length, dy / length
    tx, ty = -uy, ux
    origin = p1 if endpoint == "p1" else p2
    axis_offsets = np.arange(-10, 11, dtype=np.float64)
    deltas: list[float] = []
    for tangent_offset in np.linspace(-18.0, 18.0, 9):
        cx = origin[0] + tangent_offset * tx
        cy = origin[1] + tangent_offset * ty
        profile = bilinear_sample(
            ref_gray,
            cx + axis_offsets * ux,
            cy + axis_offsets * uy,
        )
        if np.isnan(profile).any():
            continue
        before = float(np.mean(profile[:6]))
        after = float(np.mean(profile[-6:]))
        deltas.append(after - before)
    return float(np.median(deltas)) if deltas else 0.0


def detect_dimension_boundary(
    target: np.ndarray,
    p1_pred: tuple[float, float],
    p2_pred: tuple[float, float],
    endpoint: str,
    polarity: float = 0.0,
    strip_half_width: int = D7_BOUNDARY_STRIP_HALF_WIDTH,
    strip_samples: int = D7_BOUNDARY_STRIP_SAMPLES,
    search_window: int = D7_BOUNDARY_SEARCH_WINDOW,
    prior_sigma: float = D7_BOUNDARY_PRIOR_SIGMA,
    min_edge_score: float = D7_BOUNDARY_MIN_EDGE_SCORE,
    min_points: int = D7_BOUNDARY_MIN_POINTS,
    diagnostics: dict[str, object] | None = None,
) -> BoundaryDetection | None:
    """Independently locate and fit the boundary at one dimension endpoint.

    Profiles run along the dimension axis, i.e. normal to the expected local
    boundary. Their subpixel edge locations form a transverse point cloud from
    which the actual boundary line is robustly fitted. The reported feature
    point is the intersection of that fitted boundary and the dimension axis.
    """
    if diagnostics is not None:
        diagnostics.update({
            "endpoint": endpoint,
            "stripSamples": int(strip_samples),
            "searchWindowPx": int(search_window),
            "minEdgeScore": float(min_edge_score),
            "minPoints": int(min_points),
            "usableProfiles": 0,
            "acceptedEdgePoints": 0,
            "medianEdgePeak": None,
            "inlierPoints": 0,
            "medianResidualPx": None,
            "axisCosine": None,
            "offsetPx": None,
            "failureStage": None,
        })
    dx, dy = p2_pred[0] - p1_pred[0], p2_pred[1] - p1_pred[1]
    length = math.hypot(dx, dy)
    if length < 5.0:
        if diagnostics is not None:
            diagnostics["failureStage"] = "axis_degenerate"
        return None
    ux, uy = dx / length, dy / length
    tx, ty = -uy, ux
    origin = p1_pred if endpoint == "p1" else p2_pred
    offsets = np.arange(-search_window, search_window + 1, dtype=np.float64)
    mids = (offsets[:-1] + offsets[1:]) / 2.0
    prior = np.exp(-(mids * mids) / (2.0 * prior_sigma * prior_sigma))
    polarity_sign = 1.0 if polarity > EDGE_SCORE_FLOOR else (
        -1.0 if polarity < -EDGE_SCORE_FLOOR else 0.0
    )

    edge_points: list[tuple[float, float]] = []
    edge_scores: list[float] = []
    for tangent_offset in np.linspace(-strip_half_width, strip_half_width, strip_samples):
        cx = origin[0] + tangent_offset * tx
        cy = origin[1] + tangent_offset * ty
        profile = bilinear_sample(target, cx + offsets * ux, cy + offsets * uy)
        if np.isnan(profile).any():
            continue
        if diagnostics is not None:
            diagnostics["usableProfiles"] = int(diagnostics["usableProfiles"]) + 1
        derivative = np.diff(smooth_1d(profile, 7))
        base_score = np.abs(derivative) if polarity_sign == 0.0 else derivative * polarity_sign
        score = np.maximum(base_score, 0.0) * prior
        idx = int(np.argmax(score))
        raw_edge_score = float(max(base_score[idx], 0.0))
        if raw_edge_score < min_edge_score:
            continue
        delta = parabolic_peak(score.tolist(), idx)
        step = float(mids[1] - mids[0]) if len(mids) >= 2 else 1.0
        offset = float(mids[idx] + delta * step)
        edge_points.append((float(cx + offset * ux), float(cy + offset * uy)))
        edge_scores.append(raw_edge_score)

    if diagnostics is not None:
        diagnostics["acceptedEdgePoints"] = len(edge_points)
        diagnostics["medianEdgePeak"] = (
            float(np.median(edge_scores)) if edge_scores else None
        )

    fitted = robust_fit_line(edge_points, min_points=min_points)
    if fitted is None:
        if diagnostics is not None:
            diagnostics["failureStage"] = "line_fit_failed"
        return None
    line, inliers = fitted
    a, b, c = line
    axis_cosine = abs(a * ux + b * uy)
    if diagnostics is not None:
        diagnostics["inlierPoints"] = int(len(inliers))
        diagnostics["axisCosine"] = float(axis_cosine)
    if axis_cosine < D7_BOUNDARY_MIN_AXIS_COSINE:
        if diagnostics is not None:
            diagnostics["failureStage"] = "axis_alignment_below_gate"
        return None
    residuals = np.abs(a * inliers[:, 0] + b * inliers[:, 1] + c)
    median_residual = float(np.median(residuals))
    if diagnostics is not None:
        diagnostics["medianResidualPx"] = median_residual
    if median_residual > D7_BOUNDARY_MAX_RESIDUAL_PX:
        if diagnostics is not None:
            diagnostics["failureStage"] = "fit_residual_above_gate"
        return None
    intersection = line_axis_intersection(line, origin, (ux, uy))
    if intersection is None:
        if diagnostics is not None:
            diagnostics["failureStage"] = "axis_intersection_failed"
        return None
    feature_point, offset = intersection
    if abs(offset) > search_window:
        if diagnostics is not None:
            diagnostics["offsetPx"] = float(offset)
            diagnostics["failureStage"] = "offset_out_of_search_window"
        return None
    if diagnostics is not None:
        diagnostics["offsetPx"] = float(offset)
    return BoundaryDetection(
        feature_point=feature_point,
        line=line,
        point_count=int(len(inliers)),
        median_residual_px=median_residual,
        median_edge_score=float(np.median(edge_scores)),
        offset_px=offset,
    )


def boundary_parallelism_deg(first: tuple[float, float, float],
                             second: tuple[float, float, float]) -> float:
    dot = abs(first[0] * second[0] + first[1] * second[1])
    return math.degrees(math.acos(float(np.clip(dot, -1.0, 1.0))))


def line_polarity(ref_gray: np.ndarray, p1: tuple[float, float],
                  p2: tuple[float, float]) -> float:
    dx, dy = p2[0] - p1[0], p2[1] - p1[1]
    L = math.hypot(dx, dy)
    if L < 1e-6:
        return 0.0
    nx, ny = -dy / L, dx / L
    deltas = []
    for t in np.linspace(0.1, 0.9, 9):
        cx = p1[0] * (1 - t) + p2[0] * t
        cy = p1[1] * (1 - t) + p2[1] * t
        offsets = np.arange(-12, 13, dtype=np.float64)
        xs = cx + offsets * nx
        ys = cy + offsets * ny
        prof = bilinear_sample(ref_gray, xs, ys)
        if np.isnan(prof).any():
            continue
        below = float(np.mean(prof[:8]))
        above = float(np.mean(prof[-8:]))
        deltas.append(above - below)
    if not deltas:
        return 0.0
    return float(np.median(deltas))


# ---------------------------------------------------------------------------
# Reference model construction
# ---------------------------------------------------------------------------

def sanitize_label(label: str) -> str:
    label = LABEL_ALIASES.get(label, label)
    s = (label.replace("ψ", "psi").replace("Ψ", "Psi")
              .replace("φ", "phi").replace("Φ", "Phi")
              .replace("⌀", "D"))
    s = re.sub(r"[^A-Za-z0-9_]", "_", s)
    if not s:
        s = "shape"
    if s[0].isdigit():
        s = "d" + s
    return s


def is_diameter_feature(label: str) -> bool:
    return sanitize_label(label) in DIAMETER_FEATURES


def is_circular_linestrip(shape_type: str, points: list[tuple[float, float]]) -> bool:
    if shape_type != "linestrip" or len(points) < 8:
        return False
    try:
        return circular_residual(points, fit_circle_kasa(points)) < CIRCLE_RESIDUAL_PX
    except (ValueError, np.linalg.LinAlgError):
        return False


def build_reference(label_path: Path, image_path: Path) -> ReferenceModel:
    annotation = read_labelme(label_path)
    gray = load_gray(image_path)

    seen: dict[str, int] = {}
    shapes: list[ShapeModel] = []
    for idx, raw in enumerate(annotation.get("shapes", [])):
        label = raw.get("label", "")
        if label in SKIP_LABELS:
            continue
        st = raw.get("shape_type", "")
        pts = [tuple(p) for p in raw.get("points", [])]
        san = sanitize_label(label)
        n = seen.get(san, 0)
        seen[san] = n + 1
        if n > 0:
            san = f"{san}_dup{n}"

        diameter_feature = is_diameter_feature(label)
        if diameter_feature and st != "linestrip":
            raise ValueError(
                f"diameter feature {label!r} must be a LabelMe linestrip, got {st!r}"
            )
        circular_linestrip = is_circular_linestrip(st, pts)
        if diameter_feature and not circular_linestrip:
            raise ValueError(
                f"diameter feature {label!r} must contain at least 8 points fitting a circle"
            )

        if circular_linestrip:
            try:
                cx, cy, r = robust_fit_circle(pts, fit_circle_kasa(pts))
            except (ValueError, np.linalg.LinAlgError):
                continue
            a0, a1, span = angle_extents(pts, (cx, cy, r))
            kind = "circle" if math.degrees(span) >= CLOSED_ARC_DEG else "arc"
            polarity = radial_polarity(gray, (cx, cy), r)
            template_angles = (
                np.linspace(0.0, 2.0 * math.pi, 240, endpoint=False, dtype=np.float64)
                if kind == "circle"
                else dense_arc_angles(a0, a1, r)
            )
            radial_template = radial_derivative_template(
                gray, (cx, cy), r, template_angles, TEMPLATE_HALF_WIDTH
            )
            emits_diameter_px = diameter_feature
            columns = [f"{san}_cx", f"{san}_cy", f"{san}_r"]
            quality_columns = [
                f"{san}.quality.template_score",
                f"{san}.quality.template_offset_px",
                f"{san}.quality.template_saturated",
                f"{san}.quality.edge_points",
                f"{san}.quality.fit_residual_px",
                f"{san}.quality.radius_delta_ref_px",
            ]
            reference_fit_residual = circular_residual(pts, (cx, cy, r))
            if emits_diameter_px:
                columns.append(f"{san}_diameter_px")
                quality_columns.extend([
                    f"{san}.quality.annotation_shape_type",
                    f"{san}.quality.annotation_points",
                    f"{san}.quality.reference_fit_residual_px",
                ])
            shapes.append(ShapeModel(
                index=idx, label=label, sanitized=san, kind=kind, points=pts,
                circle=(cx, cy, r), angle_start=a0, angle_end=a1,
                polarity=polarity, template_angles=template_angles,
                radial_template=radial_template,
                columns=columns, quality_columns=quality_columns,
                source_shape_type=st,
                reference_fit_residual_px=reference_fit_residual,
                emits_diameter_px=emits_diameter_px,
            ))
        elif st == "line" and len(pts) == 2:
            polarity = line_polarity(gray, pts[0], pts[1])
            endpoint_polarities = None
            quality_columns = [
                f"{san}.quality.upstream",
                f"{san}.quality.endpoint_snap_px",
            ]
            if san == "d7":
                endpoint_polarities = (
                    dimension_endpoint_polarity(gray, pts[0], pts[1], "p1"),
                    dimension_endpoint_polarity(gray, pts[0], pts[1], "p2"),
                )
                quality_columns.extend([
                    f"{san}.quality.p1_edge_points",
                    f"{san}.quality.p2_edge_points",
                    f"{san}.quality.p1_fit_residual_px",
                    f"{san}.quality.p2_fit_residual_px",
                    f"{san}.quality.p1_edge_score",
                    f"{san}.quality.p2_edge_score",
                    f"{san}.quality.p1_offset_ref_px",
                    f"{san}.quality.p2_offset_ref_px",
                    f"{san}.quality.boundary_parallelism_deg",
                ])
            shapes.append(ShapeModel(
                index=idx, label=label, sanitized=san, kind="line", points=pts,
                line_p1=pts[0], line_p2=pts[1], line_polarity=polarity,
                endpoint_polarities=endpoint_polarities,
                columns=[f"{san}_x1", f"{san}_y1", f"{san}_x2", f"{san}_y2", f"{san}_length"],
                quality_columns=quality_columns,
                source_shape_type=st,
            ))
        elif st == "point" and len(pts) == 1:
            shapes.append(ShapeModel(
                index=idx, label=label, sanitized=san, kind="point", points=pts,
                point=pts[0],
                columns=[f"{san}_x", f"{san}_y"],
                quality_columns=[
                    f"{san}.quality.anchor_distance_ref_px",
                    f"{san}.quality.upstream",
                ],
                source_shape_type=st,
            ))

    closed = [s for s in shapes if s.kind == "circle" and s.circle[2] <= ANCHOR_MAX_PIXELS]
    closed.sort(key=lambda s: s.circle[2])
    anchor_indices: list[int] = []
    if closed:
        primary = closed[0]
        anchor_indices.append(shapes.index(primary))
        if len(closed) >= 2:
            cx0, cy0 = primary.circle[0], primary.circle[1]
            second = max(closed[1:], key=lambda s: math.hypot(s.circle[0] - cx0, s.circle[1] - cy0))
            anchor_indices.append(shapes.index(second))

    return ReferenceModel(annotation, image_path, gray, shapes, anchor_indices)


# ---------------------------------------------------------------------------
# Detection helpers
# ---------------------------------------------------------------------------

def detect_circle_arc_candidate(target: np.ndarray, predicted_center: tuple[float, float],
                                predicted_radius: float, polarity: float,
                                angle_start: float, angle_end: float,
                                search_width: int,
                                prior_sigma: float | None = None,
                                reference_template: np.ndarray | None = None,
                                template_angles: np.ndarray | None = None
                                ) -> CircleArcDetection | None:
    cx, cy = predicted_center
    locked_radius = predicted_radius
    template_score = float("nan")
    template_offset = float("nan")
    template_saturated = False
    original_search_width = search_width
    original_prior_sigma = prior_sigma
    template_locked = False
    if reference_template is not None and template_angles is not None and len(template_angles) > 0:
        template_offset, template_score = template_offset_match(
            reference_template, target, predicted_center, predicted_radius, template_angles
        )
        saturation_threshold = TEMPLATE_OFFSET_SATURATION_FRAC * TEMPLATE_SEARCH_WIDTH
        if abs(template_offset) > saturation_threshold:
            # Flew to a neighbouring groove or hit the search-window wall.
            # Don't trust it; fall through to gradient-only fit.
            template_saturated = True
        elif template_score >= TEMPLATE_SCORE_FLOOR:
            locked_radius = predicted_radius + template_offset
            search_width = min(search_width, TEMPLATE_EDGE_SEARCH_WIDTH)
            prior_sigma = TEMPLATE_EDGE_PRIOR_SIGMA
            template_locked = True

    arc_extent = max(0.05, abs(angle_end - angle_start))

    def fit_at(radius: float, width: int, sigma: float | None) -> CircleArcDetection | None:
        arc_length = radius * arc_extent
        n = int(np.clip(arc_length, 60, 720))
        n = max(60, n)
        angles = np.linspace(angle_start, angle_end, n)
        pts: list[tuple[float, float]] = []
        for ang in angles:
            p = radial_edge_at_angle(target, (cx, cy), float(ang), radius,
                                      polarity, width, prior_sigma=sigma)
            if p is not None:
                pts.append(p)
        if len(pts) < max(20, n // 6):
            return None
        circle = robust_fit_circle(pts, (cx, cy, radius))
        residual = circular_residual(pts, circle)
        return CircleArcDetection(circle, len(pts), residual,
                                   template_score, template_offset, template_saturated)

    locked = fit_at(locked_radius, search_width, prior_sigma)
    if locked is not None:
        return locked
    if template_locked:
        return fit_at(predicted_radius, original_search_width, original_prior_sigma)
    return None


def detect_circle_arc(target: np.ndarray, predicted_center: tuple[float, float],
                       predicted_radius: float, polarity: float,
                       angle_start: float, angle_end: float,
                       search_width: int,
                       prior_sigma: float | None = None) -> tuple[float, float, float] | None:
    candidate = detect_circle_arc_candidate(
        target, predicted_center, predicted_radius, polarity,
        angle_start, angle_end, search_width, prior_sigma=prior_sigma
    )
    return None if candidate is None else candidate.circle


def detect_line(target: np.ndarray, p1_pred: tuple[float, float],
                p2_pred: tuple[float, float], polarity: float,
                search_width: int,
                min_edge_points: int | None = None) -> tuple[tuple[float, float], tuple[float, float]] | None:
    dx, dy = p2_pred[0] - p1_pred[0], p2_pred[1] - p1_pred[1]
    L = math.hypot(dx, dy)
    if L < 5:
        return None
    ux, uy = dx / L, dy / L
    nx, ny = -uy, ux
    n_samples = max(20, int(L / 4))
    edge_pts: list[tuple[float, float]] = []
    for t in np.linspace(0.05, 0.95, n_samples):
        cx = p1_pred[0] * (1 - t) + p2_pred[0] * t
        cy = p1_pred[1] * (1 - t) + p2_pred[1] * t
        e = perpendicular_edge_along_line(target, (cx, cy), (nx, ny), polarity, search_width)
        if e is not None:
            edge_pts.append(e)
    required = max(10, n_samples // 3) if min_edge_points is None else max(2, min_edge_points)
    if len(edge_pts) < required:
        return None
    line = fit_line_total_least_squares(edge_pts)
    return project_onto_line(p1_pred, line), project_onto_line(p2_pred, line)


def detect_dimension_endpoint_along_axis(
    target: np.ndarray,
    p1_pred: tuple[float, float],
    p2_pred: tuple[float, float],
    endpoint: str,
    strip_half_width: int = DIMENSION_ENDPOINT_STRIP_HALF_WIDTH,
    search_window: int = DIMENSION_ENDPOINT_SEARCH_WINDOW,
    prior_sigma: float = DIMENSION_ENDPOINT_PRIOR_SIGMA,
    min_edge_score: float = DIMENSION_ENDPOINT_MIN_EDGE_SCORE,
) -> tuple[tuple[float, float], float, float] | None:
    dx, dy = p2_pred[0] - p1_pred[0], p2_pred[1] - p1_pred[1]
    L = math.hypot(dx, dy)
    if L < 5:
        return None
    ux, uy = dx / L, dy / L
    nx, ny = -uy, ux
    center = 0.0 if endpoint == "p1" else L
    offsets = np.linspace(center - search_window, center + search_window, 2 * search_window + 1)
    strip_offsets = np.arange(-strip_half_width, strip_half_width + 1, dtype=np.float64)
    values: list[float] = []
    for off in offsets:
        xs = p1_pred[0] + off * ux + strip_offsets * nx
        ys = p1_pred[1] + off * uy + strip_offsets * ny
        prof = bilinear_sample(target, xs, ys)
        if np.isnan(prof).all():
            values.append(float("nan"))
        else:
            values.append(float(np.nanmean(prof)))
    arr = np.asarray(values, dtype=np.float64)
    valid = np.isfinite(arr)
    if valid.sum() < max(16, len(arr) // 3):
        return None
    arr = np.where(valid, arr, float(np.nanmedian(arr[valid])))
    arr = smooth_1d(arr, 9)
    deriv = np.diff(arr)
    if len(deriv) == 0:
        return None
    mids = (offsets[:-1] + offsets[1:]) / 2.0
    base_score = np.abs(deriv)
    prior = np.exp(-((mids - center) ** 2) / (2.0 * prior_sigma * prior_sigma))
    score = base_score * prior
    idx = int(np.argmax(score))
    edge_score = float(base_score[idx])
    if edge_score < min_edge_score:
        return None
    delta = parabolic_peak(score.tolist(), idx)
    step = float(mids[1] - mids[0]) if len(mids) >= 2 else 1.0
    off = float(mids[idx] + delta * step)
    return (p1_pred[0] + off * ux, p1_pred[1] + off * uy), edge_score, off


def arc_visibility_fraction(predicted_center: tuple[float, float], predicted_radius: float,
                            angle_start: float, angle_end: float,
                            shape: tuple[int, int], margin: int = 4) -> float:
    h, w = shape
    cx, cy = predicted_center
    n = 36
    angles = np.linspace(angle_start, angle_end, n)
    xs = cx + predicted_radius * np.cos(angles)
    ys = cy + predicted_radius * np.sin(angles)
    in_frame = (xs >= margin) & (xs < w - margin) & (ys >= margin) & (ys < h - margin)
    return float(in_frame.sum()) / float(n)


def line_visibility_fraction(p1: tuple[float, float], p2: tuple[float, float],
                              shape: tuple[int, int], margin: int = 4) -> float:
    h, w = shape
    n = 32
    ts = np.linspace(0.0, 1.0, n)
    xs = p1[0] * (1 - ts) + p2[0] * ts
    ys = p1[1] * (1 - ts) + p2[1] * ts
    in_frame = (xs >= margin) & (xs < w - margin) & (ys >= margin) & (ys < h - margin)
    return float(in_frame.sum()) / float(n)


# ---------------------------------------------------------------------------
# Image-level extraction
# ---------------------------------------------------------------------------

def _attempt_anchor(target: np.ndarray, ref_xy: tuple[float, float], guess: tuple[float, float],
                    radius: float, polarity: float, search_width: int,
                    prior_sigma: float | None = None,
                    radius_reject_frac: float = RADIUS_REJECT_FRAC,
                    ) -> tuple[float, float] | None:
    """Anchor-mode detection with center+radius gates. Returns target xy or None."""
    h, w = target.shape
    if not (0 <= guess[0] < w and 0 <= guess[1] < h):
        return None
    result = detect_circle_arc(target, guess, radius, polarity,
                               0.0, 2.0 * math.pi, search_width=search_width,
                               prior_sigma=prior_sigma)
    if result is None:
        return None
    ncx, ncy, nr = result
    if math.hypot(ncx - guess[0], ncy - guess[1]) > search_width * 1.5:
        return None
    if abs(nr - radius) > radius * radius_reject_frac:
        return None
    return (ncx, ncy)


def _attempt_anchor_template(target: np.ndarray, guess: tuple[float, float],
                             shape: ShapeModel, predicted_radius: float,
                             search_width: int, theta: float
                             ) -> tuple[float, float] | None:
    """Like _attempt_anchor but uses the shape's radial template to lock the
    radius offset robustly. Critical for circles whose outer edge gradient
    is weak relative to nested inner features (e.g. ψ3 in heavy translation).
    """
    h, w = target.shape
    if not (0 <= guess[0] < w and 0 <= guess[1] < h):
        return None
    if shape.radial_template is None or shape.template_angles is None:
        return None
    template_angles_target = shape.template_angles + theta
    pred_a0 = shape.angle_start + theta
    pred_a1 = shape.angle_end + theta
    candidate = detect_circle_arc_candidate(
        target, guess, predicted_radius, shape.polarity,
        pred_a0, pred_a1, search_width,
        prior_sigma=NON_ANCHOR_PRIOR_SIGMA,
        reference_template=shape.radial_template,
        template_angles=template_angles_target,
    )
    if candidate is None:
        return None
    ncx, ncy, nr = candidate.circle
    if math.hypot(ncx - guess[0], ncy - guess[1]) > search_width * 1.5:
        return None
    # Radius gate uses the predicted radius (already scale-corrected).
    if abs(nr - predicted_radius) > predicted_radius * RADIUS_REJECT_FRAC * 0.5:
        return None
    if candidate.template_saturated:
        return None
    return (ncx, ncy)


def extract_image(target_path: Path, ref: ReferenceModel,
                  search_width: int = DEFAULT_SEARCH_WIDTH,
                  allow_rotation: bool = True,
                  expand_anchors: bool = True,
                  initial_transform: tuple[float, float, float, float] | None = None,
                  refine_initial_transform: bool = False) -> Extraction:
    target = load_gray(target_path)
    target_edges = contrast_stretch(target)
    h, w = target.shape
    anchor_search = search_width * ANCHOR_SEARCH_MULT

    # 1. Phase-correlation prior (gradient-based, scale=1), unless an external
    # registration adapter supplied a reviewed pose. The default remains the
    # original v6 path; the optional seed never reads a target annotation.
    if initial_transform is None:
        dx0, dy0, _ = phase_correlation_shift(ref.gray, target)
        scale0, theta0 = 1.0, 0.0
    else:
        dx0, dy0, scale0, theta0 = (float(v) for v in initial_transform)
        if not all(math.isfinite(v) for v in (dx0, dy0, scale0, theta0)) or scale0 <= 0:
            raise ValueError("initial_transform must contain finite dx/dy/theta and positive scale")

    # 2a. Refine with the preferred anchor circles when visible.
    anchor_ref: list[tuple[float, float]] = []
    anchor_tgt: list[tuple[float, float]] = []
    used_anchor_indices: set[int] = set()
    preferred_anchor_indices = (
        ref.anchor_indices
        if initial_transform is None or refine_initial_transform
        else []
    )
    for ai in preferred_anchor_indices:
        s = ref.shapes[ai]
        cx, cy, r = s.circle
        guess = forward_xy(cx, cy, dx0, dy0, scale0, theta0)
        ntgt = _attempt_anchor(
            target, (cx, cy), guess, scale0 * r, s.polarity, anchor_search
        )
        if ntgt is None:
            continue
        anchor_ref.append((cx, cy))
        anchor_tgt.append(ntgt)
        used_anchor_indices.add(ai)

    if anchor_ref:
        dx, dy, scale, theta = solve_similarity(
            anchor_ref, anchor_tgt, allow_rotation=allow_rotation
        )
    else:
        dx, dy, scale, theta = dx0, dy0, scale0, theta0

    # 2b. Anchor pool expansion (v5): every closed circle still in frame is
    # a usable anchor. After the initial solve, re-predict each non-preferred
    # closed circle and add it to the anchor set if anchor-mode detection
    # succeeds. Then re-solve. Critical for positions where one preferred
    # anchor (e.g. M2) leaves the frame but ψ3 / other closed circles remain.
    expanded = False
    if expand_anchors:
        # Round 1: try all closed circles + arcs that can reasonably anchor.
        # Use template-locked detection; this handles weak edges (e.g. ψ3
        # outer ring) and nested-feature confusion that plain gradient search
        # can't disambiguate when alignment is loose.
        for i, s in enumerate(ref.shapes):
            if s.kind not in ("circle", "arc"):
                continue
            if i in used_anchor_indices:
                continue
            cx, cy, r = s.circle
            if r > ANCHOR_MAX_PIXELS and s.kind == "circle":
                continue
            pred = forward_xy(cx, cy, dx, dy, scale, theta)
            pred_r = scale * r
            ntgt = _attempt_anchor_template(target, pred, s, pred_r, anchor_search, theta)
            if ntgt is None:
                continue
            anchor_ref.append((cx, cy))
            anchor_tgt.append(ntgt)
            used_anchor_indices.add(i)
            expanded = True
        if expanded:
            dx, dy, scale, theta = solve_similarity(
                anchor_ref, anchor_tgt, allow_rotation=allow_rotation
            )
        # Round 2: with refined alignment, try anchors that initially failed
        # (the first pass may have rejected them due to scale/center error
        # propagating through the predicted radius).
        added_in_r2 = False
        if expanded:
            for i, s in enumerate(ref.shapes):
                if s.kind not in ("circle", "arc"):
                    continue
                if i in used_anchor_indices:
                    continue
                cx, cy, r = s.circle
                if r > ANCHOR_MAX_PIXELS and s.kind == "circle":
                    continue
                pred = forward_xy(cx, cy, dx, dy, scale, theta)
                pred_r = scale * r
                ntgt = _attempt_anchor_template(target, pred, s, pred_r, anchor_search, theta)
                if ntgt is None:
                    continue
                anchor_ref.append((cx, cy))
                anchor_tgt.append(ntgt)
                used_anchor_indices.add(i)
                added_in_r2 = True
            if added_in_r2:
                dx, dy, scale, theta = solve_similarity(
                    anchor_ref, anchor_tgt, allow_rotation=allow_rotation
                )

    n_anchors = len(anchor_ref)
    if initial_transform is not None:
        method = "external-pose-seed"
        if n_anchors:
            method += f"+anchors={n_anchors}"
    elif n_anchors == 0:
        method = "phase-correlation"
    elif n_anchors == 1:
        method = "anchors=1,translation"
    elif allow_rotation:
        method = f"anchors={n_anchors},similarity"
    else:
        method = f"anchors={n_anchors},translation+scale"
    if expanded:
        method += "+expanded"

    measurements: dict[str, object] = {}
    detected_circles_ref: dict[str, tuple[float, float, float]] = {}
    detected_points_ref: dict[str, tuple[float, float]] = {}

    # 3. Circles/arcs first. p1/p2 depend on circle centers; lines depend on
    # p1/p2; so detection order matters.
    for s in ref.shapes:
        if s.kind not in ("circle", "arc"):
            continue
        source_quality: list[object] = []
        if s.emits_diameter_px:
            source_quality = [
                s.source_shape_type,
                float(len(s.points)),
                s.reference_fit_residual_px,
            ]
        invalid_values = [float("nan")] * (4 if s.emits_diameter_px else 3)
        cx_ref, cy_ref, r_ref = s.circle
        pred_cx, pred_cy = forward_xy(cx_ref, cy_ref, dx, dy, scale, theta)
        pred_r = scale * r_ref
        pred_a0 = s.angle_start + theta
        pred_a1 = s.angle_end + theta
        visibility = arc_visibility_fraction(
            (pred_cx, pred_cy), pred_r, pred_a0, pred_a1, target.shape
        )
        if visibility < ARC_VISIBILITY_MIN_FRACTION:
            vals = invalid_values
            qvals = [
                float("nan"), float("nan"), 0.0,
                float("nan"), float("nan"), float("nan"),
            ] + source_quality
        else:
            # v5: enable template lock for both arcs and circles. Closed
            # circles whose outer edge is weak (e.g. ψ3 in heavily-translated
            # views) need the template to disambiguate from nested inner
            # rings that the gradient-only path locks onto.
            use_template = s.kind in ("arc", "circle")
            target_template_angles = None
            if use_template and s.template_angles is not None:
                target_template_angles = s.template_angles + theta
            candidate = detect_circle_arc_candidate(
                target, (pred_cx, pred_cy), pred_r, s.polarity,
                pred_a0, pred_a1, NON_ANCHOR_SEARCH_WIDTH,
                prior_sigma=NON_ANCHOR_PRIOR_SIGMA,
                reference_template=s.radial_template if use_template else None,
                template_angles=target_template_angles,
            )
            if candidate is None:
                vals = invalid_values
                qvals = [
                    float("nan"), float("nan"), 0.0,
                    float("nan"), float("nan"), float("nan"),
                ] + source_quality
            else:
                ncx, ncy, nr = candidate.circle
                radius_delta_ref = (nr - pred_r) / scale
                radius_gate_ref = (
                    ARC_ABS_RADIUS_REJECT_REF_PX
                    if s.kind == "arc"
                    else (pred_r * RADIUS_REJECT_FRAC) / scale
                )
                qbase = [
                    candidate.template_score,
                    candidate.template_offset,
                    1.0 if candidate.template_saturated else 0.0,
                    float(candidate.point_count),
                    candidate.median_residual,
                    radius_delta_ref,
                ] + source_quality
                if (math.hypot(ncx - pred_cx, ncy - pred_cy) > CENTER_REJECT_MULT * NON_ANCHOR_SEARCH_WIDTH
                        or abs(nr - pred_r) > pred_r * RADIUS_REJECT_FRAC
                        or abs(radius_delta_ref) > radius_gate_ref):
                    vals = invalid_values
                    qvals = qbase
                else:
                    ref_cx, ref_cy = inverse_xy(ncx, ncy, dx, dy, scale, theta)
                    ref_r = nr / scale
                    vals = [float(ref_cx), float(ref_cy), float(ref_r)]
                    if s.emits_diameter_px:
                        vals.append(float(2.0 * ref_r))
                    qvals = qbase
        for col, v in zip(s.columns, vals):
            measurements[col] = v
        for col, v in zip(s.quality_columns, qvals):
            measurements[col] = v
        if all(isinstance(v, float) and not math.isnan(v) for v in vals[:3]):
            detected_circles_ref[s.sanitized] = (vals[0], vals[1], vals[2])

    # 4. Anchor each annotated point to its nearest detected circle's centre
    # (in reference frame). Avoids inventing synthetic point coordinates.
    for s in ref.shapes:
        if s.kind != "point":
            continue
        best: tuple[float, float, float] | None = None
        best_name = None
        best_dist = float("inf")
        px_ref, py_ref = s.point
        for c in ref.shapes:
            if c.kind != "circle" or c.sanitized not in detected_circles_ref:
                continue
            ccx, ccy, _ = c.circle
            dist = math.hypot(px_ref - ccx, py_ref - ccy)
            if dist < best_dist:
                best_dist = dist
                best = detected_circles_ref[c.sanitized]
                best_name = c.sanitized
        if best is None or best_dist > POINT_ANCHOR_MAX_DISTANCE_REF_PX:
            vals: list[object] = [float("nan"), float("nan")]
            upstream_str = (
                "no_detected_circle"
                if best is None
                else f"too_far:{best_name}({best_dist:.1f}px)"
            )
            qvals = [
                float(best_dist) if math.isfinite(best_dist) else float("nan"),
                upstream_str,
            ]
        else:
            vals = [float(best[0]), float(best[1])]
            qvals = [float(best_dist), f"ok:{best_name}"]
            detected_points_ref[s.sanitized] = (float(best[0]), float(best[1]))
        for col, v in zip(s.columns, vals):
            measurements[col] = v
        for col, v in zip(s.quality_columns, qvals):
            measurements[col] = v

    def valid_point(name: str) -> tuple[float, float] | None:
        return detected_points_ref.get(name)

    def set_point_fallback(name: str, point: tuple[float, float], upstream: str) -> None:
        detected_points_ref[name] = (float(point[0]), float(point[1]))
        measurements[f"{name}_x"] = float(point[0])
        measurements[f"{name}_y"] = float(point[1])
        measurements[f"{name}.quality.anchor_distance_ref_px"] = float("nan")
        measurements[f"{name}.quality.upstream"] = upstream

    def orient_line_to_annotation(
        s: ShapeModel,
        e1: tuple[float, float],
        e2: tuple[float, float],
    ) -> tuple[tuple[float, float], tuple[float, float]]:
        direct = (
            math.hypot(e1[0] - s.line_p1[0], e1[1] - s.line_p1[1])
            + math.hypot(e2[0] - s.line_p2[0], e2[1] - s.line_p2[1])
        )
        swapped = (
            math.hypot(e2[0] - s.line_p1[0], e2[1] - s.line_p1[1])
            + math.hypot(e1[0] - s.line_p2[0], e1[1] - s.line_p2[1])
        )
        return (e1, e2) if direct <= swapped else (e2, e1)

    def normal_line_values(
        s: ShapeModel,
        line_search_width: int = search_width,
        min_edge_points: int | None = None,
    ) -> tuple[list[float], str]:
        p1 = forward_xy(s.line_p1[0], s.line_p1[1], dx, dy, scale, theta)
        p2 = forward_xy(s.line_p2[0], s.line_p2[1], dx, dy, scale, theta)
        visibility = line_visibility_fraction(p1, p2, target.shape)
        if visibility < LINE_VISIBILITY_MIN_FRACTION:
            return [float("nan")] * 5, "out_of_frame"
        result = detect_line(
            target_edges, p1, p2, s.line_polarity, line_search_width,
            min_edge_points=min_edge_points,
        )
        if result is None:
            return [float("nan")] * 5, "line_detect_failed"
        (x1, y1), (x2, y2) = result
        ref_x1, ref_y1 = inverse_xy(x1, y1, dx, dy, scale, theta)
        ref_x2, ref_y2 = inverse_xy(x2, y2, dx, dy, scale, theta)
        length = math.hypot(ref_x2 - ref_x1, ref_y2 - ref_y1)
        return [float(ref_x1), float(ref_y1), float(ref_x2), float(ref_y2), float(length)], "ok"

    def dimension_endpoint_ref(
        s: ShapeModel,
        endpoint_name: str,
    ) -> tuple[float, float, float, float] | None:
        p1 = forward_xy(s.line_p1[0], s.line_p1[1], dx, dy, scale, theta)
        p2 = forward_xy(s.line_p2[0], s.line_p2[1], dx, dy, scale, theta)
        endpoint = detect_dimension_endpoint_along_axis(target_edges, p1, p2, endpoint_name)
        if endpoint is None:
            return None
        (x, y), edge_score, offset = endpoint
        ref_x, ref_y = inverse_xy(x, y, dx, dy, scale, theta)
        return float(ref_x), float(ref_y), float(edge_score), float(offset)

    def d7_dual_boundary_values(s: ShapeModel) -> tuple[list[float], list[object]]:
        """Measure 7 from two independently detected and fitted boundaries."""
        p1_pred = forward_xy(s.line_p1[0], s.line_p1[1], dx, dy, scale, theta)
        p2_pred = forward_xy(s.line_p2[0], s.line_p2[1], dx, dy, scale, theta)
        polarities = s.endpoint_polarities or (0.0, 0.0)
        first = detect_dimension_boundary(
            target_edges, p1_pred, p2_pred, "p1", polarity=polarities[0]
        )
        second = detect_dimension_boundary(
            target_edges, p1_pred, p2_pred, "p2", polarity=polarities[1]
        )

        def metric(boundary: BoundaryDetection | None, name: str) -> float:
            if boundary is None:
                return float("nan")
            return float(getattr(boundary, name))

        failed = []
        if first is None:
            failed.append("p1")
        if second is None:
            failed.append("p2")
        if failed:
            quality: list[object] = [
                "failed:" + ",".join(failed) + "_boundary_fit",
                float("nan"),
                metric(first, "point_count"),
                metric(second, "point_count"),
                metric(first, "median_residual_px") / scale if first else float("nan"),
                metric(second, "median_residual_px") / scale if second else float("nan"),
                metric(first, "median_edge_score"),
                metric(second, "median_edge_score"),
                metric(first, "offset_px") / scale if first else float("nan"),
                metric(second, "offset_px") / scale if second else float("nan"),
                float("nan"),
            ]
            return [float("nan")] * 5, quality

        ref_x1, ref_y1 = inverse_xy(
            first.feature_point[0], first.feature_point[1], dx, dy, scale, theta
        )
        ref_x2, ref_y2 = inverse_xy(
            second.feature_point[0], second.feature_point[1], dx, dy, scale, theta
        )
        length = math.hypot(ref_x2 - ref_x1, ref_y2 - ref_y1)
        offset1_ref = first.offset_px / scale
        offset2_ref = second.offset_px / scale
        quality = [
            "ok:dual_boundary_fit",
            max(abs(offset1_ref), abs(offset2_ref)),
            float(first.point_count),
            float(second.point_count),
            first.median_residual_px / scale,
            second.median_residual_px / scale,
            first.median_edge_score,
            second.median_edge_score,
            offset1_ref,
            offset2_ref,
            boundary_parallelism_deg(first.line, second.line),
        ]
        return [
            float(ref_x1), float(ref_y1),
            float(ref_x2), float(ref_y2), float(length),
        ], quality

    def d0_8_feature_values(s: ShapeModel) -> tuple[list[float], str]:
        top = dimension_endpoint_ref(s, "p1")
        if top is None:
            return [float("nan")] * 5, "top_edge_failed"
        bottom = dimension_endpoint_ref(s, "p2")
        if bottom is None:
            return [float("nan")] * 5, "bottom_edge_failed"
        ref_x1, ref_y1, top_edge, top_offset = top
        ref_x2, ref_y2, bottom_edge, bottom_offset = bottom
        length = math.hypot(ref_x2 - ref_x1, ref_y2 - ref_y1)
        return [
            float(ref_x1), float(ref_y1), float(ref_x2), float(ref_y2), float(length)
        ], (
            f"ok:top_edge+bottom_edge(top_edge={top_edge:.1f},bottom_edge={bottom_edge:.1f},"
            f"top_offset={top_offset:.1f},bottom_offset={bottom_offset:.1f})"
        )

    def d3_2_feature_values(s: ShapeModel) -> tuple[list[float], str]:
        m2 = detected_circles_ref.get("M2")
        if m2 is None:
            return [float("nan")] * 5, "missing:M2"
        bottom = dimension_endpoint_ref(s, "p2")
        if bottom is None:
            return [float("nan")] * 5, "bottom_edge_failed"
        ref_x1, ref_y1 = m2[0], m2[1]
        ref_x2, ref_y2, bottom_edge, bottom_offset = bottom
        length = math.hypot(ref_x2 - ref_x1, ref_y2 - ref_y1)
        return [
            float(ref_x1), float(ref_y1), float(ref_x2), float(ref_y2), float(length)
        ], f"ok:M2+bottom_edge(edge={bottom_edge:.1f},offset={bottom_offset:.1f})"

    for s in ref.shapes:
        if s.kind != "line":
            continue
        upstream = "ok"
        snap_distance: float = float("nan")
        quality_values: list[object] | None = None
        if s.sanitized == "d7":
            vals, quality_values = d7_dual_boundary_values(s)
        elif s.label == "7.7":
            p1_ref = valid_point("p1")
            p2_ref = valid_point("p2")
            missing = [name for name, p in (("p1", p1_ref), ("p2", p2_ref)) if p is None]
            if missing:
                base, base_status = normal_line_values(s)
                if any(math.isnan(v) for v in base):
                    vals = [float("nan")] * 5
                    upstream = "missing:" + ",".join(missing)
                else:
                    line_p1, line_p2 = orient_line_to_annotation(
                        s,
                        (base[0], base[1]),
                        (base[2], base[3]),
                    )
                    if p1_ref is None:
                        p1_ref = line_p1
                        set_point_fallback("p1", p1_ref, "ok:d7_7_line_fallback")
                    if p2_ref is None:
                        p2_ref = line_p2
                        set_point_fallback("p2", p2_ref, "ok:d7_7_line_fallback")
                    length = math.hypot(p2_ref[0] - p1_ref[0], p2_ref[1] - p1_ref[1])
                    vals = [p1_ref[0], p1_ref[1], p2_ref[0], p2_ref[1], length]
                    upstream = "ok:" + ",".join(missing) + "_from_d7_7_line"
            else:
                length = math.hypot(p2_ref[0] - p1_ref[0], p2_ref[1] - p1_ref[1])
                vals = [p1_ref[0], p1_ref[1], p2_ref[0], p2_ref[1], length]
                upstream = "ok:p1,p2"
        elif s.label == "12":
            p2_ref = valid_point("p2")
            base, base_status = normal_line_values(s)
            if p2_ref is None:
                vals = [float("nan")] * 5
                upstream = "missing:p2"
            elif any(math.isnan(v) for v in base):
                vals = [float("nan")] * 5
                upstream = "line:" + base_status
            else:
                e1 = (base[0], base[1])
                e2 = (base[2], base[3])
                d1 = math.hypot(e1[0] - p2_ref[0], e1[1] - p2_ref[1])
                d2 = math.hypot(e2[0] - p2_ref[0], e2[1] - p2_ref[1])
                near_d = min(d1, d2)
                snap_distance = float(near_d)
                other = e1 if d1 >= d2 else e2
                length = math.hypot(other[0] - p2_ref[0], other[1] - p2_ref[1])
                vals = [p2_ref[0], p2_ref[1], other[0], other[1], length]
                upstream = "ok:p2+line"
                if near_d > D12_ENDPOINT_SNAP_WARN_PX:
                    upstream = f"warn:p2_off_line({near_d:.1f}px)"
        elif s.label in RAW_DETECTED_LINE_LABELS:
            if s.label == "0.8":
                vals, base_status = d0_8_feature_values(s)
            elif s.label == "3.2":
                vals, base_status = d3_2_feature_values(s)
            else:
                vals, base_status = normal_line_values(s)
            upstream = base_status
        else:
            vals, base_status = normal_line_values(s)
            upstream = base_status if base_status != "ok" else "ok"
        for col, v in zip(s.columns, vals):
            measurements[col] = v
        if quality_values is None:
            quality_values = [upstream, snap_distance]
        for col, v in zip(s.quality_columns, quality_values):
            measurements[col] = v

    raw_pair = {s.label: s for s in ref.shapes if s.label in RAW_DETECTED_LINE_LABELS}
    if {"0.8", "3.2"} <= raw_pair.keys():
        pair_status: dict[str, tuple[bool, str]] = {}
        for label in ("0.8", "3.2"):
            s = raw_pair[label]
            raw_length = measurements.get(s.columns[-1], float("nan"))
            try:
                ok = math.isfinite(float(raw_length))
            except (TypeError, ValueError):
                ok = False
            pair_status[label] = (ok, str(measurements.get(s.quality_columns[0], "")))

        if pair_status["0.8"][0] != pair_status["3.2"][0]:
            failed_label = "0.8" if not pair_status["0.8"][0] else "3.2"
            reason = pair_status[failed_label][1] or "invalid"
            for label in ("0.8", "3.2"):
                s = raw_pair[label]
                for col in s.columns:
                    measurements[col] = float("nan")
                measurements[s.quality_columns[0]] = (
                    f"paired_invalid:{failed_label}_failed({reason})"
                )
                measurements[s.quality_columns[1]] = float("nan")

    return Extraction(dx, dy, scale, math.degrees(theta), method, measurements)


# ---------------------------------------------------------------------------
# Directory walking
# ---------------------------------------------------------------------------

_RE_SAMPLE = re.compile(r"^(?:sample[_\-]?)?s?(\d+)$", re.IGNORECASE)
_RE_POSITION = re.compile(r"^(?:position|pos)[_\-]?(\d+)$", re.IGNORECASE)
_RE_FLAT_SAMPLE_POSITION = re.compile(
    r"(?:^|[_\-\s])(?:sample[_\-\s]*)?s?(\d+)[_\-\s]+(?:position|pos)[_\-\s]*(\d+)(?:$|[_\-\s])",
    re.IGNORECASE,
)


def infer_sample_position(path: Path, root: Path) -> tuple[str, str]:
    rel = path.relative_to(root)
    sample = position = None
    for part in rel.parts[:-1]:
        if sample is None and _RE_SAMPLE.match(part):
            sample = part
        if position is None and _RE_POSITION.match(part):
            position = part
    if sample is None or position is None:
        m = _RE_FLAT_SAMPLE_POSITION.search(path.stem)
        if m:
            sample = sample or f"s{m.group(1)}"
            position = position or f"pos{m.group(2)}"
    if sample is None and len(rel.parts) >= 3:
        sample = rel.parts[0]
    if position is None and len(rel.parts) >= 2:
        position = rel.parts[-2]
    return sample or "unknown", position or "unknown"


def walk_images(root: Path, exclude_paths: set[Path] | None = None) -> list[tuple[str, str, int, Path]]:
    excluded = {p.resolve() for p in (exclude_paths or set())}
    by_pos: dict[tuple[str, str], list[Path]] = {}
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        if p.suffix.lower() not in IMAGE_SUFFIXES:
            continue
        if p.resolve() in excluded:
            continue
        sample, position = infer_sample_position(p, root)
        by_pos.setdefault((sample, position), []).append(p)
    records: list[tuple[str, str, int, Path]] = []
    for (sample, position), paths in sorted(by_pos.items()):
        for i, p in enumerate(sorted(paths)):
            records.append((sample, position, i, p))
    return records


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _format_csv_value(v: object) -> str:
    if isinstance(v, str):
        return v
    if isinstance(v, float) and math.isnan(v):
        return "nan"
    if isinstance(v, float):
        return f"{v:.4f}"
    if isinstance(v, int):
        return str(v)
    return str(v)


def _format_summary_value(value: object, digits: int = 4) -> str:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return str(value)
    return f"{numeric:.{digits}f}" if math.isfinite(numeric) else "nan"


def write_csv(out_path: Path, ref: ReferenceModel, rows: list[Extraction],
              records: list[tuple[str, str, int, Path]]) -> list[str]:
    columns = ["sample", "position", "repeat", "image",
               "dx", "dy", "scale", "theta_deg", "align_method"]
    for s in ref.shapes:
        columns.extend(s.columns)
        columns.extend(s.quality_columns)
    with open(out_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(columns)
        for (sample, position, repeat, path), ext in zip(records, rows):
            row = [
                sample, position, repeat, str(path),
                f"{ext.transform_dx:.4f}", f"{ext.transform_dy:.4f}",
                f"{ext.transform_scale:.6f}", f"{ext.transform_theta_deg:.5f}",
                ext.align_method,
            ]
            for s in ref.shapes:
                for col in s.columns + s.quality_columns:
                    v = ext.measurements.get(col, float("nan"))
                    row.append(_format_csv_value(v))
            w.writerow(row)
    return columns


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--label", default="annotation.json", help="Path to the LabelMe JSON.")
    ap.add_argument("--reference-image", default="reference.bmp", help="Path to the annotated reference image.")
    ap.add_argument("--input-dir", required=True, help="Directory tree containing s{i}/pos{j}/*.bmp.")
    ap.add_argument("--out", required=True, help="Output measurements CSV.")
    ap.add_argument("--include-reference", action="store_true",
                    help="Also process the reference image when it is inside --input-dir. "
                         "Intended for a one-image smoke test only.")
    ap.add_argument("--print-confirmed-features", action="store_true",
                    help="Print dimension 7 and Phi12.2 values/quality after extraction.")
    ap.add_argument("--search-width", type=int, default=DEFAULT_SEARCH_WIDTH,
                    help=f"Subpixel-edge search half-width (px). Default {DEFAULT_SEARCH_WIDTH}.")
    ap.add_argument("--rotation", action="store_true",
                    help="Enable rotation in the alignment (similarity 4DoF). Off by default: "
                         "with only 2 anchors, anchor detection noise can produce a small "
                         "spurious rotation (~0.1-0.3°) that displaces line endpoints by "
                         "~1px and degrades length measurements. With v5 anchor expansion "
                         "you typically have 3+ anchors so this becomes safer to enable.")
    ap.add_argument("--no-expand-anchors", action="store_true",
                    help="Disable v5 anchor pool expansion (revert to v4 fixed-anchor behavior). "
                         "Use only for backward-compatibility comparisons.")
    ap.add_argument("--no-static-stabilize", action="store_true",
                    help="Deprecated no-op. Raw per-image detector output is always used.")
    ap.add_argument("--static-stabilize-min-completeness", type=float,
                    default=0.90,
                    help=argparse.SUPPRESS)
    args = ap.parse_args()

    reference_image = Path(args.reference_image)
    ref = build_reference(Path(args.label), reference_image)
    print(f"Reference: {len(ref.shapes)} shapes "
          f"({sum(s.kind=='circle' for s in ref.shapes)} circles, "
          f"{sum(s.kind=='arc' for s in ref.shapes)} arcs, "
          f"{sum(s.kind=='line' for s in ref.shapes)} lines, "
          f"{sum(s.kind=='point' for s in ref.shapes)} points), "
          f"anchors={[ref.shapes[i].label for i in ref.anchor_indices]}, "
          f"alignment={'similarity (incl. rotation)' if args.rotation else 'translation+scale'}")

    excluded = set() if args.include_reference else {reference_image}
    records = walk_images(Path(args.input_dir), exclude_paths=excluded)
    print(f"Found {len(records)} images.")

    extractions: list[Extraction] = []
    for sample, position, repeat, path in records:
        try:
            ext = extract_image(path, ref, search_width=args.search_width,
                                allow_rotation=args.rotation,
                                expand_anchors=not args.no_expand_anchors)
        except Exception as exc:
            print(f"  ERROR {path}: {exc}")
            ext = Extraction(0.0, 0.0, 1.0, 0.0, f"error:{exc}", {})
        primary_values = [
            v for k, v in ext.measurements.items()
            if ".quality." not in k
        ]
        n_ok = sum(1 for v in primary_values if isinstance(v, float) and not math.isnan(v))
        n_total = len(primary_values)
        print(f"  {sample}/{position}#{repeat:03d} {path.name}: "
              f"align={ext.align_method} dx={ext.transform_dx:+.1f} "
              f"dy={ext.transform_dy:+.1f} s={ext.transform_scale:.4f} "
              f"θ={ext.transform_theta_deg:+.3f}° → {n_ok}/{n_total} measurements")
        extractions.append(ext)

    print("Static size stabilization: disabled; writing raw per-image detections only.")

    columns = write_csv(Path(args.out), ref, extractions, records)
    print(f"Wrote {args.out}: {len(records)} rows × {len(columns)} columns "
          f"({len(columns) - 9} measurement columns).")
    if args.print_confirmed_features:
        print("Confirmed feature summary (reference-frame pixels):")
        for (sample, position, repeat, path), ext in zip(records, extractions):
            m = ext.measurements
            print(
                f"  {sample}/{position}#{repeat:03d} {path.name}: "
                f"7={_format_summary_value(m.get('d7_length'))} px, "
                f"status={m.get('d7.quality.upstream', 'missing')}, "
                f"edge_points={_format_summary_value(m.get('d7.quality.p1_edge_points'), 0)}/"
                f"{_format_summary_value(m.get('d7.quality.p2_edge_points'), 0)}, "
                f"fit_residual={_format_summary_value(m.get('d7.quality.p1_fit_residual_px'))}/"
                f"{_format_summary_value(m.get('d7.quality.p2_fit_residual_px'))} px, "
                f"edge_score={_format_summary_value(m.get('d7.quality.p1_edge_score'))}/"
                f"{_format_summary_value(m.get('d7.quality.p2_edge_score'))}, "
                f"prior_offset={_format_summary_value(m.get('d7.quality.p1_offset_ref_px'))}/"
                f"{_format_summary_value(m.get('d7.quality.p2_offset_ref_px'))} px, "
                f"parallelism={_format_summary_value(m.get('d7.quality.boundary_parallelism_deg'))} deg; "
                f"Phi12.2 r={_format_summary_value(m.get('Phi12_2_r'))} px, "
                f"diameter={_format_summary_value(m.get('Phi12_2_diameter_px'))} px, "
                f"edge_points={_format_summary_value(m.get('Phi12_2.quality.edge_points'), 0)}, "
                f"fit_residual={_format_summary_value(m.get('Phi12_2.quality.fit_residual_px'))} px, "
                f"template_score={_format_summary_value(m.get('Phi12_2.quality.template_score'))}, "
                f"radius_delta={_format_summary_value(m.get('Phi12_2.quality.radius_delta_ref_px'))} px"
            )


if __name__ == "__main__":
    main()
