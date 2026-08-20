"""Default-off scalar adjudication for contrast-only sidewall source rejection.

The original source-consistency payload is evidence, never mutable state.  This
module can only produce an independent effective decision for development
single-groove runs; it has no image identity, truth, mechanical or PLC input.
"""

from __future__ import annotations

import copy
import math
from typing import Any


DEFAULT_SOURCE_CONSISTENCY_ADJUDICATION_CONFIG: dict[str, Any] = {
    "schema_version": "source-consistency-adjudication/1",
    "enabled": False,
    "threshold_version": "endpoint-structure-runtime-adjudication-v1",
    "development_only": True,
    "max_endpoint_structure_difference": 0.05,
}
SOURCE_CONSISTENCY_ADJUDICATION_V2_CONFIG: dict[str, Any] = {
    "schema_version": "source-consistency-adjudication/2",
    "enabled": False,
    "strategy_version": "locked-noncontrast-gates-v2",
    "development_only": True,
}
SOURCE_CONSISTENCY_ADJUDICATION_V3_CONFIG: dict[str, Any] = {
    "schema_version": "source-consistency-adjudication/3",
    "enabled": False,
    "strategy_version": "locked-shape-profile-fixture-gates-v3",
    "development_only": True,
}
SOURCE_CONSISTENCY_ADJUDICATION_V4_CONFIG: dict[str, Any] = {
    "schema_version": "source-consistency-adjudication/4",
    "enabled": False,
    "strategy_version": "locked-visible-boundary-ownership-v4",
    "development_only": True,
}

_CHECK_DEFINITIONS = (
    ("edge_contrast_asymmetry", "contrastNormalizedDifference", "max"),
    ("edge_gradient_asymmetry", "gradientNormalizedDifference", "max"),
    ("normalized_profile_dissimilar", "normalizedProfileMae", "max"),
    ("normalized_profile_uncorrelated", "normalizedProfileCorrelation", "min"),
    ("radial_coverage_inconsistent", "radialCoverageDifference", "max"),
    ("endpoint_structure_inconsistent", "endpointStructureDifference", "max"),
)
_CHECK_IDS = tuple(item[0] for item in _CHECK_DEFINITIONS)
_METRIC_IDS = tuple(item[1] for item in _CHECK_DEFINITIONS)
_NON_CONTRAST_CHECK_IDS = _CHECK_IDS[1:]


def validate_source_consistency_adjudication_config(config: dict[str, Any]) -> None:
    if not isinstance(config, dict):
        raise ValueError("detector.source_consistency_adjudication must be an object")
    schema_version = config.get("schema_version")
    template = (
        SOURCE_CONSISTENCY_ADJUDICATION_V4_CONFIG
        if schema_version == "source-consistency-adjudication/4"
        else SOURCE_CONSISTENCY_ADJUDICATION_V3_CONFIG
        if schema_version == "source-consistency-adjudication/3"
        else SOURCE_CONSISTENCY_ADJUDICATION_V2_CONFIG
        if schema_version == "source-consistency-adjudication/2"
        else DEFAULT_SOURCE_CONSISTENCY_ADJUDICATION_CONFIG
    )
    required = set(template)
    missing = sorted(required - set(config))
    unknown = sorted(set(config) - required)
    if missing:
        raise ValueError(f"source_consistency_adjudication missing fields: {missing}")
    if unknown:
        raise ValueError(f"source_consistency_adjudication has unknown fields: {unknown}")
    if schema_version not in {
        "source-consistency-adjudication/1", "source-consistency-adjudication/2",
        "source-consistency-adjudication/3", "source-consistency-adjudication/4",
    }:
        raise ValueError("source_consistency_adjudication.schema_version is unsupported")
    if not isinstance(config["enabled"], bool):
        raise ValueError("source_consistency_adjudication.enabled must be boolean")
    if config["development_only"] is not True:
        raise ValueError("source_consistency_adjudication.development_only must be true")
    if schema_version == "source-consistency-adjudication/1":
        if not isinstance(config["threshold_version"], str) or not config["threshold_version"].strip():
            raise ValueError("source_consistency_adjudication.threshold_version must be non-empty")
        endpoint = config["max_endpoint_structure_difference"]
        if (
            isinstance(endpoint, bool)
            or not isinstance(endpoint, (int, float))
            or not math.isfinite(float(endpoint))
            or not 0.0 <= float(endpoint) <= 1.0
        ):
            raise ValueError(
                "source_consistency_adjudication.max_endpoint_structure_difference must be in [0,1]"
            )
    elif config["strategy_version"] != {
        "source-consistency-adjudication/2": "locked-noncontrast-gates-v2",
        "source-consistency-adjudication/3": "locked-shape-profile-fixture-gates-v3",
        "source-consistency-adjudication/4": "locked-visible-boundary-ownership-v4",
    }[schema_version]:
        raise ValueError("source_consistency_adjudication.strategy_version is unsupported")


def merged_source_consistency_adjudication_config(
    config: dict[str, Any] | None,
) -> dict[str, Any]:
    if config is not None and not isinstance(config, dict):
        raise ValueError("detector.source_consistency_adjudication must be an object")
    template = (
        SOURCE_CONSISTENCY_ADJUDICATION_V4_CONFIG
        if isinstance(config, dict)
        and config.get("schema_version") == "source-consistency-adjudication/4"
        else SOURCE_CONSISTENCY_ADJUDICATION_V3_CONFIG
        if isinstance(config, dict)
        and config.get("schema_version") == "source-consistency-adjudication/3"
        else SOURCE_CONSISTENCY_ADJUDICATION_V2_CONFIG
        if isinstance(config, dict)
        and config.get("schema_version") == "source-consistency-adjudication/2"
        else DEFAULT_SOURCE_CONSISTENCY_ADJUDICATION_CONFIG
    )
    merged = copy.deepcopy(template)
    if config:
        merged.update(copy.deepcopy(config))
    validate_source_consistency_adjudication_config(merged)
    return merged


def _base(config: dict[str, Any]) -> dict[str, Any]:
    return {
        "schemaVersion": config["schema_version"],
        **(
            {"strategyVersion": config["strategy_version"]}
            if config["schema_version"] in {
                "source-consistency-adjudication/2",
                "source-consistency-adjudication/3",
                "source-consistency-adjudication/4",
            }
            else {"thresholdVersion": config["threshold_version"]}
        ),
        "enabled": True,
        "developmentOnly": True,
        "authoritative": False,
        "productionDefaultAllowed": False,
        "plcAllowed": False,
        "manualTruthAppliedAtRuntime": False,
        **({"sourceSeparationBasis": None} if config["schema_version"] ==
           "source-consistency-adjudication/4" else {}),
    }


def _not_evaluated(
    base: dict[str, Any],
    *,
    original_status: Any,
    original_failed: list[str] | None,
    reason: str,
) -> dict[str, Any]:
    canonical_original_status = (
        original_status
        if original_status in {"accepted", "rejected", "not_evaluated", "disabled"}
        else None
    )
    return {
        **base,
        "decision": "NOT_EVALUATED",
        "originalStatus": canonical_original_status,
        "effectiveStatus": "not_evaluated",
        "originalFailedChecks": list(original_failed or []),
        "metrics": {},
        "checks": [],
        "failedChecks": [reason],
        "imagePoseReleaseAllowed": False,
    }


def _validated_evidence(
    source: dict[str, Any] | None,
) -> tuple[str, list[str], dict[str, float], list[dict[str, Any]]] | None:
    if not isinstance(source, dict):
        return None
    if source.get("schemaVersion") != "groove-sidewall-source-consistency/1":
        return None
    if source.get("enabled") is not True:
        return None
    status = source.get("status")
    if status not in {"accepted", "rejected"}:
        return None
    failed = source.get("failedChecks")
    metrics = source.get("metrics")
    checks = source.get("checks")
    if (
        not isinstance(failed, list)
        or not all(isinstance(item, str) for item in failed)
        or len(set(failed)) != len(failed)
        or not isinstance(metrics, dict)
        or set(metrics) != set(_METRIC_IDS)
        or not isinstance(checks, list)
        or len(checks) != len(_CHECK_DEFINITIONS)
    ):
        return None
    numeric_metrics: dict[str, float] = {}
    for metric in _METRIC_IDS:
        value = metrics.get(metric)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
            return None
        numeric_metrics[metric] = float(value)
    if [item.get("checkId") for item in checks if isinstance(item, dict)] != list(_CHECK_IDS):
        return None
    validated_checks: list[dict[str, Any]] = []
    for check, (check_id, metric, kind) in zip(checks, _CHECK_DEFINITIONS, strict=True):
        if not isinstance(check, dict):
            return None
        if check.get("checkId") != check_id or check.get("metric") != metric:
            return None
        if check.get("thresholdKind") != kind or not isinstance(check.get("passed"), bool):
            return None
        for key in ("value", "threshold", "margin"):
            value = check.get(key)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
                return None
        if not math.isclose(float(check["value"]), numeric_metrics[metric], rel_tol=0.0, abs_tol=1e-12):
            return None
        validated_checks.append(copy.deepcopy(check))
    derived_failed = [item["checkId"] for item in validated_checks if item["passed"] is False]
    if failed != derived_failed:
        return None
    if (status == "accepted") != (not failed):
        return None
    return status, list(failed), numeric_metrics, validated_checks


def adjudicate_source_consistency(
    source_consistency: dict[str, Any] | None,
    config: dict[str, Any] | None,
    *,
    fixture_source_evidence: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Return an independent effective decision; never mutate original evidence."""
    if config is None:
        return None
    merged = merged_source_consistency_adjudication_config(config)
    if not merged["enabled"]:
        return None
    base = _base(merged)
    evidence = _validated_evidence(source_consistency)
    if evidence is None:
        original_status = source_consistency.get("status") if isinstance(source_consistency, dict) else None
        original_failed = (
            source_consistency.get("failedChecks")
            if isinstance(source_consistency, dict)
            and isinstance(source_consistency.get("failedChecks"), list)
            and all(isinstance(item, str) for item in source_consistency["failedChecks"])
            else []
        )
        return _not_evaluated(
            base,
            original_status=original_status,
            original_failed=original_failed,
            reason="source_consistency_evidence_invalid",
        )
    status, failed, metrics, checks = evidence
    endpoint = metrics["endpointStructureDifference"]
    if status == "accepted":
        return {
            **base,
            "decision": "NOT_NEEDED",
            "originalStatus": status,
            "effectiveStatus": "accepted",
            "originalFailedChecks": failed,
            "metrics": {"endpointStructureDifference": endpoint},
            "checks": [],
            "failedChecks": [],
            "imagePoseReleaseAllowed": False,
        }

    check_map = {item["checkId"]: item for item in checks}
    contrast_only = failed == ["edge_contrast_asymmetry"]
    non_contrast_pass = all(check_map[check_id]["passed"] is True for check_id in _NON_CONTRAST_CHECK_IDS)
    is_v2 = merged["schema_version"] == "source-consistency-adjudication/2"
    is_v3 = merged["schema_version"] == "source-consistency-adjudication/3"
    is_v4 = merged["schema_version"] == "source-consistency-adjudication/4"
    endpoint_pass = (
        True if is_v2 or is_v3 or is_v4
        else endpoint <= float(merged["max_endpoint_structure_difference"])
    )
    photometric_only = bool(failed) and set(failed).issubset({
        "edge_contrast_asymmetry", "edge_gradient_asymmetry",
    })
    locked_shape_profile_pass = all(
        check_map[check_id]["passed"] is True
        for check_id in (
            "normalized_profile_dissimilar", "normalized_profile_uncorrelated",
            "radial_coverage_inconsistent", "endpoint_structure_inconsistent",
        )
    )
    adjudication_checks = [
        {"checkId": "original_rejected", "passed": status == "rejected"},
        {"checkId": (
            "bounded_source_failure" if is_v4
            else "photometric_only_failure" if is_v3 else "exact_contrast_only_failure"
        ), "passed": (
            bool(failed) and set(failed).issubset({
                "edge_contrast_asymmetry", "edge_gradient_asymmetry",
                "endpoint_structure_inconsistent",
            })
            if is_v4 else photometric_only if is_v3 else contrast_only
        )},
        {
            "checkId": (
                "locked_profile_and_coverage_checks_pass" if is_v4
                else "all_locked_shape_profile_checks_pass" if is_v3
                else "all_locked_noncontrast_checks_pass" if is_v2
                else "all_required_noncontrast_checks_pass"
            ),
            "passed": (
                all(check_map[check_id]["passed"] is True for check_id in (
                    "normalized_profile_dissimilar", "normalized_profile_uncorrelated",
                    "radial_coverage_inconsistent",
                ))
                if is_v4 else locked_shape_profile_pass if is_v3 else non_contrast_pass
            ),
        },
    ]
    source_separation_basis = None
    if is_v2 or is_v3 or is_v4:
        fixture_schema = (
            fixture_source_evidence.get("schemaVersion")
            if isinstance(fixture_source_evidence, dict) else None
        )
        common_fixture = isinstance(fixture_source_evidence, dict) and all(
            fixture_source_evidence.get(key) == value for key, value in {
                "status": "verified",
                "fixtureBodiesVerified": True,
                "fixtureSourceExcluded": True,
                "candidateSelectionUsedFixedAngle": False,
            }.items()
        )
        recovery_verified = bool(
            common_fixture and fixture_schema == "fixture-groove-source-exclusion/2"
            and fixture_source_evidence.get("uContourComplete") is True
            and fixture_source_evidence.get("radialSidewallsVerified") is True
            and fixture_source_evidence.get("radialRecoveryApplied") is True
        )
        complete_u_verified = bool(
            common_fixture
            and fixture_schema in {
                "fixture-groove-source-exclusion/1",
                "fixture-groove-source-exclusion/2",
            }
            and fixture_source_evidence.get("uContourComplete") is True
            and (fixture_schema != "fixture-groove-source-exclusion/2" or recovery_verified)
        )
        boundary_verified = bool(
            is_v4 and common_fixture
            and fixture_schema == "fixture-groove-source-exclusion/3"
            and fixture_source_evidence.get("twoSidewallsComplete") is True
            and fixture_source_evidence.get("visibleBoundaryOwnershipVerified") is True
            and fixture_source_evidence.get("centralFloorTrackPresent") is True
            and fixture_source_evidence.get("manualTruthAppliedAtRuntime") is False
        )
        fixture_verified = complete_u_verified or boundary_verified
        endpoint_authorized = bool(
            check_map["endpoint_structure_inconsistent"]["passed"] is True
            or (is_v4 and fixture_verified)
        )
        if is_v4:
            adjudication_checks.append({
                "checkId": "endpoint_structure_or_physical_source_verified",
                "passed": endpoint_authorized,
            })
        adjudication_checks.append({
            "checkId": "fixture_source_exclusion_verified",
            "passed": fixture_verified,
        })
        if boundary_verified:
            source_separation_basis = "visible_boundary_ownership"
        elif recovery_verified:
            source_separation_basis = "recovery_verified"
        elif complete_u_verified:
            source_separation_basis = "complete_u_contour"
    if not is_v2 and not is_v3 and not is_v4:
        adjudication_checks.append({
            "checkId": "strict_endpoint_structure",
            "metric": "endpointStructureDifference",
            "value": endpoint,
            "threshold": float(merged["max_endpoint_structure_difference"]),
            "thresholdKind": "max",
            "margin": float(merged["max_endpoint_structure_difference"]) - endpoint,
            "passed": endpoint_pass,
        })
    adjudication_failed = [item["checkId"] for item in adjudication_checks if not item["passed"]]
    accepted = not adjudication_failed
    return {
        **base,
        "decision": "ACCEPTED_OVERRIDE" if accepted else "REJECTED",
        "originalStatus": status,
        "effectiveStatus": "accepted" if accepted else "rejected",
        "originalFailedChecks": failed,
        "metrics": {"endpointStructureDifference": endpoint},
        "checks": adjudication_checks,
        "failedChecks": adjudication_failed,
        "imagePoseReleaseAllowed": accepted,
        **({"sourceSeparationBasis": source_separation_basis} if is_v4 else {}),
    }
