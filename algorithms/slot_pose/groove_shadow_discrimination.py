"""Fail-closed source disposition from existing groove physics evidence.

This module deliberately owns no numeric decision threshold. It only combines
the accepted/failed/not-evaluated outcomes of already-versioned gates.
"""

from __future__ import annotations

import math
from typing import Any


SCHEMA_VERSION = "groove-shadow-source-diagnostic/1"
SCHEMA_VERSION_V2 = "groove-shadow-source-diagnostic/2"
CONFIG_SCHEMA_VERSION = "groove-shadow-source-discrimination/1"
CONFIG_SCHEMA_VERSION_V2 = "groove-shadow-source-discrimination/2"
STRATEGY_VERSION = "physical-sidewall-source-evidence/1"
STRATEGY_VERSION_V2 = "fixture-role-u-contour-source-evidence/2"
MAX_CANDIDATES = 3

COMPLETE = "REAL_GROOVE_COMPLETE_NEAR_FIXTURE_SHADOW"
COMPLETE_VISIBLE = "REAL_GROOVE_COMPLETE_VISIBLE"
MIXED = "REAL_GROOVE_SHADOW_MIXED_OR_OCCLUDED"
INDETERMINATE = "INDETERMINATE"

DEFAULT_GROOVE_SHADOW_SOURCE_CONFIG: dict[str, Any] = {
    "schema_version": CONFIG_SCHEMA_VERSION,
    "enabled": False,
    "strategy_version": STRATEGY_VERSION,
}
GROOVE_SHADOW_SOURCE_V2_CONFIG: dict[str, Any] = {
    "schema_version": CONFIG_SCHEMA_VERSION_V2,
    "enabled": False,
    "strategy_version": STRATEGY_VERSION_V2,
}

_EVALUATION_STATUSES = {"accepted", "failed", "not_evaluated"}
_TERMINAL_STAGES = {
    "upstream_outer_circle", "candidate_generation", "groove_recognition",
    "groove_ambiguity", "polar_quality", "groove_refinement",
    "source_consistency", "valid",
}


def merged_groove_shadow_source_config(config: dict[str, Any] | None) -> dict[str, Any]:
    if config is not None and not isinstance(config, dict):
        raise ValueError("groove_shadow_source_discrimination must be an object")
    template = (
        GROOVE_SHADOW_SOURCE_V2_CONFIG
        if isinstance(config, dict) and config.get("schema_version") == CONFIG_SCHEMA_VERSION_V2
        else DEFAULT_GROOVE_SHADOW_SOURCE_CONFIG
    )
    merged = {**template, **(config or {})}
    unexpected = sorted(set(merged) - set(template))
    if unexpected:
        raise ValueError(
            "groove_shadow_source_discrimination has unsupported fields: "
            f"{unexpected}"
        )
    if merged["schema_version"] not in {CONFIG_SCHEMA_VERSION, CONFIG_SCHEMA_VERSION_V2}:
        raise ValueError("groove_shadow_source_discrimination.schema_version is unsupported")
    expected_strategy = (
        STRATEGY_VERSION_V2
        if merged["schema_version"] == CONFIG_SCHEMA_VERSION_V2 else STRATEGY_VERSION
    )
    if merged["strategy_version"] != expected_strategy:
        raise ValueError("groove_shadow_source_discrimination.strategy_version is unsupported")
    if not isinstance(merged["enabled"], bool):
        raise ValueError("groove_shadow_source_discrimination.enabled must be boolean")
    return merged


def _contains_nonfinite(value: Any) -> bool:
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return False
    if isinstance(value, (int, float)):
        return not math.isfinite(float(value))
    if isinstance(value, dict):
        return any(_contains_nonfinite(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return any(_contains_nonfinite(item) for item in value)
    return False


def _evaluation(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or value.get("status") not in _EVALUATION_STATUSES:
        return {"status": "not_evaluated", "failedChecks": ["evidence_missing"]}
    checks = value.get("failedChecks", [])
    if not isinstance(checks, list) or any(not isinstance(item, str) for item in checks):
        checks = ["invalid_failed_checks"]
    return {"status": value["status"], "failedChecks": sorted(set(checks))[:16]}


def _metrics(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    output: dict[str, Any] = {}
    for key in sorted(value)[:32]:
        item = value[key]
        if item is None or isinstance(item, (bool, str)):
            output[str(key)] = item
        elif isinstance(item, (int, float)) and math.isfinite(float(item)):
            output[str(key)] = item
    return output


def _normalize_candidate(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {
            "candidateId": "invalid",
            "coarseRecognition": _evaluation(None),
            "coarseMetrics": None,
            "physicalRefinement": _evaluation(None),
            "sidewallEvidence": None,
            "sourceConsistency": _evaluation(None),
            "sourceMetrics": None,
            "mixedOrOccludedEvidence": False,
            "sourceDisposition": INDETERMINATE,
            "failedChecks": ["candidate_evidence_invalid"],
        }
    candidate_id = value.get("candidateId")
    if not isinstance(candidate_id, str) or not candidate_id:
        candidate_id = "invalid"
    recognition = _evaluation(value.get("coarseRecognition"))
    refinement = _evaluation(value.get("physicalRefinement"))
    source = _evaluation(value.get("sourceConsistency"))
    mixed = value.get("mixedOrOccludedEvidence") is True
    failed = sorted(set(
        recognition["failedChecks"] + refinement["failedChecks"] + source["failedChecks"]
    ))[:32]
    coarse_metrics = _metrics(value.get("coarseMetrics"))
    provisional = bool(
        isinstance(coarse_metrics, dict)
        and coarse_metrics.get("provisionalRecognition") is True
    )
    fixture_excluded = bool(
        isinstance(coarse_metrics, dict)
        and coarse_metrics.get("fixtureSourceExcluded") is True
    )
    effective_source = bool(
        source["status"] == "accepted"
        or (
            isinstance(coarse_metrics, dict)
            and coarse_metrics.get("effectiveSourceAccepted") is True
        )
    )
    survivor = (
        (recognition["status"] == "accepted" or (provisional and fixture_excluded))
        and refinement["status"] == "accepted"
        and effective_source
    )
    explicitly_rejected = (
        recognition["status"] == "failed"
        or refinement["status"] == "failed"
        or (refinement["status"] == "accepted" and source["status"] == "failed")
    )
    if survivor:
        disposition = "REAL_GROOVE_SURVIVOR"
    elif mixed and explicitly_rejected:
        disposition = "MIXED_OR_OCCLUDED_EVIDENCE"
    elif explicitly_rejected:
        disposition = "NON_GROOVE_SOURCE_REJECTED"
    else:
        disposition = INDETERMINATE
    return {
        "candidateId": candidate_id,
        "coarseRecognition": recognition,
        "coarseMetrics": coarse_metrics,
        "physicalRefinement": refinement,
        "sidewallEvidence": _metrics(value.get("sidewallEvidence")),
        "sourceConsistency": source,
        "sourceMetrics": _metrics(value.get("sourceMetrics")),
        "mixedOrOccludedEvidence": mixed,
        "sourceDisposition": disposition,
        "failedChecks": failed,
    }


def build_candidate_source_evidence(
    recognition: dict[str, Any], *,
    single_refinement: dict[str, Any] | None = None,
    resolution: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Convert existing runtime diagnostics into bounded source evidence."""
    attempts = {}
    if isinstance(resolution, dict):
        attempts = {
            str(item.get("candidateId")): item.get("refinement")
            for item in resolution.get("attempts", [])
            if isinstance(item, dict)
        }
    if isinstance(single_refinement, dict):
        coarse_id = single_refinement.get("coarseCandidateId")
        if isinstance(coarse_id, str):
            attempts[coarse_id] = single_refinement
    metric_names = (
        "grooveScore", "radialDepthPx", "radialDepthRatio", "angularWidthDeg",
        "tangentialWidthPx", "localMetalContrast", "leftEdgeContrast",
        "rightEdgeContrast", "pairedEdgeSupport", "contourContinuity",
        "widthMeanDeg", "widthCoefficientOfVariation", "centerDriftDeg",
        "centerDriftRatio", "outerConnected",
    )
    output = []
    provisional_ids = set(recognition.get("provisionalCandidateIds") or [])
    accepted_assessments = [
        item for item in recognition.get("assessments", [])
        if isinstance(item, dict) and (
            item.get("accepted") is True or item.get("candidateId") in provisional_ids
        )
    ]
    for assessment in accepted_assessments[:MAX_CANDIDATES]:
        if not isinstance(assessment, dict):
            continue
        candidate_id = str(assessment.get("candidateId", "invalid"))
        refinement = attempts.get(candidate_id)
        source = refinement.get("sourceConsistency") if isinstance(refinement, dict) else None
        adjudication = (
            refinement.get("sourceConsistencyAdjudication")
            if isinstance(refinement, dict) else None
        )
        fixture_exclusion = (
            refinement.get("fixtureSourceExclusion")
            if isinstance(refinement, dict) else None
        )
        fixture_overlap = (
            fixture_exclusion.get("candidateFixtureOverlap")
            if isinstance(fixture_exclusion, dict) else None
        )
        physical_status = "not_evaluated"
        if isinstance(refinement, dict):
            physical_raw = refinement.get("physicalRefinementStatus", refinement.get("status"))
            physical_status = physical_raw if physical_raw in {"accepted", "failed"} else "not_evaluated"
        source_status = "not_evaluated"
        if isinstance(source, dict):
            source_status = {
                "accepted": "accepted", "failed": "failed", "rejected": "failed",
            }.get(source.get("status"), "not_evaluated")
        refinement_checks = list(refinement.get("failedChecks") or []) if isinstance(refinement, dict) else []
        source_checks = list(source.get("failedChecks") or []) if isinstance(source, dict) else []
        # A failed wall fit alone is not proof of occlusion: a complete groove
        # near a fixture shadow can fail consensus. Only the original locked
        # two-wall source gate (or an explicit future evidence flag) supports
        # the semantic mixed/occluded label.
        structural_source_failure = any(
            check != "edge_contrast_asymmetry" for check in source_checks
        )
        fixture_exclusion = (
            refinement.get("fixtureSourceExclusion")
            if isinstance(refinement, dict) else None
        )
        overlap = (
            fixture_exclusion.get("candidateFixtureOverlap")
            if isinstance(fixture_exclusion, dict) else None
        )
        upper_overlap_without_u_contour = bool(
            isinstance(overlap, dict)
            and overlap.get("upperFixtureOcclusionRisk") is True
            and fixture_exclusion.get("uContourComplete") is not True
        )
        lower_fixture_false_source = bool(
            isinstance(overlap, dict)
            and overlap.get("lowerFixtureFalseSourceRisk") is True
        )
        mixed = bool(
            not lower_fixture_false_source
            and (
                structural_source_failure
                or upper_overlap_without_u_contour
                or (
                    isinstance(refinement, dict)
                    and refinement.get("mixedOrOccludedEvidence") is True
                )
            )
        )
        output.append({
            "candidateId": candidate_id,
            "coarseRecognition": {
                "status": "accepted" if assessment.get("accepted") is True else "failed",
                "failedChecks": list(assessment.get("rejectionReasons") or []),
            },
            "coarseMetrics": {
                **{name: assessment.get(name) for name in metric_names if name in assessment},
                "originalRecognitionAccepted": assessment.get("accepted") is True,
                "provisionalRecognition": candidate_id in provisional_ids,
                "fixtureSourceExcluded": (
                    fixture_exclusion.get("fixtureSourceExcluded") is True
                    if isinstance(fixture_exclusion, dict) else False
                ),
                "fixtureOverlapRole": (
                    fixture_overlap.get("overlapRole")
                    if isinstance(fixture_overlap, dict) else None
                ),
                "effectiveSourceAccepted": bool(
                    source_status == "accepted"
                    or (
                        isinstance(adjudication, dict)
                        and adjudication.get("effectiveStatus") == "accepted"
                        and adjudication.get("imagePoseReleaseAllowed") is True
                    )
                ),
            },
            "physicalRefinement": {
                "status": physical_status,
                "failedChecks": refinement_checks,
            },
            "sidewallEvidence": {
                "startSidePresent": isinstance((refinement or {}).get("startSide"), dict),
                "endSidePresent": isinstance((refinement or {}).get("endSide"), dict),
                "outerCircleIntersectionsPresent": (
                    isinstance((refinement or {}).get("outerCircleIntersections"), list)
                    and len((refinement or {}).get("outerCircleIntersections")) == 2
                ),
            } if isinstance(refinement, dict) else None,
            "sourceConsistency": {
                "status": source_status,
                "failedChecks": source_checks,
            },
            "sourceMetrics": source.get("metrics") if isinstance(source, dict) else None,
            "mixedOrOccludedEvidence": mixed,
        })
    return output


def classify_groove_shadow_sources(
    candidates: list[dict[str, Any]], *, enabled: bool,
    upstream_accepted: bool, polar_quality_accepted: bool,
    existing_pose_chain_allowed: bool, terminal_stage: str,
    locked_gate_versions: dict[str, str] | None = None,
    strategy_version: str = STRATEGY_VERSION,
    raw_candidate_screening: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a bounded diagnostic without weakening any upstream gate."""
    if terminal_stage not in _TERMINAL_STAGES:
        terminal_stage = "upstream_outer_circle"
    base = {
        "schemaVersion": (
            SCHEMA_VERSION_V2 if strategy_version == STRATEGY_VERSION_V2 else SCHEMA_VERSION
        ),
        "strategyVersion": strategy_version,
        "enabled": bool(enabled),
        "terminalStage": terminal_stage,
        "poseChainAllowed": bool(existing_pose_chain_allowed),
        "selectedCandidateId": None,
        "candidateCount": len(candidates) if isinstance(candidates, list) else 0,
        "candidateEvidence": [],
        "passedChecks": [],
        "failedChecks": [],
        "lockedGateVersions": dict(sorted((locked_gate_versions or {}).items())),
    }
    if not enabled:
        return {**base, "status": "disabled", "classification": None}
    if not isinstance(candidates, list):
        return {
            **base, "status": "not_evaluated", "classification": INDETERMINATE,
            "poseChainAllowed": False, "failedChecks": ["candidate_evidence_missing"],
        }
    if len(candidates) > MAX_CANDIDATES:
        return {
            **base, "status": "rejected", "classification": INDETERMINATE,
            "poseChainAllowed": False, "failedChecks": ["candidate_capacity_exceeded"],
        }
    nonfinite = _contains_nonfinite(candidates)
    normalized = [_normalize_candidate(item) for item in candidates]
    base["candidateEvidence"] = normalized
    if not upstream_accepted:
        return {
            **base, "status": "not_evaluated", "classification": INDETERMINATE,
            "poseChainAllowed": False, "failedChecks": ["upstream_evidence_unavailable"],
        }
    if nonfinite:
        return {
            **base, "status": "rejected", "classification": INDETERMINATE,
            "poseChainAllowed": False, "failedChecks": ["nonfinite_candidate_evidence"],
        }
    survivors = [item for item in normalized if item["sourceDisposition"] == "REAL_GROOVE_SURVIVOR"]
    rejected = [item for item in normalized if item["sourceDisposition"] in {
        "NON_GROOVE_SOURCE_REJECTED", "MIXED_OR_OCCLUDED_EVIDENCE",
    }]
    unevaluated = [item for item in normalized if item["sourceDisposition"] == INDETERMINATE]
    passed: list[str] = []
    failed: list[str] = []
    classification = INDETERMINATE
    local_accepted = False
    status = "rejected"
    selected = None
    if unevaluated:
        status = "not_evaluated"
        failed.append("candidate_source_evidence_not_evaluated")
    elif len(survivors) > 1:
        failed.append("multiple_physical_survivors")
    elif len(survivors) == 1 and len(normalized) >= 2 and len(rejected) == len(normalized) - 1:
        survivor_metrics = survivors[0].get("coarseMetrics") or {}
        classification = (
            COMPLETE_VISIBLE
            if survivor_metrics.get("fixtureOverlapRole") == "none"
            else COMPLETE
        )
        local_accepted = True
        selected = survivors[0]["candidateId"]
        passed.extend([
            "unique_physical_groove_survivor",
            "all_competing_sources_explicitly_rejected",
        ])
    elif not survivors and any(item["sourceDisposition"] == "MIXED_OR_OCCLUDED_EVIDENCE" for item in normalized):
        classification = MIXED
        failed.append("mixed_or_occluded_physical_evidence")
    elif (
        not survivors
        and isinstance(raw_candidate_screening, dict)
        and isinstance(
            raw_candidate_screening.get("upperFixtureMixedOrOccludedRiskCount"), int,
        )
        and raw_candidate_screening["upperFixtureMixedOrOccludedRiskCount"] > 0
    ):
        classification = MIXED
        failed.append("upper_fixture_mixed_or_occluded_candidate_evidence")
    elif len(survivors) == 1:
        survivor_metrics = survivors[0].get("coarseMetrics") or {}
        classification = (
            COMPLETE_VISIBLE
            if survivor_metrics.get("fixtureOverlapRole") == "none"
            else COMPLETE
        )
        if len(normalized) == 1 and existing_pose_chain_allowed:
            local_accepted = True
            selected = survivors[0]["candidateId"]
            passed.append("unique_effective_candidate_survivor")
        else:
            failed.append("no_competing_source_evidence")
    elif not normalized:
        failed.append("no_candidate_evidence")
    else:
        failed.append("no_complete_physical_groove_survivor")
    if not polar_quality_accepted:
        failed.append("global_polar_quality_failed")
    pose_allowed = bool(local_accepted and polar_quality_accepted and existing_pose_chain_allowed)
    if local_accepted and polar_quality_accepted and pose_allowed:
        status = "accepted"
        passed.append("all_existing_global_gates_accepted")
    elif local_accepted:
        status = "rejected"
        if polar_quality_accepted:
            failed.append("existing_pose_chain_rejected")
    return {
        **base,
        "status": status,
        "classification": classification,
        "poseChainAllowed": pose_allowed,
        "selectedCandidateId": selected,
        "passedChecks": sorted(set(passed)),
        "failedChecks": sorted(set(failed)),
    }
