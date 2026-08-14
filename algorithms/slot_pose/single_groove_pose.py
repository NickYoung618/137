"""Versioned image-frame pose for exactly one recognized real groove."""

from __future__ import annotations

import math
from typing import Any, Iterable


SINGLE_GROOVE_POSE_SCHEMA_VERSION = "slot-single-real-groove-pose/1"
IMAGE_ANGLE_SCHEMA_VERSION = "slot-groove-image-angle/1"
TARGET_SCHEMA_VERSION = "slot-groove-target/1"
TARGET_ASSESSMENT_SCHEMA_VERSION = "slot-groove-target-assessment/1"
DEFAULT_SINGLE_GROOVE_POSE_CONFIG: dict[str, Any] = {
    "schema_version": "single-real-groove-pose-config/1",
    "output_schema_version": SINGLE_GROOVE_POSE_SCHEMA_VERSION,
    "image_angle_schema_version": IMAGE_ANGLE_SCHEMA_VERSION,
    "expected_accepted_groove_count": 1,
    "target": {
        "schema_version": TARGET_SCHEMA_VERSION,
        "nominal_deg": 85.0,
        "expected_quadrant": "lower_left",
        "physical_datum_definition_id": None,
        "angle_convention_id": None,
    },
}


def _optional_id(value: Any, name: str) -> None:
    if value is not None and (not isinstance(value, str) or not value.strip()):
        raise ValueError(f"single_groove_pose.target.{name} must be null or a non-empty string")


def validate_single_groove_pose_config(config: dict[str, Any]) -> None:
    if not isinstance(config, dict):
        raise ValueError("single_groove_pose must be an object")
    required = set(DEFAULT_SINGLE_GROOVE_POSE_CONFIG)
    missing = sorted(required - set(config))
    if missing:
        raise ValueError(f"single_groove_pose missing fields: {missing}")
    unexpected = sorted(set(config) - required)
    if unexpected:
        raise ValueError(f"single_groove_pose has unsupported fields: {unexpected}")
    if config.get("schema_version") != "single-real-groove-pose-config/1":
        raise ValueError("single_groove_pose.schema_version is unsupported")
    if config.get("output_schema_version") != SINGLE_GROOVE_POSE_SCHEMA_VERSION:
        raise ValueError("single_groove_pose.output_schema_version is unsupported")
    if config.get("image_angle_schema_version") != IMAGE_ANGLE_SCHEMA_VERSION:
        raise ValueError("single_groove_pose.image_angle_schema_version is unsupported")
    if config.get("expected_accepted_groove_count") != 1:
        raise ValueError("single_groove_pose.expected_accepted_groove_count must equal 1")
    target = config.get("target")
    if not isinstance(target, dict):
        raise ValueError("single_groove_pose.target must be an object")
    target_required = {
        "schema_version", "nominal_deg", "expected_quadrant",
        "physical_datum_definition_id", "angle_convention_id",
    }
    missing_target = sorted(target_required - set(target))
    if missing_target:
        raise ValueError(f"single_groove_pose.target missing fields: {missing_target}")
    unexpected_target = sorted(set(target) - target_required)
    if unexpected_target:
        raise ValueError(
            f"single_groove_pose.target has unsupported fields: {unexpected_target}"
        )
    if target.get("schema_version") != TARGET_SCHEMA_VERSION:
        raise ValueError("single_groove_pose.target.schema_version is unsupported")
    nominal = target.get("nominal_deg")
    if (
        isinstance(nominal, bool)
        or not isinstance(nominal, (int, float))
        or not math.isfinite(float(nominal))
        or not 0.0 <= float(nominal) < 360.0
    ):
        raise ValueError("single_groove_pose.target.nominal_deg must be finite in [0,360)")
    if target.get("expected_quadrant") not in {
        "upper_left", "upper_right", "lower_left", "lower_right",
    }:
        raise ValueError("single_groove_pose.target.expected_quadrant is invalid")
    _optional_id(target.get("physical_datum_definition_id"), "physical_datum_definition_id")
    _optional_id(target.get("angle_convention_id"), "angle_convention_id")


def merged_single_groove_pose_config(config: dict[str, Any] | None) -> dict[str, Any]:
    if config is None:
        raise ValueError("single_real_groove mode requires detector.single_groove_pose")
    target = {
        **DEFAULT_SINGLE_GROOVE_POSE_CONFIG["target"],
        **(config.get("target") if isinstance(config.get("target"), dict) else {}),
    }
    merged = {**DEFAULT_SINGLE_GROOVE_POSE_CONFIG, **config, "target": target}
    validate_single_groove_pose_config(merged)
    return merged


def _point(center: tuple[float, float], radius: float, profile_azimuth_deg: float) -> dict[str, float]:
    radians = math.radians(profile_azimuth_deg)
    return {
        "x": center[0] + radius * math.cos(radians),
        "y": center[1] + radius * math.sin(radians),
    }


def _quadrant(point: dict[str, float], center: tuple[float, float], radius: float) -> str:
    tolerance = max(1e-9, radius * 1e-8)
    dx, dy = point["x"] - center[0], point["y"] - center[1]
    horizontal = "right" if dx > tolerance else ("left" if dx < -tolerance else "axis")
    vertical = "lower" if dy > tolerance else ("upper" if dy < -tolerance else "axis")
    if horizontal == "axis":
        return f"{vertical}_axis"
    if vertical == "axis":
        return f"{horizontal}_axis"
    return f"{vertical}_{horizontal}"


def _target_assessment(
    target: dict[str, Any], _measured_quadrant: str | None, geometry_valid: bool,
) -> dict[str, Any]:
    blockers: list[str] = []
    if not geometry_valid:
        blockers.append("GROOVE_GEOMETRY_REJECTED")
    if target.get("physical_datum_definition_id") is None:
        blockers.append("PHYSICAL_DATUM_UNCONFIRMED")
    if target.get("angle_convention_id") is None:
        blockers.append("TARGET_ANGLE_CONVENTION_UNCONFIRMED")
    # A single absolute image bearing is not a datum-to-groove measurement.
    blockers.append("DATUM_RELATIVE_ANGLE_NOT_MEASURED")
    return {
        "schemaVersion": TARGET_ASSESSMENT_SCHEMA_VERSION,
        "targetContract": {
            "schemaVersion": target["schema_version"],
            "nominalDeg": float(target["nominal_deg"]),
            "expectedQuadrant": target["expected_quadrant"],
            "physicalDatumDefinitionId": target.get("physical_datum_definition_id"),
            "angleConventionId": target.get("angle_convention_id"),
        },
        "status": "NOT_EVALUATED",
        # Even a qualitative target comparison needs the image-to-physical
        # target convention.  Keep it unevaluated with the numeric fields.
        "quadrantMatches": None,
        "signedMeasurementMinusTargetDeg": None,
        "absoluteDeviationDeg": None,
        "mechanicalCorrectionDeg": None,
        "blockers": blockers,
    }


def build_single_groove_pose(
    groove_candidates: Iterable[dict[str, Any]],
    center: tuple[float, float],
    outer_radius: float,
    config: dict[str, Any],
    *,
    recognition_status: str,
) -> dict[str, Any]:
    """Build image geometry only; never turn it into a machine correction."""
    merged = merged_single_groove_pose_config(config)
    candidates = list(groove_candidates)
    if (
        len(center) != 2
        or not all(math.isfinite(float(value)) for value in center)
        or not math.isfinite(float(outer_radius))
        or float(outer_radius) <= 0.0
    ):
        raise ValueError("single groove circle geometry is invalid")
    if recognition_status not in {"accepted", "ambiguous", "failed"}:
        raise ValueError("single groove recognition status is invalid")
    if len(candidates) > 1 or recognition_status == "ambiguous":
        status = "ambiguous"
    elif len(candidates) == 1 and recognition_status == "accepted":
        status = "accepted"
    else:
        status = "failed"
    geometry_valid = status == "accepted"
    candidate = candidates[0] if geometry_valid else None
    measurement = None
    quadrant = None
    if candidate is not None:
        profile_azimuth = float(candidate["centerDeg"]) % 360.0
        if not math.isfinite(profile_azimuth):
            raise ValueError("single groove candidate azimuth is invalid")
        image_up_azimuth = (profile_azimuth + 90.0) % 360.0
        circle_point = _point(center, float(outer_radius), profile_azimuth)
        quadrant = _quadrant(circle_point, center, float(outer_radius))
        measurement = {
            "schemaVersion": merged["image_angle_schema_version"],
            "coordinateConvention": {
                "origin": "detected_physical_outer_circle_center",
                "xAxis": "right",
                "yAxis": "down",
                "zeroDirection": "image_up",
                "positiveDirection": "clockwise",
                "rangeDeg": "[0,360)",
            },
            "azimuthDeg": image_up_azimuth,
            "profileAzimuthXRightClockwiseDeg": profile_azimuth,
            "quadrant": quadrant,
            "circlePoint": circle_point,
            "radialAxis": {
                "from": {"x": float(center[0]), "y": float(center[1])},
                "to": circle_point,
            },
        }
    return {
        "schemaVersion": merged["output_schema_version"],
        "status": status,
        "expectedAcceptedGrooveCount": 1,
        "acceptedGrooveCount": len(candidates),
        "geometryValid": geometry_valid,
        "role": {
            "schemaVersion": "single-real-groove-role/1",
            "name": "real_groove",
            "status": "unique_detected" if geometry_valid else status,
            "candidateId": None if candidate is None else str(candidate["candidateId"]),
            "mechanicalGuidanceAuthoritative": False,
        },
        "imageMeasurement": measurement,
        "targetAssessment": _target_assessment(merged["target"], quadrant, geometry_valid),
    }
