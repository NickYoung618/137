"""Quality-policy adapter around immutable core measurement statuses."""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any


QUALITY_POLICY_SCHEMA_VERSION = "a-end-face-quality-policy/1"
MEASUREMENT_VALID_SUFFIX = ".quality.measurement_valid"


def _finite_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def policy_sha256(policy: Mapping[str, Any]) -> str:
    canonical = json.dumps(policy, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def validate_quality_policy(policy: Mapping[str, Any]) -> None:
    if policy.get("schemaVersion") != QUALITY_POLICY_SCHEMA_VERSION:
        raise ValueError("unsupported end-face quality policy schemaVersion")
    if not isinstance(policy.get("policyId"), str) or not policy["policyId"].strip():
        raise ValueError("quality policyId is required")
    localization = policy.get("localization")
    if not isinstance(localization, Mapping):
        raise ValueError("quality policy localization object is required")
    metrics = localization.get("requiredFiniteMetrics")
    required_metrics = {
        "transform.target_center_x_px",
        "transform.target_center_y_px",
        "transform.scale",
        "transform.rotation_deg",
    }
    if not isinstance(metrics, list) or not metrics or not required_metrics.issubset(set(metrics)):
        raise ValueError("requiredFiniteMetrics must include center, scale and rotation metrics")
    scale_range = localization.get("scaleRange")
    if not isinstance(scale_range, list) or len(scale_range) != 2:
        raise ValueError("localization.scaleRange must contain [minimum, maximum]")
    minimum = _finite_number(scale_range[0])
    maximum = _finite_number(scale_range[1])
    if minimum is None or maximum is None or minimum <= 0 or minimum > maximum:
        raise ValueError("localization.scaleRange must be finite, positive and ordered")
    margin = _finite_number(localization.get("centerMarginPx"))
    if margin is None or margin < 0:
        raise ValueError("localization.centerMarginPx must be non-negative")
    prefixes = localization.get("allowedMethodPrefixes")
    if not isinstance(prefixes, list) or not prefixes or not all(isinstance(item, str) and item for item in prefixes):
        raise ValueError("localization.allowedMethodPrefixes must contain non-empty strings")
    orientation = localization.get("orientationEvidence")
    if not isinstance(orientation, Mapping):
        raise ValueError("localization.orientationEvidence is required")
    rotation_score = _finite_number(orientation.get("minimumRotationScore"))
    notch_prominence = _finite_number(orientation.get("minimumNotchProminence"))
    if rotation_score is None or rotation_score < 0 or notch_prominence is None or notch_prominence < 0:
        raise ValueError("orientation evidence thresholds must be finite and non-negative")
    labels = localization.get("requiredFeatureLabels")
    if not isinstance(labels, list) or not all(isinstance(item, str) and item for item in labels):
        raise ValueError("localization.requiredFeatureLabels must be a string array")


def load_quality_policy(path: Path) -> dict[str, Any]:
    policy = json.loads(path.read_text(encoding="utf-8"))
    validate_quality_policy(policy)
    return policy


def _core_valid(value: Any) -> bool:
    number = _finite_number(value)
    return number is not None and number > 0.5


def canonical_feature_label(label: str) -> str:
    """Keep the raw label but expose a stable identity for known damaged diameter glyphs."""
    canonical = label.strip()
    for glyph in ("\ufffd", "φ", "Φ", "ψ", "Ψ", "ø", "Ø", "⌀"):
        canonical = canonical.replace(glyph, "")
    canonical = canonical.strip()
    return canonical or label


def diagnose_core_quality(status: Mapping[str, Any]) -> dict[str, Any]:
    """Map public core quality outputs to their immutable source conditions."""
    reason = str(status.get("reason") or "")
    source = str(status.get("source") or "")
    fields = status.get("fields") if isinstance(status.get("fields"), Mapping) else {}
    if reason == "short_line_lateral_edge_not_found" or source.startswith("short_line_"):
        detector_path = "short_line_lateral_edge"
        conditions = {
            "maximumAnnotatedLengthPx": 80.0,
            "minimumUsableLengthPx": 4.0,
            "lateralSearchPx": 12,
            "shortLinePeakRule": "peak >= max(1.4 * median, median + 5) and peak is not at search boundary",
        }
    elif reason == "d46_radial_low_score" or source.startswith("d46_"):
        detector_path = "d46_radial_ncc"
        conditions = {
            "minimumNccScore": 0.55,
            "radialSearchRangePx": 32,
            "templateHalfWidthPx": 56,
        }
    elif reason == "template_anchor_fallback" or "template" in source or "radial" in source:
        detector_path = "middle_ring_template"
        conditions = {
            "minimumTemplateScore": 0.35,
            "minimumRadialPointCount": 180,
            "maximumRadialResidualPx": 4.0,
            "templatePriorDeviationGatePx": 6.0,
            "radialImprovementMarginPx": 1.0,
        }
    elif reason == "inner_edge_insufficient_points" or source.startswith("inner_edge_"):
        detector_path = "inner_hole_edge_fit"
        conditions = {"minimumEdgePointCount": 8}
    elif reason == "outer_boundary_insufficient_points" or source.startswith("outer_boundary_"):
        detector_path = "outer_boundary_edge_fit"
        conditions = {"minimumEdgePointCount": 8, "requiresFinitePositiveCircle": True}
    elif source == "line_endpoint_template_edge":
        detector_path = "line_endpoint_template_edge"
        conditions = {"templateFallbackStillCoreValid": True}
    elif source == "linestrip_template":
        detector_path = "linestrip_template"
        conditions = {"templateFallbackStillCoreValid": True}
    else:
        detector_path = "core_unspecified"
        conditions = {}
    return {
        "detectorPath": detector_path,
        "fixedConditions": conditions,
        "observed": dict(fields),
    }


def extract_feature_quality(
    measurements: Mapping[str, Any], required_feature_labels: set[str]
) -> dict[str, dict[str, Any]]:
    labels = sorted({key[: -len(MEASUREMENT_VALID_SUFFIX)] for key in measurements if key.endswith(MEASUREMENT_VALID_SUFFIX)})
    output: dict[str, dict[str, Any]] = {}
    for label in labels:
        quality_prefix = f"{label}.quality."
        fields = {
            key[len(quality_prefix):]: value
            for key, value in measurements.items()
            if key.startswith(quality_prefix)
        }
        source = measurements.get(f"{label}.detect.source")
        reason = measurements.get(f"{label}.quality.anomaly_reason")
        canonical_label = canonical_feature_label(label)
        localization_required = label in required_feature_labels or canonical_label in required_feature_labels
        status: dict[str, Any] = {
            "feature": label,
            "canonicalFeature": canonical_label,
            "classification": "localization_required" if localization_required else "feature_measurement",
            "coreValid": _core_valid(measurements.get(f"{label}{MEASUREMENT_VALID_SUFFIX}")),
            "source": str(source) if source not in (None, "") else None,
            "reason": str(reason) if reason not in (None, "") else None,
            "fields": fields,
        }
        status["diagnostic"] = diagnose_core_quality(status)
        output[label] = status
    return output


def _check(check_id: str, passed: bool, rule: Any, observed: Any) -> dict[str, Any]:
    return {"id": check_id, "passed": bool(passed), "required": True, "rule": rule, "observed": observed}


def evaluate_quality(
    measurements: Mapping[str, Any],
    shift_method: str,
    image_size: tuple[int, int],
    policy: Mapping[str, Any],
    policy_path: Path | None = None,
) -> dict[str, Any]:
    validate_quality_policy(policy)
    localization = policy["localization"]
    required_labels = set(localization["requiredFeatureLabels"])
    features = extract_feature_quality(measurements, required_labels)
    checks: list[dict[str, Any]] = []

    required_metrics = list(localization["requiredFiniteMetrics"])
    finite_observed = {name: measurements.get(name) for name in required_metrics}
    checks.append(_check(
        "finite_transform",
        all(_finite_number(value) is not None for value in finite_observed.values()),
        {"requiredMetrics": required_metrics},
        finite_observed,
    ))

    scale = _finite_number(measurements.get("transform.scale"))
    scale_min, scale_max = map(float, localization["scaleRange"])
    checks.append(_check(
        "scale_range",
        scale is not None and scale_min <= scale <= scale_max,
        {"minimum": scale_min, "maximum": scale_max, "inclusive": True},
        scale,
    ))

    width, height = image_size
    margin = float(localization["centerMarginPx"])
    center_x = _finite_number(measurements.get("transform.target_center_x_px"))
    center_y = _finite_number(measurements.get("transform.target_center_y_px"))
    center_valid = (
        center_x is not None and center_y is not None and width > 0 and height > 0
        and -margin <= center_x < width + margin and -margin <= center_y < height + margin
    )
    checks.append(_check(
        "center_in_image",
        center_valid,
        {"width": width, "height": height, "marginPx": margin},
        {"x": center_x, "y": center_y},
    ))

    prefixes = list(localization["allowedMethodPrefixes"])
    checks.append(_check(
        "method_prefix",
        any(shift_method.startswith(prefix) for prefix in prefixes),
        {"allowedPrefixes": prefixes},
        shift_method,
    ))

    rotation_match = re.search(r"rotation_score=([-+0-9.eE]+)", shift_method)
    notch_match = re.search(r"prom=([-+0-9.eE]+)", shift_method)
    observed_rotation_score = _finite_number(rotation_match.group(1)) if rotation_match else None
    observed_notch_prominence = _finite_number(notch_match.group(1)) if notch_match else None
    orientation_policy = localization["orientationEvidence"]
    minimum_rotation_score = float(orientation_policy["minimumRotationScore"])
    minimum_notch_prominence = float(orientation_policy["minimumNotchProminence"])
    orientation_valid = (
        observed_rotation_score is not None and observed_rotation_score >= minimum_rotation_score
    ) or (
        observed_notch_prominence is not None and observed_notch_prominence >= minimum_notch_prominence
    )
    checks.append(_check(
        "orientation_evidence",
        orientation_valid,
        {
            "anyOf": {
                "minimumRotationScore": minimum_rotation_score,
                "minimumNotchProminence": minimum_notch_prominence,
            }
        },
        {
            "rotationScore": observed_rotation_score,
            "notchProminence": observed_notch_prominence,
        },
    ))

    for label in sorted(required_labels):
        matching = [
            feature for raw_label, feature in features.items()
            if raw_label == label or feature["canonicalFeature"] == label
        ]
        passed = bool(matching) and all(feature["coreValid"] for feature in matching)
        checks.append(_check(
            f"required_feature:{label}",
            passed,
            {"coreMeasurementValidRequired": True},
            None if not matching else {feature["feature"]: feature["coreValid"] for feature in matching},
        ))

    failed_checks = [item["id"] for item in checks if not item["passed"]]
    invalid_features = [label for label, status in features.items() if not status["coreValid"]]
    total = len(features)
    invalid_count = len(invalid_features)
    quality = {
        "localization": {
            "valid": not failed_checks,
            "policyId": policy["policyId"],
            "policySha256": policy_sha256(policy),
            "policyPath": str(policy_path.resolve()) if policy_path is not None else None,
            "checks": checks,
            "failedChecks": failed_checks,
        },
        "measurementCompleteness": {
            "allValid": total > 0 and invalid_count == 0,
            "total": total,
            "validCount": total - invalid_count,
            "invalidCount": invalid_count,
            "invalidFeatures": invalid_features,
        },
        "featureQuality": features,
    }
    return quality
