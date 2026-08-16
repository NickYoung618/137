"""Default-off two-capture candidate matching for one physical housing.

This module consumes existing single-frame result payloads.  It deliberately
does not perform circle or groove detection itself.
"""

from __future__ import annotations

import copy
import json
import math
import re
from pathlib import Path
from typing import Any


PAIRED_RESULT_SCHEMA_VERSION = "paired-slot-pose-result/1"
PAIRED_MANIFEST_SCHEMA_VERSION = "paired-capture-manifest/1"
PAIRED_CONFIG_SCHEMA_VERSION = "paired-slot-pose-config/1"
ANGLE_CONVENTION_ID = "image-x-right-y-down-clockwise/1"

DEFAULT_PAIRED_CONFIG: dict[str, Any] = {
    "schemaVersion": PAIRED_CONFIG_SCHEMA_VERSION,
    "enabled": False,
    "thresholdVersion": "paired-capture-match-v1",
    "maxCandidatesPerFrame": 16,
    "maxMatchResidualDeg": 2.0,
    "minMatchMarginDeg": 1.0,
    "minDiscriminatingRotationDeg": 5.0,
    "maxHalfWidthNormalizedDifference": 0.60,
    "maxProminenceNormalizedDifference": 0.60,
    "maxDeficitAreaNormalizedDifference": 0.60,
    "maxProfileNormalizedMae": 0.40,
    "target": {
        "targetAngleDeg": 85.0,
        "toleranceDeg": 5.0,
        "acceptedMinDeg": 80.0,
        "acceptedMaxDeg": 90.0,
        "datumRay": "positive_y_down",
        "positiveDirection": "clockwise",
    },
}

_CONFIG_FIELDS = set(DEFAULT_PAIRED_CONFIG)
_TARGET_FIELDS = set(DEFAULT_PAIRED_CONFIG["target"])


def _finite(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise ValueError(f"{name} must be a finite number")
    return float(value)


def wrap_360(value: float) -> float:
    result = float(value) % 360.0
    return 0.0 if abs(result) < 1e-12 else result


def wrap_180(value: float) -> float:
    result = (float(value) + 180.0) % 360.0 - 180.0
    return 0.0 if abs(result) < 1e-12 else result


def _normalized_difference(first: Any, second: Any) -> float | None:
    if first is None or second is None:
        return None
    a, b = _finite(first, "candidate feature"), _finite(second, "candidate feature")
    return abs(a - b) / max(abs(a), abs(b), 1e-9)


def validate_paired_config(config: dict[str, Any]) -> None:
    if not isinstance(config, dict):
        raise ValueError("paired config must be an object")
    missing, unknown = sorted(_CONFIG_FIELDS - set(config)), sorted(set(config) - _CONFIG_FIELDS)
    if missing:
        raise ValueError(f"paired config missing fields: {missing}")
    if unknown:
        raise ValueError(f"paired config has unknown fields: {unknown}")
    if config["schemaVersion"] != PAIRED_CONFIG_SCHEMA_VERSION:
        raise ValueError("unsupported paired config schemaVersion")
    if not isinstance(config["enabled"], bool):
        raise ValueError("paired config enabled must be boolean")
    if not isinstance(config["thresholdVersion"], str) or not config["thresholdVersion"].strip():
        raise ValueError("thresholdVersion must be non-empty")
    count = config["maxCandidatesPerFrame"]
    if isinstance(count, bool) or not isinstance(count, int) or not 1 <= count <= 64:
        raise ValueError("maxCandidatesPerFrame must be an integer in [1,64]")
    for name in (
        "maxMatchResidualDeg", "minMatchMarginDeg", "minDiscriminatingRotationDeg",
    ):
        value = _finite(config[name], name)
        if not 0.0 < value <= 180.0:
            raise ValueError(f"{name} must be in (0,180]")
    for name in (
        "maxHalfWidthNormalizedDifference", "maxProminenceNormalizedDifference",
        "maxDeficitAreaNormalizedDifference", "maxProfileNormalizedMae",
    ):
        value = _finite(config[name], name)
        if not 0.0 <= value <= 1.0:
            raise ValueError(f"{name} must be in [0,1]")
    target = config["target"]
    if not isinstance(target, dict) or set(target) != _TARGET_FIELDS:
        raise ValueError("paired config target fields are invalid")
    if target != DEFAULT_PAIRED_CONFIG["target"]:
        raise ValueError("paired config target must preserve the confirmed 85deg +/-5deg contract")


def load_paired_config(path: Path) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8"))
    validate_paired_config(config)
    return config


def _validate_sha(value: Any, name: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise ValueError(f"{name} must be a lowercase SHA-256")
    return value


def _is_safe_relative_path(value: str) -> bool:
    """Use platform-independent path rules for portable A2 manifests."""
    if value.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:[\\/]", value):
        return False
    return ".." not in re.split(r"[\\/]", value)


def validate_paired_manifest(manifest: dict[str, Any]) -> None:
    if not isinstance(manifest, dict) or manifest.get("schemaVersion") != PAIRED_MANIFEST_SCHEMA_VERSION:
        raise ValueError("unsupported paired manifest schemaVersion")
    unknown_manifest = sorted(set(manifest) - {"schemaVersion", "datasetId", "pairs"})
    if unknown_manifest:
        raise ValueError(f"paired manifest has unknown fields: {unknown_manifest}")
    if not isinstance(manifest.get("datasetId"), str) or not manifest["datasetId"].strip():
        raise ValueError("paired manifest datasetId is required")
    pairs = manifest.get("pairs")
    if not isinstance(pairs, list) or not pairs:
        raise ValueError("paired manifest pairs must be a non-empty array")
    seen_pairs: set[str] = set()
    seen_paths: set[str] = set()
    seen_shas: set[str] = set()
    for pair in pairs:
        if not isinstance(pair, dict):
            raise ValueError("paired manifest pair must be an object")
        unknown_pair = sorted(set(pair) - {"sampleId", "pairId", "rotation", "captures"})
        if unknown_pair:
            raise ValueError(f"paired manifest pair has unknown fields: {unknown_pair}")
        sample_id, pair_id = pair.get("sampleId"), pair.get("pairId")
        if not isinstance(sample_id, str) or not sample_id or not isinstance(pair_id, str) or not pair_id:
            raise ValueError("sampleId and pairId are required")
        if pair_id in seen_pairs:
            raise ValueError(f"duplicate pairId: {pair_id}")
        seen_pairs.add(pair_id)
        captures = pair.get("captures")
        if not isinstance(captures, list) or len(captures) != 2:
            raise ValueError(f"pair {pair_id} must contain exactly two captures")
        indices = [capture.get("captureIndex") for capture in captures if isinstance(capture, dict)]
        if sorted(indices) != [1, 2]:
            raise ValueError(f"pair {pair_id} captureIndex must be exactly 1 and 2")
        for capture in captures:
            unknown_capture = sorted(set(capture) - {
                "captureIndex", "relativePath", "imageSha256", "captureTimestamp",
            })
            if unknown_capture:
                raise ValueError(f"paired manifest capture has unknown fields: {unknown_capture}")
            relative = capture.get("relativePath")
            if (
                not isinstance(relative, str) or not relative
                or Path(relative).is_absolute() or not _is_safe_relative_path(relative)
            ):
                raise ValueError(f"pair {pair_id} relativePath must be safe and relative")
            sha = _validate_sha(capture.get("imageSha256"), "imageSha256")
            if relative in seen_paths or sha in seen_shas:
                raise ValueError("capture paths and SHA-256 values must be unique across pairs")
            seen_paths.add(relative)
            seen_shas.add(sha)
        rotation = pair.get("rotation")
        if not isinstance(rotation, dict):
            raise ValueError(f"pair {pair_id} rotation is required")
        unknown_rotation = sorted(set(rotation) - {
            "parameterStatus", "nominalRotationDeg", "rotationDirection",
            "rotationToleranceDeg", "conventionId",
        })
        if unknown_rotation:
            raise ValueError(f"paired manifest rotation has unknown fields: {unknown_rotation}")
        if rotation.get("conventionId") != ANGLE_CONVENTION_ID:
            raise ValueError(f"pair {pair_id} rotation convention is unsupported")
        status = rotation.get("parameterStatus")
        if status not in {"CONFIRMED", "UNCONFIRMED"}:
            raise ValueError(f"pair {pair_id} parameterStatus is invalid")
        magnitude, direction, tolerance = (
            rotation.get("nominalRotationDeg"), rotation.get("rotationDirection"),
            rotation.get("rotationToleranceDeg"),
        )
        if status == "CONFIRMED" and (magnitude is None or direction is None or tolerance is None):
            raise ValueError(f"pair {pair_id} CONFIRMED rotation requires all values")
        if magnitude is not None and not 0.0 <= _finite(magnitude, "nominalRotationDeg") < 360.0:
            raise ValueError("nominalRotationDeg must be in [0,360)")
        if direction is not None and direction not in {"CLOCKWISE", "COUNTERCLOCKWISE"}:
            raise ValueError("rotationDirection is invalid")
        if tolerance is not None and not 0.0 <= _finite(tolerance, "rotationToleranceDeg") <= 30.0:
            raise ValueError("rotationToleranceDeg must be in [0,30]")


def extract_frame_candidates(payload: dict[str, Any], capture_index: int) -> list[dict[str, Any]]:
    diagnostics = payload.get("diagnostics") if isinstance(payload, dict) else None
    diagnostics = diagnostics if isinstance(diagnostics, dict) else {}
    raw = diagnostics.get("rawCandidates")
    if not isinstance(raw, list):
        raw = diagnostics.get("candidates") if isinstance(diagnostics.get("candidates"), list) else []
    assessments = {
        str(item.get("candidateId")): item
        for item in ((diagnostics.get("grooveRecognition") or {}).get("assessments") or [])
        if isinstance(item, dict) and item.get("candidateId") is not None
    }
    groove_by_id = {
        str(item.get("candidateId")): item
        for item in (diagnostics.get("grooveCandidates") or [])
        if isinstance(item, dict) and item.get("candidateId") is not None
    }
    accepted_ids = set(groove_by_id)
    pose = diagnostics.get("singleGroovePose") or {}
    pose_candidate_id = str((pose.get("role") or {}).get("candidateId") or "")
    pose_angle = (pose.get("imageMeasurement") or {}).get("profileAzimuthXRightClockwiseDeg")
    refinement = diagnostics.get("grooveRefinement")
    source_consistency = diagnostics.get("grooveSourceConsistency")
    fixture_profiles = {
        str(item.get("candidateId")): item.get("normalizedIntensityProfile")
        for item in ((diagnostics.get("fixtureShadowEvidence") or {}).get("matches") or [])
        if isinstance(item, dict) and isinstance(item.get("normalizedIntensityProfile"), list)
    }
    output: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            continue
        candidate_id = str(item.get("candidateId") or f"candidate-{index + 1:03d}")
        if candidate_id in seen:
            raise ValueError(f"duplicate candidateId in capture {capture_index}: {candidate_id}")
        seen.add(candidate_id)
        raw_angle = _finite(item.get("centerDeg"), f"candidate {candidate_id} centerDeg")
        angle, angle_source = raw_angle, "raw_dark_center"
        groove = groove_by_id.get(candidate_id) or {}
        refined_start, refined_end = groove.get("refinedStartDeg"), groove.get("refinedEndDeg")
        if refined_start is not None and refined_end is not None:
            start = _finite(refined_start, "refinedStartDeg") % 360.0
            span = (_finite(refined_end, "refinedEndDeg") - start) % 360.0
            if 0.0 < span < 180.0:
                angle, angle_source = wrap_360(start + span / 2.0), "refined_opening_midpoint"
        if candidate_id == pose_candidate_id and pose_angle is not None:
            angle = _finite(pose_angle, "singleGroovePose image angle")
            angle_source = "single_groove_subpixel_measurement"
        assessment = assessments.get(candidate_id) or {}
        accepted = candidate_id in accepted_ids or assessment.get("accepted") is True
        reasons = list(assessment.get("rejectionReasons") or [])
        nested_refinement = (groove_by_id.get(candidate_id) or {}).get("grooveRefinement")
        candidate_refinement = nested_refinement if isinstance(nested_refinement, dict) else None
        if (
            candidate_refinement is None and accepted and isinstance(refinement, dict)
            and (len(accepted_ids) == 1 or candidate_id == pose_candidate_id)
        ):
            candidate_refinement = refinement
        candidate_source = source_consistency if accepted and isinstance(source_consistency, dict) else None
        geometry_usable = bool(
            candidate_id == pose_candidate_id and pose.get("geometryValid") is True
        ) or bool(
            candidate_refinement is not None and candidate_refinement.get("status") == "accepted"
        )
        if candidate_refinement is not None and candidate_refinement.get("status") not in {None, "accepted"}:
            reasons.append("refinement_not_accepted")
        if candidate_source is not None and candidate_source.get("status") == "rejected":
            geometry_usable = False
            reasons.append("source_consistency_rejected")
        if accepted and not geometry_usable:
            reasons.append("subpixel_geometry_not_available")
        profile = fixture_profiles.get(candidate_id)
        if profile is None and candidate_refinement is not None:
            sides = []
            for side_name in ("startSide", "endSide"):
                values = (((candidate_refinement.get(side_name) or {}).get("profileEvidence") or {})
                          .get("normalizedCanonicalGrayProfile"))
                if isinstance(values, list):
                    sides.extend(values)
            profile = sides or None
        output.append({
            "captureIndex": capture_index,
            "candidateId": candidate_id,
            "imageProfileAngleDeg": wrap_360(angle),
            "rawImageProfileAngleDeg": wrap_360(raw_angle),
            "angleSource": angle_source,
            "halfWidthDeg": item.get("halfWidthDeg"),
            "prominence": item.get("prominence"),
            "deficitArea": item.get("deficitArea"),
            "grooveScore": assessment.get("grooveScore"),
            "usable": bool(accepted and geometry_usable),
            "rejectionReasons": list(dict.fromkeys(map(str, reasons))),
            "rawCandidate": copy.deepcopy(item),
            "grooveAssessment": copy.deepcopy(assessment) if assessment else None,
            "refinement": copy.deepcopy(candidate_refinement),
            "sourceConsistency": copy.deepcopy(candidate_source),
            "normalizedProfile": copy.deepcopy(profile),
        })
    return output


def _rotation_signed(rotation: dict[str, Any]) -> float | None:
    magnitude, direction = rotation.get("nominalRotationDeg"), rotation.get("rotationDirection")
    if magnitude is None or direction is None:
        return None
    value = _finite(magnitude, "nominalRotationDeg")
    return value if direction == "CLOCKWISE" else -value


def _failure_base(pair: dict[str, Any], frames: list[dict[str, Any]], status: str, code: str) -> dict[str, Any]:
    return {
        "schemaVersion": PAIRED_RESULT_SCHEMA_VERSION,
        "sampleId": pair["sampleId"], "pairId": pair["pairId"],
        "status": status, "valid": False,
        "error": {"code": code, "stage": "paired_capture", "message": code},
        "captures": frames, "hypotheses": [], "selectedMatch": None,
        "matchMarginDeg": None, "partRelativeGrooveAngleDeg": None,
        "currentImageProfileAngleDeg": None, "currentAngleDeg": None,
        "targetAngleDeg": 85.0, "toleranceDeg": 5.0,
        "correctionRawDeg": None, "correctionDeg": None,
        "rotationDirection": None, "withinTolerance": None,
        "measurementSource": None,
        "plcExecution": {
            "status": "NOT_AUTHORIZED", "authoritative": False,
            "mechanicalCorrectionDeg": None, "plcCommand": None,
            "blockers": ["PLC_MAPPING_NOT_IN_PAIRED_CONTRACT"],
        },
    }


def _hypotheses(
    first: list[dict[str, Any]], second: list[dict[str, Any]], signed_rotation: float,
    tolerance: float, config: dict[str, Any], *, authoritative: bool,
) -> list[dict[str, Any]]:
    output = []
    for left in first:
        for right in second:
            normalized = wrap_360(right["imageProfileAngleDeg"] - signed_rotation)
            residual = abs(wrap_180(normalized - left["imageProfileAngleDeg"]))
            width = _normalized_difference(left.get("halfWidthDeg"), right.get("halfWidthDeg"))
            prominence = _normalized_difference(left.get("prominence"), right.get("prominence"))
            deficit = _normalized_difference(left.get("deficitArea"), right.get("deficitArea"))
            left_profile, right_profile = left.get("normalizedProfile"), right.get("normalizedProfile")
            profile_mae = None
            if (
                isinstance(left_profile, list) and isinstance(right_profile, list)
                and len(left_profile) == len(right_profile) and len(left_profile) >= 3
            ):
                profile_mae = sum(
                    abs(_finite(a, "profile") - _finite(b, "profile"))
                    for a, b in zip(left_profile, right_profile)
                ) / len(left_profile)
            failed = []
            if residual > float(config["maxMatchResidualDeg"]) + tolerance:
                failed.append("angular_residual")
            for value, threshold, name in (
                (width, config["maxHalfWidthNormalizedDifference"], "half_width_difference"),
                (prominence, config["maxProminenceNormalizedDifference"], "prominence_difference"),
                (deficit, config["maxDeficitAreaNormalizedDifference"], "deficit_area_difference"),
                (profile_mae, config["maxProfileNormalizedMae"], "profile_difference"),
            ):
                if value is not None and value > float(threshold):
                    failed.append(name)
            shape_penalty = sum(
                value for value in (width, prominence, deficit, profile_mae) if value is not None
            )
            output.append({
                "hypothesisId": f"{left['candidateId']}::{right['candidateId']}",
                "firstCandidateId": left["candidateId"],
                "secondCandidateId": right["candidateId"],
                "secondAngleInFirstPartFrameDeg": normalized,
                "rotationSignedDeg": signed_rotation,
                "angularResidualDeg": residual,
                "halfWidthNormalizedDifference": width,
                "prominenceNormalizedDifference": prominence,
                "deficitAreaNormalizedDifference": deficit,
                "profileNormalizedMae": profile_mae,
                "score": residual + shape_penalty,
                "firstUsable": left["usable"], "secondUsable": right["usable"],
                "passed": not failed, "failedChecks": failed,
                "authoritative": authoritative,
            })
    output.sort(key=lambda item: (item["score"], item["hypothesisId"]))
    return output


def build_paired_result(
    pair: dict[str, Any], first_payload: dict[str, Any], second_payload: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, Any]:
    validate_paired_config(config)
    capture_by_index = {item["captureIndex"]: item for item in pair["captures"]}
    first_candidates = extract_frame_candidates(first_payload, 1)
    second_candidates = extract_frame_candidates(second_payload, 2)
    frames = [
        {
            "captureIndex": index,
            "relativePath": capture_by_index[index]["relativePath"],
            "imageSha256": capture_by_index[index]["imageSha256"],
            "singleFrameSchemaVersion": payload.get("schemaVersion"),
            "singleFrameValid": bool((payload.get("result") or {}).get("valid", False)),
            "singleFrameErrorCode": (payload.get("error") or {}).get("code"),
            "candidates": candidates,
        }
        for index, payload, candidates in (
            (1, first_payload, first_candidates), (2, second_payload, second_candidates),
        )
    ]
    if any(payload.get("schemaVersion") not in {"slot-pose-result/2", "slot-pose-result/3"}
           for payload in (first_payload, second_payload)):
        return _failure_base(pair, frames, "FAILED", "PAIR_INPUT_INVALID")
    for index, payload in ((1, first_payload), (2, second_payload)):
        actual = (payload.get("image") or {}).get("sha256")
        if actual != capture_by_index[index]["imageSha256"]:
            return _failure_base(pair, frames, "FAILED", "PAIR_INPUT_INVALID")
    if not config["enabled"]:
        return _failure_base(pair, frames, "EXPERIMENT_DISABLED", "PAIR_EXPERIMENT_DISABLED")
    limit = int(config["maxCandidatesPerFrame"])
    if len(first_candidates) > limit or len(second_candidates) > limit:
        return _failure_base(pair, frames, "FAILED", "PAIR_CANDIDATE_LIMIT")
    rotation = pair["rotation"]
    signed = _rotation_signed(rotation)
    provisional = rotation["parameterStatus"] != "CONFIRMED"
    result = _failure_base(
        pair, frames, "DIAGNOSTIC_ONLY" if provisional else "FAILED",
        "PAIR_PARAMETERS_UNCONFIRMED" if provisional else "PAIR_MATCH_NOT_FOUND",
    )
    if signed is None:
        return result
    rotation_distance = min(abs(signed) % 360.0, 360.0 - abs(signed) % 360.0)
    if rotation_distance < float(config["minDiscriminatingRotationDeg"]):
        result["status"] = "FAILED" if not provisional else "DIAGNOSTIC_ONLY"
        result["error"]["code"] = "PAIR_ROTATION_NOT_DISCRIMINATING"
        result["error"]["message"] = "PAIR_ROTATION_NOT_DISCRIMINATING"
        return result
    tolerance = float(rotation.get("rotationToleranceDeg") or 0.0)
    hypotheses = _hypotheses(
        first_candidates, second_candidates, signed, tolerance, config,
        authoritative=not provisional,
    )
    result["hypotheses"] = hypotheses
    if provisional:
        return result
    passing = [item for item in hypotheses if item["passed"]]
    if not passing:
        return result
    best = passing[0]
    second_score = passing[1]["score"] if len(passing) > 1 else math.inf
    margin = second_score - best["score"]
    result["matchMarginDeg"] = None if not math.isfinite(margin) else margin
    if len(passing) > 1 and margin < float(config["minMatchMarginDeg"]):
        result["error"]["code"] = "PAIR_MATCH_AMBIGUOUS"
        result["error"]["message"] = "PAIR_MATCH_AMBIGUOUS"
        return result
    if not best["firstUsable"] and not best["secondUsable"]:
        result["error"]["code"] = "PAIR_NO_UNOBSTRUCTED_MEASUREMENT"
        result["error"]["message"] = "PAIR_NO_UNOBSTRUCTED_MEASUREMENT"
        return result
    first = next(item for item in first_candidates if item["candidateId"] == best["firstCandidateId"])
    second = next(item for item in second_candidates if item["candidateId"] == best["secondCandidateId"])
    if second["usable"]:
        part_angle = best["secondAngleInFirstPartFrameDeg"]
        current_profile = second["imageProfileAngleDeg"]
        source = "CAPTURE_2_DIRECT"
    else:
        part_angle = first["imageProfileAngleDeg"]
        current_profile = wrap_360(part_angle + signed)
        source = "CAPTURE_1_PROPAGATED"
    current_angle = wrap_180(current_profile - 90.0)
    correction_raw = wrap_180(85.0 - current_angle)
    within = 80.0 <= current_angle <= 90.0
    correction = 0.0 if within else correction_raw
    direction = "NONE" if within else ("CLOCKWISE" if correction > 0.0 else "COUNTERCLOCKWISE")
    result.update({
        "status": "DETECTED", "valid": True, "error": None,
        "selectedMatch": best, "partRelativeGrooveAngleDeg": part_angle,
        "currentImageProfileAngleDeg": current_profile, "currentAngleDeg": current_angle,
        "correctionRawDeg": correction_raw, "correctionDeg": correction,
        "rotationDirection": direction, "withinTolerance": within,
        "measurementSource": source,
    })
    return result
