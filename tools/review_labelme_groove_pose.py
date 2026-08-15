#!/usr/bin/env python3
"""Review an external LabelMe circle arc and open-groove boundary offline."""

from __future__ import annotations

import argparse
import base64
import binascii
import copy
import hashlib
import io
import json
import math
import sys
from pathlib import Path
from typing import Any, Callable

import numpy as np
from PIL import Image, ImageDraw, ImageFont

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from algorithms.slot_pose.angular_profile import (
    circular_delta_deg,
    circular_distance_deg,
    circular_midpoint_deg,
    wrap_360_deg,
)
from algorithms.slot_pose.contract import load_config, sha256_file
from algorithms.slot_pose.legacy_adapter import LegacyAEndFaceAdapter
from algorithms.slot_pose.single_groove_pose import (
    DEFAULT_SINGLE_GROOVE_POSE_CONFIG_V2,
    assess_y_down_target,
    measure_y_down_opening,
)


SCHEMA_VERSION = "manual-groove-pose-review/1"
ALGORITHM_VERSION = "1.0.0"
ANGLE_SCHEMA_VERSION = "slot-groove-image-angle/1"
TARGET_SCHEMA_VERSION = "slot-groove-target/1"
TARGET_ASSESSMENT_SCHEMA_VERSION = "slot-groove-target-assessment/1"
DEFAULT_REVIEW_CONFIG: dict[str, Any] = {
    "threshold_version": "manual-open-groove-v1",
    "minimum_circle_points": 8,
    "minimum_groove_points": 6,
    "minimum_circle_coverage_deg": 120.0,
    "maximum_circle_median_residual_px": 5.0,
    "maximum_circle_p95_residual_px": 10.0,
    "maximum_endpoint_circle_residual_px": 20.0,
    "minimum_opening_width_deg": 1.0,
    "maximum_opening_width_deg": 60.0,
    "minimum_inward_depth_from_mouth_px": 30.0,
    "minimum_interior_inward_px": 10.0,
    "minimum_interior_inward_fraction": 0.60,
    "minimum_deepest_point_fraction": 0.10,
    "maximum_deepest_point_fraction": 0.90,
    "maximum_step_to_median_ratio": 3.0,
    "maximum_step_to_radius_ratio": 0.15,
}


def _finite_points(raw: Any, minimum: int, name: str) -> np.ndarray:
    if not isinstance(raw, list) or len(raw) < minimum:
        raise ValueError(f"{name} linestrip must contain at least {minimum} finite points")
    values: list[tuple[float, float]] = []
    for point in raw:
        if (
            not isinstance(point, (list, tuple))
            or len(point) != 2
            or any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in point)
        ):
            raise ValueError(f"{name} linestrip must contain at least {minimum} finite points")
        x, y = map(float, point)
        if not math.isfinite(x) or not math.isfinite(y):
            raise ValueError(f"{name} linestrip must contain at least {minimum} finite points")
        values.append((x, y))
    return np.asarray(values, dtype=np.float64)


def _circle_dict(circle: tuple[float, float, float]) -> dict[str, float]:
    return {"centerX": float(circle[0]), "centerY": float(circle[1]), "radiusPx": float(circle[2])}


def _point_dict(point: tuple[float, float] | np.ndarray) -> dict[str, float]:
    return {"x": float(point[0]), "y": float(point[1])}


def _radial_residuals(points: np.ndarray, circle: tuple[float, float, float]) -> np.ndarray:
    return np.abs(np.hypot(points[:, 0] - circle[0], points[:, 1] - circle[1]) - circle[2])


def _summary(values: np.ndarray) -> dict[str, float]:
    return {
        "median": float(np.median(values)),
        "p95": float(np.percentile(values, 95.0)),
        "max": float(np.max(values)),
    }


def _angular_coverage_deg(points: np.ndarray, center: tuple[float, float]) -> float:
    angles = np.sort(np.mod(
        np.arctan2(points[:, 1] - center[1], points[:, 0] - center[0]),
        2.0 * math.pi,
    ))
    gaps = np.diff(np.concatenate((angles, [angles[0] + 2.0 * math.pi])))
    return math.degrees(2.0 * math.pi - float(np.max(gaps)))


def _heading_image_deg(point: np.ndarray, center: tuple[float, float]) -> float:
    dx, dy = float(point[0] - center[0]), float(point[1] - center[1])
    return wrap_360_deg(math.degrees(math.atan2(dx, -dy)))


def _point_on_circle(circle: tuple[float, float, float], heading_deg: float) -> tuple[float, float]:
    angle = math.radians(heading_deg)
    return (
        circle[0] + circle[2] * math.sin(angle),
        circle[1] - circle[2] * math.cos(angle),
    )


def _quadrant(point: tuple[float, float], center: tuple[float, float], radius: float) -> str:
    dx, dy = point[0] - center[0], point[1] - center[1]
    tolerance = max(1e-6, radius * 1e-8)
    horizontal = "right" if dx > tolerance else ("left" if dx < -tolerance else "axis")
    vertical = "lower" if dy > tolerance else ("upper" if dy < -tolerance else "axis")
    if horizontal == "axis" and vertical == "axis":
        return "center"
    if horizontal == "axis":
        return f"{vertical}_axis"
    if vertical == "axis":
        return f"{horizontal}_axis"
    return f"{vertical}_{horizontal}"


def _validate_target_contract(target: dict[str, Any]) -> None:
    if target.get("schemaVersion") != TARGET_SCHEMA_VERSION:
        raise ValueError(f"target schemaVersion must be {TARGET_SCHEMA_VERSION}")
    nominal = target.get("nominalDeg")
    if isinstance(nominal, bool) or not isinstance(nominal, (int, float)) or not math.isfinite(float(nominal)):
        raise ValueError("target nominalDeg must be finite")
    if not 0.0 <= float(nominal) < 360.0:
        raise ValueError("target nominalDeg must be in [0,360)")
    if target.get("expectedQuadrant") not in {"upper_left", "upper_right", "lower_left", "lower_right"}:
        raise ValueError("target expectedQuadrant is invalid")
    for key in ("physicalDatumDefinitionId", "angleConventionId"):
        value = target.get(key)
        if value is not None and (not isinstance(value, str) or not value.strip()):
            raise ValueError(f"target {key} must be null or a non-empty string")


def assess_target(
    measured_azimuth_deg: float | None,
    measured_quadrant: str | None,
    target_contract: dict[str, Any],
) -> dict[str, Any]:
    """Compare only when the physical datum and target convention are identified."""
    _validate_target_contract(target_contract)
    blockers: list[str] = []
    if measured_azimuth_deg is None or measured_quadrant is None:
        blockers.append("GROOVE_GEOMETRY_REJECTED")
    if target_contract.get("physicalDatumDefinitionId") is None:
        blockers.append("PHYSICAL_DATUM_UNCONFIRMED")
    if target_contract.get("angleConventionId") is None:
        blockers.append("TARGET_ANGLE_CONVENTION_UNCONFIRMED")
    comparable = not blockers
    deviation = (
        circular_delta_deg(float(measured_azimuth_deg), float(target_contract["nominalDeg"]))
        if comparable else None
    )
    return {
        "schemaVersion": TARGET_ASSESSMENT_SCHEMA_VERSION,
        "targetContract": copy.deepcopy(target_contract),
        "status": "COMPARABLE" if comparable else "NOT_EVALUATED",
        "quadrantMatches": (
            None if measured_quadrant is None
            else measured_quadrant == target_contract["expectedQuadrant"]
        ),
        "signedMeasurementMinusTargetDeg": deviation,
        "absoluteDeviationDeg": None if deviation is None else abs(deviation),
        "mechanicalCorrectionDeg": None,
        "blockers": blockers,
    }


def assess_confirmed_y_down_target(
    endpoint_headings_image_deg: list[float],
    center: tuple[float, float],
    radius: float,
    *,
    geometry_accepted: bool,
) -> dict[str, Any]:
    """Apply the runtime v2 convention to manual geometry without making it runtime truth."""
    measurement = None
    datum = None
    if geometry_accepted:
        profile = [wrap_360_deg(float(value) - 90.0) for value in endpoint_headings_image_deg]
        forward_span = (profile[1] - profile[0]) % 360.0
        start, end = (profile[0], profile[1]) if 0.0 < forward_span < 180.0 else (profile[1], profile[0])
        measurement, datum = measure_y_down_opening(
            center,
            radius,
            start,
            end,
            midpoint_source="manual_boundary_endpoints_offline_only",
            origin="manual_fitted_outer_circle_center_offline_only",
        )
        measurement["schemaVersion"] = "manual-groove-image-angle/1"
        datum["schemaVersion"] = "manual-groove-y-down-angle/1"
    target = copy.deepcopy(DEFAULT_SINGLE_GROOVE_POSE_CONFIG_V2["target"])
    return {
        "schemaVersion": "manual-groove-y-down-target-diagnostic/1",
        "status": "accepted" if geometry_accepted else "failed",
        "geometryValid": geometry_accepted,
        "runtimeInputAllowed": False,
        "imageMeasurement": measurement,
        "datumMeasurement": datum,
        "targetAssessment": assess_y_down_target(
            target,
            datum,
            plc_mapping_confirmed=False,
        ),
    }


def analyze_manual_groove_geometry(
    raw_circle_points: Any,
    raw_groove_points: Any,
    fit_circle: Callable[[Any], tuple[float, float, float]],
    robust_fit_circle: Callable[[Any, tuple[float, float, float]], tuple[float, float, float]],
    review_config: dict[str, Any],
    target_contract: dict[str, Any],
    *,
    circle_fit_source_sha256: str,
) -> dict[str, Any]:
    """Validate manual geometry and compute image-frame diagnostics only."""
    config = {**DEFAULT_REVIEW_CONFIG, **review_config}
    circle_points = _finite_points(
        raw_circle_points, int(config["minimum_circle_points"]), "outer circle visible arc",
    )
    groove_points = _finite_points(
        raw_groove_points, int(config["minimum_groove_points"]), "groove open boundary",
    )
    if len(circle_fit_source_sha256) != 64:
        raise ValueError("circle fit source SHA-256 must contain 64 characters")

    initial = tuple(map(float, fit_circle(circle_points)))
    refined = tuple(map(float, robust_fit_circle(circle_points, initial)))
    for name, circle in (("initial", initial), ("refined", refined)):
        if not all(math.isfinite(value) for value in circle) or circle[2] <= 0.0:
            raise ValueError(f"{name} circle fit is invalid")
    initial_residuals = _radial_residuals(circle_points, initial)
    refined_residuals = _radial_residuals(circle_points, refined)
    coverage = _angular_coverage_deg(circle_points, (refined[0], refined[1]))
    circle_failures: list[str] = []
    if coverage < float(config["minimum_circle_coverage_deg"]):
        circle_failures.append("insufficient_circle_coverage")
    if float(np.median(refined_residuals)) > float(config["maximum_circle_median_residual_px"]):
        circle_failures.append("circle_median_residual")
    if float(np.percentile(refined_residuals, 95.0)) > float(config["maximum_circle_p95_residual_px"]):
        circle_failures.append("circle_p95_residual")
    if circle_failures:
        raise ValueError(f"circle quality failed: {circle_failures}")

    center = (refined[0], refined[1])
    radii = np.hypot(groove_points[:, 0] - refined[0], groove_points[:, 1] - refined[1])
    inward = refined[2] - radii
    endpoint_residuals = np.abs(radii[[0, -1]] - refined[2])
    endpoint_headings = [
        _heading_image_deg(groove_points[0], center),
        _heading_image_deg(groove_points[-1], center),
    ]
    opening_width = circular_distance_deg(endpoint_headings[0], endpoint_headings[1])
    opening_center = circular_midpoint_deg(endpoint_headings[0], endpoint_headings[1])
    circle_midpoint = _point_on_circle(refined, opening_center)
    steps = np.hypot(np.diff(groove_points[:, 0]), np.diff(groove_points[:, 1]))
    if np.any(steps <= 1e-9):
        raise ValueError("groove open boundary adjacent points must be distinct")
    step_median = float(np.median(steps))
    step_max = float(np.max(steps))
    step_ratio = step_max / step_median
    mouth_depth = float(np.mean(inward[[0, -1]]))
    deepest_index = int(np.argmax(inward))
    deepest_fraction = deepest_index / float(len(groove_points) - 1)
    inward_depth_from_mouth = float(np.max(inward) - mouth_depth)
    interior_inward_fraction = float(np.mean(
        inward[1:-1] >= float(config["minimum_interior_inward_px"])
    ))

    rejection_reasons: list[str] = []
    if np.any(endpoint_residuals > float(config["maximum_endpoint_circle_residual_px"])):
        rejection_reasons.append("endpoint_not_on_outer_circle")
    if not float(config["minimum_opening_width_deg"]) <= opening_width <= float(config["maximum_opening_width_deg"]):
        rejection_reasons.append("opening_width_out_of_range")
    if inward_depth_from_mouth < float(config["minimum_inward_depth_from_mouth_px"]):
        rejection_reasons.append("insufficient_inward_depth")
    if interior_inward_fraction < float(config["minimum_interior_inward_fraction"]):
        rejection_reasons.append("insufficient_inward_continuity")
    if not (
        float(config["minimum_deepest_point_fraction"])
        <= deepest_fraction
        <= float(config["maximum_deepest_point_fraction"])
    ):
        rejection_reasons.append("deepest_point_at_boundary")
    if (
        step_ratio > float(config["maximum_step_to_median_ratio"])
        or step_max / refined[2] > float(config["maximum_step_to_radius_ratio"])
    ):
        rejection_reasons.append("boundary_discontinuity")
    rejection_reasons = list(dict.fromkeys(rejection_reasons))
    accepted = not rejection_reasons
    quadrant = _quadrant(circle_midpoint, center, refined[2]) if accepted else None
    measurement = None if not accepted else {
        "schemaVersion": ANGLE_SCHEMA_VERSION,
        "coordinateConvention": {
            "origin": "fitted_outer_circle_center",
            "xAxis": "right",
            "yAxis": "down",
            "zeroDirection": "image_up",
            "positiveDirection": "clockwise",
            "rangeDeg": "[0,360)",
        },
        "openingEndpointAzimuthsDeg": endpoint_headings,
        "openingCenterAzimuthImageDeg": opening_center,
        "openingWidthDeg": opening_width,
        "openingCenterOnCircle": _point_dict(circle_midpoint),
        "radialAxis": {
            "from": _point_dict(center),
            "to": _point_dict(circle_midpoint),
        },
        "quadrant": quadrant,
        "geometryMeasurementValid": True,
    }
    y_down_target = assess_confirmed_y_down_target(
        endpoint_headings,
        center,
        refined[2],
        geometry_accepted=accepted,
    )
    return {
        "algorithm": {
            "name": "locked-gyj-manual-groove-review",
            "version": ALGORITHM_VERSION,
            "thresholdVersion": config["threshold_version"],
            "circleFitSourceSha256": circle_fit_source_sha256,
            "delegatedCircleFitFunctions": ["fit_circle", "robust_fit_circle", "geometric_circle_fit"],
            "runtimeInputAllowed": False,
        },
        "circle": {
            "status": "accepted",
            "pointCount": int(len(circle_points)),
            "angularCoverageDeg": coverage,
            "initialKasaCircle": _circle_dict(initial),
            "initialResidualPx": _summary(initial_residuals),
            "refinedRobustGeometricCircle": _circle_dict(refined),
            "refinedResidualPx": _summary(refined_residuals),
            "failedChecks": [],
        },
        "grooveRecognition": {
            "status": "accepted" if accepted else "rejected",
            "pointCount": int(len(groove_points)),
            "endpointCircleResidualPx": [float(value) for value in endpoint_residuals],
            "endpointAzimuthImageDeg": endpoint_headings,
            "openingWidthDeg": opening_width,
            "maxInwardDepthPx": float(np.max(inward)),
            "inwardDepthFromMouthPx": inward_depth_from_mouth,
            "interiorInwardFraction": interior_inward_fraction,
            "deepestPointIndex": deepest_index,
            "deepestPointFraction": deepest_fraction,
            "stepMedianPx": step_median,
            "stepMaxPx": step_max,
            "stepMaxToMedianRatio": step_ratio,
            "rejectionReasons": rejection_reasons,
        },
        "measurement": measurement,
        "targetAssessment": assess_target(opening_center if accepted else None, quadrant, target_contract),
        "yDownTargetDiagnostic": y_down_target,
    }


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _load_image(payload: dict[str, Any], image_path: Path | None) -> tuple[Image.Image, str, str, str]:
    encoded = payload.get("imageData")
    if isinstance(encoded, str) and encoded.strip():
        raw = encoded.split(",", 1)[-1] if encoded.startswith("data:") else encoded
        try:
            data = base64.b64decode(raw, validate=True)
            image = Image.open(io.BytesIO(data)).convert("RGB")
        except (binascii.Error, OSError) as exc:
            raise ValueError("LabelMe imageData is not a decodable image") from exc
        return image, _sha256_bytes(data), Path(str(payload.get("imagePath") or "embedded-image")).name, "labelme_imageData"
    if image_path is None or not image_path.is_file():
        raise ValueError("LabelMe imageData is empty; --image must identify the external image")
    with Image.open(image_path) as source:
        image = source.convert("RGB")
    return image, sha256_file(image_path), image_path.name, "external_file"


def _ensure_external_outputs(paths: list[Path], inputs: list[Path]) -> None:
    resolved = [path.resolve() for path in paths]
    if len(set(resolved)) != len(resolved) or any(path in set(inputs) for path in resolved):
        raise ValueError("input and output paths must be distinct")
    root = PROJECT_ROOT.resolve()
    for path in resolved:
        try:
            path.relative_to(root)
        except ValueError:
            continue
        raise ValueError("manual review outputs must be outside the Git worktree")


def _semantic_copy(
    payload: dict[str, Any], circle_label: str, groove_label: str,
) -> dict[str, Any]:
    semantic = copy.deepcopy(payload)
    semantic["flags"] = {
        **(semantic.get("flags") or {}),
        "derived_semantic_copy": True,
        "runtime_input_allowed": False,
        "formal_truth": False,
    }
    label_map = {
        circle_label: "physical_outer_circle_visible_arc_manual",
        groove_label: "target_groove_open_boundary_manual",
    }
    for shape in semantic["shapes"]:
        source_label = shape.get("label")
        if source_label in label_map:
            shape["label"] = label_map[source_label]
            shape["description"] = (
                f"Derived semantic label from source {source_label!r}; offline review only; "
                "runtime_input_allowed=false; formal_truth=false."
            )
    return semantic


def _draw_preview(
    image: Image.Image,
    circle_points: np.ndarray,
    groove_points: np.ndarray,
    analysis: dict[str, Any],
    output_path: Path,
) -> None:
    canvas = image.copy()
    draw = ImageDraw.Draw(canvas)
    width = max(3, canvas.width // 1200)
    radius = max(5, canvas.width // 900)
    font = ImageFont.load_default(size=max(18, canvas.width // 220))
    circle = analysis["circle"]["refinedRobustGeometricCircle"]
    cx, cy, fitted_radius = circle["centerX"], circle["centerY"], circle["radiusPx"]
    draw.ellipse(
        (cx - fitted_radius, cy - fitted_radius, cx + fitted_radius, cy + fitted_radius),
        outline="#2ec7ff", width=width,
    )
    draw.line([tuple(point) for point in circle_points], fill="#ffe04d", width=width)
    draw.line([tuple(point) for point in groove_points], fill="#38d66b", width=width * 2)
    for point, color in ((groove_points[0], "#ff6b5e"), (groove_points[-1], "#ff6b5e")):
        draw.ellipse((point[0] - radius, point[1] - radius, point[0] + radius, point[1] + radius), fill=color)
    draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), fill="#ffffff")
    measurement = analysis["measurement"]
    if measurement is not None:
        midpoint = measurement["openingCenterOnCircle"]
        draw.line((cx, cy, midpoint["x"], midpoint["y"]), fill="#ff5dce", width=width * 2)
        draw.ellipse(
            (midpoint["x"] - radius, midpoint["y"] - radius, midpoint["x"] + radius, midpoint["y"] + radius),
            fill="#ff5dce",
        )
        measured = f"measured={measurement['openingCenterAzimuthImageDeg']:.3f}deg {measurement['quadrant']}"
    else:
        measured = "measured=invalid"
    target = analysis["yDownTargetDiagnostic"]["targetAssessment"]
    target_text = (
        f"Y-down target={target['targetContract']['nominalDeg']:.3f}+/-"
        f"{target['targetContract']['toleranceDeg']:.3f}deg status={target['toleranceStatus']}"
    )
    header_height = max(130, canvas.height // 20)
    draw.rectangle((0, 0, min(canvas.width, 3100), header_height), fill="#111111")
    draw.text((16, 10), "OFFLINE MANUAL GROOVE REVIEW - NOT RUNTIME TRUTH", fill="white", font=font)
    draw.text((16, 50), measured, fill="#ff5dce", font=font)
    draw.text((16, 88), target_text, fill="#ffffff", font=font)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path, format="JPEG", quality=92)


def review_labelme_groove_pose(
    annotation_path: Path,
    image_path: Path | None,
    config_path: Path,
    report_path: Path,
    semantic_copy_path: Path,
    preview_path: Path,
    *,
    circle_label: str,
    groove_label: str,
    target_contract: dict[str, Any],
) -> dict[str, Any]:
    annotation_path = annotation_path.resolve()
    config_path = config_path.resolve()
    image_path = image_path.resolve() if image_path is not None else None
    _ensure_external_outputs(
        [report_path, semantic_copy_path, preview_path],
        [annotation_path, config_path, *([] if image_path is None else [image_path])],
    )
    if not annotation_path.is_file():
        raise ValueError("LabelMe annotation does not exist")
    before_hash = sha256_file(annotation_path)
    payload = json.loads(annotation_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("shapes"), list):
        raise ValueError("annotation must be a LabelMe object with shapes")
    if not circle_label or not groove_label or circle_label == groove_label:
        raise ValueError("circle and groove labels must be distinct non-empty strings")
    matches: dict[str, list[dict[str, Any]]] = {
        label: [shape for shape in payload["shapes"] if shape.get("label") == label]
        for label in (circle_label, groove_label)
    }
    for label, shapes in matches.items():
        if len(shapes) != 1 or shapes[0].get("shape_type") != "linestrip":
            raise ValueError(f"exactly one LabelMe linestrip labeled {label!r} is required")

    image, image_hash, image_name, image_source = _load_image(payload, image_path)
    if payload.get("imageWidth") != image.width or payload.get("imageHeight") != image.height:
        raise ValueError("LabelMe dimensions do not match the review image")
    config = load_config(config_path)
    adapter = LegacyAEndFaceAdapter(config)
    source_hash = adapter.expected_hashes[adapter.paths.source]
    analysis = analyze_manual_groove_geometry(
        matches[circle_label][0].get("points"),
        matches[groove_label][0].get("points"),
        adapter.module.fit_circle,
        adapter.module.robust_fit_circle,
        DEFAULT_REVIEW_CONFIG,
        target_contract,
        circle_fit_source_sha256=source_hash,
    )

    circle_points = _finite_points(
        matches[circle_label][0].get("points"), DEFAULT_REVIEW_CONFIG["minimum_circle_points"], "outer circle visible arc",
    )
    groove_points = _finite_points(
        matches[groove_label][0].get("points"), DEFAULT_REVIEW_CONFIG["minimum_groove_points"], "groove open boundary",
    )
    semantic_copy_path = semantic_copy_path.resolve()
    semantic_copy_path.parent.mkdir(parents=True, exist_ok=True)
    semantic_copy_path.write_text(
        json.dumps(_semantic_copy(payload, circle_label, groove_label), ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    preview_path = preview_path.resolve()
    _draw_preview(image, circle_points, groove_points, analysis, preview_path)
    accepted = analysis["grooveRecognition"]["status"] == "accepted"
    target_status = analysis["targetAssessment"]["status"]
    status = (
        "MANUAL_GROOVE_GEOMETRY_REJECTED" if not accepted
        else "MANUAL_GEOMETRY_ACCEPTED_TARGET_COMPARABLE" if target_status == "COMPARABLE"
        else "MANUAL_GEOMETRY_ACCEPTED_TARGET_NOT_EVALUATED"
    )
    report = {
        "schemaVersion": SCHEMA_VERSION,
        "status": status,
        "source": {
            "annotationFile": annotation_path.name,
            "annotationSha256": before_hash,
            "imageFile": image_name,
            "imageSha256": image_hash,
            "imageWidth": image.width,
            "imageHeight": image.height,
            "imageSource": image_source,
            "labels": {
                "outerCircleVisibleArc": circle_label,
                "grooveOpenBoundary": groove_label,
            },
            "pointCounts": {
                "outerCircleVisibleArc": int(len(circle_points)),
                "grooveOpenBoundary": int(len(groove_points)),
            },
        },
        **analysis,
        "artifacts": {
            "semanticCopyFile": semantic_copy_path.name,
            "semanticCopySha256": sha256_file(semantic_copy_path),
            "previewFile": preview_path.name,
            "previewSha256": sha256_file(preview_path),
        },
        "limitations": [
            "This manual annotation is external development evidence and is not consumed by runtime detection.",
            "Geometry acceptance can reject non-inward shadow contours but does not turn one sample into production accuracy.",
            "The image Y-down target is diagnostic; PLC scaling, direction and transport remain unconfirmed, so mechanical correction remains null.",
        ],
    }
    report_path = report_path.resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    if sha256_file(annotation_path) != before_hash:
        raise RuntimeError("source annotation changed during review")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--annotation", required=True, type=Path)
    parser.add_argument("--image", type=Path, help="Required only when LabelMe imageData is empty")
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--circle-label", required=True)
    parser.add_argument("--groove-label", required=True)
    parser.add_argument("--target-angle-deg", required=True, type=float)
    parser.add_argument("--target-quadrant", required=True, choices=("upper_left", "upper_right", "lower_left", "lower_right"))
    parser.add_argument("--physical-datum-definition-id")
    parser.add_argument("--target-angle-convention-id")
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--semantic-copy", required=True, type=Path)
    parser.add_argument("--preview", required=True, type=Path)
    args = parser.parse_args()
    target = {
        "schemaVersion": TARGET_SCHEMA_VERSION,
        "nominalDeg": args.target_angle_deg,
        "expectedQuadrant": args.target_quadrant,
        "physicalDatumDefinitionId": args.physical_datum_definition_id,
        "angleConventionId": args.target_angle_convention_id,
    }
    try:
        report = review_labelme_groove_pose(
            args.annotation, args.image, args.config, args.report, args.semantic_copy, args.preview,
            circle_label=args.circle_label, groove_label=args.groove_label, target_contract=target,
        )
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(
        f"status={report['status']} groove={report['grooveRecognition']['status']} "
        f"measured={None if report['measurement'] is None else report['measurement']['openingCenterAzimuthImageDeg']} "
        f"target={report['targetAssessment']['status']} report={args.report}"
    )
    return 0 if report["grooveRecognition"]["status"] == "accepted" else 3


if __name__ == "__main__":
    raise SystemExit(main())
