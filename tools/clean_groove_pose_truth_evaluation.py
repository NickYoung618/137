#!/usr/bin/env python3
"""Evaluate independent outer-circle and clean-groove pose truth offline.

This module is deliberately diagnostic-only.  Human annotations are joined to
frozen runtime records by image SHA-256 and never enter the detector.
"""

from __future__ import annotations

import json
import math
import statistics
from pathlib import Path
from typing import Any, Iterable

import numpy as np

from algorithms.hole_2.main import fit_circle_kasa, robust_fit_circle
from tools.dataset_common import sha256_file


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = PROJECT_ROOT / "contracts" / "clean-groove-pose-truth-evaluation.schema.json"
ARC_LABEL = "HUMAN_outer_circle_visible_arc"
ENDPOINT_LABELS = (
    "HUMAN_clean_groove_mouth_endpoint_left",
    "HUMAN_clean_groove_mouth_endpoint_right",
)

QUALITY_GATE: dict[str, Any] = {
    "version": "independent-visible-arc-pose-truth-v1",
    "minimumPointCount": 8,
    "minimumArcCoverageDeg": 120.0,
    "maximumMedianResidualPx": 5.0,
    "maximumP95ResidualPx": 10.0,
    "maximumMaxResidualPx": 20.0,
    "maximumLeaveOneOutCenterEquivalentAngleDeg": 1.0,
    "maximumLeaveOneOutRadiusShiftRatio": 0.02,
    "mvpMaximumAbsoluteAngleErrorDeg": 5.0,
}

ANGLE_CONVENTION: dict[str, Any] = {
    "version": "image-y-down-clockwise-signed/1",
    "origin": "circle_center",
    "xAxis": "right",
    "yAxis": "down",
    "datumRay": "positive_y_down",
    "positiveDirection": "clockwise",
    "rangeDeg": "[-180,180)",
    "targetAngleDeg": 85.0,
    "toleranceDeg": 5.0,
}

POLICY: dict[str, bool] = {
    "defaultEnabled": False,
    "developmentOnly": True,
    "authoritative": False,
    "posePromotionAllowed": False,
    "runtimeInputAllowed": False,
    "plcInputAllowed": False,
    "humanTruthAppliedAtRuntime": False,
    "thresholdTuningAllowed": False,
}


def wrap_180_deg(value: float) -> float:
    """Wrap a signed angle to [-180, 180)."""
    wrapped = (float(value) + 180.0) % 360.0 - 180.0
    return 0.0 if abs(wrapped) < 1e-12 else wrapped


def current_angle_deg(center: Iterable[float], point: Iterable[float]) -> float:
    """Return angle from the downward Y ray, clockwise positive, in image coordinates."""
    cx, cy = (float(value) for value in center)
    px, py = (float(value) for value in point)
    dx, dy = px - cx, py - cy
    if not all(math.isfinite(value) for value in (cx, cy, px, py)) or math.hypot(dx, dy) <= 1e-12:
        raise ValueError("pose point must be finite and distinct from circle center")
    return wrap_180_deg(math.degrees(math.atan2(-dx, dy)))


def image_guidance(
    current_angle: float,
    *,
    point: Iterable[float],
    center: Iterable[float],
) -> dict[str, Any]:
    """Compute image-frame guidance without authorizing a PLC command."""
    cx, cy = (float(value) for value in center)
    px, py = (float(value) for value in point)
    required_region = px <= cx and py >= cy
    within_tolerance = required_region and 80.0 <= float(current_angle) <= 90.0
    correction_raw = wrap_180_deg(85.0 - float(current_angle))
    correction = 0.0 if within_tolerance else correction_raw
    if correction > 0.0:
        direction = "CLOCKWISE"
    elif correction < 0.0:
        direction = "COUNTERCLOCKWISE"
    else:
        direction = "NONE"
    return {
        "correctionRawDeg": correction_raw,
        "correctionDeg": correction,
        "rotationDirection": direction,
        "withinTolerance": within_tolerance,
        "requiredRegionPassed": required_region,
    }


def _outside_worktree(path: Path) -> None:
    resolved = path.resolve()
    if resolved == PROJECT_ROOT or PROJECT_ROOT in resolved.parents:
        raise ValueError("output must be outside the Git worktree")


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read JSON: {path.name}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"JSON root must be an object: {path.name}")
    return payload


def _load_results(path: Path) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise ValueError(f"cannot read runtime JSONL: {path.name}") from exc
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
            image_sha = record["image"]["sha256"]
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            raise ValueError(f"invalid runtime record at line {line_number}") from exc
        if not isinstance(image_sha, str) or len(image_sha) != 64:
            raise ValueError(f"invalid runtime image SHA at line {line_number}")
        if image_sha in records:
            raise ValueError(f"duplicate runtime image SHA: {image_sha}")
        records[image_sha] = record
    return records


def _finite_points(value: Any, name: str, *, minimum: int) -> np.ndarray:
    points = np.asarray(value, dtype=np.float64)
    if points.ndim != 2 or points.shape[1:] != (2,) or len(points) < minimum or not np.isfinite(points).all():
        raise ValueError(f"{name} must contain at least {minimum} finite 2D points")
    return points


def _human_endpoint(labelme: dict[str, Any], label: str) -> np.ndarray:
    matches = [
        shape for shape in labelme.get("shapes", [])
        if isinstance(shape, dict) and shape.get("label") == label
    ]
    if len(matches) != 1 or matches[0].get("shape_type") != "point":
        raise ValueError(f"{label} must be exactly one point shape")
    points = _finite_points(matches[0].get("points"), label, minimum=1)
    if len(points) != 1:
        raise ValueError(f"{label} must contain exactly one point")
    return points[0]


def _human_arc(labelme: dict[str, Any]) -> np.ndarray | None:
    matches = [
        shape for shape in labelme.get("shapes", [])
        if isinstance(shape, dict) and shape.get("label") == ARC_LABEL
    ]
    if not matches:
        return None
    if len(matches) != 1 or matches[0].get("shape_type") != "linestrip":
        raise ValueError(f"{ARC_LABEL} must be exactly one linestrip")
    return _finite_points(matches[0].get("points"), ARC_LABEL, minimum=1)


def _circle_payload(circle: tuple[float, float, float]) -> dict[str, Any]:
    return {
        "center": {"x": float(circle[0]), "y": float(circle[1])},
        "radiusPx": float(circle[2]),
    }


def _percentile(values: Iterable[float], quantile: float) -> float:
    ordered = sorted(float(value) for value in values)
    if not ordered:
        raise ValueError("percentile requires values")
    position = (len(ordered) - 1) * float(quantile) / 100.0
    lower, upper = math.floor(position), math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def _residual(points: np.ndarray, circle: tuple[float, float, float]) -> dict[str, float]:
    values = np.abs(np.hypot(points[:, 0] - circle[0], points[:, 1] - circle[1]) - circle[2])
    return {
        "median": float(statistics.median(float(value) for value in values)),
        "p95": _percentile(values, 95.0),
        "max": float(np.max(values)),
    }


def _angular_coverage(points: np.ndarray, circle: tuple[float, float, float]) -> float:
    angles = np.sort(np.mod(np.arctan2(points[:, 1] - circle[1], points[:, 0] - circle[0]), 2.0 * math.pi))
    wrapped = np.concatenate((angles, angles[:1] + 2.0 * math.pi))
    largest_gap = float(np.max(np.diff(wrapped)))
    return float(math.degrees(2.0 * math.pi - largest_gap))


def _check(check_id: str, value: float, threshold: float, kind: str) -> dict[str, Any]:
    passed = value >= threshold if kind == "min" else value <= threshold
    return {
        "checkId": check_id,
        "value": float(value),
        "threshold": float(threshold),
        "thresholdKind": kind,
        "passed": bool(passed),
    }


def _fit_human_circle(points: np.ndarray | None) -> tuple[dict[str, Any], list[str]]:
    empty = {
        "inputReferencePresent": points is not None,
        "inputPointCount": 0 if points is None else len(points),
        "fitMethods": {
            "initial": "algorithms.hole_2.main.fit_circle_kasa",
            "refined": "algorithms.hole_2.main.robust_fit_circle+geometric_circle_fit",
        },
        "initialKasa": None,
        "refinedRobustGeometric": None,
        "initialAngularCoverageDeg": None,
        "refinedAngularCoverageDeg": None,
        "initialResidualPx": None,
        "refinedResidualPx": None,
        "stability": None,
        "qualityChecks": [],
        "failedChecks": [],
        "usable": False,
    }
    if points is None:
        empty["failedChecks"] = ["OUTER_CIRCLE_REFERENCE_MISSING"]
        return empty, list(empty["failedChecks"])
    if len(points) < 3:
        empty["failedChecks"] = ["INSUFFICIENT_ARC_POINT_COUNT"]
        return empty, list(empty["failedChecks"])
    try:
        initial = tuple(float(value) for value in fit_circle_kasa(points))
        refined = tuple(float(value) for value in robust_fit_circle(points, initial))
    except (ValueError, np.linalg.LinAlgError, FloatingPointError) as exc:
        empty["failedChecks"] = ["OUTER_CIRCLE_FIT_FAILED"]
        return empty, list(empty["failedChecks"])
    if initial[2] <= 0 or refined[2] <= 0 or not all(math.isfinite(value) for value in initial + refined):
        empty["failedChecks"] = ["OUTER_CIRCLE_FIT_FAILED"]
        return empty, list(empty["failedChecks"])

    initial_residual = _residual(points, initial)
    refined_residual = _residual(points, refined)
    initial_coverage = _angular_coverage(points, initial)
    refined_coverage = _angular_coverage(points, refined)
    leave_one_out: list[tuple[float, float, float]] = []
    if len(points) > 3:
        for index in range(len(points)):
            subset = np.delete(points, index, axis=0)
            try:
                fallback = tuple(float(value) for value in fit_circle_kasa(subset))
                fitted = tuple(float(value) for value in robust_fit_circle(subset, fallback))
            except (ValueError, np.linalg.LinAlgError, FloatingPointError):
                continue
            if fitted[2] > 0 and all(math.isfinite(value) for value in fitted):
                leave_one_out.append(fitted)
    center_shifts = [math.hypot(circle[0] - refined[0], circle[1] - refined[1]) for circle in leave_one_out]
    radius_shifts = [abs(circle[2] - refined[2]) for circle in leave_one_out]
    max_center_shift = max(center_shifts, default=refined[2])
    max_radius_shift = max(radius_shifts, default=refined[2])
    center_equivalent = math.degrees(math.atan2(max_center_shift, refined[2]))
    radius_ratio = max_radius_shift / refined[2]
    stability = {
        "leaveOneOutFitCount": len(leave_one_out),
        "initialToRefinedCenterShiftPx": math.hypot(initial[0] - refined[0], initial[1] - refined[1]),
        "initialToRefinedRadiusShiftPx": abs(initial[2] - refined[2]),
        "maximumLeaveOneOutCenterShiftPx": max_center_shift,
        "maximumLeaveOneOutCenterEquivalentAngleDeg": center_equivalent,
        "maximumLeaveOneOutRadiusShiftPx": max_radius_shift,
        "maximumLeaveOneOutRadiusShiftRatio": radius_ratio,
    }
    unique_point_count = len({(float(point[0]), float(point[1])) for point in points})
    checks = [
        _check("minimum_arc_point_count", unique_point_count, QUALITY_GATE["minimumPointCount"], "min"),
        _check("minimum_arc_coverage_deg", refined_coverage, QUALITY_GATE["minimumArcCoverageDeg"], "min"),
        _check("maximum_median_residual_px", refined_residual["median"], QUALITY_GATE["maximumMedianResidualPx"], "max"),
        _check("maximum_p95_residual_px", refined_residual["p95"], QUALITY_GATE["maximumP95ResidualPx"], "max"),
        _check("maximum_max_residual_px", refined_residual["max"], QUALITY_GATE["maximumMaxResidualPx"], "max"),
        _check("maximum_leave_one_out_center_equivalent_angle_deg", center_equivalent,
               QUALITY_GATE["maximumLeaveOneOutCenterEquivalentAngleDeg"], "max"),
        _check("maximum_leave_one_out_radius_shift_ratio", radius_ratio,
               QUALITY_GATE["maximumLeaveOneOutRadiusShiftRatio"], "max"),
    ]
    blocker_by_check = {
        "minimum_arc_point_count": "INSUFFICIENT_ARC_UNIQUE_POINT_COUNT",
        "minimum_arc_coverage_deg": "INSUFFICIENT_ARC_COVERAGE",
        "maximum_median_residual_px": "CIRCLE_MEDIAN_RESIDUAL_EXCEEDED",
        "maximum_p95_residual_px": "CIRCLE_P95_RESIDUAL_EXCEEDED",
        "maximum_max_residual_px": "CIRCLE_MAX_RESIDUAL_EXCEEDED",
        "maximum_leave_one_out_center_equivalent_angle_deg": "CIRCLE_CENTER_UNSTABLE",
        "maximum_leave_one_out_radius_shift_ratio": "CIRCLE_RADIUS_UNSTABLE",
    }
    failed = [blocker_by_check[item["checkId"]] for item in checks if not item["passed"]]
    payload = {
        "inputReferencePresent": True,
        "inputPointCount": len(points),
        "fitMethods": dict(empty["fitMethods"]),
        "initialKasa": _circle_payload(initial),
        "refinedRobustGeometric": _circle_payload(refined),
        "initialAngularCoverageDeg": initial_coverage,
        "refinedAngularCoverageDeg": refined_coverage,
        "initialResidualPx": initial_residual,
        "refinedResidualPx": refined_residual,
        "stability": stability,
        "qualityChecks": checks,
        "failedChecks": failed,
        "usable": not failed,
    }
    return payload, failed


def _runtime_candidate(record: dict[str, Any]) -> tuple[dict[str, Any], np.ndarray, tuple[float, float, float]]:
    result = record.get("result")
    diagnostics = record.get("diagnostics")
    if not isinstance(result, dict) or not isinstance(diagnostics, dict):
        raise ValueError("runtime result or diagnostics are missing")
    physical = diagnostics.get("physicalOuterCircle")
    if not isinstance(physical, dict) or physical.get("status") != "accepted":
        raise ValueError("physical outer circle is not accepted")
    circle_payload = physical.get("physicalCircle")
    if not isinstance(circle_payload, dict):
        raise ValueError("physical outer circle is missing")
    circle = (
        float(circle_payload.get("centerX")),
        float(circle_payload.get("centerY")),
        float(circle_payload.get("radiusPx")),
    )
    if circle[2] <= 0 or not all(math.isfinite(value) for value in circle):
        raise ValueError("physical outer circle is invalid")
    refinement = diagnostics.get("grooveRefinement")
    if not isinstance(refinement, dict) or refinement.get("physicalRefinementStatus") != "accepted":
        raise ValueError("groove physical refinement is not accepted")
    intersections = refinement.get("outerCircleIntersections")
    if not isinstance(intersections, list) or len(intersections) != 2:
        raise ValueError("groove refinement must contain two outer-circle intersections")
    endpoints = _finite_points(
        [[item.get("x"), item.get("y")] for item in intersections if isinstance(item, dict)],
        "runtime outer-circle intersections",
        minimum=2,
    )
    if len(endpoints) != 2:
        raise ValueError("groove refinement must contain exactly two finite intersections")
    midpoint = np.mean(endpoints, axis=0)
    source = refinement.get("sourceConsistency") or diagnostics.get("grooveSourceConsistency")
    if not isinstance(source, dict):
        raise ValueError("groove source consistency is missing")
    failed = source.get("failedChecks")
    if not isinstance(failed, list):
        raise ValueError("groove source-consistency failedChecks are missing")
    payload = {
        "topLevelValid": bool(result.get("valid")),
        "detectionStatus": result.get("detectionStatus"),
        "guidanceStatus": result.get("guidanceStatus"),
        "physicalCircle": _circle_payload(circle),
        "sourceConsistencyStatus": source.get("status"),
        "sourceConsistencyFailedChecks": [str(item) for item in failed],
    }
    return payload, midpoint, circle


def _validate_labelme(entry: dict[str, Any], validation_path: Path) -> dict[str, Any]:
    relative = entry.get("labelmeRelativePath")
    if not isinstance(relative, str) or Path(relative).is_absolute() or ".." in Path(relative).parts:
        raise ValueError("unsafe LabelMe relative path")
    path = validation_path.parent / relative
    if sha256_file(path) != entry.get("labelmeSha256"):
        raise ValueError("LabelMe SHA-256 mismatch")
    labelme = _load_json(path)
    if labelme.get("imageWidth") != entry.get("imageWidth") or labelme.get("imageHeight") != entry.get("imageHeight"):
        raise ValueError("LabelMe dimensions do not match validation")
    flags = labelme.get("flags")
    if (
        not isinstance(flags, dict)
        or not flags.get("human_verified")
        or not flags.get("independent_annotation")
        or flags.get("annotation_pending")
        or flags.get("copied_from_auto")
        or flags.get("runtime_input_allowed")
        or flags.get("threshold_tuning_allowed")
        or flags.get("plc_input_allowed")
    ):
        raise ValueError("LabelMe independent human flags are invalid")
    return labelme


def _entry(
    validation_entry: dict[str, Any],
    labelme: dict[str, Any],
    record: dict[str, Any],
) -> dict[str, Any]:
    if record.get("image", {}).get("width") != validation_entry.get("imageWidth") \
            or record.get("image", {}).get("height") != validation_entry.get("imageHeight"):
        raise ValueError("runtime image dimensions do not match validation")
    endpoints = [_human_endpoint(labelme, label) for label in ENDPOINT_LABELS]
    human_midpoint = np.mean(np.asarray(endpoints), axis=0)
    runtime_payload, candidate_midpoint, runtime_circle = _runtime_candidate(record)
    human_circle, blockers = _fit_human_circle(_human_arc(labelme))

    candidate_current = current_angle_deg(runtime_circle[:2], candidate_midpoint)
    candidate_guidance = image_guidance(candidate_current, point=candidate_midpoint, center=runtime_circle[:2])
    initial_circle_payload = human_circle["initialKasa"]
    refined_circle_payload = human_circle["refinedRobustGeometric"]

    def circle_tuple(payload: dict[str, Any] | None) -> tuple[float, float, float] | None:
        if payload is None:
            return None
        return payload["center"]["x"], payload["center"]["y"], payload["radiusPx"]

    initial_circle = circle_tuple(initial_circle_payload)
    refined_circle = circle_tuple(refined_circle_payload)
    human_initial = current_angle_deg(initial_circle[:2], human_midpoint) if initial_circle else None
    human_refined = current_angle_deg(refined_circle[:2], human_midpoint) if refined_circle else None
    initial_guidance = image_guidance(human_initial, point=human_midpoint, center=initial_circle[:2]) if initial_circle else None
    refined_guidance = image_guidance(human_refined, point=human_midpoint, center=refined_circle[:2]) if refined_circle else None
    diagnostic = {
        "finalTruth": False,
        "humanCurrentAngleFromInitialKasaDeg": human_initial,
        "humanCurrentAngleFromRefinedDeg": human_refined,
        "candidateCurrentAngleDeg": candidate_current,
        "candidateMinusInitialKasaDeg": wrap_180_deg(candidate_current - human_initial) if human_initial is not None else None,
        "candidateMinusRefinedDeg": wrap_180_deg(candidate_current - human_refined) if human_refined is not None else None,
        "humanInitialGuidance": initial_guidance,
        "humanRefinedGuidance": refined_guidance,
        "candidateGuidance": candidate_guidance,
    }
    circle_comparison = None
    final_pose = None
    if human_circle["usable"] and refined_circle is not None and human_refined is not None and refined_guidance is not None:
        circle_comparison = {
            "centerErrorPx": math.hypot(runtime_circle[0] - refined_circle[0], runtime_circle[1] - refined_circle[1]),
            "radiusAbsoluteErrorPx": abs(runtime_circle[2] - refined_circle[2]),
        }
        error = wrap_180_deg(candidate_current - human_refined)
        final_pose = {
            "humanCurrentAngleDeg": human_refined,
            "candidateCurrentAngleDeg": candidate_current,
            "candidateMinusHumanErrorDeg": error,
            "absoluteAngleErrorDeg": abs(error),
            "humanGuidance": refined_guidance,
            "candidateGuidance": candidate_guidance,
            "candidateGeometryWithinMvpWindow": abs(error) <= QUALITY_GATE["mvpMaximumAbsoluteAngleErrorDeg"],
        }
    return {
        "imageId": validation_entry["imageId"],
        "sourceImageSha256": validation_entry["sourceImageSha256"],
        "humanLabelmeSha256": validation_entry["labelmeSha256"],
        "evaluationStatus": "EVALUATED" if final_pose is not None else "NOT_EVALUATED",
        "blockers": blockers,
        "humanCircle": human_circle,
        "runtimeCandidate": runtime_payload,
        "diagnosticOnly": diagnostic,
        "circleComparison": circle_comparison,
        "finalPose": final_pose,
    }


def _stable_floats(value: Any) -> Any:
    """Remove platform-only floating tails before validating and serializing."""
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("report contains a non-finite value")
        rounded = round(value, 12)
        return 0.0 if rounded == 0.0 else rounded
    if isinstance(value, dict):
        return {key: _stable_floats(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_stable_floats(item) for item in value]
    return value


def build_clean_groove_pose_truth_evaluation(
    validation_path: Path,
    results_path: Path,
    output_path: Path,
) -> dict[str, Any]:
    """Build a SHA-bound, fail-closed offline evaluation report."""
    validation_path, results_path, output_path = map(Path, (validation_path, results_path, output_path))
    _outside_worktree(output_path)
    if output_path.exists():
        raise ValueError("output must not already exist")
    validation = _load_json(validation_path)
    if validation.get("schemaVersion") != "clean-groove-pixel-review/1" or validation.get("artifactType") != "VALIDATION":
        raise ValueError("validation must be clean-groove-pixel-review/1 VALIDATION")
    if validation.get("semanticAuthority") != "FINAL_HUMAN_CLARIFICATION_A":
        raise ValueError("validation must preserve FINAL_HUMAN_CLARIFICATION_A authority")
    counts = validation.get("counts")
    entries = validation.get("entries")
    if not isinstance(counts, dict) or counts.get("pending") != 0:
        raise ValueError("validation must have pending=0")
    if not isinstance(entries, list) or not entries:
        raise ValueError("validation entries are missing")
    truth_policy = validation.get("truthPolicy")
    if (
        not isinstance(truth_policy, dict)
        or truth_policy.get("autoGeometryParsed")
        or truth_policy.get("autoCoordinatesCopied")
        or truth_policy.get("accuracyEvaluationAllowed")
        or truth_policy.get("thresholdTuningAllowed")
        or truth_policy.get("runtimeInputAllowed")
        or truth_policy.get("plcInputAllowed")
    ):
        raise ValueError("validation truth policy is unsafe")
    results = _load_results(results_path)
    report_entries: list[dict[str, Any]] = []
    seen: set[str] = set()
    for validation_entry in entries:
        if not isinstance(validation_entry, dict):
            raise ValueError("validation entry must be an object")
        image_id = validation_entry.get("imageId")
        if not isinstance(image_id, str) or "part-006" in image_id:
            raise ValueError("sealed sample part-006 is forbidden")
        image_sha = validation_entry.get("sourceImageSha256")
        if not isinstance(image_sha, str) or len(image_sha) != 64 or image_sha in seen:
            raise ValueError("duplicate or invalid validation image SHA")
        seen.add(image_sha)
        if (
            not validation_entry.get("wallEndpointPixelReviewComplete")
            or not validation_entry.get("wallPixelTruthAvailable")
            or not validation_entry.get("endpointPixelTruthAvailable")
            or validation_entry.get("validationErrors") != []
        ):
            raise ValueError("entry is not WALL_ENDPOINT_COMPLETE")
        labelme = _validate_labelme(validation_entry, validation_path)
        record = results.get(image_sha)
        if record is None:
            raise ValueError(f"missing runtime image SHA: {image_sha}")
        report_entries.append(_entry(validation_entry, labelme, record))

    report = {
        "schemaVersion": "clean-groove-pose-truth-evaluation/1",
        "artifactType": "DIAGNOSTIC",
        "sourceValidationSha256": sha256_file(validation_path),
        "sourceResultsSha256": sha256_file(results_path),
        "qualityGate": dict(QUALITY_GATE),
        "angleConvention": dict(ANGLE_CONVENTION),
        "entries": report_entries,
        "summary": {
            "imageCount": len(report_entries),
            "evaluatedCount": sum(item["evaluationStatus"] == "EVALUATED" for item in report_entries),
            "notEvaluatedCount": sum(item["evaluationStatus"] == "NOT_EVALUATED" for item in report_entries),
            "humanCircleUsableCount": sum(item["humanCircle"]["usable"] for item in report_entries),
            "candidateGeometryWithinMvpWindowCount": sum(
                bool(item["finalPose"] and item["finalPose"]["candidateGeometryWithinMvpWindow"])
                for item in report_entries
            ),
        },
        "policy": dict(POLICY),
    }
    report = _stable_floats(report)
    try:
        import jsonschema

        jsonschema.Draft202012Validator(_load_json(SCHEMA_PATH)).validate(report)
    except ImportError:
        pass
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return report
