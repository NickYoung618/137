#!/usr/bin/env python3
"""Export offline AUTO LabelMe diagnostics anchored to one manual reference sample."""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.dataset_common import safe_relative_path, sha256_file, write_json
from tools.render_slot_pose_review import load_results


REFERENCE_SCHEMA_VERSION = "slot-pose-development-reference/1"
INDEX_SCHEMA_VERSION = "reference-anchored-slot-pose-diagnostics/1"
INDEX_SCHEMA_VERSION_V2 = "reference-anchored-slot-pose-diagnostics/2"
COMPARISON_MEANING = "OBSERVATION_ONLY_NOT_ACCURACY_ERROR"
HUMAN_TRUTH_LABELS = {
    "physical_outer_circle_truth",
    "physical_outer_circle_visible_arc_manual",
    "target_groove_open_boundary_manual",
}


def _object(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be an object")
    return value


def _sha(value: Any, name: str) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise ValueError(f"{name} must be a lowercase SHA-256")
    return value


def _number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise ValueError(f"{name} must be finite")
    return float(value)


def _nullable_number(value: Any) -> float | None:
    return None if value is None else _number(value, "diagnostic number")


def _circular_delta(value: float, reference: float) -> float:
    return (float(value) - float(reference) + 180.0) % 360.0 - 180.0


def _require_external(path: Path) -> None:
    try:
        path.resolve().relative_to(PROJECT_ROOT.resolve())
    except ValueError:
        return
    raise ValueError("reference diagnostic outputs must stay outside the Git worktree")


def build_development_reference(
    manual_review: dict[str, Any],
    comparison: dict[str, Any],
    *,
    actual_manual_record_sha256: str | None = None,
    actual_comparison_record_sha256: str | None = None,
) -> dict[str, Any]:
    """Build a hash-locked reference that is valid for its one source image only."""
    if manual_review.get("schemaVersion") != "manual-groove-pose-review/1":
        raise ValueError("manual review schema is unsupported")
    if comparison.get("schemaVersion") != "slot-pose-reference-comparison/1" or comparison.get("status") != "COMPARED":
        raise ValueError("reference comparison must be a completed v1 comparison")
    if comparison.get("referenceStatus") != "DEVELOPMENT_REFERENCE":
        raise ValueError("reference comparison is not development reference evidence")
    if comparison.get("productionAccuracyClaimed") is not False or comparison.get("runtimeInputAllowed") is not False:
        raise ValueError("reference comparison has unsafe truth/runtime flags")
    algorithm = _object(manual_review.get("algorithm"), "manual algorithm")
    if algorithm.get("runtimeInputAllowed") is not False:
        raise ValueError("manual review must forbid runtime input")
    manual_source = _object(manual_review.get("source"), "manual source")
    comparison_source = _object(comparison.get("source"), "comparison source")
    pairs = (
        ("imageSha256", manual_source.get("imageSha256"), comparison_source.get("imageSha256"), "image hash"),
        ("annotationSha256", manual_source.get("annotationSha256"), comparison_source.get("annotationSha256"), "annotation hash"),
        ("circleFitSourceSha256", algorithm.get("circleFitSourceSha256"), comparison_source.get("circleFitSourceSha256"), "circle-fit source hash"),
    )
    locked: dict[str, str] = {}
    for key, manual_value, comparison_value, label in pairs:
        left, right = _sha(manual_value, f"manual {label}"), _sha(comparison_value, f"comparison {label}")
        if left != right:
            raise ValueError(f"{label} mismatch between manual review and comparison")
        locked[key] = left
    manual_record_hash = _sha(comparison_source.get("manualRecordSha256"), "manual record hash")
    if actual_manual_record_sha256 is not None and _sha(actual_manual_record_sha256, "actual manual record hash") != manual_record_hash:
        raise ValueError("manual record file hash mismatch")
    comparison_record_hash = (
        None if actual_comparison_record_sha256 is None
        else _sha(actual_comparison_record_sha256, "actual comparison record hash")
    )
    circle = _object(manual_review.get("circle"), "manual circle")
    if circle.get("status") != "accepted":
        raise ValueError("manual reference circle is not accepted")
    manual_circle = _object(circle.get("refinedRobustGeometricCircle"), "manual refined circle")
    residual = _object(circle.get("refinedResidualPx"), "manual circle residual")
    measurement = _object(manual_review.get("measurement"), "manual measurement")
    y_down = _object(manual_review.get("yDownTargetDiagnostic"), "manual Y-down diagnostic")
    datum = _object(y_down.get("datumMeasurement"), "manual Y-down measurement")
    assessment = _object(y_down.get("targetAssessment"), "manual target assessment")
    circle_delta = _object(comparison.get("circleDelta"), "same-image circle delta")
    groove_delta = _object(comparison.get("grooveOpeningDelta"), "same-image groove delta")
    return {
        "schemaVersion": REFERENCE_SCHEMA_VERSION,
        "scope": "DEVELOPMENT_REFERENCE_ONLY",
        "source": {
            **locked,
            "manualRecordSha256": manual_record_hash,
            "runtimeRecordSha256": _sha(comparison_source.get("runtimeRecordSha256"), "runtime record hash"),
            "comparisonRecordSha256": comparison_record_hash,
        },
        "manualCircle": {
            "centerX": _number(manual_circle.get("centerX"), "manual circle centerX"),
            "centerY": _number(manual_circle.get("centerY"), "manual circle centerY"),
            "radiusPx": _number(manual_circle.get("radiusPx"), "manual circle radius"),
            "pointCount": int(circle.get("pointCount")),
            "angularCoverageDeg": _number(circle.get("angularCoverageDeg"), "manual circle coverage"),
            "residualPx": {key: _number(residual.get(key), f"manual residual {key}") for key in ("median", "p95", "max")},
        },
        "manualMeasurements": {
            "imageUpClockwiseDeg": _number(measurement.get("openingCenterAzimuthImageDeg"), "manual image-up angle"),
            "yDownSignedDeg": _number(datum.get("measuredFromPositiveYClockwiseDeg"), "manual Y-down angle"),
            "quadrant": str(measurement.get("quadrant")),
        },
        "sameImageAutomaticDifference": {
            "circleCenterDistancePx": _number(circle_delta.get("centerDistancePx"), "circle center difference"),
            "radiusAbsolutePx": _number(circle_delta.get("radiusAbsolutePx"), "circle radius difference"),
            "openingCircularDeg": _number(groove_delta.get("automaticMinusManualCircularDeg"), "opening circular difference"),
            "openingAbsoluteCircularDeg": _number(groove_delta.get("absoluteCircularDeg"), "opening absolute difference"),
        },
        "targetContract": _object(assessment.get("targetContract"), "target contract"),
        "runtimeInputAllowed": False,
        "productionAccuracyClaimed": False,
        "appliesAsAccuracyTruthToOtherImages": False,
    }


def _safe_name(index: int, image_id: str, relative: Path) -> str:
    stem = re.sub(r"[^A-Za-z0-9._-]+", "-", f"{index:04d}-{image_id}-{relative.stem}").strip("-.")
    return (stem[:150] or f"diagnostic-{index:04d}") + ".json"


def _point_dict(point: Any) -> tuple[float, float] | None:
    if not isinstance(point, dict):
        return None
    try:
        return _number(point.get("x"), "point x"), _number(point.get("y"), "point y")
    except ValueError:
        return None


def _point_list(points: Any) -> list[list[float]]:
    output: list[list[float]] = []
    if not isinstance(points, list):
        return output
    for point in points:
        if not isinstance(point, list) or len(point) != 2:
            continue
        try:
            output.append([_number(point[0], "point x"), _number(point[1], "point y")])
        except ValueError:
            continue
    return output


def _shape(label: str, shape_type: str, points: list[list[float]], *, group_id: int | None = None) -> dict[str, Any]:
    if not label.startswith("AUTO_") or label in HUMAN_TRUTH_LABELS:
        raise ValueError("automatic diagnostic label must use the AUTO_ namespace")
    return {
        "label": label, "points": points, "group_id": group_id,
        "description": "algorithm generated diagnostic only; not human truth",
        "shape_type": shape_type, "flags": {"algorithm_generated": True, "formal_truth": False},
    }


def _auto_shapes(result: dict[str, Any]) -> list[dict[str, Any]]:
    diagnostics = _object(result.get("diagnostics") or {}, "result diagnostics")
    shapes: list[dict[str, Any]] = []
    physical = diagnostics.get("physicalOuterCircle") or {}
    circle = physical.get("physicalCircle") if physical.get("status") == "accepted" else None
    if isinstance(circle, dict):
        cx = _number(circle.get("centerX"), "circle centerX")
        cy = _number(circle.get("centerY"), "circle centerY")
        radius = _number(circle.get("radiusPx"), "circle radius")
        if radius > 0.0:
            shapes.append(_shape("AUTO_detected_physical_outer_circle", "circle", [[cx, cy], [cx + radius, cy]], group_id=1))
    refinement = diagnostics.get("grooveRefinement") or {}
    if refinement.get("status") == "accepted":
        intersections = [_point_dict(point) for point in refinement.get("outerCircleIntersections") or []]
        if len(intersections) == 2 and all(point is not None for point in intersections):
            shapes.append(_shape(
                "AUTO_detected_groove_opening", "line",
                [[float(point[0]), float(point[1])] for point in intersections if point is not None], group_id=2,
            ))
        for side_index, side_name in enumerate(("startSide", "endSide"), start=3):
            side = refinement.get(side_name) or {}
            support = _point_list(side.get("points"))
            if len(support) >= 2:
                shapes.append(_shape(f"AUTO_{side_name}_inliers", "linestrip", support, group_id=side_index))
            for point_index, point in enumerate(_point_list(side.get("rejectedPoints")), start=1):
                shapes.append(_shape(f"AUTO_{side_name}_rejected_{point_index:03d}", "point", [point], group_id=side_index))
    pose = diagnostics.get("singleGroovePose") or {}
    datum = pose.get("datumMeasurement") or {}
    center = _point_dict(datum.get("center"))
    opening = _point_dict(datum.get("grooveOpeningPoint"))
    if pose.get("geometryValid") is True and center is not None and opening is not None:
        shapes.append(_shape(
            "AUTO_detected_groove_radial_axis", "line",
            [[center[0], center[1]], [opening[0], opening[1]]], group_id=2,
        ))
    return shapes


def export_diagnostics(
    manifest: dict[str, Any],
    results: list[dict[str, Any]],
    data_root: Path,
    reference: dict[str, Any],
    output_dir: Path,
) -> dict[str, Any]:
    output_dir = output_dir.resolve()
    _require_external(output_dir)
    if reference.get("schemaVersion") != REFERENCE_SCHEMA_VERSION or reference.get("runtimeInputAllowed") is not False:
        raise ValueError("development reference is invalid or runtime-unsafe")
    dataset_id = str(manifest.get("datasetId") or "")
    if not dataset_id:
        raise ValueError("manifest datasetId is required")
    result_by_task: dict[str, dict[str, Any]] = {}
    for result in results:
        task_id = str(result.get("taskId") or "")
        if task_id in result_by_task:
            raise ValueError(f"duplicate taskId: {task_id}")
        result_by_task[task_id] = result
    validated: list[tuple[int, dict[str, Any], Path, Path, dict[str, Any]]] = []
    expected_tasks: set[str] = set()
    data_root = data_root.resolve()
    labelme_dir = output_dir / "labelme-auto"
    for index, item in enumerate(manifest.get("images") or [], start=1):
        relative = safe_relative_path(str(item.get("relativePath") or ""))
        image_path = data_root / relative
        if not image_path.is_file():
            raise ValueError(f"missing image: {relative.as_posix()}")
        image_hash = sha256_file(image_path)
        if image_hash != item.get("sha256"):
            raise ValueError(f"manifest image hash mismatch: {relative.as_posix()}")
        task_id = f"{dataset_id}:{item['imageId']}"
        expected_tasks.add(task_id)
        result = result_by_task.get(task_id)
        if result is None:
            raise ValueError(f"missing result for {task_id}")
        result_hash = (result.get("image") or {}).get("sha256")
        if result_hash != image_hash:
            raise ValueError(f"result image hash mismatch for {task_id}")
        annotation_relative = Path("labelme-auto") / _safe_name(index, str(item["imageId"]), relative)
        validated.append((index, item, relative, annotation_relative, result))
    unexpected = sorted(set(result_by_task) - expected_tasks)
    if unexpected:
        raise ValueError(f"unexpected result taskIds: {unexpected}")

    output_dir.mkdir(parents=True, exist_ok=True)
    labelme_dir.mkdir(parents=True, exist_ok=True)
    write_json(output_dir / "development-reference.json", reference)
    records: list[dict[str, Any]] = []
    uses_closed_loop_guidance = any(
        isinstance((((result.get("diagnostics") or {}).get("singleGroovePose") or {}).get("guidance")), dict)
        for *_, result in validated
    )
    reference_angle = _number(reference["manualMeasurements"]["yDownSignedDeg"], "reference Y-down angle")
    for _, item, relative, annotation_relative, result in validated:
        annotation_path = output_dir / annotation_relative
        image_path = data_root / relative
        diagnostics = result.get("diagnostics") or {}
        pose = diagnostics.get("singleGroovePose") or {}
        datum = pose.get("datumMeasurement") or {}
        assessment = pose.get("targetAssessment") or {}
        guidance = pose.get("guidance") or {}
        measured = _nullable_number(datum.get("measuredFromPositiveYClockwiseDeg"))
        position = datum.get("position") or {}
        quadrant = None
        if position:
            quadrant = f"{position.get('vertical')}_{position.get('horizontal')}"
        error = result.get("error") or {}
        payload = {
            "version": "5.0.1",
            "flags": {
                "algorithm_generated": True, "diagnostic_only": True,
                "human_verified": False, "independent_from_algorithm": False,
                "formal_truth": False, "runtime_input_allowed": False,
                "annotation_version": (
                    "slot-pose-auto-diagnostic-v2" if guidance else "slot-pose-auto-diagnostic-v1"
                ),
            },
            "shapes": _auto_shapes(result),
            "imagePath": os.path.relpath(image_path, annotation_path.parent),
            "imageData": None,
            "imageHeight": int(item["height"]), "imageWidth": int(item["width"]),
        }
        if Path(payload["imagePath"]).is_absolute():
            raise ValueError("exported LabelMe imagePath must be relative")
        write_json(annotation_path, payload)
        records.append({
            "imageId": item["imageId"], "relativeImagePath": relative.as_posix(),
            "imageSha256": item["sha256"],
            "autoAnnotationRelativePath": annotation_relative.as_posix(),
            "autoAnnotationSha256": sha256_file(annotation_path),
            "detectionErrorCode": error.get("code"), "detectionErrorStage": error.get("stage"),
            "formalMechanicalAngleDeg": (
                (guidance.get("plcExecution") or {}).get("mechanicalCorrectionDeg")
                if guidance else (result.get("result") or {}).get("signedRelativeRotationDeg")
            ),
            "measuredYDownDeg": measured, "quadrant": quadrant,
            "targetToleranceStatus": assessment.get("toleranceStatus"),
            "targetPositionGatePassed": assessment.get("positionGatePassed"),
            "targetAngleTolerancePassed": assessment.get("angleTolerancePassed"),
            "developmentReferenceYDownDeg": reference_angle,
            "observedCircularDeltaToReferenceDeg": None if measured is None else _circular_delta(measured, reference_angle),
            "comparisonMeaning": COMPARISON_MEANING,
            "accuracyStatus": "NOT_EVALUATED",
            "detectionStatus": guidance.get("detectionStatus"),
            "guidanceStatus": guidance.get("guidanceStatus"),
            "targetAngleDeg": guidance.get("targetAngleDeg"),
            "toleranceDeg": guidance.get("toleranceDeg"),
            "correctionRawDeg": guidance.get("correctionRawDeg"),
            "imageFrameCorrectionDeg": guidance.get("imageFrameCorrectionDeg"),
            "rotationDirection": guidance.get("rotationDirection"),
            "withinTolerance": guidance.get("withinTolerance"),
            "plcExecutionStatus": (guidance.get("plcExecution") or {}).get("status"),
        })
    policy = manifest.get("policy") if isinstance(manifest.get("policy"), dict) else {}
    index_payload = {
        "schemaVersion": INDEX_SCHEMA_VERSION_V2 if uses_closed_loop_guidance else INDEX_SCHEMA_VERSION,
        "datasetId": dataset_id, "datasetFingerprint": manifest.get("datasetFingerprint"),
        "imageCount": len(records),
        "reference": {
            "schemaVersion": reference["schemaVersion"], "scope": reference["scope"],
            "imageSha256": reference["source"]["imageSha256"],
            "manualYDownSignedDeg": reference_angle,
            "comparisonMeaning": COMPARISON_MEANING,
        },
        "evaluation": {
            "accuracyStatus": "NOT_EVALUATED", "accuracyReason": "PER_IMAGE_HUMAN_TRUTH_UNAVAILABLE",
            "staticRepeatabilityStatus": "NOT_EVALUATED",
            "staticRepeatabilityReason": (
                "GROUPING_NOT_EXPLICIT" if policy.get("groupingExplicit") is not True
                else "PER_IMAGE_HUMAN_TRUTH_UNAVAILABLE"
            ),
            "productionAccuracyClaimed": False,
        },
        "records": records,
    }
    write_json(output_dir / "diagnostic-index.json", index_payload)
    with (output_dir / "diagnostics.csv").open("w", newline="", encoding="utf-8") as handle:
        fields = [
            "image_id", "relative_image_path", "auto_annotation_relative_path", "detection_error_code",
            "detection_error_stage", "formal_mechanical_angle_deg", "measured_y_down_deg", "quadrant",
            "target_tolerance_status", "development_reference_y_down_deg",
            "observed_circular_delta_to_reference_deg", "comparison_meaning", "accuracy_status",
            "detection_status", "guidance_status", "target_angle_deg", "tolerance_deg",
            "correction_raw_deg", "image_frame_correction_deg", "rotation_direction",
            "within_tolerance", "plc_execution_status",
        ]
        writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader()
        for record in records:
            writer.writerow({
                "image_id": record["imageId"], "relative_image_path": record["relativeImagePath"],
                "auto_annotation_relative_path": record["autoAnnotationRelativePath"],
                "detection_error_code": record["detectionErrorCode"],
                "detection_error_stage": record["detectionErrorStage"],
                "formal_mechanical_angle_deg": record["formalMechanicalAngleDeg"],
                "measured_y_down_deg": record["measuredYDownDeg"], "quadrant": record["quadrant"],
                "target_tolerance_status": record["targetToleranceStatus"],
                "development_reference_y_down_deg": record["developmentReferenceYDownDeg"],
                "observed_circular_delta_to_reference_deg": record["observedCircularDeltaToReferenceDeg"],
                "comparison_meaning": record["comparisonMeaning"], "accuracy_status": record["accuracyStatus"],
                "detection_status": record["detectionStatus"],
                "guidance_status": record["guidanceStatus"],
                "target_angle_deg": record["targetAngleDeg"],
                "tolerance_deg": record["toleranceDeg"],
                "correction_raw_deg": record["correctionRawDeg"],
                "image_frame_correction_deg": record["imageFrameCorrectionDeg"],
                "rotation_direction": record["rotationDirection"],
                "within_tolerance": record["withinTolerance"],
                "plc_execution_status": record["plcExecutionStatus"],
            })
    return index_payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--results", required=True, type=Path)
    parser.add_argument("--data-root", required=True, type=Path)
    parser.add_argument("--manual-review", required=True, type=Path)
    parser.add_argument("--reference-comparison", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    try:
        manual = json.loads(args.manual_review.read_text(encoding="utf-8"))
        comparison = json.loads(args.reference_comparison.read_text(encoding="utf-8"))
        reference = build_development_reference(
            manual, comparison,
            actual_manual_record_sha256=sha256_file(args.manual_review),
            actual_comparison_record_sha256=sha256_file(args.reference_comparison),
        )
        index = export_diagnostics(
            json.loads(args.manifest.read_text(encoding="utf-8")), load_results(args.results),
            args.data_root, reference, args.output_dir,
        )
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(
        f"Exported {index['imageCount']} AUTO LabelMe diagnostics: "
        f"accuracy={index['evaluation']['accuracyStatus']} "
        f"static_repeatability={index['evaluation']['staticRepeatabilityStatus']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
