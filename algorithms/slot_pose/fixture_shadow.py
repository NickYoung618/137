"""Non-destructive fixed-fixture shadow evidence and bounded overlap hypotheses."""

from __future__ import annotations

import copy
import math
import statistics
from typing import Any, Iterable

import numpy as np

from algorithms.slot_pose.angular_profile import circular_distance_deg, wrap_360_deg


TEMPLATE_KEYS = {
    "template_id", "center_deg", "max_center_drift_deg", "half_width_deg",
    "max_half_width_delta_deg", "prominence_reference",
    "max_prominence_normalized_difference", "deficit_area_reference",
    "max_deficit_normalized_difference", "intensity_profile", "gradient_profile",
    "template_source", "human_verified",
}

DEFAULT_FIXTURE_SHADOW_CONFIG: dict[str, Any] = {
    "schema_version": "fixture-shadow-model/1",
    "enabled": False,
    "coordinate_frame_id": "image-x-right-y-down-clockwise/1",
    "threshold_version": "fixture-shadow-evidence-v1",
    "profile_sample_count": 33,
    "profile_window_half_width_deg": 16.0,
    "pair_max_prominence_normalized_difference": 0.35,
    "pair_max_deficit_normalized_difference": 0.45,
    "pair_max_profile_mae": 0.30,
    "enable_overlap_decomposition": False,
    "max_overlap_hypotheses": 4,
    "min_residual_level": 0.18,
    "min_residual_width_deg": 1.0,
    "residual_dedup_center_deg": 2.0,
    "templates": [
        {
            "template_id": "fixture-shadow-a",
            "center_deg": 31.394,
            "max_center_drift_deg": 3.0,
            "half_width_deg": 10.875,
            "max_half_width_delta_deg": 4.0,
            "prominence_reference": 103.329,
            "max_prominence_normalized_difference": 0.60,
            "deficit_area_reference": 311.221,
            "max_deficit_normalized_difference": 1.0,
            "intensity_profile": [],
            "gradient_profile": [],
            "template_source": "historical-json-diagnostic-not-human-truth",
            "human_verified": False,
        },
        {
            "template_id": "fixture-shadow-b",
            "center_deg": 327.746,
            "max_center_drift_deg": 3.0,
            "half_width_deg": 11.125,
            "max_half_width_delta_deg": 4.0,
            "prominence_reference": 98.866,
            "max_prominence_normalized_difference": 0.60,
            "deficit_area_reference": 277.711,
            "max_deficit_normalized_difference": 1.0,
            "intensity_profile": [],
            "gradient_profile": [],
            "template_source": "historical-json-diagnostic-not-human-truth",
            "human_verified": False,
        },
    ],
}


def _finite_number(value: Any, name: str, *, positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"fixture_shadow_model.{name} must be a finite number")
    result = float(value)
    if not math.isfinite(result) or (positive and result <= 0.0):
        qualifier = "positive finite" if positive else "finite"
        raise ValueError(f"fixture_shadow_model.{name} must be {qualifier}")
    return result


def validate_fixture_shadow_config(config: dict[str, Any]) -> None:
    if not isinstance(config, dict):
        raise ValueError("detector.fixture_shadow_model must be an object")
    required = set(DEFAULT_FIXTURE_SHADOW_CONFIG)
    missing = sorted(required - set(config))
    unknown = sorted(set(config) - required)
    if missing:
        raise ValueError(f"fixture_shadow_model missing fields: {missing}")
    if unknown:
        raise ValueError(f"fixture_shadow_model has unknown fields: {unknown}")
    if config["schema_version"] != "fixture-shadow-model/1":
        raise ValueError("fixture_shadow_model.schema_version is unsupported")
    if config["coordinate_frame_id"] != "image-x-right-y-down-clockwise/1":
        raise ValueError("fixture_shadow_model.coordinate_frame_id is unsupported")
    if not isinstance(config["threshold_version"], str) or not config["threshold_version"].strip():
        raise ValueError("fixture_shadow_model.threshold_version must be non-empty")
    for key in ("enabled", "enable_overlap_decomposition"):
        if not isinstance(config[key], bool):
            raise ValueError(f"fixture_shadow_model.{key} must be boolean")
    sample_count = config["profile_sample_count"]
    if isinstance(sample_count, bool) or not isinstance(sample_count, int) or sample_count < 9 or sample_count > 129 or sample_count % 2 == 0:
        raise ValueError("fixture_shadow_model.profile_sample_count must be odd in [9,129]")
    for key in (
        "profile_window_half_width_deg", "pair_max_prominence_normalized_difference",
        "pair_max_deficit_normalized_difference", "pair_max_profile_mae",
        "min_residual_level", "min_residual_width_deg", "residual_dedup_center_deg",
    ):
        value = _finite_number(config[key], key, positive=True)
        if "normalized" in key or key in {"pair_max_profile_mae", "min_residual_level"}:
            if value > 1.0:
                raise ValueError(f"fixture_shadow_model.{key} must be in (0,1]")
    maximum = config["max_overlap_hypotheses"]
    if isinstance(maximum, bool) or not isinstance(maximum, int) or not 1 <= maximum <= 8:
        raise ValueError("fixture_shadow_model.max_overlap_hypotheses must be in [1,8]")
    templates = config["templates"]
    if not isinstance(templates, list) or len(templates) != 2:
        raise ValueError("fixture_shadow_model.templates must contain exactly two templates")
    identifiers: set[str] = set()
    reference_states: list[bool] = []
    for index, template in enumerate(templates):
        if not isinstance(template, dict):
            raise ValueError("fixture_shadow_model template must be an object")
        missing_template = sorted(TEMPLATE_KEYS - set(template))
        unknown_template = sorted(set(template) - TEMPLATE_KEYS)
        if missing_template or unknown_template:
            raise ValueError(
                f"fixture_shadow_model.templates[{index}] fields invalid: "
                f"missing={missing_template} unknown={unknown_template}"
            )
        identifier = template["template_id"]
        if not isinstance(identifier, str) or not identifier or identifier in identifiers:
            raise ValueError("fixture_shadow_model template_id must be unique and non-empty")
        identifiers.add(identifier)
        center = _finite_number(template["center_deg"], f"templates[{index}].center_deg")
        if not 0.0 <= center < 360.0:
            raise ValueError("fixture_shadow_model template center_deg must be in [0,360)")
        for key in (
            "max_center_drift_deg", "half_width_deg", "max_half_width_delta_deg",
            "prominence_reference", "max_prominence_normalized_difference",
            "deficit_area_reference", "max_deficit_normalized_difference",
        ):
            value = _finite_number(template[key], f"templates[{index}].{key}", positive=True)
            if key.startswith("max_") and "normalized" in key and value > 2.0:
                raise ValueError(f"fixture_shadow_model template {key} is unbounded")
        if not isinstance(template["template_source"], str) or not template["template_source"]:
            raise ValueError("fixture_shadow_model template_source must be non-empty")
        if not isinstance(template["human_verified"], bool):
            raise ValueError("fixture_shadow_model human_verified must be boolean")
        intensity = template["intensity_profile"]
        gradient = template["gradient_profile"]
        if not isinstance(intensity, list) or not isinstance(gradient, list):
            raise ValueError("fixture_shadow_model profile arrays must be lists")
        has_reference = bool(intensity or gradient)
        if has_reference and (
            len(intensity) != sample_count or len(gradient) != sample_count
            or not all(isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))
                       for value in intensity + gradient)
        ):
            raise ValueError("fixture_shadow_model reference profile length/content is invalid")
        if bool(intensity) != bool(gradient):
            raise ValueError("fixture_shadow_model intensity and gradient profiles must be provided together")
        reference_states.append(has_reference)
    if config["enable_overlap_decomposition"] and not all(reference_states):
        raise ValueError("fixture_shadow_model overlap decomposition requires both reference profiles")
    if config["enable_overlap_decomposition"] and not all(
        bool(item["human_verified"]) for item in templates
    ):
        raise ValueError("fixture_shadow_model overlap decomposition requires human-verified templates")


def merged_fixture_shadow_config(config: dict[str, Any] | None) -> dict[str, Any]:
    if config is not None and not isinstance(config, dict):
        raise ValueError("detector.fixture_shadow_model must be an object")
    merged = copy.deepcopy(DEFAULT_FIXTURE_SHADOW_CONFIG)
    if config:
        for key, value in config.items():
            merged[key] = copy.deepcopy(value)
    validate_fixture_shadow_config(merged)
    return merged


def _circular_samples(profile: np.ndarray, center_deg: float, half_width_deg: float, count: int) -> np.ndarray:
    offsets = np.linspace(-half_width_deg, half_width_deg, count, dtype=float)
    positions = (center_deg + offsets) % 360.0
    indices = positions * profile.size / 360.0
    lower = np.floor(indices).astype(int) % profile.size
    upper = (lower + 1) % profile.size
    fraction = indices - np.floor(indices)
    return profile[lower] * (1.0 - fraction) + profile[upper] * fraction


def _normalize(values: np.ndarray) -> np.ndarray:
    array = np.asarray(values, dtype=float)
    low, high = float(np.min(array)), float(np.max(array))
    if high - low <= 1e-9:
        return np.zeros_like(array)
    return (array - low) / (high - low)


def _normalized_difference(value: float, reference: float) -> float:
    return abs(float(value) - float(reference)) / max(abs(float(reference)), 1e-9)


def _profile_evidence(profile: np.ndarray, candidate: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    raw = _circular_samples(
        profile, float(candidate["centerDeg"]),
        float(config["profile_window_half_width_deg"]), int(config["profile_sample_count"]),
    )
    normalized = _normalize(raw)
    gradient = np.gradient(normalized)
    return {
        "rawIntensityProfile": [float(value) for value in raw],
        "normalizedIntensityProfile": [float(value) for value in normalized],
        "normalizedGradientProfile": [float(value) for value in gradient],
    }


def _mae(first: Iterable[float], second: Iterable[float]) -> float:
    left, right = np.asarray(list(first), dtype=float), np.asarray(list(second), dtype=float)
    if left.shape != right.shape or left.size == 0:
        return math.inf
    return float(np.mean(np.abs(left - right)))


def _correlation(first: Iterable[float], second: Iterable[float]) -> float | None:
    left, right = np.asarray(list(first), dtype=float), np.asarray(list(second), dtype=float)
    if left.shape != right.shape or left.size == 0:
        return None
    left = left - float(np.mean(left))
    right = right - float(np.mean(right))
    denominator = float(np.linalg.norm(left) * np.linalg.norm(right))
    if denominator <= 1e-12:
        return 1.0 if float(np.max(np.abs(left - right))) <= 1e-12 else 0.0
    return float(np.dot(left, right) / denominator)


def _match_candidate(
    candidate: dict[str, Any], template: dict[str, Any],
    profile_evidence: dict[str, Any], config: dict[str, Any],
) -> dict[str, Any]:
    center_distance = circular_distance_deg(float(candidate["centerDeg"]), float(template["center_deg"]))
    width_difference = abs(float(candidate["halfWidthDeg"]) - float(template["half_width_deg"]))
    prominence_difference = _normalized_difference(
        float(candidate["prominence"]), float(template["prominence_reference"])
    )
    deficit_difference = _normalized_difference(
        float(candidate["deficitArea"]), float(template["deficit_area_reference"])
    )
    checks = {
        "center_drift": center_distance <= float(template["max_center_drift_deg"]),
        "half_width": width_difference <= float(template["max_half_width_delta_deg"]),
        "prominence": prominence_difference <= float(template["max_prominence_normalized_difference"]),
        "deficit_area": deficit_difference <= float(template["max_deficit_normalized_difference"]),
    }
    intensity_reference = template["intensity_profile"]
    gradient_reference = template["gradient_profile"]
    intensity_mae = (
        _mae(profile_evidence["normalizedIntensityProfile"], intensity_reference)
        if intensity_reference else None
    )
    gradient_mae = (
        _mae(profile_evidence["normalizedGradientProfile"], gradient_reference)
        if gradient_reference else None
    )
    intensity_correlation = (
        _correlation(profile_evidence["normalizedIntensityProfile"], intensity_reference)
        if intensity_reference else None
    )
    gradient_correlation = (
        _correlation(profile_evidence["normalizedGradientProfile"], gradient_reference)
        if gradient_reference else None
    )
    if intensity_reference:
        maximum_profile_mae = float(config["pair_max_profile_mae"])
        checks["intensity_profile"] = bool(intensity_mae is not None and intensity_mae <= maximum_profile_mae)
        checks["gradient_profile"] = bool(gradient_mae is not None and gradient_mae <= maximum_profile_mae)
    margins = [
        1.0 - center_distance / float(template["max_center_drift_deg"]),
        1.0 - width_difference / float(template["max_half_width_delta_deg"]),
        1.0 - prominence_difference / float(template["max_prominence_normalized_difference"]),
        1.0 - deficit_difference / float(template["max_deficit_normalized_difference"]),
    ]
    if intensity_reference:
        margins.extend([
            1.0 - float(intensity_mae) / float(config["pair_max_profile_mae"]),
            1.0 - float(gradient_mae) / float(config["pair_max_profile_mae"]),
        ])
    failed = [key for key, passed in checks.items() if not passed]
    return {
        "candidateId": str(candidate["candidateId"]),
        "templateId": str(template["template_id"]),
        "status": "matched" if not failed else "not_matched",
        "centerDistanceDeg": float(center_distance),
        "widthDifferenceDeg": float(width_difference),
        "prominenceNormalizedDifference": float(prominence_difference),
        "deficitNormalizedDifference": float(deficit_difference),
        "intensityProfileMae": intensity_mae,
        "gradientProfileMae": gradient_mae,
        "intensityProfileCorrelation": intensity_correlation,
        "gradientProfileCorrelation": gradient_correlation,
        "profileReferenceAvailable": bool(intensity_reference),
        "checks": checks,
        "passedChecks": [key for key, passed in checks.items() if passed],
        "matchScore": float(max(0.0, min(1.0, statistics.fmean(margins)))),
        "failedChecks": failed,
        **profile_evidence,
    }


def _pair_evidence(matches: list[dict[str, Any]], candidates: dict[str, dict[str, Any]],
                   config: dict[str, Any]) -> dict[str, Any]:
    template_ids = [str(item["template_id"]) for item in config["templates"]]
    choices = {
        template_id: [
            match for match in matches
            if match["templateId"] == template_id and match["status"] == "matched"
        ]
        for template_id in template_ids
    }
    combinations = [
        (first, second)
        for first in choices[template_ids[0]]
        for second in choices[template_ids[1]]
        if first["candidateId"] != second["candidateId"]
    ]
    if not combinations:
        return {
            "status": "incomplete", "selectedCandidateIds": None,
            "candidatePairCount": 0, "failedChecks": ["fixture_pair_incomplete"],
        }
    ranked = sorted(
        combinations,
        key=lambda pair: (-(pair[0]["matchScore"] + pair[1]["matchScore"]),
                          pair[0]["candidateId"], pair[1]["candidateId"]),
    )
    if len(ranked) > 1 and abs(
        sum(item["matchScore"] for item in ranked[0])
        - sum(item["matchScore"] for item in ranked[1])
    ) <= 1e-9:
        return {
            "status": "ambiguous", "selectedCandidateIds": None,
            "candidatePairCount": len(ranked), "failedChecks": ["fixture_pair_ambiguous"],
        }
    selected = ranked[0]
    first, second = (candidates[item["candidateId"]] for item in selected)
    prominence_ratio = min(float(first["prominence"]), float(second["prominence"])) / max(
        float(first["prominence"]), float(second["prominence"]), 1e-9
    )
    deficit_ratio = min(float(first["deficitArea"]), float(second["deficitArea"])) / max(
        float(first["deficitArea"]), float(second["deficitArea"]), 1e-9
    )
    profile_mae = _mae(
        selected[0]["normalizedIntensityProfile"], selected[1]["normalizedIntensityProfile"]
    )
    gradient_mae = _mae(
        selected[0]["normalizedGradientProfile"], selected[1]["normalizedGradientProfile"]
    )
    failed = []
    if 1.0 - prominence_ratio > float(config["pair_max_prominence_normalized_difference"]):
        failed.append("fixture_pair_prominence_dissimilar")
    if 1.0 - deficit_ratio > float(config["pair_max_deficit_normalized_difference"]):
        failed.append("fixture_pair_deficit_dissimilar")
    if profile_mae > float(config["pair_max_profile_mae"]):
        failed.append("fixture_pair_profile_dissimilar")
    if gradient_mae > float(config["pair_max_profile_mae"]):
        failed.append("fixture_pair_gradient_dissimilar")
    return {
        "status": "complete" if not failed else "inconsistent",
        "selectedCandidateIds": [item["candidateId"] for item in selected],
        "candidatePairCount": len(ranked),
        "pairProminenceRatio": float(prominence_ratio),
        "pairDeficitRatio": float(deficit_ratio),
        "pairIntensityProfileMae": profile_mae,
        "pairGradientProfileMae": gradient_mae,
        "failedChecks": failed,
    }


def _runs(mask: np.ndarray) -> list[tuple[int, int]]:
    result: list[tuple[int, int]] = []
    start: int | None = None
    for index, flag in enumerate(mask.tolist() + [False]):
        if flag and start is None:
            start = index
        elif not flag and start is not None:
            result.append((start, index - 1))
            start = None
    return result


def _overlap_hypotheses(
    matches: list[dict[str, Any]], candidates: dict[str, dict[str, Any]],
    config: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if not config["enable_overlap_decomposition"]:
        return {"status": "disabled", "hypothesisCount": 0, "hypotheses": []}, []
    hypotheses: list[dict[str, Any]] = []
    residual_candidates: list[dict[str, Any]] = []
    half_window = float(config["profile_window_half_width_deg"])
    count = int(config["profile_sample_count"])
    step = 2.0 * half_window / max(1, count - 1)
    templates = {str(item["template_id"]): item for item in config["templates"]}
    for match in matches:
        if match["status"] != "matched" or not match["profileReferenceAvailable"]:
            continue
        template = templates[match["templateId"]]
        observed = np.asarray(match["normalizedIntensityProfile"], dtype=float)
        predicted = np.asarray(template["intensity_profile"], dtype=float)
        residual = np.maximum(0.0, predicted - observed)
        for low, high in _runs(residual >= float(config["min_residual_level"])):
            width = (high - low + 1) * step
            if width < float(config["min_residual_width_deg"]):
                continue
            source = candidates[match["candidateId"]]
            start = wrap_360_deg(float(source["centerDeg"]) - half_window + (low - 0.5) * step)
            end = wrap_360_deg(float(source["centerDeg"]) - half_window + (high + 0.5) * step)
            center = wrap_360_deg(float(source["centerDeg"]) - half_window + (low + high) * 0.5 * step)
            identifier = f"residual-{len(hypotheses) + 1:03d}"
            record = {
                "hypothesisId": identifier,
                "sourceCandidateId": match["candidateId"],
                "templateId": match["templateId"],
                "modelKind": "fixture_plus_groove_residual",
                "residualStartDeg": start, "residualEndDeg": end,
                "residualCenterDeg": center, "residualWidthDeg": width,
                "residualArea": float(np.sum(residual[low:high + 1]) * step),
                "observedProfile": observed.tolist(),
                "predictedFixtureProfile": predicted.tolist(),
                "residualProfile": residual.tolist(),
            }
            hypotheses.append(record)
            residual_candidates.append({
                "candidateId": identifier,
                "centerDeg": center,
                "halfWidthDeg": width / 2.0,
                "startDeg": start, "endDeg": end,
                "wrapsBoundary": start > end,
                "prominence": float(np.max(residual[low:high + 1]) * 255.0),
                "deficitArea": record["residualArea"] * 255.0,
                "rank": len(residual_candidates) + 1,
                "hypothesisSource": record,
            })
            if len(hypotheses) > int(config["max_overlap_hypotheses"]):
                return {
                    "status": "overflow", "hypothesisCount": len(hypotheses),
                    "hypotheses": hypotheses, "failedChecks": ["overlap_hypothesis_limit"],
                }, []
    distinct: list[dict[str, Any]] = []
    distinct_records: list[dict[str, Any]] = []
    for item, record in sorted(zip(residual_candidates, hypotheses), key=lambda pair: pair[0]["centerDeg"]):
        if any(
            circular_distance_deg(float(item["centerDeg"]), float(existing["centerDeg"]))
            <= float(config["residual_dedup_center_deg"])
            for existing in distinct
        ):
            continue
        distinct.append(item)
        distinct_records.append(record)
    status = "none" if not distinct else ("unique" if len(distinct) == 1 else "ambiguous")
    return {
        "status": status, "hypothesisCount": len(distinct_records),
        "hypotheses": distinct_records,
        "failedChecks": [] if status == "unique" else [f"overlap_{status}"],
    }, distinct if status == "unique" else []


def analyze_fixture_shadows(
    angular_profile: np.ndarray,
    candidates: Iterable[dict[str, Any]],
    config: dict[str, Any] | None,
) -> dict[str, Any]:
    merged = merged_fixture_shadow_config(config)
    items = [dict(item) for item in candidates]
    raw_ids = [str(item["candidateId"]) for item in items]
    base = {
        "schemaVersion": "fixture-shadow-evidence/1",
        "thresholdVersion": merged["threshold_version"],
        "enabled": bool(merged["enabled"]),
        "coordinateFrameId": merged["coordinate_frame_id"],
        "rawCandidateCount": len(items),
        "rawCandidateIds": raw_ids,
        "candidateSuppressionApplied": False,
        "suppressedCandidateIds": [],
    }
    if not merged["enabled"]:
        return {
            **base, "status": "disabled", "candidateMatches": [],
            "pairEvidence": {"status": "disabled", "selectedCandidateIds": None},
            "overlapDecomposition": {"status": "disabled", "hypothesisCount": 0, "hypotheses": []},
            "residualCandidates": [],
        }
    profile = np.asarray(angular_profile, dtype=float)
    if profile.ndim != 1 or profile.size < 36 or not np.isfinite(profile).all():
        raise ValueError("fixture shadow angular profile must be finite 1D data")
    by_id = {str(item["candidateId"]): item for item in items}
    profiles = {identifier: _profile_evidence(profile, item, merged) for identifier, item in by_id.items()}
    matches = [
        _match_candidate(candidate, template, profiles[str(candidate["candidateId"])], merged)
        for candidate in items for template in merged["templates"]
    ]
    pair = _pair_evidence(matches, by_id, merged)
    if merged["enable_overlap_decomposition"] and pair["status"] != "complete":
        overlap, residual = ({
            "status": "template_incomplete",
            "hypothesisCount": 0,
            "hypotheses": [],
            "failedChecks": ["fixture_pair_not_complete"],
        }, [])
    else:
        overlap, residual = _overlap_hypotheses(matches, by_id, merged)
    return {
        **base,
        "status": "evaluated",
        "templateHumanVerified": all(bool(item["human_verified"]) for item in merged["templates"]),
        "candidateMatches": matches,
        "pairEvidence": pair,
        "overlapDecomposition": overlap,
        "residualCandidates": residual,
    }


def build_fixture_overlap_evaluation_candidates(
    raw_candidates: Iterable[dict[str, Any]],
    fixture_evidence: dict[str, Any],
) -> dict[str, Any]:
    """Replace only a uniquely decomposed merged interval in the evaluation view.

    Raw candidates remain untouched and auditable.  The replacement is driven by
    a unique residual model, never by a fixed angle or template match alone.
    """
    raw = [dict(item) for item in raw_candidates]
    residual = [dict(item) for item in fixture_evidence.get("residualCandidates") or []]
    overlap = fixture_evidence.get("overlapDecomposition") or {}
    if overlap.get("status") != "unique" or len(residual) != 1:
        return {
            "candidates": raw,
            "replacementApplied": False,
            "replacedSourceCandidateIds": [],
            "replacementCandidateIds": [],
        }
    source_id = str((residual[0].get("hypothesisSource") or {}).get("sourceCandidateId") or "")
    raw_ids = {str(item.get("candidateId")) for item in raw}
    if not source_id or source_id not in raw_ids:
        return {
            "candidates": raw,
            "replacementApplied": False,
            "replacedSourceCandidateIds": [],
            "replacementCandidateIds": [],
        }
    evaluation = [item for item in raw if str(item.get("candidateId")) != source_id]
    evaluation.extend(residual)
    return {
        "candidates": evaluation,
        "replacementApplied": True,
        "replacedSourceCandidateIds": [source_id],
        "replacementCandidateIds": [str(residual[0]["candidateId"])],
    }
