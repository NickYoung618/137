"""Versioned image-frame pose for exactly one recognized real groove."""

from __future__ import annotations

import copy
import math
from typing import Any, Iterable

from algorithms.slot_pose.angular_profile import wrap_360_deg


SINGLE_GROOVE_POSE_SCHEMA_VERSION = "slot-single-real-groove-pose/1"
SINGLE_GROOVE_POSE_SCHEMA_VERSION_V2 = "slot-single-real-groove-pose/2"
SINGLE_GROOVE_POSE_SCHEMA_VERSION_V3 = "slot-single-real-groove-pose/3"
IMAGE_ANGLE_SCHEMA_VERSION = "slot-groove-image-angle/1"
IMAGE_ANGLE_SCHEMA_VERSION_V2 = "slot-groove-image-angle/2"
Y_DOWN_ANGLE_SCHEMA_VERSION = "slot-groove-y-down-angle/1"
TARGET_SCHEMA_VERSION = "slot-groove-target/1"
TARGET_SCHEMA_VERSION_V2 = "slot-groove-target/2"
TARGET_SCHEMA_VERSION_V3 = "slot-groove-target/3"
TARGET_ASSESSMENT_SCHEMA_VERSION = "slot-groove-target-assessment/1"
TARGET_ASSESSMENT_SCHEMA_VERSION_V2 = "slot-groove-target-assessment/2"
IMAGE_FRAME_GUIDANCE_SCHEMA_VERSION = "slot-image-frame-guidance/1"

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

DEFAULT_SINGLE_GROOVE_POSE_CONFIG_V2: dict[str, Any] = {
    "schema_version": "single-real-groove-pose-config/2",
    "output_schema_version": SINGLE_GROOVE_POSE_SCHEMA_VERSION_V2,
    "image_angle_schema_version": IMAGE_ANGLE_SCHEMA_VERSION_V2,
    "datum_angle_schema_version": Y_DOWN_ANGLE_SCHEMA_VERSION,
    "expected_accepted_groove_count": 1,
    "target": {
        "schema_version": TARGET_SCHEMA_VERSION_V2,
        "nominal_deg": 85.0,
        "tolerance_deg": 5.0,
        "accepted_min_deg": 80.0,
        "accepted_max_deg": 90.0,
        "required_horizontal_position": "left",
        "required_vertical_position": "lower_or_axis",
        "physical_datum_definition_id": "detected-physical-circle-positive-y-down-ray/1",
        "angle_convention_id": "image-y-down-clockwise-signed/1",
    },
}

DEFAULT_SINGLE_GROOVE_POSE_CONFIG_V3: dict[str, Any] = {
    "schema_version": "single-real-groove-pose-config/3",
    "output_schema_version": SINGLE_GROOVE_POSE_SCHEMA_VERSION_V3,
    "image_angle_schema_version": IMAGE_ANGLE_SCHEMA_VERSION_V2,
    "datum_angle_schema_version": Y_DOWN_ANGLE_SCHEMA_VERSION,
    "expected_accepted_groove_count": 1,
    "target": {
        "schema_version": TARGET_SCHEMA_VERSION_V3,
        "nominal_deg": 85.0,
        "tolerance_deg": 5.0,
        "accepted_min_deg": 80.0,
        "accepted_max_deg": 90.0,
        "required_horizontal_position": "left",
        "required_vertical_position": "lower_or_axis",
        "physical_datum_definition_id": "detected-physical-circle-positive-y-down-ray/1",
        "angle_convention_id": "image-y-down-clockwise-signed/1",
    },
}


def _optional_id(value: Any, name: str) -> None:
    if value is not None and (not isinstance(value, str) or not value.strip()):
        raise ValueError(f"single_groove_pose.target.{name} must be null or a non-empty string")


def _finite_number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise ValueError(f"single_groove_pose.target.{name} must be finite")
    return float(value)


def _validate_exact_fields(payload: dict[str, Any], required: set[str], name: str) -> None:
    missing = sorted(required - set(payload))
    unexpected = sorted(set(payload) - required)
    if missing:
        raise ValueError(f"{name} missing fields: {missing}")
    if unexpected:
        raise ValueError(f"{name} has unsupported fields: {unexpected}")


def _validate_v1(config: dict[str, Any]) -> None:
    required = set(DEFAULT_SINGLE_GROOVE_POSE_CONFIG)
    _validate_exact_fields(config, required, "single_groove_pose")
    if config.get("output_schema_version") != SINGLE_GROOVE_POSE_SCHEMA_VERSION:
        raise ValueError("single_groove_pose.output_schema_version is unsupported")
    if config.get("image_angle_schema_version") != IMAGE_ANGLE_SCHEMA_VERSION:
        raise ValueError("single_groove_pose.image_angle_schema_version is unsupported")
    target = config.get("target")
    if not isinstance(target, dict):
        raise ValueError("single_groove_pose.target must be an object")
    fields = {
        "schema_version", "nominal_deg", "expected_quadrant",
        "physical_datum_definition_id", "angle_convention_id",
    }
    _validate_exact_fields(target, fields, "single_groove_pose.target")
    if target.get("schema_version") != TARGET_SCHEMA_VERSION:
        raise ValueError("single_groove_pose.target.schema_version is unsupported")
    nominal = _finite_number(target.get("nominal_deg"), "nominal_deg")
    if not 0.0 <= nominal < 360.0:
        raise ValueError("single_groove_pose.target.nominal_deg must be in [0,360)")
    if target.get("expected_quadrant") not in {
        "upper_left", "upper_right", "lower_left", "lower_right",
    }:
        raise ValueError("single_groove_pose.target.expected_quadrant is invalid")
    _optional_id(target.get("physical_datum_definition_id"), "physical_datum_definition_id")
    _optional_id(target.get("angle_convention_id"), "angle_convention_id")


def _validate_refined_guidance_config(config: dict[str, Any], *, version: int) -> None:
    default = (
        DEFAULT_SINGLE_GROOVE_POSE_CONFIG_V2
        if version == 2 else DEFAULT_SINGLE_GROOVE_POSE_CONFIG_V3
    )
    required = set(default)
    _validate_exact_fields(config, required, "single_groove_pose")
    expected_output = (
        SINGLE_GROOVE_POSE_SCHEMA_VERSION_V2
        if version == 2 else SINGLE_GROOVE_POSE_SCHEMA_VERSION_V3
    )
    if config.get("output_schema_version") != expected_output:
        raise ValueError("single_groove_pose.output_schema_version is unsupported")
    if config.get("image_angle_schema_version") != IMAGE_ANGLE_SCHEMA_VERSION_V2:
        raise ValueError("single_groove_pose.image_angle_schema_version is unsupported")
    if config.get("datum_angle_schema_version") != Y_DOWN_ANGLE_SCHEMA_VERSION:
        raise ValueError("single_groove_pose.datum_angle_schema_version is unsupported")
    target = config.get("target")
    if not isinstance(target, dict):
        raise ValueError("single_groove_pose.target must be an object")
    fields = set(default["target"])
    _validate_exact_fields(target, fields, "single_groove_pose.target")
    expected_target_schema = TARGET_SCHEMA_VERSION_V2 if version == 2 else TARGET_SCHEMA_VERSION_V3
    if target.get("schema_version") != expected_target_schema:
        raise ValueError("single_groove_pose.target.schema_version is unsupported")
    numeric = {
        key: _finite_number(target.get(key), key)
        for key in ("nominal_deg", "tolerance_deg", "accepted_min_deg", "accepted_max_deg")
    }
    if numeric != {"nominal_deg": 85.0, "tolerance_deg": 5.0, "accepted_min_deg": 80.0, "accepted_max_deg": 90.0}:
        raise ValueError(
            f"single_groove_pose v{version} target must be the confirmed +85deg +/-5deg contract"
        )
    if target.get("required_horizontal_position") != "left":
        raise ValueError(f"single_groove_pose v{version} target requires left horizontal position")
    if target.get("required_vertical_position") != "lower_or_axis":
        raise ValueError(f"single_groove_pose v{version} target requires lower_or_axis vertical position")
    for key in ("physical_datum_definition_id", "angle_convention_id"):
        value = target.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"single_groove_pose.target.{key} must be a non-empty string")


def _validate_v2(config: dict[str, Any]) -> None:
    _validate_refined_guidance_config(config, version=2)


def _validate_v3(config: dict[str, Any]) -> None:
    _validate_refined_guidance_config(config, version=3)
    target = config["target"]
    for key in ("physical_datum_definition_id", "angle_convention_id"):
        if target[key] != DEFAULT_SINGLE_GROOVE_POSE_CONFIG_V3["target"][key]:
            raise ValueError(f"single_groove_pose v3 target {key} is immutable")


def validate_single_groove_pose_config(config: dict[str, Any]) -> None:
    if not isinstance(config, dict):
        raise ValueError("single_groove_pose must be an object")
    version = config.get("schema_version")
    if version == "single-real-groove-pose-config/1":
        _validate_v1(config)
    elif version == "single-real-groove-pose-config/2":
        _validate_v2(config)
    elif version == "single-real-groove-pose-config/3":
        _validate_v3(config)
    else:
        raise ValueError("single_groove_pose.schema_version is unsupported")
    if config.get("expected_accepted_groove_count") != 1:
        raise ValueError("single_groove_pose.expected_accepted_groove_count must equal 1")


def merged_single_groove_pose_config(config: dict[str, Any] | None) -> dict[str, Any]:
    if config is None:
        raise ValueError("single_real_groove mode requires detector.single_groove_pose")
    if not isinstance(config, dict):
        raise ValueError("single_groove_pose must be an object")
    version = config.get("schema_version")
    if version == "single-real-groove-pose-config/1":
        default = DEFAULT_SINGLE_GROOVE_POSE_CONFIG
    elif version == "single-real-groove-pose-config/2":
        default = DEFAULT_SINGLE_GROOVE_POSE_CONFIG_V2
    elif version == "single-real-groove-pose-config/3":
        default = DEFAULT_SINGLE_GROOVE_POSE_CONFIG_V3
    else:
        raise ValueError("single_groove_pose.schema_version is unsupported")
    target_override = config.get("target") if isinstance(config.get("target"), dict) else {}
    merged = {
        **copy.deepcopy(default),
        **config,
        "target": {**copy.deepcopy(default["target"]), **target_override},
    }
    validate_single_groove_pose_config(merged)
    return merged


def _point(center: tuple[float, float], radius: float, profile_azimuth_deg: float) -> dict[str, float]:
    radians = math.radians(profile_azimuth_deg)
    return {
        "x": float(center[0]) + radius * math.cos(radians),
        "y": float(center[1]) + radius * math.sin(radians),
    }


def _position(point: dict[str, float], center: tuple[float, float], radius: float) -> tuple[str, str, float, float]:
    tolerance = max(1e-9, radius * 1e-8)
    dx, dy = point["x"] - center[0], point["y"] - center[1]
    horizontal = "right" if dx > tolerance else ("left" if dx < -tolerance else "axis")
    vertical = "lower" if dy > tolerance else ("upper" if dy < -tolerance else "axis")
    return horizontal, vertical, dx, dy


def _quadrant(horizontal: str, vertical: str) -> str:
    if horizontal == "axis":
        return f"{vertical}_axis"
    if vertical == "axis":
        return f"{horizontal}_axis"
    return f"{vertical}_{horizontal}"


def _wrap_signed(value: float) -> float:
    result = (float(value) + 180.0) % 360.0 - 180.0
    return 0.0 if abs(result) < 1e-12 else result


def measure_y_down_opening(
    center: tuple[float, float],
    outer_radius: float,
    start_profile_deg: float,
    end_profile_deg: float,
    *,
    midpoint_source: str,
    origin: str = "detected_physical_outer_circle_center",
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Measure one opening from ordered circular boundaries in the shared image convention."""
    if (
        len(center) != 2
        or not all(math.isfinite(float(value)) for value in center)
        or not math.isfinite(float(outer_radius))
        or float(outer_radius) <= 0.0
    ):
        raise ValueError("single groove circle geometry is invalid")
    if not isinstance(midpoint_source, str) or not midpoint_source.strip():
        raise ValueError("single groove midpoint source must be non-empty")
    if not isinstance(origin, str) or not origin.strip():
        raise ValueError("single groove coordinate origin must be non-empty")
    start = float(start_profile_deg) % 360.0
    end = float(end_profile_deg) % 360.0
    if not all(math.isfinite(value) for value in (start, end)):
        raise ValueError("single groove refined boundaries are invalid")
    span = (end - start) % 360.0
    if not 0.0 < span < 180.0:
        raise ValueError("single groove refined boundary order is invalid")
    profile_azimuth = wrap_360_deg(start + span / 2.0)
    image_up_azimuth = (profile_azimuth + 90.0) % 360.0
    circle_point = _point(center, float(outer_radius), profile_azimuth)
    horizontal, vertical, dx, dy = _position(circle_point, center, float(outer_radius))
    measurement = {
        "schemaVersion": IMAGE_ANGLE_SCHEMA_VERSION_V2,
        "coordinateConvention": {
            "origin": origin,
            "xAxis": "right",
            "yAxis": "down",
            "zeroDirection": "image_up",
            "positiveDirection": "clockwise",
            "rangeDeg": "[0,360)",
        },
        "azimuthDeg": image_up_azimuth,
        "profileAzimuthXRightClockwiseDeg": profile_azimuth,
        "quadrant": _quadrant(horizontal, vertical),
        "circlePoint": circle_point,
        "radialAxis": {
            "from": {"x": float(center[0]), "y": float(center[1])},
            "to": circle_point,
        },
        "midpointSource": midpoint_source,
    }
    measured = _wrap_signed(math.degrees(math.atan2(-dx, dy)))
    position_passed = horizontal == "left" and vertical in {"lower", "axis"}
    datum = {
        "schemaVersion": Y_DOWN_ANGLE_SCHEMA_VERSION,
        "coordinateConvention": {
            "origin": origin,
            "xAxis": "right",
            "yAxis": "down",
            "datumRay": "positive_y_down",
            "positiveDirection": "clockwise",
            "rangeDeg": "[-180,180)",
        },
        "grooveOpening": {
            "startProfileDeg": start,
            "endProfileDeg": end,
            "midpointProfileDeg": profile_azimuth,
            "midpointSource": midpoint_source,
        },
        "center": {"x": float(center[0]), "y": float(center[1])},
        "grooveOpeningPoint": circle_point,
        "offset": {"dx": dx, "dy": dy},
        "position": {
            "horizontal": horizontal,
            "vertical": vertical,
            "requiredRegionPassed": position_passed,
        },
        "measuredFromPositiveYClockwiseDeg": measured,
    }
    return measurement, datum


def _v1_target_assessment(target: dict[str, Any], geometry_valid: bool) -> dict[str, Any]:
    blockers: list[str] = []
    if not geometry_valid:
        blockers.append("GROOVE_GEOMETRY_REJECTED")
    if target.get("physical_datum_definition_id") is None:
        blockers.append("PHYSICAL_DATUM_UNCONFIRMED")
    if target.get("angle_convention_id") is None:
        blockers.append("TARGET_ANGLE_CONVENTION_UNCONFIRMED")
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
        "quadrantMatches": None,
        "signedMeasurementMinusTargetDeg": None,
        "absoluteDeviationDeg": None,
        "mechanicalCorrectionDeg": None,
        "blockers": blockers,
    }


def _v2_target_contract(target: dict[str, Any]) -> dict[str, Any]:
    return {
        "schemaVersion": target["schema_version"],
        "nominalDeg": float(target["nominal_deg"]),
        "toleranceDeg": float(target["tolerance_deg"]),
        "acceptedMinDeg": float(target["accepted_min_deg"]),
        "acceptedMaxDeg": float(target["accepted_max_deg"]),
        "requiredHorizontalPosition": target["required_horizontal_position"],
        "requiredVerticalPosition": target["required_vertical_position"],
        "physicalDatumDefinitionId": target["physical_datum_definition_id"],
        "angleConventionId": target["angle_convention_id"],
    }


def assess_y_down_target(
    target: dict[str, Any], datum: dict[str, Any] | None, *, plc_mapping_confirmed: bool,
) -> dict[str, Any]:
    contract = _v2_target_contract(target)
    if datum is None:
        return {
            "schemaVersion": TARGET_ASSESSMENT_SCHEMA_VERSION_V2,
            "targetContract": contract,
            "status": "NOT_EVALUATED",
            "positionGatePassed": None,
            "angleTolerancePassed": None,
            "toleranceStatus": "NOT_EVALUATED",
            "signedMeasurementMinusTargetDeg": None,
            "absoluteDeviationDeg": None,
            "imageFrameCorrectionDeg": None,
            "imageFrameCorrectionDirection": None,
            "mechanicalCorrectionDeg": None,
            "plcCommandAuthoritative": False,
            "blockers": ["GROOVE_GEOMETRY_REJECTED"],
        }
    measured = float(datum["measuredFromPositiveYClockwiseDeg"])
    position_passed = bool(datum["position"]["requiredRegionPassed"])
    epsilon = 1e-9
    angle_passed = (
        float(target["accepted_min_deg"]) - epsilon
        <= measured
        <= float(target["accepted_max_deg"]) + epsilon
    )
    deviation = _wrap_signed(measured - float(target["nominal_deg"]))
    correction = _wrap_signed(float(target["nominal_deg"]) - measured)
    if correction > 0.0:
        direction = "clockwise"
    elif correction < 0.0:
        direction = "counter_clockwise"
    else:
        direction = "none"
    blockers = [] if plc_mapping_confirmed else ["PLC_MAPPING_UNCONFIRMED"]
    return {
        "schemaVersion": TARGET_ASSESSMENT_SCHEMA_VERSION_V2,
        "targetContract": contract,
        "status": "EVALUATED",
        "positionGatePassed": position_passed,
        "angleTolerancePassed": angle_passed,
        "toleranceStatus": "PASS" if position_passed and angle_passed else "FAIL",
        "signedMeasurementMinusTargetDeg": deviation,
        "absoluteDeviationDeg": abs(deviation),
        "imageFrameCorrectionDeg": correction,
        "imageFrameCorrectionDirection": direction,
        "mechanicalCorrectionDeg": correction if plc_mapping_confirmed else None,
        "plcCommandAuthoritative": bool(plc_mapping_confirmed),
        "blockers": blockers,
    }


def build_closed_loop_guidance(
    target: dict[str, Any],
    datum: dict[str, Any] | None,
    *,
    geometry_valid: bool,
    plc_mapping_confirmed: bool,
) -> dict[str, Any]:
    """Convert one trusted image-frame measurement into stateless closed-loop guidance."""
    coordinate_convention = {
        "origin": "detected_physical_outer_circle_center",
        "xAxis": "right",
        "yAxis": "down",
        "datumRay": "positive_y_down",
        "physicalDatumAlias": "workpiece_negative_y_lower_half_axis",
        "positiveDirection": "clockwise",
        "rangeDeg": "[-180,180)",
    }
    plc_execution = {
        "status": "READY" if plc_mapping_confirmed else "BLOCKED_MAPPING_UNCONFIRMED",
        "mechanicalCorrectionDeg": None,
        "plcCommand": None,
        "authoritative": bool(plc_mapping_confirmed),
        "blockers": [] if plc_mapping_confirmed else ["PLC_MAPPING_UNCONFIRMED"],
    }
    base = {
        "schemaVersion": IMAGE_FRAME_GUIDANCE_SCHEMA_VERSION,
        "targetAngleDeg": float(target["nominal_deg"]),
        "toleranceDeg": float(target["tolerance_deg"]),
        "acceptedRangeDeg": [
            float(target["accepted_min_deg"]), float(target["accepted_max_deg"]),
        ],
        "coordinateConvention": coordinate_convention,
        "plcExecution": plc_execution,
    }
    if not geometry_valid or datum is None:
        return {
            **base,
            "detectionStatus": "DETECTION_FAILED",
            "guidanceStatus": "NOT_AVAILABLE",
            "currentAngleDeg": None,
            "correctionRawDeg": None,
            "correctionDeg": None,
            "imageFrameCorrectionDeg": None,
            "rotationDirection": None,
            "withinTolerance": None,
        }
    measured = _wrap_signed(float(datum["measuredFromPositiveYClockwiseDeg"]))
    correction_raw = _wrap_signed(float(target["nominal_deg"]) - measured)
    epsilon = 1e-9
    in_angle_deadband = (
        float(target["accepted_min_deg"]) - epsilon
        <= measured
        <= float(target["accepted_max_deg"]) + epsilon
    )
    in_target_region = bool(datum["position"]["requiredRegionPassed"])
    within_tolerance = in_angle_deadband and in_target_region
    correction = 0.0 if within_tolerance else correction_raw
    if within_tolerance or correction == 0.0:
        direction = "NONE"
    elif correction > 0.0:
        direction = "CLOCKWISE"
    else:
        direction = "COUNTERCLOCKWISE"
    if plc_mapping_confirmed:
        plc_execution["mechanicalCorrectionDeg"] = correction
    return {
        **base,
        "detectionStatus": "DETECTED",
        "guidanceStatus": (
            "DETECTED_IN_POSITION" if within_tolerance
            else "DETECTED_NEEDS_ADJUSTMENT"
        ),
        "currentAngleDeg": measured,
        "correctionRawDeg": correction_raw,
        "correctionDeg": correction,
        "imageFrameCorrectionDeg": correction,
        "rotationDirection": direction,
        "withinTolerance": within_tolerance,
    }


def _accepted_status(candidates: list[dict[str, Any]], recognition_status: str) -> str:
    if len(candidates) > 1 or recognition_status == "ambiguous":
        return "ambiguous"
    if len(candidates) == 1 and recognition_status == "accepted":
        return "accepted"
    return "failed"


def build_single_groove_pose(
    groove_candidates: Iterable[dict[str, Any]],
    center: tuple[float, float],
    outer_radius: float,
    config: dict[str, Any],
    *,
    recognition_status: str,
    plc_mapping_confirmed: bool = False,
) -> dict[str, Any]:
    """Build versioned single-groove diagnostics; top-level authority stays separate."""
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
    status = _accepted_status(candidates, recognition_status)
    geometry_valid = status == "accepted"
    candidate = candidates[0] if geometry_valid else None
    is_v2 = merged["schema_version"] == "single-real-groove-pose-config/2"
    is_v3 = merged["schema_version"] == "single-real-groove-pose-config/3"
    is_refined = is_v2 or is_v3
    if is_refined and candidate is not None:
        refinement = candidate.get("grooveRefinement")
        if not isinstance(refinement, dict) or refinement.get("status") != "accepted":
            status = "failed"
            geometry_valid = False
            candidate = None
    measurement = None
    datum = None
    if candidate is not None:
        if is_refined:
            try:
                start = float(candidate["refinedStartDeg"]) % 360.0
                end = float(candidate["refinedEndDeg"]) % 360.0
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError("single groove refined boundaries are invalid") from exc
            span = (end - start) % 360.0
            if not 0.0 < span < 180.0:
                raise ValueError("single groove refined boundary order is invalid")
            profile_azimuth = wrap_360_deg(start + span / 2.0)
            midpoint_source = "subpixel_sidewall_outer_circle_intersections"
        else:
            profile_azimuth = float(candidate["centerDeg"]) % 360.0
            start = float(candidate["startDeg"]) % 360.0
            end = float(candidate["endDeg"]) % 360.0
            midpoint_source = "intensity_weighted_candidate_center"
        if not all(math.isfinite(value) for value in (profile_azimuth, start, end)):
            raise ValueError("single groove candidate azimuth is invalid")
        image_up_azimuth = (profile_azimuth + 90.0) % 360.0
        circle_point = _point(center, float(outer_radius), profile_azimuth)
        horizontal, vertical, dx, dy = _position(circle_point, center, float(outer_radius))
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
            "quadrant": _quadrant(horizontal, vertical),
            "circlePoint": circle_point,
            "radialAxis": {
                "from": {"x": float(center[0]), "y": float(center[1])},
                "to": circle_point,
            },
        }
        if is_refined:
            measurement, datum = measure_y_down_opening(
                center,
                float(outer_radius),
                start,
                end,
                midpoint_source=midpoint_source,
            )

    target_assessment = None
    if is_v2:
        target_assessment = assess_y_down_target(
            merged["target"], datum, plc_mapping_confirmed=plc_mapping_confirmed,
        )
    elif not is_v3:
        target_assessment = _v1_target_assessment(merged["target"], geometry_valid)
    result = {
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
            "mechanicalGuidanceAuthoritative": bool(
                is_refined and geometry_valid and plc_mapping_confirmed
            ),
        },
        "imageMeasurement": measurement,
    }
    if is_v2:
        result["targetAssessment"] = target_assessment
    elif not is_v3:
        result["targetAssessment"] = target_assessment
    if is_refined:
        result["datumMeasurement"] = datum
    if is_v3:
        result["guidance"] = build_closed_loop_guidance(
            merged["target"], datum,
            geometry_valid=geometry_valid,
            plc_mapping_confirmed=plc_mapping_confirmed,
        )
    return result
