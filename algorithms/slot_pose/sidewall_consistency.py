"""Hard-gated evidence that two refined sides share one physical groove source."""

from __future__ import annotations

import copy
import math
from typing import Any

import numpy as np


DEFAULT_SIDEWALL_CONSISTENCY_CONFIG: dict[str, Any] = {
    "schema_version": "groove-sidewall-source-consistency/1",
    "enabled": False,
    "threshold_version": "sidewall-source-consistency-v1",
    "max_contrast_normalized_difference": 0.12,
    "max_gradient_normalized_difference": 0.35,
    "max_normalized_profile_mae": 0.22,
    "min_normalized_profile_correlation": 0.75,
    "max_radial_coverage_difference": 0.20,
    "max_endpoint_structure_difference": 0.15,
}


def validate_sidewall_consistency_config(config: dict[str, Any]) -> None:
    if not isinstance(config, dict):
        raise ValueError("detector.sidewall_source_consistency must be an object")
    required = set(DEFAULT_SIDEWALL_CONSISTENCY_CONFIG)
    missing = sorted(required - set(config))
    unknown = sorted(set(config) - required)
    if missing:
        raise ValueError(f"sidewall_source_consistency missing fields: {missing}")
    if unknown:
        raise ValueError(f"sidewall_source_consistency has unknown fields: {unknown}")
    if config["schema_version"] != "groove-sidewall-source-consistency/1":
        raise ValueError("sidewall_source_consistency.schema_version is unsupported")
    if not isinstance(config["enabled"], bool):
        raise ValueError("sidewall_source_consistency.enabled must be boolean")
    if not isinstance(config["threshold_version"], str) or not config["threshold_version"].strip():
        raise ValueError("sidewall_source_consistency.threshold_version must be non-empty")
    for key in (
        "max_contrast_normalized_difference", "max_gradient_normalized_difference",
        "max_normalized_profile_mae", "min_normalized_profile_correlation",
        "max_radial_coverage_difference", "max_endpoint_structure_difference",
    ):
        value = config[key]
        if (
            isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(float(value)) or not 0.0 <= float(value) <= 1.0
        ):
            raise ValueError(f"sidewall_source_consistency.{key} must be in [0,1]")


def merged_sidewall_consistency_config(config: dict[str, Any] | None) -> dict[str, Any]:
    if config is not None and not isinstance(config, dict):
        raise ValueError("detector.sidewall_source_consistency must be an object")
    merged = copy.deepcopy(DEFAULT_SIDEWALL_CONSISTENCY_CONFIG)
    if config:
        merged.update(copy.deepcopy(config))
    validate_sidewall_consistency_config(merged)
    return merged


def _normalized_difference(first: float, second: float) -> float:
    return abs(float(first) - float(second)) / max(abs(float(first)), abs(float(second)), 1e-9)


def _profile(side: dict[str, Any], name: str) -> np.ndarray:
    evidence = side.get("profileEvidence")
    if not isinstance(evidence, dict):
        raise ValueError("missing profile evidence")
    values = np.asarray(evidence.get(name), dtype=float)
    if values.ndim != 1 or values.size < 3 or not np.isfinite(values).all():
        raise ValueError(f"invalid sidewall profile: {name}")
    return values


def _correlation(first: np.ndarray, second: np.ndarray) -> float:
    if first.shape != second.shape:
        return -1.0
    left = first - float(np.mean(first))
    right = second - float(np.mean(second))
    denominator = float(np.linalg.norm(left) * np.linalg.norm(right))
    if denominator <= 1e-12:
        return 1.0 if float(np.max(np.abs(first - second))) <= 1e-12 else 0.0
    return float(np.dot(left, right) / denominator)


def assess_sidewall_source_consistency(
    refinement: dict[str, Any],
    config: dict[str, Any] | None,
) -> dict[str, Any]:
    merged = merged_sidewall_consistency_config(config)
    base = {
        "schemaVersion": "groove-sidewall-source-consistency/1",
        "thresholdVersion": merged["threshold_version"],
        "enabled": bool(merged["enabled"]),
    }
    if not merged["enabled"]:
        return {**base, "status": "disabled", "metrics": {}, "checks": [], "failedChecks": []}
    if not isinstance(refinement, dict) or refinement.get("status") != "accepted":
        return {
            **base, "status": "not_evaluated", "metrics": {}, "checks": [],
            "failedChecks": ["refinement_not_accepted"],
        }
    start, end = refinement.get("startSide"), refinement.get("endSide")
    if not isinstance(start, dict) or not isinstance(end, dict):
        return {
            **base, "status": "rejected", "metrics": {}, "checks": [],
            "failedChecks": ["sidewall_evidence_missing"],
        }
    try:
        start_contrast = float(start["edgeContrastMedian"])
        end_contrast = float(end["edgeContrastMedian"])
        start_gradient = float(start["edgeGradientMedianPerPx"])
        end_gradient = float(end["edgeGradientMedianPerPx"])
        start_profile = _profile(start, "normalizedCanonicalGrayProfile")
        end_profile = _profile(end, "normalizedCanonicalGrayProfile")
        start_raw = _profile(start, "rawCanonicalGrayProfile")
        end_raw = _profile(end, "rawCanonicalGrayProfile")
        start_coverage = float(start["profileEvidence"]["radialCoverage"])
        end_coverage = float(end["profileEvidence"]["radialCoverage"])
    except (KeyError, TypeError, ValueError, OverflowError):
        return {
            **base, "status": "rejected", "metrics": {}, "checks": [],
            "failedChecks": ["sidewall_profile_invalid"],
        }
    if start_profile.shape != end_profile.shape or start_raw.shape != end_raw.shape:
        return {
            **base, "status": "rejected", "metrics": {}, "checks": [],
            "failedChecks": ["sidewall_profile_length_mismatch"],
        }
    metrics = {
        "contrastNormalizedDifference": _normalized_difference(start_contrast, end_contrast),
        "gradientNormalizedDifference": _normalized_difference(start_gradient, end_gradient),
        "normalizedProfileMae": float(np.mean(np.abs(start_profile - end_profile))),
        "normalizedProfileCorrelation": _correlation(start_profile, end_profile),
        "radialCoverageDifference": abs(start_coverage - end_coverage),
        "endpointStructureDifference": float(np.mean(np.abs(start_raw - end_raw)) / 255.0),
    }
    definitions = [
        ("edge_contrast_asymmetry", "contrastNormalizedDifference",
         "max_contrast_normalized_difference", "max"),
        ("edge_gradient_asymmetry", "gradientNormalizedDifference",
         "max_gradient_normalized_difference", "max"),
        ("normalized_profile_dissimilar", "normalizedProfileMae",
         "max_normalized_profile_mae", "max"),
        ("normalized_profile_uncorrelated", "normalizedProfileCorrelation",
         "min_normalized_profile_correlation", "min"),
        ("radial_coverage_inconsistent", "radialCoverageDifference",
         "max_radial_coverage_difference", "max"),
        ("endpoint_structure_inconsistent", "endpointStructureDifference",
         "max_endpoint_structure_difference", "max"),
    ]
    checks = []
    failed = []
    for failure, metric_name, threshold_name, direction in definitions:
        value = float(metrics[metric_name])
        threshold = float(merged[threshold_name])
        passed = value <= threshold if direction == "max" else value >= threshold
        margin = threshold - value if direction == "max" else value - threshold
        checks.append({
            "checkId": failure, "metric": metric_name, "value": value,
            "threshold": threshold, "thresholdKind": direction,
            "margin": margin, "passed": passed,
        })
        if not passed:
            failed.append(failure)
    return {
        **base,
        "status": "accepted" if not failed else "rejected",
        "metrics": metrics,
        "checks": checks,
        "failedChecks": failed,
    }
