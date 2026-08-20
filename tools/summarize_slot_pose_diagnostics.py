#!/usr/bin/env python3
"""Summarize path-safe multi-frame slot-pose review diagnostics."""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from collections import Counter
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.dataset_common import write_json


def circular_delta_deg(value: float, reference: float) -> float:
    return (float(value) - float(reference) + 180.0) % 360.0 - 180.0


def circular_mean_deg(values: list[float]) -> float:
    if not values:
        raise ValueError("circular mean requires at least one value")
    radians = [math.radians(value) for value in values]
    return math.degrees(math.atan2(sum(math.sin(value) for value in radians), sum(math.cos(value) for value in radians))) % 360.0


def percentile(values: list[float], quantile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(float(value) for value in values)
    position = (len(ordered) - 1) * quantile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def _cluster_observations(observations: list[dict[str, Any]], threshold_deg: float) -> list[list[dict[str, Any]]]:
    if not observations:
        return []
    ordered = sorted(observations, key=lambda item: (float(item["angleDeg"]), item["imageId"], item["candidateId"]))
    gaps = [
        (float(ordered[(index + 1) % len(ordered)]["angleDeg"]) - float(ordered[index]["angleDeg"])) % 360.0
        for index in range(len(ordered))
    ]
    start = (max(range(len(gaps)), key=lambda index: gaps[index]) + 1) % len(ordered)
    rotated = ordered[start:] + ordered[:start]
    clusters: list[list[dict[str, Any]]] = [[rotated[0]]]
    for item in rotated[1:]:
        previous = clusters[-1][-1]
        if abs(circular_delta_deg(float(item["angleDeg"]), float(previous["angleDeg"]))) > threshold_deg:
            clusters.append([])
        clusters[-1].append(item)
    return clusters


def candidate_clusters(records: list[dict[str, Any]], threshold_deg: float) -> list[dict[str, Any]]:
    observations = [
        {
            "imageId": record["imageId"],
            "candidateId": candidate["candidateId"],
            "angleDeg": float(candidate["centerDeg"]),
            "halfWidthDeg": float(candidate["halfWidthDeg"]),
            "prominence": float(candidate["prominence"]),
            "rank": int(candidate["rank"]),
        }
        for record in records
        for candidate in record.get("candidates") or []
    ]
    output: list[dict[str, Any]] = []
    frame_count = len(records)
    raw_clusters = _cluster_observations(observations, threshold_deg)
    summaries: list[tuple[float, dict[str, Any]]] = []
    for cluster in raw_clusters:
        angles = [float(item["angleDeg"]) for item in cluster]
        mean = circular_mean_deg(angles)
        deltas = [circular_delta_deg(angle, mean) for angle in angles]
        prominence = [float(item["prominence"]) for item in cluster]
        half_width = [float(item["halfWidthDeg"]) for item in cluster]
        frame_support = len({str(item["imageId"]) for item in cluster})
        radians = [math.radians(angle) for angle in angles]
        resultant = math.hypot(sum(math.cos(value) for value in radians), sum(math.sin(value) for value in radians)) / len(radians)
        circular_std = math.degrees(math.sqrt(max(0.0, -2.0 * math.log(max(resultant, 1e-12)))))
        prominence_mean = statistics.fmean(prominence)
        summary = {
            "clusterId": None,
            "frameSupport": frame_support,
            "frameSupportRate": frame_support / frame_count if frame_count else 0.0,
            "observationCount": len(cluster),
            "circularMeanDeg": mean,
            "circularStdDeg": circular_std,
            "circularRangeDeg": max(deltas) - min(deltas),
            "absoluteDeviationP95Deg": percentile([abs(value) for value in deltas], 0.95),
            "halfWidthMeanDeg": statistics.fmean(half_width),
            "halfWidthStdDeg": statistics.pstdev(half_width) if len(half_width) > 1 else 0.0,
            "prominenceMean": prominence_mean,
            "prominenceP50": percentile(prominence, 0.5),
            "prominenceStd": statistics.pstdev(prominence) if len(prominence) > 1 else 0.0,
            "prominenceCoefficientOfVariation": (
                statistics.pstdev(prominence) / prominence_mean if len(prominence) > 1 and prominence_mean else 0.0
            ),
            "rankCounts": dict(sorted(Counter(str(item["rank"]) for item in cluster).items())),
            "stableDiagnosticFeature": frame_support / frame_count >= 0.8 if frame_count else False,
            "authoritativeRole": False,
        }
        summaries.append((mean, summary))
    for index, (_, summary) in enumerate(sorted(summaries, key=lambda item: item[0]), start=1):
        summary["clusterId"] = f"angle-cluster-{index:03d}"
        output.append(summary)
    return output


def candidate_id_tracks(records: list[dict[str, Any]], threshold_deg: float) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        for candidate in record.get("candidates") or []:
            grouped.setdefault(str(candidate["candidateId"]), []).append({
                "imageId": record["imageId"],
                "candidateId": candidate["candidateId"],
                "angleDeg": float(candidate["centerDeg"]),
                "halfWidthDeg": float(candidate["halfWidthDeg"]),
                "prominence": float(candidate["prominence"]),
                "rank": int(candidate["rank"]),
            })
    frame_count = len(records)
    tracks: list[dict[str, Any]] = []
    for candidate_id, observations in sorted(grouped.items()):
        modes = []
        for mode in _cluster_observations(observations, threshold_deg):
            angles = [float(item["angleDeg"]) for item in mode]
            mean = circular_mean_deg(angles)
            deltas = [circular_delta_deg(angle, mean) for angle in angles]
            modes.append({
                "observationCount": len(mode),
                "circularMeanDeg": mean,
                "circularRangeDeg": max(deltas) - min(deltas),
            })
        modes.sort(key=lambda item: (-int(item["observationCount"]), float(item["circularMeanDeg"])))
        prominence = [float(item["prominence"]) for item in observations]
        half_width = [float(item["halfWidthDeg"]) for item in observations]
        frame_support = len({str(item["imageId"]) for item in observations})
        tracks.append({
            "candidateId": candidate_id,
            "frameSupport": frame_support,
            "frameSupportRate": frame_support / frame_count if frame_count else 0.0,
            "angleModeCount": len(modes),
            "angleModes": modes,
            "imageFrameStable": frame_support / frame_count >= 0.8 and len(modes) == 1 if frame_count else False,
            "halfWidthMeanDeg": statistics.fmean(half_width),
            "halfWidthStdDeg": statistics.pstdev(half_width) if len(half_width) > 1 else 0.0,
            "prominenceMean": statistics.fmean(prominence),
            "prominenceStd": statistics.pstdev(prominence) if len(prominence) > 1 else 0.0,
            "rankCounts": dict(sorted(Counter(str(item["rank"]) for item in observations).items())),
            "authoritativeRole": False,
        })
    return tracks


def summarize_run(label: str, review: dict[str, Any], threshold_deg: float) -> dict[str, Any]:
    records = list(review.get("records") or [])
    total = len(records)
    error_counts = Counter(record.get("result", {}).get("errorCode") or "NONE" for record in records)
    candidate_counts = Counter(len(record.get("candidates") or []) for record in records)
    groove_candidate_counts = Counter(len(record.get("grooveCandidates") or []) for record in records)
    groove_status_counts = Counter(
        (record.get("grooveRecognition") or {}).get("status") or "not_available" for record in records
    )
    groove_rejections = Counter(
        reason
        for record in records
        for assessment in (record.get("grooveRecognition") or {}).get("assessments") or []
        for reason in assessment.get("rejectionReasons") or []
    )
    rejected_candidate_counts = [
        sum(
            not bool(assessment.get("accepted"))
            for assessment in (record.get("grooveRecognition") or {}).get("assessments") or []
        )
        for record in records
    ]
    single_poses = [record.get("singleGroovePose") or {} for record in records]
    single_status_counts = Counter(pose.get("status") or "not_available" for pose in single_poses)
    single_geometry_count = sum(pose.get("geometryValid") is True for pose in single_poses)
    single_measurements = [
        pose.get("imageMeasurement") or {} for pose in single_poses
        if isinstance((pose.get("imageMeasurement") or {}).get("azimuthDeg"), (int, float))
    ]
    single_azimuths = [float(item["azimuthDeg"]) for item in single_measurements]
    single_quadrants = Counter(str(item.get("quadrant") or "unknown") for item in single_measurements)
    datum_blocked_count = sum(
        record.get("result", {}).get("errorCode") == "DATUM_DEFINITION_UNCONFIRMED"
        for record in records
    )
    refinements = [record.get("grooveRefinement") or {} for record in records]
    refinement_status_counts = Counter(item.get("status") or "not_available" for item in refinements)
    refinement_schema_counts = Counter(item.get("schemaVersion") or "unknown" for item in refinements)
    refinement_threshold_counts = Counter(item.get("thresholdVersion") or "unknown" for item in refinements)
    refinement_failures = Counter(
        reason for item in refinements for reason in item.get("failedChecks") or []
    )
    refinement_elapsed = [
        float(item["elapsedMs"]) for item in refinements
        if isinstance(item.get("elapsedMs"), (int, float))
    ]
    sidewalls = [
        side for refinement in refinements for side_name in ("startSide", "endSide")
        if isinstance((side := refinement.get(side_name)), dict)
    ]
    wall_family_strategy_counts = Counter(
        str(side.get("wallFamilyStrategyVersion") or side.get("lineFitStrategy") or "unknown")
        for side in sidewalls
    )
    wall_family_status_counts = Counter(
        str(side.get("wallFamilyStatus") or "not_available") for side in sidewalls
    )
    def side_values(key: str, nested: str | None = None) -> list[float]:
        output: list[float] = []
        for side in sidewalls:
            value = (side.get(nested) or {}).get(key) if nested else side.get(key)
            if isinstance(value, (int, float)):
                output.append(float(value))
        return output

    def distribution(values: list[float]) -> dict[str, Any]:
        return {
            "n": len(values), "min": min(values) if values else None,
            "p50": percentile(values, 0.5), "p95": percentile(values, 0.95),
            "max": max(values) if values else None,
        }
    datum_measurements = [pose.get("datumMeasurement") or {} for pose in single_poses]
    y_down_angles = [
        float(item["measuredFromPositiveYClockwiseDeg"])
        for item in datum_measurements
        if isinstance(item.get("measuredFromPositiveYClockwiseDeg"), (int, float))
    ]
    assessments = [pose.get("targetAssessment") or {} for pose in single_poses]
    target_tolerance_statuses = Counter(
        item.get("toleranceStatus") or "not_available" for item in assessments
    )
    position_pass_count = sum(item.get("positionGatePassed") is True for item in assessments)
    angle_pass_count = sum(item.get("angleTolerancePassed") is True for item in assessments)
    correction_count = sum(
        isinstance(item.get("imageFrameCorrectionDeg"), (int, float)) for item in assessments
    )
    plc_blocked_count = sum(
        "PLC_MAPPING_UNCONFIRMED" in (item.get("blockers") or []) for item in assessments
    )
    guidances = [record.get("guidance") or {} for record in records]
    detection_status_counts = Counter(
        item.get("detectionStatus") or "not_available" for item in guidances
    )
    guidance_status_counts = Counter(
        item.get("guidanceStatus") or "not_available" for item in guidances
    )
    rotation_direction_counts = Counter(
        item.get("rotationDirection") or "not_available" for item in guidances
    )
    guidance_correction_count = sum(
        isinstance(item.get("imageFrameCorrectionDeg"), (int, float)) for item in guidances
    )
    guidance_plc_blocked_count = sum(
        item.get("plcExecutionStatus") == "BLOCKED_MAPPING_UNCONFIRMED" for item in guidances
    )
    role_status_counts = Counter(record.get("roleSuggestion", {}).get("status") or "not_available" for record in records)
    role_signatures = Counter(
        json.dumps(record.get("roleSuggestion", {}).get("selectedRoleCandidateIds"), sort_keys=True)
        for record in records
        if record.get("roleSuggestion", {}).get("selectedRoleCandidateIds")
    )
    elapsed = [float(record["elapsedMs"]) for record in records if isinstance(record.get("elapsedMs"), (int, float))]
    circle_count = sum(
        1 for record in records
        if all(isinstance((record.get("face") or {}).get(key), (int, float)) for key in ("centerX", "centerY", "radiusPx"))
    )
    physical_circle_count = sum(
        (record.get("physicalOuterCircle") or {}).get("status") == "accepted" for record in records
    )
    physical_circle_failures = Counter(
        reason
        for record in records
        for reason in (record.get("physicalOuterCircle") or {}).get("failedChecks") or []
    )
    complete_ring_count = sum(1 for record in records if (record.get("angularProfile") or {}).get("completeRing") is True)
    candidate_extraction_count = sum(1 for record in records if record.get("candidateSummary") is not None)
    role_unique_count = sum(1 for record in records if record.get("roleSuggestion", {}).get("status") == "unique_diagnostic_hypothesis")
    formal_valid_count = sum(1 for record in records if record.get("result", {}).get("valid") is True)
    localizations = [record.get("circleLocalization") or {} for record in records]
    localization_status_counts = Counter(item.get("status") or "not_available" for item in localizations)
    proposal_counts = [len(item.get("componentProposals") or []) for item in localizations]
    eligible_proposal_counts = [
        sum(proposal.get("status") == "eligible" for proposal in item.get("componentProposals") or [])
        for item in localizations
    ]
    sparse_circle_counts = [len(item.get("circleCandidates") or []) for item in localizations]
    localization_elapsed = [
        float(item["timingMs"]["totalLocalization"])
        for item in localizations
        if isinstance((item.get("timingMs") or {}).get("totalLocalization"), (int, float))
    ]
    polar_adjudications = [
        item for record in records
        if isinstance((item := record.get("polarQualityAdjudication")), dict)
    ]
    polar_decisions = Counter(
        str(item.get("decision") or "not_available") for item in polar_adjudications
    )
    polar_original_failures = Counter(
        check for item in polar_adjudications for check in item.get("originalFailedChecks") or []
    )
    polar_effective_failures = Counter(
        check for item in polar_adjudications for check in item.get("effectiveFailedChecks") or []
    )
    polar_proof_failures = Counter(
        check for item in polar_adjudications for check in item.get("failedChecks") or []
    )
    source_adjudications = [
        item for record in records
        if isinstance((item := record.get("sidewallSourceConsistencyAdjudication")), dict)
    ]
    source_decisions = Counter(
        str(item.get("decision") or "not_available") for item in source_adjudications
    )
    source_bases = Counter(
        str(item.get("sourceSeparationBasis") or "not_verified")
        for item in source_adjudications
    )
    source_original_failures = Counter(
        check for item in source_adjudications for check in item.get("originalFailedChecks") or []
    )
    source_proof_failures = Counter(
        check for item in source_adjudications for check in item.get("failedChecks") or []
    )
    return {
        "label": label,
        "imageCount": total,
        "circleEstimateAvailable": {"count": circle_count, "rate": circle_count / total if total else 0.0},
        "alignmentCircleEstimateAvailable": {"count": circle_count, "rate": circle_count / total if total else 0.0},
        "physicalOuterCircleAccepted": {
            "count": physical_circle_count, "rate": physical_circle_count / total if total else 0.0,
        },
        "physicalOuterCircleFailureCounts": dict(sorted(physical_circle_failures.items())),
        "polarQualityAdjudication": {
            "evaluatedCount": len(polar_adjudications),
            "decisionCounts": dict(sorted(polar_decisions.items())),
            "originalFailureCounts": dict(sorted(polar_original_failures.items())),
            "effectiveFailureCounts": dict(sorted(polar_effective_failures.items())),
            "proofFailureCounts": dict(sorted(polar_proof_failures.items())),
            "imagePoseReleaseAllowedCount": sum(
                item.get("imagePoseReleaseAllowed") is True for item in polar_adjudications
            ),
        },
        "sourceConsistencyAdjudication": {
            "evaluatedCount": len(source_adjudications),
            "decisionCounts": dict(sorted(source_decisions.items())),
            "sourceSeparationBasisCounts": dict(sorted(source_bases.items())),
            "originalFailureCounts": dict(sorted(source_original_failures.items())),
            "proofFailureCounts": dict(sorted(source_proof_failures.items())),
            "imagePoseReleaseAllowedCount": sum(
                item.get("imagePoseReleaseAllowed") is True for item in source_adjudications
            ),
        },
        "circleLocalizationStatusCounts": dict(sorted(localization_status_counts.items())),
        "componentProposalCountDistribution": dict(sorted(Counter(proposal_counts).items())),
        "eligibleComponentProposalCountDistribution": dict(sorted(Counter(eligible_proposal_counts).items())),
        "sparseCircleCandidateCountDistribution": dict(sorted(Counter(sparse_circle_counts).items())),
        "localizationElapsedMs": {
            "n": len(localization_elapsed),
            "p50": percentile(localization_elapsed, 0.5),
            "p95": percentile(localization_elapsed, 0.95),
            "max": max(localization_elapsed) if localization_elapsed else None,
        },
        "completeRingAccepted": {"count": complete_ring_count, "rate": complete_ring_count / total if total else 0.0},
        "candidateExtractionCompleted": {"count": candidate_extraction_count, "rate": candidate_extraction_count / total if total else 0.0},
        "candidateCountDistribution": {str(key): value for key, value in sorted(candidate_counts.items())},
        "candidateClusters": candidate_clusters(records, threshold_deg),
        "candidateIdTracks": candidate_id_tracks(records, threshold_deg),
        "grooveCandidateCountDistribution": {str(key): value for key, value in sorted(groove_candidate_counts.items())},
        "grooveCandidateClusters": candidate_clusters(
            [{**record, "candidates": record.get("grooveCandidates") or []} for record in records], threshold_deg,
        ),
        "grooveRecognitionStatusCounts": dict(sorted(groove_status_counts.items())),
        "grooveRejectionReasonCounts": dict(sorted(groove_rejections.items())),
        "rejectedDarkCandidateCount": sum(rejected_candidate_counts),
        "rejectedDarkCandidateCountDistribution": dict(sorted(Counter(rejected_candidate_counts).items())),
        "singleGroovePoseStatusCounts": dict(sorted(single_status_counts.items())),
        "singleGrooveGeometryValid": {
            "count": single_geometry_count,
            "rate": single_geometry_count / total if total else 0.0,
        },
        "imageGrooveAzimuthAvailable": {
            "count": len(single_azimuths),
            "rate": len(single_azimuths) / total if total else 0.0,
            "unstratifiedRawAngleStatistics": "NOT_EVALUATED",
            "reason": "image bearings require confirmed condition/truth groups before cross-frame statistics",
        },
        "singleGrooveQuadrantCounts": dict(sorted(single_quadrants.items())),
        "grooveRefinementStatusCounts": dict(sorted(refinement_status_counts.items())),
        "grooveRefinementSchemaCounts": dict(sorted(refinement_schema_counts.items())),
        "grooveRefinementThresholdCounts": dict(sorted(refinement_threshold_counts.items())),
        "grooveRefinementFailureCounts": dict(sorted(refinement_failures.items())),
        "grooveRefinementElapsedMs": distribution(refinement_elapsed),
        "grooveSidewallEvidence": {
            "lineInlierRatio": distribution(side_values("lineInlierRatio")),
            "lineLongitudinalCoverage": distribution(side_values("lineLongitudinalCoverage")),
            "lineResidualP95Px": distribution(side_values("p95", "lineResidualPx")),
            "supportMargin": distribution(side_values("supportMargin")),
            "rawHypothesisCount": distribution(side_values("rawHypothesisCount")),
            "physicalSourceFamilyCount": distribution(side_values("physicalSourceFamilyCount")),
            "eligiblePhysicalSourceFamilyCount": distribution(
                side_values("eligiblePhysicalSourceFamilyCount")
            ),
            "radialAlignmentDeltaDeg": distribution(side_values("radialAlignmentDeltaDeg")),
            "wallFamilySelectionElapsedMs": distribution(
                side_values("wallFamilySelectionElapsedMs")
            ),
            "wallFamilyStrategyCounts": dict(sorted(wall_family_strategy_counts.items())),
            "wallFamilyStatusCounts": dict(sorted(wall_family_status_counts.items())),
        },
        "yDownDatumAngleAvailable": {
            "count": len(y_down_angles), "rate": len(y_down_angles) / total if total else 0.0,
            "unstratifiedRawAngleStatistics": "NOT_EVALUATED",
            "reason": "different physical orientations require condition/truth groups before accuracy statistics",
        },
        "targetToleranceStatusCounts": dict(sorted(target_tolerance_statuses.items())),
        "targetPositionGatePassed": {
            "count": position_pass_count, "rate": position_pass_count / total if total else 0.0,
        },
        "targetAngleTolerancePassed": {
            "count": angle_pass_count, "rate": angle_pass_count / total if total else 0.0,
        },
        "imageFrameCorrectionAvailable": {
            "count": correction_count, "rate": correction_count / total if total else 0.0,
        },
        "plcGuidanceBlocked": {
            "count": max(plc_blocked_count, guidance_plc_blocked_count),
            "rate": max(plc_blocked_count, guidance_plc_blocked_count) / total if total else 0.0,
        },
        "detectionStatusCounts": dict(sorted(detection_status_counts.items())),
        "guidanceStatusCounts": dict(sorted(guidance_status_counts.items())),
        "rotationDirectionCounts": dict(sorted(rotation_direction_counts.items())),
        "closedLoopImageFrameCorrectionAvailable": {
            "count": guidance_correction_count,
            "rate": guidance_correction_count / total if total else 0.0,
        },
        "accuracyEvaluation": {
            "status": "NOT_EVALUATED",
            "reason": "PER_IMAGE_HUMAN_TRUTH_UNAVAILABLE",
        },
        "staticRepeatabilityEvaluation": {
            "status": "NOT_EVALUATED",
            "reason": "CONFIRMED_SAME_SAMPLE_POSE_CONDITION_GROUPS_UNAVAILABLE",
        },
        "mechanicalGuidanceBlockedByDatum": {
            "count": datum_blocked_count,
            "rate": datum_blocked_count / total if total else 0.0,
        },
        "roleAssignmentUnique": {"count": role_unique_count, "rate": role_unique_count / total if total else 0.0},
        "roleStatusCounts": dict(sorted(role_status_counts.items())),
        "selectedRoleSignatureCounts": dict(sorted(role_signatures.items())),
        "formalValid": {"count": formal_valid_count, "rate": formal_valid_count / total if total else 0.0},
        "errorCodeCounts": dict(sorted(error_counts.items())),
        "elapsedMs": {
            "n": len(elapsed),
            "p50": percentile(elapsed, 0.5),
            "p95": percentile(elapsed, 0.95),
            "max": max(elapsed) if elapsed else None,
        },
    }


def paired_circle_comparisons(runs: list[tuple[str, dict[str, Any]]]) -> list[dict[str, Any]]:
    comparisons: list[dict[str, Any]] = []
    for left_index in range(len(runs)):
        for right_index in range(left_index + 1, len(runs)):
            left_label, left_review = runs[left_index]
            right_label, right_review = runs[right_index]
            left_records = {str(item["imageId"]): item for item in left_review.get("records") or []}
            right_records = {str(item["imageId"]): item for item in right_review.get("records") or []}
            center_distances: list[float] = []
            radius_differences: list[float] = []
            for image_id in sorted(set(left_records) & set(right_records)):
                circles = []
                for record in (left_records[image_id], right_records[image_id]):
                    physical = record.get("physicalOuterCircle") or {}
                    circle = physical.get("physicalCircle") if physical.get("status") == "accepted" else None
                    circles.append(circle)
                if not all(isinstance(circle, dict) for circle in circles):
                    continue
                left_circle, right_circle = circles
                center_distances.append(math.hypot(
                    float(left_circle["centerX"]) - float(right_circle["centerX"]),
                    float(left_circle["centerY"]) - float(right_circle["centerY"]),
                ))
                radius_differences.append(abs(float(left_circle["radiusPx"]) - float(right_circle["radiusPx"])))
            comparisons.append({
                "left": left_label, "right": right_label,
                "matchedAcceptedCircleCount": len(center_distances),
                "centerDistancePx": {
                    "p50": percentile(center_distances, 0.5), "p95": percentile(center_distances, 0.95),
                    "max": max(center_distances) if center_distances else None,
                },
                "radiusAbsoluteDifferencePx": {
                    "p50": percentile(radius_differences, 0.5), "p95": percentile(radius_differences, 0.95),
                    "max": max(radius_differences) if radius_differences else None,
                },
            })
    return comparisons


def paired_refinement_comparisons(runs: list[tuple[str, dict[str, Any]]]) -> list[dict[str, Any]]:
    comparisons: list[dict[str, Any]] = []
    for left_index in range(len(runs)):
        for right_index in range(left_index + 1, len(runs)):
            left_label, left_review = runs[left_index]
            right_label, right_review = runs[right_index]
            left_records = {str(item["imageId"]): item for item in left_review.get("records") or []}
            right_records = {str(item["imageId"]): item for item in right_review.get("records") or []}
            deltas: list[float] = []
            for image_id in sorted(set(left_records) & set(right_records)):
                refinements = [left_records[image_id].get("grooveRefinement") or {}, right_records[image_id].get("grooveRefinement") or {}]
                if not all(item.get("status") == "accepted" for item in refinements):
                    continue
                midpoints = [item.get("openingMidpointProfileDeg") for item in refinements]
                if not all(isinstance(value, (int, float)) for value in midpoints):
                    continue
                deltas.append(circular_delta_deg(float(midpoints[1]), float(midpoints[0])))
            absolute = [abs(value) for value in deltas]
            comparisons.append({
                "left": left_label, "right": right_label,
                "matchedAcceptedRefinementCount": len(deltas),
                "midpointCircularDeltaDeg": {
                    "p50": percentile(deltas, 0.5), "p95": percentile(deltas, 0.95),
                    "maxAbsolute": max(absolute) if absolute else None,
                    "absoluteP95": percentile(absolute, 0.95),
                },
            })
    return comparisons


def parse_run(value: str) -> tuple[str, Path]:
    label, separator, raw_path = value.partition("=")
    if not separator or not label or not raw_path:
        raise argparse.ArgumentTypeError("run must be LABEL=REVIEW_JSON")
    return label, Path(raw_path)


def build_summary(runs: list[tuple[str, dict[str, Any]]], threshold_deg: float) -> dict[str, Any]:
    if not 0.0 < threshold_deg <= 180.0:
        raise ValueError("cluster threshold must be in (0,180]")
    return {
        "schemaVersion": "slot-pose-diagnostic-comparison/1",
        "candidateClusterThresholdDeg": threshold_deg,
        "roleSuggestionsAreAuthoritative": False,
        "runs": [summarize_run(label, review, threshold_deg) for label, review in runs],
        "pairedCircleComparisons": paired_circle_comparisons(runs),
        "pairedRefinementComparisons": paired_refinement_comparisons(runs),
        "interpretationLimits": [
            "Cross-frame stability can identify repeatable image features but cannot prove a drawing datum/target role.",
            "A stable image-frame cluster can still be a fixture, occlusion or lighting boundary.",
            "A valid v3 image-frame correction is not an executable PLC/mechanical command until mapping is confirmed.",
            "JPEG diagnostics cannot replace original-BMP angle accuracy truth.",
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="append", required=True, type=parse_run, help="LABEL=REVIEW_JSON")
    parser.add_argument("--cluster-threshold-deg", type=float, default=8.0)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        runs = [(label, json.loads(path.read_text(encoding="utf-8"))) for label, path in args.run]
        summary = build_summary(runs, args.cluster_threshold_deg)
        write_json(args.output, summary)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(f"Wrote {args.output}: runs={len(summary['runs'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
