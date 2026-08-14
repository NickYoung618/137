"""Fail-closed quality wrapper around the locked gyj physical-circle core."""

from __future__ import annotations

import math
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


def merged_physical_outer_circle_config(config: dict[str, Any] | None) -> dict[str, Any]:
    merged = {**DEFAULT_PHYSICAL_OUTER_CIRCLE_CONFIG, **(config or {})}
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
    return merged


def _circle_dict(circle: tuple[float, float, float]) -> dict[str, float]:
    return {"centerX": float(circle[0]), "centerY": float(circle[1]), "radiusPx": float(circle[2])}


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

    points: list[tuple[float, float]] = []
    point_angle_indices: list[int] = []
    n_angles = int(cfg["n_angles"])
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

    fit_x, fit_y, fit_radius = map(
        float,
        robust_fit_circle(points, (search[0], search[1], search[2])),
    )
    if not all(math.isfinite(value) for value in (fit_x, fit_y, fit_radius)) or fit_radius <= 0.0:
        diagnostics["failedChecks"].append("invalid_circle_fit")
        return diagnostics

    xy = np.asarray(points, dtype=float)
    residuals = np.abs(np.hypot(xy[:, 0] - fit_x, xy[:, 1] - fit_y) - fit_radius)
    inliers = residuals <= float(cfg["inlier_residual_px"]) * scale
    inlier_count = int(np.count_nonzero(inliers))
    inlier_ratio = inlier_count / len(points)
    angle_indices = np.asarray(point_angle_indices, dtype=int)[inliers]
    bins = np.floor(angle_indices * int(cfg["angular_bin_count"]) / n_angles).astype(int)
    coverage = len(set(bins.tolist())) / int(cfg["angular_bin_count"])
    residual_p95 = float(np.percentile(residuals[inliers], 95)) if inlier_count else math.inf
    center_shift = math.hypot(fit_x - search[0], fit_y - search[1])
    radius_ratio_search = fit_radius / search[2]
    radius_ratio_alignment = fit_radius / alignment[2]
    diagnostics.update({
        "physicalCircle": _circle_dict((fit_x, fit_y, fit_radius)),
        "inlierCount": inlier_count,
        "inlierRatio": inlier_ratio,
        "angularCoverage": coverage,
        "residualP95Px": residual_p95 if math.isfinite(residual_p95) else None,
        "centerShiftPx": center_shift,
        "radiusRatioToSearchPrior": radius_ratio_search,
        "radiusRatioToAlignment": radius_ratio_alignment,
    })
    checks = diagnostics["failedChecks"]
    if inlier_ratio < float(cfg["min_inlier_ratio"]): checks.append("inlier_ratio")
    if coverage < float(cfg["min_angular_coverage"]): checks.append("angular_coverage")
    if residual_p95 > float(cfg["max_residual_p95_px"]) * scale: checks.append("residual_p95")
    if center_shift > float(cfg["max_center_shift_px"]) * scale: checks.append("center_shift")
    if not float(cfg["min_radius_ratio"]) <= radius_ratio_search <= float(cfg["max_radius_ratio"]):
        checks.append("radius_ratio")
    if not checks:
        diagnostics["status"] = "accepted"
    return diagnostics
