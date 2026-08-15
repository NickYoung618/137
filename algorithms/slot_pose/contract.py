"""Stable v2 output contract and angle semantics for A-face slot pose."""

from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tools.dataset_common import inspect_image


SCHEMA_VERSION = "slot-pose-result/2"
ALGORITHM_NAME = "legacy-a-end-face-slot-pose-adapter"
ALGORITHM_VERSION = "0.9.0"
ERROR_CODES = {
    "INPUT_INVALID",
    "ASSET_MISMATCH",
    "FACE_NOT_FOUND",
    "SLOT_NOT_FOUND",
    "SLOT_ROTATION_INCONSISTENT",
    "SLOT_FIT_FAILED",
    "SLOT_PAIR_NOT_FOUND",
    "SLOT_PAIR_AMBIGUOUS",
    "ROLE_ASSIGNMENT_FAILED",
    "ROLE_ASSIGNMENT_AMBIGUOUS",
    "GROOVE_RECOGNITION_FAILED",
    "GROOVE_RECOGNITION_AMBIGUOUS",
    "GROOVE_REFINEMENT_FAILED",
    "PHYSICAL_OUTER_CIRCLE_FAILED",
    "RING_TRUNCATED",
    "QUALITY_REJECTED",
    "TARGET_SEMANTICS_UNCONFIRMED",
    "DATUM_DEFINITION_UNCONFIRMED",
    "FEATURE_MAPPING_UNCONFIRMED",
    "OUTPUT_PURPOSE_UNCONFIRMED",
    "PLC_MAPPING_UNCONFIRMED",
    "POSE_CONVENTION_UNCONFIRMED",
    "ANGLE_OUT_OF_RANGE",
    "INTERNAL_ERROR",
}


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def config_sha256(config_path: Path) -> str:
    return sha256_file(config_path)


def load_config(config_path: Path) -> dict[str, Any]:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if config.get("schema_version") != "slot-pose-config/1":
        raise ValueError("unsupported slot-pose config schema_version")
    if config.get("project") != "137-housing-slot-pose":
        raise ValueError("configuration is not a slot-pose project config")
    for key in ("config_id", "legacy_asset", "pose", "detector"):
        if key not in config:
            raise ValueError(f"configuration field is required: {key}")
    pose = config["pose"]
    if not isinstance(pose, dict):
        raise ValueError("pose configuration must be an object")
    pose.setdefault("target_semantics_confirmed", False)
    detector = config["detector"]
    if not isinstance(detector, dict):
        raise ValueError("detector configuration must be an object")
    mode = detector.setdefault("diagnostic_mode", "legacy_single_notch")
    if mode not in {
        "legacy_single_notch", "paired_notches_centerline", "multi_notch_roles", "single_real_groove",
    }:
        raise ValueError(f"unsupported detector.diagnostic_mode: {mode!r}")
    face_roi = detector.get("face_search_roi_normalized")
    if face_roi is not None:
        if (
            not isinstance(face_roi, list)
            or len(face_roi) != 4
            or any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in face_roi)
            or not all(math.isfinite(float(value)) for value in face_roi)
        ):
            raise ValueError("detector.face_search_roi_normalized must be [x_min,y_min,x_max,y_max]")
        x_min, y_min, x_max, y_max = map(float, face_roi)
        if not (0.0 <= x_min < x_max <= 1.0 and 0.0 <= y_min < y_max <= 1.0):
            raise ValueError("detector.face_search_roi_normalized must be ordered within [0,1]")
    if mode == "paired_notches_centerline":
        from algorithms.slot_pose.angular_profile import validate_pairing_config, validate_profile_config

        if not isinstance(detector.get("profile"), dict) or not isinstance(detector.get("pairing"), dict):
            raise ValueError("paired mode requires detector.profile and detector.pairing objects")
        validate_profile_config(detector["profile"])
        validate_pairing_config(detector["pairing"])
        disagreement = detector.get("max_polar_pair_disagreement_deg")
        if not isinstance(disagreement, (int, float)) or not 0.0 < float(disagreement) <= 180.0:
            raise ValueError("max_polar_pair_disagreement_deg must be in (0, 180]")
    if mode in {"multi_notch_roles", "single_real_groove"}:
        from algorithms.slot_pose.angular_profile import validate_profile_config
        from algorithms.slot_pose.groove_recognition import merged_groove_config
        from algorithms.slot_pose.physical_outer_circle import merged_physical_outer_circle_config

        if not isinstance(detector.get("profile"), dict):
            raise ValueError(f"{mode} mode requires detector.profile")
        validate_profile_config(detector["profile"])
        detector["groove_recognition"] = merged_groove_config(detector.get("groove_recognition"))
        detector["physical_outer_circle"] = merged_physical_outer_circle_config(
            detector.get("physical_outer_circle")
        )
    if mode == "multi_notch_roles":
        from algorithms.slot_pose.role_assignment import validate_role_config

        if not isinstance(detector.get("role_assignment"), dict):
            raise ValueError("multi-role mode requires detector.role_assignment")
        validate_role_config(detector["role_assignment"])
    if mode == "single_real_groove":
        from algorithms.slot_pose.single_groove_pose import merged_single_groove_pose_config

        detector["single_groove_pose"] = merged_single_groove_pose_config(
            detector.get("single_groove_pose")
        )
        if detector["single_groove_pose"]["schema_version"] == "single-real-groove-pose-config/2":
            from algorithms.slot_pose.groove_refinement import merged_groove_refinement_config

            detector["groove_refinement"] = merged_groove_refinement_config(
                detector.get("groove_refinement")
            )
    return config


def wrap_angle_deg(value: float) -> float:
    wrapped = (float(value) + 180.0) % 360.0 - 180.0
    return 0.0 if abs(wrapped) < 1e-12 else wrapped


def signed_relative_angle(candidate_image_deg: float, zero_image_deg: float, positive_direction: str) -> float:
    """Map image azimuth (clockwise-positive because y grows down) to machine sign."""
    delta_clockwise = wrap_angle_deg(candidate_image_deg - zero_image_deg)
    if positive_direction == "cw":
        return delta_clockwise
    if positive_direction == "ccw":
        return wrap_angle_deg(-delta_clockwise)
    raise ValueError("positive_direction must be 'cw' or 'ccw'")


def build_result(
    image_path: Path,
    config_path: Path,
    config: dict[str, Any],
    task_id: str | None,
    diagnostics: dict[str, Any],
    *,
    angle_deg: float | None = None,
    confidence: float | None = None,
    error_code: str | None = None,
    error_message: str | None = None,
    error_stage: str | None = None,
) -> dict[str, Any]:
    image_path = image_path.resolve()
    image = inspect_image(image_path)
    task_id = task_id or f"offline:{image['sha256'][:16]}"
    valid = error_code is None
    pose = config["pose"]
    if valid and not bool(pose.get("conventions_confirmed", False)):
        raise ValueError("valid pose requires confirmed mechanical conventions")
    if valid and not bool(pose.get("target_semantics_confirmed", False)):
        raise ValueError("valid pose requires confirmed target semantics")
    if not valid:
        angle_deg = None
        confidence = None
    assets = config["legacy_asset"]
    payload = {
        "schemaVersion": SCHEMA_VERSION,
        "taskId": task_id,
        "createdAtUtc": datetime.now(timezone.utc).isoformat(),
        "image": {"path": str(image_path), **image},
        "algorithm": {
            "name": ALGORITHM_NAME,
            "version": ALGORITHM_VERSION,
            "configSha256": config_sha256(config_path),
            "configId": config["config_id"],
            "assets": {
                "sourceSha256": assets["source_sha256"],
                "annotationSha256": assets["annotation_sha256"],
                "referenceSha256": assets["reference_sha256"],
            },
        },
        "result": {
            "signedRelativeRotationDeg": angle_deg,
            "unit": "deg",
            "confidence": confidence,
            "valid": valid,
            "referenceFrame": pose["reference_frame"],
            "targetFrame": pose["target_frame"],
            "positiveDirection": pose.get("positive_direction"),
        },
        "technicalStatus": "succeeded" if valid else "failed",
        "error": None if valid else {
            "code": error_code,
            "message": error_message or error_code,
            "stage": error_stage or "unknown",
        },
        "diagnostics": {
            **diagnostics,
            "poseConventionsConfirmed": bool(pose.get("conventions_confirmed", False)),
            "targetSemanticsConfirmed": bool(pose.get("target_semantics_confirmed", False)),
            "drawingDatumDefinitionConfirmed": bool(pose.get("drawing_datum_definition_confirmed", False)),
            "a2DrawingFeatureMappingConfirmed": bool(pose.get("a2_drawing_feature_mapping_confirmed", False)),
            "outputPurpose": pose.get("output_purpose"),
            "productionPlcMappingConfirmed": bool(pose.get("production_plc_mapping_confirmed", False)),
            "failClosed": True,
        },
    }
    validate_result(payload)
    return payload


def validate_result(payload: dict[str, Any]) -> None:
    if payload.get("schemaVersion") != SCHEMA_VERSION:
        raise ValueError("invalid slot pose schemaVersion")
    if not payload.get("taskId") or not payload.get("createdAtUtc"):
        raise ValueError("taskId and createdAtUtc are required")
    result = payload.get("result", {})
    valid = result.get("valid")
    angle = result.get("signedRelativeRotationDeg")
    confidence = result.get("confidence")
    error = payload.get("error")
    if result.get("unit") != "deg":
        raise ValueError("slot pose angle unit must be deg")
    if valid is True:
        if not isinstance(angle, (int, float)) or not -180.0 <= float(angle) < 180.0:
            raise ValueError("valid pose requires angle in [-180, 180)")
        if not isinstance(confidence, (int, float)) or not 0.0 <= float(confidence) <= 1.0:
            raise ValueError("valid pose requires confidence in [0, 1]")
        if payload.get("technicalStatus") != "succeeded" or error is not None:
            raise ValueError("valid pose requires succeeded status and null error")
    elif valid is False:
        if angle is not None or confidence is not None:
            raise ValueError("invalid pose must not carry angle or confidence")
        if payload.get("technicalStatus") != "failed" or not isinstance(error, dict):
            raise ValueError("invalid pose requires failed status and error")
        if error.get("code") not in ERROR_CODES or not error.get("stage"):
            raise ValueError("invalid pose requires stable error code and stage")
    else:
        raise ValueError("result.valid must be boolean")
