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
    unknown = sorted(set(supplied) - set(DEFAULT_PHYSICAL_OUTER_CIRCLE_CONFIG) - {"sector_robustness"})
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
    return merged


def _circle_dict(circle: tuple[float, float, float]) -> dict[str, float]:
    return {"centerX": float(circle[0]), "centerY": float(circle[1]), "radiusPx": float(circle[2])}


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
