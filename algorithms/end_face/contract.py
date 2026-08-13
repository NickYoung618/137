"""Stable v3 JSON contract for one-image A-end-face inspection."""

from __future__ import annotations

import hashlib
import math
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from algorithms.end_face import CORE_SOURCE_SHA256


SCHEMA_VERSION = "a-end-face-result/3"
ALGORITHM_NAME = "desktop-a-end-face-core"
ALGORITHM_VERSION = "1.3.0"


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def json_safe(value: Any) -> Any:
    """Convert detector values to strict JSON values (never NaN/Infinity)."""
    if isinstance(value, Path):
        return str(value)
    if hasattr(value, "item") and callable(value.item):
        return json_safe(value.item())
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, Mapping):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [json_safe(item) for item in value]
    return value


def _algorithm(
    quality: Mapping[str, Any] | None = None,
    candidate_provenance: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    localization = quality.get("localization", {}) if isinstance(quality, Mapping) else {}
    return {
        "name": ALGORITHM_NAME,
        "version": ALGORITHM_VERSION,
        "coreSourceSha256": CORE_SOURCE_SHA256,
        "qualityPolicy": {
            "policyId": localization.get("policyId"),
            "sha256": localization.get("policySha256"),
        },
        "shortLineCandidate": dict(candidate_provenance) if candidate_provenance is not None else None,
    }


def success_result(
    *,
    task_id: str,
    image: Path,
    image_info: Mapping[str, Any],
    annotation: Path,
    reference: Path,
    pixel_size: float,
    shift_method: str,
    measurements: Mapping[str, Any],
    quality: Mapping[str, Any],
    short_line_candidates: Mapping[str, Any] | None = None,
    candidate_provenance: Mapping[str, Any] | None = None,
    elapsed_ms: float,
) -> dict[str, Any]:
    localization = quality["localization"]
    payload = {
        "schemaVersion": SCHEMA_VERSION,
        "taskId": task_id,
        "technicalStatus": "succeeded",
        "execution": {"elapsedMs": elapsed_ms},
        "input": {
            "image": {"path": str(image.resolve()), **dict(image_info)},
            "annotation": {"path": str(annotation.resolve()), "sha256": sha256_file(annotation)},
            "reference": {"path": str(reference.resolve()), "sha256": sha256_file(reference)},
        },
        "algorithm": _algorithm(quality, candidate_provenance),
        "result": {
            "valid": bool(localization["valid"]),
            "pixelSize": pixel_size,
            "shiftMethod": shift_method,
            "localization": quality["localization"],
            "measurementCompleteness": quality["measurementCompleteness"],
            "featureQuality": quality["featureQuality"],
            "measurements": measurements,
            "shortLineCandidates": dict(short_line_candidates or {}),
        },
        "error": None,
    }
    payload = json_safe(payload)
    validate_result(payload)
    return payload


def failure_result(
    *,
    task_id: str,
    image: Path,
    annotation: Path,
    error: Exception,
    elapsed_ms: float = 0.0,
    quality: Mapping[str, Any] | None = None,
    candidate_provenance: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload = {
        "schemaVersion": SCHEMA_VERSION,
        "taskId": task_id,
        "technicalStatus": "failed",
        "execution": {"elapsedMs": max(0.0, float(elapsed_ms))},
        "input": {
            "image": {"path": str(image.resolve())},
            "annotation": {"path": str(annotation.resolve())},
        },
        "algorithm": _algorithm(quality, candidate_provenance),
        "result": None,
        "error": {"code": "DETECTION_FAILED", "message": str(error)},
    }
    validate_result(payload)
    return payload


def validate_result(payload: Mapping[str, Any]) -> None:
    if payload.get("schemaVersion") != SCHEMA_VERSION:
        raise ValueError("unsupported end-face result schema")
    if not payload.get("taskId"):
        raise ValueError("taskId is required")
    execution = payload.get("execution")
    if not isinstance(execution, Mapping) or (elapsed := execution.get("elapsedMs")) is None:
        raise ValueError("execution.elapsedMs is required")
    if not isinstance(elapsed, (int, float)) or isinstance(elapsed, bool) or not math.isfinite(float(elapsed)) or elapsed < 0:
        raise ValueError("execution.elapsedMs must be a finite non-negative number")
    status = payload.get("technicalStatus")
    if status == "succeeded":
        result = payload.get("result")
        if not isinstance(result, Mapping) or payload.get("error") is not None:
            raise ValueError("succeeded result requires result and null error")
        localization = result.get("localization")
        completeness = result.get("measurementCompleteness")
        feature_quality = result.get("featureQuality")
        short_line_candidates = result.get("shortLineCandidates")
        if not isinstance(localization, Mapping) or not isinstance(localization.get("valid"), bool):
            raise ValueError("result.localization.valid is required")
        if result.get("valid") is not localization.get("valid"):
            raise ValueError("result.valid must equal result.localization.valid")
        if not isinstance(completeness, Mapping) or not isinstance(completeness.get("allValid"), bool):
            raise ValueError("result.measurementCompleteness.allValid is required")
        if not isinstance(feature_quality, Mapping) or not isinstance(result.get("measurements"), Mapping):
            raise ValueError("featureQuality and measurements are required")
        if not isinstance(short_line_candidates, Mapping):
            raise ValueError("result.shortLineCandidates is required")
        for label, feature in feature_quality.items():
            if (
                not isinstance(feature, Mapping)
                or feature.get("feature") != label
                or not feature.get("canonicalFeature")
                or not isinstance(feature.get("coreValid"), bool)
            ):
                raise ValueError("each featureQuality item requires matching feature, canonicalFeature and coreValid")
        valid_transitions = {"both_valid", "recovered", "regressed", "both_invalid"}
        for label, comparison in short_line_candidates.items():
            if not isinstance(comparison, Mapping) or comparison.get("feature") != label:
                raise ValueError("each short-line candidate requires a matching feature")
            core_result = comparison.get("core")
            candidate = comparison.get("candidate")
            if not isinstance(core_result, Mapping) or not isinstance(core_result.get("coreValid"), bool):
                raise ValueError("each short-line candidate requires core.coreValid")
            if not isinstance(candidate, Mapping) or not isinstance(candidate.get("candidateValid"), bool):
                raise ValueError("each short-line candidate requires candidate.candidateValid")
            core_valid = core_result["coreValid"]
            candidate_valid = candidate["candidateValid"]
            expected = (
                "both_valid" if core_valid and candidate_valid
                else "recovered" if candidate_valid
                else "regressed" if core_valid
                else "both_invalid"
            )
            if comparison.get("transition") != expected or expected not in valid_transitions:
                raise ValueError("short-line transition must match independent core/candidate states")
    elif status == "failed":
        error = payload.get("error")
        if payload.get("result") is not None or not isinstance(error, Mapping) or not error.get("code"):
            raise ValueError("failed result requires null result and an error code")
    else:
        raise ValueError("technicalStatus must be succeeded or failed")
