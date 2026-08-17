"""Default-off single/180-degree paired image-frame groove guidance."""

from __future__ import annotations

import copy
import math
import re
from pathlib import Path
from typing import Any

from .paired_capture import extract_frame_candidates, wrap_180, wrap_360

REQUEST_VERSION = "half-turn-guidance-request/1"
CONFIG_VERSION = "half-turn-guidance-config/1"
RESULT_VERSION = "half-turn-guidance-result/1"
ANGLE_CONVENTION_ID = "image-x-right-y-down-clockwise/1"

DEFAULT_CONFIG: dict[str, Any] = {
    "schemaVersion": CONFIG_VERSION,
    "enabled": False,
    "developmentOnly": True,
    "authoritative": False,
    "posePromotionAllowed": False,
    "thresholdVersion": "half-turn-pair-match-v1",
    "maxCandidatesPerFrame": 16,
    "maxMatchResidualDeg": 2.0,
    "minMatchMarginDeg": 1.0,
    "maxHalfWidthNormalizedDifference": 0.60,
    "maxProminenceNormalizedDifference": 0.60,
    "maxDeficitAreaNormalizedDifference": 0.60,
    "maxProfileNormalizedMae": 0.40,
    "targetAngleDeg": 85.0,
    "toleranceDeg": 5.0,
}


def _finite(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise ValueError(f"{name} must be finite")
    return float(value)


def wrap_180_prefer_positive(value: float) -> float:
    wrapped = wrap_180(value)
    return 180.0 if abs(wrapped + 180.0) < 1e-12 else wrapped


def _safe_relative(value: Any) -> bool:
    if not isinstance(value, str) or not value or value.startswith(("/", "\\")):
        return False
    if re.match(r"^[A-Za-z]:[\\/]", value):
        return False
    return ".." not in re.split(r"[\\/]", value)


def validate_config(config: dict[str, Any]) -> None:
    if not isinstance(config, dict) or set(config) != set(DEFAULT_CONFIG):
        raise ValueError("half-turn config fields are invalid")
    if config["schemaVersion"] != CONFIG_VERSION:
        raise ValueError("unsupported half-turn config schemaVersion")
    for name in ("enabled", "developmentOnly", "authoritative", "posePromotionAllowed"):
        if not isinstance(config[name], bool):
            raise ValueError(f"{name} must be boolean")
    if config["developmentOnly"] is not True or config["authoritative"] is not False or config["posePromotionAllowed"] is not False:
        raise ValueError("half-turn MVP safety policy cannot be relaxed")
    if not isinstance(config["thresholdVersion"], str) or not config["thresholdVersion"]:
        raise ValueError("thresholdVersion is required")
    count = config["maxCandidatesPerFrame"]
    if isinstance(count, bool) or not isinstance(count, int) or not 1 <= count <= 64:
        raise ValueError("maxCandidatesPerFrame must be in [1,64]")
    for name in ("maxMatchResidualDeg", "minMatchMarginDeg"):
        if not 0.0 < _finite(config[name], name) <= 180.0:
            raise ValueError(f"{name} must be in (0,180]")
    for name in ("maxHalfWidthNormalizedDifference", "maxProminenceNormalizedDifference", "maxDeficitAreaNormalizedDifference", "maxProfileNormalizedMae"):
        if not 0.0 <= _finite(config[name], name) <= 1.0:
            raise ValueError(f"{name} must be in [0,1]")
    if _finite(config["targetAngleDeg"], "targetAngleDeg") != 85.0 or _finite(config["toleranceDeg"], "toleranceDeg") != 5.0:
        raise ValueError("target contract must remain 85deg +/-5deg")


def validate_request_manifest(manifest: dict[str, Any]) -> None:
    if not isinstance(manifest, dict) or manifest.get("schemaVersion") != REQUEST_VERSION:
        raise ValueError("unsupported guidance request schemaVersion")
    if set(manifest) != {"schemaVersion", "datasetId", "requests"}:
        raise ValueError("guidance request manifest fields are invalid")
    if not isinstance(manifest["datasetId"], str) or not manifest["datasetId"]:
        raise ValueError("datasetId is required")
    requests = manifest["requests"]
    if not isinstance(requests, list) or not requests:
        raise ValueError("requests must be a non-empty array")
    seen_requests: set[str] = set()
    seen_shas: set[str] = set()
    for request in requests:
        if not isinstance(request, dict) or set(request) != {"requestId", "sampleId", "mode", "captures", "halfTurn"}:
            raise ValueError("request fields are invalid")
        request_id, sample_id, mode = request["requestId"], request["sampleId"], request["mode"]
        if not isinstance(request_id, str) or not request_id or request_id in seen_requests:
            raise ValueError("requestId must be non-empty and unique")
        seen_requests.add(request_id)
        if not isinstance(sample_id, str) or not sample_id:
            raise ValueError("sampleId is required")
        expected = 1 if mode == "SINGLE_CAPTURE" else 2 if mode == "HALF_TURN_PAIR" else 0
        captures = request["captures"]
        if expected == 0 or not isinstance(captures, list) or len(captures) != expected:
            raise ValueError("mode and capture count are inconsistent")
        if sorted(item.get("captureIndex") for item in captures if isinstance(item, dict)) != list(range(1, expected + 1)):
            raise ValueError("captureIndex sequence is invalid")
        for capture in captures:
            if set(capture) != {"captureIndex", "relativePath", "imageSha256"} or not _safe_relative(capture["relativePath"]):
                raise ValueError("capture path or fields are invalid")
            sha = capture["imageSha256"]
            if not isinstance(sha, str) or not re.fullmatch(r"[0-9a-f]{64}", sha) or sha in seen_shas:
                raise ValueError("imageSha256 must be lowercase and unique")
            seen_shas.add(sha)
        half_turn = request["halfTurn"]
        if mode == "SINGLE_CAPTURE" and half_turn is not None:
            raise ValueError("single capture halfTurn must be null")
        if mode == "HALF_TURN_PAIR":
            expected_half = {
                "nominalRotationDeg": 180.0,
                "directionRequired": False,
                "executionResponsibility": "EXTERNAL_HARDWARE",
                "conventionId": ANGLE_CONVENTION_ID,
            }
            if half_turn != expected_half:
                raise ValueError("half-turn pair requires the direction-independent 180deg contract")


def _error(request: dict[str, Any], code: str, captures: list[dict[str, Any]], hypotheses: list[dict[str, Any]] | None = None, *, status: str = "FAILED") -> dict[str, Any]:
    return {
        "schemaVersion": RESULT_VERSION,
        "requestId": request["requestId"], "sampleId": request["sampleId"], "mode": request["mode"],
        "status": status, "valid": False,
        "detectionStatus": "DETECTION_FAILED", "verificationStatus": "NOT_AVAILABLE", "guidanceStatus": "NOT_AVAILABLE",
        "error": {"code": code, "stage": "half_turn_guidance", "message": code},
        "captures": captures, "hypotheses": hypotheses or [], "selectedMatch": None,
        "measurementSource": None, "currentImageProfileAngleDeg": None, "currentAngleDeg": None,
        "targetAngleDeg": 85.0, "toleranceDeg": 5.0,
        "correctionRawDeg": None, "correctionDeg": None, "rotationDirection": None, "withinTolerance": None,
        "developmentOnly": True, "authoritative": False, "posePromotionAllowed": False,
        "realPairValidationStatus": "NOT_APPLICABLE" if request["mode"] == "SINGLE_CAPTURE" else "MISSING",
        "plcExecution": None,
    }


def _guidance(request: dict[str, Any], captures: list[dict[str, Any]], profile_angle: float, source: str, hypotheses: list[dict[str, Any]], selected: dict[str, Any] | None, verification: str) -> dict[str, Any]:
    current = wrap_180(profile_angle - 90.0)
    raw = wrap_180_prefer_positive(85.0 - current)
    within = 80.0 <= current <= 90.0
    correction = 0.0 if within else raw
    direction = "NONE" if within else ("CLOCKWISE" if correction > 0.0 else "COUNTERCLOCKWISE")
    result = _error(request, "INTERNAL", captures, hypotheses)
    result.update({
        "status": "DETECTED", "valid": True, "detectionStatus": "DETECTED",
        "verificationStatus": verification,
        "guidanceStatus": "DETECTED_IN_POSITION" if within else "DETECTED_NEEDS_ADJUSTMENT",
        "error": None, "selectedMatch": selected, "measurementSource": source,
        "currentImageProfileAngleDeg": wrap_360(profile_angle), "currentAngleDeg": current,
        "correctionRawDeg": raw, "correctionDeg": correction, "rotationDirection": direction,
        "withinTolerance": within,
    })
    return result


def _frame(capture: dict[str, Any], payload: dict[str, Any], index: int) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if payload.get("schemaVersion") not in {"slot-pose-result/2", "slot-pose-result/3"}:
        raise ValueError("unsupported single-frame result")
    if (payload.get("image") or {}).get("sha256") != capture["imageSha256"]:
        raise ValueError("single-frame SHA does not match request")
    candidates = extract_frame_candidates(payload, index)
    diagnostics = payload.get("diagnostics") or {}
    pose = diagnostics.get("singleGroovePose") or {}
    pose_candidate_id = str((pose.get("role") or {}).get("candidateId") or "")
    adjudication = diagnostics.get("sidewallSourceConsistencyAdjudication") or {}
    effective_override = bool(
        (payload.get("result") or {}).get("valid") is True
        and pose.get("geometryValid") is True
        and adjudication.get("schemaVersion") == "source-consistency-adjudication/1"
        and adjudication.get("decision") == "ACCEPTED_OVERRIDE"
        and adjudication.get("effectiveStatus") == "accepted"
        and adjudication.get("imagePoseReleaseAllowed") is True
        and adjudication.get("manualTruthAppliedAtRuntime") is False
    )
    for item in candidates:
        item["effectiveUsabilitySource"] = "ORIGINAL_SINGLE_FRAME_GATES"
        if effective_override and item["candidateId"] == pose_candidate_id:
            item["usable"] = True
            item["effectiveUsabilitySource"] = "VERSIONED_SOURCE_CONSISTENCY_ADJUDICATION"
            item["originalRejectionReasonsRetained"] = list(item.get("rejectionReasons") or [])
    return ({
        "captureIndex": index, "relativePath": capture["relativePath"], "imageSha256": capture["imageSha256"],
        "singleFrameValid": bool((payload.get("result") or {}).get("valid")),
        "singleFrameErrorCode": (payload.get("error") or {}).get("code"), "candidates": copy.deepcopy(candidates),
    }, candidates)


def _normdiff(a: Any, b: Any) -> float | None:
    if a is None or b is None:
        return None
    x, y = _finite(a, "feature"), _finite(b, "feature")
    return abs(x - y) / max(abs(x), abs(y), 1e-9)


def _pair_hypotheses(first: list[dict[str, Any]], second: list[dict[str, Any]], config: dict[str, Any]) -> list[dict[str, Any]]:
    output = []
    for left in first:
        for right in second:
            normalized = wrap_360(right["imageProfileAngleDeg"] - 180.0)
            residual = abs(wrap_180(normalized - left["imageProfileAngleDeg"]))
            evidence = {
                "halfWidthNormalizedDifference": _normdiff(left.get("halfWidthDeg"), right.get("halfWidthDeg")),
                "prominenceNormalizedDifference": _normdiff(left.get("prominence"), right.get("prominence")),
                "deficitAreaNormalizedDifference": _normdiff(left.get("deficitArea"), right.get("deficitArea")),
            }
            left_profile, right_profile = left.get("normalizedProfile"), right.get("normalizedProfile")
            profile_mae = None
            if isinstance(left_profile, list) and isinstance(right_profile, list) and len(left_profile) == len(right_profile) and len(left_profile) >= 3:
                profile_mae = sum(abs(_finite(a, "profile") - _finite(b, "profile")) for a, b in zip(left_profile, right_profile)) / len(left_profile)
            evidence["profileNormalizedMae"] = profile_mae
            failed = []
            if residual > config["maxMatchResidualDeg"]:
                failed.append("angular_residual")
            for field, threshold_field, code in (
                ("halfWidthNormalizedDifference", "maxHalfWidthNormalizedDifference", "half_width_difference"),
                ("prominenceNormalizedDifference", "maxProminenceNormalizedDifference", "prominence_difference"),
                ("deficitAreaNormalizedDifference", "maxDeficitAreaNormalizedDifference", "deficit_area_difference"),
                ("profileNormalizedMae", "maxProfileNormalizedMae", "profile_difference"),
            ):
                if evidence[field] is not None and evidence[field] > config[threshold_field]:
                    failed.append(code)
            score = residual + sum(value for value in evidence.values() if value is not None)
            output.append({
                "hypothesisId": f"{left['candidateId']}::{right['candidateId']}",
                "firstCandidateId": left["candidateId"], "secondCandidateId": right["candidateId"],
                "secondAngleInFirstPartFrameDeg": normalized, "angularResidualDeg": residual,
                **evidence, "score": score, "firstUsable": left["usable"], "secondUsable": right["usable"],
                "passed": not failed, "eligible": not failed and (left["usable"] or right["usable"]),
                "failedChecks": failed,
            })
    return sorted(output, key=lambda item: (item["score"], item["hypothesisId"]))


def build_guidance_result(request: dict[str, Any], payloads_by_sha: dict[str, dict[str, Any]], config: dict[str, Any]) -> dict[str, Any]:
    validate_config(config)
    frames, candidate_sets = [], []
    try:
        for index, capture in enumerate(request["captures"], 1):
            payload = payloads_by_sha.get(capture["imageSha256"])
            if payload is None:
                return _error(request, "INPUT_RESULT_MISSING", frames)
            frame, candidates = _frame(capture, payload, index)
            frames.append(frame); candidate_sets.append(candidates)
    except (ValueError, TypeError, KeyError):
        return _error(request, "INPUT_RESULT_INVALID", frames)
    if not config["enabled"]:
        return _error(request, "EXPERIMENT_DISABLED", frames, status="EXPERIMENT_DISABLED")
    if any(len(items) > config["maxCandidatesPerFrame"] for items in candidate_sets):
        return _error(request, "CANDIDATE_LIMIT_EXCEEDED", frames)
    if request["mode"] == "SINGLE_CAPTURE":
        usable = [item for item in candidate_sets[0] if item["usable"]]
        if len(usable) == 0:
            return _error(request, frames[0].get("singleFrameErrorCode") or "NO_COMPLETE_GROOVE", frames)
        if len(usable) > 1:
            return _error(request, "SINGLE_GROOVE_AMBIGUOUS", frames)
        return _guidance(request, frames, usable[0]["imageProfileAngleDeg"], "SINGLE_CAPTURE_DIRECT", [], None, "SINGLE_FRAME_ONLY")
    hypotheses = _pair_hypotheses(candidate_sets[0], candidate_sets[1], config)
    passing = [item for item in hypotheses if item["passed"]]
    eligible = [item for item in hypotheses if item["eligible"]]
    if not passing:
        return _error(request, "PAIR_EVIDENCE_INCONSISTENT", frames, hypotheses)
    if not eligible:
        return _error(request, "NO_COMPLETE_GROOVE", frames, hypotheses)
    best = eligible[0]
    if len(eligible) > 1 and eligible[1]["score"] - best["score"] < config["minMatchMarginDeg"]:
        return _error(request, "PAIR_MATCH_AMBIGUOUS", frames, hypotheses)
    left = next(item for item in candidate_sets[0] if item["candidateId"] == best["firstCandidateId"])
    right = next(item for item in candidate_sets[1] if item["candidateId"] == best["secondCandidateId"])
    if right["usable"]:
        profile, source = right["imageProfileAngleDeg"], "CAPTURE_2_DIRECT"
    else:
        profile, source = wrap_360(left["imageProfileAngleDeg"] + 180.0), "CAPTURE_1_PROPAGATED_HALF_TURN"
    return _guidance(request, frames, profile, source, hypotheses, best, "PAIR_VERIFIED")


def run_manifest(manifest: dict[str, Any], payloads_by_sha: dict[str, dict[str, Any]], config: dict[str, Any]) -> list[dict[str, Any]]:
    validate_request_manifest(manifest)
    return [build_guidance_result(request, payloads_by_sha, config) for request in manifest["requests"]]
