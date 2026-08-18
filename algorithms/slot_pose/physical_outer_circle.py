"""Fail-closed quality wrapper around the locked gyj physical-circle core."""

from __future__ import annotations

import itertools
import math
import time
from typing import Any, Callable

import numpy as np


DEFAULT_PHYSICAL_OUTER_CIRCLE_CONFIG: dict[str, Any] = {
    "threshold_version": "gyj-outer-boundary+slot-quality-v2",
    "n_angles": 720,
    "min_edge_point_count": 180,
    "inlier_residual_px": 8.0,
    "min_inlier_ratio": 0.75,
    "angular_bin_count": 36,
    "min_angular_coverage": 0.65,
    "max_residual_p95_px": 5.0,
    "max_center_shift_px": 80.0,
    "min_radius_ratio": 0.94,
    "max_radius_ratio": 1.10,
}

DEFAULT_SECTOR_ROBUSTNESS_CONFIG: dict[str, Any] = {
    "schema_version": "physical-circle-sector-robustness/1",
    "enabled": False,
    "sector_bin_count": 36,
    "min_points_per_sector": 3,
    "suspect_residual_p95_multiplier": 1.0,
    "max_excluded_sector_count": 4,
    "max_contiguous_excluded_deg": 40.0,
    "min_retained_angular_coverage": 0.72,
    "max_refit_center_delta_px": 3.0,
    "max_refit_radius_delta_px": 3.0,
}

DEFAULT_EDGE_FAMILY_SELECTION_CONFIG: dict[str, Any] = {
    "schema_version": "physical-circle-edge-family-selection/1",
    "enabled": False,
    "strategy_version": "deterministic-three-point-global-circle-v1",
    "max_peaks_per_ray": 8,
    "min_gradient": 4.0,
    "min_separation_px": 3.0,
    "min_background_persistence_ratio": 0.95,
    "min_seed_votes": 3,
    "max_seed_count": 16384,
    "max_hypotheses": 128,
    "max_families": 8,
    "refinement_iterations": 1,
    "assignment_residual_px": 8.0,
    "min_support_ratio": 0.65,
    "min_angular_coverage": 0.65,
    "max_preliminary_residual_p95_px": 8.0,
    "dedup_center_px": 16.0,
    "dedup_radius_px": 16.0,
    "min_support_overlap_ratio": 0.80,
    "min_assignment_overlap_ratio": 0.40,
}

EDGE_FAMILY_STRATEGY_V1 = "deterministic-three-point-global-circle-v1"
EDGE_FAMILY_STRATEGY_V2 = "deterministic-family-consensus-circle-v2"
FAMILY_CONSENSUS_MAX_ITERATIONS = 16


def merged_edge_family_selection_config(config: dict[str, Any] | None) -> dict[str, Any]:
    supplied = config or {}
    prefix = "detector.physical_outer_circle.edge_family_selection"
    if not isinstance(supplied, dict):
        raise ValueError(f"{prefix} must be an object")
    unknown = sorted(set(supplied) - set(DEFAULT_EDGE_FAMILY_SELECTION_CONFIG))
    if unknown:
        raise ValueError(f"{prefix} has unknown fields: {unknown}")
    merged = {**DEFAULT_EDGE_FAMILY_SELECTION_CONFIG, **supplied}
    if merged["schema_version"] != "physical-circle-edge-family-selection/1":
        raise ValueError(f"{prefix}.schema_version is unsupported")
    if not isinstance(merged["enabled"], bool):
        raise ValueError(f"{prefix}.enabled must be boolean")
    if merged["strategy_version"] not in {
        EDGE_FAMILY_STRATEGY_V1, EDGE_FAMILY_STRATEGY_V2,
    }:
        raise ValueError(f"{prefix}.strategy_version is unsupported")
    integer_bounds = {
        "max_peaks_per_ray": (1, 8),
        "min_seed_votes": (1, 72),
        "max_seed_count": (8, 65536),
        "max_hypotheses": (1, 1024),
        "max_families": (1, 16),
        "refinement_iterations": (1, 4),
    }
    for key, (minimum, maximum) in integer_bounds.items():
        value = merged[key]
        if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
            raise ValueError(f"{prefix}.{key} must be an integer in [{minimum},{maximum}]")
    if merged["max_hypotheses"] > merged["max_seed_count"]:
        raise ValueError(f"{prefix}.max_hypotheses cannot exceed max_seed_count")
    if merged["max_families"] > merged["max_hypotheses"]:
        raise ValueError(f"{prefix}.max_families cannot exceed max_hypotheses")
    positive = (
        "min_gradient", "min_separation_px", "assignment_residual_px",
        "max_preliminary_residual_p95_px", "dedup_center_px", "dedup_radius_px",
    )
    for key in positive:
        value = merged[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
            raise ValueError(f"{prefix}.{key} must be a finite number")
        merged[key] = float(value)
        if merged[key] <= 0.0:
            raise ValueError(f"{prefix}.{key} must be positive")
    ratios = (
        "min_background_persistence_ratio", "min_support_ratio",
        "min_angular_coverage", "min_support_overlap_ratio",
        "min_assignment_overlap_ratio",
    )
    for key in ratios:
        value = merged[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
            raise ValueError(f"{prefix}.{key} must be a finite number")
        merged[key] = float(value)
        if not 0.0 <= merged[key] <= 1.0 or key in {"min_support_ratio", "min_angular_coverage"} and merged[key] == 0.0:
            raise ValueError(f"{prefix}.{key} must be in the supported ratio range")
    return merged


def merged_sector_robustness_config(
    config: dict[str, Any] | None,
    *,
    n_angles: int,
) -> dict[str, Any]:
    supplied = config or {}
    if not isinstance(supplied, dict):
        raise ValueError("detector.physical_outer_circle.sector_robustness must be an object")
    unknown = sorted(set(supplied) - set(DEFAULT_SECTOR_ROBUSTNESS_CONFIG))
    if unknown:
        raise ValueError(
            f"detector.physical_outer_circle.sector_robustness has unknown fields: {unknown}"
        )
    merged = {**DEFAULT_SECTOR_ROBUSTNESS_CONFIG, **supplied}
    prefix = "detector.physical_outer_circle.sector_robustness"
    if merged["schema_version"] != "physical-circle-sector-robustness/1":
        raise ValueError(f"{prefix}.schema_version is unsupported")
    if not isinstance(merged["enabled"], bool):
        raise ValueError(f"{prefix}.enabled must be boolean")
    for key in ("sector_bin_count", "min_points_per_sector", "max_excluded_sector_count"):
        value = merged[key]
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"{prefix}.{key} must be an integer")
    bins = int(merged["sector_bin_count"])
    excluded = int(merged["max_excluded_sector_count"])
    if not 4 <= bins <= min(72, int(n_angles)):
        raise ValueError(f"{prefix}.sector_bin_count is outside the supported range")
    if int(merged["min_points_per_sector"]) <= 0:
        raise ValueError(f"{prefix}.min_points_per_sector must be positive")
    if not 0 <= excluded < bins:
        raise ValueError(f"{prefix}.max_excluded_sector_count must be smaller than sector_bin_count")
    for key in (
        "suspect_residual_p95_multiplier", "max_contiguous_excluded_deg",
        "min_retained_angular_coverage", "max_refit_center_delta_px",
        "max_refit_radius_delta_px",
    ):
        value = merged[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
            raise ValueError(f"{prefix}.{key} must be a finite number")
        merged[key] = float(value)
    if merged["suspect_residual_p95_multiplier"] < 1.0:
        raise ValueError(f"{prefix}.suspect_residual_p95_multiplier must be >=1")
    if not 0.0 < merged["max_contiguous_excluded_deg"] < 180.0:
        raise ValueError(f"{prefix}.max_contiguous_excluded_deg must be in (0,180)")
    if not 0.0 < merged["min_retained_angular_coverage"] <= 1.0:
        raise ValueError(f"{prefix}.min_retained_angular_coverage must be in (0,1]")
    if any(merged[key] <= 0.0 for key in ("max_refit_center_delta_px", "max_refit_radius_delta_px")):
        raise ValueError(f"{prefix} refit delta limits must be positive")
    maximum_retained = (bins - excluded) / bins
    if merged["enabled"] and merged["min_retained_angular_coverage"] > maximum_retained:
        raise ValueError(
            f"{prefix}.min_retained_angular_coverage cannot be met at max exclusion"
        )
    return merged


def merged_physical_outer_circle_config(config: dict[str, Any] | None) -> dict[str, Any]:
    supplied = config or {}
    if not isinstance(supplied, dict):
        raise ValueError("detector.physical_outer_circle must be an object")
    unknown = sorted(
        set(supplied) - set(DEFAULT_PHYSICAL_OUTER_CIRCLE_CONFIG)
        - {"sector_robustness", "edge_family_selection"}
    )
    if unknown:
        raise ValueError(f"detector.physical_outer_circle has unknown fields: {unknown}")
    merged = {**DEFAULT_PHYSICAL_OUTER_CIRCLE_CONFIG, **supplied}
    if not isinstance(merged["threshold_version"], str) or not merged["threshold_version"].strip():
        raise ValueError("detector.physical_outer_circle.threshold_version must be non-empty")
    for key in ("n_angles", "min_edge_point_count", "angular_bin_count"):
        if not isinstance(merged[key], int) or merged[key] <= 0:
            raise ValueError(f"detector.physical_outer_circle.{key} must be a positive integer")
    if merged["n_angles"] < merged["angular_bin_count"]:
        raise ValueError("detector.physical_outer_circle angular sampling is too sparse")
    if merged["min_edge_point_count"] > merged["n_angles"]:
        raise ValueError("detector.physical_outer_circle.min_edge_point_count exceeds n_angles")
    for key in ("min_inlier_ratio", "min_angular_coverage"):
        if not 0.0 < float(merged[key]) <= 1.0:
            raise ValueError(f"detector.physical_outer_circle.{key} must be in (0,1]")
    for key in ("inlier_residual_px", "max_residual_p95_px", "max_center_shift_px"):
        if float(merged[key]) <= 0.0:
            raise ValueError(f"detector.physical_outer_circle.{key} must be positive")
    if not 0.0 < float(merged["min_radius_ratio"]) < float(merged["max_radius_ratio"]):
        raise ValueError("detector.physical_outer_circle radius ratios must be ordered and positive")
    merged["sector_robustness"] = merged_sector_robustness_config(
        supplied.get("sector_robustness"),
        n_angles=int(merged["n_angles"]),
    )
    merged["edge_family_selection"] = merged_edge_family_selection_config(
        supplied.get("edge_family_selection")
    )
    return merged


def _circle_dict(circle: tuple[float, float, float]) -> dict[str, float]:
    return {"centerX": float(circle[0]), "centerY": float(circle[1]), "radiusPx": float(circle[2])}


def _circle_from_three(points: tuple[tuple[float, float], ...]) -> tuple[float, float, float] | None:
    (x1, y1), (x2, y2), (x3, y3) = points
    determinant = 2.0 * (x1 * (y2 - y3) + x2 * (y3 - y1) + x3 * (y1 - y2))
    if abs(determinant) < 1e-6:
        return None
    q1 = x1 * x1 + y1 * y1
    q2 = x2 * x2 + y2 * y2
    q3 = x3 * x3 + y3 * y3
    cx = (q1 * (y2 - y3) + q2 * (y3 - y1) + q3 * (y1 - y2)) / determinant
    cy = (q1 * (x3 - x2) + q2 * (x1 - x3) + q3 * (x2 - x1)) / determinant
    radius = math.hypot(x1 - cx, y1 - cy)
    circle = (float(cx), float(cy), float(radius))
    if radius <= 0.0 or not all(math.isfinite(value) for value in circle):
        return None
    return circle


def _algebraic_hypothesis_fit(points: np.ndarray) -> tuple[float, float, float] | None:
    if len(points) < 3 or points.ndim != 2 or points.shape[1] != 2 or not np.isfinite(points).all():
        return None
    x = points[:, 0]
    y = points[:, 1]
    matrix = np.column_stack((2.0 * x, 2.0 * y, np.ones(len(points))))
    try:
        cx, cy, constant = np.linalg.lstsq(matrix, x * x + y * y, rcond=None)[0]
    except np.linalg.LinAlgError:
        return None
    radius_sq = float(constant + cx * cx + cy * cy)
    if radius_sq <= 0.0:
        return None
    circle = (float(cx), float(cy), math.sqrt(radius_sq))
    return circle if all(math.isfinite(value) for value in circle) else None


def _circle_in_search_envelope(
    circle: tuple[float, float, float], search: tuple[float, float, float],
    *, max_center_shift_px: float, min_radius_ratio: float, max_radius_ratio: float,
) -> bool:
    return bool(
        math.hypot(circle[0] - search[0], circle[1] - search[1]) <= max_center_shift_px
        and min_radius_ratio <= circle[2] / search[2] <= max_radius_ratio
    )


def _normalized_family_rays(ray_candidates: list[dict[str, Any]], n_angles: int) -> dict[int, list[dict[str, float]]]:
    normalized: dict[int, list[dict[str, float]]] = {}
    for record in ray_candidates:
        index = record.get("angleIndex")
        if isinstance(index, bool) or not isinstance(index, int) or not 0 <= index < n_angles:
            raise ValueError("edge-family angleIndex is invalid")
        if index in normalized:
            raise ValueError("edge-family evidence contains a duplicate angleIndex")
        candidates: list[dict[str, float]] = []
        for candidate in record.get("candidates", []):
            values = {
                key: float(candidate[key])
                for key in ("x", "y", "radiusPx", "strength", "backgroundPersistenceRatio")
            }
            if not all(math.isfinite(value) for value in values.values()) or values["radiusPx"] <= 0.0:
                raise ValueError("edge-family candidate evidence must be finite and positive")
            if candidate.get("polarity") != "bright_to_dark":
                raise ValueError("edge-family candidate polarity must be bright_to_dark")
            candidates.append(values)
        normalized[index] = sorted(
            candidates,
            key=lambda item: (item["radiusPx"], item["x"], item["y"], -item["strength"]),
        )
    return normalized


def _assign_family_candidates(
    candidate_x: np.ndarray, candidate_y: np.ndarray,
    circle: tuple[float, float, float], gate_px: float,
) -> tuple[np.ndarray, np.ndarray]:
    residuals = np.abs(
        np.hypot(candidate_x - circle[0], candidate_y - circle[1]) - circle[2]
    )
    residuals = np.where(np.isfinite(residuals), residuals, np.inf)
    choices = np.argmin(residuals, axis=1)
    rows = np.arange(candidate_x.shape[0])
    best = residuals[rows, choices]
    indices = np.flatnonzero(best <= gate_px)
    points = np.column_stack((candidate_x[indices, choices[indices]], candidate_y[indices, choices[indices]]))
    return points, indices


def _assignment_signature(points: np.ndarray, indices: np.ndarray) -> tuple[tuple[int, float, float], ...]:
    return tuple(
        (int(ray), round(float(point[0]), 6), round(float(point[1]), 6))
        for ray, point in zip(indices, points)
    )


def _assignment_change_count(
    first: tuple[tuple[int, float, float], ...],
    second: tuple[tuple[int, float, float], ...],
) -> int:
    first_by_ray = {item[0]: item[1:] for item in first}
    second_by_ray = {item[0]: item[1:] for item in second}
    return sum(first_by_ray.get(ray) != second_by_ray.get(ray) for ray in first_by_ray.keys() | second_by_ray.keys())


def _consolidate_family_consensus(
    family: dict[str, Any],
    candidate_x: np.ndarray,
    candidate_y: np.ndarray,
    *,
    gate: float,
    n_angles: int,
    angular_bin_count: int,
    minimum_support: int,
    preliminary_residual_gate: float,
    trigger_residual_gate: float,
    config: dict[str, Any],
    search: tuple[float, float, float],
    center_limit: float,
    min_radius_ratio: float,
    max_radius_ratio: float,
) -> dict[str, Any]:
    members = list(family.get("_members") or [family])
    member_circles = np.asarray([member["circle"] for member in members], dtype=np.float64)
    initial = tuple(map(float, np.median(member_circles, axis=0)))
    diagnostic: dict[str, Any] = {
        "schemaVersion": "physical-circle-family-consensus/1",
        "status": "invalid",
        "applied": True,
        "triggerResidualP95Px": trigger_residual_gate,
        "originalResidualP95Px": float(family["p95"]),
        "memberHypothesisCount": int(family.get("memberCount", len(members))),
        "maxIterations": FAMILY_CONSENSUS_MAX_ITERATIONS,
        "iterationCount": 0,
        "converged": False,
        "assignmentChangeCounts": [],
        "initialCircle": _circle_dict(initial),
        "finalCircle": None,
        "supportRayCount": 0,
        "angularCoverage": 0.0,
        "residualMedianPx": None,
        "residualP95Px": None,
        "failedChecks": [],
    }
    if not all(math.isfinite(value) for value in initial) or not _circle_in_search_envelope(
        initial, search, max_center_shift_px=center_limit,
        min_radius_ratio=min_radius_ratio, max_radius_ratio=max_radius_ratio,
    ):
        diagnostic["failedChecks"] = ["family_consensus_invalid"]
        return {**family, "failed": ["family_consensus_invalid"], "consensus": diagnostic}

    circle = initial
    points, indices = _assign_family_candidates(candidate_x, candidate_y, circle, gate)
    signature = _assignment_signature(points, indices)
    converged = False
    for iteration in range(1, FAMILY_CONSENSUS_MAX_ITERATIONS + 1):
        diagnostic["iterationCount"] = iteration
        if len(points) < 3:
            diagnostic["failedChecks"] = ["family_consensus_insufficient_support"]
            break
        fitted = _algebraic_hypothesis_fit(points)
        if fitted is None or not _circle_in_search_envelope(
            fitted, search, max_center_shift_px=center_limit,
            min_radius_ratio=min_radius_ratio, max_radius_ratio=max_radius_ratio,
        ):
            diagnostic["failedChecks"] = ["family_consensus_invalid"]
            break
        next_points, next_indices = _assign_family_candidates(candidate_x, candidate_y, fitted, gate)
        next_signature = _assignment_signature(next_points, next_indices)
        changes = _assignment_change_count(signature, next_signature)
        diagnostic["assignmentChangeCounts"].append(changes)
        circle, points, indices, signature = fitted, next_points, next_indices, next_signature
        if changes == 0:
            converged = True
            break
    if not converged and not diagnostic["failedChecks"]:
        diagnostic["failedChecks"] = ["family_consensus_not_converged"]

    failed = list(diagnostic["failedChecks"])
    coverage = 0.0
    median = math.inf
    p95 = math.inf
    if len(points) >= 3 and all(math.isfinite(value) for value in circle):
        residuals = np.abs(
            np.hypot(points[:, 0] - circle[0], points[:, 1] - circle[1]) - circle[2]
        )
        bins = np.floor(indices * angular_bin_count / n_angles).astype(int)
        coverage = len(set(bins.tolist())) / angular_bin_count
        median = float(np.median(residuals))
        p95 = float(np.percentile(residuals, 95))
        if len(points) < minimum_support:
            failed.append("family_support")
        if coverage < float(config["min_angular_coverage"]):
            failed.append("family_angular_coverage")
        if p95 > preliminary_residual_gate:
            failed.append("family_residual_p95")
    elif "family_consensus_insufficient_support" not in failed:
        failed.append("family_consensus_insufficient_support")
    failed = list(dict.fromkeys(failed))
    diagnostic.update({
        "status": "converged" if converged and not failed else "rejected",
        "converged": converged,
        "finalCircle": _circle_dict(circle) if all(math.isfinite(value) for value in circle) else None,
        "supportRayCount": len(points),
        "angularCoverage": coverage,
        "residualMedianPx": median if math.isfinite(median) else None,
        "residualP95Px": p95 if math.isfinite(p95) else None,
        "failedChecks": failed,
    })
    return {
        **family,
        "circle": circle,
        "points": points,
        "indices": indices,
        "assignmentByRay": {int(ray): point for ray, point in zip(indices, points)},
        "support": len(points),
        "coverage": coverage,
        "median": median,
        "p95": p95,
        "failed": failed,
        "consensus": diagnostic,
    }


def _preserve_qualified_family(
    family: dict[str, Any], *, trigger_residual_gate: float,
) -> dict[str, Any]:
    """Keep a v1-qualified family byte-for-byte when correction is not needed."""
    circle = tuple(map(float, family["circle"]))
    return {
        **family,
        "consensus": {
            "schemaVersion": "physical-circle-family-consensus/1",
            "status": "not_needed",
            "applied": False,
            "triggerResidualP95Px": float(trigger_residual_gate),
            "originalResidualP95Px": float(family["p95"]),
            "memberHypothesisCount": int(family.get("memberCount", 1)),
            "maxIterations": FAMILY_CONSENSUS_MAX_ITERATIONS,
            "iterationCount": 0,
            "converged": False,
            "assignmentChangeCounts": [],
            "initialCircle": _circle_dict(circle),
            "finalCircle": _circle_dict(circle),
            "supportRayCount": int(family["support"]),
            "angularCoverage": float(family["coverage"]),
            "residualMedianPx": float(family["median"]),
            "residualP95Px": float(family["p95"]),
            "failedChecks": [],
        },
    }


def select_circle_edge_family(
    ray_candidates: list[dict[str, Any]],
    *,
    search: tuple[float, float, float],
    n_angles: int,
    config: dict[str, Any] | None,
    scale: float,
    max_center_shift_px: float,
    min_radius_ratio: float,
    max_radius_ratio: float,
    angular_bin_count: int = 36,
    consensus_trigger_residual_p95_px: float = 0.0,
) -> tuple[dict[str, Any], np.ndarray, np.ndarray]:
    """Select exactly one globally consistent physical-circle edge family."""
    started = time.perf_counter_ns()
    cfg = merged_edge_family_selection_config(config)
    empty_points = np.empty((0, 2), dtype=float)
    empty_indices = np.asarray([], dtype=int)
    diagnostics: dict[str, Any] = {
        "schemaVersion": "physical-circle-edge-family-selection/1",
        "enabled": bool(cfg["enabled"]),
        "strategyVersion": str(cfg["strategy_version"]),
        "status": "disabled" if not cfg["enabled"] else "no_family",
        "rayCount": int(n_angles),
        "candidateCount": 0,
        "missingRayCount": int(n_angles),
        "seedCount": 0,
        "hypothesisCount": 0,
        "familyCount": 0,
        "qualifiedFamilyCount": 0,
        "families": [],
        "selectedFamilyId": None,
        "failedChecks": [],
        "timingMs": {"candidateExtraction": 0.0, "familySelection": 0.0, "robustFit": 0.0, "total": 0.0},
    }
    if not cfg["enabled"]:
        diagnostics["timingMs"]["total"] = (time.perf_counter_ns() - started) / 1e6
        return diagnostics, empty_points, empty_indices
    if (
        n_angles < 4 or angular_bin_count < 4 or angular_bin_count > n_angles
        or scale <= 0.0 or search[2] <= 0.0
        or not all(math.isfinite(float(value)) for value in (*search, scale, max_center_shift_px, min_radius_ratio, max_radius_ratio, consensus_trigger_residual_p95_px))
        or consensus_trigger_residual_p95_px < 0.0
    ):
        diagnostics.update({"status": "invalid", "failedChecks": ["invalid_edge_family_evidence"]})
        diagnostics["timingMs"]["total"] = (time.perf_counter_ns() - started) / 1e6
        return diagnostics, empty_points, empty_indices
    try:
        rays = _normalized_family_rays(ray_candidates, n_angles)
    except (KeyError, TypeError, ValueError, OverflowError):
        diagnostics.update({"status": "invalid", "failedChecks": ["invalid_edge_family_evidence"]})
        diagnostics["timingMs"]["total"] = (time.perf_counter_ns() - started) / 1e6
        return diagnostics, empty_points, empty_indices
    diagnostics["candidateCount"] = sum(len(items) for items in rays.values())
    diagnostics["missingRayCount"] = n_angles - sum(bool(items) for items in rays.values())
    if diagnostics["candidateCount"] == 0:
        diagnostics["failedChecks"] = ["no_qualified_edge_family"]
        diagnostics["timingMs"]["total"] = (time.perf_counter_ns() - started) / 1e6
        return diagnostics, empty_points, empty_indices

    candidate_width = max(1, max((len(items) for items in rays.values()), default=0))
    candidate_x = np.full((n_angles, candidate_width), np.nan, dtype=np.float64)
    candidate_y = np.full((n_angles, candidate_width), np.nan, dtype=np.float64)
    for ray_index, items in rays.items():
        for candidate_index, item in enumerate(items):
            candidate_x[ray_index, candidate_index] = item["x"]
            candidate_y[ray_index, candidate_index] = item["y"]

    gate = float(cfg["assignment_residual_px"]) * scale
    center_limit = float(max_center_shift_px) * scale
    # One rotation-equivariant, well-conditioned triplet per start is enough to
    # generate the bounded global hypotheses.  Keeping a second overlapping
    # triplet only duplicated the same families and consumed the single-shot
    # latency budget without adding independent physical evidence.
    patterns = ((n_angles // 3, 2 * n_angles // 3),)
    coarse_quantizer = max(
        1.0,
        min(float(cfg["dedup_center_px"]), float(cfg["dedup_radius_px"])) * scale,
    )
    fine_quantizer = max(1.0, float(cfg["min_separation_px"]) * scale)
    seed_buckets: dict[
        tuple[int, int, int], dict[tuple[int, int, int], dict[str, Any]]
    ] = {}
    for start in range(n_angles):
        for second_offset, third_offset in patterns:
            anchor_indices = (start, (start + second_offset) % n_angles, (start + third_offset) % n_angles)
            anchor_candidates = [rays.get(index, []) for index in anchor_indices]
            if any(not items for items in anchor_candidates):
                continue
            for combination in itertools.product(*anchor_candidates):
                diagnostics["seedCount"] += 1
                if diagnostics["seedCount"] > int(cfg["max_seed_count"]):
                    diagnostics.update({"status": "overflow", "failedChecks": ["family_search_overflow"]})
                    diagnostics["timingMs"]["familySelection"] = (time.perf_counter_ns() - started) / 1e6
                    diagnostics["timingMs"]["total"] = diagnostics["timingMs"]["familySelection"]
                    return diagnostics, empty_points, empty_indices
                circle = _circle_from_three(tuple((item["x"], item["y"]) for item in combination))
                if circle is None or not _circle_in_search_envelope(
                    circle, search, max_center_shift_px=center_limit,
                    min_radius_ratio=min_radius_ratio, max_radius_ratio=max_radius_ratio,
                ):
                    continue
                coarse_cell = tuple(int(round(value / coarse_quantizer)) for value in circle)
                fine_cell = tuple(int(round(value / fine_quantizer)) for value in circle)
                bucket = seed_buckets.setdefault(coarse_cell, {})
                entry = bucket.get(fine_cell)
                if entry is None:
                    bucket[fine_cell] = {"circle": circle, "count": 1}
                else:
                    entry["count"] += 1
                    entry["circle"] = min(entry["circle"], circle)

    # A coarse parameter cell normally represents one noisy family.  Retaining
    # its two strongest fine modes preserves evidence for two nearby physical
    # circles (which must remain ambiguous) without refining every noisy seed.
    seed_entries: list[dict[str, Any]] = []
    for coarse_cell in sorted(seed_buckets):
        entries = sorted(
            (
                item for item in seed_buckets[coarse_cell].values()
                if int(item["count"]) >= int(cfg["min_seed_votes"])
            ),
            key=lambda item: (-int(item["count"]), *item["circle"]),
        )
        if not entries:
            continue
        seed_entries.append(entries[0])
        if len(entries) > 1 and 2 * int(entries[1]["count"]) >= int(entries[0]["count"]):
            seed_entries.append(entries[1])

    hypotheses: list[dict[str, Any]] = []
    hypothesis_by_assignment: dict[tuple[tuple[int, float, float], ...], dict[str, Any]] = {}
    minimum_support = max(3, int(math.ceil(float(cfg["min_support_ratio"]) * n_angles)))
    for seed_entry in sorted(seed_entries, key=lambda item: item["circle"]):
        seed = seed_entry["circle"]
        seed_member_count = int(seed_entry["count"])
        circle = seed
        points = empty_points
        indices = empty_indices
        for _ in range(int(cfg["refinement_iterations"])):
            points, indices = _assign_family_candidates(candidate_x, candidate_y, circle, gate)
            if len(points) < 3:
                break
            fitted = _algebraic_hypothesis_fit(points)
            if fitted is None or not _circle_in_search_envelope(
                fitted, search, max_center_shift_px=center_limit,
                min_radius_ratio=min_radius_ratio, max_radius_ratio=max_radius_ratio,
            ):
                points = empty_points
                indices = empty_indices
                break
            circle = fitted
        if len(points) < 3:
            continue
        points, indices = _assign_family_candidates(candidate_x, candidate_y, circle, gate)
        if len(points) < 3:
            continue
        residuals = np.abs(np.hypot(points[:, 0] - circle[0], points[:, 1] - circle[1]) - circle[2])
        bins = np.floor(indices * angular_bin_count / n_angles).astype(int)
        coverage = len(set(bins.tolist())) / angular_bin_count
        p95 = float(np.percentile(residuals, 95))
        failed = []
        if len(points) < minimum_support: failed.append("family_support")
        if coverage < float(cfg["min_angular_coverage"]): failed.append("family_angular_coverage")
        if p95 > float(cfg["max_preliminary_residual_p95_px"]) * scale:
            failed.append("family_residual_p95")
        if "family_support" in failed:
            continue
        assignment_signature = tuple(
            (int(ray), round(float(point[0]), 6), round(float(point[1]), 6))
            for ray, point in zip(indices, points)
        )
        existing = hypothesis_by_assignment.get(assignment_signature)
        if existing is not None:
            existing["memberCount"] += seed_member_count
            continue
        hypothesis = {
            "circle": circle, "points": points, "indices": indices,
            "assignmentByRay": {int(ray): point for ray, point in zip(indices, points)},
            "support": len(points), "coverage": coverage,
            "median": float(np.median(residuals)), "p95": p95,
            "failed": failed, "memberCount": seed_member_count,
        }
        hypotheses.append(hypothesis)
        hypothesis_by_assignment[assignment_signature] = hypothesis
        if len(hypotheses) > int(cfg["max_hypotheses"]):
            diagnostics.update({"status": "overflow", "failedChecks": ["family_search_overflow"]})
            diagnostics["hypothesisCount"] = len(hypotheses)
            diagnostics["timingMs"]["familySelection"] = (time.perf_counter_ns() - started) / 1e6
            diagnostics["timingMs"]["total"] = diagnostics["timingMs"]["familySelection"]
            return diagnostics, empty_points, empty_indices
    diagnostics["hypothesisCount"] = len(hypotheses)

    families: list[dict[str, Any]] = []
    for hypothesis in sorted(
        hypotheses,
        key=lambda item: (-item["support"], item["p95"], *item["circle"]),
    ):
        match = None
        current_ids = set(hypothesis["indices"].tolist())
        for family in families:
            family_ids = set(family["indices"].tolist())
            common_ids = current_ids & family_ids
            overlap = len(common_ids) / max(1, min(len(current_ids), len(family_ids)))
            hypothesis_by_ray = hypothesis["assignmentByRay"]
            family_by_ray = family["assignmentByRay"]
            same_assignment_ratio = (
                sum(
                    float(np.hypot(*(hypothesis_by_ray[ray] - family_by_ray[ray])))
                    < 0.5 * float(cfg["min_separation_px"]) * scale
                    for ray in common_ids
                ) / len(common_ids)
                if common_ids else 0.0
            )
            center_delta = math.hypot(
                hypothesis["circle"][0] - family["circle"][0],
                hypothesis["circle"][1] - family["circle"][1],
            )
            radius_delta = abs(hypothesis["circle"][2] - family["circle"][2])
            if (
                center_delta <= float(cfg["dedup_center_px"]) * scale
                and radius_delta <= float(cfg["dedup_radius_px"]) * scale
                and overlap >= float(cfg["min_support_overlap_ratio"])
                and same_assignment_ratio >= float(cfg["min_assignment_overlap_ratio"])
            ):
                match = family
                break
        if match is None:
            if len(families) >= int(cfg["max_families"]):
                diagnostics.update({"status": "overflow", "failedChecks": ["family_search_overflow"]})
                diagnostics["familyCount"] = len(families)
                diagnostics["timingMs"]["familySelection"] = (time.perf_counter_ns() - started) / 1e6
                diagnostics["timingMs"]["total"] = diagnostics["timingMs"]["familySelection"]
                return diagnostics, empty_points, empty_indices
            families.append({**hypothesis, "_members": [hypothesis]})
        else:
            match["memberCount"] += 1

            match["_members"].append(hypothesis)

    if cfg["strategy_version"] == EDGE_FAMILY_STRATEGY_V2:
        families = [
            (
                _preserve_qualified_family(
                    family,
                    trigger_residual_gate=consensus_trigger_residual_p95_px,
                )
                if family["p95"] <= consensus_trigger_residual_p95_px
                else _consolidate_family_consensus(
                    family, candidate_x, candidate_y,
                    gate=gate, n_angles=n_angles, angular_bin_count=angular_bin_count,
                    minimum_support=minimum_support,
                    preliminary_residual_gate=(
                        float(cfg["max_preliminary_residual_p95_px"]) * scale
                    ),
                    trigger_residual_gate=consensus_trigger_residual_p95_px,
                    config=cfg, search=search, center_limit=center_limit,
                    min_radius_ratio=min_radius_ratio, max_radius_ratio=max_radius_ratio,
                )
            )
            for family in families
        ]

    families.sort(key=lambda item: (-item["support"], item["p95"], *item["circle"]))
    summaries = []
    qualified: list[dict[str, Any]] = []
    for index, family in enumerate(families, start=1):
        family_id = f"edge-family-{index:03d}"
        status = "qualified" if not family["failed"] else "rejected"
        family["familyId"] = family_id
        summary = {
            "familyId": family_id,
            "circle": _circle_dict(family["circle"]),
            "supportRayCount": int(family["support"]),
            "angularCoverage": float(family["coverage"]),
            "residualMedianPx": float(family["median"]),
            "residualP95Px": float(family["p95"]),
            "memberHypothesisCount": int(family["memberCount"]),
            "status": status,
            "failedChecks": list(family["failed"]),
        }
        if cfg["strategy_version"] == EDGE_FAMILY_STRATEGY_V2:
            summary["consensus"] = family["consensus"]
        summaries.append(summary)
        if status == "qualified":
            qualified.append(family)
    diagnostics.update({
        "familyCount": len(families),
        "qualifiedFamilyCount": len(qualified),
        "families": summaries,
    })
    if len(qualified) == 1:
        selected = qualified[0]
        diagnostics.update({"status": "selected", "selectedFamilyId": selected["familyId"]})
        result_points = selected["points"]
        result_indices = selected["indices"]
    elif len(qualified) > 1:
        diagnostics.update({"status": "ambiguous", "failedChecks": ["ambiguous_edge_families"]})
        result_points, result_indices = empty_points, empty_indices
    else:
        diagnostics.update({"status": "no_family", "failedChecks": ["no_qualified_edge_family"]})
        result_points, result_indices = empty_points, empty_indices
    elapsed = (time.perf_counter_ns() - started) / 1e6
    diagnostics["timingMs"].update({"familySelection": elapsed, "total": elapsed})
    return diagnostics, result_points, result_indices


def _circular_sector_runs(flags: list[bool]) -> list[list[int]]:
    if not flags or not any(flags):
        return []
    if all(flags):
        return [list(range(len(flags)))]
    starts = [index for index, flag in enumerate(flags) if flag and not flags[index - 1]]
    runs: list[list[int]] = []
    for start in starts:
        run: list[int] = []
        index = start
        while flags[index]:
            run.append(index)
            index = (index + 1) % len(flags)
        runs.append(run)
    return runs


def _sector_evidence(
    residuals: np.ndarray,
    inliers: np.ndarray,
    angle_indices: np.ndarray,
    *,
    n_angles: int,
    config: dict[str, Any],
    residual_threshold_px: float,
) -> dict[str, Any]:
    bin_count = int(config["sector_bin_count"])
    point_bins = np.floor(angle_indices * bin_count / n_angles).astype(int)
    gate = residual_threshold_px * float(config["suspect_residual_p95_multiplier"])
    sectors: list[dict[str, Any]] = []
    suspect_flags: list[bool] = []
    for sector_id in range(bin_count):
        selected = point_bins == sector_id
        values = residuals[selected]
        point_count = int(values.size)
        residual_p95 = float(np.percentile(values, 95)) if point_count else None
        suspect = bool(
            point_count >= int(config["min_points_per_sector"])
            and residual_p95 is not None
            and residual_p95 > gate
        )
        suspect_flags.append(suspect)
        sectors.append({
            "sectorId": sector_id,
            "startDeg": sector_id * 360.0 / bin_count,
            "endDeg": (sector_id + 1) * 360.0 / bin_count,
            "wrapsBoundary": False,
            "pointCount": point_count,
            "inlierCount": int(np.count_nonzero(inliers[selected])),
            "residualMedianPx": float(np.median(values)) if point_count else None,
            "residualP95Px": residual_p95,
            "residualMaxPx": float(np.max(values)) if point_count else None,
            "suspect": suspect,
            "reasons": ["residual_p95"] if suspect else [],
        })
    runs = _circular_sector_runs(suspect_flags)
    run_records = [{
        "sectorIds": run,
        "startDeg": run[0] * 360.0 / bin_count,
        "endDeg": ((run[-1] + 1) % bin_count) * 360.0 / bin_count,
        "wrapsBoundary": run[0] > run[-1],
        "sectorCount": len(run),
        "totalAngleDeg": len(run) * 360.0 / bin_count,
    } for run in runs]
    return {
        "schemaVersion": "physical-circle-sector-evidence/1",
        "binCount": bin_count,
        "residualGatePx": gate,
        "suspectSectorCount": int(sum(suspect_flags)),
        "suspectSectorIds": [index for index, flag in enumerate(suspect_flags) if flag],
        "suspectRuns": run_records,
        "sectors": sectors,
    }


def _fit_quality(
    points: np.ndarray,
    angle_indices: np.ndarray,
    circle: tuple[float, float, float],
    *,
    alignment: tuple[float, float, float],
    search: tuple[float, float, float],
    n_angles: int,
    config: dict[str, Any],
    scale: float,
) -> dict[str, Any]:
    fit_x, fit_y, fit_radius = circle
    residuals = np.abs(np.hypot(points[:, 0] - fit_x, points[:, 1] - fit_y) - fit_radius)
    inliers = residuals <= float(config["inlier_residual_px"]) * scale
    inlier_count = int(np.count_nonzero(inliers))
    inlier_ratio = inlier_count / len(points)
    bins = np.floor(
        angle_indices[inliers] * int(config["angular_bin_count"]) / n_angles
    ).astype(int)
    coverage = len(set(bins.tolist())) / int(config["angular_bin_count"])
    residual_p95 = float(np.percentile(residuals[inliers], 95)) if inlier_count else math.inf
    center_shift = math.hypot(fit_x - search[0], fit_y - search[1])
    radius_ratio_search = fit_radius / search[2]
    radius_ratio_alignment = fit_radius / alignment[2]
    failed: list[str] = []
    if inlier_ratio < float(config["min_inlier_ratio"]): failed.append("inlier_ratio")
    if coverage < float(config["min_angular_coverage"]): failed.append("angular_coverage")
    if residual_p95 > float(config["max_residual_p95_px"]) * scale: failed.append("residual_p95")
    if center_shift > float(config["max_center_shift_px"]) * scale: failed.append("center_shift")
    if not float(config["min_radius_ratio"]) <= radius_ratio_search <= float(config["max_radius_ratio"]):
        failed.append("radius_ratio")
    return {
        "circle": circle,
        "residuals": residuals,
        "inliers": inliers,
        "inlierCount": inlier_count,
        "inlierRatio": inlier_ratio,
        "angularCoverage": coverage,
        "residualP95Px": residual_p95,
        "centerShiftPx": center_shift,
        "radiusRatioToSearchPrior": radius_ratio_search,
        "radiusRatioToAlignment": radius_ratio_alignment,
        "failedChecks": failed,
    }


def locate_physical_outer_circle(
    gray: np.ndarray,
    alignment_center: tuple[float, float],
    alignment_radius_px: float,
    search_center: tuple[float, float],
    search_radius_px: float,
    outer_boundary_edge_point: Callable[..., tuple[float, float] | None],
    robust_fit_circle: Callable[..., tuple[float, float, float]],
    config: dict[str, Any] | None,
    *,
    source_sha256: str,
    pixel_scale: float = 1.0,
    outer_boundary_edge_candidates: Callable[..., list[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    """Run gyj edge extraction/fitting and apply stricter slot-specific quality gates."""
    cfg = merged_physical_outer_circle_config(config)
    alignment = (*map(float, alignment_center), float(alignment_radius_px))
    search = (*map(float, search_center), float(search_radius_px))
    scale = float(pixel_scale)
    diagnostics: dict[str, Any] = {
        "status": "failed",
        "thresholdVersion": cfg["threshold_version"],
        "sourceAlgorithm": "gyj.outer_boundary_edge_point+robust_fit_circle",
        "sourceSha256": source_sha256,
        "alignmentCircle": _circle_dict(alignment),
        "searchPriorCircle": _circle_dict(search),
        "physicalCircle": None,
        "edgePointCount": 0,
        "inlierCount": 0,
        "inlierRatio": 0.0,
        "angularCoverage": 0.0,
        "residualP95Px": None,
        "residualThresholdPx": float(cfg["max_residual_p95_px"]) * scale,
        "residualMarginPx": None,
        "sectorEvidence": None,
        "edgeFamilySelection": {
            "schemaVersion": "physical-circle-edge-family-selection/1",
            "enabled": bool(cfg["edge_family_selection"]["enabled"]),
            "strategyVersion": str(cfg["edge_family_selection"]["strategy_version"]),
            "status": "disabled" if not cfg["edge_family_selection"]["enabled"] else "invalid",
            "rayCount": int(cfg["n_angles"]), "candidateCount": 0,
            "missingRayCount": int(cfg["n_angles"]), "seedCount": 0,
            "hypothesisCount": 0, "familyCount": 0, "qualifiedFamilyCount": 0,
            "families": [], "selectedFamilyId": None, "failedChecks": [],
            "timingMs": {"candidateExtraction": 0.0, "familySelection": 0.0, "robustFit": 0.0, "total": 0.0},
        },
        "robustRefit": {
            "schemaVersion": "physical-circle-sector-refit/1",
            "enabled": bool(cfg["sector_robustness"]["enabled"]),
            "attempted": False,
            "status": "not_needed" if cfg["sector_robustness"]["enabled"] else "disabled",
            "reasons": [],
        },
        "failedChecks": [],
    }
    if (
        gray.ndim != 2
        or len(source_sha256) != 64
        or not all(math.isfinite(value) for value in (*alignment, *search, scale))
        or alignment[2] <= 0.0
        or search[2] <= 0.0
        or scale <= 0.0
    ):
        diagnostics["failedChecks"].append("invalid_alignment_prior")
        return diagnostics

    n_angles = int(cfg["n_angles"])
    family_cfg = cfg["edge_family_selection"]
    if family_cfg["enabled"]:
        if outer_boundary_edge_candidates is None:
            diagnostics["edgeFamilySelection"].update({
                "status": "invalid", "failedChecks": ["edge_family_primitive_unavailable"],
            })
            diagnostics["failedChecks"].append("edge_family_primitive_unavailable")
            return diagnostics
        extraction_started = time.perf_counter_ns()
        ray_records: list[dict[str, Any]] = []
        try:
            for index, angle in enumerate(np.linspace(0.0, 2.0 * math.pi, n_angles, endpoint=False)):
                candidates = outer_boundary_edge_candidates(
                    gray, (search[0], search[1]), float(angle), search[2],
                    min_gradient=float(family_cfg["min_gradient"]),
                    separation_px=float(family_cfg["min_separation_px"]) * scale,
                    max_peaks=int(family_cfg["max_peaks_per_ray"]),
                    min_background_persistence_ratio=float(family_cfg["min_background_persistence_ratio"]),
                )
                ray_records.append({
                    "angleIndex": index, "angleRad": float(angle),
                    "candidates": candidates,
                })
        except (TypeError, ValueError, FloatingPointError, OverflowError):
            elapsed = (time.perf_counter_ns() - extraction_started) / 1e6
            diagnostics["edgeFamilySelection"].update({
                "status": "invalid", "failedChecks": ["invalid_edge_family_evidence"],
            })
            diagnostics["edgeFamilySelection"]["timingMs"].update({
                "candidateExtraction": elapsed, "total": elapsed,
            })
            diagnostics["failedChecks"].append("invalid_edge_family_evidence")
            return diagnostics
        extraction_ms = (time.perf_counter_ns() - extraction_started) / 1e6
        family, selected_points, selected_indices = select_circle_edge_family(
            ray_records, search=search, n_angles=n_angles, config=family_cfg, scale=scale,
            max_center_shift_px=float(cfg["max_center_shift_px"]),
            min_radius_ratio=float(cfg["min_radius_ratio"]),
            max_radius_ratio=float(cfg["max_radius_ratio"]),
            angular_bin_count=int(cfg["angular_bin_count"]),
            consensus_trigger_residual_p95_px=(
                float(cfg["max_residual_p95_px"]) * scale
            ),
        )
        family["timingMs"]["candidateExtraction"] = extraction_ms
        family["timingMs"]["total"] += extraction_ms
        diagnostics["edgeFamilySelection"] = family
        if family["status"] != "selected":
            diagnostics["failedChecks"].extend(family["failedChecks"])
            return diagnostics
        points = [(float(point[0]), float(point[1])) for point in selected_points]
        point_angle_indices = selected_indices.tolist()
        diagnostics["sourceAlgorithm"] = (
            "slot_pose.outer_boundary_edge_candidates+global-circle-family+gyj.robust_fit_circle"
        )
    else:
        points = []
        point_angle_indices = []
        for index, angle in enumerate(np.linspace(0.0, 2.0 * math.pi, n_angles, endpoint=False)):
            point = outer_boundary_edge_point(gray, (search[0], search[1]), float(angle), search[2])
            if point is None or len(point) != 2 or not all(math.isfinite(float(value)) for value in point):
                continue
            points.append((float(point[0]), float(point[1])))
            point_angle_indices.append(index)
    diagnostics["edgePointCount"] = len(points)
    if len(points) < max(int(cfg["min_edge_point_count"]), int(cfg["angular_bin_count"])):
        diagnostics["failedChecks"].append("insufficient_edge_points")
        return diagnostics

    fit_started = time.perf_counter_ns()
    fit_x, fit_y, fit_radius = map(
        float,
        robust_fit_circle(points, (search[0], search[1], search[2])),
    )
    if family_cfg["enabled"]:
        fit_ms = (time.perf_counter_ns() - fit_started) / 1e6
        diagnostics["edgeFamilySelection"]["timingMs"]["robustFit"] = fit_ms
        diagnostics["edgeFamilySelection"]["timingMs"]["total"] += fit_ms
    if not all(math.isfinite(value) for value in (fit_x, fit_y, fit_radius)) or fit_radius <= 0.0:
        diagnostics["failedChecks"].append("invalid_circle_fit")
        return diagnostics

    xy = np.asarray(points, dtype=float)
    all_angle_indices = np.asarray(point_angle_indices, dtype=int)
    quality = _fit_quality(
        xy, all_angle_indices, (fit_x, fit_y, fit_radius), alignment=alignment,
        search=search, n_angles=n_angles, config=cfg, scale=scale,
    )
    residual_p95 = float(quality["residualP95Px"])
    diagnostics.update({
        "physicalCircle": _circle_dict((fit_x, fit_y, fit_radius)),
        "inlierCount": quality["inlierCount"],
        "inlierRatio": quality["inlierRatio"],
        "angularCoverage": quality["angularCoverage"],
        "residualP95Px": residual_p95 if math.isfinite(residual_p95) else None,
        "residualMarginPx": (
            float(cfg["max_residual_p95_px"]) * scale - residual_p95
            if math.isfinite(residual_p95) else None
        ),
        "centerShiftPx": quality["centerShiftPx"],
        "radiusRatioToSearchPrior": quality["radiusRatioToSearchPrior"],
        "radiusRatioToAlignment": quality["radiusRatioToAlignment"],
    })
    checks = diagnostics["failedChecks"]
    checks.extend(quality["failedChecks"])
    sector_cfg = cfg["sector_robustness"]
    evidence = _sector_evidence(
        quality["residuals"], quality["inliers"], all_angle_indices,
        n_angles=n_angles, config=sector_cfg,
        residual_threshold_px=float(cfg["max_residual_p95_px"]) * scale,
    )
    diagnostics["sectorEvidence"] = evidence

    if sector_cfg["enabled"] and checks == ["residual_p95"]:
        reasons: list[str] = []
        suspect_ids = set(evidence["suspectSectorIds"])
        if not suspect_ids:
            reasons.append("no_localized_suspect_sector")
        if len(suspect_ids) > int(sector_cfg["max_excluded_sector_count"]):
            reasons.append("too_many_suspect_sectors")
        if any(
            float(run["totalAngleDeg"]) > float(sector_cfg["max_contiguous_excluded_deg"])
            for run in evidence["suspectRuns"]
        ):
            reasons.append("suspect_run_too_wide")
        sector_bins = np.floor(
            all_angle_indices * int(sector_cfg["sector_bin_count"]) / n_angles
        ).astype(int)
        retained = np.asarray([bin_id not in suspect_ids for bin_id in sector_bins], dtype=bool)
        retained_bins = len(set(sector_bins[retained].tolist())) / int(sector_cfg["sector_bin_count"])
        if retained_bins < float(sector_cfg["min_retained_angular_coverage"]):
            reasons.append("retained_coverage")
        refit_record = diagnostics["robustRefit"]
        refit_record.update({
            "excludedSectorIds": sorted(suspect_ids),
            "excludedPointCount": int(np.count_nonzero(~retained)),
            "retainedPointCount": int(np.count_nonzero(retained)),
            "retainedAngularCoverage": retained_bins,
        })
        if reasons:
            refit_record.update({"status": "rejected", "reasons": reasons})
        else:
            retained_points = xy[retained]
            retained_angles = all_angle_indices[retained]
            refit_record["attempted"] = True
            refit = tuple(map(float, robust_fit_circle(
                retained_points.tolist(), (fit_x, fit_y, fit_radius),
            )))
            refit_quality = _fit_quality(
                retained_points, retained_angles, refit, alignment=alignment,
                search=search, n_angles=n_angles, config=cfg, scale=scale,
            )
            center_delta = math.hypot(refit[0] - fit_x, refit[1] - fit_y)
            radius_delta = abs(refit[2] - fit_radius)
            if center_delta > float(sector_cfg["max_refit_center_delta_px"]) * scale:
                reasons.append("refit_center_delta")
            if radius_delta > float(sector_cfg["max_refit_radius_delta_px"]) * scale:
                reasons.append("refit_radius_delta")
            reasons.extend(f"refit_{check}" for check in refit_quality["failedChecks"])
            refit_record.update({
                "status": "rejected" if reasons else "accepted",
                "reasons": reasons,
                "initialCircle": _circle_dict((fit_x, fit_y, fit_radius)),
                "refitCircle": _circle_dict(refit),
                "centerDeltaPx": center_delta,
                "radiusDeltaPx": radius_delta,
                "residualP95Px": (
                    refit_quality["residualP95Px"]
                    if math.isfinite(refit_quality["residualP95Px"]) else None
                ),
                "failedChecks": refit_quality["failedChecks"],
            })
            if not reasons:
                checks.clear()
                diagnostics.update({
                    "physicalCircle": _circle_dict(refit),
                    "inlierCount": refit_quality["inlierCount"],
                    "inlierRatio": refit_quality["inlierRatio"],
                    "angularCoverage": refit_quality["angularCoverage"],
                    "residualP95Px": refit_quality["residualP95Px"],
                    "residualMarginPx": (
                        float(cfg["max_residual_p95_px"]) * scale
                        - float(refit_quality["residualP95Px"])
                    ),
                    "centerShiftPx": refit_quality["centerShiftPx"],
                    "radiusRatioToSearchPrior": refit_quality["radiusRatioToSearchPrior"],
                    "radiusRatioToAlignment": refit_quality["radiusRatioToAlignment"],
                })
    elif sector_cfg["enabled"]:
        diagnostics["robustRefit"].update({
            "status": "not_needed",
            "reasons": ["failure_not_residual_only"] if checks else ["initial_fit_accepted"],
        })
    if not checks:
        diagnostics["status"] = "accepted"
    return diagnostics
