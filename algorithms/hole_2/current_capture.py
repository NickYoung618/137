"""Current-capture registration and measurement from one manual reference.

The frozen two-shape manual annotation and its paired image are the only
runtime reference.  Registration supports are derived from that image's own
pixels; dimension 7 and Phi12.2 are seeded by its annotation and re-detected
from every target image under the existing quality gates.
"""
from __future__ import annotations

import hashlib
import json
import math
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np
from PIL import Image

from .main import (
    D7_BOUNDARY_MIN_AXIS_COSINE,
    EDGE_SCORE_FLOOR,
    BoundaryDetection,
    Extraction,
    ReferenceModel,
    ShapeModel,
    build_reference,
    bilinear_sample,
    boundary_parallelism_deg,
    circular_residual,
    contrast_stretch,
    detect_dimension_boundary,
    extract_image,
    fit_circle_kasa,
    forward_xy,
    geometric_circle_fit,
    gradient_magnitude,
    inverse_xy,
    line_axis_intersection,
    load_gray,
    parabolic_peak,
    radial_edge_at_angle,
    robust_fit_line,
    solve_similarity,
    smooth_1d,
)


ALGORITHM_VERSION = "hole2-current-capture-registration/5"
RESULT_SCHEMA_VERSION = "hole2-current-capture-result/2"
EVIDENCE_SCOPE = "single_image_pixel_geometry_only_not_repeatability_mm_accuracy_or_production_ok_ng"
AUTHORITATIVE_REFERENCE_VERSION = "hole2-authoritative-manual-reference/1"
AUTHORITATIVE_REFERENCE_ANNOTATION_SHA256 = (
    "018e3449c051c15f7946315bd0d7f21cd79f4d4983efca0d11c7d98f02bfffa6"
)
AUTHORITATIVE_REFERENCE_IMAGE_SHA256 = (
    "faf357c2e6e8e58d667f76a3d9ed4f4d51ab4d451c2661cf0efbc641405b2d8b"
)


@dataclass(frozen=True)
class SimilarityTransform:
    """Reference-pixel to target-pixel similarity transform."""

    dx: float
    dy: float
    scale: float
    theta_deg: float

    @property
    def theta_rad(self) -> float:
        return math.radians(self.theta_deg)

    def forward(self, x: float, y: float) -> tuple[float, float]:
        return forward_xy(x, y, self.dx, self.dy, self.scale, self.theta_rad)

    def inverse(self, x: float, y: float) -> tuple[float, float]:
        return inverse_xy(x, y, self.dx, self.dy, self.scale, self.theta_rad)

    def as_dict(self) -> dict[str, float]:
        return {
            "dx": float(self.dx),
            "dy": float(self.dy),
            "scale": float(self.scale),
            "thetaDeg": float(self.theta_deg),
        }

    def inverse_as_dict(self) -> dict[str, float]:
        """Return target-to-reference parameters in the same similarity form."""
        if not math.isfinite(self.scale) or self.scale <= 0.0:
            raise ValueError("similarity scale must be finite and positive")
        inverse_dx, inverse_dy = self.inverse(0.0, 0.0)
        return {
            "dx": float(inverse_dx),
            "dy": float(inverse_dy),
            "scale": float(1.0 / self.scale),
            "thetaDeg": float(-self.theta_deg),
        }


@dataclass(frozen=True)
class _SupportGroup:
    group_id: str
    shapes: tuple[ShapeModel, ...]
    reference_point: tuple[float, float]

    @property
    def labels(self) -> list[str]:
        return [shape.label for shape in self.shapes]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_authoritative_reference(
    annotation_path: Path,
    image_path: Path,
) -> ReferenceModel:
    """Load the only authoritative runtime reference or fail closed."""
    if not annotation_path.is_file():
        raise FileNotFoundError(
            f"authoritative reference annotation does not exist: {annotation_path}"
        )
    if not image_path.is_file():
        raise FileNotFoundError(
            f"authoritative reference image does not exist: {image_path}"
        )
    annotation_sha = sha256_file(annotation_path)
    if annotation_sha != AUTHORITATIVE_REFERENCE_ANNOTATION_SHA256:
        raise ValueError(
            "authoritative reference annotation SHA-256 mismatch: "
            f"expected={AUTHORITATIVE_REFERENCE_ANNOTATION_SHA256} actual={annotation_sha}"
        )
    image_sha = sha256_file(image_path)
    if image_sha != AUTHORITATIVE_REFERENCE_IMAGE_SHA256:
        raise ValueError(
            "authoritative reference image SHA-256 mismatch: "
            f"expected={AUTHORITATIVE_REFERENCE_IMAGE_SHA256} actual={image_sha}"
        )
    model = build_reference(annotation_path, image_path)
    shapes = {shape.sanitized: shape for shape in model.shapes}
    if set(shapes) != {"d7", "Phi12_2"}:
        raise ValueError("authoritative reference must contain exactly 7 and Phi12.2")
    d7 = shapes["d7"]
    phi = shapes["Phi12_2"]
    if d7.kind != "line" or len(d7.points) != 2:
        raise ValueError("authoritative reference 7 must be a two-point line")
    if phi.kind != "arc" or len(phi.points) != 80 or phi.circle is None:
        raise ValueError("authoritative reference Phi12.2 must be an 80-point arc")
    return model


def _transform_from_registration(registration: dict[str, Any]) -> SimilarityTransform:
    value = registration.get("transform")
    if not registration.get("registrationValid") or not isinstance(value, dict):
        raise ValueError("registration transform is unavailable")
    return SimilarityTransform(
        float(value["dx"]), float(value["dy"]),
        float(value["scale"]), float(value["thetaDeg"]),
    )


def load_registration_config(path: Path) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8"))
    if config.get("schema_version") != "hole2-current-capture-registration-config/1":
        raise ValueError("unsupported registration config schema_version")
    orientations = config.get("orientations_deg")
    if not isinstance(orientations, list) or set(orientations) != {0, 90, 180, 270}:
        raise ValueError("orientations_deg must contain exactly 0, 90, 180, 270")
    for section in (
        "coarse", "supports", "quality", "registration_recovery", "d7",
        "phi12_2", "geometry_consistency",
    ):
        if not isinstance(config.get(section), dict):
            raise ValueError(f"registration config missing object: {section}")
    coarse = config["coarse"]
    if not (0 < float(coarse["scale_min"]) < float(coarse["scale_max"])):
        raise ValueError("coarse scale bounds are invalid")
    if float(coarse["scale_step"]) <= 0:
        raise ValueError("coarse scale_step must be positive")
    quality = config["quality"]
    if int(quality["min_support_groups"]) < 3:
        raise ValueError("min_support_groups must be at least 3")
    phi = config["phi12_2"]
    main_min = float(phi["min_radius_scale_ratio"])
    recovery_min = float(phi["recovery_min_radius_scale_ratio"])
    if not math.isclose(main_min, 0.88, abs_tol=1e-12):
        raise ValueError("phi12_2 main min_radius_scale_ratio must remain 0.88")
    if not math.isclose(recovery_min, 0.84, abs_tol=1e-12):
        raise ValueError("phi12_2 recovery_min_radius_scale_ratio must remain 0.84")
    if recovery_min >= main_min:
        raise ValueError("phi12_2 recovery radius lower bound must be below main bound")
    center_recovery_radius = float(phi["center_recovery_search_radius_px"])
    if not 0.0 < center_recovery_radius < float(phi["search_radius_px"]):
        raise ValueError("phi12_2 center recovery search radius must be positive and locally bounded")
    if not 0 < int(phi["multicircle_radial_search_width_px"]) <= int(phi["search_radius_px"]):
        raise ValueError("phi12_2 multicircle radial search must remain locally bounded")
    if not 0.0 < float(phi["multicircle_ransac_inlier_residual_px"]) <= float(
        phi["max_fit_residual_target_px"]
    ):
        raise ValueError("phi12_2 multicircle RANSAC residual cannot loosen the fit gate")
    if not 0.0 < float(phi["min_angle_coverage_fraction"]) <= 1.0:
        raise ValueError("phi12_2 minimum angle coverage fraction is invalid")
    d7 = config["d7"]
    offsets = d7["band_offsets_target_px"]
    if not isinstance(offsets, list) or len(offsets) < 3 or 0.0 not in [float(v) for v in offsets]:
        raise ValueError("d7 parallel bands require at least three explicit offsets including zero")
    if int(d7["min_consistent_bands"]) < 3 or int(d7["min_consistent_bands"]) > len(offsets):
        raise ValueError("d7 min_consistent_bands is invalid")
    if int(d7["band_strip_samples"]) < int(d7["min_boundary_points"]):
        raise ValueError("d7 band strip samples cannot undercut the original point gate")
    if float(d7["max_cross_band_length_deviation_px"]) <= 0.0:
        raise ValueError("d7 cross-band length deviation gate must be positive")
    if not 3.0 <= float(d7["paired_edge_min_width_target_px"]) < float(
        d7["paired_edge_max_width_target_px"]
    ) <= 24.0:
        raise ValueError("d7 paired edge width bounds are invalid")
    if int(d7["paired_edge_min_support"]) < int(d7["min_boundary_points"]):
        raise ValueError("d7 paired edge support cannot undercut the original point gate")
    if float(d7["paired_edge_min_peak"]) < float(d7["min_edge_score"]):
        raise ValueError("d7 paired edge peak cannot undercut the original edge gate")
    if int(d7["paired_edge_strip_samples"]) < int(d7["paired_edge_min_support"]):
        raise ValueError("d7 paired edge strip samples cannot undercut its support gate")
    phase_half_width = int(phi["phase_profile_half_width_px"])
    if phase_half_width < 10 or phase_half_width > int(phi["search_radius_px"]):
        raise ValueError("phi12_2 phase profile half width must remain locally bounded")
    if not 0.0 <= float(phi["phase_angle_extension_deg"]) <= 10.0:
        raise ValueError("phi12_2 phase angle extension must remain at most 10 degrees")
    if int(phi["phase_min_points"]) < int(phi["min_edge_points"]):
        raise ValueError("phi12_2 phase point gate cannot undercut the original point gate")
    if float(phi["phase_ransac_inlier_residual_px"]) > float(
        phi["max_fit_residual_target_px"]
    ):
        raise ValueError("phi12_2 phase RANSAC residual cannot loosen the fit gate")
    if float(phi["phase_min_edge_score"]) < EDGE_SCORE_FLOOR:
        raise ValueError("phi12_2 phase edge score cannot undercut the core floor")
    geometry_gate = float(config["geometry_consistency"]["max_reference_ratio_absolute_deviation"])
    if not 0.0 < geometry_gate < 0.25:
        raise ValueError("geometry consistency ratio gate is invalid")
    registration_recovery = config["registration_recovery"]
    recovery_refine_radius = float(registration_recovery["refine_search_radius_target_px"])
    primary_refine_radius = float(config["supports"]["refine_search_radius_target_px"])
    primary_search_radius = float(config["supports"]["search_radius_target_px"])
    if not primary_refine_radius < recovery_refine_radius <= primary_search_radius:
        raise ValueError(
            "registration recovery refine radius must exceed primary refine radius "
            "without exceeding the original support search radius"
        )
    return config


def fit_similarity_transform(
    reference_points: Iterable[tuple[float, float]],
    target_points: Iterable[tuple[float, float]],
) -> tuple[SimilarityTransform, list[float]]:
    reference = np.asarray(list(reference_points), dtype=np.float64)
    target = np.asarray(list(target_points), dtype=np.float64)
    if len(reference) != len(target) or len(reference) < 2:
        raise ValueError("similarity fit needs equal point sets with at least two points")
    dx, dy, scale, theta = solve_similarity(reference, target, allow_rotation=True)
    transform = SimilarityTransform(dx, dy, scale, math.degrees(theta))
    predictions = np.asarray([transform.forward(float(x), float(y)) for x, y in reference])
    residuals = np.linalg.norm(predictions - target, axis=1)
    return transform, [float(value) for value in residuals]


def _circular_shapes(reference: ReferenceModel) -> list[ShapeModel]:
    return [shape for shape in reference.shapes if shape.kind in ("circle", "arc") and shape.circle]


def _cluster_supports(reference: ReferenceModel, distance: float) -> list[_SupportGroup]:
    shapes = _circular_shapes(reference)
    if not shapes:
        raise ValueError("reference annotation has no circle/arc registration shapes")
    centers = np.asarray([shape.circle[:2] for shape in shapes], dtype=np.float64)
    unseen = set(range(len(shapes)))
    components: list[list[int]] = []
    while unseen:
        seed = min(unseen)
        unseen.remove(seed)
        stack = [seed]
        component: list[int] = []
        while stack:
            index = stack.pop()
            component.append(index)
            neighbours = [
                other for other in sorted(unseen)
                if float(np.linalg.norm(centers[index] - centers[other])) <= distance
            ]
            for other in neighbours:
                unseen.remove(other)
                stack.append(other)
        components.append(sorted(component))

    groups: list[_SupportGroup] = []
    for number, component in enumerate(components):
        members = tuple(shapes[index] for index in component)
        member_centers = np.asarray([shape.circle[:2] for shape in members], dtype=np.float64)
        point = tuple(float(v) for v in member_centers.mean(axis=0))
        groups.append(_SupportGroup(f"g{number:02d}", members, point))
    return groups


def _primary_group(groups: list[_SupportGroup]) -> _SupportGroup:
    return max(
        groups,
        key=lambda group: (
            any(
                shape.source_shape_type != "derived_image_edge_support"
                for shape in group.shapes
            ),
            len(group.shapes),
            sum(len(shape.points) for shape in group.shapes),
            sum(float(shape.circle[2]) for shape in group.shapes),
        ),
    )


def _resize_gradient(gray: np.ndarray, downsample: int) -> np.ndarray:
    if downsample <= 1:
        small = gray.astype(np.float64, copy=False)
    else:
        height, width = gray.shape
        image = Image.fromarray(gray.astype(np.float32))
        small = np.asarray(
            image.resize(
                (max(16, width // downsample), max(16, height // downsample)),
                Image.Resampling.BILINEAR,
            ),
            dtype=np.float64,
        )
    return gradient_magnitude(small)


def _derive_image_registration_model(
    reference: ReferenceModel,
    config: dict[str, Any],
) -> ReferenceModel:
    """Add distributed pixel-edge supports derived only from the new image.

    The two manual shapes retain their measurement meaning.  The synthetic
    support shapes are an internal registration representation of stable,
    spatially distributed high-gradient patches in the same authoritative
    image; they never enter measurement extraction or result geometry.
    """
    downsample = int(config["supports"]["downsample"])
    gradient = _resize_gradient(reference.gray, downsample)
    height, width = gradient.shape
    global_scale = _gradient_normalizer(gradient)
    cluster_distance = float(
        config["supports"]["reference_cluster_distance_px"]
    )
    circular_centers = [
        (float(shape.circle[0]), float(shape.circle[1]))
        for shape in reference.shapes
        if shape.circle is not None
    ]
    supports: list[ShapeModel] = []
    rows, columns = 4, 6
    margin_y = max(2, height // 20)
    margin_x = max(2, width // 20)
    usable_height = max(1, height - 2 * margin_y)
    usable_width = max(1, width - 2 * margin_x)
    for row in range(rows):
        y0 = margin_y + row * usable_height // rows
        y1 = margin_y + (row + 1) * usable_height // rows
        for column in range(columns):
            x0 = margin_x + column * usable_width // columns
            x1 = margin_x + (column + 1) * usable_width // columns
            cell = gradient[y0:y1, x0:x1]
            if cell.size < 24:
                continue
            flat = np.argsort(cell.ravel())[::-1]
            selected: list[tuple[int, int]] = []
            for flat_index in flat:
                local_y, local_x = np.unravel_index(int(flat_index), cell.shape)
                y, x = y0 + int(local_y), x0 + int(local_x)
                if float(gradient[y, x]) / global_scale < float(
                    config["supports"]["min_edge_peak_normalized"]
                ):
                    break
                if any(abs(x - px) <= 2 and abs(y - py) <= 2 for py, px in selected):
                    continue
                selected.append((y, x))
                if len(selected) >= 20:
                    break
            if len(selected) < 12:
                continue
            points = [
                (float(x * downsample), float(y * downsample))
                for y, x in selected
            ]
            center_x = float(np.mean([point[0] for point in points]))
            center_y = float(np.mean([point[1] for point in points]))
            if any(
                math.hypot(center_x - x, center_y - y) <= 1.1 * cluster_distance
                for x, y in circular_centers
            ):
                continue
            supports.append(ShapeModel(
                index=10_000 + len(supports),
                label=f"__image_registration_support_{row}_{column}",
                sanitized=f"__image_registration_support_{row}_{column}",
                kind="arc",
                points=points,
                circle=(center_x, center_y, 1.0),
                source_shape_type="derived_image_edge_support",
            ))
    if len(supports) < int(config["quality"]["min_support_groups"]):
        raise ValueError("authoritative reference image has insufficient registration supports")
    return ReferenceModel(
        annotation=reference.annotation,
        image_path=reference.image_path,
        gray=reference.gray,
        shapes=[*reference.shapes, *supports],
        anchor_indices=list(reference.anchor_indices),
    )


def _ring_kernel(shape: tuple[int, int], radii: list[float]) -> np.ndarray:
    kernel = np.zeros(shape, dtype=np.float64)
    for radius in radii:
        if radius < 2.0:
            continue
        count = max(80, int(round(4.0 * math.pi * radius)))
        angles = np.linspace(0.0, 2.0 * math.pi, count, endpoint=False)
        xs = np.rint(radius * np.cos(angles)).astype(np.int64) % shape[1]
        ys = np.rint(radius * np.sin(angles)).astype(np.int64) % shape[0]
        positions = np.unique(np.column_stack([ys, xs]), axis=0)
        if len(positions):
            weight = 1.0 / (len(positions) * max(1, len(radii)))
            kernel[positions[:, 0], positions[:, 1]] += weight
    return kernel


def _coarse_hypotheses(
    target: np.ndarray,
    primary: _SupportGroup,
    config: dict[str, Any],
) -> list[dict[str, float]]:
    coarse = config["coarse"]
    downsample = int(coarse["downsample"])
    gradient = _resize_gradient(target, downsample)
    cap = float(np.percentile(gradient, 99.5))
    if not math.isfinite(cap) or cap <= 1e-9:
        return []
    gradient = np.clip(gradient, 0.0, cap)
    gradient_fft = np.fft.rfft2(gradient)
    raw: list[dict[str, float]] = []
    scales = np.arange(
        float(coarse["scale_min"]),
        float(coarse["scale_max"]) + 0.5 * float(coarse["scale_step"]),
        float(coarse["scale_step"]),
    )
    reference_radii = [float(shape.circle[2]) for shape in primary.shapes]
    for scale in scales:
        radii_small = [radius * float(scale) / downsample for radius in reference_radii]
        kernel = _ring_kernel(gradient.shape, radii_small)
        correlation = np.fft.irfft2(
            gradient_fft * np.conj(np.fft.rfft2(kernel)), s=gradient.shape
        ).real
        margin = int(math.ceil(max(radii_small))) + 3
        if margin * 2 >= min(correlation.shape):
            continue
        valid = correlation[margin:correlation.shape[0] - margin,
                            margin:correlation.shape[1] - margin]
        peak_count = min(int(coarse["max_peaks_per_scale"]), valid.size)
        if peak_count <= 0:
            continue
        indices = np.argpartition(valid.ravel(), -peak_count)[-peak_count:]
        for flat_index in indices:
            row, column = np.unravel_index(int(flat_index), valid.shape)
            raw.append({
                "score": float(valid[row, column] / cap),
                "scale": float(scale),
                "centerX": float((column + margin) * downsample),
                "centerY": float((row + margin) * downsample),
            })

    selected: list[dict[str, float]] = []
    nms = float(coarse["nonmaximum_distance_px"])
    for item in sorted(raw, key=lambda value: value["score"], reverse=True):
        if any(
            math.hypot(item["centerX"] - previous["centerX"],
                       item["centerY"] - previous["centerY"]) < nms
            for previous in selected
        ):
            continue
        selected.append(item)
        if len(selected) >= int(coarse["max_global_hypotheses"]):
            break
    return selected


def _summed_area(array: np.ndarray) -> np.ndarray:
    return np.pad(array.cumsum(axis=0).cumsum(axis=1), ((1, 0), (1, 0)))


def _window_sums(integral: np.ndarray, height: int, width: int) -> np.ndarray:
    return (
        integral[height:, width:]
        - integral[:-height, width:]
        - integral[height:, :-width]
        + integral[:-height, :-width]
    )


def _image_template_hypotheses(
    reference: ReferenceModel,
    target: np.ndarray,
    primary: _SupportGroup,
    config: dict[str, Any],
) -> list[dict[str, float | str]]:
    """Find coarse poses by matching the new reference's measured-part ROI."""
    coarse = config["coarse"]
    downsample = int(coarse["downsample"])
    reference_gradient = _resize_gradient(reference.gray, downsample)
    target_gradient = _resize_gradient(target, downsample)
    measurement_shapes = [
        shape for shape in reference.shapes
        if shape.source_shape_type != "derived_image_edge_support"
    ]
    points = [point for shape in measurement_shapes for point in shape.points]
    if not points:
        return []
    xs = [point[0] / downsample for point in points]
    ys = [point[1] / downsample for point in points]
    radius = max(
        (float(shape.circle[2]) / downsample for shape in measurement_shapes
         if shape.circle is not None),
        default=20.0,
    )
    margin = max(12, int(math.ceil(0.45 * radius)))
    x0 = max(0, int(math.floor(min(xs))) - margin)
    x1 = min(reference_gradient.shape[1], int(math.ceil(max(xs))) + margin + 1)
    y0 = max(0, int(math.floor(min(ys))) - margin)
    y1 = min(reference_gradient.shape[0], int(math.ceil(max(ys))) + margin + 1)
    template_base = reference_gradient[y0:y1, x0:x1]
    if min(template_base.shape) < 12:
        return []
    target_cap = float(np.percentile(target_gradient, 99.5))
    if not math.isfinite(target_cap) or target_cap <= 1e-9:
        return []
    target_gradient = np.clip(target_gradient, 0.0, target_cap)
    target_integral = _summed_area(target_gradient)
    target_square_integral = _summed_area(target_gradient * target_gradient)
    raw: list[dict[str, float | str]] = []
    scales = np.arange(
        float(coarse["scale_min"]),
        float(coarse["scale_max"]) + 0.5 * float(coarse["scale_step"]),
        float(coarse["scale_step"]),
    )
    for scale in scales:
        template = np.asarray(
            Image.fromarray(template_base.astype(np.float32)).resize(
                (max(8, int(round(template_base.shape[1] * scale))),
                 max(8, int(round(template_base.shape[0] * scale)))),
                Image.Resampling.BILINEAR,
            ),
            dtype=np.float64,
        )
        height, width = template.shape
        if height >= target_gradient.shape[0] or width >= target_gradient.shape[1]:
            continue
        template = template - float(np.mean(template))
        template_norm = float(np.linalg.norm(template))
        if template_norm <= 1e-9:
            continue
        fft_shape = (
            target_gradient.shape[0] + height - 1,
            target_gradient.shape[1] + width - 1,
        )
        correlation = np.fft.irfft2(
            np.fft.rfft2(target_gradient, fft_shape)
            * np.conj(np.fft.rfft2(template, fft_shape)),
            s=fft_shape,
        ).real[:target_gradient.shape[0] - height + 1,
               :target_gradient.shape[1] - width + 1]
        sums = _window_sums(target_integral, height, width)
        squares = _window_sums(target_square_integral, height, width)
        count = float(height * width)
        local_energy = np.maximum(squares - sums * sums / count, 1e-9)
        normalized = correlation / (template_norm * np.sqrt(local_energy))
        peak_count = min(int(coarse["max_peaks_per_scale"]), normalized.size)
        indices = np.argpartition(normalized.ravel(), -peak_count)[-peak_count:]
        for flat_index in indices:
            row, column = np.unravel_index(int(flat_index), normalized.shape)
            center_x = (
                float(column)
                + scale * (primary.reference_point[0] / downsample - x0)
            ) * downsample
            center_y = (
                float(row)
                + scale * (primary.reference_point[1] / downsample - y0)
            ) * downsample
            raw.append({
                "score": float(normalized[row, column]),
                "scale": float(scale),
                "centerX": float(center_x),
                "centerY": float(center_y),
                "hypothesisSource": "authoritative_reference_image_roi",
            })
    selected: list[dict[str, float | str]] = []
    nms = float(coarse["nonmaximum_distance_px"])
    for item in sorted(raw, key=lambda value: float(value["score"]), reverse=True):
        if any(
            math.hypot(
                float(item["centerX"]) - float(previous["centerX"]),
                float(item["centerY"]) - float(previous["centerY"]),
            ) < nms
            and abs(float(item["scale"]) - float(previous["scale"])) < 0.08
            for previous in selected
        ):
            continue
        selected.append(item)
        if len(selected) >= 8:
            break
    return selected


def _initial_transform(
    reference_point: tuple[float, float],
    target_center: tuple[float, float],
    scale: float,
    orientation_deg: float,
) -> SimilarityTransform:
    theta = math.radians(orientation_deg)
    c, s = math.cos(theta), math.sin(theta)
    rx = scale * (c * reference_point[0] - s * reference_point[1])
    ry = scale * (s * reference_point[0] + c * reference_point[1])
    return SimilarityTransform(target_center[0] - rx, target_center[1] - ry,
                               scale, orientation_deg)


def _gradient_normalizer(gradient: np.ndarray) -> float:
    value = float(np.percentile(gradient, 99.0))
    if value <= 1e-9:
        value = float(np.max(gradient))
    return max(value, 1e-9)


def _score_support(
    group: _SupportGroup,
    transform: SimilarityTransform,
    gradient: np.ndarray,
    downsample: int,
    search_radius_px: float,
    search_step_px: float,
    support_config: dict[str, Any],
) -> dict[str, Any]:
    point_sets: list[np.ndarray] = []
    for shape in group.shapes:
        points = np.asarray(shape.points, dtype=np.float64)
        mapped = np.asarray([transform.forward(float(x), float(y)) for x, y in points])
        point_sets.append(mapped / float(downsample))

    radius_small = max(0, int(round(search_radius_px / downsample)))
    step_small = max(1, int(round(search_step_px / downsample)))
    offsets = range(-radius_small, radius_small + 1, step_small)
    scored: list[tuple[float, int, int, float]] = []
    min_visible = float(support_config["min_visible_fraction"])
    for offset_y in offsets:
        for offset_x in offsets:
            shape_scores: list[float] = []
            visible_fractions: list[float] = []
            for points in point_sets:
                xs = np.rint(points[:, 0] + offset_x).astype(np.int64)
                ys = np.rint(points[:, 1] + offset_y).astype(np.int64)
                visible = ((xs >= 0) & (xs < gradient.shape[1])
                           & (ys >= 0) & (ys < gradient.shape[0]))
                fraction = float(visible.mean()) if len(visible) else 0.0
                visible_fractions.append(fraction)
                if fraction < min_visible:
                    shape_scores.append(0.0)
                else:
                    shape_scores.append(float(np.median(gradient[ys[visible], xs[visible]])))
            score = float(np.median(shape_scores)) if shape_scores else 0.0
            scored.append((score, offset_x, offset_y,
                           float(np.median(visible_fractions)) if visible_fractions else 0.0))

    peak, offset_x, offset_y, visibility = max(scored, key=lambda item: item[0])
    score_values = np.asarray([item[0] for item in scored], dtype=np.float64)
    normalizer = _gradient_normalizer(gradient)
    peak_normalized = float(peak / normalizer)
    prominence = float((peak - np.median(score_values)) / normalizer)
    offset_target = (
        float(offset_x * downsample),
        float(offset_y * downsample),
    )
    saturation_limit = search_radius_px * float(support_config["offset_saturation_fraction"])
    boundary = {
        "xLower": offset_target[0] <= -saturation_limit,
        "xUpper": offset_target[0] >= saturation_limit,
        "yLower": offset_target[1] <= -saturation_limit,
        "yUpper": offset_target[1] >= saturation_limit,
        "limitPx": float(saturation_limit),
    }
    saturated = any(boundary[name] for name in ("xLower", "xUpper", "yLower", "yUpper"))
    predicted = transform.forward(*group.reference_point)
    target_point = (predicted[0] + offset_target[0], predicted[1] + offset_target[1])
    valid = (
        visibility >= min_visible
        and peak_normalized >= float(support_config["min_edge_peak_normalized"])
        and prominence >= float(support_config["min_edge_prominence_normalized"])
        and not saturated
    )
    reasons: list[str] = []
    if visibility < min_visible:
        reasons.append("insufficient_visibility")
    if peak_normalized < float(support_config["min_edge_peak_normalized"]):
        reasons.append("edge_peak_below_gate")
    if prominence < float(support_config["min_edge_prominence_normalized"]):
        reasons.append("edge_prominence_below_gate")
    if saturated:
        reasons.append("offset_saturated")
    return {
        "groupId": group.group_id,
        "labels": group.labels,
        "referencePointPx": [float(group.reference_point[0]), float(group.reference_point[1])],
        "targetPointPx": [float(target_point[0]), float(target_point[1])],
        "offsetPx": [offset_target[0], offset_target[1]],
        "edgePeakNormalized": peak_normalized,
        "edgeProminenceNormalized": prominence,
        "visibleFraction": visibility,
        "searchBoundary": boundary,
        "gateDiagnostics": {
            "visibility": {"value": visibility, "minimum": min_visible,
                           "passed": visibility >= min_visible},
            "edgePeak": {"value": peak_normalized,
                         "minimum": float(support_config["min_edge_peak_normalized"]),
                         "passed": peak_normalized >= float(support_config["min_edge_peak_normalized"])},
            "edgeProminence": {"value": prominence,
                               "minimum": float(support_config["min_edge_prominence_normalized"]),
                               "passed": prominence >= float(support_config["min_edge_prominence_normalized"])},
            "searchBoundary": {"passed": not saturated, "hitDimensions": [
                name for name in ("xLower", "xUpper", "yLower", "yUpper") if boundary[name]
            ]},
        },
        "valid": bool(valid),
        "failureReason": None if valid else ",".join(reasons),
    }


def _convex_hull(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    unique = sorted(set((float(x), float(y)) for x, y in points))
    if len(unique) <= 1:
        return unique

    def cross(origin, first, second):
        return ((first[0] - origin[0]) * (second[1] - origin[1])
                - (first[1] - origin[1]) * (second[0] - origin[0]))

    lower: list[tuple[float, float]] = []
    for point in unique:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], point) <= 0:
            lower.pop()
        lower.append(point)
    upper: list[tuple[float, float]] = []
    for point in reversed(unique):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], point) <= 0:
            upper.pop()
        upper.append(point)
    return lower[:-1] + upper[:-1]


def _polygon_area(points: list[tuple[float, float]]) -> float:
    if len(points) < 3:
        return 0.0
    return abs(sum(
        points[index][0] * points[(index + 1) % len(points)][1]
        - points[(index + 1) % len(points)][0] * points[index][1]
        for index in range(len(points))
    )) * 0.5


def _spatial_coverage(
    valid_supports: list[dict[str, Any]], groups: list[_SupportGroup]
) -> float:
    support_points = [tuple(item["referencePointPx"]) for item in valid_supports]
    all_points = [group.reference_point for group in groups]
    numerator = _polygon_area(_convex_hull(support_points))
    denominator = _polygon_area(_convex_hull(all_points))
    return float(numerator / denominator) if denominator > 1e-9 else 0.0


def _angle_difference_degrees(value: float, reference: float) -> float:
    return (value - reference + 180.0) % 360.0 - 180.0


def _fit_supported_pose(
    supports: list[dict[str, Any]],
    quality: dict[str, Any],
) -> tuple[SimilarityTransform | None, list[float], list[dict[str, Any]]]:
    valid = [support for support in supports if support["valid"]]
    if len(valid) < int(quality["min_support_groups"]):
        return None, [], valid
    reference = [tuple(item["referencePointPx"]) for item in valid]
    target = [tuple(item["targetPointPx"]) for item in valid]
    transform, residuals = fit_similarity_transform(reference, target)
    if len(valid) > int(quality["min_support_groups"]):
        gate = float(quality["max_residual_px"])
        kept = [item for item, residual in zip(valid, residuals) if residual <= gate]
        if len(kept) >= int(quality["min_support_groups"]) and len(kept) < len(valid):
            reference = [tuple(item["referencePointPx"]) for item in kept]
            target = [tuple(item["targetPointPx"]) for item in kept]
            transform, residuals = fit_similarity_transform(reference, target)
            valid = kept
    return transform, residuals, valid


def _candidate(
    hypothesis: dict[str, float],
    orientation_deg: int,
    groups: list[_SupportGroup],
    primary: _SupportGroup,
    gradient: np.ndarray,
    config: dict[str, Any],
) -> dict[str, Any]:
    support_config = config["supports"]
    quality = config["quality"]
    downsample = int(support_config["downsample"])
    initial = _initial_transform(
        primary.reference_point,
        (hypothesis["centerX"], hypothesis["centerY"]),
        hypothesis["scale"],
        orientation_deg,
    )
    first_supports = [
        _score_support(
            group, initial, gradient, downsample,
            float(support_config["search_radius_target_px"]),
            float(support_config["search_step_target_px"]), support_config,
        )
        for group in groups
    ]
    transform, _, first_valid = _fit_supported_pose(first_supports, quality)
    failure_reasons: list[str] = []
    if transform is None:
        failure_reasons.append("insufficient_support_groups")
        final_supports = first_supports
        residuals: list[float] = []
    else:
        final_supports = [
            _score_support(
                group, transform, gradient, downsample,
                float(support_config["refine_search_radius_target_px"]),
                max(1.0, float(support_config["search_step_target_px"]) * 0.5),
                support_config,
            )
            for group in groups
        ]
        refined, residuals, final_valid = _fit_supported_pose(final_supports, quality)
        if refined is None:
            failure_reasons.append("insufficient_refined_support_groups")
            transform = None
        else:
            transform = refined
            first_valid = final_valid

    valid_supports = [support for support in final_supports if support["valid"]]
    support_count = len(valid_supports)
    coverage = _spatial_coverage(valid_supports, groups)
    median_residual = float(np.median(residuals)) if residuals else float("inf")
    max_residual = float(max(residuals)) if residuals else float("inf")
    if support_count < int(quality["min_support_groups"]):
        failure_reasons.append("support_count_below_gate")
    if coverage < float(quality["min_spatial_coverage"]):
        failure_reasons.append("spatial_coverage_below_gate")
    if transform is not None:
        if abs(_angle_difference_degrees(transform.theta_deg, orientation_deg)) > float(quality["max_fine_angle_deg"]):
            failure_reasons.append("fine_angle_out_of_range")
        if not (float(quality["min_scale"]) <= transform.scale <= float(quality["max_scale"])):
            failure_reasons.append("scale_out_of_range")
        coarse_fraction = abs(transform.scale / hypothesis["scale"] - 1.0)
        if coarse_fraction > float(quality["max_scale_change_from_coarse_fraction"]):
            failure_reasons.append("scale_change_from_coarse_too_large")
    if median_residual > float(quality["max_median_residual_px"]):
        failure_reasons.append("median_residual_above_gate")
    if max_residual > float(quality["max_residual_px"]):
        failure_reasons.append("max_residual_above_gate")

    score = sum(
        support["edgePeakNormalized"] + 0.5 * support["edgeProminenceNormalized"]
        for support in valid_supports
    )
    if math.isfinite(median_residual):
        score -= median_residual / max(1.0, float(quality["max_median_residual_px"]))
    fine_angle_delta = None if transform is None else abs(
        _angle_difference_degrees(transform.theta_deg, orientation_deg)
    )
    scale_value = None if transform is None else float(transform.scale)
    scale_change = None if transform is None else abs(
        transform.scale / hypothesis["scale"] - 1.0
    )
    gate_diagnostics = {
        "supportCount": {"value": support_count,
                         "minimum": int(quality["min_support_groups"]),
                         "passed": support_count >= int(quality["min_support_groups"])},
        "spatialCoverage": {"value": coverage,
                            "minimum": float(quality["min_spatial_coverage"]),
                            "passed": coverage >= float(quality["min_spatial_coverage"])},
        "medianResidualPx": {"value": None if not math.isfinite(median_residual) else median_residual,
                             "maximum": float(quality["max_median_residual_px"]),
                             "passed": median_residual <= float(quality["max_median_residual_px"])},
        "maxResidualPx": {"value": None if not math.isfinite(max_residual) else max_residual,
                          "maximum": float(quality["max_residual_px"]),
                          "passed": max_residual <= float(quality["max_residual_px"])},
        "fineAngleDeltaDeg": {"value": fine_angle_delta,
                              "maximum": float(quality["max_fine_angle_deg"]),
                              "passed": fine_angle_delta is not None and fine_angle_delta <= float(quality["max_fine_angle_deg"])},
        "scale": {"value": scale_value, "minimum": float(quality["min_scale"]),
                  "maximum": float(quality["max_scale"]),
                  "passed": scale_value is not None and float(quality["min_scale"]) <= scale_value <= float(quality["max_scale"])},
        "scaleChangeFromCoarse": {"value": scale_change,
                                  "maximum": float(quality["max_scale_change_from_coarse_fraction"]),
                                  "passed": scale_change is not None and scale_change <= float(quality["max_scale_change_from_coarse_fraction"])},
    }
    return {
        "orientationDeg": int(orientation_deg),
        "coarse": dict(hypothesis),
        "transform": None if transform is None else transform.as_dict(),
        "score": float(score),
        "supportCount": support_count,
        "spatialCoverage": coverage,
        "medianResidualPx": None if not math.isfinite(median_residual) else median_residual,
        "maxResidualPx": None if not math.isfinite(max_residual) else max_residual,
        "supports": final_supports,
        "gateDiagnostics": gate_diagnostics,
        "valid": not failure_reasons and transform is not None,
        "failureReasons": sorted(set(failure_reasons)),
    }


def _roundtrip_error(transform: SimilarityTransform, groups: list[_SupportGroup]) -> float:
    return max(
        math.dist(point, transform.inverse(*transform.forward(*point)))
        for point in (group.reference_point for group in groups)
    )


def _distinct_pose_candidates(
    candidates: list[dict[str, Any]],
    reference_point: tuple[float, float],
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    """Collapse coarse seeds that refined to the same physical pose."""
    distinct: list[dict[str, Any]] = []
    position_tolerance = 0.25 * float(config["coarse"]["nonmaximum_distance_px"])
    for candidate in candidates:
        value = candidate.get("transform")
        if not isinstance(value, dict):
            continue
        transform = SimilarityTransform(
            float(value["dx"]), float(value["dy"]),
            float(value["scale"]), float(value["thetaDeg"]),
        )
        center = transform.forward(*reference_point)
        duplicate = False
        for previous in distinct:
            previous_value = previous["transform"]
            previous_transform = SimilarityTransform(
                float(previous_value["dx"]), float(previous_value["dy"]),
                float(previous_value["scale"]), float(previous_value["thetaDeg"]),
            )
            previous_center = previous_transform.forward(*reference_point)
            if (
                math.dist(center, previous_center) <= position_tolerance
                and abs(transform.scale / previous_transform.scale - 1.0) <= 0.05
                and abs(_angle_difference_degrees(
                    transform.theta_deg, previous_transform.theta_deg
                )) <= 3.0
            ):
                duplicate = True
                break
        if not duplicate:
            distinct.append(candidate)
    return distinct


def _registration_coordinate_fields(
    reference: ReferenceModel,
    target_gray: np.ndarray,
    transform: SimilarityTransform | None,
) -> dict[str, Any]:
    return {
        "referenceImageSize": [int(reference.gray.shape[1]), int(reference.gray.shape[0])],
        "targetImageSize": [int(target_gray.shape[1]), int(target_gray.shape[0])],
        "transformDirection": "reference_px_to_target_px",
        "inverseTransformDirection": "target_px_to_reference_px",
        "inverseTransform": None if transform is None else transform.inverse_as_dict(),
    }


def _registration_image_consistency(
    reference_gray: np.ndarray,
    target_gray: np.ndarray,
    transform: SimilarityTransform,
    downsample: int = 8,
) -> dict[str, float | int]:
    """Compare a pose against distributed pixels from the sole reference image."""
    ref_image = Image.fromarray(reference_gray.astype(np.float32)).resize(
        (max(16, reference_gray.shape[1] // downsample),
         max(16, reference_gray.shape[0] // downsample)),
        Image.Resampling.BILINEAR,
    )
    target_image = Image.fromarray(target_gray.astype(np.float32)).resize(
        (max(16, target_gray.shape[1] // downsample),
         max(16, target_gray.shape[0] // downsample)),
        Image.Resampling.BILINEAR,
    )
    reference = np.asarray(ref_image, dtype=np.float64)
    target = np.asarray(target_image, dtype=np.float64)
    ref_gy, ref_gx = np.gradient(reference)
    target_gy, target_gx = np.gradient(target)
    ref_magnitude = np.hypot(ref_gx, ref_gy)
    threshold = float(np.percentile(ref_magnitude, 70.0))
    ys, xs = np.nonzero(ref_magnitude >= threshold)
    if len(xs) > 6000:
        indices = np.linspace(0, len(xs) - 1, 6000, dtype=np.int64)
        xs, ys = xs[indices], ys[indices]
    reference_x = xs.astype(np.float64) * downsample
    reference_y = ys.astype(np.float64) * downsample
    theta = transform.theta_rad
    c, s = math.cos(theta), math.sin(theta)
    target_x = (
        transform.dx + transform.scale * (c * reference_x - s * reference_y)
    ) / downsample
    target_y = (
        transform.dy + transform.scale * (s * reference_x + c * reference_y)
    ) / downsample
    visible = (
        (target_x >= 1.0) & (target_x < target.shape[1] - 2.0)
        & (target_y >= 1.0) & (target_y < target.shape[0] - 2.0)
    )
    if int(visible.sum()) < 200:
        return {"score": -1.0, "intensityCorrelation": -1.0,
                "gradientDirectionSupport": 0.0, "visiblePoints": int(visible.sum())}
    xs = xs[visible]
    ys = ys[visible]
    target_x = target_x[visible]
    target_y = target_y[visible]
    ref_values = reference[ys, xs]
    target_values = bilinear_sample(target, target_x, target_y)
    finite = np.isfinite(target_values)
    ref_values = ref_values[finite]
    target_values = target_values[finite]
    ref_values = ref_values - float(np.mean(ref_values))
    target_values = target_values - float(np.mean(target_values))
    denominator = float(np.linalg.norm(ref_values) * np.linalg.norm(target_values))
    if denominator <= 1e-9:
        return {"score": -1.0, "intensityCorrelation": -1.0,
                "gradientDirectionSupport": 0.0, "visiblePoints": int(len(ref_values))}
    intensity_correlation = float(np.dot(ref_values, target_values) / denominator)
    ref_gx_values = ref_gx[ys, xs][finite]
    ref_gy_values = ref_gy[ys, xs][finite]
    target_gx_values = bilinear_sample(target_gx, target_x[finite], target_y[finite])
    target_gy_values = bilinear_sample(target_gy, target_x[finite], target_y[finite])
    rotated_x = c * ref_gx_values - s * ref_gy_values
    rotated_y = s * ref_gx_values + c * ref_gy_values
    direction_denominator = (
        np.hypot(rotated_x, rotated_y)
        * np.hypot(target_gx_values, target_gy_values)
    )
    usable = direction_denominator > 1e-9
    if usable.any():
        direction_cosine = (
            rotated_x[usable] * target_gx_values[usable]
            + rotated_y[usable] * target_gy_values[usable]
        ) / direction_denominator[usable]
        gradient_support = float(np.mean(np.clip(direction_cosine, -1.0, 1.0)))
    else:
        gradient_support = 0.0
    score = 0.5 * intensity_correlation + 0.5 * gradient_support
    return {
        "score": float(score),
        "intensityCorrelation": float(intensity_correlation),
        "gradientDirectionSupport": float(gradient_support),
        "visiblePoints": int(len(ref_values)),
    }


def _add_image_consistency_scores(
    candidates: list[dict[str, Any]],
    reference_gray: np.ndarray,
    target_gray: np.ndarray,
) -> None:
    for candidate in candidates:
        value = candidate.get("transform")
        if not isinstance(value, dict):
            diagnostic = {"score": -1.0, "intensityCorrelation": -1.0,
                          "gradientDirectionSupport": 0.0, "visiblePoints": 0}
        else:
            diagnostic = _registration_image_consistency(
                reference_gray,
                target_gray,
                SimilarityTransform(
                    float(value["dx"]), float(value["dy"]),
                    float(value["scale"]), float(value["thetaDeg"]),
                ),
            )
        candidate["imageConsistency"] = diagnostic
        candidate["rawSupportScore"] = candidate["score"]
        candidate["score"] = float(candidate["score"] + 3.0 * diagnostic["score"])


def _unscored_orientation_candidates(config: dict[str, Any]) -> list[dict[str, Any]]:
    return [{
        "orientationDeg": int(orientation),
        "coarse": None,
        "transform": None,
        "score": None,
        "supportCount": 0,
        "spatialCoverage": 0.0,
        "medianResidualPx": None,
        "maxResidualPx": None,
        "supports": [],
        "valid": False,
        "failureReasons": ["no_global_hypothesis"],
    } for orientation in config["orientations_deg"]]


def _identity_self_registration(
    reference: ReferenceModel,
    target_gray: np.ndarray,
) -> dict[str, Any]:
    transform = SimilarityTransform(0.0, 0.0, 1.0, 0.0)
    selected = {
        "orientationDeg": 0,
        "coarse": {"score": 1.0, "scale": 1.0, "centerX": None, "centerY": None},
        "transform": transform.as_dict(),
        "score": 1.0,
        "supportCount": None,
        "spatialCoverage": 1.0,
        "medianResidualPx": 0.0,
        "maxResidualPx": 0.0,
        "supports": [],
        "gateDiagnostics": {"identitySelfCheck": {"passed": True}},
        "valid": True,
        "failureReasons": [],
        "registrationPass": "authoritative_reference_identity",
    }
    return {
        "registrationValid": True,
        "failureReason": None,
        "primaryFailureReason": None,
        "registrationRecoveryPass": None,
        "candidates": [selected],
        "selected": selected,
        "transform": transform.as_dict(),
        "candidateScoreMargin": None,
        "roundtripErrorPx": 0.0,
        **_registration_coordinate_fields(reference, target_gray, transform),
    }


def register_current_capture(
    reference: ReferenceModel,
    target_gray: np.ndarray,
    config: dict[str, Any],
) -> dict[str, Any]:
    """Register one target using only authoritative-reference image evidence."""
    groups = _cluster_supports(
        reference, float(config["supports"]["reference_cluster_distance_px"])
    )
    primary = _primary_group(groups)
    ring_hypotheses = _coarse_hypotheses(target_gray, primary, config)
    for hypothesis in ring_hypotheses:
        hypothesis["hypothesisSource"] = "annotated_circle_ring"
    image_hypotheses = _image_template_hypotheses(
        reference, target_gray, primary, config
    )
    hypotheses = [*image_hypotheses, *ring_hypotheses]
    if not hypotheses:
        return {
            "registrationValid": False,
            "failureReason": "no_global_hypothesis",
            "primaryFailureReason": "no_global_hypothesis",
            "registrationRecoveryPass": None,
            "candidates": _unscored_orientation_candidates(config),
            "selected": None, "transform": None,
            "candidateScoreMargin": None,
            "roundtripErrorPx": None,
            **_registration_coordinate_fields(reference, target_gray, None),
        }
    support_downsample = int(config["supports"]["downsample"])
    gradient = _resize_gradient(target_gray, support_downsample)
    candidates = [
        _candidate(hypothesis, int(orientation), groups, primary, gradient, config)
        for hypothesis in hypotheses
        for orientation in config["orientations_deg"]
    ]
    _add_image_consistency_scores(candidates, reference.gray, target_gray)
    for candidate in candidates:
        candidate["registrationPass"] = "primary"
    candidates.sort(key=lambda item: item["score"], reverse=True)
    valid = [item for item in candidates if item["valid"]]
    if not valid:
        recovery = config.get("registration_recovery") or {}
        if bool(recovery.get("enabled", False)):
            recovery_config = {
                **config,
                "supports": {
                    **config["supports"],
                    "refine_search_radius_target_px": float(
                        recovery["refine_search_radius_target_px"]
                    ),
                },
            }
            recovery_candidates = [
                _candidate(
                    hypothesis, int(orientation), groups, primary, gradient,
                    recovery_config,
                )
                for hypothesis in hypotheses
                for orientation in config["orientations_deg"]
            ]
            _add_image_consistency_scores(
                recovery_candidates, reference.gray, target_gray
            )
            for candidate in recovery_candidates:
                candidate["registrationPass"] = "recovery"
            candidates.extend(recovery_candidates)
            candidates.sort(key=lambda item: item["score"], reverse=True)
            valid = sorted(
                (item for item in recovery_candidates if item["valid"]),
                key=lambda item: item["score"], reverse=True,
            )
        if not valid:
            return {
                "registrationValid": False,
                "failureReason": "no_valid_candidate",
                "primaryFailureReason": "no_valid_candidate",
                "registrationRecoveryPass": (
                    "stable_multi_support" if bool(recovery.get("enabled", False)) else None
                ),
                "candidates": candidates, "selected": None, "transform": None,
                "candidateScoreMargin": None,
                "roundtripErrorPx": None,
                **_registration_coordinate_fields(reference, target_gray, None),
            }
        registration_recovery_pass = "stable_multi_support"
        primary_failure_reason = "no_valid_candidate"
    else:
        registration_recovery_pass = None
        primary_failure_reason = None
    distinct_valid = _distinct_pose_candidates(valid, primary.reference_point, config)
    best = distinct_valid[0]
    margin = (
        None if len(distinct_valid) == 1
        else float(best["score"] - distinct_valid[1]["score"])
    )
    if margin is not None and margin < float(config["quality"]["min_candidate_score_margin"]):
        return {
            "registrationValid": False,
            "failureReason": "ambiguous_candidates",
            "primaryFailureReason": primary_failure_reason,
            "registrationRecoveryPass": registration_recovery_pass,
            "candidates": candidates, "selected": best, "transform": None,
            "candidateScoreMargin": margin,
            "roundtripErrorPx": None,
            **_registration_coordinate_fields(reference, target_gray, None),
        }
    transform = SimilarityTransform(
        best["transform"]["dx"], best["transform"]["dy"],
        best["transform"]["scale"], best["transform"]["thetaDeg"],
    )
    roundtrip = _roundtrip_error(transform, groups)
    if roundtrip > float(config["quality"]["max_roundtrip_error_px"]):
        return {
            "registrationValid": False,
            "failureReason": "roundtrip_error_above_gate",
            "primaryFailureReason": primary_failure_reason,
            "registrationRecoveryPass": registration_recovery_pass,
            "candidates": candidates, "selected": best, "transform": None,
            "candidateScoreMargin": margin,
            "roundtripErrorPx": roundtrip,
            **_registration_coordinate_fields(reference, target_gray, None),
        }
    return {
        "registrationValid": True,
        "failureReason": None,
        "primaryFailureReason": primary_failure_reason,
        "registrationRecoveryPass": registration_recovery_pass,
        "candidates": candidates,
        "selected": best,
        "transform": transform.as_dict(),
        "candidateScoreMargin": margin,
        "roundtripErrorPx": roundtrip,
        **_registration_coordinate_fields(reference, target_gray, transform),
    }


def _finite_values(mapping: dict[str, Any], keys: list[str]) -> bool:
    try:
        return all(math.isfinite(float(mapping[key])) for key in keys)
    except (KeyError, TypeError, ValueError):
        return False


def _quality_subset(measurements: dict[str, Any], prefix: str) -> dict[str, Any]:
    quality = {
        key: value for key, value in measurements.items()
        if key.startswith(prefix + ".quality.")
    }
    # Preserve legacy fully-qualified diagnostics while exposing the new
    # delivery gates under their exact contract names for simple consumers.
    for name in (
        "candidate_recovery_pass",
        "candidate_main_lower_bound_saturated",
        "candidate_main_radius_scale_ratio",
        "candidate_radius_scale_ratio",
        "candidate_fallback_pass",
        "candidate_fallback_failure",
    ):
        qualified = f"{prefix}.quality.{name}"
        if qualified in measurements:
            quality[name] = measurements[qualified]
    return quality


def _point_sequence_available(value: Any) -> bool:
    return (
        isinstance(value, list)
        and len(value) >= 2
        and all(
            isinstance(point, list)
            and len(point) == 2
            and all(isinstance(axis, (int, float)) and math.isfinite(float(axis)) for axis in point)
            for point in value
        )
    )


def _d7_evidence_audit(
    measurement_valid: bool,
    boundaries: list[dict[str, Any]],
) -> tuple[bool, str, str | None]:
    if not measurement_valid:
        return False, "not_applicable", "measurement_invalid"
    supported_sides = {
        str(boundary.get("side"))
        for boundary in boundaries
        if isinstance(boundary, dict)
        and boundary.get("side") in {"A", "B"}
        and _point_sequence_available(boundary.get("rawPointsPx"))
        and _point_sequence_available(boundary.get("segmentPointsPx"))
    }
    if supported_sides == {"A", "B"}:
        return True, "complete", None
    if supported_sides:
        return False, "partial", "only_one_boundary_evidence_available"
    return False, "unavailable", "boundary_evidence_unavailable"


def _phi_measurement_arc_segments(
    segments: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    # The reference LabelMe annotation calibrates one physical visible arc.
    # A mirrored/opposite arc may remain in quality diagnostics, but it is not
    # a second measurement target and must not be delivered as such.
    return [
        segment for segment in segments
        if isinstance(segment, dict)
        and segment.get("side") == "reference_left"
        and _point_sequence_available(segment.get("pointsPx"))
    ]


def _phi_evidence_audit(
    measurement_valid: bool,
    measurement_segments: list[dict[str, Any]],
) -> tuple[bool, str, str | None]:
    if not measurement_valid:
        return False, "not_applicable", "measurement_invalid"
    if measurement_segments:
        return True, "complete", None
    return False, "unavailable", "calibrated_arc_evidence_unavailable"


def build_feature_outputs(
    measurements: dict[str, Any],
    transform: SimilarityTransform,
    phi_support_angles: Iterable[float],
    phi_source_detector: str = "hole2-v6",
    d7_source_detector: str = "hole2-v6-dual-boundary",
) -> tuple[dict[str, Any], dict[str, Any]]:
    compatible_keys = [
        "d7_x1", "d7_y1", "d7_x2", "d7_y2", "d7_length",
        "Phi12_2_cx", "Phi12_2_cy", "Phi12_2_r", "Phi12_2_diameter_px",
    ]
    compatible = {key: measurements.get(key, float("nan")) for key in compatible_keys}

    d7_boundary_evidence = measurements.get(
        "d7.quality.candidate_boundary_evidence_target_px"
    )
    if not isinstance(d7_boundary_evidence, list):
        d7_boundary_evidence = []
    d7_legacy_review_evidence = measurements.get(
        "d7.quality.candidate_legacy_boundary_review_target_px"
    )
    if not isinstance(d7_legacy_review_evidence, list):
        d7_legacy_review_evidence = []
    phi_arc_evidence = measurements.get(
        "Phi12_2.quality.candidate_evidence_arc_segments_target_px"
    )
    if not isinstance(phi_arc_evidence, list):
        phi_arc_evidence = []
    phi_measurement_arc_evidence = _phi_measurement_arc_segments(phi_arc_evidence)

    d7_keys = ["d7_x1", "d7_y1", "d7_x2", "d7_y2", "d7_length"]
    if _finite_values(measurements, d7_keys):
        reference_points = [
            [float(measurements["d7_x1"]), float(measurements["d7_y1"])],
            [float(measurements["d7_x2"]), float(measurements["d7_y2"])],
        ]
        target_points = [list(transform.forward(*point)) for point in reference_points]
        d7_reference = {"coordinateSystem": "authoritative_reference_px", "pointsPx": reference_points,
                        "lengthPx": float(measurements["d7_length"])}
        d7_target = {"coordinateSystem": "target_px", "pointsPx": target_points,
                     "lengthPx": float(math.dist(target_points[0], target_points[1]))}
        d7_target["rawEdgeEvidence"] = {
            "semantics": "neck_outer_contour_edges",
            "evidenceAvailable": bool(d7_boundary_evidence),
            "boundaries": [
                {
                    "side": boundary.get("side"),
                    "pointsPx": boundary.get("rawPointsPx", []),
                    "transitionPairsPx": boundary.get("transitionPairsPx", []),
                    "supportPointsPx": boundary.get("supportPointsPx", []),
                    "supportTransitionPairsPx": boundary.get(
                        "supportTransitionPairsPx", []
                    ),
                    "supportEvidenceMode": boundary.get("supportEvidenceMode"),
                }
                for boundary in d7_boundary_evidence
                if isinstance(boundary, dict)
            ],
            "legacyReviewBoundaries": [
                {
                    "side": boundary.get("side"),
                    "semantics": boundary.get("semantics"),
                    "rawPointsPx": boundary.get("rawPointsPx", []),
                    "inlierPointsPx": boundary.get("inlierPointsPx", []),
                    "reviewOnly": True,
                    "equivalentToFormalBoundary": False,
                }
                for boundary in d7_legacy_review_evidence
                if isinstance(boundary, dict)
            ],
        }
        d7_target["fittedGeometry"] = {
            "type": "parallel_lines",
            "isDetectedContour": False,
            "boundaries": [
                {
                    "side": boundary.get("side"),
                    "lineEquation": boundary.get("lineEquation"),
                    "segmentPointsPx": boundary.get("segmentPointsPx", []),
                }
                for boundary in d7_boundary_evidence
                if isinstance(boundary, dict)
            ],
            "legacyReviewBoundaries": [
                {
                    "side": boundary.get("side"),
                    "semantics": boundary.get("semantics"),
                    "lineEquation": boundary.get("lineEquation"),
                    "segmentPointsPx": boundary.get("segmentPointsPx", []),
                    "reviewOnly": True,
                    "equivalentToFormalBoundary": False,
                }
                for boundary in d7_legacy_review_evidence
                if isinstance(boundary, dict)
            ],
        }
        d7_target["measurementAnnotation"] = {
            "type": "perpendicular_distance",
            "pointsPx": target_points,
            "valuePx": d7_target["lengthPx"],
        }
        d7_valid, d7_reason = True, None
    else:
        d7_reference = d7_target = None
        d7_valid = False
        d7_reason = str(
            measurements.get("d7.quality.candidate_failure")
            or measurements.get("d7.quality.upstream", "detector_invalid")
        )

    phi_keys = ["Phi12_2_cx", "Phi12_2_cy", "Phi12_2_r", "Phi12_2_diameter_px"]
    if _finite_values(measurements, phi_keys):
        cx = float(measurements["Phi12_2_cx"])
        cy = float(measurements["Phi12_2_cy"])
        radius = float(measurements["Phi12_2_r"])
        target_center = transform.forward(cx, cy)
        support_reference = [
            [cx + radius * math.cos(float(angle)), cy + radius * math.sin(float(angle))]
            for angle in phi_support_angles
        ]
        support_target = [list(transform.forward(*point)) for point in support_reference]
        phi_reference = {
            "coordinateSystem": "authoritative_reference_px", "centerPx": [cx, cy],
            "radiusPx": radius, "diameterPx": 2.0 * radius,
            "supportPointsPx": support_reference,
        }
        phi_target = {
            "coordinateSystem": "target_px", "centerPx": list(target_center),
            "radiusPx": transform.scale * radius,
            "diameterPx": 2.0 * transform.scale * radius,
            "supportPointsPx": support_target,
        }
        phi_target["rawEdgeEvidence"] = {
            "semantics": "outer_contour_calibrated_visible_arc",
            "evidenceAvailable": bool(phi_measurement_arc_evidence),
            "arcSegments": [
                {
                    "side": segment.get("side"),
                    "pointsPx": segment.get("pointsPx", []),
                }
                for segment in phi_measurement_arc_evidence
                if isinstance(segment, dict)
            ],
        }
        phi_target["fittedGeometry"] = {
            "type": "circle_model",
            "centerPx": list(target_center),
            "radiusPx": transform.scale * radius,
            "isDetectedContour": False,
        }
        phi_target["measurementAnnotation"] = {
            "type": "diameter",
            "valuePx": phi_target["diameterPx"],
        }
        phi_valid, phi_reason = True, None
    else:
        phi_reference = phi_target = None
        phi_valid = False
        phi_reason = str(measurements.get("Phi12_2.quality.candidate_failure", "detector_invalid"))

    d7_quality = _quality_subset(measurements, "d7")
    phi_quality = _quality_subset(measurements, "Phi12_2")
    d7_evidence_complete, d7_audit_status, d7_audit_reason = _d7_evidence_audit(
        d7_valid, d7_boundary_evidence
    )
    phi_evidence_complete, phi_audit_status, phi_audit_reason = _phi_evidence_audit(
        phi_valid, phi_measurement_arc_evidence
    )
    d7_recovery_pass = (
        d7_quality.get("candidate_fallback_pass")
        or d7_quality.get("candidate_recovery_pass")
    )
    phi_recovery_pass = phi_quality.get("candidate_recovery_pass")
    features = {
        "7": {
            "featureCode": "HOLE2-DIM-7", "measurementValid": d7_valid,
            "evidenceComplete": d7_evidence_complete,
            "evidenceAuditStatus": d7_audit_status,
            "evidenceAuditReason": d7_audit_reason,
            "qualityStatus": "valid" if d7_valid else "invalid",
            "failureReason": d7_reason, "sourceDetector": d7_source_detector,
            "recoveryPass": d7_recovery_pass,
            "reference": d7_reference, "target": d7_target,
            "quality": d7_quality,
        },
        "Phi12.2": {
            "featureCode": "HOLE2-DIA-12_2", "measurementValid": phi_valid,
            "evidenceComplete": phi_evidence_complete,
            "evidenceAuditStatus": phi_audit_status,
            "evidenceAuditReason": phi_audit_reason,
            "qualityStatus": "valid" if phi_valid else "invalid",
            "failureReason": phi_reason, "sourceDetector": phi_source_detector,
            "recoveryPass": phi_recovery_pass,
            "reference": phi_reference, "target": phi_target,
            "quality": phi_quality,
        },
    }
    return features, compatible


def _invalid_features(reason: str) -> dict[str, Any]:
    return {
        "7": {
            "featureCode": "HOLE2-DIM-7", "measurementValid": False,
            "evidenceComplete": False, "evidenceAuditStatus": "not_applicable",
            "evidenceAuditReason": "measurement_invalid",
            "qualityStatus": "invalid",
            "failureReason": reason, "sourceDetector": "hole2-v6-dual-boundary",
            "recoveryPass": None,
            "reference": None, "target": None, "quality": {},
        },
        "Phi12.2": {
            "featureCode": "HOLE2-DIA-12_2", "measurementValid": False,
            "evidenceComplete": False, "evidenceAuditStatus": "not_applicable",
            "evidenceAuditReason": "measurement_invalid",
            "qualityStatus": "invalid",
            "failureReason": reason, "sourceDetector": "hole2-v6-current-capture-candidate",
            "recoveryPass": None,
            "reference": None, "target": None, "quality": {},
        },
    }


def evaluate_geometry_consistency(
    features: dict[str, Any],
    reference: ReferenceModel,
    config: dict[str, Any],
    registration: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Diagnose ratio outliers and reject only with independent risk evidence."""
    d7_shape = next((shape for shape in reference.shapes if shape.sanitized == "d7"), None)
    phi_shape = next((shape for shape in reference.shapes if shape.sanitized == "Phi12_2"), None)
    if (
        d7_shape is None or d7_shape.line_p1 is None or d7_shape.line_p2 is None
        or phi_shape is None or phi_shape.circle is None
    ):
        return {
            "evaluated": False, "outlier": False, "rejected": False,
            "failureReason": "reference_geometry_missing",
            "outlierReason": None,
            "ratioSource": "authoritative_manual_reference_geometry",
            "decision": "not_evaluated",
            "corroboratingEvidence": [],
            "hardRejectionPolicy": "ratio_outlier_requires_independent_risk_evidence",
            "outputAdjustmentApplied": False,
        }
    reference_ratio = math.dist(d7_shape.line_p1, d7_shape.line_p2) / (
        2.0 * float(phi_shape.circle[2])
    )
    gate = float(config["geometry_consistency"]["max_reference_ratio_absolute_deviation"])
    report: dict[str, Any] = {
        "evaluated": False,
        "outlier": False,
        "rejected": False,
        "failureReason": None,
        "outlierReason": None,
        "ratioSource": "authoritative_manual_reference_geometry",
        "referenceRatio": float(reference_ratio),
        "targetRatio": None,
        "absoluteDeviation": None,
        "maximumAbsoluteDeviation": gate,
        "decision": "not_evaluated",
        "corroboratingEvidence": [],
        "hardRejectionPolicy": "ratio_outlier_requires_independent_risk_evidence",
        "outputAdjustmentApplied": False,
    }
    d7 = features["7"]
    phi = features["Phi12.2"]
    if not d7["measurementValid"] or not phi["measurementValid"]:
        report["failureReason"] = "both_features_not_valid"
        return report
    target_ratio = float(d7["target"]["lengthPx"]) / float(phi["target"]["diameterPx"])
    deviation = abs(target_ratio - reference_ratio)
    outlier = deviation > gate
    corroborating_evidence: list[str] = []
    registration_recovery = None if registration is None else registration.get(
        "registrationRecoveryPass"
    )
    if registration_recovery:
        corroborating_evidence.append(
            "registration_recovery:" + str(registration_recovery)
        )
    if (
        phi.get("recoveryPass") == "legacy_magnitude_quality_fallback"
        or phi.get("sourceDetector")
        == "hole2-v6-current-capture-legacy-magnitude-quality-fallback"
    ):
        corroborating_evidence.append("phi_legacy_magnitude_quality_fallback")
    if d7.get("sourceDetector") == "hole2-v6-original-quality-fallback":
        corroborating_evidence.append("d7_v6_original_quality_fallback")
    rejected = outlier and bool(corroborating_evidence)
    if rejected:
        decision = "rejected_with_corroborating_evidence"
        failure_reason = "geometry_ratio_inconsistent"
        outlier_reason = "geometry_ratio_outlier"
    elif outlier:
        decision = "diagnostic_only_unconfirmed"
        failure_reason = None
        outlier_reason = "geometry_ratio_outlier_unconfirmed"
    else:
        decision = "consistent"
        failure_reason = None
        outlier_reason = None
    report.update({
        "evaluated": True,
        "outlier": outlier,
        "rejected": rejected,
        "failureReason": failure_reason,
        "outlierReason": outlier_reason,
        "targetRatio": target_ratio,
        "absoluteDeviation": deviation,
        "decision": decision,
        "corroboratingEvidence": corroborating_evidence,
    })
    for feature in (d7, phi):
        feature["quality"]["geometryConsistency"] = dict(report)
    if rejected:
        # Preserve source detector, recovery audit and legacy/reference business
        # columns, but never expose suspicious geometry as a valid new result.
        for feature in (d7, phi):
            feature["measurementValid"] = False
            feature["qualityStatus"] = "invalid"
            feature["failureReason"] = "geometry_ratio_inconsistent"
            feature["reference"] = None
            feature["target"] = None
    return report


def _phi_radius_search_pass(
    gradient: np.ndarray,
    normalizer: float,
    predicted_center: tuple[float, float],
    predicted_radius: float,
    cosines: np.ndarray,
    sines: np.ndarray,
    phi_config: dict[str, Any],
    min_radius_scale_ratio: float,
) -> dict[str, Any] | None:
    """Run one bounded radius pass; refinement cannot escape its bounds."""
    search_radius = float(phi_config["search_radius_px"])
    center_step = float(phi_config["center_search_step_px"])
    radius_step = float(phi_config["radius_search_step_px"])
    refine_step = float(phi_config["refine_step_px"])
    radius_min = predicted_radius * min_radius_scale_ratio
    radius_max = predicted_radius * float(phi_config["max_radius_scale_ratio"])
    scored: list[tuple[float, float, float, float]] = []
    for offset_y in np.arange(-search_radius, search_radius + 0.5 * center_step, center_step):
        for offset_x in np.arange(-search_radius, search_radius + 0.5 * center_step, center_step):
            candidate_cx = predicted_center[0] + float(offset_x)
            candidate_cy = predicted_center[1] + float(offset_y)
            for candidate_radius in np.arange(radius_min, radius_max + 0.5 * radius_step, radius_step):
                values = bilinear_sample(
                    gradient,
                    candidate_cx + candidate_radius * cosines,
                    candidate_cy + candidate_radius * sines,
                )
                visible = np.isfinite(values)
                score = float(np.median(values[visible])) if float(visible.mean()) >= 0.80 else 0.0
                scored.append((score, candidate_cx, candidate_cy, float(candidate_radius)))
    if not scored:
        return None
    coarse_best = max(scored, key=lambda item: item[0])
    refined: list[tuple[float, float, float, float]] = []
    refine_radius_min = max(radius_min, coarse_best[3] - radius_step)
    refine_radius_max = min(radius_max, coarse_best[3] + radius_step)
    for candidate_cy in np.arange(
        coarse_best[2] - center_step, coarse_best[2] + center_step + 0.5 * refine_step, refine_step
    ):
        for candidate_cx in np.arange(
            coarse_best[1] - center_step, coarse_best[1] + center_step + 0.5 * refine_step, refine_step
        ):
            for candidate_radius in np.arange(
                refine_radius_min, refine_radius_max + 0.5 * refine_step, refine_step
            ):
                values = bilinear_sample(
                    gradient,
                    candidate_cx + candidate_radius * cosines,
                    candidate_cy + candidate_radius * sines,
                )
                visible = np.isfinite(values)
                score = float(np.median(values[visible])) if float(visible.mean()) >= 0.80 else 0.0
                refined.append((score, float(candidate_cx), float(candidate_cy), float(candidate_radius)))
    if not refined:
        return None
    peak, target_cx, target_cy, target_radius = max(refined, key=lambda item: item[0])
    center_offset_x = float(target_cx - predicted_center[0])
    center_offset_y = float(target_cy - predicted_center[1])
    center_offset = math.hypot(center_offset_x, center_offset_y)
    bound_tolerance = 0.5 * refine_step + 1e-9
    center_limit = search_radius * float(phi_config["boundary_saturation_fraction"])
    center_boundary = {
        "xLower": center_offset_x <= -center_limit,
        "xUpper": center_offset_x >= center_limit,
        "yLower": center_offset_y <= -center_limit,
        "yUpper": center_offset_y >= center_limit,
        "limitPx": center_limit,
    }
    return {
        "peak": float(peak),
        "target_cx": target_cx,
        "target_cy": target_cy,
        "target_radius": target_radius,
        "radius_scale_ratio": float(target_radius / predicted_radius),
        "center_offset": center_offset,
        "center_offset_x": center_offset_x,
        "center_offset_y": center_offset_y,
        "center_boundary": center_boundary,
        "radius_lower_bound": float(radius_min),
        "radius_upper_bound": float(radius_max),
        "prominence": float((peak - np.median([item[0] for item in scored])) / normalizer),
        "edge_peak": float(peak / normalizer),
        "lower_radius_saturated": target_radius <= radius_min + bound_tolerance,
        "upper_radius_saturated": target_radius >= radius_max - bound_tolerance,
        "center_saturated": any(center_boundary[name] for name in ("xLower", "xUpper", "yLower", "yUpper")),
    }


def _ransac_circle(
    points: np.ndarray,
    *,
    trials: int,
    inlier_residual_px: float,
    minimum_inliers: int,
) -> tuple[tuple[float, float, float], np.ndarray, float] | None:
    """Fit a deterministic RANSAC circle and refine only its inliers."""
    if len(points) < max(3, minimum_inliers):
        return None
    rng = np.random.default_rng(0)
    best: tuple[int, float, tuple[float, float, float], np.ndarray] | None = None
    for _ in range(max(1, trials)):
        indices = rng.choice(len(points), size=3, replace=False)
        try:
            circle = fit_circle_kasa(points[indices])
        except (ValueError, np.linalg.LinAlgError):
            continue
        if not all(math.isfinite(float(value)) for value in circle) or circle[2] <= 0.0:
            continue
        residuals = np.abs(
            np.hypot(points[:, 0] - circle[0], points[:, 1] - circle[1]) - circle[2]
        )
        inliers = residuals <= inlier_residual_px
        count = int(inliers.sum())
        if count < minimum_inliers:
            continue
        median = float(np.median(residuals[inliers]))
        ranked = (count, -median, circle, inliers)
        if best is None or ranked[:2] > best[:2]:
            best = ranked
    if best is None:
        return None
    inliers = best[3]
    refined = geometric_circle_fit(points[inliers], best[2])
    residual = circular_residual(points[inliers], refined)
    return refined, inliers, residual


def _phi_multicircle_recovery(
    target: np.ndarray,
    shape: ShapeModel,
    transform: SimilarityTransform,
    predicted_center: tuple[float, float],
    predicted_radius: float,
    main: dict[str, Any],
    gradient: np.ndarray,
    normalizer: float,
    phi_config: dict[str, Any],
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    """Use polarity-aware radial edges and RANSAC to reject a wrong circle."""
    image = contrast_stretch(target)
    angle_start = float(shape.angle_start + transform.theta_rad)
    angle_end = float(shape.angle_end + transform.theta_rad)
    expected_extent = max(0.05, abs(angle_end - angle_start))
    sample_count = max(120, int(predicted_radius * expected_extent))
    angles = np.linspace(angle_start, angle_end, min(480, sample_count), dtype=np.float64)
    search_width = int(phi_config["multicircle_radial_search_width_px"])
    seed_centers = [
        predicted_center,
        (float(main["target_cx"]), float(main["target_cy"])),
        (
            0.5 * (predicted_center[0] + float(main["target_cx"])),
            0.5 * (predicted_center[1] + float(main["target_cy"])),
        ),
    ]
    radius_mid = predicted_radius * 0.5 * (
        float(phi_config["min_radius_scale_ratio"])
        + float(phi_config["max_radius_scale_ratio"])
    )
    seed_radii = [predicted_radius, float(main["target_radius"]), radius_mid]
    radius_min = predicted_radius * float(phi_config["min_radius_scale_ratio"])
    radius_max = predicted_radius * float(phi_config["max_radius_scale_ratio"])
    center_limit = float(phi_config["search_radius_px"]) * float(
        phi_config["boundary_saturation_fraction"]
    )
    candidates: list[dict[str, Any]] = []
    for seed_center in seed_centers:
        for seed_radius in seed_radii:
            edge_points: list[tuple[float, float]] = []
            point_angles: list[float] = []
            for angle in angles:
                polarity_token = math.copysign(
                    EDGE_SCORE_FLOOR + 1.0, float(shape.polarity)
                ) if abs(float(shape.polarity)) > 1e-9 else 0.0
                point = radial_edge_at_angle(
                    image, seed_center, float(angle), float(seed_radius),
                    polarity_token, search_width,
                )
                if point is not None:
                    edge_points.append(point)
                    point_angles.append(float(angle))
            points = np.asarray(edge_points, dtype=np.float64)
            fitted = _ransac_circle(
                points,
                trials=int(phi_config["multicircle_ransac_trials"]),
                inlier_residual_px=float(phi_config["multicircle_ransac_inlier_residual_px"]),
                minimum_inliers=int(phi_config["min_edge_points"]),
            )
            if fitted is None:
                continue
            circle, inliers, residual = fitted
            cx, cy, radius = (float(value) for value in circle)
            inlier_angles = np.unwrap(np.asarray(point_angles, dtype=np.float64)[inliers])
            covered_extent = float(np.ptp(inlier_angles)) if len(inlier_angles) > 1 else 0.0
            coverage_fraction = min(1.0, covered_extent / expected_extent)
            support_values = bilinear_sample(
                gradient,
                cx + radius * np.cos(angles),
                cy + radius * np.sin(angles),
            )
            side_values = np.concatenate([
                bilinear_sample(
                    gradient, cx + (radius + offset) * np.cos(angles),
                    cy + (radius + offset) * np.sin(angles),
                )
                for offset in (-6.0, 6.0)
            ])
            support_values = support_values[np.isfinite(support_values)]
            side_values = side_values[np.isfinite(side_values)]
            peak = float(np.median(support_values)) if len(support_values) else 0.0
            side = float(np.median(side_values)) if len(side_values) else peak
            edge_peak = peak / normalizer
            prominence = (peak - side) / normalizer
            offset_x = cx - predicted_center[0]
            offset_y = cy - predicted_center[1]
            ratio = radius / predicted_radius
            boundary = {
                "xLower": offset_x <= -center_limit,
                "xUpper": offset_x >= center_limit,
                "yLower": offset_y <= -center_limit,
                "yUpper": offset_y >= center_limit,
                "limitPx": center_limit,
            }
            reasons: list[str] = []
            if not radius_min <= radius <= radius_max:
                reasons.append("radius_scale_ratio_out_of_range")
            if any(boundary[name] for name in ("xLower", "xUpper", "yLower", "yUpper")):
                reasons.append("center_boundary_saturated")
            if residual > float(phi_config["max_fit_residual_target_px"]):
                reasons.append("ransac_residual_above_gate")
            if coverage_fraction < float(phi_config["min_angle_coverage_fraction"]):
                reasons.append("angle_coverage_below_gate")
            if edge_peak < float(phi_config["min_edge_peak_normalized"]):
                reasons.append("edge_peak_below_gate")
            if prominence < float(phi_config["min_edge_prominence_normalized"]):
                reasons.append("edge_prominence_below_gate")
            candidates.append({
                "target_cx": cx, "target_cy": cy, "target_radius": radius,
                "radius_scale_ratio": ratio,
                "center_offset": math.hypot(offset_x, offset_y),
                "center_offset_x": offset_x, "center_offset_y": offset_y,
                "center_boundary": boundary,
                "radius_lower_bound": radius_min, "radius_upper_bound": radius_max,
                "edge_peak": edge_peak, "prominence": prominence,
                "lower_radius_saturated": radius <= radius_min + 1e-6,
                "upper_radius_saturated": radius >= radius_max - 1e-6,
                "center_saturated": any(boundary[name] for name in ("xLower", "xUpper", "yLower", "yUpper")),
                "ransac_inliers": int(inliers.sum()),
                "ransac_residual": residual,
                "angle_coverage_fraction": coverage_fraction,
                "failureReasons": reasons,
                "score": edge_peak + prominence + coverage_fraction - residual / max(
                    1.0, float(phi_config["max_fit_residual_target_px"])
                ),
            })
    accepted = [candidate for candidate in candidates if not candidate["failureReasons"]]
    selected = max(accepted, key=lambda candidate: candidate["score"], default=None)
    diagnostics = {
        "candidate_multicircle_count": len(candidates),
        "candidate_multicircle_valid_count": len(accepted),
        "candidate_multicircle_rejections": [
            candidate["failureReasons"] for candidate in candidates if candidate["failureReasons"]
        ],
        "candidate_multicircle_ransac_inliers": (
            None if selected is None else selected["ransac_inliers"]
        ),
        "candidate_multicircle_ransac_residual_target_px": (
            None if selected is None else selected["ransac_residual"]
        ),
        "candidate_multicircle_angle_coverage_fraction": (
            None if selected is None else selected["angle_coverage_fraction"]
        ),
        "candidate_multicircle_polarity_enforced": abs(float(shape.polarity)) > 1e-9,
    }
    return selected, diagnostics


def _reference_edge_phase_fraction(
    reference: ReferenceModel,
    shape: ShapeModel,
    phi_config: dict[str, Any],
) -> tuple[float | None, dict[str, Any]]:
    """Infer annotation edge phase from authoritative reference pixels only."""
    if (
        shape.circle is None
        or shape.template_angles is None
        or abs(float(shape.polarity)) <= 1e-9
    ):
        return None, {"failure": "reference_polarity_or_geometry_unavailable"}
    half_width = int(phi_config["phase_profile_half_width_px"])
    offsets = np.arange(-half_width, half_width + 1, dtype=np.float64)
    center_index = half_width
    polarity_sign = 1.0 if float(shape.polarity) > 0.0 else -1.0
    cx, cy, radius = (float(value) for value in shape.circle)
    annotated_samples = [
        (
            math.atan2(float(point[1]) - cy, float(point[0]) - cx),
            math.hypot(float(point[0]) - cx, float(point[1]) - cy),
        )
        for point in shape.points
        if len(point) == 2
    ]
    if not annotated_samples:
        annotated_samples = [
            (float(angle), radius) for angle in shape.template_angles
        ]
    fractions: list[float] = []
    contrasts: list[float] = []
    for angle, annotated_radius in annotated_samples:
        profile = bilinear_sample(
            reference.gray,
            cx + (annotated_radius + offsets) * math.cos(float(angle)),
            cy + (annotated_radius + offsets) * math.sin(float(angle)),
        )
        if np.isnan(profile).any():
            continue
        # Calibrate the phase on the same smoothed signal used by target
        # detection.  Mixing a raw reference profile with a smoothed target
        # profile changes the meaning of the phase fraction and shifts the
        # selected physical boundary even during template self-check.
        oriented = smooth_1d(
            profile * polarity_sign,
            int(phi_config["phase_profile_smooth_window"]),
        )
        inner = float(np.median(oriented[:5]))
        outer = float(np.median(oriented[-5:]))
        contrast = outer - inner
        if contrast < float(phi_config["phase_min_contrast"]):
            continue
        fraction = float((oriented[center_index] - inner) / contrast)
        if math.isfinite(fraction) and -0.25 <= fraction <= 1.25:
            fractions.append(fraction)
            contrasts.append(contrast)
    minimum = int(phi_config["phase_min_points"])
    if len(fractions) < minimum:
        return None, {
            "failure": "reference_phase_support_below_gate",
            "support": len(fractions),
            "minimumSupport": minimum,
        }
    phase = float(np.clip(np.median(fractions), 0.05, 0.95))
    return phase, {
        "failure": None,
        "support": len(fractions),
        "minimumSupport": minimum,
        "medianContrast": float(np.median(contrasts)),
        "phaseFraction": phase,
        "calibrationSamples": "manual_annotation_points",
    }


def _phase_edge_at_angle(
    image: np.ndarray,
    center: tuple[float, float],
    radius: float,
    angle: float,
    polarity_sign: float,
    phase_fraction: float,
    phi_config: dict[str, Any],
) -> tuple[tuple[float, float], float, float, float] | None:
    half_width = int(phi_config["phase_profile_half_width_px"])
    offsets = np.arange(-half_width, half_width + 1, dtype=np.float64)
    profile = bilinear_sample(
        image,
        center[0] + (radius + offsets) * math.cos(angle),
        center[1] + (radius + offsets) * math.sin(angle),
    )
    if np.isnan(profile).any():
        return None
    oriented = smooth_1d(
        profile * polarity_sign, int(phi_config["phase_profile_smooth_window"])
    )
    derivative = np.diff(oriented)
    mids = (offsets[:-1] + offsets[1:]) * 0.5
    prior_sigma = max(2.0, half_width * 0.42)
    prior = np.exp(-(mids * mids) / (2.0 * prior_sigma * prior_sigma))
    score = np.maximum(derivative, 0.0) * prior
    peak_index = int(np.argmax(score))
    raw_peak = float(max(derivative[peak_index], 0.0))
    local = derivative[np.abs(mids) <= min(6.0, half_width * 0.5)]
    local_positive = float(max(float(np.max(local)), 0.0)) if len(local) else 0.0
    local_negative = float(max(-float(np.min(local)), 0.0)) if len(local) else 0.0
    local_polarity_margin = local_positive - local_negative
    if raw_peak < float(phi_config["phase_min_edge_score"]):
        return None
    inner_start = max(0, peak_index - 8)
    inner_stop = max(inner_start + 1, peak_index - 3)
    outer_start = min(len(oriented), peak_index + 5)
    outer_stop = min(len(oriented), peak_index + 10)
    if inner_stop > len(oriented) or outer_stop <= outer_start:
        return None
    inner = float(np.median(oriented[inner_start:inner_stop]))
    outer = float(np.median(oriented[outer_start:outer_stop]))
    contrast = outer - inner
    if contrast < float(phi_config["phase_min_contrast"]):
        return None
    threshold = inner + phase_fraction * contrast
    crossing_offset: float | None = None
    for index in range(
        max(0, peak_index - 2), min(len(oriented) - 1, peak_index + 9)
    ):
        first = float(oriented[index])
        second = float(oriented[index + 1])
        if first <= threshold <= second and second > first:
            fraction = (threshold - first) / (second - first)
            crossing_offset = float(offsets[index] + fraction)
            break
    if crossing_offset is None:
        return None
    edge_radius = radius + crossing_offset
    return (
        (
            float(center[0] + edge_radius * math.cos(angle)),
            float(center[1] + edge_radius * math.sin(angle)),
        ),
        raw_peak,
        contrast,
        local_polarity_margin,
    )


def _refine_phi_reference_phase(
    target: np.ndarray,
    reference: ReferenceModel,
    shape: ShapeModel,
    transform: SimilarityTransform,
    predicted_center: tuple[float, float],
    predicted_radius: float,
    seed: dict[str, Any],
    normalizer: float,
    phi_config: dict[str, Any],
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    phase, reference_diagnostic = _reference_edge_phase_fraction(
        reference, shape, phi_config
    )
    diagnostics: dict[str, Any] = {
        "candidate_edge_semantics": "reference_phase_outer_polarity_edge",
        "candidate_reference_edge_phase_fraction": phase,
        "candidate_reference_phase": reference_diagnostic,
        "candidate_polarity_enforced": phase is not None,
        "candidate_phase_failure": None,
    }
    if phase is None:
        diagnostics["candidate_phase_failure"] = reference_diagnostic["failure"]
        return None, diagnostics
    polarity_sign = 1.0 if float(shape.polarity) > 0.0 else -1.0
    extension = math.radians(float(phi_config["phase_angle_extension_deg"]))
    d7_shape = next(
        (item for item in reference.shapes if item.sanitized == "d7"), None
    )
    if shape.circle is None or shape.angle_start is None or shape.angle_end is None:
        diagnostics["candidate_phase_failure"] = "reference_arc_geometry_unavailable"
        return None, diagnostics
    left_start = float(shape.angle_start + transform.theta_rad - extension)
    left_end = float(shape.angle_end + transform.theta_rad + extension)
    samples_per_side = max(160, int(phi_config["phase_min_points"] * 5))
    angle_groups: tuple[tuple[str, np.ndarray], ...] = ((
        "reference_left", np.linspace(left_start, left_end, samples_per_side)
    ),)
    if d7_shape is not None and d7_shape.line_p1 is not None and d7_shape.line_p2 is not None:
        ref_cx, ref_cy, _ = shape.circle
        d7_midpoint = (
            0.5 * (d7_shape.line_p1[0] + d7_shape.line_p2[0]),
            0.5 * (d7_shape.line_p1[1] + d7_shape.line_p2[1]),
        )
        symmetry_axis = math.atan2(
            d7_midpoint[1] - ref_cy, d7_midpoint[0] - ref_cx
        )
        right_start = float(
            2.0 * symmetry_axis - shape.angle_end + transform.theta_rad - extension
        )
        right_end = float(
            2.0 * symmetry_axis - shape.angle_start + transform.theta_rad + extension
        )
        angle_groups += ((
            "reference_right", np.linspace(right_start, right_end, samples_per_side)
        ),)
    else:
        diagnostics["candidate_opposite_arc_status"] = "reference_geometry_unavailable"
    image = contrast_stretch(target)
    points: list[tuple[float, float]] = []
    point_angles: list[float] = []
    point_sides: list[str] = []
    edge_peaks: list[float] = []
    contrasts: list[float] = []
    polarity_support: list[bool] = []
    seed_center = (float(seed["target_cx"]), float(seed["target_cy"]))
    seed_radius = float(seed["target_radius"])
    for side_name, angles in angle_groups:
        for angle in angles:
            detected = _phase_edge_at_angle(
                image, seed_center, seed_radius, float(angle), polarity_sign,
                phase, phi_config,
            )
            if detected is None:
                continue
            point, edge_peak, contrast, local_polarity_margin = detected
            points.append(point)
            point_angles.append(float(angle))
            point_sides.append(side_name)
            edge_peaks.append(edge_peak)
            contrasts.append(contrast)
            polarity_support.append(local_polarity_margin >= 0.0)
    point_array = np.asarray(points, dtype=np.float64)
    angle_array = np.asarray(point_angles, dtype=np.float64)
    side_array = np.asarray(point_sides, dtype=object)
    polarity_array = np.asarray(polarity_support, dtype=bool)
    edge_peak_array = np.asarray(edge_peaks, dtype=np.float64)
    contrast_array = np.asarray(contrasts, dtype=np.float64)
    reference_mask = side_array == "reference_left"
    fitted = _ransac_circle(
        point_array[reference_mask],
        trials=int(phi_config["phase_ransac_trials"]),
        inlier_residual_px=float(phi_config["phase_ransac_inlier_residual_px"]),
        minimum_inliers=int(phi_config["phase_min_points"]),
    ) if reference_mask.any() else None
    if fitted is None:
        diagnostics.update({
            "candidate_phase_failure": "phase_circle_fit_failed",
            "candidate_phase_edge_points": int(reference_mask.sum()),
            "candidate_phase_raw_points": int(reference_mask.sum()),
            "candidate_phase_inlier_fraction": None,
        })
        return None, diagnostics
    circle, reference_inliers, residual = fitted
    inliers = np.zeros(len(points), dtype=bool)
    inliers[np.flatnonzero(reference_mask)] = reference_inliers
    evidence_inliers = inliers.copy()
    opposite_mask = side_array == "reference_right"
    opposite_fit = _ransac_circle(
        point_array[opposite_mask],
        trials=int(phi_config["phase_ransac_trials"]),
        inlier_residual_px=float(phi_config["phase_ransac_inlier_residual_px"]),
        minimum_inliers=int(phi_config["phase_min_points"]),
    ) if opposite_mask.any() else None
    if opposite_fit is not None:
        _, opposite_inliers, _ = opposite_fit
        evidence_inliers[np.flatnonzero(opposite_mask)] = opposite_inliers
    inlier_count = int(reference_inliers.sum())
    reference_raw_count = int(reference_mask.sum())
    inlier_fraction = float(inlier_count / reference_raw_count) if reference_raw_count else 0.0
    cx, cy, radius = (float(value) for value in circle)
    side_diagnostics: list[dict[str, Any]] = []
    evidence_segments: list[dict[str, Any]] = []
    side_coverages: list[float] = []
    side_inlier_counts: list[int] = []
    side_circle_models: list[tuple[float, float, float]] = []
    side_circle_residuals: list[float] = []
    for side_name, side_angles in angle_groups:
        side_mask = evidence_inliers & (side_array == side_name)
        side_count = int(side_mask.sum())
        side_inlier_counts.append(side_count)
        selected_angles = np.unwrap(angle_array[side_mask])
        expected_extent = max(1e-9, abs(float(side_angles[-1] - side_angles[0])))
        side_coverage = (
            float(np.ptp(selected_angles) / expected_extent)
            if len(selected_angles) > 1 else 0.0
        )
        side_coverage = min(1.0, side_coverage)
        side_coverages.append(side_coverage)
        ordered = point_array[side_mask]
        if len(ordered):
            order = np.argsort(angle_array[side_mask])
            ordered = ordered[order]
        side_diagnostics.append({
            "side": side_name,
            "inlierPoints": side_count,
            "angleCoverageFraction": side_coverage,
            "polaritySupportFraction": (
                float(np.mean(polarity_array[side_mask])) if side_count else 0.0
            ),
        })
        if side_count >= int(phi_config["phase_min_points"]):
            try:
                side_circle = geometric_circle_fit(
                    ordered, fit_circle_kasa(ordered)
                )
                side_circle_models.append(tuple(float(value) for value in side_circle))
                side_circle_residuals.append(float(circular_residual(ordered, side_circle)))
                side_diagnostics[-1].update({
                    "circleCenterPx": [float(side_circle[0]), float(side_circle[1])],
                    "circleRadiusPx": float(side_circle[2]),
                    "circleResidualPx": side_circle_residuals[-1],
                })
            except (ValueError, np.linalg.LinAlgError):
                side_diagnostics[-1]["circleFitFailure"] = "side_circle_fit_failed"
    coverage = side_coverages[0] if side_coverages else 0.0
    side_center_disagreement = None
    side_radius_disagreement = None
    if len(side_circle_models) == 2:
        # Only reference_left has a LabelMe-defined subpixel edge phase in the
        # legacy reference.  The mirrored side is still mandatory image
        # evidence, but cannot safely redefine that phase.  Use the calibrated
        # side for the one circle model and require the independently detected
        # opposite arc to agree with it under the unchanged residual gate.
        common_model_residuals = [
            float(circular_residual(point_array[evidence_inliers & (side_array == side)],
                                    (cx, cy, radius)))
            for side, _ in angle_groups
        ]
        side_center_disagreement = math.dist(
            side_circle_models[0][:2], side_circle_models[1][:2]
        )
        side_radius_disagreement = abs(
            side_circle_models[0][2] - side_circle_models[1][2]
        )
    offset_x = cx - predicted_center[0]
    offset_y = cy - predicted_center[1]
    phase_seed_offset_x = cx - seed_center[0]
    phase_seed_offset_y = cy - seed_center[1]
    center_limit = float(seed["center_boundary"]["limitPx"])
    center_boundary = {
        "xLower": phase_seed_offset_x <= -center_limit,
        "xUpper": phase_seed_offset_x >= center_limit,
        "yLower": phase_seed_offset_y <= -center_limit,
        "yUpper": phase_seed_offset_y >= center_limit,
        "limitPx": center_limit,
    }
    radius_min = float(seed["radius_lower_bound"])
    radius_max = float(seed["radius_upper_bound"])
    reasons: list[str] = []
    polarity_support_fraction = (
        float(np.mean(polarity_array[reference_mask])) if reference_mask.any() else 0.0
    )
    if not radius_min <= radius <= radius_max:
        reasons.append("phase_radius_out_of_bounds")
    if any(center_boundary[key] for key in ("xLower", "xUpper", "yLower", "yUpper")):
        reasons.append("phase_center_boundary_saturated")
    if inlier_count < int(phi_config["phase_min_points"]):
        reasons.append("phase_edge_points_below_gate")
    if residual > float(phi_config["max_fit_residual_target_px"]):
        reasons.append("phase_fit_residual_above_gate")
    if coverage < float(phi_config["min_angle_coverage_fraction"]):
        reasons.append("phase_angle_coverage_below_gate")
    if polarity_support_fraction < float(phi_config["min_angle_coverage_fraction"]):
        reasons.append("phase_polarity_support_below_gate")
    diagnostics.update({
        "candidate_phase_failure": None if not reasons else ",".join(reasons),
        "candidate_phase_edge_points": inlier_count,
        "candidate_phase_raw_points": reference_raw_count,
        "candidate_phase_inlier_fraction": inlier_fraction,
        "candidate_phase_fit_residual_target_px": float(residual),
        "candidate_phase_seed_center_offset_x_target_px": phase_seed_offset_x,
        "candidate_phase_seed_center_offset_y_target_px": phase_seed_offset_y,
        "candidate_phase_seed_center_offset_target_px": math.hypot(
            phase_seed_offset_x, phase_seed_offset_y
        ),
        "candidate_phase_seed_center_x_boundary": {
            "lower": bool(center_boundary["xLower"]),
            "upper": bool(center_boundary["xUpper"]),
            "limitPx": center_limit,
        },
        "candidate_phase_seed_center_y_boundary": {
            "lower": bool(center_boundary["yLower"]),
            "upper": bool(center_boundary["yUpper"]),
            "limitPx": center_limit,
        },
        "candidate_phase_angle_coverage_fraction": coverage,
        "candidate_phase_side_diagnostics": side_diagnostics,
        "candidate_phase_circle_fit_contract": (
            "reference_calibrated_arc_model_with_opposite_arc_consistency"
        ),
        "candidate_phase_common_model_side_residuals_target_px": (
            common_model_residuals if len(side_circle_models) == 2 else None
        ),
        "candidate_phase_side_center_disagreement_target_px": side_center_disagreement,
        "candidate_phase_side_radius_disagreement_target_px": side_radius_disagreement,
        "candidate_phase_polarity_support_fraction": polarity_support_fraction,
        "candidate_phase_angle_extension_deg": float(phi_config["phase_angle_extension_deg"]),
        "candidate_phase_edge_peak_normalized": float(
            np.median(edge_peak_array[reference_mask]) / normalizer
        ),
        "candidate_phase_contrast": float(np.median(contrast_array[reference_mask])),
    })
    if reasons:
        diagnostics["candidate_evidence_arc_segments_status"] = "rejected_with_phase_candidate"
        return None, diagnostics
    for index, (side_name, _) in enumerate(angle_groups):
        side_info = side_diagnostics[index]
        side_mask = evidence_inliers & (side_array == side_name)
        side_model_residual = side_info.get("circleResidualPx")
        side_accepted = (
            int(side_info["inlierPoints"]) >= int(phi_config["phase_min_points"])
            and float(side_info["angleCoverageFraction"])
            >= float(phi_config["min_angle_coverage_fraction"])
            and float(side_info["polaritySupportFraction"])
            >= float(phi_config["min_angle_coverage_fraction"])
            and side_model_residual is not None
            and float(side_model_residual)
            <= float(phi_config["max_fit_residual_target_px"])
        )
        side_info["acceptedAsVisibleArcEvidence"] = side_accepted
        side_info["commonCircleResidualPx"] = (
            None if len(side_circle_models) != 2
            else common_model_residuals[index]
        )
        if not side_accepted:
            continue
        selected_points = point_array[side_mask]
        selected_angles = angle_array[side_mask]
        selected_points = selected_points[np.argsort(selected_angles)]
        evidence_segments.append({
            "side": side_name,
            "pointsPx": [[float(x), float(y)] for x, y in selected_points],
        })
    diagnostics["candidate_evidence_arc_segments_status"] = (
        "complete_two_side" if len(evidence_segments) == 2
        else "reference_side_only_opposite_unverified"
    )
    diagnostics["candidate_evidence_arc_segments_target_px"] = evidence_segments
    refined = dict(seed)
    refined.update({
        "target_cx": cx,
        "target_cy": cy,
        "target_radius": radius,
        "radius_scale_ratio": radius / predicted_radius,
        "center_offset": math.hypot(offset_x, offset_y),
        "center_offset_x": offset_x,
        "center_offset_y": offset_y,
        "center_boundary": center_boundary,
        "center_saturated": False,
        "lower_radius_saturated": radius <= radius_min + 1e-6,
        "upper_radius_saturated": radius >= radius_max - 1e-6,
        "edge_peak": float(np.median(edge_peak_array[reference_mask]) / normalizer),
        "phase_refined": True,
    })
    return refined, diagnostics


def _phi_global_center_diagnostics(
    candidate: dict[str, Any],
    predicted_center: tuple[float, float],
    phi_config: dict[str, Any],
) -> dict[str, Any]:
    """Audit cumulative center motion against the original primary window."""
    offset_x = float(candidate["target_cx"] - predicted_center[0])
    offset_y = float(candidate["target_cy"] - predicted_center[1])
    limit = float(phi_config["search_radius_px"]) * float(
        phi_config["boundary_saturation_fraction"]
    )
    x_boundary = {"lower": offset_x <= -limit, "upper": offset_x >= limit, "limitPx": limit}
    y_boundary = {"lower": offset_y <= -limit, "upper": offset_y >= limit, "limitPx": limit}
    return {
        "candidate_global_center_offset_x_target_px": offset_x,
        "candidate_global_center_offset_y_target_px": offset_y,
        "candidate_global_center_offset_target_px": math.hypot(offset_x, offset_y),
        "candidate_global_center_x_boundary": x_boundary,
        "candidate_global_center_y_boundary": y_boundary,
        "candidate_global_center_boundary_saturated": bool(
            x_boundary["lower"] or x_boundary["upper"]
            or y_boundary["lower"] or y_boundary["upper"]
        ),
    }


def _detect_phi12_2(
    target: np.ndarray,
    reference: ReferenceModel,
    transform: SimilarityTransform,
    config: dict[str, Any],
    *,
    exact_template_angle_domain: bool = False,
) -> tuple[dict[str, float] | None, dict[str, Any]]:
    shape = next((item for item in reference.shapes if item.sanitized == "Phi12_2"), None)
    if shape is None or shape.circle is None:
        return None, {"candidate_failure": "reference_feature_missing"}
    cx, cy, radius = shape.circle
    predicted_center = transform.forward(cx, cy)
    predicted_radius = transform.scale * radius
    phi_config = dict(config["phi12_2"])
    if exact_template_angle_domain:
        # The authoritative 80-point manual arc already defines both ends of
        # the physical evidence domain.  The historical extension existed to
        # compensate for the old coarse reference and must not enlarge this
        # new template into the neck connection.
        phi_config["phase_angle_extension_deg"] = 0.0
    gradient = gradient_magnitude(contrast_stretch(target))
    normalizer = _gradient_normalizer(gradient)
    angles = np.linspace(
        shape.angle_start + transform.theta_rad,
        shape.angle_end + transform.theta_rad,
        120,
        dtype=np.float64,
    )
    cosines, sines = np.cos(angles), np.sin(angles)
    polarity = float(shape.polarity)
    polarity_name = "positive" if polarity > 0.0 else ("negative" if polarity < 0.0 else "unsigned")
    angle_coverage_deg = float(math.degrees(abs(shape.angle_end - shape.angle_start)))
    main_min = float(phi_config["min_radius_scale_ratio"])
    main = _phi_radius_search_pass(
        gradient, normalizer, predicted_center, predicted_radius,
        cosines, sines, phi_config, main_min,
    )
    if main is None:
        return None, {
            "candidate_failure": "edge_search_empty",
            "candidate_recovery_pass": None,
            "candidate_main_lower_bound_saturated": False,
        }

    recovery_pass: str | None = None
    selected = main
    multicircle_diagnostics: dict[str, Any] = {}
    center_recovery_seed_offset: list[float] | None = None
    if bool(main["lower_radius_saturated"]):
        recovery_pass = "expanded_radius"
        expanded = _phi_radius_search_pass(
            gradient, normalizer, predicted_center, predicted_radius,
            cosines, sines, phi_config,
            float(phi_config["recovery_min_radius_scale_ratio"]),
        )
        if expanded is None:
            return None, {
                "candidate_failure": "expanded_radius_search_empty",
                "candidate_recovery_pass": recovery_pass,
                "candidate_main_lower_bound_saturated": True,
                "candidate_main_radius_scale_ratio": main["radius_scale_ratio"],
            }
        selected = expanded
    elif bool(main["center_saturated"]):
        recovery_pass = "center_recenter"
        center_recovery_seed_offset = [
            float(main["center_offset_x"]), float(main["center_offset_y"]),
        ]
        recenter_config = {
            **phi_config,
            "search_radius_px": float(phi_config["center_recovery_search_radius_px"]),
        }
        recentered = _phi_radius_search_pass(
            gradient, normalizer,
            (float(main["target_cx"]), float(main["target_cy"])),
            predicted_radius, cosines, sines, recenter_config, main_min,
        )
        if recentered is None:
            return None, {
                "candidate_failure": "center_recenter_search_empty",
                "candidate_recovery_pass": recovery_pass,
                "candidate_main_lower_bound_saturated": False,
                "candidate_main_radius_scale_ratio": main["radius_scale_ratio"],
                "candidate_center_recovery_seed_offset_target_px": center_recovery_seed_offset,
            }
        # The second pass owns a small local window around a strong ring-edge
        # seed.  Keep its local boundary flags, but report displacement from
        # the original registration prediction for auditability.
        recentered["center_offset_x"] = float(recentered["target_cx"] - predicted_center[0])
        recentered["center_offset_y"] = float(recentered["target_cy"] - predicted_center[1])
        recentered["center_offset"] = math.hypot(
            recentered["center_offset_x"], recentered["center_offset_y"]
        )
        selected = recentered
    elif (
        bool(main["upper_radius_saturated"])
        or float(main["edge_peak"]) < float(phi_config["min_edge_peak_normalized"])
        or float(main["prominence"]) < float(phi_config["min_edge_prominence_normalized"])
    ):
        recovery_pass = "robust_multicircle"
        recovered, multicircle_diagnostics = _phi_multicircle_recovery(
            target, shape, transform, predicted_center, predicted_radius,
            main, gradient, normalizer, phi_config,
        )
        if recovered is not None:
            selected = recovered

    legacy_magnitude_edge_peak = float(selected["edge_peak"])
    legacy_magnitude_prominence = float(selected["prominence"])
    global_center_diagnostics = _phi_global_center_diagnostics(
        selected, predicted_center, phi_config
    )
    phase_fallback_rejection: str | None = None
    phase_diagnostics: dict[str, Any] = {
        "candidate_edge_semantics": "gradient_magnitude_legacy",
        "candidate_reference_edge_phase_fraction": None,
        "candidate_polarity_enforced": False,
        "candidate_phase_failure": "reference_polarity_unavailable",
    }
    if abs(float(shape.polarity)) > 1e-9:
        phase_selected, phase_diagnostics = _refine_phi_reference_phase(
            target, reference, shape, transform, predicted_center, predicted_radius,
            selected, normalizer, phi_config,
        )
        if phase_selected is None:
            phase_failure = str(phase_diagnostics["candidate_phase_failure"])
            bounded_phase_failures = {
                "phase_radius_out_of_bounds",
                "phase_center_boundary_saturated",
                "phase_angle_coverage_below_gate",
            }
            failure_parts = set(phase_failure.split(","))
            fallback_eligible = (
                bool(failure_parts)
                and (
                    failure_parts <= bounded_phase_failures
                    or failure_parts == {"phase_polarity_support_below_gate"}
                )
            )
            if fallback_eligible:
                phase_diagnostics["candidate_phase_fallback"] = (
                    "legacy_magnitude_quality_fallback"
                )
            phase_inlier_fraction = phase_diagnostics.get(
                "candidate_phase_inlier_fraction"
            )
            if (
                fallback_eligible
                and failure_parts == {"phase_polarity_support_below_gate"}
                and phase_inlier_fraction is not None
                and float(phase_inlier_fraction)
                < float(phi_config["min_angle_coverage_fraction"])
            ):
                fallback_eligible = False
                phase_fallback_rejection = "phase_inlier_fraction_below_gate"
            if (
                fallback_eligible
                and recovery_pass == "center_recenter"
                and bool(global_center_diagnostics[
                    "candidate_global_center_boundary_saturated"
                ])
            ):
                fallback_eligible = False
                phase_fallback_rejection = (
                    "global_center_displacement_requires_phase_evidence"
                )
            if fallback_eligible:
                phase_diagnostics.update({
                    "candidate_edge_semantics": "legacy_gradient_magnitude_quality_fallback",
                    "candidate_polarity_enforced": False,
                    "candidate_phase_fallback": "legacy_magnitude_quality_fallback",
                })
                if recovery_pass is None:
                    recovery_pass = "legacy_magnitude_quality_fallback"
            else:
                return None, {
                    "candidate_failure": (
                        phase_failure if phase_fallback_rejection is None
                        else f"{phase_failure},{phase_fallback_rejection}"
                    ),
                    "candidate_recovery_pass": recovery_pass,
                    "candidate_main_lower_bound_saturated": bool(main["lower_radius_saturated"]),
                    "candidate_main_radius_scale_ratio": float(main["radius_scale_ratio"]),
                    "candidate_phase_fallback_rejection": phase_fallback_rejection,
                    **global_center_diagnostics,
                    **phase_diagnostics,
                    **multicircle_diagnostics,
                }
        else:
            phase_diagnostics["candidate_phase_fallback"] = None
            selected = phase_selected
            global_center_diagnostics = _phi_global_center_diagnostics(
                selected, predicted_center, phi_config
            )

    target_cx = float(selected["target_cx"])
    target_cy = float(selected["target_cy"])
    target_radius = float(selected["target_radius"])
    ratio = float(selected["radius_scale_ratio"])
    support_angles = np.linspace(
        shape.angle_start + transform.theta_rad,
        shape.angle_end + transform.theta_rad,
        max(80, int(phi_config["min_edge_points"] * 3)),
        dtype=np.float64,
    )
    radial_offsets = np.arange(-7.0, 8.0, 1.0)
    residuals: list[float] = []
    edge_scores: list[float] = []
    for angle in support_angles:
        values = bilinear_sample(
            gradient,
            target_cx + (target_radius + radial_offsets) * math.cos(float(angle)),
            target_cy + (target_radius + radial_offsets) * math.sin(float(angle)),
        )
        valid = np.isfinite(values)
        if not valid.any():
            continue
        safe = np.where(valid, values, 0.0)
        prior = np.exp(-(radial_offsets * radial_offsets) / (2.0 * 2.5 * 2.5))
        index = int(np.argmax(safe * prior))
        residuals.append(abs(float(radial_offsets[index])))
        edge_scores.append(float(safe[index]))
    point_count = int(
        phase_diagnostics.get("candidate_phase_edge_points", len(residuals))
    )
    fit_residual = float(
        phase_diagnostics.get(
            "candidate_phase_fit_residual_target_px",
            float(np.median(residuals)) if residuals else float("inf"),
        )
    )
    saturated = bool(
        selected["center_saturated"]
        or selected["lower_radius_saturated"]
        or selected["upper_radius_saturated"]
    )
    selected_min = (
        float(phi_config["recovery_min_radius_scale_ratio"])
        if recovery_pass == "expanded_radius" else main_min
    )
    phase_refined = bool(selected.get("phase_refined", False))
    acceptance_edge_peak = (
        legacy_magnitude_edge_peak if phase_refined else float(selected["edge_peak"])
    )
    acceptance_prominence = (
        legacy_magnitude_prominence if phase_refined else float(selected["prominence"])
    )
    edge_peak_gate = float(phi_config["min_edge_peak_normalized"])
    prominence_gate = float(phi_config["min_edge_prominence_normalized"])
    reasons: list[str] = []
    if not (selected_min <= ratio <= float(phi_config["max_radius_scale_ratio"])):
        reasons.append("radius_scale_ratio_out_of_range")
    if point_count < int(phi_config["min_edge_points"]):
        reasons.append("edge_points_below_gate")
    if fit_residual > float(phi_config["max_fit_residual_target_px"]):
        reasons.append("fit_residual_above_gate")
    if acceptance_edge_peak < edge_peak_gate:
        reasons.append("edge_peak_below_gate")
    if acceptance_prominence < prominence_gate:
        reasons.append("edge_prominence_below_gate")
    if saturated:
        reasons.append("search_boundary_saturated")
    quality = {
        "candidate_failure": None if not reasons else ",".join(reasons),
        "candidate_recovery_pass": recovery_pass,
        "candidate_main_lower_bound_saturated": bool(main["lower_radius_saturated"]),
        "candidate_main_radius_scale_ratio": float(main["radius_scale_ratio"]),
        "candidate_radius_scale_ratio": ratio,
        "candidate_edge_points": float(point_count),
        "candidate_fit_residual_target_px": fit_residual,
        "candidate_center_offset_target_px": float(selected["center_offset"]),
        "candidate_center_offset_x_target_px": float(selected["center_offset_x"]),
        "candidate_center_offset_y_target_px": float(selected["center_offset_y"]),
        "candidate_center_recovery_seed_offset_target_px": center_recovery_seed_offset,
        "candidate_center_x_boundary": {
            "lower": bool(selected["center_boundary"]["xLower"]),
            "upper": bool(selected["center_boundary"]["xUpper"]),
            "limitPx": float(selected["center_boundary"]["limitPx"]),
        },
        "candidate_center_y_boundary": {
            "lower": bool(selected["center_boundary"]["yLower"]),
            "upper": bool(selected["center_boundary"]["yUpper"]),
            "limitPx": float(selected["center_boundary"]["limitPx"]),
        },
        "candidate_radius_lower_bound_target_px": float(selected["radius_lower_bound"]),
        "candidate_radius_upper_bound_target_px": float(selected["radius_upper_bound"]),
        "candidate_upper_radius_boundary_saturated": bool(selected["upper_radius_saturated"]),
        "candidate_edge_polarity": polarity_name,
        "candidate_edge_polarity_reference_delta": polarity,
        "candidate_angle_coverage_deg": angle_coverage_deg,
        "candidate_edge_peak_normalized": float(selected["edge_peak"]),
        "candidate_edge_prominence_normalized": float(selected["prominence"]),
        "candidate_legacy_magnitude_edge_peak_normalized": legacy_magnitude_edge_peak,
        "candidate_legacy_magnitude_edge_prominence_normalized": legacy_magnitude_prominence,
        "candidate_legacy_magnitude_edge_peak_gate_passed": (
            legacy_magnitude_edge_peak >= edge_peak_gate
        ),
        "candidate_legacy_magnitude_edge_prominence_gate_passed": (
            legacy_magnitude_prominence >= prominence_gate
        ),
        "candidate_phase_evidence_gate_passed": (
            phase_refined and phase_diagnostics.get("candidate_phase_failure") is None
        ),
        "candidate_acceptance_score_contract": (
            "reference_phase_multi_evidence" if phase_refined
            else "legacy_gradient_magnitude"
        ),
        "candidate_median_edge_score": float(np.median(edge_scores)) if edge_scores else float("nan"),
        "candidate_search_boundary_saturated": saturated,
        "candidate_lower_radius_boundary_saturated": bool(selected["lower_radius_saturated"]),
        "candidate_phase_fallback_rejection": phase_fallback_rejection,
        **global_center_diagnostics,
        **phase_diagnostics,
        **multicircle_diagnostics,
    }
    if reasons:
        return None, quality
    ref_cx, ref_cy = transform.inverse(target_cx, target_cy)
    return {
        "Phi12_2_cx": ref_cx,
        "Phi12_2_cy": ref_cy,
        "Phi12_2_r": float(target_radius / transform.scale),
        "Phi12_2_diameter_px": float(2.0 * target_radius / transform.scale),
    }, quality


def _paired_contour_boundary(
    image: np.ndarray,
    p1_target: tuple[float, float],
    p2_target: tuple[float, float],
    endpoint: str,
    outer_polarity: float,
    d7_config: dict[str, Any],
    diagnostics: dict[str, Any],
) -> BoundaryDetection | None:
    """Use paired transitions to estimate the physical outer-contour locus.

    The photographed contour is a finite-width dark edge response.  Its two
    opposite-polarity transitions are raw image evidence; their midpoint is
    the subpixel estimate of the underlying physical edge.  This distinction
    prevents either side of the optical edge band from being misreported as
    the part boundary.
    """
    diagnostics.update({
        "endpoint": endpoint,
        "boundarySemantics": "paired_transition_center_estimate_of_outer_contour",
        "pairSupport": 0,
        "outerPeakMedian": None,
        "innerPeakMedian": None,
        "pairWidthMedianPx": None,
        "inlierPoints": 0,
        "medianResidualPx": None,
        "axisCosine": None,
        "offsetPx": None,
        "failureStage": None,
        "layerStabilizationAttempted": False,
        "layerStabilizationUsed": False,
        "layerStabilizationInitialFailureStage": None,
        "layerStabilizationRawPointCount": 0,
        "layerStabilizationInlierPointCount": 0,
        "layerStabilizationResidualGatePx": float(
            d7_config["max_fit_residual_target_px"]
        ),
        "layerStabilizationFailure": None,
    })
    dx = p2_target[0] - p1_target[0]
    dy = p2_target[1] - p1_target[1]
    length = math.hypot(dx, dy)
    if length < 5.0:
        diagnostics["failureStage"] = "axis_degenerate"
        return None
    if abs(float(outer_polarity)) <= 1e-9:
        diagnostics["failureStage"] = "reference_outer_polarity_unavailable"
        return None
    axis = (dx / length, dy / length)
    tangent = (-axis[1], axis[0])
    origin = p1_target if endpoint == "p1" else p2_target
    search_window = 42
    offsets = np.arange(-search_window, search_window + 1, dtype=np.float64)
    mids = (offsets[:-1] + offsets[1:]) * 0.5
    prior_sigma = float(d7_config["paired_edge_prior_sigma_px"])
    prior = np.exp(-(mids * mids) / (2.0 * prior_sigma * prior_sigma))
    outer_sign = 1.0 if outer_polarity > 0.0 else -1.0
    # p1's interior lies towards p2 (+axis); p2's lies towards p1 (-axis).
    interior_sign = 1.0 if endpoint == "p1" else -1.0
    minimum_width = float(d7_config["paired_edge_min_width_target_px"])
    maximum_width = float(d7_config["paired_edge_max_width_target_px"])
    minimum_peak = float(d7_config["paired_edge_min_peak"])
    contour_points: list[tuple[float, float]] = []
    outer_transition_points: list[tuple[float, float]] = []
    inner_transition_points: list[tuple[float, float]] = []
    outer_peaks: list[float] = []
    inner_peaks: list[float] = []
    pair_widths: list[float] = []
    tangent_coordinates: list[float] = []
    axis_coordinates: list[float] = []

    for tangent_offset in np.linspace(
        -float(d7_config["paired_edge_strip_half_width_px"]),
        float(d7_config["paired_edge_strip_half_width_px"]),
        int(d7_config["paired_edge_strip_samples"]),
    ):
        center = (
            origin[0] + tangent_offset * tangent[0],
            origin[1] + tangent_offset * tangent[1],
        )
        profile = bilinear_sample(
            image,
            center[0] + offsets * axis[0],
            center[1] + offsets * axis[1],
        )
        if np.isnan(profile).any():
            continue
        derivative = np.diff(smooth_1d(profile, 7))
        outer_score = derivative * outer_sign
        inner_score = -derivative * outer_sign
        best: tuple[float, float, float, float, float, float, float] | None = None
        for outer_index in range(1, len(derivative) - 1):
            outer_peak = float(outer_score[outer_index])
            if (
                outer_peak < minimum_peak
                or outer_peak < float(outer_score[outer_index - 1])
                or outer_peak < float(outer_score[outer_index + 1])
            ):
                continue
            for inner_index in range(1, len(derivative) - 1):
                signed_width = float(
                    (mids[inner_index] - mids[outer_index]) * interior_sign
                )
                if not minimum_width <= signed_width <= maximum_width:
                    continue
                inner_peak = float(inner_score[inner_index])
                if (
                    inner_peak < minimum_peak
                    or inner_peak < float(inner_score[inner_index - 1])
                    or inner_peak < float(inner_score[inner_index + 1])
                ):
                    continue
                outer_delta = parabolic_peak(outer_score.tolist(), outer_index)
                inner_delta = parabolic_peak(inner_score.tolist(), inner_index)
                outer_position = float(mids[outer_index] + outer_delta)
                inner_position = float(mids[inner_index] + inner_delta)
                center_position = 0.5 * (outer_position + inner_position)
                pair_score = float(
                    min(outer_peak, inner_peak)
                    * math.sqrt(prior[outer_index] * prior[inner_index])
                )
                candidate = (
                    pair_score, center_position, outer_position, inner_position,
                    outer_peak, inner_peak,
                    abs(inner_position - outer_position),
                )
                if best is None or candidate[0] > best[0]:
                    best = candidate
        if best is None:
            continue
        (_, center_position, outer_position, inner_position,
         outer_peak, inner_peak, pair_width) = best
        contour_points.append((float(center[0] + center_position * axis[0]),
                               float(center[1] + center_position * axis[1])))
        outer_transition_points.append((
            float(center[0] + outer_position * axis[0]),
            float(center[1] + outer_position * axis[1])))
        inner_transition_points.append((
            float(center[0] + inner_position * axis[0]),
            float(center[1] + inner_position * axis[1])))
        outer_peaks.append(outer_peak)
        inner_peaks.append(inner_peak)
        pair_widths.append(pair_width)
        tangent_coordinates.append(float(tangent_offset))
        axis_coordinates.append(float(center_position))

    diagnostics.update({
        "pairSupport": len(contour_points),
        "outerPeakMedian": None if not outer_peaks else float(np.median(outer_peaks)),
        "innerPeakMedian": None if not inner_peaks else float(np.median(inner_peaks)),
        "pairWidthMedianPx": None if not pair_widths else float(np.median(pair_widths)),
        # Preserve raw paired-transition evidence even when the subsequent
        # line fit is rejected.  Callers may audit those points, but they may
        # not promote the rejected boundary to a measurement.
        "rawContourLocusPointsPx": [list(point) for point in contour_points],
        "rawOuterTransitionPointsPx": [list(point) for point in outer_transition_points],
        "rawInnerTransitionPointsPx": [list(point) for point in inner_transition_points],
        "transitionPairsPx": [
            [list(outer), list(inner)]
            for outer, inner in zip(outer_transition_points, inner_transition_points)
        ],
    })
    minimum_support = int(d7_config["paired_edge_min_support"])
    fitted = robust_fit_line(contour_points, min_points=minimum_support)
    if fitted is None:
        diagnostics["failureStage"] = "outer_contour_locus_fit_failed"
        return None
    line, inliers = fitted
    diagnostics["inlierPoints"] = int(len(inliers))
    axis_cosine = abs(float(line[0]) * axis[0] + float(line[1]) * axis[1])
    diagnostics["axisCosine"] = axis_cosine
    residuals = np.abs(line[0] * inliers[:, 0] + line[1] * inliers[:, 1] + line[2])
    median_residual = float(np.median(residuals))
    diagnostics["medianResidualPx"] = median_residual
    initial_failure = None
    if axis_cosine < D7_BOUNDARY_MIN_AXIS_COSINE:
        initial_failure = "axis_alignment_below_gate"
    elif median_residual > float(d7_config["max_fit_residual_target_px"]):
        initial_failure = "fit_residual_above_gate"
    if initial_failure is not None:
        diagnostics["layerStabilizationAttempted"] = True
        diagnostics["layerStabilizationInitialFailureStage"] = initial_failure
        diagnostics["layerStabilizationRawPointCount"] = len(contour_points)
        stabilized, stabilization = _fit_dominant_paired_layer(
            contour_points,
            tangent_coordinates,
            axis_coordinates,
            minimum_support=minimum_support,
            residual_gate=float(d7_config["max_fit_residual_target_px"]),
        )
        diagnostics.update(stabilization)
        if stabilized is None:
            diagnostics["failureStage"] = initial_failure
            return None
        line, inliers = stabilized
        diagnostics["layerStabilizationUsed"] = True
        diagnostics["inlierPoints"] = int(len(inliers))
        axis_cosine = abs(float(line[0]) * axis[0] + float(line[1]) * axis[1])
        diagnostics["axisCosine"] = axis_cosine
        residuals = np.abs(
            line[0] * inliers[:, 0] + line[1] * inliers[:, 1] + line[2]
        )
        median_residual = float(np.median(residuals))
        diagnostics["medianResidualPx"] = median_residual
        # Stabilization changes candidate generation only.  The final
        # acceptance checks deliberately reuse every existing quality gate.
        if axis_cosine < D7_BOUNDARY_MIN_AXIS_COSINE:
            diagnostics["failureStage"] = "axis_alignment_below_gate"
            return None
        if median_residual > float(d7_config["max_fit_residual_target_px"]):
            diagnostics["failureStage"] = "fit_residual_above_gate"
            return None
    intersection = line_axis_intersection(line, origin, axis)
    if intersection is None:
        diagnostics["failureStage"] = "axis_intersection_failed"
        return None
    feature_point, offset = intersection
    diagnostics["offsetPx"] = float(offset)
    if abs(offset) > search_window:
        diagnostics["failureStage"] = "offset_out_of_search_window"
        return None
    direction = np.asarray([-float(line[1]), float(line[0])], dtype=np.float64)
    projections = inliers @ direction
    segment = [
        (inliers[int(np.argmin(projections))]).tolist(),
        (inliers[int(np.argmax(projections))]).tolist(),
    ]
    diagnostics.update({
        "rawContourLocusPointsPx": [list(point) for point in contour_points],
        "rawOuterTransitionPointsPx": [list(point) for point in outer_transition_points],
        "rawInnerTransitionPointsPx": [list(point) for point in inner_transition_points],
        "transitionPairsPx": [
            [list(outer), list(inner)]
            for outer, inner in zip(outer_transition_points, inner_transition_points)
        ],
        "inlierContourLocusPointsPx": inliers.tolist(),
        "fittedLine": [float(value) for value in line],
        "fittedSegmentPointsPx": segment,
    })
    return BoundaryDetection(
        feature_point=feature_point,
        line=tuple(float(value) for value in line),
        point_count=int(len(inliers)),
        median_residual_px=median_residual,
        median_edge_score=float(min(np.median(outer_peaks), np.median(inner_peaks))),
        offset_px=float(offset),
    )


def _fit_dominant_paired_layer(
    contour_points: list[tuple[float, float]],
    tangent_coordinates: list[float],
    axis_coordinates: list[float],
    *,
    minimum_support: int,
    residual_gate: float,
) -> tuple[
    tuple[tuple[float, float, float], np.ndarray] | None,
    dict[str, Any],
]:
    """Recover a dominant paired-transition layer without nominal guidance.

    The fit is expressed in the scan frame: tangent position is the independent
    coordinate and the paired-transition midpoint is the dependent coordinate.
    A Theil-Sen median slope resists a minority neighbouring layer.  Inliers
    are selected with the *existing* D7 fit-residual gate, and an independently
    supported second layer makes the result ambiguous and therefore invalid.
    """
    quality: dict[str, Any] = {
        "layerStabilizationInlierPointCount": 0,
        "layerStabilizationResidualGatePx": float(residual_gate),
        "layerStabilizationFailure": None,
    }
    points = np.asarray(contour_points, dtype=np.float64)
    tangent = np.asarray(tangent_coordinates, dtype=np.float64)
    axial = np.asarray(axis_coordinates, dtype=np.float64)
    if (
        points.ndim != 2 or points.shape[1:] != (2,)
        or len(points) != len(tangent) or len(points) != len(axial)
        or len(points) < minimum_support
    ):
        quality["layerStabilizationFailure"] = "support_below_gate"
        return None, quality

    def layer_mask(x: np.ndarray, y: np.ndarray) -> np.ndarray | None:
        slopes = [
            float((y[j] - y[i]) / (x[j] - x[i]))
            for i in range(len(x))
            for j in range(i + 1, len(x))
            if abs(float(x[j] - x[i])) > 1e-9
        ]
        if not slopes:
            return None
        slope = float(np.median(np.asarray(slopes, dtype=np.float64)))
        intercept = float(np.median(y - slope * x))
        return np.abs(y - (slope * x + intercept)) <= residual_gate

    selected = layer_mask(tangent, axial)
    if selected is None or int(selected.sum()) < minimum_support:
        quality["layerStabilizationFailure"] = "dominant_layer_support_below_gate"
        return None, quality

    # A second independently supported layer is genuine ambiguity.  Do not
    # resolve it by proximity to the reference length or a nominal dimension.
    rejected = ~selected
    if int(rejected.sum()) >= minimum_support:
        alternate = layer_mask(tangent[rejected], axial[rejected])
        if alternate is not None and int(alternate.sum()) >= minimum_support:
            quality["layerStabilizationFailure"] = "ambiguous_competing_layers"
            return None, quality

    inlier_points = points[selected]
    fitted = robust_fit_line(
        [tuple(float(value) for value in point) for point in inlier_points],
        min_points=minimum_support,
    )
    if fitted is None:
        quality["layerStabilizationFailure"] = "dominant_layer_fit_failed"
        return None, quality
    line, fitted_inliers = fitted
    quality["layerStabilizationInlierPointCount"] = int(len(fitted_inliers))
    return (line, fitted_inliers), quality


def _d7_multiband_recovery(
    image: np.ndarray,
    p1_target: tuple[float, float],
    p2_target: tuple[float, float],
    polarities: tuple[float, float],
    d7_config: dict[str, Any],
) -> tuple[tuple[tuple[float, float], tuple[float, float]] | None, dict[str, Any]]:
    """Recover two boundaries from independently fitted parallel scan bands."""
    dx, dy = p2_target[0] - p1_target[0], p2_target[1] - p1_target[1]
    length = math.hypot(dx, dy)
    if length < 5.0:
        return None, {
            "candidate_recovery_pass": "multi_parallel_bands",
            "candidate_multiband_failure": "axis_degenerate",
            "candidate_multiband_bands": [],
        }
    axis = (dx / length, dy / length)
    tangent = (-axis[1], axis[0])
    bands: list[dict[str, Any]] = []
    side_candidates: dict[str, list[dict[str, Any]]] = {"p1": [], "p2": []}
    for band_offset in [float(value) for value in d7_config["band_offsets_target_px"]]:
        shift = (band_offset * tangent[0], band_offset * tangent[1])
        first_origin = (p1_target[0] + shift[0], p1_target[1] + shift[1])
        second_origin = (p2_target[0] + shift[0], p2_target[1] + shift[1])
        first_diagnostic: dict[str, Any] = {}
        second_diagnostic: dict[str, Any] = {}
        first = detect_dimension_boundary(
            image, first_origin, second_origin, "p1", polarity=polarities[0],
            strip_half_width=int(d7_config["band_strip_half_width_px"]),
            strip_samples=int(d7_config["band_strip_samples"]),
            min_edge_score=float(d7_config["min_edge_score"]),
            min_points=int(d7_config["min_boundary_points"]),
            diagnostics=first_diagnostic,
        )
        second = detect_dimension_boundary(
            image, first_origin, second_origin, "p2", polarity=polarities[1],
            strip_half_width=int(d7_config["band_strip_half_width_px"]),
            strip_samples=int(d7_config["band_strip_samples"]),
            min_edge_score=float(d7_config["min_edge_score"]),
            min_points=int(d7_config["min_boundary_points"]),
            diagnostics=second_diagnostic,
        )
        band: dict[str, Any] = {
            "offsetTargetPx": band_offset,
            "p1Strip": first_diagnostic,
            "p2Strip": second_diagnostic,
            "valid": False,
            "failureReasons": [],
        }
        first_center = None if first is None else line_axis_intersection(
            first.line, p1_target, axis
        )
        second_center = None if second is None else line_axis_intersection(
            second.line, p2_target, axis
        )
        for side_name, boundary, center in (
            ("p1", first, first_center), ("p2", second, second_center)
        ):
            if boundary is None or center is None:
                continue
            side_candidates[side_name].append({
                "bandOffsetTargetPx": band_offset,
                "centerTargetPx": [float(center[0][0]), float(center[0][1])],
                "axisOffsetTargetPx": float(center[1]),
                "line": [float(value) for value in boundary.line],
                "pointCount": int(boundary.point_count),
                "residualTargetPx": float(boundary.median_residual_px),
                "edgePeak": float(boundary.median_edge_score),
                "rawPointsPx": first_diagnostic.get("rawEdgePointsPx", [])
                if side_name == "p1" else second_diagnostic.get("rawEdgePointsPx", []),
                "segmentPointsPx": first_diagnostic.get("fittedSegmentPointsPx", [])
                if side_name == "p1" else second_diagnostic.get("fittedSegmentPointsPx", []),
            })
        if first is None or second is None:
            band["failureReasons"].append("boundary_fit_failed")
            band["failedSides"] = [
                side for side, boundary in (("p1", first), ("p2", second))
                if boundary is None
            ]
            bands.append(band)
            continue
        if first_center is None or second_center is None:
            band["failureReasons"].append("central_axis_intersection_failed")
            bands.append(band)
            continue
        parallelism = boundary_parallelism_deg(first.line, second.line)
        reasons: list[str] = []
        if min(first.point_count, second.point_count) < int(d7_config["min_boundary_points"]):
            reasons.append("boundary_points_below_gate")
        if max(first.median_residual_px, second.median_residual_px) > float(
            d7_config["max_fit_residual_target_px"]
        ):
            reasons.append("fit_residual_above_gate")
        if min(first.median_edge_score, second.median_edge_score) < float(
            d7_config["min_edge_score"]
        ):
            reasons.append("edge_score_below_gate")
        if parallelism > float(d7_config["max_boundary_parallelism_deg"]):
            reasons.append("boundary_parallelism_above_gate")
        center_first, center_second = first_center[0], second_center[0]
        band.update({
            "valid": not reasons,
            "failureReasons": reasons,
            "centerP1TargetPx": [float(center_first[0]), float(center_first[1])],
            "centerP2TargetPx": [float(center_second[0]), float(center_second[1])],
            "lengthTargetPx": float(math.dist(center_first, center_second)),
            "parallelismDeg": float(parallelism),
            "maxResidualTargetPx": float(max(
                first.median_residual_px, second.median_residual_px
            )),
            "minEdgePeak": float(min(first.median_edge_score, second.median_edge_score)),
            "minPointCount": int(min(first.point_count, second.point_count)),
        })
        bands.append(band)

    valid = [band for band in bands if band["valid"]]
    minimum_bands = int(d7_config["min_consistent_bands"])
    quality: dict[str, Any] = {
        "candidate_recovery_pass": "multi_parallel_bands",
        "candidate_multiband_bands": bands,
        "candidate_multiband_valid_count": len(valid),
        "candidate_multiband_inlier_count": 0,
        "candidate_multiband_failure": None,
    }

    def aggregate_independent_sides() -> tuple[
        tuple[tuple[float, float], tuple[float, float]] | None, dict[str, Any]
    ]:
        aggregates: dict[str, dict[str, Any]] = {}
        gate = float(d7_config["max_cross_band_length_deviation_px"])
        for side_name in ("p1", "p2"):
            candidates = side_candidates[side_name]
            quality[f"candidate_multiband_{side_name}_candidate_count"] = len(candidates)
            if len(candidates) < minimum_bands:
                quality["candidate_multiband_failure"] = f"{side_name}_bands_below_gate"
                return None, quality
            median_offset = float(np.median([
                candidate["axisOffsetTargetPx"] for candidate in candidates
            ]))
            inlier_candidates = [
                candidate for candidate in candidates
                if abs(candidate["axisOffsetTargetPx"] - median_offset) <= gate
            ]
            quality[f"candidate_multiband_{side_name}_inlier_count"] = len(inlier_candidates)
            quality[f"candidate_multiband_{side_name}_median_axis_offset_target_px"] = median_offset
            if len(inlier_candidates) < minimum_bands:
                quality["candidate_multiband_failure"] = f"{side_name}_consistency_below_gate"
                return None, quality
            points = np.asarray([
                candidate["centerTargetPx"] for candidate in inlier_candidates
            ], dtype=np.float64)
            representative = min(
                inlier_candidates,
                key=lambda candidate: abs(candidate["axisOffsetTargetPx"] - median_offset),
            )
            aggregates[side_name] = {
                "point": tuple(float(value) for value in np.median(points, axis=0)),
                "line": tuple(representative["line"]),
                "inliers": inlier_candidates,
                "representative": representative,
            }
        parallelism = boundary_parallelism_deg(
            aggregates["p1"]["line"], aggregates["p2"]["line"]
        )
        quality["candidate_multiband_independent_parallelism_deg"] = float(parallelism)
        if parallelism > float(d7_config["max_boundary_parallelism_deg"]):
            quality["candidate_multiband_failure"] = "independent_parallelism_above_gate"
            return None, quality
        all_inliers = aggregates["p1"]["inliers"] + aggregates["p2"]["inliers"]
        quality["candidate_multiband_independent_residual_max_target_px"] = float(max(
            candidate["residualTargetPx"] for candidate in all_inliers
        ))
        quality["candidate_multiband_independent_edge_peak_min"] = float(min(
            candidate["edgePeak"] for candidate in all_inliers
        ))
        quality["candidate_multiband_inlier_count"] = min(
            len(aggregates["p1"]["inliers"]), len(aggregates["p2"]["inliers"])
        )
        quality["candidate_multiband_aggregation"] = "independent_side_median"
        quality["candidate_multiband_failure"] = None
        quality["candidate_boundary_semantics"] = "neck_outer_contour_edges"
        quality["candidate_boundary_evidence_target_px"] = [
            {
                "side": side,
                "rawPointsPx": aggregates[source]["representative"]["rawPointsPx"],
                "segmentPointsPx": aggregates[source]["representative"]["segmentPointsPx"],
                "lineEquation": list(aggregates[source]["line"]),
            }
            for side, source in (("A", "p1"), ("B", "p2"))
        ]
        return (aggregates["p1"]["point"], aggregates["p2"]["point"]), quality

    if len(valid) < minimum_bands:
        quality["candidate_multiband_failure"] = "valid_paired_bands_below_gate"
        return aggregate_independent_sides()
    lengths = np.asarray([band["lengthTargetPx"] for band in valid], dtype=np.float64)
    median_length = float(np.median(lengths))
    deviation_gate = float(d7_config["max_cross_band_length_deviation_px"])
    inliers = [
        band for band in valid
        if abs(float(band["lengthTargetPx"]) - median_length) <= deviation_gate
    ]
    quality["candidate_multiband_median_length_target_px"] = median_length
    quality["candidate_multiband_max_length_deviation_target_px"] = float(
        max(abs(float(band["lengthTargetPx"]) - median_length) for band in valid)
    )
    quality["candidate_multiband_inlier_count"] = len(inliers)
    if len(inliers) < minimum_bands:
        quality["candidate_multiband_failure"] = "consistent_paired_bands_below_gate"
        return aggregate_independent_sides()
    first_points = np.asarray([band["centerP1TargetPx"] for band in inliers], dtype=np.float64)
    second_points = np.asarray([band["centerP2TargetPx"] for band in inliers], dtype=np.float64)
    aggregated_first = tuple(float(value) for value in np.median(first_points, axis=0))
    aggregated_second = tuple(float(value) for value in np.median(second_points, axis=0))
    quality.update({
        "candidate_multiband_aggregation": "paired_band_median",
        "candidate_multiband_parallelism_max_deg": float(max(
            band["parallelismDeg"] for band in inliers
        )),
        "candidate_multiband_residual_max_target_px": float(max(
            band["maxResidualTargetPx"] for band in inliers
        )),
        "candidate_multiband_edge_peak_min": float(min(
            band["minEdgePeak"] for band in inliers
        )),
        "candidate_multiband_length_target_px": float(math.dist(
            aggregated_first, aggregated_second
        )),
    })
    representative_band = min(
        inliers,
        key=lambda band: abs(float(band["lengthTargetPx"]) - median_length),
    )
    quality["candidate_boundary_semantics"] = "neck_outer_contour_edges"
    quality["candidate_boundary_evidence_target_px"] = [
        {
            "side": side,
            "rawPointsPx": representative_band[key].get("rawEdgePointsPx", []),
            "segmentPointsPx": representative_band[key].get("fittedSegmentPointsPx", []),
            "lineEquation": representative_band[key].get("fittedLine"),
        }
        for side, key in (("A", "p1Strip"), ("B", "p2Strip"))
    ]
    return (aggregated_first, aggregated_second), quality


def _shared_parallel_boundary_geometry(
    evidence: list[dict[str, Any]],
) -> tuple[
    tuple[tuple[float, float], tuple[float, float]],
    list[dict[str, Any]],
    dict[str, Any],
] | None:
    """Fit a common line direction and return its exact normal connector.

    The two offsets come only from their respective image-derived point
    clouds.  No nominal dimension or target annotation participates.
    """
    if len(evidence) != 2:
        return None
    point_sets: list[np.ndarray] = []
    normals: list[np.ndarray] = []
    for boundary in evidence:
        points = np.asarray(boundary.get("rawPointsPx", []), dtype=np.float64)
        equation = boundary.get("lineEquation")
        if (
            points.ndim != 2 or points.shape[0] < 2 or points.shape[1] != 2
            or not isinstance(equation, list) or len(equation) != 3
        ):
            return None
        normal = np.asarray(equation[:2], dtype=np.float64)
        norm = float(np.linalg.norm(normal))
        if not math.isfinite(norm) or norm <= 1e-12:
            return None
        normal /= norm
        if normals and float(normal @ normals[0]) < 0.0:
            normal = -normal
        point_sets.append(points)
        normals.append(normal)
    common_normal = normals[0] + normals[1]
    normal_norm = float(np.linalg.norm(common_normal))
    if normal_norm <= 1e-12:
        return None
    common_normal /= normal_norm
    tangent = np.asarray([-common_normal[1], common_normal[0]], dtype=np.float64)
    offsets = [float(np.median(points @ common_normal)) for points in point_sets]
    tangent_coordinate = float(np.median(np.concatenate([
        points @ tangent for points in point_sets
    ])))
    dimension_points = tuple(
        tuple(float(value) for value in offset * common_normal + tangent_coordinate * tangent)
        for offset in offsets
    )
    fitted_boundaries: list[dict[str, Any]] = []
    for boundary, points, offset in zip(evidence, point_sets, offsets):
        projections = points @ tangent
        segment = [
            (offset * common_normal + float(np.min(projections)) * tangent).tolist(),
            (offset * common_normal + float(np.max(projections)) * tangent).tolist(),
        ]
        fitted_boundaries.append({
            **boundary,
            "lineEquation": [
                float(common_normal[0]), float(common_normal[1]), -offset
            ],
            "segmentPointsPx": segment,
        })
    diagnostics = {
        "candidate_boundary_fit_contract": "shared_parallel_direction_from_two_point_clouds",
        "candidate_boundary_common_normal_target": common_normal.tolist(),
        "candidate_boundary_perpendicular_distance_target_px": abs(offsets[0] - offsets[1]),
        "candidate_boundary_nominal_adjustment_applied": False,
    }
    return dimension_points, fitted_boundaries, diagnostics


def _paired_contour_support_window(
    image: np.ndarray,
    p1_target: tuple[float, float],
    p2_target: tuple[float, float],
    endpoint: str,
    outer_polarity: float,
    d7_config: dict[str, Any],
    diagnostics: dict[str, Any],
) -> None:
    """Collect paired-transition midpoints for audit extension efficiently.

    This is the raw-evidence portion of :func:`_paired_contour_boundary` with
    the same search window, smoothing, local-peak, polarity, width, peak and
    prior-score semantics.  Candidate-pair scoring is vectorized because an
    audit extension scans several translated strips.  It never returns a
    business boundary and therefore cannot change D7 measurement geometry.
    """
    diagnostics.update({
        "pairSupport": 0,
        "failureStage": None,
        "layerStabilizationFailure": None,
        "rawContourLocusPointsPx": [],
        "transitionPairsPx": [],
    })
    dx = p2_target[0] - p1_target[0]
    dy = p2_target[1] - p1_target[1]
    length = math.hypot(dx, dy)
    if length < 5.0:
        diagnostics["failureStage"] = "axis_degenerate"
        return
    if abs(float(outer_polarity)) <= 1e-9:
        diagnostics["failureStage"] = "reference_outer_polarity_unavailable"
        return
    axis = np.asarray((dx / length, dy / length), dtype=np.float64)
    tangent = np.asarray((-axis[1], axis[0]), dtype=np.float64)
    origin = np.asarray(
        p1_target if endpoint == "p1" else p2_target, dtype=np.float64
    )
    offsets = np.arange(-42, 43, dtype=np.float64)
    mids = (offsets[:-1] + offsets[1:]) * 0.5
    prior_sigma = float(d7_config["paired_edge_prior_sigma_px"])
    prior = np.exp(-(mids * mids) / (2.0 * prior_sigma * prior_sigma))
    outer_sign = 1.0 if outer_polarity > 0.0 else -1.0
    interior_sign = 1.0 if endpoint == "p1" else -1.0
    minimum_width = float(d7_config["paired_edge_min_width_target_px"])
    maximum_width = float(d7_config["paired_edge_max_width_target_px"])
    minimum_peak = float(d7_config["paired_edge_min_peak"])
    contour_points: list[list[float]] = []
    transition_pairs: list[list[list[float]]] = []
    tangent_coordinates: list[float] = []
    axis_coordinates: list[float] = []

    for tangent_offset in np.linspace(
        -float(d7_config["paired_edge_strip_half_width_px"]),
        float(d7_config["paired_edge_strip_half_width_px"]),
        int(d7_config["paired_edge_strip_samples"]),
    ):
        center = origin + tangent_offset * tangent
        profile = bilinear_sample(
            image, center[0] + offsets * axis[0], center[1] + offsets * axis[1]
        )
        if np.isnan(profile).any():
            continue
        derivative = np.diff(smooth_1d(profile, 7))
        outer_score = derivative * outer_sign
        inner_score = -derivative * outer_sign
        outer_indices = np.flatnonzero(
            (outer_score[1:-1] >= minimum_peak)
            & (outer_score[1:-1] >= outer_score[:-2])
            & (outer_score[1:-1] >= outer_score[2:])
        ) + 1
        inner_indices = np.flatnonzero(
            (inner_score[1:-1] >= minimum_peak)
            & (inner_score[1:-1] >= inner_score[:-2])
            & (inner_score[1:-1] >= inner_score[2:])
        ) + 1
        if outer_indices.size == 0 or inner_indices.size == 0:
            continue
        signed_width = (
            mids[inner_indices][None, :] - mids[outer_indices][:, None]
        ) * interior_sign
        width_valid = (signed_width >= minimum_width) & (
            signed_width <= maximum_width
        )
        if not bool(np.any(width_valid)):
            continue
        scores = np.minimum(
            outer_score[outer_indices][:, None],
            inner_score[inner_indices][None, :],
        ) * np.sqrt(
            prior[outer_indices][:, None] * prior[inner_indices][None, :]
        )
        scores = np.where(width_valid, scores, -np.inf)
        flat_index = int(np.argmax(scores))
        outer_rank, inner_rank = np.unravel_index(flat_index, scores.shape)
        outer_index = int(outer_indices[outer_rank])
        inner_index = int(inner_indices[inner_rank])
        outer_position = float(
            mids[outer_index] + parabolic_peak(outer_score.tolist(), outer_index)
        )
        inner_position = float(
            mids[inner_index] + parabolic_peak(inner_score.tolist(), inner_index)
        )
        center_position = 0.5 * (outer_position + inner_position)
        midpoint = center + center_position * axis
        outer_point = center + outer_position * axis
        inner_point = center + inner_position * axis
        contour_points.append([float(midpoint[0]), float(midpoint[1])])
        transition_pairs.append([
            [float(outer_point[0]), float(outer_point[1])],
            [float(inner_point[0]), float(inner_point[1])],
        ])
        tangent_coordinates.append(float(tangent_offset))
        axis_coordinates.append(float(center_position))

    diagnostics.update({
        "pairSupport": len(contour_points),
        "rawContourLocusPointsPx": contour_points,
        "transitionPairsPx": transition_pairs,
    })
    minimum_support = int(d7_config["paired_edge_min_support"])
    fitted = robust_fit_line(contour_points, min_points=minimum_support)
    if fitted is None:
        diagnostics["failureStage"] = "outer_contour_locus_fit_failed"
        return
    line, inliers = fitted
    axis_cosine = abs(float(line[0]) * axis[0] + float(line[1]) * axis[1])
    residuals = np.abs(line[0] * inliers[:, 0] + line[1] * inliers[:, 1] + line[2])
    median_residual = float(np.median(residuals))
    if (
        axis_cosine < D7_BOUNDARY_MIN_AXIS_COSINE
        or median_residual > float(d7_config["max_fit_residual_target_px"])
    ):
        _, stabilization = _fit_dominant_paired_layer(
            contour_points,
            tangent_coordinates,
            axis_coordinates,
            minimum_support=minimum_support,
            residual_gate=float(d7_config["max_fit_residual_target_px"]),
        )
        diagnostics.update(stabilization)
        if stabilization.get("layerStabilizationFailure") is not None:
            diagnostics["failureStage"] = "paired_layer_ambiguous"


def _extend_d7_paired_support(
    image: np.ndarray,
    p1_target: tuple[float, float],
    p2_target: tuple[float, float],
    polarities: tuple[float, float],
    d7_config: dict[str, Any],
    *,
    outward_direction: tuple[float, float],
    dimension_points: tuple[tuple[float, float], tuple[float, float]],
    evidence: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Extend audit segments with contiguous *paired* straight-neck support.

    The official paired-transition equations and measurement intersections
    are frozen inputs.  Moving strips reuse the existing line-search layout,
    but every added point is still the midpoint of two opposite-polarity
    transitions and must satisfy the unchanged fit-residual gate against the
    frozen line.  A/B must both extend continuously; no point can refit the
    business geometry or upgrade legacy evidence semantics.
    """
    diagnostics: dict[str, Any] = {
        "candidate_boundary_support_extension_attempted": True,
        "candidate_boundary_support_clipping_attempted": True,
        "candidate_boundary_support_extension_contract": (
            "frozen_paired_line_extended_by_contiguous_outward_paired_support"
        ),
        "candidate_boundary_support_extension_complete": False,
        "candidate_boundary_support_sides": [],
    }
    if len(evidence) != 2 or len(dimension_points) != 2:
        diagnostics["candidate_boundary_support_stop_reason"] = "formal_geometry_unavailable"
        return evidence, diagnostics
    outward = np.asarray(outward_direction, dtype=np.float64)
    outward_norm = float(np.linalg.norm(outward))
    if not math.isfinite(outward_norm) or outward_norm <= 1e-12:
        diagnostics["candidate_boundary_support_stop_reason"] = "outward_direction_degenerate"
        return evidence, diagnostics
    outward /= outward_norm

    equations: list[np.ndarray] = []
    for boundary in evidence:
        equation = boundary.get("lineEquation")
        if not isinstance(equation, list) or len(equation) != 3:
            diagnostics["candidate_boundary_support_stop_reason"] = "formal_line_unavailable"
            return evidence, diagnostics
        line = np.asarray(equation, dtype=np.float64)
        normal_norm = float(np.linalg.norm(line[:2]))
        if not np.isfinite(line).all() or normal_norm <= 1e-12:
            diagnostics["candidate_boundary_support_stop_reason"] = "formal_line_invalid"
            return evidence, diagnostics
        equations.append(line / normal_norm)

    primary_boundaries: list[dict[str, Any]] = []
    primary_maxima: list[float] = []
    for index, boundary in enumerate(evidence):
        origin = np.asarray(dimension_points[index], dtype=np.float64)
        line = equations[index]
        raw_points: list[list[float]] = []
        raw_pairs: list[Any] = []
        original_points = boundary.get("rawPointsPx", [])
        original_pairs = boundary.get("transitionPairsPx", [])
        for point_index, point in enumerate(original_points):
            if not isinstance(point, list) or len(point) != 2:
                continue
            point_array = np.asarray(point, dtype=np.float64)
            residual = abs(float(line[:2] @ point_array + line[2]))
            if float((point_array - origin) @ outward) < -1e-6:
                continue
            if residual > float(d7_config["max_fit_residual_target_px"]):
                continue
            raw_points.append([float(point_array[0]), float(point_array[1])])
            if point_index < len(original_pairs):
                raw_pairs.append(original_pairs[point_index])
        if len(raw_points) < 2:
            diagnostics["candidate_boundary_support_stop_reason"] = (
                "outward_primary_paired_support_unavailable"
            )
            primary_boundaries.append({
                **boundary,
                "rawPointsPx": raw_points,
                "transitionPairsPx": raw_pairs,
                "supportPointsPx": [],
                "supportTransitionPairsPx": [],
                "supportEvidenceMode": "paired_transition_midpoints_only",
                "segmentPointsPx": [],
                "supportClippedToNeckDirection": True,
                "supportDirectionTarget": outward.tolist(),
            })
            primary_maxima.append(0.0)
            continue

        points = np.asarray(raw_points, dtype=np.float64)
        signed = points @ line[:2] + line[2]
        projected = points - signed[:, None] * line[:2]
        outward_coordinates = (projected - origin) @ outward
        start = projected[int(np.argmin(outward_coordinates))]
        end = projected[int(np.argmax(outward_coordinates))]
        primary_boundaries.append({
            **boundary,
            "rawPointsPx": raw_points,
            "transitionPairsPx": raw_pairs,
            "supportPointsPx": [],
            "supportTransitionPairsPx": [],
            "supportEvidenceMode": "paired_transition_midpoints_only",
            "segmentPointsPx": [start.tolist(), end.tolist()],
            "supportClippedToNeckDirection": True,
            "supportDirectionTarget": outward.tolist(),
        })
        primary_maxima.append(float(np.max(outward_coordinates)))

    if any(len(boundary.get("segmentPointsPx", [])) != 2 for boundary in primary_boundaries):
        diagnostics["candidate_boundary_support_sides"] = [
            {
                "side": boundary.get("side"),
                "primaryMaxOffsetTargetPx": primary_maxima[index],
                "candidateMaxOffsetTargetPx": None,
                "acceptedMaxOffsetTargetPx": primary_maxima[index],
                "acceptedOffsetsTargetPx": [],
                "pairedPointCount": len(boundary.get("rawPointsPx", [])),
                "extensionPointCount": 0,
                "stopOffsetTargetPx": primary_maxima[index],
                "stopReason": "outward_primary_paired_support_unavailable",
                "windowDiagnostics": [],
            }
            for index, boundary in enumerate(primary_boundaries)
        ]
        diagnostics["candidate_boundary_support_lengths_target_px"] = [
            0.0 if len(boundary.get("segmentPointsPx", [])) != 2
            else float(math.dist(*boundary["segmentPointsPx"]))
            for boundary in primary_boundaries
        ]
        return primary_boundaries, diagnostics

    positive_window_offsets = sorted({
        float(value) for value in d7_config["band_offsets_target_px"]
        if float(value) > 0.0
    })
    if not positive_window_offsets:
        diagnostics["candidate_boundary_support_stop_reason"] = "no_outward_windows"
        return primary_boundaries, diagnostics

    strip_half_width = float(d7_config["paired_edge_strip_half_width_px"])
    strip_samples = int(d7_config["paired_edge_strip_samples"])
    sampling_pitch = (2.0 * strip_half_width) / max(1, strip_samples - 1)
    maximum_continuity_gap = 2.0 * sampling_pitch + 1e-6
    residual_gate = float(d7_config["max_fit_residual_target_px"])
    origins = [np.asarray(point, dtype=np.float64) for point in dimension_points]
    side_candidates: list[dict[int, dict[str, Any]]] = [{}, {}]
    window_diagnostics: list[list[dict[str, Any]]] = [[], []]

    for window_offset in positive_window_offsets:
        shifted = [
            tuple(float(value) for value in (
                np.asarray(point, dtype=np.float64) + window_offset * outward
            ))
            for point in (p1_target, p2_target)
        ]
        for index, endpoint in enumerate(("p1", "p2")):
            window_quality: dict[str, Any] = {}
            _paired_contour_support_window(
                image, shifted[0], shifted[1], endpoint, polarities[index],
                d7_config, window_quality,
            )
            raw_window_points = window_quality.get("rawContourLocusPointsPx", [])
            raw_window_pairs = window_quality.get("transitionPairsPx", [])
            competing_layer = (
                window_quality.get("layerStabilizationFailure")
                == "ambiguous_competing_layers"
            )
            accepted_residuals: list[float] = []
            accepted_tangent: list[float] = []
            for point_index, point in enumerate(raw_window_points):
                if competing_layer or not isinstance(point, list) or len(point) != 2:
                    continue
                point_array = np.asarray(point, dtype=np.float64)
                tangent_coordinate = float((point_array - origins[index]) @ outward)
                if tangent_coordinate <= primary_maxima[index] + 1e-6:
                    continue
                residual = abs(float(
                    equations[index][:2] @ point_array + equations[index][2]
                ))
                if residual > residual_gate:
                    continue
                quantized = int(round(tangent_coordinate / max(sampling_pitch, 1e-6)))
                prior = side_candidates[index].get(quantized)
                transition_pair = (
                    raw_window_pairs[point_index]
                    if point_index < len(raw_window_pairs) else None
                )
                if not (
                    isinstance(transition_pair, list)
                    and len(transition_pair) == 2
                    and all(
                        isinstance(pair_point, list) and len(pair_point) == 2
                        for pair_point in transition_pair
                    )
                ):
                    continue
                candidate = {
                    "point": [float(point_array[0]), float(point_array[1])],
                    "transitionPair": transition_pair,
                    "tangentOffsetTargetPx": tangent_coordinate,
                    "residualTargetPx": residual,
                    "windowOffsetTargetPx": window_offset,
                }
                if prior is None or residual < float(prior["residualTargetPx"]):
                    side_candidates[index][quantized] = candidate
                accepted_residuals.append(residual)
                accepted_tangent.append(tangent_coordinate)
            window_diagnostics[index].append({
                "offsetTargetPx": window_offset,
                "pairSupport": int(window_quality.get("pairSupport", 0)),
                "fitFailureStage": window_quality.get("failureStage"),
                "competingLayerRejected": competing_layer,
                "candidatePointCount": len(raw_window_points),
                "acceptedByFrozenResidualCount": len(accepted_residuals),
                "residualMedianTargetPx": (
                    None if not accepted_residuals
                    else float(np.median(accepted_residuals))
                ),
                "residualMaxTargetPx": (
                    None if not accepted_residuals else float(max(accepted_residuals))
                ),
                "tangentMinimumTargetPx": (
                    None if not accepted_tangent else float(min(accepted_tangent))
                ),
                "tangentMaximumTargetPx": (
                    None if not accepted_tangent else float(max(accepted_tangent))
                ),
            })

    accepted_by_side: list[list[dict[str, Any]]] = []
    side_status: list[dict[str, Any]] = []
    for index, boundary in enumerate(primary_boundaries):
        ordered = sorted(
            side_candidates[index].values(),
            key=lambda candidate: float(candidate["tangentOffsetTargetPx"]),
        )
        contiguous: list[dict[str, Any]] = []
        current_offset = primary_maxima[index]
        stop_offset: float | None = None
        stop_reason = "no_outward_candidate"
        for candidate in ordered:
            tangent_offset = float(candidate["tangentOffsetTargetPx"])
            if tangent_offset - current_offset > maximum_continuity_gap:
                stop_offset = tangent_offset
                stop_reason = "continuity_gap"
                break
            contiguous.append(candidate)
            current_offset = max(current_offset, tangent_offset)
            stop_reason = "continuous_paired_support_complete"
        if len(contiguous) < 2:
            stop_reason = (
                "continuity_gap" if stop_reason == "continuity_gap"
                else "extension_support_below_gate"
            )
        accepted_by_side.append(contiguous)
        side_status.append({
            "side": boundary.get("side"),
            "primaryMaxOffsetTargetPx": primary_maxima[index],
            "candidateMaxOffsetTargetPx": (
                None if not ordered
                else float(max(item["tangentOffsetTargetPx"] for item in ordered))
            ),
            "acceptedMaxOffsetTargetPx": (
                primary_maxima[index] if not contiguous else current_offset
            ),
            "acceptedOffsetsTargetPx": [
                float(item["tangentOffsetTargetPx"]) for item in contiguous
            ],
            "pairedPointCount": len(boundary.get("rawPointsPx", [])),
            "extensionPointCount": len(contiguous),
            "stopOffsetTargetPx": stop_offset,
            "stopReason": stop_reason,
            "samplingPitchTargetPx": sampling_pitch,
            "maximumContinuityGapTargetPx": maximum_continuity_gap - 1e-6,
            "windowDiagnostics": window_diagnostics[index],
        })

    extension_complete = all(len(candidates) >= 2 for candidates in accepted_by_side)
    diagnostics["candidate_boundary_support_extension_complete"] = extension_complete
    diagnostics["candidate_boundary_support_sides"] = side_status
    if not extension_complete:
        diagnostics["candidate_boundary_support_stop_reason"] = (
            "dual_side_continuity_not_met"
            if any(candidates for candidates in accepted_by_side)
            else "dual_side_extension_support_below_gate"
        )
        diagnostics["candidate_boundary_support_lengths_target_px"] = [
            float(math.dist(*boundary["segmentPointsPx"]))
            for boundary in primary_boundaries
        ]
        return primary_boundaries, diagnostics

    updated: list[dict[str, Any]] = []
    for index, boundary in enumerate(primary_boundaries):
        accepted = accepted_by_side[index]
        support_points = [item["point"] for item in accepted]
        support_pairs = [
            item["transitionPair"] for item in accepted
            if item["transitionPair"] is not None
        ]
        all_points = np.asarray(
            boundary["rawPointsPx"] + support_points, dtype=np.float64
        )
        signed = all_points @ equations[index][:2] + equations[index][2]
        projected = all_points - signed[:, None] * equations[index][:2]
        coordinates = (projected - origins[index]) @ outward
        start = projected[int(np.argmin(coordinates))]
        end = projected[int(np.argmax(coordinates))]
        updated.append({
            **boundary,
            "supportPointsPx": support_points,
            "supportTransitionPairsPx": support_pairs,
            "supportEvidenceMode": (
                "paired_transition_midpoints_plus_contiguous_outward_paired_support"
            ),
            "segmentPointsPx": [start.tolist(), end.tolist()],
        })

    diagnostics["candidate_boundary_support_lengths_target_px"] = [
        float(math.dist(*boundary["segmentPointsPx"])) for boundary in updated
    ]
    return updated, diagnostics


def _detect_d7_tangent(
    target: np.ndarray,
    reference: ReferenceModel,
    transform: SimilarityTransform,
    phi_reference_values: dict[str, float],
    config: dict[str, Any],
) -> tuple[dict[str, float] | None, dict[str, Any]]:
    d7_shape = next((item for item in reference.shapes if item.sanitized == "d7"), None)
    phi_shape = next((item for item in reference.shapes if item.sanitized == "Phi12_2"), None)
    if (d7_shape is None or d7_shape.line_p1 is None or d7_shape.line_p2 is None
            or phi_shape is None or phi_shape.circle is None):
        return None, {"candidate_failure": "reference_feature_missing"}

    p1_ref, p2_ref = d7_shape.line_p1, d7_shape.line_p2
    axis_dx, axis_dy = p2_ref[0] - p1_ref[0], p2_ref[1] - p1_ref[1]
    axis_length = math.hypot(axis_dx, axis_dy)
    if axis_length < 5.0:
        return None, {"candidate_failure": "reference_axis_degenerate"}
    axis_ref = (axis_dx / axis_length, axis_dy / axis_length)
    normal_ref = (-axis_ref[1], axis_ref[0])
    midpoint_ref = ((p1_ref[0] + p2_ref[0]) * 0.5,
                    (p1_ref[1] + p2_ref[1]) * 0.5)
    phi_cx_ref, phi_cy_ref, phi_radius_ref = phi_shape.circle
    signed_distance_ref = (
        (midpoint_ref[0] - phi_cx_ref) * normal_ref[0]
        + (midpoint_ref[1] - phi_cy_ref) * normal_ref[1]
    )
    tangent_error_ref = abs(abs(signed_distance_ref) - phi_radius_ref)
    d7_config = config["d7"]
    if tangent_error_ref > float(d7_config["max_reference_tangent_error_px"]):
        return None, {
            "candidate_failure": "reference_d7_not_tangent_to_phi12_2",
            "candidate_reference_tangent_error_px": tangent_error_ref,
        }
    side = 1.0 if signed_distance_ref >= 0.0 else -1.0

    theta = transform.theta_rad
    c, s = math.cos(theta), math.sin(theta)
    normal_target = (
        c * normal_ref[0] - s * normal_ref[1],
        s * normal_ref[0] + c * normal_ref[1],
    )
    phi_target_center = transform.forward(
        phi_reference_values["Phi12_2_cx"], phi_reference_values["Phi12_2_cy"]
    )
    phi_target_radius = transform.scale * phi_reference_values["Phi12_2_r"]
    tangent_target = (
        phi_target_center[0] + side * phi_target_radius * normal_target[0],
        phi_target_center[1] + side * phi_target_radius * normal_target[1],
    )
    p1_target = transform.forward(*p1_ref)
    p2_target = transform.forward(*p2_ref)
    midpoint_target = ((p1_target[0] + p2_target[0]) * 0.5,
                       (p1_target[1] + p2_target[1]) * 0.5)
    axis_shift = (
        (tangent_target[0] - midpoint_target[0]) * normal_target[0]
        + (tangent_target[1] - midpoint_target[1]) * normal_target[1]
    )
    if abs(axis_shift) > float(d7_config["max_axis_shift_target_px"]):
        return None, {
            "candidate_failure": "tangent_axis_shift_above_gate",
            "candidate_reference_tangent_error_px": tangent_error_ref,
            "candidate_axis_shift_target_px": axis_shift,
        }
    p1_shifted = (p1_target[0] + axis_shift * normal_target[0],
                  p1_target[1] + axis_shift * normal_target[1])
    p2_shifted = (p2_target[0] + axis_shift * normal_target[0],
                  p2_target[1] + axis_shift * normal_target[1])
    polarities = d7_shape.endpoint_polarities or (0.0, 0.0)
    image = contrast_stretch(target)
    first_diagnostic: dict[str, Any] = {}
    second_diagnostic: dict[str, Any] = {}
    first = _paired_contour_boundary(
        image, p1_shifted, p2_shifted, "p1", polarities[0],
        d7_config, first_diagnostic,
    )
    second = _paired_contour_boundary(
        image, p1_shifted, p2_shifted, "p2", polarities[1],
        d7_config, second_diagnostic,
    )

    def recover_multiband(
        primary_quality: dict[str, Any],
    ) -> tuple[dict[str, float] | None, dict[str, Any]]:
        recovered, recovery_quality = _d7_multiband_recovery(
            image, p1_shifted, p2_shifted, polarities, d7_config
        )
        combined = {**primary_quality, **recovery_quality}
        combined["candidate_primary_failed_sides"] = list(
            combined.get("candidate_failed_sides", [])
        )
        combined["candidate_multiband_diagnostic_pass"] = recovered is not None
        combined["candidate_multiband_semantics_rejected"] = recovered is not None
        combined["candidate_multiband_semantics_rejection_reason"] = (
            "single_gradient_edge_is_not_paired_transition_contour_locus"
            if recovered is not None else None
        )
        # This legacy recovery selects one strongest gradient per profile.  It
        # remains useful diagnostics, but the 030 manual audit proved that it
        # can consistently select a neighbouring optical layer while every
        # numerical gate passes.  It therefore cannot directly produce the
        # current-capture D7.  The separately computed v6 result may still be
        # returned only through its own original dual-boundary quality gate;
        # such a value is explicitly marked as having unavailable new-style
        # boundary evidence.
        combined["candidate_semantic_fallback_allowed"] = True
        combined["candidate_recovery_pass"] = None
        if recovered is not None:
            combined["candidate_multiband_failure"] = "boundary_semantics_mismatch"
        return None, combined

    if first is None or second is None:
        failed_sides = [
            side for side, boundary in (("p1", first), ("p2", second))
            if boundary is None
        ]
        return recover_multiband({
            "candidate_failure": "tangent_boundary_fit_failed",
            "candidate_boundary_semantics": "neck_outer_contour_edges",
            "candidate_reference_tangent_error_px": tangent_error_ref,
            "candidate_axis_shift_target_px": axis_shift,
            "candidate_failed_sides": failed_sides,
            "candidate_p1_strip": first_diagnostic,
            "candidate_p2_strip": second_diagnostic,
        })
    parallelism = boundary_parallelism_deg(first.line, second.line)
    reasons: list[str] = []
    if min(first.point_count, second.point_count) < int(d7_config["min_boundary_points"]):
        reasons.append("boundary_points_below_gate")
    if max(first.median_residual_px, second.median_residual_px) > float(d7_config["max_fit_residual_target_px"]):
        reasons.append("fit_residual_above_gate")
    if min(first.median_edge_score, second.median_edge_score) < float(d7_config["min_edge_score"]):
        reasons.append("edge_score_below_gate")
    if parallelism > float(d7_config["max_boundary_parallelism_deg"]):
        reasons.append("boundary_parallelism_above_gate")
    quality = {
        "candidate_failure": None if not reasons else ",".join(reasons),
        "candidate_recovery_pass": (
            "paired_transition_layer_stabilization"
            if first_diagnostic.get("layerStabilizationUsed")
            or second_diagnostic.get("layerStabilizationUsed")
            else None
        ),
        "candidate_layer_stabilized_sides": [
            side_name
            for side_name, side_diagnostic in (
                ("p1", first_diagnostic), ("p2", second_diagnostic)
            )
            if side_diagnostic.get("layerStabilizationUsed")
        ],
        "candidate_boundary_semantics": "neck_outer_contour_edges",
        "candidate_reference_tangent_error_px": tangent_error_ref,
        "candidate_axis_shift_target_px": axis_shift,
        "candidate_p1_edge_points": float(first.point_count),
        "candidate_p2_edge_points": float(second.point_count),
        "candidate_p1_fit_residual_target_px": float(first.median_residual_px),
        "candidate_p2_fit_residual_target_px": float(second.median_residual_px),
        "candidate_p1_edge_score": float(first.median_edge_score),
        "candidate_p2_edge_score": float(second.median_edge_score),
        "candidate_boundary_parallelism_deg": float(parallelism),
        "candidate_failed_sides": [],
        "candidate_p1_strip": first_diagnostic,
        "candidate_p2_strip": second_diagnostic,
        "candidate_p1_pair_support": int(first_diagnostic["pairSupport"]),
        "candidate_p2_pair_support": int(second_diagnostic["pairSupport"]),
        "candidate_p1_outer_peak": first_diagnostic["outerPeakMedian"],
        "candidate_p2_outer_peak": second_diagnostic["outerPeakMedian"],
        "candidate_p1_inner_peak": first_diagnostic["innerPeakMedian"],
        "candidate_p2_inner_peak": second_diagnostic["innerPeakMedian"],
        "candidate_p1_pair_width_target_px": first_diagnostic["pairWidthMedianPx"],
        "candidate_p2_pair_width_target_px": second_diagnostic["pairWidthMedianPx"],
        "candidate_boundary_evidence_target_px": [
            {
                "side": "A",
                "rawPointsPx": first_diagnostic.get("rawContourLocusPointsPx", []),
                "transitionPairsPx": first_diagnostic.get("transitionPairsPx", []),
                "segmentPointsPx": first_diagnostic.get("fittedSegmentPointsPx", []),
                "lineEquation": first_diagnostic.get("fittedLine"),
            },
            {
                "side": "B",
                "rawPointsPx": second_diagnostic.get("rawContourLocusPointsPx", []),
                "transitionPairsPx": second_diagnostic.get("transitionPairsPx", []),
                "segmentPointsPx": second_diagnostic.get("fittedSegmentPointsPx", []),
                "lineEquation": second_diagnostic.get("fittedLine"),
            },
        ],
    }
    if reasons:
        return recover_multiband(quality)
    first_point, second_point = first.feature_point, second.feature_point
    shared = _shared_parallel_boundary_geometry(
        quality["candidate_boundary_evidence_target_px"]
    )
    if shared is not None:
        (first_point, second_point), shared_evidence, shared_quality = shared
        outward = (side * normal_target[0], side * normal_target[1])
        shared_evidence, extension_quality = _extend_d7_paired_support(
            image, p1_shifted, p2_shifted, polarities, d7_config,
            outward_direction=outward,
            dimension_points=(first_point, second_point),
            evidence=shared_evidence,
        )
        quality["candidate_boundary_evidence_target_px"] = shared_evidence
        quality.update(shared_quality)
        quality.update(extension_quality)
    ref_first = transform.inverse(*first_point)
    ref_second = transform.inverse(*second_point)
    return {
        "d7_x1": ref_first[0], "d7_y1": ref_first[1],
        "d7_x2": ref_second[0], "d7_y2": ref_second[1],
        "d7_length": math.dist(ref_first, ref_second),
    }, quality


def _replay_v6_d7_review_evidence(
    target: np.ndarray,
    reference: ReferenceModel,
    extraction: Extraction,
    v6_measurements: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Replay the frozen v6 boundary calls for review-only line evidence.

    The replay is exposed only when both detected intersections reproduce the
    official v6 business coordinates after the same extraction transform.
    These single-gradient lines are not promoted to the paired-transition
    physical-boundary contract and therefore cannot complete evidence audit.
    """
    diagnostics: dict[str, Any] = {
        "legacyReplayAttempted": True,
        "legacyReplayMatchesMeasurement": False,
        "legacyReplayFailure": None,
    }
    shape = next((item for item in reference.shapes if item.sanitized == "d7"), None)
    keys = ("d7_x1", "d7_y1", "d7_x2", "d7_y2", "d7_length")
    if (
        shape is None or shape.line_p1 is None or shape.line_p2 is None
        or not _finite_values(v6_measurements, list(keys))
    ):
        diagnostics["legacyReplayFailure"] = "v6_measurement_or_reference_unavailable"
        return [], diagnostics
    transform = SimilarityTransform(
        float(extraction.transform_dx), float(extraction.transform_dy),
        float(extraction.transform_scale), float(extraction.transform_theta_deg),
    )
    p1_target = transform.forward(*shape.line_p1)
    p2_target = transform.forward(*shape.line_p2)
    polarities = shape.endpoint_polarities or (0.0, 0.0)
    stretched = contrast_stretch(target)
    strip_diagnostics: list[dict[str, Any]] = [{}, {}]
    detections = [
        detect_dimension_boundary(
            stretched, p1_target, p2_target, "p1", polarity=polarities[0],
            diagnostics=strip_diagnostics[0],
        ),
        detect_dimension_boundary(
            stretched, p1_target, p2_target, "p2", polarity=polarities[1],
            diagnostics=strip_diagnostics[1],
        ),
    ]
    if any(item is None for item in detections):
        diagnostics["legacyReplayFailure"] = "boundary_replay_failed"
        diagnostics["legacyReplayStrips"] = strip_diagnostics
        return [], diagnostics
    expected = [
        transform.forward(float(v6_measurements["d7_x1"]), float(v6_measurements["d7_y1"])),
        transform.forward(float(v6_measurements["d7_x2"]), float(v6_measurements["d7_y2"])),
    ]
    actual = [item.feature_point for item in detections if item is not None]
    if any(
        not (
            math.isclose(actual_point[0], expected_point[0], rel_tol=1e-9, abs_tol=1e-6)
            and math.isclose(actual_point[1], expected_point[1], rel_tol=1e-9, abs_tol=1e-6)
        )
        for actual_point, expected_point in zip(actual, expected)
    ):
        diagnostics["legacyReplayFailure"] = "measurement_intersection_mismatch"
        diagnostics["legacyReplayExpectedIntersectionsTargetPx"] = expected
        diagnostics["legacyReplayActualIntersectionsTargetPx"] = actual
        return [], diagnostics

    review: list[dict[str, Any]] = []
    for side_name, strip in zip(("A", "B"), strip_diagnostics):
        review.append({
            "side": side_name,
            "semantics": "legacy_single_gradient_boundary",
            "rawPointsPx": strip.get("rawEdgePointsPx", []),
            "inlierPointsPx": strip.get("inlierEdgePointsPx", []),
            "lineEquation": strip.get("fittedLine"),
            "segmentPointsPx": strip.get("fittedSegmentPointsPx", []),
            "reviewOnly": True,
            "equivalentToFormalBoundary": False,
            "replayMatchesMeasurement": True,
        })
    diagnostics.update({
        "legacyReplayMatchesMeasurement": True,
        "legacyReplayExpectedIntersectionsTargetPx": expected,
        "legacyReplayActualIntersectionsTargetPx": actual,
        "legacyReplayStrips": strip_diagnostics,
    })
    return review, diagnostics


def _v6_d7_fallback(
    v6_measurements: dict[str, Any],
    candidate_quality: dict[str, Any],
    legacy_review_evidence: list[dict[str, Any]] | None = None,
) -> tuple[dict[str, float] | None, dict[str, Any]]:
    """Return the untouched v6 d7 only when its original detector passed.

    ``ok:dual_boundary_fit`` is emitted by v6 only after both boundary calls
    pass their original point-count, edge-score, residual and axis gates.  We
    additionally require all five legacy business values to be finite.  No
    current-capture threshold is substituted for that original decision.
    """
    quality = dict(candidate_quality)
    quality["candidate_fallback_pass"] = None
    quality["candidate_fallback_failure"] = None
    quality.pop("candidate_boundary_evidence_target_px", None)
    quality["candidate_boundary_evidence_status"] = "unavailable_v6_original_quality_fallback"
    keys = ("d7_x1", "d7_y1", "d7_x2", "d7_y2", "d7_length")
    original_valid = (
        v6_measurements.get("d7.quality.upstream") == "ok:dual_boundary_fit"
        and _finite_values(v6_measurements, list(keys))
    )
    if not original_valid:
        quality["candidate_fallback_failure"] = "v6_original_quality_rejected"
        return None, quality
    quality["candidate_fallback_pass"] = "v6_original_quality"
    if legacy_review_evidence:
        quality["candidate_legacy_boundary_review_target_px"] = legacy_review_evidence
    return {key: float(v6_measurements[key]) for key in keys}, quality


def sanitize_json_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): sanitize_json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [sanitize_json_value(item) for item in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        number = float(value)
        return number if math.isfinite(number) else None
    return value


def _assert_no_nonfinite(value: Any, path: str = "result") -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            _assert_no_nonfinite(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _assert_no_nonfinite(item, f"{path}[{index}]")
    elif isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"non-finite number at {path}")


def validate_result_contract(result: dict[str, Any]) -> None:
    required = {
        "schemaVersion", "algorithmVersion", "configVersion", "runtimeInputs",
        "registration", "features", "referenceMeasurements", "timingMs", "evidenceScope",
        "qualityStatus", "geometryConsistency", "authoritativeReference",
    }
    missing = sorted(required - result.keys())
    if missing:
        raise ValueError("result missing required fields: " + ",".join(missing))
    if result["schemaVersion"] != RESULT_SCHEMA_VERSION:
        raise ValueError("unsupported result schemaVersion")
    roles = [item.get("role") for item in result["runtimeInputs"]]
    expected_roles = [
        "authoritative_reference_annotation", "authoritative_reference_image",
        "target_image", "configuration",
    ]
    if sorted(roles) != sorted(expected_roles) or len(roles) != 4:
        raise ValueError("runtime inputs must contain only the authoritative reference, target, and configuration")
    for item in result["runtimeInputs"]:
        digest = item.get("sha256")
        if (not isinstance(item.get("path"), str) or not isinstance(digest, str)
                or len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest)):
            raise ValueError("each runtime input requires a path and lowercase SHA-256")
    registration_required = {
        "registrationValid", "failureReason", "candidates", "selected", "transform",
        "primaryFailureReason", "registrationRecoveryPass",
        "inverseTransform", "transformDirection", "inverseTransformDirection",
        "referenceImageSize", "targetImageSize",
    }
    if not isinstance(result["registration"], dict) or not registration_required <= result["registration"].keys():
        raise ValueError("registration object is incomplete")
    registration = result["registration"]
    if registration["transformDirection"] != "reference_px_to_target_px":
        raise ValueError("registration transformDirection is invalid")
    if registration["inverseTransformDirection"] != "target_px_to_reference_px":
        raise ValueError("registration inverseTransformDirection is invalid")
    if registration["registrationValid"]:
        if registration["transform"] is None or registration["inverseTransform"] is None:
            raise ValueError("valid registration requires forward and inverse transforms")
    elif registration["transform"] is not None or registration["inverseTransform"] is not None:
        raise ValueError("invalid registration must not expose final transforms")
    authoritative_reference = result["authoritativeReference"]
    reference_required = {
        "referenceVersion", "templateSelfCheck", "transformDirection", "transform",
        "annotationShapeSummary", "registrationEvidenceSource",
    }
    if not isinstance(authoritative_reference, dict) or not reference_required <= authoritative_reference.keys():
        raise ValueError("authoritativeReference object is incomplete")
    if authoritative_reference["referenceVersion"] != AUTHORITATIVE_REFERENCE_VERSION:
        raise ValueError("authoritativeReference referenceVersion is invalid")
    if authoritative_reference["transformDirection"] != "authoritative_reference_px_to_target_px":
        raise ValueError("authoritativeReference transformDirection is invalid")
    if authoritative_reference["registrationEvidenceSource"] != "authoritative_reference_image_pixels":
        raise ValueError("registration must use authoritative reference image pixels")
    if registration["registrationValid"] and not isinstance(authoritative_reference["transform"], dict):
        raise ValueError("valid registration requires authoritative reference transform")
    if not registration["registrationValid"] and authoritative_reference["transform"] is not None:
        raise ValueError("invalid registration cannot expose authoritative reference transform")
    role_map = {item["role"]: item for item in result["runtimeInputs"]}
    if role_map["authoritative_reference_annotation"]["sha256"] != AUTHORITATIVE_REFERENCE_ANNOTATION_SHA256:
        raise ValueError("runtime authoritative annotation SHA-256 is not frozen")
    if role_map["authoritative_reference_image"]["sha256"] != AUTHORITATIVE_REFERENCE_IMAGE_SHA256:
        raise ValueError("runtime authoritative image SHA-256 is not frozen")
    if set(result["features"]) != {"7", "Phi12.2"}:
        raise ValueError("features must contain exactly 7 and Phi12.2")
    feature_required = {
        "featureCode", "measurementValid", "qualityStatus", "failureReason", "sourceDetector",
        "recoveryPass", "reference", "target", "quality", "evidenceComplete",
        "evidenceAuditStatus", "evidenceAuditReason",
    }
    for name, feature in result["features"].items():
        if not isinstance(feature, dict) or not feature_required <= feature.keys():
            raise ValueError(f"feature {name} is incomplete")
        expected_status = "valid" if feature["measurementValid"] else "invalid"
        if feature["qualityStatus"] != expected_status:
            raise ValueError(f"feature {name} qualityStatus conflicts with measurementValid")
        audit_status = feature["evidenceAuditStatus"]
        if audit_status not in {"complete", "partial", "unavailable", "not_applicable"}:
            raise ValueError(f"feature {name} evidenceAuditStatus is invalid")
        if bool(feature["evidenceComplete"]) != (audit_status == "complete"):
            raise ValueError(f"feature {name} evidenceComplete conflicts with audit status")
        if not feature["measurementValid"] and audit_status != "not_applicable":
            raise ValueError(f"feature {name} invalid measurement requires not_applicable evidence")
        if feature["measurementValid"] and audit_status == "not_applicable":
            raise ValueError(f"feature {name} valid measurement requires evidence audit")
        if not feature["measurementValid"] and (feature["reference"] is not None or feature["target"] is not None):
            raise ValueError(f"feature {name} invalid result must not contain finite geometry")
    status = result["qualityStatus"]
    if not isinstance(status, dict) or not {
        "technicalValid", "state", "failureReasons", "productionDisposition"
    } <= status.keys():
        raise ValueError("qualityStatus is incomplete")
    expected_technical = bool(result["registration"]["registrationValid"]) and all(
        bool(feature["measurementValid"]) for feature in result["features"].values()
    )
    if bool(status["technicalValid"]) != expected_technical:
        raise ValueError("qualityStatus.technicalValid conflicts with registration/features")
    geometry = result["geometryConsistency"]
    geometry_required = {
        "evaluated", "outlier", "rejected", "failureReason", "outlierReason",
        "ratioSource", "decision", "corroboratingEvidence",
        "hardRejectionPolicy", "outputAdjustmentApplied",
    }
    if not isinstance(geometry, dict) or not geometry_required <= geometry.keys():
        raise ValueError("geometryConsistency object is incomplete")
    if geometry["rejected"] and not geometry["outlier"]:
        raise ValueError("geometryConsistency cannot reject a non-outlier")
    if geometry["rejected"] and not geometry["corroboratingEvidence"]:
        raise ValueError("geometryConsistency rejection requires corroborating evidence")
    if status["productionDisposition"] != "not_evaluated":
        raise ValueError("productionDisposition must remain not_evaluated")
    if not isinstance(result["timingMs"], dict) or float(result["timingMs"].get("total", -1)) < 0:
        raise ValueError("timingMs.total must be non-negative")
    if result["evidenceScope"] != EVIDENCE_SCOPE:
        raise ValueError("invalid evidenceScope")
    _assert_no_nonfinite(result)


def run_current_capture(
    authoritative_reference_annotation_path: Path,
    authoritative_reference_image_path: Path,
    target_image_path: Path,
    config_path: Path,
) -> dict[str, Any]:
    started = time.perf_counter()
    config = load_registration_config(config_path)
    measurement_reference = load_authoritative_reference(
        authoritative_reference_annotation_path, authoritative_reference_image_path
    )
    registration_model = _derive_image_registration_model(
        measurement_reference, config
    )
    target = load_gray(target_image_path)
    reference_image_sha = sha256_file(authoritative_reference_image_path)
    target_image_sha = sha256_file(target_image_path)
    template_self_check = target_image_sha == reference_image_sha
    registration_started = time.perf_counter()
    if template_self_check:
        registration = _identity_self_registration(
            measurement_reference, target
        )
    else:
        # The current end-face station has a fixed camera/part orientation.
        # Keep scale/translation/fine-angle estimation, but do not invite
        # orthogonal false matches from visually repeated circular structures.
        direct_reference_config = {**config, "orientations_deg": [0]}
        registration = register_current_capture(
            registration_model, target, direct_reference_config
        )
    registration_ms = (time.perf_counter() - registration_started) * 1000.0
    extraction_ms = 0.0
    errors: list[str] = []
    raw_measurements: dict[str, Any] = {}
    compatible: dict[str, Any] = {}
    if not registration["registrationValid"]:
        features = _invalid_features("registration_invalid:" + str(registration["failureReason"]))
        geometry_consistency = {
            "evaluated": False, "outlier": False, "rejected": False,
            "failureReason": "registration_invalid",
            "outlierReason": None,
            "ratioSource": "authoritative_manual_reference_geometry",
            "decision": "not_evaluated",
            "corroboratingEvidence": [],
            "hardRejectionPolicy": "ratio_outlier_requires_independent_risk_evidence",
            "outputAdjustmentApplied": False,
        }
    else:
        transform = _transform_from_registration(registration)
        extraction_started = time.perf_counter()
        extraction: Extraction = extract_image(
            target_image_path, measurement_reference, allow_rotation=True,
            expand_anchors=False,
            initial_transform=(transform.dx, transform.dy, transform.scale, transform.theta_rad),
            refine_initial_transform=False,
        )
        extraction_ms = (time.perf_counter() - extraction_started) * 1000.0
        raw_measurements = dict(extraction.measurements)
        measurements = dict(raw_measurements)
        phi_values, phi_quality = _detect_phi12_2(
            target, measurement_reference, transform, config,
            exact_template_angle_domain=True,
        )
        for key, value in phi_quality.items():
            measurements[f"Phi12_2.quality.{key}"] = value
        phi_source = "hole2-v6-current-capture-candidate"
        if phi_quality.get("candidate_phase_fallback") == "legacy_magnitude_quality_fallback":
            phi_source = "hole2-v6-current-capture-legacy-magnitude-quality-fallback"
        elif phi_quality.get("candidate_polarity_enforced") is True:
            phi_source = "hole2-v6-current-capture-reference-arc-with-opposite-arc-audit"
        d7_source = "hole2-v6-current-capture-paired-transition-outer-contour-lines"
        if phi_values is not None:
            measurements.update(phi_values)
            d7_values, d7_quality = _detect_d7_tangent(
                target, measurement_reference, transform, phi_values, config
            )
            if (
                d7_values is not None
                and d7_quality.get("candidate_recovery_pass") == "multi_parallel_bands"
            ):
                d7_source = "hole2-v6-current-capture-multi-parallel-bands"
            if d7_values is None:
                legacy_review, legacy_review_quality = _replay_v6_d7_review_evidence(
                    target, measurement_reference, extraction, raw_measurements
                )
                d7_quality["candidate_legacy_boundary_review_diagnostics"] = (
                    legacy_review_quality
                )
                d7_values, d7_quality = _v6_d7_fallback(
                    raw_measurements, d7_quality, legacy_review
                )
                if d7_values is not None:
                    d7_source = "hole2-v6-original-quality-fallback"
            for key, value in d7_quality.items():
                measurements[f"d7.quality.{key}"] = value
            if d7_values is None:
                for key in ("d7_x1", "d7_y1", "d7_x2", "d7_y2", "d7_length"):
                    measurements[key] = float("nan")
            else:
                measurements.update(d7_values)
        else:
            # Never silently promote a legacy v6 arc that failed the independent
            # current-capture candidate gates.
            for key in ("Phi12_2_cx", "Phi12_2_cy", "Phi12_2_r", "Phi12_2_diameter_px"):
                measurements[key] = float("nan")
            for key in ("d7_x1", "d7_y1", "d7_x2", "d7_y2", "d7_length"):
                measurements[key] = float("nan")
            measurements["d7.quality.candidate_failure"] = "upstream_phi12_2_candidate_invalid"
        shape = next((
            item for item in measurement_reference.shapes
            if item.sanitized == "Phi12_2"
        ), None)
        phi_angles = [] if shape is None or shape.template_angles is None else shape.template_angles
        features, compatible = build_feature_outputs(
            measurements, transform, phi_angles,
            phi_source_detector=phi_source,
            d7_source_detector=d7_source,
        )
        geometry_consistency = evaluate_geometry_consistency(
            features, measurement_reference, config, registration=registration
        )

    runtime_inputs = [
        {"role": "authoritative_reference_annotation", "path": str(authoritative_reference_annotation_path), "sha256": sha256_file(authoritative_reference_annotation_path)},
        {"role": "authoritative_reference_image", "path": str(authoritative_reference_image_path), "sha256": reference_image_sha},
        {"role": "target_image", "path": str(target_image_path), "sha256": target_image_sha},
        {"role": "configuration", "path": str(config_path), "sha256": sha256_file(config_path)},
    ]
    measurement_transform = None
    if registration["registrationValid"]:
        measurement_transform = transform.as_dict()
    authoritative_reference = {
        "referenceVersion": AUTHORITATIVE_REFERENCE_VERSION,
        "templateSelfCheck": template_self_check,
        "transformDirection": "authoritative_reference_px_to_target_px",
        "transform": measurement_transform,
        "registrationEvidenceSource": "authoritative_reference_image_pixels",
        "annotationShapeSummary": {
            "7": {"shapeType": "line", "pointCount": 2},
            "Phi12.2": {"shapeType": "linestrip", "pointCount": 80},
        },
    }
    quality_failures: list[str] = []
    if not registration["registrationValid"]:
        quality_failures.append("registration:" + str(registration["failureReason"]))
    for feature_name, feature in features.items():
        if not feature["measurementValid"]:
            quality_failures.append(
                f"feature:{feature_name}:" + str(feature["failureReason"])
            )
    if not registration["registrationValid"]:
        quality_state = "registration_invalid"
    elif quality_failures:
        quality_state = "measurement_invalid"
    else:
        quality_state = "complete"
    quality_status = {
        "technicalValid": not quality_failures,
        "state": quality_state,
        "failureReasons": quality_failures,
        "productionDisposition": "not_evaluated",
    }
    total_ms = (time.perf_counter() - started) * 1000.0
    result = sanitize_json_value({
        "schemaVersion": RESULT_SCHEMA_VERSION,
        "algorithmVersion": ALGORITHM_VERSION,
        "configVersion": config["config_version"],
        "runtimeInputs": runtime_inputs,
        "authoritativeReference": authoritative_reference,
        "registration": registration,
        "features": features,
        "qualityStatus": quality_status,
        "geometryConsistency": geometry_consistency,
        "referenceMeasurements": compatible,
        "v6Measurements": raw_measurements,
        "timingMs": {
            "registration": registration_ms,
            "extraction": extraction_ms,
            "total": total_ms,
        },
        "evidenceScope": EVIDENCE_SCOPE,
        "errors": errors,
    })
    validate_result_contract(result)
    return result


def write_result(path: Path, result: dict[str, Any]) -> None:
    validate_result_contract(result)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
