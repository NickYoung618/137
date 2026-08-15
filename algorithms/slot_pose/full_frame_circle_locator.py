"""Bounded full-frame housing-circle proposals with locked-gyj refinement.

The low-resolution component geometry in this module is deliberately only a
proposal mechanism.  A proposal cannot become the physical outer circle until
it passes a sparse call and then the existing full physical-circle quality gate.
"""

from __future__ import annotations

import math
import time
from collections import deque
from typing import Any, Callable

import numpy as np
from PIL import Image

from algorithms.slot_pose.physical_outer_circle import locate_physical_outer_circle


DEFAULT_FULL_FRAME_CIRCLE_LOCATOR_CONFIG: dict[str, Any] = {
    "schema_version": "full-frame-circle-locator/1",
    "enabled": False,
    "strategy_version": "otsu-components+sparse-gyj+full-gyj-v1",
    "downsample_factor": 16,
    "threshold_offsets": [0],
    "allowed_center_normalized": [0.05, 0.05, 0.95, 0.95],
    "min_radius_to_min_image_dim": 0.30,
    "max_radius_to_min_image_dim": 0.49,
    "min_component_area_ratio": 0.02,
    "min_bbox_aspect_ratio": 0.72,
    "min_fill_ratio": 0.15,
    "max_fill_ratio": 1.0,
    "allow_border_contact": False,
    "min_border_clearance_ratio": 0.01,
    "max_coarse_candidates": 6,
    "proposal_dedup_center_ratio": 0.04,
    "proposal_dedup_radius_ratio": 0.04,
    "physical_dedup_center_ratio": 0.02,
    "physical_dedup_radius_ratio": 0.02,
    "sparse_n_angles": 180,
    "sparse_min_edge_point_count": 45,
    "sparse_angular_bin_count": 36,
    "selection_min_score_margin": 0.05,
    "score_weights": {
        "inlier": 0.30,
        "coverage": 0.30,
        "residual": 0.20,
        "prior": 0.20,
    },
}


_CONFIG_KEYS = frozenset(DEFAULT_FULL_FRAME_CIRCLE_LOCATOR_CONFIG)


def _finite_number(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise ValueError(f"detector.full_frame_circle_locator.{field} must be finite")
    return float(value)


def merged_full_frame_circle_locator_config(config: dict[str, Any] | None) -> dict[str, Any]:
    if config is not None and not isinstance(config, dict):
        raise ValueError("detector.full_frame_circle_locator must be an object")
    unknown = set(config or {}) - _CONFIG_KEYS
    if unknown:
        raise ValueError(f"detector.full_frame_circle_locator has unknown fields: {sorted(unknown)}")
    merged = {**DEFAULT_FULL_FRAME_CIRCLE_LOCATOR_CONFIG, **(config or {})}
    merged["score_weights"] = {
        **DEFAULT_FULL_FRAME_CIRCLE_LOCATOR_CONFIG["score_weights"],
        **((config or {}).get("score_weights") or {}),
    }
    if merged["schema_version"] != "full-frame-circle-locator/1":
        raise ValueError("unsupported detector.full_frame_circle_locator.schema_version")
    if not isinstance(merged["enabled"], bool):
        raise ValueError("detector.full_frame_circle_locator.enabled must be boolean")
    if not isinstance(merged["strategy_version"], str) or not merged["strategy_version"].strip():
        raise ValueError("detector.full_frame_circle_locator.strategy_version must be non-empty")
    for field, minimum in (
        ("downsample_factor", 2),
        ("max_coarse_candidates", 1),
        ("sparse_n_angles", 36),
        ("sparse_min_edge_point_count", 8),
        ("sparse_angular_bin_count", 4),
    ):
        value = merged[field]
        if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
            raise ValueError(f"detector.full_frame_circle_locator.{field} must be an integer >= {minimum}")
    if merged["sparse_min_edge_point_count"] > merged["sparse_n_angles"]:
        raise ValueError("sparse_min_edge_point_count exceeds sparse_n_angles")
    if merged["sparse_angular_bin_count"] > merged["sparse_n_angles"]:
        raise ValueError("sparse_angular_bin_count exceeds sparse_n_angles")
    offsets = merged["threshold_offsets"]
    if (
        not isinstance(offsets, list) or not 1 <= len(offsets) <= 5
        or any(isinstance(item, bool) or not isinstance(item, int) or not -64 <= item <= 64 for item in offsets)
        or len(set(offsets)) != len(offsets)
    ):
        raise ValueError("detector.full_frame_circle_locator.threshold_offsets must contain 1..5 unique integers in [-64,64]")
    roi = merged["allowed_center_normalized"]
    if not isinstance(roi, list) or len(roi) != 4:
        raise ValueError("allowed_center_normalized must be [xmin,ymin,xmax,ymax]")
    values = [_finite_number(item, "allowed_center_normalized") for item in roi]
    if not (0.0 <= values[0] < values[2] <= 1.0 and 0.0 <= values[1] < values[3] <= 1.0):
        raise ValueError("allowed_center_normalized must be ordered within [0,1]")
    merged["allowed_center_normalized"] = values
    for field in (
        "min_radius_to_min_image_dim", "max_radius_to_min_image_dim",
        "min_component_area_ratio", "min_bbox_aspect_ratio", "min_fill_ratio",
        "max_fill_ratio", "min_border_clearance_ratio", "proposal_dedup_center_ratio",
        "proposal_dedup_radius_ratio", "physical_dedup_center_ratio",
        "physical_dedup_radius_ratio", "selection_min_score_margin",
    ):
        merged[field] = _finite_number(merged[field], field)
    if not 0.0 < merged["min_radius_to_min_image_dim"] < merged["max_radius_to_min_image_dim"] <= 0.75:
        raise ValueError("locator radius ratios must be ordered in (0,0.75]")
    for field in (
        "min_component_area_ratio", "min_bbox_aspect_ratio", "min_fill_ratio",
        "max_fill_ratio", "proposal_dedup_center_ratio", "proposal_dedup_radius_ratio",
        "physical_dedup_center_ratio", "physical_dedup_radius_ratio",
        "selection_min_score_margin",
    ):
        if not 0.0 <= merged[field] <= 1.0:
            raise ValueError(f"detector.full_frame_circle_locator.{field} must be in [0,1]")
    if merged["min_fill_ratio"] > merged["max_fill_ratio"]:
        raise ValueError("locator fill ratios must be ordered")
    if not isinstance(merged["allow_border_contact"], bool):
        raise ValueError("detector.full_frame_circle_locator.allow_border_contact must be boolean")
    if merged["min_border_clearance_ratio"] < 0.0:
        raise ValueError("min_border_clearance_ratio must be non-negative")
    weights = merged["score_weights"]
    if not isinstance(weights, dict) or set(weights) != {"inlier", "coverage", "residual", "prior"}:
        raise ValueError("locator score_weights must contain inlier, coverage, residual and prior")
    weights = {key: _finite_number(value, f"score_weights.{key}") for key, value in weights.items()}
    if any(value < 0.0 for value in weights.values()) or not math.isclose(sum(weights.values()), 1.0, abs_tol=1e-9):
        raise ValueError("locator score_weights must be non-negative and sum to 1")
    merged["score_weights"] = weights
    return merged


def _otsu_threshold(image: np.ndarray) -> int:
    histogram = np.bincount(image.reshape(-1), minlength=256).astype(float)
    count = float(image.size)
    total = float(np.dot(np.arange(256, dtype=float), histogram))
    background_count = 0.0
    background_total = 0.0
    best_variance = -1.0
    best = 0
    for threshold in range(255):
        background_count += histogram[threshold]
        if background_count <= 0.0:
            continue
        foreground_count = count - background_count
        if foreground_count <= 0.0:
            break
        background_total += threshold * histogram[threshold]
        mean_background = background_total / background_count
        mean_foreground = (total - background_total) / foreground_count
        variance = background_count * foreground_count * (mean_background - mean_foreground) ** 2
        if variance > best_variance:
            best_variance = variance
            best = threshold
    return best


def _downsample_uint8(gray: np.ndarray, factor: int) -> np.ndarray:
    if not isinstance(gray, np.ndarray) or gray.ndim != 2 or gray.size == 0:
        raise ValueError("full-frame locator requires a non-empty 2-D grayscale image")
    if not np.isfinite(gray).all():
        raise ValueError("full-frame locator input must contain only finite pixels")
    source = np.clip(gray, 0.0, 255.0).astype(np.uint8, copy=False)
    height, width = source.shape
    small_size = (max(2, math.ceil(width / factor)), max(2, math.ceil(height / factor)))
    return np.asarray(Image.fromarray(source, mode="L").resize(small_size, Image.Resampling.BILINEAR))


def _components(mask: np.ndarray) -> list[dict[str, int]]:
    height, width = mask.shape
    visited = np.zeros(mask.shape, dtype=bool)
    output: list[dict[str, int]] = []
    for y0, x0 in np.argwhere(mask):
        y = int(y0)
        x = int(x0)
        if visited[y, x]:
            continue
        visited[y, x] = True
        queue: deque[tuple[int, int]] = deque([(x, y)])
        min_x = max_x = x
        min_y = max_y = y
        count = 0
        while queue:
            current_x, current_y = queue.pop()
            count += 1
            min_x = min(min_x, current_x)
            max_x = max(max_x, current_x)
            min_y = min(min_y, current_y)
            max_y = max(max_y, current_y)
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    if dx == 0 and dy == 0:
                        continue
                    nx, ny = current_x + dx, current_y + dy
                    if 0 <= nx < width and 0 <= ny < height and mask[ny, nx] and not visited[ny, nx]:
                        visited[ny, nx] = True
                        queue.append((nx, ny))
        output.append({"minX": min_x, "minY": min_y, "maxX": max_x, "maxY": max_y, "count": count})
    return output


def _same_circle(a: dict[str, Any], b: dict[str, Any], center_ratio: float, radius_ratio: float) -> bool:
    smaller = min(float(a["radiusPx"]), float(b["radiusPx"]))
    if smaller <= 0.0:
        return False
    center_distance = math.hypot(float(a["centerX"]) - float(b["centerX"]), float(a["centerY"]) - float(b["centerY"]))
    return center_distance <= max(2.0, center_ratio * smaller) and abs(float(a["radiusPx"]) - float(b["radiusPx"])) <= radius_ratio * smaller


def extract_component_proposals(gray: np.ndarray, config: dict[str, Any] | None) -> list[dict[str, Any]]:
    cfg = merged_full_frame_circle_locator_config(config)
    factor = int(cfg["downsample_factor"])
    small = _downsample_uint8(gray, factor)
    small_height, small_width = small.shape
    original_height, original_width = gray.shape
    base_threshold = _otsu_threshold(small)
    raw: list[dict[str, Any]] = []
    min_component_pixels = max(4, math.ceil(float(cfg["min_component_area_ratio"]) * small.size))
    for offset in cfg["threshold_offsets"]:
        threshold = max(0, min(254, base_threshold + int(offset)))
        for component in _components(small > threshold):
            if component["count"] < min_component_pixels:
                continue
            bbox_width = component["maxX"] - component["minX"] + 1
            bbox_height = component["maxY"] - component["minY"] + 1
            center_small_x = (component["minX"] + component["maxX"] + 1.0) / 2.0
            center_small_y = (component["minY"] + component["maxY"] + 1.0) / 2.0
            radius_small = (bbox_width + bbox_height) / 4.0
            radius = radius_small * factor
            center_x = center_small_x * factor
            center_y = center_small_y * factor
            aspect = min(bbox_width, bbox_height) / max(bbox_width, bbox_height)
            fill = component["count"] / float(bbox_width * bbox_height)
            clearance_small = min(
                component["minX"], component["minY"],
                small_width - 1 - component["maxX"], small_height - 1 - component["maxY"],
            )
            clearance_ratio = clearance_small / max(radius_small, 1e-9)
            failed: list[str] = []
            allowed = cfg["allowed_center_normalized"]
            normalized_x = center_x / original_width
            normalized_y = center_y / original_height
            radius_ratio = radius / min(original_width, original_height)
            if not (allowed[0] <= normalized_x <= allowed[2] and allowed[1] <= normalized_y <= allowed[3]):
                failed.append("center_region")
            if not cfg["min_radius_to_min_image_dim"] <= radius_ratio <= cfg["max_radius_to_min_image_dim"]:
                failed.append("radius_range")
            if aspect < cfg["min_bbox_aspect_ratio"]:
                failed.append("bbox_aspect_ratio")
            if not cfg["min_fill_ratio"] <= fill <= cfg["max_fill_ratio"]:
                failed.append("fill_ratio")
            if not cfg["allow_border_contact"] and clearance_ratio < cfg["min_border_clearance_ratio"]:
                failed.append("border_clearance")
            raw.append({
                "proposalId": None,
                "threshold": threshold,
                "thresholds": [threshold],
                "bboxNormalized": [
                    component["minX"] * factor / original_width,
                    component["minY"] * factor / original_height,
                    min(original_width, (component["maxX"] + 1) * factor) / original_width,
                    min(original_height, (component["maxY"] + 1) * factor) / original_height,
                ],
                "centerX": center_x,
                "centerY": center_y,
                "radiusPx": radius,
                "referenceScale": None,
                "componentPixelCount": int(component["count"]),
                "componentAreaRatio": component["count"] / float(small.size),
                "bboxAspectRatio": aspect,
                "fillRatio": fill,
                "borderClearanceRatio": clearance_ratio,
                "status": "eligible" if not failed else "rejected",
                "failedChecks": failed,
            })
    deduplicated: list[dict[str, Any]] = []
    for item in sorted(raw, key=lambda value: (value["centerY"], value["centerX"], value["radiusPx"], value["threshold"])):
        match = next((prior for prior in deduplicated if _same_circle(
            item, prior, cfg["proposal_dedup_center_ratio"], cfg["proposal_dedup_radius_ratio"],
        )), None)
        if match is None:
            deduplicated.append(item)
        else:
            match["thresholds"] = sorted(set(match["thresholds"] + item["thresholds"]))
            if match["status"] == "rejected" and item["status"] == "eligible":
                thresholds = match["thresholds"]
                match.update(item)
                match["thresholds"] = thresholds
    for index, item in enumerate(deduplicated, start=1):
        item["proposalId"] = f"proposal-{index:03d}"
    return deduplicated


def _score_candidate(physical: dict[str, Any], proposal: dict[str, Any], cfg: dict[str, Any], final_cfg: dict[str, Any]) -> tuple[dict[str, float], float]:
    inlier = max(0.0, min(1.0, float(physical["inlierRatio"])))
    coverage = max(0.0, min(1.0, float(physical["angularCoverage"])))
    residual_value = float(physical["residualP95Px"])
    residual_limit = float(final_cfg.get("max_residual_p95_px", 5.0))
    residual = max(0.0, 1.0 - residual_value / max(residual_limit, 1e-9))
    fit = physical["physicalCircle"]
    prior_error = (
        math.hypot(float(fit["centerX"]) - float(proposal["centerX"]), float(fit["centerY"]) - float(proposal["centerY"]))
        + abs(float(fit["radiusPx"]) - float(proposal["radiusPx"]))
    ) / max(float(proposal["radiusPx"]), 1e-9)
    prior = max(0.0, 1.0 - prior_error)
    components = {"inlier": inlier, "coverage": coverage, "residual": residual, "prior": prior}
    score = sum(float(cfg["score_weights"][key]) * value for key, value in components.items())
    return components, score


def locate_full_frame_circle(
    gray: np.ndarray,
    reference_circle: tuple[float, float, float],
    outer_boundary_edge_point: Callable[..., tuple[float, float] | None],
    robust_fit_circle: Callable[..., tuple[float, float, float]],
    config: dict[str, Any] | None,
    *,
    final_physical_config: dict[str, Any] | None,
    source_sha256: str,
) -> dict[str, Any]:
    cfg = merged_full_frame_circle_locator_config(config)
    started = time.perf_counter_ns()
    diagnostics: dict[str, Any] = {
        "schemaVersion": "full-frame-circle-localization/1",
        "strategy": cfg["strategy_version"],
        "status": "not_found",
        "bestCandidateId": None,
        "secondCandidateId": None,
        "bestScore": None,
        "secondBestScore": None,
        "scoreMargin": None,
        "selectedCandidateId": None,
        "componentProposals": [],
        "circleCandidates": [],
        "clusters": [],
        "finalPhysicalCircle": None,
        "finalPhysicalCircleDiagnostics": None,
        "failedChecks": [],
        "timingMs": {},
    }
    proposal_started = time.perf_counter_ns()
    proposals = extract_component_proposals(gray, cfg)
    diagnostics["componentProposals"] = proposals
    diagnostics["timingMs"]["proposalExtraction"] = (time.perf_counter_ns() - proposal_started) / 1e6
    eligible = [item for item in proposals if item["status"] == "eligible"]
    if not eligible:
        diagnostics["failedChecks"] = ["no_eligible_component"]
        diagnostics["timingMs"].update({"sparseAssessment": 0.0, "selection": 0.0, "finalRefinement": 0.0})
        diagnostics["timingMs"]["totalLocalization"] = (time.perf_counter_ns() - started) / 1e6
        return diagnostics
    if len(eligible) > int(cfg["max_coarse_candidates"]):
        diagnostics["status"] = "overflow"
        diagnostics["failedChecks"] = ["coarse_candidate_overflow"]
        diagnostics["timingMs"].update({"sparseAssessment": 0.0, "selection": 0.0, "finalRefinement": 0.0})
        diagnostics["timingMs"]["totalLocalization"] = (time.perf_counter_ns() - started) / 1e6
        return diagnostics
    reference_radius = float(reference_circle[2])
    sparse_started = time.perf_counter_ns()
    sparse_cfg = {
        **(final_physical_config or {}),
        "threshold_version": f"{cfg['strategy_version']}/sparse",
        "n_angles": int(cfg["sparse_n_angles"]),
        "min_edge_point_count": int(cfg["sparse_min_edge_point_count"]),
        "angular_bin_count": int(cfg["sparse_angular_bin_count"]),
    }
    candidates: list[dict[str, Any]] = []
    for index, proposal in enumerate(eligible, start=1):
        proposal["referenceScale"] = float(proposal["radiusPx"]) / reference_radius
        physical = locate_physical_outer_circle(
            gray,
            (float(proposal["centerX"]), float(proposal["centerY"])),
            float(proposal["radiusPx"]),
            (float(proposal["centerX"]), float(proposal["centerY"])),
            float(proposal["radiusPx"]),
            outer_boundary_edge_point,
            robust_fit_circle,
            sparse_cfg,
            source_sha256=source_sha256,
            pixel_scale=float(proposal["referenceScale"]),
        )
        accepted = physical["status"] == "accepted"
        components = None
        score = None
        if accepted:
            components, score = _score_candidate(physical, proposal, cfg, sparse_cfg)
        candidates.append({
            "candidateId": f"circle-candidate-{index:03d}",
            "rank": None,
            "proposalId": proposal["proposalId"],
            "status": "accepted" if accepted else "rejected",
            "coarsePhysicalCircle": physical.get("physicalCircle"),
            "edgePointCount": physical.get("edgePointCount", 0),
            "inlierCount": physical.get("inlierCount", 0),
            "inlierRatio": physical.get("inlierRatio", 0.0),
            "angularCoverage": physical.get("angularCoverage", 0.0),
            "residualP95Px": physical.get("residualP95Px"),
            "centerShiftPx": physical.get("centerShiftPx"),
            "scoreComponents": components,
            "score": score,
            "failedChecks": list(physical.get("failedChecks") or []),
        })
    diagnostics["timingMs"]["sparseAssessment"] = (time.perf_counter_ns() - sparse_started) / 1e6
    ranked = sorted(
        (item for item in candidates if item["status"] == "accepted"),
        key=lambda item: (-float(item["score"]), item["candidateId"]),
    )
    for rank, item in enumerate(ranked, start=1):
        item["rank"] = rank
    diagnostics["circleCandidates"] = candidates
    selection_started = time.perf_counter_ns()
    clusters: list[dict[str, Any]] = []
    for candidate in ranked:
        circle = candidate["coarsePhysicalCircle"]
        assert circle is not None
        match = next((cluster for cluster in clusters if _same_circle(
            circle,
            cluster["representativeCircle"],
            cfg["physical_dedup_center_ratio"], cfg["physical_dedup_radius_ratio"],
        )), None)
        if match is None:
            clusters.append({
                "clusterId": None,
                "memberCandidateIds": [candidate["candidateId"]],
                "representativeCandidateId": candidate["candidateId"],
                "representativeCircle": circle,
                "score": candidate["score"],
            })
        else:
            match["memberCandidateIds"].append(candidate["candidateId"])
    clusters.sort(key=lambda item: (-float(item["score"]), item["representativeCandidateId"]))
    for index, cluster in enumerate(clusters, start=1):
        cluster["clusterId"] = f"circle-cluster-{index:03d}"
    diagnostics["clusters"] = clusters
    if not clusters:
        diagnostics["failedChecks"] = ["no_sparse_physical_candidate"]
        diagnostics["timingMs"]["selection"] = (time.perf_counter_ns() - selection_started) / 1e6
        diagnostics["timingMs"]["finalRefinement"] = 0.0
        diagnostics["timingMs"]["totalLocalization"] = (time.perf_counter_ns() - started) / 1e6
        return diagnostics
    best = clusters[0]
    second = clusters[1] if len(clusters) > 1 else None
    diagnostics.update({
        "bestCandidateId": best["representativeCandidateId"],
        "secondCandidateId": None if second is None else second["representativeCandidateId"],
        "bestScore": float(best["score"]),
        "secondBestScore": None if second is None else float(second["score"]),
        "scoreMargin": None if second is None else float(best["score"] - second["score"]),
    })
    if second is not None and float(diagnostics["scoreMargin"]) < float(cfg["selection_min_score_margin"]):
        diagnostics["status"] = "ambiguous"
        diagnostics["failedChecks"] = ["selection_score_margin"]
        diagnostics["timingMs"]["selection"] = (time.perf_counter_ns() - selection_started) / 1e6
        diagnostics["timingMs"]["finalRefinement"] = 0.0
        diagnostics["timingMs"]["totalLocalization"] = (time.perf_counter_ns() - started) / 1e6
        return diagnostics
    diagnostics["selectedCandidateId"] = best["representativeCandidateId"]
    diagnostics["timingMs"]["selection"] = (time.perf_counter_ns() - selection_started) / 1e6
    final_started = time.perf_counter_ns()
    winner = next(item for item in candidates if item["candidateId"] == best["representativeCandidateId"])
    # Re-run the authoritative 720-ray gate from the original component seed.
    # The sparse fitted center is selection evidence, not a new search prior:
    # moving the ray origin after sparse fitting changes which physical edge an
    # outermost-crossing ray sees near fixture contacts.
    search = next(item for item in eligible if item["proposalId"] == winner["proposalId"])
    final_scale = float(search["radiusPx"]) / reference_radius
    final = locate_physical_outer_circle(
        gray,
        (float(search["centerX"]), float(search["centerY"])),
        float(search["radiusPx"]),
        (float(search["centerX"]), float(search["centerY"])),
        float(search["radiusPx"]),
        outer_boundary_edge_point,
        robust_fit_circle,
        final_physical_config,
        source_sha256=source_sha256,
        pixel_scale=final_scale,
    )
    diagnostics["timingMs"]["finalRefinement"] = (time.perf_counter_ns() - final_started) / 1e6
    diagnostics["finalPhysicalCircleDiagnostics"] = final
    if final["status"] != "accepted":
        diagnostics["status"] = "refinement_failed"
        diagnostics["failedChecks"] = ["final_physical_circle"] + list(final.get("failedChecks") or [])
    else:
        diagnostics["status"] = "accepted"
        diagnostics["finalPhysicalCircle"] = final["physicalCircle"]
    diagnostics["timingMs"]["totalLocalization"] = (time.perf_counter_ns() - started) / 1e6
    return diagnostics
