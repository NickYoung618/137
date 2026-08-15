"""Subpixel groove-side refinement and sidewall/outer-circle intersections."""

from __future__ import annotations

import math
import time
from typing import Any, Callable

import numpy as np

from algorithms.slot_pose.angular_profile import circular_distance_deg, wrap_360_deg


SCHEMA_VERSION = "slot-groove-subpixel-opening/1"
SCHEMA_VERSION_V2 = "slot-groove-subpixel-opening/2"
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


def validate_groove_refinement_config(config: dict[str, Any]) -> None:
    if not isinstance(config, dict):
        raise ValueError("groove_refinement must be an object")
    required = set(DEFAULT_GROOVE_REFINEMENT_CONFIG)
    missing = sorted(required - set(config))
    unexpected = sorted(set(config) - required)
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


def _side_points(
    gray: np.ndarray,
    center: tuple[float, float],
    radii: np.ndarray,
    coarse_angle_deg: float,
    polarity: str,
    bilinear_sample: Callable[[np.ndarray, np.ndarray, np.ndarray], np.ndarray],
    parabolic_peak: Callable[[list[float], int], float],
    config: dict[str, Any],
) -> tuple[list[tuple[float, float]], list[float], list[float]]:
    points: list[tuple[float, float]] = []
    contrasts: list[float] = []
    gradients: list[float] = []
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
    return points, contrasts, gradients


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
    return {
        "schemaVersion": (
            SCHEMA_VERSION_V2 if config["threshold_version"] == THRESHOLD_VERSION_V2 else SCHEMA_VERSION
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
        points, contrasts, gradients = _side_points(
            array, center, radii, coarse, polarity, bilinear_sample, parabolic_peak, merged,
        )
        if len(points) < int(merged["min_side_points"]):
            failures.append(f"{name}_insufficient_support")
            sides[name] = {
                "supportPointCount": len(points), "sampledPointCount": int(len(radii)),
                "edgeContrastMedian": None if not contrasts else float(np.median(contrasts)),
                "edgeGradientMedianPerPx": None if not gradients else float(np.median(gradients)),
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
            SCHEMA_VERSION_V2 if merged["threshold_version"] == THRESHOLD_VERSION_V2 else SCHEMA_VERSION
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
