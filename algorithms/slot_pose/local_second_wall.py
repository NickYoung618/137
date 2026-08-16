"""Default-off diagnostic search for a second wall in one local dark opening.

The module never promotes a hypothesis to the authoritative single-groove pose.
It reuses the existing subpixel side sampler/line fitter and source-consistency
evidence, while retaining every rejected hypothesis for audit.
"""

from __future__ import annotations

import copy
import math
from typing import Any, Callable

import numpy as np

from algorithms.slot_pose.angular_profile import circular_distance_deg, wrap_360_deg
from algorithms.slot_pose.groove_refinement import (
    _profile_evidence,
    _select_consensus_line,
    _side_points,
    merged_groove_refinement_config,
)
from algorithms.slot_pose.sidewall_consistency import assess_sidewall_source_consistency


DEFAULT_LOCAL_SECOND_WALL_CONFIG: dict[str, Any] = {
    "schema_version": "local-second-wall-diagnostic/2",
    "enabled": False,
    "threshold_version": "local-second-wall-diagnostic-v2",
    "scan_step_deg": 1.0,
    "inward_search_extent_deg": 30.0,
    "outward_search_extent_deg": 30.0,
    "max_seeds_per_domain": 32,
    "max_total_search_jobs": 256,
    "max_wall_candidates": 32,
    "min_wall_separation_deg": 2.0,
    "max_wall_separation_deg": 30.0,
    "max_parallel_difference_deg": 25.0,
    "max_endpoint_circle_residual_px": 0.50,
    "min_radial_coverage": 0.60,
    "max_radial_coverage_difference": 0.20,
    "min_opening_dark_fraction": 0.70,
    "opening_sample_angles": 9,
    "opening_sample_radii": 9,
    "candidate_merge_deg": 0.50,
}


def validate_local_second_wall_config(config: dict[str, Any]) -> None:
    if not isinstance(config, dict):
        raise ValueError("detector.local_second_wall_diagnostic must be an object")
    required = set(DEFAULT_LOCAL_SECOND_WALL_CONFIG)
    missing, unknown = sorted(required - set(config)), sorted(set(config) - required)
    if missing:
        raise ValueError(f"local_second_wall_diagnostic missing fields: {missing}")
    if unknown:
        raise ValueError(f"local_second_wall_diagnostic has unknown fields: {unknown}")
    if config["schema_version"] != "local-second-wall-diagnostic/2":
        raise ValueError("local_second_wall_diagnostic.schema_version is unsupported")
    if not isinstance(config["enabled"], bool):
        raise ValueError("local_second_wall_diagnostic.enabled must be boolean")
    if not isinstance(config["threshold_version"], str) or not config["threshold_version"].strip():
        raise ValueError("local_second_wall_diagnostic.threshold_version must be non-empty")
    for key in (
        "max_seeds_per_domain", "max_total_search_jobs", "max_wall_candidates",
        "opening_sample_angles", "opening_sample_radii",
    ):
        value = config[key]
        minimum, maximum = ((8, 1024) if key == "max_total_search_jobs" else (2, 256))
        if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
            raise ValueError(
                f"local_second_wall_diagnostic.{key} must be an integer in [{minimum},{maximum}]"
            )
    for key in (
        "scan_step_deg", "inward_search_extent_deg", "outward_search_extent_deg",
        "min_wall_separation_deg",
        "max_wall_separation_deg", "max_parallel_difference_deg", "candidate_merge_deg",
        "max_endpoint_circle_residual_px",
    ):
        value = config[key]
        if (
            isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(float(value)) or not 0.0 < float(value) <= 180.0
        ):
            raise ValueError(f"local_second_wall_diagnostic.{key} must be in (0,180]")
    for key in (
        "min_radial_coverage", "max_radial_coverage_difference", "min_opening_dark_fraction",
    ):
        value = config[key]
        if (
            isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(float(value)) or not 0.0 <= float(value) <= 1.0
        ):
            raise ValueError(f"local_second_wall_diagnostic.{key} must be in [0,1]")
    if float(config["min_wall_separation_deg"]) >= float(config["max_wall_separation_deg"]):
        raise ValueError("local_second_wall_diagnostic wall separation bounds must be ordered")
    if max(
        float(config["inward_search_extent_deg"]),
        float(config["outward_search_extent_deg"]),
    ) > float(config["max_wall_separation_deg"]):
        raise ValueError(
            "local_second_wall_diagnostic search extents must not exceed physical wall separation"
        )


def merged_local_second_wall_config(config: dict[str, Any] | None) -> dict[str, Any]:
    if config is not None and not isinstance(config, dict):
        raise ValueError("detector.local_second_wall_diagnostic must be an object")
    merged = copy.deepcopy(DEFAULT_LOCAL_SECOND_WALL_CONFIG)
    if config:
        merged.update(copy.deepcopy(config))
    validate_local_second_wall_config(merged)
    return merged


def _base(config: dict[str, Any], status: str) -> dict[str, Any]:
    return {
        "schemaVersion": "local-second-wall-diagnostic/4",
        "thresholdVersion": config["threshold_version"],
        "enabled": bool(config["enabled"]),
        "status": status,
        "failureStage": None,
        "errorCode": None,
        "authoritative": False,
        "posePromotionAllowed": False,
        "anchorEvidence": [],
        "searchDomains": [],
        "sideSearchCandidates": [],
        "sideSearchMergeClusters": [],
        "searchOutcomeSummary": {},
        "rawHypotheses": [],
        "hypothesisMergeClusters": [],
        "hypotheses": [],
        "canonicalWallPairs": [],
        "experimentalCandidate": None,
        "partialObservation": None,
    }


def _domain_wraps(start_deg: float, end_deg: float, signed_direction: int) -> bool:
    if signed_direction > 0:
        return end_deg < start_deg
    return end_deg > start_deg


def _build_search_domains(
    local_start: float,
    local_span: float,
    anchor_angles: dict[str, float],
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    """Build bounded domains on both sides of each untrusted coarse endpoint."""
    step = float(config["scan_step_deg"])
    inward_span = min(float(config["inward_search_extent_deg"]), 0.5 * float(local_span))
    outward_span = float(config["outward_search_extent_deg"])
    definitions = (
        ("startSide", "INWARD", 1, inward_span),
        ("startSide", "OUTWARD", -1, outward_span),
        ("endSide", "INWARD", -1, inward_span),
        ("endSide", "OUTWARD", 1, outward_span),
    )
    domains: list[dict[str, Any]] = []
    for anchor_side, direction, signed_direction, span in definitions:
        start = wrap_360_deg(float(anchor_angles[anchor_side]))
        end = wrap_360_deg(start + signed_direction * span)
        seed_count = min(
            int(config["max_seeds_per_domain"]),
            max(2, int(math.ceil(span / step)) + 1),
        )
        seeds = [
            wrap_360_deg(start + signed_direction * span * index / (seed_count - 1))
            for index in range(seed_count)
        ]
        domains.append({
            "domainId": f"{anchor_side}-{direction.lower()}",
            "anchorSide": anchor_side,
            "direction": direction,
            "signedDirection": signed_direction,
            "startDeg": start,
            "endDeg": end,
            "spanDeg": float(span),
            "wrapsBoundary": _domain_wraps(start, end, signed_direction),
            "seedCount": seed_count,
            "seedAnglesDeg": seeds,
            "physicalLimitDeg": float(config["max_wall_separation_deg"]),
            "source": "untrusted_coarse_endpoint",
        })
    return domains


def _canonical_pair_id(first_cluster_id: str, second_cluster_id: str) -> str:
    first, second = sorted((str(first_cluster_id), str(second_cluster_id)))
    return f"canonical-wall-pair:{first}|{second}"


def _inside_interval(angle: float, start: float, span: float, margin: float) -> bool:
    return ((float(angle) - (float(start) - margin)) % 360.0) <= span + 2.0 * margin


def _line_parallel_difference(first: dict[str, Any], second: dict[str, Any]) -> float | None:
    try:
        left = np.asarray((float(first["line"]["a"]), float(first["line"]["b"])), dtype=float)
        right = np.asarray((float(second["line"]["a"]), float(second["line"]["b"])), dtype=float)
    except (KeyError, TypeError, ValueError):
        return None
    denominator = float(np.linalg.norm(left) * np.linalg.norm(right))
    if denominator <= 1e-12:
        return None
    cosine = max(-1.0, min(1.0, abs(float(np.dot(left, right))) / denominator))
    return math.degrees(math.acos(cosine))


def _radial_coverage(side: dict[str, Any]) -> float | None:
    try:
        value = float(side["profileEvidence"]["radialCoverage"])
    except (KeyError, TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def _opening_dark_fraction(
    gray: np.ndarray,
    center: tuple[float, float],
    outer_radius: float,
    start_deg: float,
    span_deg: float,
    depth_px: float,
    start_side: dict[str, Any],
    end_side: dict[str, Any],
    bilinear_sample: Callable[[np.ndarray, np.ndarray, np.ndarray], np.ndarray],
    refinement_config: dict[str, Any],
    config: dict[str, Any],
    pixel_scale: float,
) -> tuple[float | None, dict[str, Any]]:
    profiles = [start_side.get("profileEvidence"), end_side.get("profileEvidence")]
    if not all(isinstance(item, dict) for item in profiles):
        return None, {"sampleCount": 0, "finiteCount": 0, "thresholdGray": None}
    try:
        metal = float(np.median([float(item["metalLevelMedian"]) for item in profiles]))
        dark = float(np.median([float(item["grooveLevelMedian"]) for item in profiles]))
    except (KeyError, TypeError, ValueError):
        return None, {"sampleCount": 0, "finiteCount": 0, "thresholdGray": None}
    threshold = 0.5 * (metal + dark)
    angular_margin = min(0.25 * span_deg, max(0.15, 0.08 * span_deg))
    if span_deg <= 2.0 * angular_margin:
        return None, {"sampleCount": 0, "finiteCount": 0, "thresholdGray": threshold}
    angles = np.linspace(
        start_deg + angular_margin, start_deg + span_deg - angular_margin,
        int(config["opening_sample_angles"]), dtype=float,
    )
    minimum_inset = float(refinement_config["radial_inset_min_px"]) * pixel_scale
    maximum_inset = min(
        float(refinement_config["radial_inset_max_px"]) * pixel_scale,
        0.80 * float(depth_px),
    )
    if maximum_inset <= minimum_inset:
        return None, {"sampleCount": 0, "finiteCount": 0, "thresholdGray": threshold}
    radii = outer_radius - np.linspace(
        minimum_inset, maximum_inset, int(config["opening_sample_radii"]), dtype=float,
    )
    mesh_angles, mesh_radii = np.meshgrid(angles, radii)
    radians = np.radians(mesh_angles)
    xs = center[0] + mesh_radii * np.cos(radians)
    ys = center[1] + mesh_radii * np.sin(radians)
    values = np.asarray(bilinear_sample(gray, xs.ravel(), ys.ravel()), dtype=float)
    finite = np.isfinite(values)
    fraction = None if not bool(np.any(finite)) else float(np.mean(values[finite] <= threshold))
    return fraction, {
        "sampleCount": int(values.size), "finiteCount": int(np.count_nonzero(finite)),
        "thresholdGray": float(threshold), "metalLevelMedian": metal,
        "darkLevelMedian": dark,
    }


def _candidate_side(
    gray: np.ndarray,
    center: tuple[float, float],
    outer_radius: float,
    radii: np.ndarray,
    seed_deg: float,
    polarity: str,
    bilinear_sample: Callable[[np.ndarray, np.ndarray, np.ndarray], np.ndarray],
    parabolic_peak: Callable[[list[float], int], float],
    refinement_config: dict[str, Any],
    pixel_scale: float,
) -> dict[str, Any]:
    points, contrasts, gradients, observations = _side_points(
        gray, center, radii, seed_deg, polarity, bilinear_sample, parabolic_peak,
        refinement_config,
    )
    profile = _profile_evidence(observations, radii)
    decision = _select_consensus_line(
        points, minimum=int(refinement_config["min_side_points"]), center=center,
        outer_radius=outer_radius, coarse_angle_deg=seed_deg,
        maximum_delta_deg=float(refinement_config["max_intersection_coarse_delta_deg"]),
        config=refinement_config, pixel_scale=pixel_scale,
    )
    base = {
        "seedDeg": float(seed_deg), "polarity": polarity,
        "searchWindowDeg": {
            "startDeg": wrap_360_deg(seed_deg - float(refinement_config["tangential_search_margin_deg"])),
            "endDeg": wrap_360_deg(seed_deg + float(refinement_config["tangential_search_margin_deg"])),
            "halfWidthDeg": float(refinement_config["tangential_search_margin_deg"]),
        },
        "detectedPointCount": len(points), "profileEvidence": profile,
        "edgeContrastMedian": None if not contrasts else float(np.median(contrasts)),
        "edgeGradientMedianPerPx": None if not gradients else float(np.median(gradients)),
        "searchStatus": str(decision["status"]), "failedCheck": decision["failedCheck"],
    }
    if decision["status"] != "accepted":
        if len(points) < int(refinement_config["min_side_points"]):
            rejection_stage = "EDGE_SAMPLING"
        elif decision["failedCheck"] == "intersection":
            rejection_stage = "OUTER_CIRCLE_INTERSECTION"
        else:
            rejection_stage = "LINE_CONSENSUS"
        return {
            **base, "rejectionStage": rejection_stage,
            "fitToSeedDeltaDeg": None, "intersectionAngleDeg": None,
            "line": None, "lineSegment": None, "points": [],
        }
    mask = np.asarray(decision["inlierMask"], dtype=bool)
    kept = np.asarray(points, dtype=float)[mask]
    line = decision["line"]
    direction = np.asarray((-float(line[1]), float(line[0])), dtype=float)
    projected = kept @ direction
    first, last = kept[int(np.argmin(projected))], kept[int(np.argmax(projected))]
    return {
        **base, "rejectionStage": None,
        "supportPointCount": int(len(kept)),
        "sampledPointCount": int(len(radii)),
        "lineInlierRatio": float(decision["inlierRatio"]),
        "lineLongitudinalCoverage": float(decision["longitudinalCoverage"]),
        "lineResidualPx": {"p95": float(decision["residualP95Px"])},
        "line": {"a": float(line[0]), "b": float(line[1]), "c": float(line[2])},
        "lineSegment": {
            "start": {"x": float(first[0]), "y": float(first[1])},
            "end": {"x": float(last[0]), "y": float(last[1])},
        },
        "points": [[float(value) for value in point] for point in kept],
        "intersectionAngleDeg": float(decision["intersectionAngleDeg"]),
        "fitToSeedDeltaDeg": float(
            (float(decision["intersectionAngleDeg"]) - float(seed_deg) + 180.0) % 360.0 - 180.0
        ),
        "intersection": {
            "x": float(decision["intersection"][0]),
            "y": float(decision["intersection"][1]),
        },
    }


def _side_line_segment(side: dict[str, Any]) -> dict[str, Any] | None:
    line, points = side.get("line"), side.get("points")
    if not isinstance(line, dict) or not isinstance(points, list) or len(points) < 2:
        return None
    try:
        array = np.asarray(points, dtype=float)
        direction = np.asarray((-float(line["b"]), float(line["a"])), dtype=float)
    except (KeyError, TypeError, ValueError):
        return None
    if array.ndim != 2 or array.shape[1] != 2 or not np.isfinite(array).all():
        return None
    projected = array @ direction
    first, last = array[int(np.argmin(projected))], array[int(np.argmax(projected))]
    return {
        "start": {"x": float(first[0]), "y": float(first[1])},
        "end": {"x": float(last[0]), "y": float(last[1])},
    }


def _cluster_side_searches(
    candidates: list[dict[str, Any]], polarity: str, merge_deg: float,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Preserve the v1 greedy representative behavior and expose every merge."""
    accepted = [item for item in candidates if item.get("intersectionAngleDeg") is not None]
    accepted.sort(key=lambda item: (
        float(item["intersectionAngleDeg"]), float(item["seedDeg"]),
        str(item.get("searchDomainId") or ""),
    ))
    working: list[dict[str, Any]] = []
    for side in candidates:
        side["mergeClusterId"] = None
        side["mergeDisposition"] = "NOT_CLUSTERED_FIT_REJECTED"
    for side in accepted:
        selected = next((
            cluster for cluster in working
            if circular_distance_deg(
                float(side["intersectionAngleDeg"]),
                float(cluster["representative"]["intersectionAngleDeg"]),
            ) <= merge_deg
        ), None)
        if selected is None:
            selected = {"representative": side, "members": []}
            working.append(selected)
        selected["members"].append(side)
    clusters: list[dict[str, Any]] = []
    representatives: list[dict[str, Any]] = []
    for index, cluster in enumerate(working, start=1):
        identifier = f"{polarity}-wall-cluster-{index:03d}"
        representative = cluster["representative"]
        members = cluster["members"]
        representative["mergeClusterId"] = identifier
        representative["mergeDisposition"] = "REPRESENTATIVE"
        for member in members:
            member["mergeClusterId"] = identifier
            if member is not representative:
                member["mergeDisposition"] = "SUPPRESSED_MEMBER"
        reference_angle = float(representative["intersectionAngleDeg"])
        deltas = [
            (float(item["intersectionAngleDeg"]) - reference_angle + 180.0) % 360.0 - 180.0
            for item in members
        ]
        clusters.append({
            "clusterId": identifier,
            "polarity": polarity,
            "representativeSearchCandidateId": representative["searchCandidateId"],
            "representativeAngleDeg": reference_angle,
            "memberSearchCandidateIds": [item["searchCandidateId"] for item in members],
            "suppressedSearchCandidateIds": [
                item["searchCandidateId"] for item in members if item is not representative
            ],
            "memberSeedDeg": [float(item["seedDeg"]) for item in members],
            "memberFittedAngleDeg": [float(item["intersectionAngleDeg"]) for item in members],
            "memberDomainIds": list(dict.fromkeys(
                str(item.get("searchDomainId") or "legacy-local-interval") for item in members
            )),
            "memberDirections": list(dict.fromkeys(
                str(item.get("searchDirection") or "LEGACY") for item in members
            )),
            "fittedAngleSpreadDeg": float(max(deltas) - min(deltas)),
            "memberCount": len(members),
            "mergeThresholdDeg": float(merge_deg),
            "selectionRule": "lowest_fitted_angle_then_seed_v1_compatible",
        })
        representatives.append(representative)
    return representatives, clusters


def _search_summary(
    candidates: list[dict[str, Any]], clusters: list[dict[str, Any]], polarity: str,
) -> dict[str, Any]:
    selected = [item for item in candidates if item["polarity"] == polarity]
    accepted = [item for item in selected if item["searchStatus"] == "accepted"]
    failures: dict[str, int] = {}
    for item in selected:
        stage = str(item.get("rejectionStage") or "ACCEPTED")
        failures[stage] = failures.get(stage, 0) + 1
    matching_clusters = [item for item in clusters if item["polarity"] == polarity]
    if not accepted:
        classification = "NO_EDGE_SIGNAL"
    elif len(matching_clusters) == 1:
        classification = "SINGLE_EDGE_ATTRACTOR"
    else:
        classification = "MULTIPLE_EDGE_CLUSTERS"
    return {
        "polarity": polarity,
        "seedCount": len(selected),
        "acceptedFitCount": len(accepted),
        "rejectionStageCounts": failures,
        "mergeClusterCount": len(matching_clusters),
        "mergeClusterSizes": [int(item["memberCount"]) for item in matching_clusters],
        "classification": classification,
    }


def diagnose_local_second_wall(
    gray: np.ndarray,
    center: tuple[float, float],
    outer_radius: float,
    coarse_candidate: dict[str, Any],
    initial_refinement: dict[str, Any],
    bilinear_sample: Callable[[np.ndarray, np.ndarray, np.ndarray], np.ndarray],
    parabolic_peak: Callable[[list[float], int], float],
    refinement_config: dict[str, Any] | None,
    source_consistency_config: dict[str, Any] | None,
    config: dict[str, Any] | None,
    *,
    pixel_scale: float = 1.0,
) -> dict[str, Any]:
    """Enumerate local alternatives and return a non-authoritative diagnostic."""
    merged = merged_local_second_wall_config(config)
    if not merged["enabled"]:
        return _base(merged, "DISABLED")
    result = _base(merged, "NOT_EVALUATED")
    result["coarseCandidateId"] = coarse_candidate.get("candidateId")
    if initial_refinement.get("status") != "accepted":
        result["failureStage"] = "candidate_anchor"
        result["errorCode"] = "CANDIDATE_MISSING"
        result["failedChecks"] = ["initial_refinement_not_accepted"]
        return result
    try:
        local_start = float(coarse_candidate["startDeg"]) % 360.0
        local_end = float(coarse_candidate["endDeg"]) % 360.0
        depth = float(coarse_candidate["radialDepthPx"])
    except (KeyError, TypeError, ValueError):
        result["failureStage"] = "candidate_anchor"
        result["errorCode"] = "CANDIDATE_MISSING"
        result["failedChecks"] = ["invalid_coarse_candidate"]
        return result
    local_span = (local_end - local_start) % 360.0
    if not 0.0 < local_span < 180.0 or not math.isfinite(depth) or depth <= 0.0:
        result["failureStage"] = "candidate_anchor"
        result["errorCode"] = "CANDIDATE_MISSING"
        result["failedChecks"] = ["invalid_local_interval"]
        return result
    result["localInterval"] = {
        "startDeg": local_start, "endDeg": local_end, "spanDeg": local_span,
        "source": "coarse_raw_dark_candidate",
        "boundaryAuthoritative": False,
        "coarseCandidateId": coarse_candidate.get("candidateId"),
        "initialRefinedEndpointProfileDeg": initial_refinement.get("openingEndpointProfileDeg"),
    }
    refinement = merged_groove_refinement_config(refinement_config)
    minimum_inset = float(refinement["radial_inset_min_px"]) * pixel_scale
    maximum_inset = min(float(refinement["radial_inset_max_px"]) * pixel_scale, 0.80 * depth)
    if maximum_inset <= minimum_inset:
        result["failureStage"] = "local_second_wall_search"
        result["errorCode"] = "LOCAL_SECOND_WALL_NOT_FOUND"
        result["failedChecks"] = ["insufficient_radial_depth"]
        return result
    radii = outer_radius - np.linspace(
        minimum_inset, maximum_inset, int(refinement["radial_sample_count"]), dtype=float,
    )
    radii = radii[radii > 1.0]
    if len(radii) < int(refinement["min_side_points"]):
        result["failureStage"] = "local_second_wall_search"
        result["errorCode"] = "LOCAL_SECOND_WALL_NOT_FOUND"
        result["failedChecks"] = ["insufficient_radial_support"]
        return result
    anchors: list[tuple[str, dict[str, Any], str]] = []
    for name, polarity in (("startSide", "rising"), ("endSide", "falling")):
        side = initial_refinement.get(name)
        if isinstance(side, dict) and isinstance(side.get("line"), dict):
            anchors.append((name, side, polarity))
    result["anchorSides"] = [name for name, _, _ in anchors]
    endpoint_angles = initial_refinement.get("openingEndpointProfileDeg")
    for name, side, required_polarity in anchors:
        endpoint_index = 0 if name == "startSide" else 1
        endpoint_angle = None
        if isinstance(endpoint_angles, list) and len(endpoint_angles) > endpoint_index:
            try:
                endpoint_angle = float(endpoint_angles[endpoint_index]) % 360.0
            except (TypeError, ValueError):
                endpoint_angle = None
        result["anchorEvidence"].append({
            "anchorSide": name,
            "endpointAngleDeg": endpoint_angle,
            "requiredOppositePolarity": required_polarity,
            "line": side.get("line"),
            "lineSegment": _side_line_segment(side),
            "supportPointCount": side.get("supportPointCount"),
            "edgeContrastMedian": side.get("edgeContrastMedian"),
            "edgeGradientMedianPerPx": side.get("edgeGradientMedianPerPx"),
            "profileEvidence": side.get("profileEvidence"),
        })
    if len(anchors) != 2:
        result["failureStage"] = "candidate_anchor"
        result["errorCode"] = "CANDIDATE_MISSING"
        result["failedChecks"] = ["anchor_side_missing"]
        return result
    anchor_angles = {
        str(item["anchorSide"]): float(item["endpointAngleDeg"])
        for item in result["anchorEvidence"] if item.get("endpointAngleDeg") is not None
    }
    if set(anchor_angles) != {"startSide", "endSide"}:
        result["failureStage"] = "candidate_anchor"
        result["errorCode"] = "CANDIDATE_MISSING"
        result["failedChecks"] = ["anchor_angle_missing"]
        return result
    domains = _build_search_domains(local_start, local_span, anchor_angles, merged)
    total_jobs = sum(int(item["seedCount"]) * 2 for item in domains)
    result["searchDomains"] = domains
    result["searchLimits"] = {
        "maxSeedsPerDomain": int(merged["max_seeds_per_domain"]),
        "maxTotalSearchJobs": int(merged["max_total_search_jobs"]),
        "maxWallCandidates": int(merged["max_wall_candidates"]),
        "actualTotalSearchJobs": total_jobs,
    }
    if total_jobs > int(merged["max_total_search_jobs"]):
        result["failureStage"] = "local_second_wall_search"
        result["errorCode"] = "LOCAL_SECOND_WALL_NOT_FOUND"
        result["failedChecks"] = ["search_job_limit_exceeded"]
        return result
    all_searches: list[dict[str, Any]] = []
    polarity_counters = {"falling": 0, "rising": 0}
    for domain in domains:
        for polarity in ("falling", "rising"):
            for seed_index, seed in enumerate(domain["seedAnglesDeg"], start=1):
                side = _candidate_side(
                    np.asarray(gray), center, outer_radius, radii, float(seed), polarity,
                    bilinear_sample, parabolic_peak, refinement, pixel_scale,
                )
                polarity_counters[polarity] += 1
                side["searchCandidateId"] = (
                    f"{polarity}-wall-search-{polarity_counters[polarity]:03d}"
                )
                side["searchDomainId"] = domain["domainId"]
                side["searchDirection"] = domain["direction"]
                side["searchAnchorSide"] = domain["anchorSide"]
                side["seedIndexWithinDomain"] = seed_index
                side["domainSpanDeg"] = float(domain["spanDeg"])
                side["failedChecks"] = [] if side["searchStatus"] == "accepted" else [
                    str(side.get("failedCheck") or "side_search_not_accepted")
                ]
                all_searches.append(side)
    searched: dict[str, list[dict[str, Any]]] = {}
    side_clusters: list[dict[str, Any]] = []
    for polarity in ("falling", "rising"):
        raw_sides = [item for item in all_searches if item["polarity"] == polarity]
        representatives, clusters = _cluster_side_searches(
            raw_sides, polarity, float(merged["candidate_merge_deg"]),
        )
        searched[polarity] = representatives
        side_clusters.extend(clusters)
    for side in all_searches:
        if "failedChecks" not in side:
            side["failedChecks"] = [] if side["searchStatus"] == "accepted" else [
                str(side.get("failedCheck") or "side_search_not_accepted")
            ]
    result["sideSearchCandidates"] = sorted(
        all_searches,
        key=lambda item: (
            str(item["searchDomainId"]), str(item["polarity"]),
            int(item["seedIndexWithinDomain"]),
        ),
    )
    result["sideSearchMergeClusters"] = sorted(
        side_clusters, key=lambda item: (str(item["polarity"]), str(item["clusterId"])),
    )
    result["searchOutcomeSummary"] = {
        polarity: _search_summary(all_searches, side_clusters, polarity)
        for polarity in sorted({str(item["polarity"]) for item in all_searches})
    }
    result["searchLimits"]["actualWallCandidates"] = len(side_clusters)
    if len(side_clusters) > int(merged["max_wall_candidates"]):
        result["failureStage"] = "physical_wall_clustering"
        result["errorCode"] = "MULTIPLE_LOCAL_OPENINGS"
        result["failedChecks"] = ["wall_candidate_limit_exceeded"]
        return result

    initial_source = assess_sidewall_source_consistency(
        initial_refinement, source_consistency_config,
    )
    result["initialPairEvidence"] = {
        "endpointProfileDeg": [anchor_angles["startSide"], anchor_angles["endSide"]],
        "sourceConsistencyStatus": initial_source.get("status"),
        "sourceConsistencyFailedChecks": initial_source.get("failedChecks") or [],
        "treatedAsConfirmedWalls": False,
    }

    def circle_residual(side: dict[str, Any]) -> float:
        intersection = side.get("intersection")
        if not isinstance(intersection, dict):
            return math.inf
        try:
            return abs(math.hypot(
                float(intersection["x"]) - center[0],
                float(intersection["y"]) - center[1],
            ) - outer_radius)
        except (KeyError, TypeError, ValueError):
            return math.inf

    def compact_wall(side: dict[str, Any]) -> dict[str, Any]:
        return {
            "clusterId": side.get("mergeClusterId"),
            "searchCandidateId": side.get("searchCandidateId"),
            "polarity": side.get("polarity"),
            "angleDeg": side.get("intersectionAngleDeg"),
            "searchDomainId": side.get("searchDomainId"),
            "searchDirection": side.get("searchDirection"),
            "line": side.get("line"),
            "lineSegment": side.get("lineSegment"),
            "intersection": side.get("intersection"),
            "points": side.get("points") or [],
        }

    hypotheses: list[dict[str, Any]] = []
    for start_side in searched.get("falling", []):
        for end_side in searched.get("rising", []):
            start_angle = float(start_side["intersectionAngleDeg"])
            end_angle = float(end_side["intersectionAngleDeg"])
            opening_span = (end_angle - start_angle) % 360.0
            if circular_distance_deg(start_angle, end_angle) <= float(merged["candidate_merge_deg"]):
                continue
            pair_id = _canonical_pair_id(
                str(start_side["mergeClusterId"]), str(end_side["mergeClusterId"]),
            )
            parallel = _line_parallel_difference(start_side, end_side)
            start_coverage, end_coverage = _radial_coverage(start_side), _radial_coverage(end_side)
            if opening_span <= float(merged["max_wall_separation_deg"]):
                dark_fraction, dark_evidence = _opening_dark_fraction(
                    np.asarray(gray), center, outer_radius, start_angle, opening_span, depth,
                    start_side, end_side, bilinear_sample, refinement, merged, pixel_scale,
                )
            else:
                dark_fraction, dark_evidence = None, {
                    "sampleCount": 0, "finiteCount": 0, "thresholdGray": None,
                    "skipped": "wall_separation_above_physical_maximum",
                }
            constructed = {
                "status": "accepted", "startSide": start_side, "endSide": end_side,
                "openingEndpointProfileDeg": [start_angle, end_angle],
            }
            source = assess_sidewall_source_consistency(constructed, source_consistency_config)
            endpoint_residuals = [circle_residual(start_side), circle_residual(end_side)]
            endpoint_residual_gate = float(merged["max_endpoint_circle_residual_px"]) * pixel_scale
            initial_endpoints = [anchor_angles["startSide"], anchor_angles["endSide"]]
            reuses_initial = (
                (
                    circular_distance_deg(start_angle, initial_endpoints[0]) <= float(merged["candidate_merge_deg"])
                    and circular_distance_deg(end_angle, initial_endpoints[1]) <= float(merged["candidate_merge_deg"])
                ) or (
                    circular_distance_deg(start_angle, initial_endpoints[1]) <= float(merged["candidate_merge_deg"])
                    and circular_distance_deg(end_angle, initial_endpoints[0]) <= float(merged["candidate_merge_deg"])
                )
            )
            rejected_initial_reuse = reuses_initial and initial_source.get("status") != "accepted"
            checks = [
                {"layer": "candidate_origin", "hardGate": True,
                 "checkId": "reuses_rejected_initial_pair", "passed": not rejected_initial_reuse,
                 "value": reuses_initial,
                 "threshold": "initial source-consistency pair must not be reused after rejection"},
                {"layer": "local_geometry", "hardGate": True,
                 "checkId": "minimum_wall_separation", "passed": opening_span >= float(merged["min_wall_separation_deg"]),
                 "value": opening_span, "threshold": float(merged["min_wall_separation_deg"])},
                {"layer": "local_geometry", "hardGate": True,
                 "checkId": "maximum_wall_separation", "passed": opening_span <= float(merged["max_wall_separation_deg"]),
                 "value": opening_span, "threshold": float(merged["max_wall_separation_deg"])},
                {"layer": "local_geometry", "hardGate": True,
                 "checkId": "wall_parallelism", "passed": parallel is not None and parallel <= float(merged["max_parallel_difference_deg"]),
                 "value": parallel, "threshold": float(merged["max_parallel_difference_deg"])},
                {"layer": "local_geometry", "hardGate": True,
                 "checkId": "radial_coverage", "passed": start_coverage is not None and end_coverage is not None and min(start_coverage, end_coverage) >= float(merged["min_radial_coverage"]),
                 "value": [start_coverage, end_coverage], "threshold": float(merged["min_radial_coverage"])},
                {"layer": "local_geometry", "hardGate": True,
                 "checkId": "radial_coverage_consistency", "passed": start_coverage is not None and end_coverage is not None and abs(start_coverage - end_coverage) <= float(merged["max_radial_coverage_difference"]),
                 "value": None if start_coverage is None or end_coverage is None else abs(start_coverage - end_coverage),
                 "threshold": float(merged["max_radial_coverage_difference"])},
                {"layer": "mouth_endpoint", "hardGate": True,
                 "checkId": "outer_circle_endpoint_residual", "passed": max(endpoint_residuals) <= endpoint_residual_gate,
                 "value": endpoint_residuals, "threshold": endpoint_residual_gate},
                {"layer": "opening_structure", "hardGate": True,
                 "checkId": "local_dark_opening_continuity", "passed": dark_fraction is not None and dark_fraction >= float(merged["min_opening_dark_fraction"]),
                 "value": dark_fraction, "threshold": float(merged["min_opening_dark_fraction"])},
                {"layer": "sidewall_source", "hardGate": True,
                 "checkId": "sidewall_source_consistency", "passed": source.get("status") == "accepted",
                 "value": source.get("metrics"), "threshold": source.get("thresholdVersion")},
            ]
            failed = [str(item["checkId"]) for item in checks if not item["passed"]]
            failed.extend(f"source_consistency:{value}" for value in source.get("failedChecks") or [])
            numeric_margins = [
                float(merged["max_wall_separation_deg"]) - opening_span,
                float(merged["max_parallel_difference_deg"]) - (parallel if parallel is not None else 180.0),
                (dark_fraction if dark_fraction is not None else -1.0) - float(merged["min_opening_dark_fraction"]),
            ]
            hypotheses.append({
                "hypothesisId": None, "rawHypothesisId": "",
                "canonicalPairId": pair_id,
                "wallClusterIds": [
                    str(start_side["mergeClusterId"]), str(end_side["mergeClusterId"]),
                ],
                "candidateSeedDeg": float(end_side["seedDeg"]),
                "candidateSearchId": end_side["searchCandidateId"],
                "candidateMergeClusterId": end_side["mergeClusterId"],
                "candidateAngleDeg": end_angle,
                "openingEndpointProfileDeg": [start_angle, end_angle],
                "openingWidthDeg": opening_span,
                "coarseIntervalRelation": {
                    "fallingInside": _inside_interval(start_angle, local_start, local_span, 0.0),
                    "risingInside": _inside_interval(end_angle, local_start, local_span, 0.0),
                    "reusesInitialEndpoints": reuses_initial,
                },
                "metrics": {
                    "parallelDifferenceDeg": parallel,
                    "radialCoverage": [start_coverage, end_coverage],
                    "openingDarkFraction": dark_fraction,
                    "openingDarkEvidence": dark_evidence,
                    "endpointCircleResidualPx": endpoint_residuals,
                    "sourceConsistency": source,
                },
                "scoreComponents": {
                    "widthUpperMarginDeg": numeric_margins[0],
                    "parallelMarginDeg": numeric_margins[1],
                    "darkContinuityMargin": numeric_margins[2],
                },
                "checks": checks,
                "failedChecks": list(dict.fromkeys(failed)),
                "passed": not failed,
                "score": float(min(numeric_margins)),
                "candidateSide": end_side,
                "wallCandidates": [compact_wall(start_side), compact_wall(end_side)],
            })
    hypotheses.sort(key=lambda item: (
        not bool(item["passed"]), -float(item["score"]), str(item["canonicalPairId"]),
    ))
    for index, hypothesis in enumerate(hypotheses, start=1):
        hypothesis["rawHypothesisId"] = f"raw-local-wall-hypothesis-{index:03d}"
        hypothesis["hypothesisId"] = f"local-wall-pair-{index:03d}"
        hypothesis["hypothesisMergeClusterId"] = f"canonical-pair-cluster-{index:03d}"
        hypothesis["mergeDisposition"] = "CANONICAL_SINGLETON"
    hypothesis_clusters: list[dict[str, Any]] = []
    for index, hypothesis in enumerate(hypotheses, start=1):
        hypothesis_clusters.append({
            "clusterId": f"canonical-pair-cluster-{index:03d}",
            "canonicalPairId": hypothesis["canonicalPairId"],
            "representativeRawHypothesisId": hypothesis["rawHypothesisId"],
            "memberRawHypothesisIds": [hypothesis["rawHypothesisId"]],
            "suppressedRawHypothesisIds": [], "memberCount": 1,
            "mergeThresholdDeg": float(merged["candidate_merge_deg"]),
            "selectionRule": "unordered_wall_cluster_pair_no_sequence_merge",
        })
    result["rawHypotheses"] = hypotheses
    result["hypothesisMergeClusters"] = hypothesis_clusters
    result["hypotheses"] = hypotheses
    result["canonicalWallPairs"] = hypotheses
    passed = [item for item in hypotheses if item["passed"]]
    if len(passed) == 1:
        result["status"] = "UNIQUE_DIAGNOSTIC"
        result["experimentalCandidate"] = {
            "hypothesisId": passed[0]["hypothesisId"],
            "canonicalPairId": passed[0]["canonicalPairId"],
            "wallClusterIds": passed[0]["wallClusterIds"],
            "wallCandidates": passed[0]["wallCandidates"],
            "openingEndpointProfileDeg": passed[0]["openingEndpointProfileDeg"],
            "openingWidthDeg": passed[0]["openingWidthDeg"],
            "authoritative": False,
            "posePromotionAllowed": False,
        }
    elif len(passed) > 1:
        result["status"] = "MULTIPLE_LOCAL_OPENINGS"
        result["failureStage"] = "local_opening_uniqueness"
        result["errorCode"] = "MULTIPLE_LOCAL_OPENINGS"
    else:
        source_only_rejected = any(
            item["failedChecks"]
            and all(
                value == "sidewall_source_consistency"
                or value == "reuses_rejected_initial_pair"
                or str(value).startswith("source_consistency:")
                for value in item["failedChecks"]
            )
            for item in hypotheses
        )
        observed_clusters = [
            str(item["clusterId"])
            for item in result["sideSearchMergeClusters"]
            if isinstance(item, dict) and item.get("clusterId")
        ]
        partially_observed = bool(observed_clusters) and (
            len(observed_clusters) == 1 or source_only_rejected
        )
        if partially_observed:
            result["status"] = "PARTIALLY_OBSERVED"
            result["failureStage"] = "single_wall_observability"
            result["errorCode"] = "PARTIAL_GROOVE_OBSERVATION"
            result["partialObservation"] = {
                "observedWallClusterIds": observed_clusters,
                "observedWallCandidateCount": len(observed_clusters),
                "completeSameSourceOpeningObserved": False,
                "trueGrooveWallIdentityConfirmed": False,
                "humanConfirmationAppliedAtRuntime": False,
                "oppositeWallObservability": "UNCONFIRMED",
                "reason": (
                    "SINGLE_WALL_CLUSTER"
                    if len(observed_clusters) == 1
                    else "NO_SAME_SOURCE_WALL_PAIR"
                ),
            }
        else:
            result["status"] = "LOCAL_SECOND_WALL_NOT_FOUND"
            result["failureStage"] = "local_second_wall_search"
            result["errorCode"] = "LOCAL_SECOND_WALL_NOT_FOUND"
    result["passedHypothesisCount"] = len(passed)
    if len(passed) == 1:
        result["failedChecks"] = []
    elif len(passed) > 1:
        result["failedChecks"] = ["multiple_same_opening_second_walls"]
    else:
        result["failedChecks"] = [
            (
                "no_complete_same_source_opening"
                if result["status"] == "PARTIALLY_OBSERVED"
                else "no_unique_same_opening_second_wall"
            ) if hypotheses else "no_second_wall_hypothesis"
        ]
    return result
