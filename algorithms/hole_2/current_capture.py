"""Current-capture pose registration adapter for the existing hole-2 v6 core.

The runtime API deliberately has no target-annotation argument.  It derives a
pose from the old reference annotation and the target pixels, gates the pose
with spatially distributed edge supports, then delegates measurements to v6.
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


ALGORITHM_VERSION = "hole2-current-capture-registration/3"
RESULT_SCHEMA_VERSION = "hole2-current-capture-result/1"
EVIDENCE_SCOPE = "single_image_pixel_geometry_only_not_repeatability_mm_accuracy_or_production_ok_ng"


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


def register_current_capture(
    reference: ReferenceModel,
    target_gray: np.ndarray,
    config: dict[str, Any],
) -> dict[str, Any]:
    """Register one target using old-reference geometry only."""
    groups = _cluster_supports(
        reference, float(config["supports"]["reference_cluster_distance_px"])
    )
    primary = _primary_group(groups)
    hypotheses = _coarse_hypotheses(target_gray, primary, config)
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
    best = valid[0]
    margin = None if len(valid) == 1 else float(best["score"] - valid[1]["score"])
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

    d7_keys = ["d7_x1", "d7_y1", "d7_x2", "d7_y2", "d7_length"]
    if _finite_values(measurements, d7_keys):
        reference_points = [
            [float(measurements["d7_x1"]), float(measurements["d7_y1"])],
            [float(measurements["d7_x2"]), float(measurements["d7_y2"])],
        ]
        target_points = [list(transform.forward(*point)) for point in reference_points]
        d7_reference = {"coordinateSystem": "reference_px", "pointsPx": reference_points,
                        "lengthPx": float(measurements["d7_length"])}
        d7_target = {"coordinateSystem": "target_px", "pointsPx": target_points,
                     "lengthPx": float(math.dist(target_points[0], target_points[1]))}
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
            "coordinateSystem": "reference_px", "centerPx": [cx, cy],
            "radiusPx": radius, "diameterPx": 2.0 * radius,
            "supportPointsPx": support_reference,
        }
        phi_target = {
            "coordinateSystem": "target_px", "centerPx": list(target_center),
            "radiusPx": transform.scale * radius,
            "diameterPx": 2.0 * transform.scale * radius,
            "supportPointsPx": support_target,
        }
        phi_valid, phi_reason = True, None
    else:
        phi_reference = phi_target = None
        phi_valid = False
        phi_reason = str(measurements.get("Phi12_2.quality.candidate_failure", "detector_invalid"))

    d7_quality = _quality_subset(measurements, "d7")
    phi_quality = _quality_subset(measurements, "Phi12_2")
    d7_recovery_pass = (
        d7_quality.get("candidate_fallback_pass")
        or d7_quality.get("candidate_recovery_pass")
    )
    phi_recovery_pass = phi_quality.get("candidate_recovery_pass")
    features = {
        "7": {
            "featureCode": "HOLE2-DIM-7", "measurementValid": d7_valid,
            "qualityStatus": "valid" if d7_valid else "invalid",
            "failureReason": d7_reason, "sourceDetector": d7_source_detector,
            "recoveryPass": d7_recovery_pass,
            "reference": d7_reference, "target": d7_target,
            "quality": d7_quality,
        },
        "Phi12.2": {
            "featureCode": "HOLE2-DIA-12_2", "measurementValid": phi_valid,
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
            "qualityStatus": "invalid",
            "failureReason": reason, "sourceDetector": "hole2-v6-dual-boundary",
            "recoveryPass": None,
            "reference": None, "target": None, "quality": {},
        },
        "Phi12.2": {
            "featureCode": "HOLE2-DIA-12_2", "measurementValid": False,
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
) -> dict[str, Any]:
    """Diagnose/reject gross wrong-edge pairs without changing any measurement."""
    d7_shape = next((shape for shape in reference.shapes if shape.sanitized == "d7"), None)
    phi_shape = next((shape for shape in reference.shapes if shape.sanitized == "Phi12_2"), None)
    if (
        d7_shape is None or d7_shape.line_p1 is None or d7_shape.line_p2 is None
        or phi_shape is None or phi_shape.circle is None
    ):
        return {
            "evaluated": False, "rejected": False,
            "failureReason": "reference_geometry_missing",
            "ratioSource": "old_reference_annotation_geometry",
        }
    reference_ratio = math.dist(d7_shape.line_p1, d7_shape.line_p2) / (
        2.0 * float(phi_shape.circle[2])
    )
    gate = float(config["geometry_consistency"]["max_reference_ratio_absolute_deviation"])
    report: dict[str, Any] = {
        "evaluated": False,
        "rejected": False,
        "failureReason": None,
        "ratioSource": "old_reference_annotation_geometry",
        "referenceRatio": float(reference_ratio),
        "targetRatio": None,
        "absoluteDeviation": None,
        "maximumAbsoluteDeviation": gate,
        "outputAdjustmentApplied": False,
    }
    d7 = features["7"]
    phi = features["Phi12.2"]
    if not d7["measurementValid"] or not phi["measurementValid"]:
        report["failureReason"] = "both_features_not_valid"
        return report
    target_ratio = float(d7["target"]["lengthPx"]) / float(phi["target"]["diameterPx"])
    deviation = abs(target_ratio - reference_ratio)
    rejected = deviation > gate
    report.update({
        "evaluated": True,
        "rejected": rejected,
        "failureReason": "geometry_ratio_inconsistent" if rejected else None,
        "targetRatio": target_ratio,
        "absoluteDeviation": deviation,
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
    """Infer annotation edge phase from the old reference pixels only."""
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
    fractions: list[float] = []
    contrasts: list[float] = []
    for angle in shape.template_angles:
        profile = bilinear_sample(
            reference.gray,
            cx + (radius + offsets) * math.cos(float(angle)),
            cy + (radius + offsets) * math.sin(float(angle)),
        )
        if np.isnan(profile).any():
            continue
        oriented = profile * polarity_sign
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
    }


def _phase_edge_at_angle(
    image: np.ndarray,
    center: tuple[float, float],
    radius: float,
    angle: float,
    polarity_sign: float,
    phase_fraction: float,
    phi_config: dict[str, Any],
) -> tuple[tuple[float, float], float, float] | None:
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
    angle_start = float(shape.angle_start + transform.theta_rad - extension)
    angle_end = float(shape.angle_end + transform.theta_rad + extension)
    angles = np.linspace(angle_start, angle_end, max(160, int(phi_config["phase_min_points"] * 5)))
    image = contrast_stretch(target)
    points: list[tuple[float, float]] = []
    point_angles: list[float] = []
    edge_peaks: list[float] = []
    contrasts: list[float] = []
    seed_center = (float(seed["target_cx"]), float(seed["target_cy"]))
    seed_radius = float(seed["target_radius"])
    for angle in angles:
        detected = _phase_edge_at_angle(
            image, seed_center, seed_radius, float(angle), polarity_sign,
            phase, phi_config,
        )
        if detected is None:
            continue
        point, edge_peak, contrast = detected
        points.append(point)
        point_angles.append(float(angle))
        edge_peaks.append(edge_peak)
        contrasts.append(contrast)
    fitted = _ransac_circle(
        np.asarray(points, dtype=np.float64),
        trials=int(phi_config["phase_ransac_trials"]),
        inlier_residual_px=float(phi_config["phase_ransac_inlier_residual_px"]),
        minimum_inliers=int(phi_config["phase_min_points"]),
    ) if points else None
    if fitted is None:
        diagnostics.update({
            "candidate_phase_failure": "phase_circle_fit_failed",
            "candidate_phase_edge_points": len(points),
        })
        return None, diagnostics
    circle, inliers, residual = fitted
    cx, cy, radius = (float(value) for value in circle)
    inlier_angles = np.unwrap(np.asarray(point_angles, dtype=np.float64)[inliers])
    expected_extent = max(1e-9, abs(angle_end - angle_start))
    coverage = float(np.ptp(inlier_angles) / expected_extent) if len(inlier_angles) > 1 else 0.0
    coverage = min(1.0, coverage)
    offset_x = cx - predicted_center[0]
    offset_y = cy - predicted_center[1]
    center_limit = float(seed["center_boundary"]["limitPx"])
    center_boundary = {
        "xLower": offset_x <= -center_limit,
        "xUpper": offset_x >= center_limit,
        "yLower": offset_y <= -center_limit,
        "yUpper": offset_y >= center_limit,
        "limitPx": center_limit,
    }
    radius_min = float(seed["radius_lower_bound"])
    radius_max = float(seed["radius_upper_bound"])
    reasons: list[str] = []
    if not radius_min <= radius <= radius_max:
        reasons.append("phase_radius_out_of_bounds")
    if any(center_boundary[key] for key in ("xLower", "xUpper", "yLower", "yUpper")):
        reasons.append("phase_center_boundary_saturated")
    if int(inliers.sum()) < int(phi_config["phase_min_points"]):
        reasons.append("phase_edge_points_below_gate")
    if residual > float(phi_config["max_fit_residual_target_px"]):
        reasons.append("phase_fit_residual_above_gate")
    if coverage < float(phi_config["min_angle_coverage_fraction"]):
        reasons.append("phase_angle_coverage_below_gate")
    diagnostics.update({
        "candidate_phase_failure": None if not reasons else ",".join(reasons),
        "candidate_phase_edge_points": int(inliers.sum()),
        "candidate_phase_raw_points": len(points),
        "candidate_phase_fit_residual_target_px": float(residual),
        "candidate_phase_angle_coverage_fraction": coverage,
        "candidate_phase_angle_extension_deg": float(phi_config["phase_angle_extension_deg"]),
        "candidate_phase_edge_peak_normalized": float(np.median(edge_peaks) / normalizer),
        "candidate_phase_contrast": float(np.median(contrasts)),
    })
    if reasons:
        return None, diagnostics
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
        "edge_peak": float(np.median(edge_peaks) / normalizer),
        "phase_refined": True,
    })
    return refined, diagnostics


def _detect_phi12_2(
    target: np.ndarray,
    reference: ReferenceModel,
    transform: SimilarityTransform,
    config: dict[str, Any],
) -> tuple[dict[str, float] | None, dict[str, Any]]:
    shape = next((item for item in reference.shapes if item.sanitized == "Phi12_2"), None)
    if shape is None or shape.circle is None:
        return None, {"candidate_failure": "reference_feature_missing"}
    cx, cy, radius = shape.circle
    predicted_center = transform.forward(cx, cy)
    predicted_radius = transform.scale * radius
    phi_config = config["phi12_2"]
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
            return None, {
                "candidate_failure": str(phase_diagnostics["candidate_phase_failure"]),
                "candidate_recovery_pass": recovery_pass,
                "candidate_main_lower_bound_saturated": bool(main["lower_radius_saturated"]),
                "candidate_main_radius_scale_ratio": float(main["radius_scale_ratio"]),
                **phase_diagnostics,
                **multicircle_diagnostics,
            }
        selected = phase_selected

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
    reasons: list[str] = []
    if not (selected_min <= ratio <= float(phi_config["max_radius_scale_ratio"])):
        reasons.append("radius_scale_ratio_out_of_range")
    if point_count < int(phi_config["min_edge_points"]):
        reasons.append("edge_points_below_gate")
    if fit_residual > float(phi_config["max_fit_residual_target_px"]):
        reasons.append("fit_residual_above_gate")
    if float(selected["edge_peak"]) < float(phi_config["min_edge_peak_normalized"]):
        reasons.append("edge_peak_below_gate")
    if float(selected["prominence"]) < float(phi_config["min_edge_prominence_normalized"]):
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
        "candidate_median_edge_score": float(np.median(edge_scores)) if edge_scores else float("nan"),
        "candidate_search_boundary_saturated": saturated,
        "candidate_lower_radius_boundary_saturated": bool(selected["lower_radius_saturated"]),
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
    """Fit the centerline of a dark physical contour from two edge polarities."""
    diagnostics.update({
        "endpoint": endpoint,
        "boundarySemantics": "paired_edge_centerline",
        "pairSupport": 0,
        "outerPeakMedian": None,
        "innerPeakMedian": None,
        "pairWidthMedianPx": None,
        "inlierPoints": 0,
        "medianResidualPx": None,
        "axisCosine": None,
        "offsetPx": None,
        "failureStage": None,
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
    edge_points: list[tuple[float, float]] = []
    outer_peaks: list[float] = []
    inner_peaks: list[float] = []
    pair_widths: list[float] = []

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
        best: tuple[float, float, float, float, float] | None = None
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
                    pair_score, center_position, outer_peak, inner_peak,
                    abs(inner_position - outer_position),
                )
                if best is None or candidate[0] > best[0]:
                    best = candidate
        if best is None:
            continue
        _, center_position, outer_peak, inner_peak, pair_width = best
        edge_points.append((
            float(center[0] + center_position * axis[0]),
            float(center[1] + center_position * axis[1]),
        ))
        outer_peaks.append(outer_peak)
        inner_peaks.append(inner_peak)
        pair_widths.append(pair_width)

    diagnostics.update({
        "pairSupport": len(edge_points),
        "outerPeakMedian": None if not outer_peaks else float(np.median(outer_peaks)),
        "innerPeakMedian": None if not inner_peaks else float(np.median(inner_peaks)),
        "pairWidthMedianPx": None if not pair_widths else float(np.median(pair_widths)),
    })
    minimum_support = int(d7_config["paired_edge_min_support"])
    fitted = robust_fit_line(edge_points, min_points=minimum_support)
    if fitted is None:
        diagnostics["failureStage"] = "paired_centerline_fit_failed"
        return None
    line, inliers = fitted
    diagnostics["inlierPoints"] = int(len(inliers))
    axis_cosine = abs(float(line[0]) * axis[0] + float(line[1]) * axis[1])
    diagnostics["axisCosine"] = axis_cosine
    if axis_cosine < D7_BOUNDARY_MIN_AXIS_COSINE:
        diagnostics["failureStage"] = "axis_alignment_below_gate"
        return None
    residuals = np.abs(line[0] * inliers[:, 0] + line[1] * inliers[:, 1] + line[2])
    median_residual = float(np.median(residuals))
    diagnostics["medianResidualPx"] = median_residual
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
    return BoundaryDetection(
        feature_point=feature_point,
        line=tuple(float(value) for value in line),
        point_count=int(len(inliers)),
        median_residual_px=median_residual,
        median_edge_score=float(min(np.median(outer_peaks), np.median(inner_peaks))),
        offset_px=float(offset),
    )


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
    return (aggregated_first, aggregated_second), quality


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
        if recovered is None:
            return None, combined
        recovered_first, recovered_second = recovered
        ref_first = transform.inverse(*recovered_first)
        ref_second = transform.inverse(*recovered_second)
        combined["candidate_primary_failed_sides"] = list(
            combined.get("candidate_failed_sides", [])
        )
        combined["candidate_failed_sides"] = []
        combined["candidate_failure"] = None
        return {
            "d7_x1": ref_first[0], "d7_y1": ref_first[1],
            "d7_x2": ref_second[0], "d7_y2": ref_second[1],
            "d7_length": math.dist(ref_first, ref_second),
        }, combined

    if first is None or second is None:
        failed_sides = [
            side for side, boundary in (("p1", first), ("p2", second))
            if boundary is None
        ]
        return recover_multiband({
            "candidate_failure": "tangent_boundary_fit_failed",
            "candidate_boundary_semantics": "paired_edge_centerline",
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
        "candidate_recovery_pass": None,
        "candidate_boundary_semantics": "paired_edge_centerline",
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
    }
    if reasons:
        return recover_multiband(quality)
    ref_first = transform.inverse(*first.feature_point)
    ref_second = transform.inverse(*second.feature_point)
    return {
        "d7_x1": ref_first[0], "d7_y1": ref_first[1],
        "d7_x2": ref_second[0], "d7_y2": ref_second[1],
        "d7_length": math.dist(ref_first, ref_second),
    }, quality


def _v6_d7_fallback(
    v6_measurements: dict[str, Any],
    candidate_quality: dict[str, Any],
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
    keys = ("d7_x1", "d7_y1", "d7_x2", "d7_y2", "d7_length")
    original_valid = (
        v6_measurements.get("d7.quality.upstream") == "ok:dual_boundary_fit"
        and _finite_values(v6_measurements, list(keys))
    )
    if not original_valid:
        quality["candidate_fallback_failure"] = "v6_original_quality_rejected"
        return None, quality
    quality["candidate_fallback_pass"] = "v6_original_quality"
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
        "qualityStatus", "geometryConsistency",
    }
    missing = sorted(required - result.keys())
    if missing:
        raise ValueError("result missing required fields: " + ",".join(missing))
    if result["schemaVersion"] != RESULT_SCHEMA_VERSION:
        raise ValueError("unsupported result schemaVersion")
    roles = [item.get("role") for item in result["runtimeInputs"]]
    expected_roles = ["reference_annotation", "reference_image", "target_image", "configuration"]
    if sorted(roles) != sorted(expected_roles) or len(roles) != 4:
        raise ValueError("runtime input roles must be exactly reference_annotation, reference_image, target_image, configuration")
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
    if set(result["features"]) != {"7", "Phi12.2"}:
        raise ValueError("features must contain exactly 7 and Phi12.2")
    feature_required = {
        "featureCode", "measurementValid", "qualityStatus", "failureReason", "sourceDetector",
        "recoveryPass", "reference", "target", "quality",
    }
    for name, feature in result["features"].items():
        if not isinstance(feature, dict) or not feature_required <= feature.keys():
            raise ValueError(f"feature {name} is incomplete")
        expected_status = "valid" if feature["measurementValid"] else "invalid"
        if feature["qualityStatus"] != expected_status:
            raise ValueError(f"feature {name} qualityStatus conflicts with measurementValid")
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
    if status["productionDisposition"] != "not_evaluated":
        raise ValueError("productionDisposition must remain not_evaluated")
    if not isinstance(result["timingMs"], dict) or float(result["timingMs"].get("total", -1)) < 0:
        raise ValueError("timingMs.total must be non-negative")
    if result["evidenceScope"] != EVIDENCE_SCOPE:
        raise ValueError("invalid evidenceScope")
    _assert_no_nonfinite(result)


def run_current_capture(
    label_path: Path,
    reference_image_path: Path,
    target_image_path: Path,
    config_path: Path,
) -> dict[str, Any]:
    started = time.perf_counter()
    config = load_registration_config(config_path)
    reference = build_reference(label_path, reference_image_path)
    target = load_gray(target_image_path)
    registration_started = time.perf_counter()
    registration = register_current_capture(reference, target, config)
    registration_ms = (time.perf_counter() - registration_started) * 1000.0
    extraction_ms = 0.0
    errors: list[str] = []
    raw_measurements: dict[str, Any] = {}
    compatible: dict[str, Any] = {}
    if not registration["registrationValid"]:
        features = _invalid_features("registration_invalid:" + str(registration["failureReason"]))
        geometry_consistency = {
            "evaluated": False, "rejected": False,
            "failureReason": "registration_invalid",
            "ratioSource": "old_reference_annotation_geometry",
            "outputAdjustmentApplied": False,
        }
    else:
        transform_data = registration["transform"]
        transform = SimilarityTransform(
            transform_data["dx"], transform_data["dy"],
            transform_data["scale"], transform_data["thetaDeg"],
        )
        extraction_started = time.perf_counter()
        extraction: Extraction = extract_image(
            target_image_path, reference, allow_rotation=True,
            expand_anchors=False,
            initial_transform=(transform.dx, transform.dy, transform.scale, transform.theta_rad),
            refine_initial_transform=False,
        )
        extraction_ms = (time.perf_counter() - extraction_started) * 1000.0
        raw_measurements = dict(extraction.measurements)
        measurements = dict(raw_measurements)
        phi_values, phi_quality = _detect_phi12_2(target, reference, transform, config)
        for key, value in phi_quality.items():
            measurements[f"Phi12_2.quality.{key}"] = value
        phi_source = "hole2-v6-current-capture-candidate"
        d7_source = "hole2-v6-current-capture-paired-contour-centerline"
        if phi_values is not None:
            measurements.update(phi_values)
            d7_values, d7_quality = _detect_d7_tangent(
                target, reference, transform, phi_values, config
            )
            if (
                d7_values is not None
                and d7_quality.get("candidate_recovery_pass") == "multi_parallel_bands"
            ):
                d7_source = "hole2-v6-current-capture-multi-parallel-bands"
            if d7_values is None:
                d7_values, d7_quality = _v6_d7_fallback(raw_measurements, d7_quality)
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
        shape = next((item for item in reference.shapes if item.sanitized == "Phi12_2"), None)
        phi_angles = [] if shape is None or shape.template_angles is None else shape.template_angles
        features, compatible = build_feature_outputs(
            measurements, transform, phi_angles,
            phi_source_detector=phi_source,
            d7_source_detector=d7_source,
        )
        geometry_consistency = evaluate_geometry_consistency(features, reference, config)

    runtime_inputs = [
        {"role": "reference_annotation", "path": str(label_path), "sha256": sha256_file(label_path)},
        {"role": "reference_image", "path": str(reference_image_path), "sha256": sha256_file(reference_image_path)},
        {"role": "target_image", "path": str(target_image_path), "sha256": sha256_file(target_image_path)},
        {"role": "configuration", "path": str(config_path), "sha256": sha256_file(config_path)},
    ]
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
