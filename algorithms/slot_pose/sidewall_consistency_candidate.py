"""Non-authoritative, default-off candidate for source-consistency diagnosis."""

from __future__ import annotations

import copy
import math
from typing import Any


DEFAULT_SIDEWALL_CONSISTENCY_CANDIDATE_CONFIG: dict[str, Any] = {
    "schema_version": "sidewall-source-consistency-candidate/1",
    "enabled": False,
    "threshold_version": "endpoint-structure-development-candidate-v1",
    "development_only": True,
    "max_endpoint_structure_difference": 0.05,
}


def validate_sidewall_consistency_candidate_config(config: dict[str, Any]) -> None:
    if not isinstance(config, dict):
        raise ValueError("detector.sidewall_source_consistency_candidate must be an object")
    required = set(DEFAULT_SIDEWALL_CONSISTENCY_CANDIDATE_CONFIG)
    missing = sorted(required - set(config))
    unknown = sorted(set(config) - required)
    if missing:
        raise ValueError(f"sidewall_source_consistency_candidate missing fields: {missing}")
    if unknown:
        raise ValueError(f"sidewall_source_consistency_candidate has unknown fields: {unknown}")
    if config["schema_version"] != "sidewall-source-consistency-candidate/1":
        raise ValueError("sidewall_source_consistency_candidate.schema_version is unsupported")
    if not isinstance(config["enabled"], bool):
        raise ValueError("sidewall_source_consistency_candidate.enabled must be boolean")
    if config["development_only"] is not True:
        raise ValueError("sidewall_source_consistency_candidate.development_only must be true")
    if not isinstance(config["threshold_version"], str) or not config["threshold_version"].strip():
        raise ValueError("sidewall_source_consistency_candidate.threshold_version must be non-empty")
    value = config["max_endpoint_structure_difference"]
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)) \
            or not 0.0 <= float(value) <= 1.0:
        raise ValueError("sidewall_source_consistency_candidate.max_endpoint_structure_difference must be in [0,1]")


def merged_sidewall_consistency_candidate_config(config: dict[str, Any] | None) -> dict[str, Any]:
    if config is not None and not isinstance(config, dict):
        raise ValueError("detector.sidewall_source_consistency_candidate must be an object")
    merged = copy.deepcopy(DEFAULT_SIDEWALL_CONSISTENCY_CANDIDATE_CONFIG)
    if config:
        merged.update(copy.deepcopy(config))
    validate_sidewall_consistency_candidate_config(merged)
    return merged


def assess_sidewall_consistency_candidate(
    source_consistency: dict[str, Any] | None,
    config: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Return diagnostic evidence only; disabled/absent configuration returns no field."""
    if config is None:
        return None
    merged = merged_sidewall_consistency_candidate_config(config)
    if not merged["enabled"]:
        return None
    base = {
        "schemaVersion": "sidewall-source-consistency-candidate/1",
        "thresholdVersion": merged["threshold_version"],
        "developmentOnly": True,
        "authoritative": False,
        "posePromotionAllowed": False,
        "manualTruthAppliedAtRuntime": False,
    }
    if not isinstance(source_consistency, dict):
        return {**base, "status": "NOT_EVALUATED", "originalStatus": None,
                "originalFailedChecks": [], "metrics": {}, "checks": [],
                "failedChecks": ["source_consistency_missing"]}
    original_status = source_consistency.get("status")
    failed = source_consistency.get("failedChecks")
    metrics = source_consistency.get("metrics")
    checks = source_consistency.get("checks")
    if not isinstance(failed, list) or not all(isinstance(item, str) for item in failed) \
            or not isinstance(metrics, dict) or not isinstance(checks, list):
        return {**base, "status": "NOT_EVALUATED", "originalStatus": original_status,
                "originalFailedChecks": [], "metrics": {}, "checks": [],
                "failedChecks": ["source_consistency_evidence_invalid"]}
    endpoint = metrics.get("endpointStructureDifference")
    if isinstance(endpoint, bool) or not isinstance(endpoint, (int, float)) or not math.isfinite(float(endpoint)):
        return {**base, "status": "NOT_EVALUATED", "originalStatus": original_status,
                "originalFailedChecks": list(failed), "metrics": {}, "checks": [],
                "failedChecks": ["endpoint_structure_metric_missing"]}
    check_map = {item.get("checkId"): item for item in checks if isinstance(item, dict)}
    required_other_checks = {
        "edge_gradient_asymmetry", "normalized_profile_dissimilar", "normalized_profile_uncorrelated",
        "radial_coverage_inconsistent", "endpoint_structure_inconsistent",
    }
    other_checks_pass = all(check_map.get(check_id, {}).get("passed") is True for check_id in required_other_checks)
    contrast_only = original_status == "rejected" and failed == ["edge_contrast_asymmetry"]
    endpoint_pass = float(endpoint) <= float(merged["max_endpoint_structure_difference"])
    candidate_checks = [
        {"checkId": "original_rejected_contrast_only", "passed": contrast_only},
        {"checkId": "all_other_original_checks_passed", "passed": other_checks_pass},
        {"checkId": "development_endpoint_structure", "metric": "endpointStructureDifference",
         "value": float(endpoint), "threshold": float(merged["max_endpoint_structure_difference"]),
         "thresholdKind": "max", "passed": endpoint_pass},
    ]
    candidate_failed = [item["checkId"] for item in candidate_checks if not item["passed"]]
    return {
        **base,
        "status": "CANDIDATE_SUPPORTED" if not candidate_failed else "CANDIDATE_REJECTED",
        "originalStatus": original_status,
        "originalFailedChecks": list(failed),
        "metrics": {"endpointStructureDifference": float(endpoint)},
        "checks": candidate_checks,
        "failedChecks": candidate_failed,
    }
