"""Stable JSON contract for one-image A-end-face inspection."""

from __future__ import annotations

import hashlib
import math
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from algorithms.end_face import CORE_SOURCE_SHA256


SCHEMA_VERSION = "a-end-face-result/1"
ALGORITHM_NAME = "desktop-a-end-face-core"
ALGORITHM_VERSION = "1.0.0"


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


def invalid_features(measurements: Mapping[str, Any]) -> list[str]:
    suffix = ".quality.measurement_valid"
    invalid: list[str] = []
    for key, value in measurements.items():
        if not key.endswith(suffix):
            continue
        try:
            valid = float(value) > 0.5
        except (TypeError, ValueError):
            valid = False
        if not valid:
            invalid.append(key[: -len(suffix)])
    return sorted(invalid)


def success_result(
    *,
    task_id: str,
    image: Path,
    annotation: Path,
    reference: Path,
    pixel_size: float,
    shift_method: str,
    measurements: Mapping[str, Any],
) -> dict[str, Any]:
    rejected = invalid_features(measurements)
    valid = not rejected
    payload = {
        "schemaVersion": SCHEMA_VERSION,
        "taskId": task_id,
        "technicalStatus": "succeeded",
        "input": {
            "image": {"path": str(image.resolve()), "sha256": sha256_file(image)},
            "annotation": {"path": str(annotation.resolve()), "sha256": sha256_file(annotation)},
            "reference": {"path": str(reference.resolve()), "sha256": sha256_file(reference)},
        },
        "algorithm": {
            "name": ALGORITHM_NAME,
            "version": ALGORITHM_VERSION,
            "coreSourceSha256": CORE_SOURCE_SHA256,
        },
        "result": {
            "valid": valid,
            "pixelSize": pixel_size,
            "shiftMethod": shift_method,
            "invalidFeatures": rejected,
            "measurements": json_safe(measurements),
        },
        "error": None,
    }
    validate_result(payload)
    return payload


def failure_result(*, task_id: str, image: Path, annotation: Path, error: Exception) -> dict[str, Any]:
    payload = {
        "schemaVersion": SCHEMA_VERSION,
        "taskId": task_id,
        "technicalStatus": "failed",
        "input": {
            "image": {"path": str(image.resolve())},
            "annotation": {"path": str(annotation.resolve())},
        },
        "algorithm": {
            "name": ALGORITHM_NAME,
            "version": ALGORITHM_VERSION,
            "coreSourceSha256": CORE_SOURCE_SHA256,
        },
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
    status = payload.get("technicalStatus")
    if status == "succeeded":
        result = payload.get("result")
        if not isinstance(result, Mapping) or payload.get("error") is not None:
            raise ValueError("succeeded result requires result and null error")
        if not isinstance(result.get("valid"), bool) or not isinstance(result.get("measurements"), Mapping):
            raise ValueError("result.valid and result.measurements are required")
    elif status == "failed":
        error = payload.get("error")
        if payload.get("result") is not None or not isinstance(error, Mapping) or not error.get("code"):
            raise ValueError("failed result requires null result and an error code")
    else:
        raise ValueError("technicalStatus must be succeeded or failed")
