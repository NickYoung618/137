"""Robustly refine the physical housing outer circle from an alignment prior."""

from __future__ import annotations

import math
from typing import Any, Callable

import numpy as np


DEFAULT_PHYSICAL_OUTER_CIRCLE_CONFIG: dict[str, Any] = {
    "threshold_version": "physical-outer-circle-v1",
    "n_angles": 720,
    "n_radii": 241,
    "inner_search_offset_px": -40.0,
    "outer_search_offset_px": 200.0,
    "edge_window_px": 7,
    "edge_gap_px": 3,
    "min_edge_contrast": 25.0,
    "min_inner_intensity": 35.0,
    "inlier_residual_px": 8.0,
    "min_inlier_ratio": 0.80,
    "angular_bin_count": 36,
    "min_angular_coverage": 0.65,
    "max_residual_p95_px": 5.0,
    "max_center_shift_px": 80.0,
    "min_radius_ratio": 0.97,
    "max_radius_ratio": 1.10,
}


def merged_physical_outer_circle_config(config: dict[str, Any] | None) -> dict[str, Any]:
    merged = {**DEFAULT_PHYSICAL_OUTER_CIRCLE_CONFIG, **(config or {})}
    if not isinstance(merged["threshold_version"], str) or not merged["threshold_version"].strip():
        raise ValueError("detector.physical_outer_circle.threshold_version must be non-empty")
    for key in ("n_angles", "n_radii", "edge_window_px", "edge_gap_px", "angular_bin_count"):
        if not isinstance(merged[key], int) or merged[key] <= 0:
            raise ValueError(f"detector.physical_outer_circle.{key} must be a positive integer")
    if merged["n_angles"] < merged["angular_bin_count"] or merged["n_radii"] < 21:
        raise ValueError("detector.physical_outer_circle sampling is too sparse")
    if not float(merged["inner_search_offset_px"]) < float(merged["outer_search_offset_px"]):
        raise ValueError("detector.physical_outer_circle search offsets must be ordered")
    for key in ("min_inlier_ratio", "min_angular_coverage"):
        if not 0.0 < float(merged[key]) <= 1.0:
            raise ValueError(f"detector.physical_outer_circle.{key} must be in (0,1]")
    for key in ("min_edge_contrast", "min_inner_intensity", "inlier_residual_px",
                "max_residual_p95_px", "max_center_shift_px"):
        if float(merged[key]) <= 0.0:
            raise ValueError(f"detector.physical_outer_circle.{key} must be positive")
    if not 0.0 < float(merged["min_radius_ratio"]) < float(merged["max_radius_ratio"]):
        raise ValueError("detector.physical_outer_circle radius ratios must be ordered and positive")
    return merged


def locate_physical_outer_circle(
    gray: np.ndarray,
    alignment_center: tuple[float, float],
    alignment_radius_px: float,
    polar_resample: Callable[..., np.ndarray],
    robust_fit_circle: Callable[..., tuple[float, float, float]],
    config: dict[str, Any] | None,
    *,
    pixel_scale: float = 1.0,
) -> dict[str, Any]:
    """Locate the outermost metal-to-background edge and return fail-closed quality evidence."""
    cfg = merged_physical_outer_circle_config(config)
    cx, cy = map(float, alignment_center)
    radius = float(alignment_radius_px)
    scale = float(pixel_scale)
    diagnostics: dict[str, Any] = {
        "status": "failed",
        "thresholdVersion": cfg["threshold_version"],
        "alignmentCircle": {"centerX": cx, "centerY": cy, "radiusPx": radius},
        "physicalCircle": None,
        "edgePointCount": 0,
        "inlierCount": 0,
        "inlierRatio": 0.0,
        "angularCoverage": 0.0,
        "residualP95Px": None,
        "failedChecks": [],
    }
    if gray.ndim != 2 or not all(math.isfinite(v) for v in (cx, cy, radius, scale)) or radius <= 0 or scale <= 0:
        diagnostics["failedChecks"].append("invalid_alignment_prior")
        return diagnostics

    inner = radius + float(cfg["inner_search_offset_px"]) * scale
    outer = radius + float(cfg["outer_search_offset_px"]) * scale
    edge_window = int(cfg["edge_window_px"])
    edge_gap = int(cfg["edge_gap_px"])
    n_radii = int(cfg["n_radii"])
    margin = edge_window + edge_gap + 1
    if inner <= 0 or n_radii <= 2 * margin + 1:
        diagnostics["failedChecks"].append("invalid_search_band")
        return diagnostics

    polar = np.asarray(polar_resample(gray, (cx, cy), inner, outer, n_radii, int(cfg["n_angles"])), dtype=float)
    if polar.shape != (n_radii, int(cfg["n_angles"])) or not np.isfinite(polar).all():
        diagnostics["failedChecks"].append("invalid_polar_samples")
        return diagnostics
    cumulative = np.vstack((np.zeros((1, polar.shape[1])), np.cumsum(polar, axis=0)))
    contrast = np.full_like(polar, -np.inf)
    for row in range(margin, n_radii - margin):
        inner_mean = (cumulative[row - edge_gap] - cumulative[row - edge_gap - edge_window]) / edge_window
        outer_mean = (cumulative[row + edge_gap + edge_window + 1] - cumulative[row + edge_gap + 1]) / edge_window
        contrast[row] = inner_mean - outer_mean

    radii = np.linspace(inner, outer, n_radii)
    angles = np.linspace(0.0, 2.0 * math.pi, polar.shape[1], endpoint=False)
    selected_rows: list[int] = []
    selected_angles: list[int] = []
    for column in range(polar.shape[1]):
        eligible = np.flatnonzero(
            (contrast[:, column] >= float(cfg["min_edge_contrast"]))
            & (polar[:, column] >= float(cfg["min_inner_intensity"]))
        )
        if eligible.size:
            selected_rows.append(int(eligible[-1]))
            selected_angles.append(column)
    diagnostics["edgePointCount"] = len(selected_rows)
    if len(selected_rows) < max(8, int(cfg["angular_bin_count"])):
        diagnostics["failedChecks"].append("insufficient_edge_points")
        return diagnostics

    chosen_radii = radii[np.asarray(selected_rows)]
    chosen_angles = angles[np.asarray(selected_angles)]
    xs = cx + chosen_radii * np.cos(chosen_angles)
    ys = cy + chosen_radii * np.sin(chosen_angles)
    fit_x, fit_y, fit_radius = map(float, robust_fit_circle(list(zip(xs, ys)), (cx, cy, radius)))
    residuals = np.abs(np.hypot(xs - fit_x, ys - fit_y) - fit_radius)
    inlier_gate = float(cfg["inlier_residual_px"]) * scale
    inliers = residuals <= inlier_gate
    inlier_count = int(np.count_nonzero(inliers))
    inlier_ratio = inlier_count / len(residuals)
    bins = np.floor(np.asarray(selected_angles)[inliers] * int(cfg["angular_bin_count"]) / polar.shape[1]).astype(int)
    coverage = len(set(bins.tolist())) / int(cfg["angular_bin_count"])
    residual_p95 = float(np.percentile(residuals[inliers], 95)) if inlier_count else math.inf
    center_shift = math.hypot(fit_x - cx, fit_y - cy)
    radius_ratio = fit_radius / radius
    diagnostics.update({
        "physicalCircle": {"centerX": fit_x, "centerY": fit_y, "radiusPx": fit_radius},
        "inlierCount": inlier_count,
        "inlierRatio": inlier_ratio,
        "angularCoverage": coverage,
        "residualP95Px": residual_p95 if math.isfinite(residual_p95) else None,
        "centerShiftPx": center_shift,
        "radiusRatioToAlignment": radius_ratio,
    })
    checks = diagnostics["failedChecks"]
    if inlier_ratio < float(cfg["min_inlier_ratio"]): checks.append("inlier_ratio")
    if coverage < float(cfg["min_angular_coverage"]): checks.append("angular_coverage")
    if residual_p95 > float(cfg["max_residual_p95_px"]) * scale: checks.append("residual_p95")
    if center_shift > float(cfg["max_center_shift_px"]) * scale: checks.append("center_shift")
    if not float(cfg["min_radius_ratio"]) <= radius_ratio <= float(cfg["max_radius_ratio"]): checks.append("radius_ratio")
    if not checks:
        diagnostics["status"] = "accepted"
    return diagnostics
