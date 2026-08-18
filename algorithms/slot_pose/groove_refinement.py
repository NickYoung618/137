"""Subpixel groove-side refinement and sidewall/outer-circle intersections."""

from __future__ import annotations

import math
import time
from typing import Any, Callable

import numpy as np

from algorithms.slot_pose.angular_profile import circular_distance_deg, wrap_360_deg


SCHEMA_VERSION = "slot-groove-subpixel-opening/1"
SCHEMA_VERSION_V2 = "slot-groove-subpixel-opening/2"
SCHEMA_VERSION_V3 = "slot-groove-subpixel-opening/3"
SCHEMA_VERSION_V4 = "slot-groove-subpixel-opening/4"
THRESHOLD_VERSION_V1 = "groove-sidewall-subpixel-v1"
THRESHOLD_VERSION_V2 = "groove-sidewall-subpixel-v2"
DEFAULT_GROOVE_REFINEMENT_CONFIG: dict[str, Any] = {
    "threshold_version": THRESHOLD_VERSION_V1,
    "radial_inset_min_px": 12.0,
    "radial_inset_max_px": 95.0,
    "radial_sample_count": 31,
    "tangential_search_margin_deg": 4.0,
    "tangential_sample_step_px": 0.35,
    "contrast_inner_offset_px": 3.0,
    "contrast_outer_offset_px": 12.0,
    "min_side_points": 16,
    "min_edge_contrast": 15.0,
    "min_edge_gradient_per_px": 2.0,
    "max_line_residual_p95_px": 2.0,
    "max_intersection_coarse_delta_deg": 2.0,
    "allow_endpoint_reversal": False,
    "line_consensus_min_inlier_ratio": 0.50,
    "line_consensus_min_span_ratio": 0.70,
    "line_consensus_min_pair_separation_ratio": 0.25,
    "line_consensus_model_merge_deg": 0.10,
    "line_consensus_min_support_margin": 2,
    "line_consensus_max_refit_hypotheses": 32,
}
DEFAULT_WALL_EDGE_FAMILY_CONFIG: dict[str, Any] = {
    "schema_version": "groove-wall-edge-family/1",
    "enabled": False,
    "strategy_version": "bounded-cross-radius-wall-family-v1",
    "max_peaks_per_row": 4,
    "min_peak_separation_px": 1.5,
    "max_hypotheses": 64,
}
WALL_EDGE_FAMILY_V2_CONFIG: dict[str, Any] = {
    "schema_version": "groove-wall-edge-family/2",
    "enabled": False,
    "strategy_version": "shared-longitudinal-wall-family-v2",
    "max_peaks_per_row": 4,
    "min_peak_separation_px": 1.5,
    "max_hypotheses": 64,
    "min_shared_support_count": 16,
    "min_shared_span_ratio": 0.7,
    "max_direction_delta_deg": 0.5,
    "max_shared_separation_p95_px": 6.0,
    "max_shared_separation_px": 6.0,
    "max_endpoint_chord_distance_px": 6.0,
    "max_endpoint_angle_delta_deg": 0.25,
    "max_radial_alignment_delta_deg": 8.0,
}


def validate_groove_refinement_config(config: dict[str, Any]) -> None:
    if not isinstance(config, dict):
        raise ValueError("groove_refinement must be an object")
    required = set(DEFAULT_GROOVE_REFINEMENT_CONFIG)
    missing = sorted(required - set(config))
    unexpected = sorted(set(config) - required - {"wall_edge_family"})
    if missing:
        raise ValueError(f"groove_refinement missing fields: {missing}")
    if unexpected:
        raise ValueError(f"groove_refinement has unsupported fields: {unexpected}")
    if config["threshold_version"] not in {THRESHOLD_VERSION_V1, THRESHOLD_VERSION_V2}:
        raise ValueError("groove_refinement.threshold_version is unsupported")
    for key in (
        "radial_inset_min_px", "radial_inset_max_px", "tangential_search_margin_deg",
        "tangential_sample_step_px", "contrast_inner_offset_px", "contrast_outer_offset_px",
        "min_edge_contrast", "min_edge_gradient_per_px", "max_line_residual_p95_px",
        "max_intersection_coarse_delta_deg",
    ):
        value = config[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)) or float(value) <= 0.0:
            raise ValueError(f"groove_refinement.{key} must be a positive finite number")
    if float(config["radial_inset_min_px"]) >= float(config["radial_inset_max_px"]):
        raise ValueError("groove_refinement radial inset bounds must be ordered")
    if float(config["contrast_inner_offset_px"]) >= float(config["contrast_outer_offset_px"]):
        raise ValueError("groove_refinement contrast offsets must be ordered")
    for key in ("radial_sample_count", "min_side_points"):
        value = config[key]
        if isinstance(value, bool) or not isinstance(value, int) or value < 3:
            raise ValueError(f"groove_refinement.{key} must be an integer >=3")
    if int(config["min_side_points"]) > int(config["radial_sample_count"]):
        raise ValueError("groove_refinement.min_side_points exceeds radial_sample_count")
    if not isinstance(config["allow_endpoint_reversal"], bool):
        raise ValueError("groove_refinement.allow_endpoint_reversal must be boolean")
    for key in (
        "line_consensus_min_inlier_ratio", "line_consensus_min_span_ratio",
        "line_consensus_min_pair_separation_ratio",
    ):
        value = config[key]
        if (
            isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(float(value)) or not 0.0 < float(value) <= 1.0
        ):
            raise ValueError(f"groove_refinement.{key} must be in (0,1]")
    merge = config["line_consensus_model_merge_deg"]
    if (
        isinstance(merge, bool) or not isinstance(merge, (int, float))
        or not math.isfinite(float(merge)) or not 0.0 < float(merge) <= 180.0
    ):
        raise ValueError("groove_refinement.line_consensus_model_merge_deg must be in (0,180]")
    for key, minimum, maximum in (
        ("line_consensus_min_support_margin", 1, None),
        ("line_consensus_max_refit_hypotheses", 2, 128),
    ):
        value = config[key]
        if (
            isinstance(value, bool) or not isinstance(value, int) or value < minimum
            or (maximum is not None and value > maximum)
        ):
            suffix = f" in [{minimum},{maximum}]" if maximum is not None else f" >={minimum}"
            raise ValueError(f"groove_refinement.{key} must be an integer{suffix}")
    if "wall_edge_family" in config:
        family = config["wall_edge_family"]
        if not isinstance(family, dict):
            raise ValueError("groove_refinement.wall_edge_family must be an object")
        schema = family.get("schema_version", DEFAULT_WALL_EDGE_FAMILY_CONFIG["schema_version"])
        strategy = family.get("strategy_version", DEFAULT_WALL_EDGE_FAMILY_CONFIG["strategy_version"])
        pair = (schema, strategy)
        allowed = {
            (
                DEFAULT_WALL_EDGE_FAMILY_CONFIG["schema_version"],
                DEFAULT_WALL_EDGE_FAMILY_CONFIG["strategy_version"],
            ): DEFAULT_WALL_EDGE_FAMILY_CONFIG,
            (
                WALL_EDGE_FAMILY_V2_CONFIG["schema_version"],
                WALL_EDGE_FAMILY_V2_CONFIG["strategy_version"],
            ): WALL_EDGE_FAMILY_V2_CONFIG,
        }
        if pair not in allowed:
            raise ValueError("groove_refinement.wall_edge_family schema/strategy pair is unsupported")
        defaults = allowed[pair]
        merged_family = {**defaults, **family}
        unknown = sorted(set(merged_family) - set(defaults))
        if unknown:
            raise ValueError(f"groove_refinement.wall_edge_family has unsupported fields: {unknown}")
        if not isinstance(merged_family["enabled"], bool):
            raise ValueError("groove_refinement.wall_edge_family.enabled must be boolean")
        for key, low, high in (("max_peaks_per_row", 2, 8), ("max_hypotheses", 2, 128)):
            value = merged_family[key]
            if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
                raise ValueError(f"groove_refinement.wall_edge_family.{key} must be in [{low},{high}]")
        separation = merged_family["min_peak_separation_px"]
        if (
            isinstance(separation, bool) or not isinstance(separation, (int, float))
            or not math.isfinite(float(separation)) or float(separation) <= 0.0
        ):
            raise ValueError("groove_refinement.wall_edge_family.min_peak_separation_px must be positive")
        if defaults is WALL_EDGE_FAMILY_V2_CONFIG:
            for key in ("min_shared_support_count",):
                value = merged_family[key]
                if isinstance(value, bool) or not isinstance(value, int) or not 3 <= value <= 128:
                    raise ValueError(f"groove_refinement.wall_edge_family.{key} must be in [3,128]")
            ratio = merged_family["min_shared_span_ratio"]
            if (
                isinstance(ratio, bool) or not isinstance(ratio, (int, float))
                or not math.isfinite(float(ratio)) or not 0.0 < float(ratio) <= 1.0
            ):
                raise ValueError("groove_refinement.wall_edge_family.min_shared_span_ratio must be in (0,1]")
            for key in (
                "max_direction_delta_deg", "max_shared_separation_p95_px",
                "max_shared_separation_px", "max_endpoint_chord_distance_px",
                "max_endpoint_angle_delta_deg", "max_radial_alignment_delta_deg",
            ):
                value = merged_family[key]
                if (
                    isinstance(value, bool) or not isinstance(value, (int, float))
                    or not math.isfinite(float(value)) or float(value) <= 0.0
                ):
                    raise ValueError(f"groove_refinement.wall_edge_family.{key} must be positive and finite")
            if float(merged_family["max_direction_delta_deg"]) > 45.0:
                raise ValueError("groove_refinement.wall_edge_family.max_direction_delta_deg must be <=45")
            if float(merged_family["max_endpoint_angle_delta_deg"]) > 45.0:
                raise ValueError("groove_refinement.wall_edge_family.max_endpoint_angle_delta_deg must be <=45")
            if float(merged_family["max_radial_alignment_delta_deg"]) > 45.0:
                raise ValueError("groove_refinement.wall_edge_family.max_radial_alignment_delta_deg must be <=45")
            if (
                float(merged_family["max_shared_separation_p95_px"])
                > float(merged_family["max_shared_separation_px"])
            ):
                raise ValueError("groove_refinement.wall_edge_family separation bounds must be ordered")
        config["wall_edge_family"] = merged_family


def merged_groove_refinement_config(config: dict[str, Any] | None) -> dict[str, Any]:
    merged = {**DEFAULT_GROOVE_REFINEMENT_CONFIG, **(config or {})}
    validate_groove_refinement_config(merged)
    return merged


def _summary(values: np.ndarray) -> dict[str, float]:
    return {
        "median": float(np.median(values)),
        "p95": float(np.percentile(values, 95.0)),
        "max": float(np.max(values)),
    }


def _small_percentile_95(values: np.ndarray) -> float:
    """Linear P95 for tiny sidewall sets without repeated np.percentile setup."""
    ordered = np.sort(np.asarray(values, dtype=float))
    position = (len(ordered) - 1) * 0.95
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return float(ordered[lower])
    fraction = position - lower
    return float(ordered[lower] + (ordered[upper] - ordered[lower]) * fraction)


def _fit_line_tls(points: np.ndarray) -> tuple[float, float, float]:
    centroid = np.mean(points, axis=0)
    centered = points - centroid
    _, singular, vh = np.linalg.svd(centered, full_matrices=False)
    if len(singular) < 2 or not np.isfinite(singular).all() or singular[0] <= 1e-9:
        raise ValueError("degenerate sidewall points")
    direction = vh[0]
    a, b = -float(direction[1]), float(direction[0])
    norm = math.hypot(a, b)
    if norm <= 1e-12:
        raise ValueError("degenerate sidewall line")
    a, b = a / norm, b / norm
    c = -(a * float(centroid[0]) + b * float(centroid[1]))
    return a, b, c


def _robust_fit_line(points: list[tuple[float, float]], minimum: int) -> tuple[tuple[float, float, float], np.ndarray, np.ndarray]:
    kept = np.asarray(points, dtype=float)
    if len(kept) < minimum or not np.isfinite(kept).all():
        raise ValueError("insufficient finite sidewall points")
    for _ in range(6):
        line = _fit_line_tls(kept)
        residuals = np.abs(line[0] * kept[:, 0] + line[1] * kept[:, 1] + line[2])
        median = float(np.median(residuals))
        mad = float(np.median(np.abs(residuals - median))) + 1e-9
        gate = max(0.35, median + 3.0 * 1.4826 * mad)
        mask = residuals <= gate
        if int(np.count_nonzero(mask)) < minimum or bool(np.all(mask)):
            break
        kept = kept[mask]
    line = _fit_line_tls(kept)
    residuals = np.abs(line[0] * kept[:, 0] + line[1] * kept[:, 1] + line[2])
    return line, kept, residuals


def _profile_angle(point: tuple[float, float] | np.ndarray, center: tuple[float, float]) -> float:
    return wrap_360_deg(math.degrees(math.atan2(float(point[1]) - center[1], float(point[0]) - center[0])))


def _line_projection_coverage(points: np.ndarray, mask: np.ndarray, line: tuple[float, float, float]) -> float:
    direction = np.asarray((-line[1], line[0]), dtype=float)
    projected = points @ direction
    total_span = float(np.max(projected) - np.min(projected))
    if total_span <= 1e-9 or int(np.count_nonzero(mask)) < 2:
        return 0.0
    kept = projected[mask]
    return float((np.max(kept) - np.min(kept)) / total_span)


def _circular_delta_abs(left: float, right: float) -> float:
    return abs((float(left) - float(right) + 180.0) % 360.0 - 180.0)


def _radial_line_alignment_deg(
    line: tuple[float, float, float], intersection: tuple[float, float],
    center: tuple[float, float],
) -> float:
    direction = np.asarray((-float(line[1]), float(line[0])), dtype=float)
    radial = np.asarray(intersection, dtype=float) - np.asarray(center, dtype=float)
    direction_norm = float(np.linalg.norm(direction))
    radial_norm = float(np.linalg.norm(radial))
    if direction_norm <= 1e-9 or radial_norm <= 1e-9:
        return math.inf
    cosine = float(np.clip(abs(np.dot(
        direction / direction_norm, radial / radial_norm,
    )), 0.0, 1.0))
    return math.degrees(math.acos(cosine))


def _select_consensus_line(
    points: list[tuple[float, float]],
    *,
    minimum: int,
    center: tuple[float, float],
    outer_radius: float,
    coarse_angle_deg: float,
    maximum_delta_deg: float,
    config: dict[str, Any],
    pixel_scale: float,
) -> dict[str, Any]:
    """Select one deterministic straight sidewall consensus or fail explicitly."""
    array = np.asarray(points, dtype=float)
    base = {
        "status": "not_found", "failedCheck": "consensus_not_found",
        "detectedPointCount": int(len(array)), "inlierCount": 0,
        "rejectedPointCount": int(len(array)), "inlierRatio": None,
        "longitudinalCoverage": None, "residualP95Px": None,
        "rawHypothesisCount": 0, "refitHypothesisCount": 0,
        "hypothesisCount": 0, "bestModelId": None, "secondModelId": None,
        "bestSupportCount": None, "secondSupportCount": None, "supportMargin": None,
        "line": None, "inlierMask": None, "residuals": None,
        "intersection": None, "intersectionAngleDeg": None,
    }
    if len(array) < minimum or not np.isfinite(array).all():
        return {**base, "failedCheck": "insufficient_support"}
    pair_distances = np.linalg.norm(array[:, None, :] - array[None, :, :], axis=2)
    maximum_pair_distance = float(np.max(pair_distances))
    if maximum_pair_distance <= 1e-9:
        return base
    minimum_pair_distance = (
        float(config["line_consensus_min_pair_separation_ratio"]) * maximum_pair_distance
    )
    residual_gate = float(config["max_line_residual_p95_px"]) * pixel_scale
    minimum_ratio = float(config["line_consensus_min_inlier_ratio"])
    minimum_span = float(config["line_consensus_min_span_ratio"])
    raw_hypotheses: dict[bytes, dict[str, Any]] = {}
    saw_minimum = saw_ratio = saw_span = saw_residual = False
    hypotheses: list[dict[str, Any]] = []
    for first in range(len(array)):
        for second in range(first + 1, len(array)):
            delta = array[second] - array[first]
            distance = float(np.linalg.norm(delta))
            if distance < minimum_pair_distance:
                continue
            a, b = -float(delta[1]) / distance, float(delta[0]) / distance
            c = -(a * float(array[first, 0]) + b * float(array[first, 1]))
            pair_residuals = np.abs(a * array[:, 0] + b * array[:, 1] + c)
            mask = pair_residuals <= residual_gate
            count = int(np.count_nonzero(mask))
            if count < minimum:
                continue
            saw_minimum = True
            mask_key = np.packbits(mask).tobytes()
            rank_key = (
                -count, _small_percentile_95(pair_residuals[mask]),
                -distance, first, second,
            )
            previous = raw_hypotheses.get(mask_key)
            if previous is None or rank_key < previous["rankKey"]:
                raw_hypotheses[mask_key] = {"rankKey": rank_key, "mask": mask}
    refit_limit = int(config["line_consensus_max_refit_hypotheses"])
    selected_raw = sorted(raw_hypotheses.values(), key=lambda item: item["rankKey"])[:refit_limit]
    for raw in selected_raw:
        mask = np.asarray(raw["mask"], dtype=bool)
        for _ in range(6):
            if int(np.count_nonzero(mask)) < minimum:
                break
            try:
                line = _fit_line_tls(array[mask])
            except (ValueError, np.linalg.LinAlgError):
                break
            all_residuals = np.abs(
                line[0] * array[:, 0] + line[1] * array[:, 1] + line[2]
            )
            updated = all_residuals <= residual_gate
            if bool(np.array_equal(mask, updated)):
                break
            mask = updated
        count = int(np.count_nonzero(mask))
        if count < minimum:
            continue
        try:
            line = _fit_line_tls(array[mask])
        except (ValueError, np.linalg.LinAlgError):
            continue
        all_residuals = np.abs(
            line[0] * array[:, 0] + line[1] * array[:, 1] + line[2]
        )
        inlier_residuals = all_residuals[mask]
        ratio = count / len(array)
        if ratio < minimum_ratio:
            continue
        saw_ratio = True
        coverage = _line_projection_coverage(array, mask, line)
        if coverage < minimum_span:
            continue
        saw_span = True
        residual_p95 = _small_percentile_95(inlier_residuals)
        if residual_p95 > residual_gate:
            continue
        saw_residual = True
        try:
            intersection, intersection_angle = _circle_intersection(
                line, center, outer_radius, coarse_angle_deg, maximum_delta_deg,
            )
        except ValueError:
            continue
        hypotheses.append({
            "line": line, "mask": mask, "residuals": inlier_residuals,
            "inlierCount": count, "inlierRatio": ratio,
            "longitudinalCoverage": coverage, "residualP95Px": residual_p95,
            "intersection": intersection, "intersectionAngleDeg": intersection_angle,
        })
    if not hypotheses:
        if not saw_minimum:
            failure = "consensus_not_found"
        elif not saw_ratio:
            failure = "consensus_inlier_ratio"
        elif not saw_span:
            failure = "consensus_span"
        elif not saw_residual:
            failure = "line_residual"
        else:
            failure = "intersection"
        return {
            **base, "failedCheck": failure,
            "rawHypothesisCount": len(raw_hypotheses),
            "refitHypothesisCount": len(selected_raw),
        }
    hypotheses.sort(key=lambda item: (
        -int(item["inlierCount"]), float(item["residualP95Px"]),
        -float(item["longitudinalCoverage"]), float(item["intersectionAngleDeg"]),
    ))
    distinct: list[dict[str, Any]] = []
    merge_deg = float(config["line_consensus_model_merge_deg"])
    for hypothesis in hypotheses:
        if any(
            _circular_delta_abs(hypothesis["intersectionAngleDeg"], existing["intersectionAngleDeg"])
            <= merge_deg
            for existing in distinct
        ):
            continue
        distinct.append(hypothesis)
    for index, hypothesis in enumerate(distinct, start=1):
        hypothesis["modelId"] = f"side-model-{index:03d}"
    best = distinct[0]
    second = distinct[1] if len(distinct) > 1 else None
    margin = None if second is None else int(best["inlierCount"] - second["inlierCount"])
    common = {
        **base,
        "rawHypothesisCount": len(raw_hypotheses),
        "refitHypothesisCount": len(selected_raw),
        "hypothesisCount": len(distinct),
        "bestModelId": best["modelId"],
        "secondModelId": None if second is None else second["modelId"],
        "bestSupportCount": int(best["inlierCount"]),
        "secondSupportCount": None if second is None else int(second["inlierCount"]),
        "supportMargin": margin,
    }
    if second is not None and margin is not None and margin < int(config["line_consensus_min_support_margin"]):
        return {**common, "status": "ambiguous", "failedCheck": "consensus_ambiguous"}
    mask = np.asarray(best["mask"], dtype=bool)
    return {
        **common,
        "status": "accepted", "failedCheck": None,
        "inlierCount": int(best["inlierCount"]),
        "rejectedPointCount": int(len(array) - best["inlierCount"]),
        "inlierRatio": float(best["inlierRatio"]),
        "longitudinalCoverage": float(best["longitudinalCoverage"]),
        "residualP95Px": float(best["residualP95Px"]),
        "line": best["line"], "inlierMask": mask,
        "residuals": best["residuals"],
        "intersection": best["intersection"],
        "intersectionAngleDeg": float(best["intersectionAngleDeg"]),
    }


def _hypothesis_rank(item: dict[str, Any]) -> tuple[Any, ...]:
    line = tuple(round(float(value), 12) for value in item["line"])
    signature = tuple(sorted(item["candidateSignature"]))
    return (
        -int(item["supportCount"]), float(item["residualP95Px"]),
        -float(item["longitudinalCoverage"]), float(item["intersectionAngleDeg"]),
        line, signature,
    )


def _exact_hypothesis_dedup(hypotheses: list[dict[str, Any]]) -> list[dict[str, Any]]:
    exact: dict[frozenset[tuple[int, int, int]], dict[str, Any]] = {}
    for item in sorted(hypotheses, key=_hypothesis_rank):
        signature = item["candidateSignature"]
        if signature not in exact:
            exact[signature] = item
    ordered = sorted(exact.values(), key=_hypothesis_rank)
    for index, item in enumerate(ordered, start=1):
        item["hypothesisId"] = f"wall-hypothesis-{index:03d}"
    return ordered


def _wall_hypothesis_equivalence(
    left: dict[str, Any], right: dict[str, Any], *, center: tuple[float, float],
    config: dict[str, Any], pixel_scale: float,
) -> dict[str, Any]:
    base = {
        "leftHypothesisId": left["hypothesisId"],
        "rightHypothesisId": right["hypothesisId"],
        "finiteGeometry": False, "equivalent": False, "failedChecks": [],
    }
    try:
        line_left = np.asarray(left["line"], dtype=float)
        line_right = np.asarray(right["line"], dtype=float)
        if line_left.shape != (3,) or line_right.shape != (3,):
            raise ValueError("invalid line")
        left_points = np.asarray([item[1]["point"] for item in left["selected"]], dtype=float)
        right_points = np.asarray([item[1]["point"] for item in right["selected"]], dtype=float)
        intersections = np.asarray([left["intersection"], right["intersection"]], dtype=float)
        if (
            left_points.ndim != 2 or right_points.ndim != 2
            or left_points.shape[1:] != (2,) or right_points.shape[1:] != (2,)
            or not np.isfinite(line_left).all() or not np.isfinite(line_right).all()
            or not np.isfinite(left_points).all() or not np.isfinite(right_points).all()
            or not np.isfinite(intersections).all()
        ):
            raise ValueError("nonfinite geometry")
        direction_left = np.asarray((-line_left[1], line_left[0]), dtype=float)
        direction_right = np.asarray((-line_right[1], line_right[0]), dtype=float)
        direction_left /= np.linalg.norm(direction_left)
        direction_right /= np.linalg.norm(direction_right)
        if float(np.dot(direction_left, direction_right)) < 0.0:
            direction_right = -direction_right
        dot = float(np.clip(np.dot(direction_left, direction_right), -1.0, 1.0))
        direction_delta = math.degrees(math.acos(dot))
        common = direction_left + direction_right
        common_norm = float(np.linalg.norm(common))
        if not math.isfinite(common_norm) or common_norm <= 1e-9:
            raise ArithmeticError("degenerate common frame")
        longitudinal = common / common_norm
        transverse = np.asarray((-longitudinal[1], longitudinal[0]), dtype=float)
        origin = np.asarray(center, dtype=float)
        left_projection = (left_points - origin) @ longitudinal
        right_projection = (right_points - origin) @ longitudinal
        left_range = (float(np.min(left_projection)), float(np.max(left_projection)))
        right_range = (float(np.min(right_projection)), float(np.max(right_projection)))
        shared_start = max(left_range[0], right_range[0])
        shared_end = min(left_range[1], right_range[1])
        shared_span = shared_end - shared_start
        shorter_span = min(left_range[1] - left_range[0], right_range[1] - right_range[0])
        if not all(math.isfinite(value) for value in (*left_range, *right_range, shared_span, shorter_span)):
            raise ValueError("nonfinite projection")
        shared_ratio = shared_span / shorter_span if shorter_span > 1e-9 and shared_span > 0.0 else 0.0
        left_shared = int(np.count_nonzero((left_projection >= shared_start) & (left_projection <= shared_end)))
        right_shared = int(np.count_nonzero((right_projection >= shared_start) & (right_projection <= shared_end)))

        def transverse_coordinate(line: np.ndarray, position: float) -> float:
            denominator = float(line[0] * transverse[0] + line[1] * transverse[1])
            if abs(denominator) <= 1e-9:
                raise ArithmeticError("degenerate common frame")
            point = origin + position * longitudinal
            return -float(line[0] * point[0] + line[1] * point[1] + line[2]) / denominator

        shared_positions = [shared_start, (shared_start + shared_end) * 0.5, shared_end]
        if shared_span > 0.0:
            shared_positions.extend(float(value) for value in left_projection if shared_start <= value <= shared_end)
            shared_positions.extend(float(value) for value in right_projection if shared_start <= value <= shared_end)
        signed = np.asarray([
            transverse_coordinate(line_left, position) - transverse_coordinate(line_right, position)
            for position in shared_positions
        ], dtype=float)
        if not np.isfinite(signed).all():
            raise ValueError("nonfinite separation")
        absolute = np.abs(signed)
        separation_p95 = _small_percentile_95(absolute)
        separation_max = float(np.max(absolute))
        endpoint_chord = float(np.linalg.norm(intersections[0] - intersections[1]))
        endpoint_angle = _circular_delta_abs(
            float(left["intersectionAngleDeg"]), float(right["intersectionAngleDeg"]),
        )
    except ArithmeticError:
        return {**base, "failedChecks": ["degenerate_common_frame"]}
    except (ValueError, TypeError, ZeroDivisionError, np.linalg.LinAlgError):
        return {**base, "failedChecks": ["nonfinite_equivalence_geometry"]}

    thresholds = {
        "minSharedSupportCount": int(config["min_shared_support_count"]),
        "minSharedSpanRatio": float(config["min_shared_span_ratio"]),
        "maxDirectionDeltaDeg": float(config["max_direction_delta_deg"]),
        "maxSharedSeparationP95Px": float(config["max_shared_separation_p95_px"]) * pixel_scale,
        "maxSharedSeparationPx": float(config["max_shared_separation_px"]) * pixel_scale,
        "maxEndpointChordDistancePx": float(config["max_endpoint_chord_distance_px"]) * pixel_scale,
        "maxEndpointAngleDeltaDeg": float(config["max_endpoint_angle_delta_deg"]),
    }
    failed: list[str] = []
    if left_shared < thresholds["minSharedSupportCount"] or right_shared < thresholds["minSharedSupportCount"]:
        failed.append("insufficient_shared_support")
    if shared_ratio < thresholds["minSharedSpanRatio"]:
        failed.append("insufficient_shared_span")
    if direction_delta > thresholds["maxDirectionDeltaDeg"]:
        failed.append("direction_mismatch")
    if (
        separation_p95 > thresholds["maxSharedSeparationP95Px"]
        or separation_max > thresholds["maxSharedSeparationPx"]
    ):
        failed.append("shared_span_separation")
    if endpoint_chord > thresholds["maxEndpointChordDistancePx"]:
        failed.append("outer_endpoint_distance")
    if endpoint_angle > thresholds["maxEndpointAngleDeltaDeg"]:
        failed.append("outer_endpoint_angle")
    return {
        **base, "finiteGeometry": True,
        "sharedRangePx": [shared_start, shared_end], "sharedSpanPx": shared_span,
        "sharedSpanRatioOfShorter": shared_ratio,
        "leftSharedSupportCount": left_shared, "rightSharedSupportCount": right_shared,
        "directionDeltaDeg": direction_delta,
        "signedSeparationStartPx": float(signed[0]),
        "signedSeparationMidPx": float(signed[1]),
        "signedSeparationEndPx": float(signed[2]),
        "separationP95Px": separation_p95, "separationMaxPx": separation_max,
        "endpointChordDistancePx": endpoint_chord, "endpointAngleDeltaDeg": endpoint_angle,
        "thresholds": thresholds, "equivalent": not failed, "failedChecks": failed,
    }


def _group_wall_source_families(
    hypotheses: list[dict[str, Any]], *, center: tuple[float, float],
    config: dict[str, Any], pixel_scale: float,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    unique = _exact_hypothesis_dedup(hypotheses)
    comparisons: list[dict[str, Any]] = []
    equivalent: dict[tuple[str, str], bool] = {}
    for left_index, left in enumerate(unique):
        for right in unique[left_index + 1:]:
            comparison = _wall_hypothesis_equivalence(
                left, right, center=center, config=config, pixel_scale=pixel_scale,
            )
            comparisons.append(comparison)
            equivalent[(left["hypothesisId"], right["hypothesisId"])] = bool(comparison["equivalent"])
    families: list[list[dict[str, Any]]] = [[item] for item in unique]
    while True:
        mergeable: list[tuple[tuple[str, ...], int, int]] = []
        for left_index, left_family in enumerate(families):
            for right_index in range(left_index + 1, len(families)):
                right_family = families[right_index]
                if all(
                    equivalent.get(tuple(sorted((left["hypothesisId"], right["hypothesisId"]))), False)
                    for left in left_family for right in right_family
                ):
                    ids = tuple(sorted(
                        item["hypothesisId"] for item in (*left_family, *right_family)
                    ))
                    mergeable.append((ids, left_index, right_index))
        if not mergeable:
            break
        _, left_index, right_index = min(mergeable)
        merged = sorted((*families[left_index], *families[right_index]), key=_hypothesis_rank)
        families = [
            family for index, family in enumerate(families)
            if index not in {left_index, right_index}
        ] + [merged]
        families.sort(key=lambda family: tuple(item["hypothesisId"] for item in family))
    representatives: list[dict[str, Any]] = []
    eligible_representatives: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []
    for index, family in enumerate(sorted(families, key=lambda items: _hypothesis_rank(min(items, key=_hypothesis_rank))), start=1):
        representative = min(family, key=_hypothesis_rank)
        family_id = f"wall-source-family-{index:03d}"
        representatives.append(representative)
        alignment_delta = _radial_line_alignment_deg(
            representative["line"], representative["intersection"], center,
        )
        alignment_passed = bool(
            math.isfinite(alignment_delta)
            and alignment_delta <= float(config["max_radial_alignment_delta_deg"])
        )
        if alignment_passed:
            eligible_representatives.append(representative)
        summaries.append({
            "familyId": family_id,
            "memberHypothesisIds": sorted(item["hypothesisId"] for item in family),
            "representativeHypothesisId": representative["hypothesisId"],
            "effectiveSupportCount": int(representative["supportCount"]),
            "residualP95Px": float(representative["residualP95Px"]),
            "longitudinalCoverage": float(representative["longitudinalCoverage"]),
            "intersectionAngleDeg": float(representative["intersectionAngleDeg"]),
            "canonicalLine": {
                "a": float(representative["line"][0]),
                "b": float(representative["line"][1]),
                "c": float(representative["line"][2]),
            },
            "radialAlignmentDeltaDeg": alignment_delta if math.isfinite(alignment_delta) else None,
            "radialAlignmentThresholdDeg": float(config["max_radial_alignment_delta_deg"]),
            "radialAlignmentPassed": alignment_passed,
        })
    representatives.sort(key=_hypothesis_rank)
    return representatives, {
        "wallFamilySchemaVersion": "groove-wall-source-family-diagnostic/1",
        "wallFamilyStrategyVersion": "shared-longitudinal-wall-family-v2",
        "rawHypothesisCount": len(unique),
        "physicalSourceFamilyCount": len(representatives),
        "eligiblePhysicalSourceFamilyCount": len(eligible_representatives),
        "sourceFamilyComparisons": comparisons,
        "sourceFamilySummaries": summaries,
        "wallFamilyRecoveryUsed": True,
        "_sourceFamilyRepresentatives": representatives,
        "_eligibleSourceFamilyRepresentatives": sorted(
            eligible_representatives, key=_hypothesis_rank,
        ),
    }


def _select_wall_family(
    candidate_rows: list[list[dict[str, Any]]], *, minimum: int,
    center: tuple[float, float], outer_radius: float, coarse_angle_deg: float,
    maximum_delta_deg: float, config: dict[str, Any], pixel_scale: float,
    max_hypotheses: int,
) -> dict[str, Any]:
    """Select one straight cross-radius edge family from bounded row candidates."""
    base = {
        "status": "not_found", "failedCheck": "wall_family_not_found",
        "candidateCount": sum(len(row) for row in candidate_rows),
        "seedCount": 0, "hypothesisCount": 0,
        "familySummaries": [],
        "bestSupportCount": None, "secondSupportCount": None,
        "supportMargin": None, "supportRowIndices": [], "selectedCandidates": [],
        "line": None, "residuals": None, "intersection": None,
        "intersectionAngleDeg": None, "longitudinalCoverage": None,
    }
    if len(candidate_rows) < minimum:
        return {**base, "failedCheck": "insufficient_rows"}
    finite_rows: list[list[dict[str, Any]]] = []
    for row in candidate_rows:
        finite = []
        for item in row:
            point = item.get("point") if isinstance(item, dict) else None
            if (
                isinstance(point, (tuple, list)) and len(point) == 2
                and all(math.isfinite(float(value)) for value in point)
            ):
                finite.append({**item, "point": (float(point[0]), float(point[1]))})
        finite.sort(key=lambda item: (item["point"][0], item["point"][1]))
        finite_rows.append(finite)
    residual_gate = float(config["max_line_residual_p95_px"]) * pixel_scale
    minimum_separation = max(
        1, int(math.ceil(
            float(config["line_consensus_min_pair_separation_ratio"])
            * max(1, len(finite_rows) - 1)
        )),
    )
    seeds: list[tuple[float, float, float]] = []
    nonempty_indices = [index for index, row in enumerate(finite_rows) if row]
    if len(nonempty_indices) > 8:
        anchor_positions = np.linspace(0, len(nonempty_indices) - 1, 8)
        anchor_indices = sorted({nonempty_indices[int(round(value))] for value in anchor_positions})
    else:
        anchor_indices = nonempty_indices
    for first_offset, first_row in enumerate(anchor_indices):
        for second_row in anchor_indices[first_offset + 1:]:
            if second_row - first_row < minimum_separation:
                continue
            for first in finite_rows[first_row]:
                for second in finite_rows[second_row]:
                    x1, y1 = first["point"]
                    x2, y2 = second["point"]
                    dx, dy = x2 - x1, y2 - y1
                    norm = math.hypot(dx, dy)
                    if norm <= 1e-9:
                        continue
                    a, b = -dy / norm, dx / norm
                    c = -(a * x1 + b * y1)
                    if a < 0.0 or (abs(a) <= 1e-12 and b < 0.0):
                        a, b, c = -a, -b, -c
                    seeds.append((a, b, c))
    base["seedCount"] = len(seeds)
    preliminary: dict[tuple[int, ...], dict[str, Any]] = {}
    for line in seeds:
        selected: list[tuple[int, dict[str, Any], float]] = []
        for row_index, row in enumerate(finite_rows):
            ranked = sorted(
                (
                    abs(line[0] * item["point"][0] + line[1] * item["point"][1] + line[2]),
                    item["point"][0], item["point"][1], item,
                )
                for item in row
            )
            if ranked and ranked[0][0] <= residual_gate:
                selected.append((row_index, ranked[0][3], float(ranked[0][0])))
        if len(selected) < minimum:
            continue
        key = tuple(
            value
            for row_index, item, _ in selected
            for value in (
                row_index,
                int(round(item["point"][0] * 1000.0)),
                int(round(item["point"][1] * 1000.0)),
            )
        )
        rank = (-len(selected), _small_percentile_95(np.asarray([item[2] for item in selected])))
        previous = preliminary.get(key)
        if previous is None or rank < previous["rank"]:
            preliminary[key] = {"line": line, "selected": selected, "rank": rank}
    selected_seeds = sorted(preliminary.values(), key=lambda item: item["rank"])[:max_hypotheses]
    hypotheses: list[dict[str, Any]] = []
    minimum_ratio = float(config["line_consensus_min_inlier_ratio"])
    minimum_coverage = float(config["line_consensus_min_span_ratio"])
    for seed in selected_seeds:
        selected = seed["selected"]
        for _ in range(4):
            points = np.asarray([item[1]["point"] for item in selected], dtype=float)
            try:
                line = _fit_line_tls(points)
            except (ValueError, np.linalg.LinAlgError):
                selected = []
                break
            updated: list[tuple[int, dict[str, Any], float]] = []
            for row_index, row in enumerate(finite_rows):
                ranked = sorted(
                    (
                        abs(line[0] * item["point"][0] + line[1] * item["point"][1] + line[2]),
                        item["point"][0], item["point"][1], item,
                    )
                    for item in row
                )
                if ranked and ranked[0][0] <= residual_gate:
                    updated.append((row_index, ranked[0][3], float(ranked[0][0])))
            if [(i, x["point"]) for i, x, _ in updated] == [
                (i, x["point"]) for i, x, _ in selected
            ]:
                selected = updated
                break
            selected = updated
        if len(selected) < minimum:
            continue
        row_indices = [item[0] for item in selected]
        ratio = len(selected) / len(finite_rows)
        coverage = (
            (max(row_indices) - min(row_indices)) / max(1, len(finite_rows) - 1)
        )
        if ratio < minimum_ratio or coverage < minimum_coverage:
            continue
        points = np.asarray([item[1]["point"] for item in selected], dtype=float)
        try:
            line = _fit_line_tls(points)
        except (ValueError, np.linalg.LinAlgError):
            continue
        residuals = np.abs(line[0] * points[:, 0] + line[1] * points[:, 1] + line[2])
        residual_p95 = _small_percentile_95(residuals)
        if residual_p95 > residual_gate:
            continue
        try:
            intersection, angle = _circle_intersection(
                line, center, outer_radius, coarse_angle_deg, maximum_delta_deg,
            )
        except ValueError:
            continue
        hypotheses.append({
            "line": line, "selected": selected, "residuals": residuals,
            "supportCount": len(selected), "supportRowIndices": row_indices,
            "longitudinalCoverage": coverage, "residualP95Px": residual_p95,
            "intersection": intersection, "intersectionAngleDeg": angle,
            "candidateSignature": frozenset(
                (
                    row_index,
                    int(round(item["point"][0] * 1000.0)),
                    int(round(item["point"][1] * 1000.0)),
                )
                for row_index, item, _ in selected
            ),
        })
    hypotheses.sort(key=lambda item: (
        -item["supportCount"], item["residualP95Px"],
        -item["longitudinalCoverage"], item["intersectionAngleDeg"],
    ))
    family_selection_started_ns = time.perf_counter_ns()
    def legacy_distinct_hypotheses() -> list[dict[str, Any]]:
        output: list[dict[str, Any]] = []
        merge_deg = float(config["line_consensus_model_merge_deg"])
        for hypothesis in hypotheses:
            if any(
                (
                    _circular_delta_abs(
                        hypothesis["intersectionAngleDeg"], existing["intersectionAngleDeg"],
                    ) <= merge_deg
                    or (
                        len(hypothesis["candidateSignature"] & existing["candidateSignature"])
                        / max(1, len(hypothesis["candidateSignature"] | existing["candidateSignature"]))
                        >= float(config["line_consensus_min_inlier_ratio"])
                    )
                )
                for existing in output
            ):
                continue
            output.append(hypothesis)
        return output

    def has_unique_best(items: list[dict[str, Any]]) -> bool:
        if not items:
            return False
        best_item = items[0]
        minimum_margin = int(config["line_consensus_min_support_margin"])
        close = [
            item for item in items[1:]
            if best_item["supportCount"] - item["supportCount"] < minimum_margin
        ]
        return not any(
            not (
                best_item["supportCount"] >= item["supportCount"]
                and best_item["residualP95Px"] <= item["residualP95Px"]
                and best_item["longitudinalCoverage"] >= item["longitudinalCoverage"]
                and (
                    best_item["supportCount"] > item["supportCount"]
                    or best_item["residualP95Px"] < item["residualP95Px"]
                    or best_item["longitudinalCoverage"] > item["longitudinalCoverage"]
                )
            )
            for item in close
        )

    family_config = config.get("wall_edge_family", DEFAULT_WALL_EDGE_FAMILY_CONFIG)
    source_diagnostic: dict[str, Any] = {}
    if family_config.get("strategy_version") == "shared-longitudinal-wall-family-v2":
        legacy_distinct = legacy_distinct_hypotheses()
        _, source_diagnostic = _group_wall_source_families(
            hypotheses, center=center, config=family_config, pixel_scale=pixel_scale,
        )
        distinct = source_diagnostic.pop("_eligibleSourceFamilyRepresentatives")
        source_representatives = source_diagnostic.pop("_sourceFamilyRepresentatives", [])
        source_diagnostic["radialEligibilityFallbackApplied"] = False
        source_diagnostic["legacyAcceptedRepresentativePreserved"] = False
        if has_unique_best(legacy_distinct):
            distinct = legacy_distinct
            source_diagnostic["legacyAcceptedRepresentativePreserved"] = True
        elif not distinct and source_representatives:
            distinct = legacy_distinct
            source_diagnostic["radialEligibilityFallbackApplied"] = True
    else:
        distinct = legacy_distinct_hypotheses()
    if not distinct:
        return {
            **base, **source_diagnostic, "hypothesisCount": 0,
            **({
                "selectedPhysicalSourceFamilyId": None,
                "wallFamilySelectionElapsedMs": (
                    time.perf_counter_ns() - family_selection_started_ns
                ) / 1e6,
            } if source_diagnostic else {}),
        }
    best = distinct[0]
    second = distinct[1] if len(distinct) > 1 else None
    margin = None if second is None else best["supportCount"] - second["supportCount"]
    minimum_support_margin = int(config["line_consensus_min_support_margin"])
    close_competitors = [
        item for item in distinct[1:]
        if best["supportCount"] - item["supportCount"] < minimum_support_margin
    ]
    nondominated_close = [
        item for item in close_competitors
        if not (
            best["supportCount"] >= item["supportCount"]
            and best["residualP95Px"] <= item["residualP95Px"]
            and best["longitudinalCoverage"] >= item["longitudinalCoverage"]
            and (
                best["supportCount"] > item["supportCount"]
                or best["residualP95Px"] < item["residualP95Px"]
                or best["longitudinalCoverage"] > item["longitudinalCoverage"]
            )
        )
    ]
    common = {
        **base, **source_diagnostic, "hypothesisCount": len(distinct),
        "familySummaries": [{
            "familyId": f"wall-family-{index:03d}",
            "supportCount": item["supportCount"],
            "residualP95Px": item["residualP95Px"],
            "longitudinalCoverage": item["longitudinalCoverage"],
            "intersectionAngleDeg": item["intersectionAngleDeg"],
        } for index, item in enumerate(distinct[:8], start=1)],
        "bestSupportCount": best["supportCount"],
        "secondSupportCount": None if second is None else second["supportCount"],
        "supportMargin": margin,
    }
    if source_diagnostic:
        selected_summary = next(
            (
                item for item in source_diagnostic["sourceFamilySummaries"]
                if best["hypothesisId"] in item["memberHypothesisIds"]
            ), None,
        )
        common.update({
            "selectedPhysicalSourceFamilyId": (
                None if selected_summary is None else selected_summary["familyId"]
            ),
            "wallFamilySelectionElapsedMs": (
                time.perf_counter_ns() - family_selection_started_ns
            ) / 1e6,
        })
    if nondominated_close:
        return {**common, "status": "ambiguous", "failedCheck": "wall_family_ambiguous"}
    return {
        **common, "status": "accepted", "failedCheck": None,
        "supportRowIndices": best["supportRowIndices"],
        "selectedCandidates": [item[1] for item in best["selected"]],
        "line": best["line"], "residuals": best["residuals"],
        "intersection": best["intersection"],
        "intersectionAngleDeg": best["intersectionAngleDeg"],
        "longitudinalCoverage": best["longitudinalCoverage"],
    }


def _side_points(
    gray: np.ndarray,
    center: tuple[float, float],
    radii: np.ndarray,
    coarse_angle_deg: float,
    polarity: str,
    bilinear_sample: Callable[[np.ndarray, np.ndarray, np.ndarray], np.ndarray],
    parabolic_peak: Callable[[list[float], int], float],
    config: dict[str, Any],
) -> tuple[list[tuple[float, float]], list[float], list[float], list[dict[str, Any]]]:
    points: list[tuple[float, float]] = []
    contrasts: list[float] = []
    gradients: list[float] = []
    observations: list[dict[str, Any]] = []
    margin_deg = float(config["tangential_search_margin_deg"])
    target_step_px = float(config["tangential_sample_step_px"])
    inner_offset = float(config["contrast_inner_offset_px"])
    outer_offset = float(config["contrast_outer_offset_px"])
    for radius in radii:
        extent_px = radius * math.radians(margin_deg)
        count = max(15, int(math.ceil(2.0 * extent_px / target_step_px)) + 1)
        tangent = np.linspace(-extent_px, extent_px, count, dtype=float)
        angle_deg = coarse_angle_deg + np.degrees(tangent / radius)
        radians = np.radians(angle_deg)
        xs = center[0] + radius * np.cos(radians)
        ys = center[1] + radius * np.sin(radians)
        values = np.asarray(bilinear_sample(gray, xs, ys), dtype=float)
        if values.shape != tangent.shape or not np.isfinite(values).all():
            continue
        # Preserve edge position while suppressing pixel texture.
        smooth = np.convolve(values, np.asarray([1.0, 2.0, 1.0]) / 4.0, mode="same")
        gradient = np.gradient(smooth, tangent)
        signed = -gradient if polarity == "falling" else gradient
        guard = max(3, int(math.ceil(inner_offset / max(target_step_px, 1e-9))))
        if len(signed) <= 2 * guard + 3:
            continue
        local_index = int(np.argmax(signed[guard:-guard])) + guard
        delta = float(parabolic_peak(signed.tolist(), local_index))
        delta = max(-1.0, min(1.0, delta))
        step_px = float(tangent[1] - tangent[0])
        refined_tangent = float(tangent[local_index] + delta * step_px)
        before = (tangent >= refined_tangent - outer_offset) & (tangent <= refined_tangent - inner_offset)
        after = (tangent >= refined_tangent + inner_offset) & (tangent <= refined_tangent + outer_offset)
        if int(np.count_nonzero(before)) < 2 or int(np.count_nonzero(after)) < 2:
            continue
        before_level = float(np.median(values[before]))
        after_level = float(np.median(values[after]))
        contrast = before_level - after_level if polarity == "falling" else after_level - before_level
        strength = float(signed[local_index])
        if contrast < float(config["min_edge_contrast"]) or strength < float(config["min_edge_gradient_per_px"]):
            continue
        refined_angle = math.radians(coarse_angle_deg + math.degrees(refined_tangent / radius))
        points.append((
            center[0] + radius * math.cos(refined_angle),
            center[1] + radius * math.sin(refined_angle),
        ))
        contrasts.append(contrast)
        gradients.append(strength)
        local_offsets = np.linspace(-outer_offset, outer_offset, 17, dtype=float)
        canonical_offsets = local_offsets if polarity == "falling" else -local_offsets
        local_profile = np.interp(refined_tangent + canonical_offsets, tangent, values)
        observations.append({
            "radiusPx": float(radius),
            "contrast": contrast,
            "gradient": strength,
            "metalLevel": before_level if polarity == "falling" else after_level,
            "grooveLevel": after_level if polarity == "falling" else before_level,
            "canonicalGrayProfile": [float(value) for value in local_profile],
        })
    return points, contrasts, gradients, observations


def _side_candidate_rows(
    gray: np.ndarray,
    center: tuple[float, float],
    radii: np.ndarray,
    coarse_angle_deg: float,
    polarity: str,
    bilinear_sample: Callable[[np.ndarray, np.ndarray, np.ndarray], np.ndarray],
    parabolic_peak: Callable[[list[float], int], float],
    config: dict[str, Any],
) -> list[list[dict[str, Any]]]:
    """Sample each radial row once and retain bounded polarity-correct peaks."""
    family = config["wall_edge_family"]
    rows: list[list[dict[str, Any]]] = []
    margin_deg = float(config["tangential_search_margin_deg"])
    target_step_px = float(config["tangential_sample_step_px"])
    inner_offset = float(config["contrast_inner_offset_px"])
    outer_offset = float(config["contrast_outer_offset_px"])
    for radius in radii:
        extent_px = radius * math.radians(margin_deg)
        count = max(15, int(math.ceil(2.0 * extent_px / target_step_px)) + 1)
        tangent = np.linspace(-extent_px, extent_px, count, dtype=float)
        angle_deg = coarse_angle_deg + np.degrees(tangent / radius)
        radians = np.radians(angle_deg)
        xs = center[0] + radius * np.cos(radians)
        ys = center[1] + radius * np.sin(radians)
        values = np.asarray(bilinear_sample(gray, xs, ys), dtype=float)
        if values.shape != tangent.shape or not np.isfinite(values).all():
            rows.append([])
            continue
        smooth = np.convolve(values, np.asarray([1.0, 2.0, 1.0]) / 4.0, mode="same")
        gradient = np.gradient(smooth, tangent)
        signed = -gradient if polarity == "falling" else gradient
        guard = max(3, int(math.ceil(inner_offset / max(target_step_px, 1e-9))))
        peak_indices = [
            index for index in range(guard, len(signed) - guard)
            if signed[index] >= signed[index - 1]
            and signed[index] > signed[index + 1]
            and signed[index] >= float(config["min_edge_gradient_per_px"])
        ]
        peak_indices.sort(key=lambda index: (-float(signed[index]), float(tangent[index])))
        accepted_offsets: list[float] = []
        candidates: list[dict[str, Any]] = []
        for local_index in peak_indices:
            delta = max(-1.0, min(1.0, float(parabolic_peak(signed.tolist(), local_index))))
            step_px = float(tangent[1] - tangent[0])
            refined_tangent = float(tangent[local_index] + delta * step_px)
            if any(
                abs(refined_tangent - existing) < float(family["min_peak_separation_px"])
                for existing in accepted_offsets
            ):
                continue
            before = (
                (tangent >= refined_tangent - outer_offset)
                & (tangent <= refined_tangent - inner_offset)
            )
            after = (
                (tangent >= refined_tangent + inner_offset)
                & (tangent <= refined_tangent + outer_offset)
            )
            if int(np.count_nonzero(before)) < 2 or int(np.count_nonzero(after)) < 2:
                continue
            before_level = float(np.median(values[before]))
            after_level = float(np.median(values[after]))
            contrast = (
                before_level - after_level if polarity == "falling"
                else after_level - before_level
            )
            strength = float(signed[local_index])
            if contrast < float(config["min_edge_contrast"]):
                continue
            refined_angle = math.radians(
                coarse_angle_deg + math.degrees(refined_tangent / radius)
            )
            local_offsets = np.linspace(-outer_offset, outer_offset, 17, dtype=float)
            canonical_offsets = local_offsets if polarity == "falling" else -local_offsets
            local_profile = np.interp(refined_tangent + canonical_offsets, tangent, values)
            accepted_offsets.append(refined_tangent)
            candidates.append({
                "point": (
                    center[0] + radius * math.cos(refined_angle),
                    center[1] + radius * math.sin(refined_angle),
                ),
                "radiusPx": float(radius), "tangentialOffsetPx": refined_tangent,
                "contrast": contrast, "gradient": strength, "strength": strength,
                "metalLevel": before_level if polarity == "falling" else after_level,
                "grooveLevel": after_level if polarity == "falling" else before_level,
                "canonicalGrayProfile": [float(value) for value in local_profile],
            })
            if len(candidates) >= int(family["max_peaks_per_row"]):
                break
        rows.append(candidates)
    return rows


def _profile_evidence(
    observations: list[dict[str, Any]], all_radii: np.ndarray,
) -> dict[str, Any] | None:
    if not observations:
        return None
    profiles = np.asarray([item["canonicalGrayProfile"] for item in observations], dtype=float)
    raw_profile = np.median(profiles, axis=0)
    low, high = float(np.min(raw_profile)), float(np.max(raw_profile))
    normalized = (
        np.zeros_like(raw_profile) if high - low <= 1e-9
        else (raw_profile - low) / (high - low)
    )
    outer, inner = float(np.max(all_radii)), float(np.min(all_radii))
    span = max(outer - inner, 1e-9)
    radial = [(outer - float(item["radiusPx"])) / span for item in observations]
    coverage = max(radial) - min(radial) if len(radial) > 1 else 0.0
    return {
        "schemaVersion": "groove-sidewall-local-profile/1",
        "canonicalDirection": "metal_to_dark",
        "radialPositionsNormalized": [float(value) for value in radial],
        "edgeContrastProfile": [float(item["contrast"]) for item in observations],
        "edgeGradientProfile": [float(item["gradient"]) for item in observations],
        "metalLevelProfile": [float(item["metalLevel"]) for item in observations],
        "grooveLevelProfile": [float(item["grooveLevel"]) for item in observations],
        "metalLevelMedian": float(np.median([item["metalLevel"] for item in observations])),
        "grooveLevelMedian": float(np.median([item["grooveLevel"] for item in observations])),
        "rawCanonicalGrayProfile": [float(value) for value in raw_profile],
        "normalizedCanonicalGrayProfile": [float(value) for value in normalized],
        "radialCoverage": float(coverage),
    }


def _circle_intersection(
    line: tuple[float, float, float], center: tuple[float, float], radius: float,
    coarse_angle_deg: float, maximum_delta_deg: float,
) -> tuple[tuple[float, float], float]:
    a, b, c = line
    signed_distance = a * center[0] + b * center[1] + c
    distance = abs(signed_distance)
    if not math.isfinite(distance) or distance >= radius:
        raise ValueError("sidewall line does not intersect outer circle")
    foot_x = center[0] - a * signed_distance
    foot_y = center[1] - b * signed_distance
    extent = math.sqrt(max(0.0, radius * radius - distance * distance))
    direction = (-b, a)
    intersections = [
        (foot_x + extent * direction[0], foot_y + extent * direction[1]),
        (foot_x - extent * direction[0], foot_y - extent * direction[1]),
    ]
    ranked = sorted(
        ((_profile_angle(point, center), point) for point in intersections),
        key=lambda item: circular_distance_deg(item[0], coarse_angle_deg),
    )
    selected_angle, selected = ranked[0]
    if circular_distance_deg(selected_angle, coarse_angle_deg) > maximum_delta_deg:
        raise ValueError("sidewall intersection is not near coarse boundary")
    if abs(
        circular_distance_deg(ranked[0][0], coarse_angle_deg)
        - circular_distance_deg(ranked[1][0], coarse_angle_deg)
    ) < 1e-6:
        raise ValueError("sidewall intersection is ambiguous")
    return (float(selected[0]), float(selected[1])), selected_angle


def _empty_result(candidate_id: str | None, config: dict[str, Any], failures: list[str]) -> dict[str, Any]:
    family_enabled = bool(config.get("wall_edge_family", {}).get("enabled", False))
    family_v2 = bool(
        family_enabled
        and config.get("wall_edge_family", {}).get("strategy_version")
        == "shared-longitudinal-wall-family-v2"
    )
    return {
        "schemaVersion": (
            SCHEMA_VERSION_V4 if family_v2 else SCHEMA_VERSION_V3 if family_enabled else (
                SCHEMA_VERSION_V2
                if config["threshold_version"] == THRESHOLD_VERSION_V2 else SCHEMA_VERSION
            )
        ),
        "thresholdVersion": config["threshold_version"],
        "status": "failed",
        "coarseCandidateId": candidate_id,
        "startSide": None,
        "endSide": None,
        "outerCircleIntersections": None,
        "intersectionCircleResidualPx": None,
        "openingEndpointProfileDeg": None,
        "openingWidthDeg": None,
        "openingMidpointProfileDeg": None,
        "failedChecks": list(dict.fromkeys(failures)),
    }


def refine_groove_opening(
    gray: np.ndarray,
    center: tuple[float, float],
    outer_radius: float,
    candidate: dict[str, Any],
    bilinear_sample: Callable[[np.ndarray, np.ndarray, np.ndarray], np.ndarray],
    parabolic_peak: Callable[[list[float], int], float],
    config: dict[str, Any] | None,
    *,
    pixel_scale: float = 1.0,
) -> dict[str, Any]:
    """Refine both groove sides and intersect their robust lines with the outer circle."""
    started_ns = time.perf_counter_ns()

    def finish(result: dict[str, Any]) -> dict[str, Any]:
        result["elapsedMs"] = (time.perf_counter_ns() - started_ns) / 1e6
        return result

    merged = merged_groove_refinement_config(config)
    candidate_id = str(candidate.get("candidateId")) if candidate.get("candidateId") is not None else None
    array = np.asarray(gray)
    geometry = (*center, outer_radius, pixel_scale)
    if array.ndim != 2 or not np.isfinite(array).all():
        return finish(_empty_result(candidate_id, merged, ["invalid_image"]))
    if len(center) != 2 or not all(math.isfinite(float(value)) for value in geometry) or outer_radius <= 0.0 or pixel_scale <= 0.0:
        return finish(_empty_result(candidate_id, merged, ["invalid_circle"]))
    try:
        start = float(candidate["startDeg"]) % 360.0
        end = float(candidate["endDeg"]) % 360.0
        depth = float(candidate["radialDepthPx"])
    except (KeyError, TypeError, ValueError):
        return finish(_empty_result(candidate_id, merged, ["invalid_candidate"]))
    if not all(math.isfinite(value) for value in (start, end, depth)) or depth <= 0.0:
        return finish(_empty_result(candidate_id, merged, ["invalid_candidate"]))
    span = (end - start) % 360.0
    if span > 180.0:
        if not merged["allow_endpoint_reversal"]:
            return finish(_empty_result(candidate_id, merged, ["coarse_endpoint_order"]))
        start, end = end, start
        span = (end - start) % 360.0
    if span <= 0.0 or span >= 180.0:
        return finish(_empty_result(candidate_id, merged, ["invalid_coarse_opening"]))

    min_inset = float(merged["radial_inset_min_px"]) * pixel_scale
    max_inset = min(
        float(merged["radial_inset_max_px"]) * pixel_scale,
        max(0.0, 0.80 * depth),
    )
    if max_inset <= min_inset:
        return finish(_empty_result(candidate_id, merged, ["insufficient_radial_depth"]))
    radii = outer_radius - np.linspace(
        min_inset, max_inset, int(merged["radial_sample_count"]), dtype=float,
    )
    radii = radii[radii > 1.0]
    if len(radii) < int(merged["min_side_points"]):
        return finish(_empty_result(candidate_id, merged, ["insufficient_radial_support"]))

    sides: dict[str, dict[str, Any]] = {}
    failures: list[str] = []
    intersections: list[tuple[float, float]] = []
    endpoint_angles: list[float] = []
    for name, coarse, polarity in (("startSide", start, "falling"), ("endSide", end, "rising")):
        family_enabled = bool(merged.get("wall_edge_family", {}).get("enabled", False))
        if family_enabled:
            wall_family_strategy = str(merged["wall_edge_family"]["strategy_version"])
            candidate_rows = _side_candidate_rows(
                array, center, radii, coarse, polarity,
                bilinear_sample, parabolic_peak, merged,
            )
            strongest = [row[0] for row in candidate_rows if row]
            strongest_points = [item["point"] for item in strongest]
            original = _select_consensus_line(
                strongest_points, minimum=int(merged["min_side_points"]), center=center,
                outer_radius=outer_radius, coarse_angle_deg=coarse,
                maximum_delta_deg=float(merged["max_intersection_coarse_delta_deg"]),
                config=merged, pixel_scale=pixel_scale,
            )
            original_summary = {
                "status": original["status"], "failedCheck": original["failedCheck"],
                "detectedPointCount": original["detectedPointCount"],
                "bestSupportCount": original["bestSupportCount"],
                "secondSupportCount": original["secondSupportCount"],
                "supportMargin": original["supportMargin"],
            }
            original_accepted = original["status"] == "accepted"
            decision = (
                {
                    "status": "not_evaluated", "failedCheck": None,
                    "candidateCount": sum(len(row) for row in candidate_rows),
                    "seedCount": 0, "hypothesisCount": 0, "familySummaries": [],
                    "bestSupportCount": None, "secondSupportCount": None,
                    "supportMargin": None,
                }
                if original_accepted else _select_wall_family(
                    candidate_rows, minimum=int(merged["min_side_points"]), center=center,
                    outer_radius=outer_radius, coarse_angle_deg=coarse,
                    maximum_delta_deg=float(merged["tangential_search_margin_deg"]),
                    config=merged, pixel_scale=pixel_scale,
                    max_hypotheses=int(merged["wall_edge_family"]["max_hypotheses"]),
                )
            )
            if not original_accepted and decision["status"] != "accepted":
                failures.append(f"{name}_{decision['failedCheck']}")
                sides[name] = {
                    "lineFitStrategy": wall_family_strategy,
                    "wallFamilyRecoveryUsed": True,
                    "sampledPointCount": int(len(radii)),
                    "candidatePointCount": int(decision["candidateCount"]),
                    "wallFamilyStatus": decision["status"],
                    "wallFamilyFailedCheck": decision["failedCheck"],
                    "wallFamilySeedCount": decision["seedCount"],
                    "wallFamilyHypothesisCount": decision["hypothesisCount"],
                    "wallFamilySummaries": decision["familySummaries"],
                    **{
                        key: decision[key] for key in (
                            "wallFamilySchemaVersion", "wallFamilyStrategyVersion",
                            "rawHypothesisCount", "physicalSourceFamilyCount",
                            "eligiblePhysicalSourceFamilyCount",
                            "selectedPhysicalSourceFamilyId",
                            "wallFamilySelectionElapsedMs",
                            "radialEligibilityFallbackApplied",
                            "legacyAcceptedRepresentativePreserved",
                            "sourceFamilyComparisons", "sourceFamilySummaries",
                        ) if key in decision
                    },
                    "bestSupportCount": decision["bestSupportCount"],
                    "secondSupportCount": decision["secondSupportCount"],
                    "supportMargin": decision["supportMargin"],
                    "originalStrongestEdgeDecision": original_summary,
                    "profileEvidence": None, "line": None,
                    "lineResidualPx": None, "points": [],
                }
                continue
            if original_accepted:
                original_mask = np.asarray(original["inlierMask"], dtype=bool)
                selected = [
                    item for item, keep in zip(strongest, original_mask, strict=True) if keep
                ]
                effective_line = original["line"]
                effective_residuals = np.asarray(original["residuals"], dtype=float)
                effective_intersection = original["intersection"]
                effective_angle = original["intersectionAngleDeg"]
                effective_coverage = original["longitudinalCoverage"]
                effective_strategy = "deterministic-consensus-tls-v2-preserved"
            else:
                selected = decision["selectedCandidates"]
                effective_line = decision["line"]
                effective_residuals = np.asarray(decision["residuals"], dtype=float)
                effective_intersection = decision["intersection"]
                effective_angle = decision["intersectionAngleDeg"]
                effective_coverage = decision["longitudinalCoverage"]
                effective_strategy = wall_family_strategy
            points = [item["point"] for item in selected]
            contrasts = [float(item["contrast"]) for item in selected]
            gradients = [float(item["gradient"]) for item in selected]
            observations = [{
                key: item[key] for key in (
                    "radiusPx", "contrast", "gradient", "metalLevel", "grooveLevel",
                    "canonicalGrayProfile",
                )
            } for item in selected]
            profile_evidence = _profile_evidence(observations, radii)
            line = effective_line
            residuals = effective_residuals
            intersection = effective_intersection
            angle = effective_angle
            radial_alignment = _radial_line_alignment_deg(line, intersection, center)
            radial_threshold = float(
                merged["wall_edge_family"].get("max_radial_alignment_delta_deg", 8.0)
            )
            sides[name] = {
                "lineFitStrategy": effective_strategy,
                "wallFamilyRecoveryUsed": not original_accepted,
                "sampledPointCount": int(len(radii)),
                "candidatePointCount": int(decision["candidateCount"]),
                "supportPointCount": len(points),
                "rejectedPointCount": int(decision["candidateCount"] - len(points)),
                "edgeContrastMedian": float(np.median(contrasts)),
                "edgeGradientMedianPerPx": float(np.median(gradients)),
                "profileEvidence": profile_evidence,
                "wallFamilyStatus": "not_needed" if original_accepted else decision["status"],
                "wallFamilyFailedCheck": None,
                "wallFamilySeedCount": decision["seedCount"],
                "wallFamilyHypothesisCount": decision["hypothesisCount"],
                "wallFamilySummaries": decision["familySummaries"],
                **{
                    key: decision[key] for key in (
                        "wallFamilySchemaVersion", "wallFamilyStrategyVersion",
                        "rawHypothesisCount", "physicalSourceFamilyCount",
                        "eligiblePhysicalSourceFamilyCount",
                        "selectedPhysicalSourceFamilyId",
                        "wallFamilySelectionElapsedMs",
                        "radialEligibilityFallbackApplied",
                        "legacyAcceptedRepresentativePreserved",
                        "sourceFamilyComparisons", "sourceFamilySummaries",
                    ) if key in decision
                },
                "bestSupportCount": decision["bestSupportCount"],
                "secondSupportCount": decision["secondSupportCount"],
                "supportMargin": decision["supportMargin"],
                "radialAlignmentDeltaDeg": (
                    radial_alignment if math.isfinite(radial_alignment) else None
                ),
                "radialAlignmentThresholdDeg": radial_threshold,
                "radialAlignmentPassed": bool(
                    math.isfinite(radial_alignment)
                    and radial_alignment <= radial_threshold
                ),
                "lineLongitudinalCoverage": effective_coverage,
                "originalStrongestEdgeDecision": original_summary,
                "line": {"a": line[0], "b": line[1], "c": line[2]},
                "lineResidualPx": _summary(residuals),
                "points": [[float(value) for value in point] for point in points],
            }
            intersections.append(intersection)
            endpoint_angles.append(angle)
            continue
        points, contrasts, gradients, observations = _side_points(
            array, center, radii, coarse, polarity, bilinear_sample, parabolic_peak, merged,
        )
        profile_evidence = _profile_evidence(observations, radii)
        if len(points) < int(merged["min_side_points"]):
            failures.append(f"{name}_insufficient_support")
            sides[name] = {
                "supportPointCount": len(points), "sampledPointCount": int(len(radii)),
                "edgeContrastMedian": None if not contrasts else float(np.median(contrasts)),
                "edgeGradientMedianPerPx": None if not gradients else float(np.median(gradients)),
                "profileEvidence": profile_evidence,
                "line": None, "lineResidualPx": None, "points": [list(point) for point in points],
            }
            continue
        if merged["threshold_version"] == THRESHOLD_VERSION_V2:
            decision = _select_consensus_line(
                points, minimum=int(merged["min_side_points"]), center=center,
                outer_radius=outer_radius, coarse_angle_deg=coarse,
                maximum_delta_deg=float(merged["max_intersection_coarse_delta_deg"]),
                config=merged, pixel_scale=pixel_scale,
            )
            if decision["status"] != "accepted":
                failures.append(f"{name}_{decision['failedCheck']}")
                sides[name] = {
                    "detectedPointCount": len(points), "supportPointCount": 0,
                    "sampledPointCount": int(len(radii)),
                    "rejectedPointCount": len(points),
                    "edgeContrastMedian": float(np.median(contrasts)),
                    "edgeGradientMedianPerPx": float(np.median(gradients)),
                    "profileEvidence": profile_evidence,
                    "lineFitStrategy": "deterministic-consensus-tls-v2",
                    "lineConsensusGatePx": float(merged["max_line_residual_p95_px"]) * pixel_scale,
                    "lineInlierRatio": decision["inlierRatio"],
                    "lineLongitudinalCoverage": decision["longitudinalCoverage"],
                    "rawLineHypothesisCount": decision["rawHypothesisCount"],
                    "refitLineHypothesisCount": decision["refitHypothesisCount"],
                    "lineHypothesisCount": decision["hypothesisCount"],
                    "bestModelId": decision["bestModelId"], "secondModelId": decision["secondModelId"],
                    "bestSupportCount": decision["bestSupportCount"],
                    "secondSupportCount": decision["secondSupportCount"],
                    "supportMargin": decision["supportMargin"],
                    "line": None, "lineResidualPx": None,
                    "detectedPoints": [list(map(float, point)) for point in points],
                    "points": [], "rejectedPoints": [list(map(float, point)) for point in points],
                }
                continue
            mask = np.asarray(decision["inlierMask"], dtype=bool)
            point_array = np.asarray(points, dtype=float)
            kept = point_array[mask]
            rejected = point_array[~mask]
            line = decision["line"]
            residuals = np.asarray(decision["residuals"], dtype=float)
            intersection = decision["intersection"]
            angle = decision["intersectionAngleDeg"]
            residual_summary = _summary(residuals)
            sides[name] = {
                "detectedPointCount": len(points), "supportPointCount": int(len(kept)),
                "sampledPointCount": int(len(radii)), "rejectedPointCount": int(len(rejected)),
                "edgeContrastMedian": float(np.median(contrasts)),
                "edgeGradientMedianPerPx": float(np.median(gradients)),
                "profileEvidence": profile_evidence,
                "lineFitStrategy": "deterministic-consensus-tls-v2",
                "lineConsensusGatePx": float(merged["max_line_residual_p95_px"]) * pixel_scale,
                "lineInlierRatio": decision["inlierRatio"],
                "lineLongitudinalCoverage": decision["longitudinalCoverage"],
                "rawLineHypothesisCount": decision["rawHypothesisCount"],
                "refitLineHypothesisCount": decision["refitHypothesisCount"],
                "lineHypothesisCount": decision["hypothesisCount"],
                "bestModelId": decision["bestModelId"], "secondModelId": decision["secondModelId"],
                "bestSupportCount": decision["bestSupportCount"],
                "secondSupportCount": decision["secondSupportCount"],
                "supportMargin": decision["supportMargin"],
                "line": {"a": line[0], "b": line[1], "c": line[2]},
                "lineResidualPx": residual_summary,
                "detectedPoints": [[float(value) for value in point] for point in point_array],
                "points": [[float(value) for value in point] for point in kept],
                "rejectedPoints": [[float(value) for value in point] for point in rejected],
            }
        else:
            try:
                line, kept, residuals = _robust_fit_line(points, int(merged["min_side_points"]))
            except (ValueError, np.linalg.LinAlgError):
                failures.append(f"{name}_line_fit")
                continue
            residual_summary = _summary(residuals)
            if residual_summary["p95"] > float(merged["max_line_residual_p95_px"]) * pixel_scale:
                failures.append(f"{name}_line_residual")
            try:
                intersection, angle = _circle_intersection(
                    line, center, outer_radius, coarse,
                    float(merged["max_intersection_coarse_delta_deg"]),
                )
            except ValueError:
                failures.append(f"{name}_intersection")
                intersection, angle = None, None
            sides[name] = {
                "supportPointCount": int(len(kept)),
                "sampledPointCount": int(len(radii)),
                "edgeContrastMedian": float(np.median(contrasts)),
                "edgeGradientMedianPerPx": float(np.median(gradients)),
                "profileEvidence": profile_evidence,
                "line": {"a": line[0], "b": line[1], "c": line[2]},
                "lineResidualPx": residual_summary,
                "points": [[float(value) for value in point] for point in kept],
            }
        if intersection is not None and angle is not None:
            intersections.append(intersection)
            endpoint_angles.append(angle)

    if failures or len(intersections) != 2:
        result = _empty_result(candidate_id, merged, failures or ["intersection_count"])
        result["startSide"] = sides.get("startSide")
        result["endSide"] = sides.get("endSide")
        return finish(result)
    refined_width = (endpoint_angles[1] - endpoint_angles[0]) % 360.0
    if refined_width <= 0.0 or refined_width >= 180.0:
        result = _empty_result(candidate_id, merged, ["refined_endpoint_order"])
        result["startSide"] = sides.get("startSide")
        result["endSide"] = sides.get("endSide")
        return finish(result)
    midpoint = wrap_360_deg(endpoint_angles[0] + refined_width / 2.0)
    circle_residuals = [
        abs(math.hypot(point[0] - center[0], point[1] - center[1]) - outer_radius)
        for point in intersections
    ]
    return finish({
        "schemaVersion": (
            SCHEMA_VERSION_V4 if bool(
                merged.get("wall_edge_family", {}).get("enabled", False)
                and merged.get("wall_edge_family", {}).get("strategy_version")
                == "shared-longitudinal-wall-family-v2"
            ) else SCHEMA_VERSION_V3 if bool(
                merged.get("wall_edge_family", {}).get("enabled", False)
            ) else (
                SCHEMA_VERSION_V2
                if merged["threshold_version"] == THRESHOLD_VERSION_V2 else SCHEMA_VERSION
            )
        ),
        "thresholdVersion": merged["threshold_version"],
        "status": "accepted",
        "coarseCandidateId": candidate_id,
        "startSide": sides["startSide"],
        "endSide": sides["endSide"],
        "outerCircleIntersections": [
            {"x": float(point[0]), "y": float(point[1])} for point in intersections
        ],
        "intersectionCircleResidualPx": circle_residuals,
        "openingEndpointProfileDeg": endpoint_angles,
        "openingWidthDeg": refined_width,
        "openingMidpointProfileDeg": midpoint,
        "failedChecks": [],
    })
