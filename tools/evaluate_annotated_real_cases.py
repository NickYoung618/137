#!/usr/bin/env python3
"""Strictly compare reviewed same-image LabelMe truth with runtime detections."""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
import sys
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageFont

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from algorithms.slot_pose.angular_profile import circular_delta_deg
from algorithms.slot_pose.contract import load_config
from algorithms.slot_pose.legacy_adapter import LegacyAEndFaceAdapter
from tools.dataset_common import safe_relative_path, sha256_file, write_json
from tools.render_slot_pose_review import load_results
from tools.review_labelme_groove_pose import DEFAULT_REVIEW_CONFIG, analyze_manual_groove_geometry


CIRCLE_LABELS = {"physical_outer_circle_truth", "physical_outer_circle_visible_arc_manual"}
GROOVE_LABEL = "target_groove_open_boundary_manual"


def _percentile(values: list[float], quantile: float) -> float:
    ordered = sorted(float(value) for value in values)
    position = (len(ordered) - 1) * quantile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def compute_static_repeatability(
    manifest: dict[str, Any], records: list[dict[str, Any]], *, configured_min_repeats: int,
) -> dict[str, Any]:
    policy = manifest.get("policy") if isinstance(manifest.get("policy"), dict) else {}
    if policy.get("groupingExplicit") is not True:
        return {
            "schemaVersion": "slot-pose-static-repeatability/1",
            "status": "NOT_EVALUATED", "reason": "GROUPING_NOT_EXPLICIT",
            "metricSource": "circular_detection_minus_human_truth_residual",
            "groups": [], "limitStatus": "NOT_EVALUATED",
        }
    expected = policy.get("expectedRepeatsPerGroup")
    if isinstance(expected, bool) or not isinstance(expected, int) or expected <= 0:
        expected = int(configured_min_repeats)
    record_by_id = {str(record["imageId"]): record for record in records}
    grouped: dict[tuple[str, str, str, str], list[str]] = {}
    incomplete_ids: list[str] = []
    for item in manifest.get("images") or []:
        values = tuple(str(item.get(key) or "") for key in ("split", "sampleId", "position", "conditionId"))
        if any(not value or value == "unknown" for value in values):
            incomplete_ids.append(str(item.get("imageId")))
            continue
        grouped.setdefault(values, []).append(str(item["imageId"]))
    groups: list[dict[str, Any]] = []
    for key, image_ids in sorted(grouped.items()):
        residuals = [
            float(record_by_id[image_id]["difference"]["measuredAngleCircularDeg"])
            for image_id in image_ids
            if image_id in record_by_id
            and record_by_id[image_id].get("evaluationEligible") is True
            and isinstance((record_by_id[image_id].get("difference") or {}).get("measuredAngleCircularDeg"), (int, float))
        ]
        base = {
            "groupKey": {"split": key[0], "sampleId": key[1], "position": key[2], "conditionId": key[3]},
            "expectedRepeatCount": expected,
            "manifestFrameCount": len(image_ids),
            "validRepeatCount": len(residuals),
            "metricSource": "circular_detection_minus_human_truth_residual",
            "residualCircularRangeDeg": None,
            "residualStdDeg": None,
            "residualAbsoluteDeviationP95Deg": None,
            "toleranceStatus": "NOT_EVALUATED",
        }
        if len(residuals) < expected:
            groups.append({**base, "status": "NOT_EVALUATED", "reason": "INSUFFICIENT_REVIEWED_VALID_REPEATS"})
            continue
        radians = [math.radians(value) for value in residuals]
        mean = math.degrees(math.atan2(
            sum(math.sin(value) for value in radians), sum(math.cos(value) for value in radians),
        ))
        centered = [circular_delta_deg(value, mean) for value in residuals]
        groups.append({
            **base,
            "status": "EVALUATED", "reason": None,
            "circularResidualMeanDeg": mean,
            "residualCircularRangeDeg": max(centered) - min(centered),
            "residualStdDeg": statistics.pstdev(centered),
            "residualAbsoluteDeviationP95Deg": _percentile([abs(value) for value in centered], 0.95),
        })
    evaluated = sum(group["status"] == "EVALUATED" for group in groups)
    if not evaluated:
        reason = "GROUP_METADATA_INCOMPLETE" if incomplete_ids and not groups else "NO_COMPLETE_STATIC_GROUP"
        status = "NOT_EVALUATED"
    else:
        reason = None
        status = "EVALUATED"
    return {
        "schemaVersion": "slot-pose-static-repeatability/1",
        "status": status, "reason": reason,
        "metricSource": "circular_detection_minus_human_truth_residual",
        "expectedRepeatsPerGroup": expected,
        "evaluatedGroupCount": evaluated,
        "totalGroupCount": len(groups),
        "incompleteMetadataImageCount": len(incomplete_ids),
        "groups": groups,
        "limitStatus": "NOT_EVALUATED",
        "limitReason": "QUALITY_REPEATABILITY_LIMIT_UNCONFIRMED",
    }


def _finite_points(points: Any) -> bool:
    return (
        isinstance(points, list)
        and all(
            isinstance(point, list) and len(point) == 2
            and all(
                not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(float(value))
                for value in point
            )
            for point in points
        )
    )


def annotation_eligibility(
    payload: dict[str, Any],
    entry: dict[str, Any],
    *,
    actual_image_sha256: str,
    actual_annotation_sha256: str,
) -> list[str]:
    reasons: list[str] = []
    flags = payload.get("flags") if isinstance(payload.get("flags"), dict) else {}
    if entry.get("reviewStatus") != "reviewed":
        reasons.append("REVIEW_STATUS_NOT_REVIEWED")
    if flags.get("human_verified") is not True or entry.get("humanVerified") is not True:
        reasons.append("HUMAN_VERIFICATION_REQUIRED")
    if flags.get("independent_from_algorithm") is not True or entry.get("independentFromAlgorithm") is not True:
        reasons.append("INDEPENDENT_ANNOTATION_REQUIRED")
    if flags.get("formal_truth") is not True:
        reasons.append("FORMAL_TRUTH_REQUIRED")
    if flags.get("runtime_input_allowed") is not False:
        reasons.append("RUNTIME_TRUTH_LEAKAGE_RISK")
    annotator = entry.get("annotator")
    reviewer = entry.get("reviewer")
    if not isinstance(annotator, str) or not annotator.strip():
        reasons.append("ANNOTATOR_REQUIRED")
    if not isinstance(reviewer, str) or not reviewer.strip():
        reasons.append("REVIEWER_REQUIRED")
    if isinstance(annotator, str) and isinstance(reviewer, str) and annotator.strip() == reviewer.strip():
        reasons.append("INDEPENDENT_REVIEWER_REQUIRED")
    if entry.get("imageSha256") != actual_image_sha256:
        reasons.append("IMAGE_HASH_MISMATCH")
    if entry.get("annotationSha256") != actual_annotation_sha256:
        reasons.append("ANNOTATION_HASH_MISMATCH")
    shapes = payload.get("shapes") if isinstance(payload.get("shapes"), list) else []
    circle_shapes = [shape for shape in shapes if shape.get("label") in CIRCLE_LABELS]
    groove_shapes = [shape for shape in shapes if shape.get("label") == GROOVE_LABEL]
    if len(circle_shapes) != 1:
        reasons.append("PHYSICAL_CIRCLE_TRUTH_REQUIRED")
    else:
        circle = circle_shapes[0]
        points = circle.get("points")
        if not _finite_points(points):
            reasons.append("CIRCLE_FINITE_POINTS")
        elif circle.get("shape_type") == "circle" and len(points) != 2:
            reasons.append("CIRCLE_POINT_COUNT")
        elif circle.get("shape_type") == "linestrip" and len(points) < 8:
            reasons.append("CIRCLE_POINT_COUNT")
        elif circle.get("shape_type") not in {"circle", "linestrip"}:
            reasons.append("CIRCLE_SHAPE_TYPE")
    if len(groove_shapes) != 1:
        reasons.append("GROOVE_TRUTH_REQUIRED")
    else:
        groove = groove_shapes[0]
        if groove.get("shape_type") != "linestrip":
            reasons.append("GROOVE_SHAPE_TYPE")
        if not _finite_points(groove.get("points")):
            reasons.append("GROOVE_FINITE_POINTS")
        elif len(groove["points"]) < 6:
            reasons.append("GROOVE_POINT_COUNT")
    return list(dict.fromkeys(reasons))


def _circle_points(shape: dict[str, Any]) -> list[list[float]]:
    points = shape["points"]
    if shape["shape_type"] == "linestrip":
        return points
    center = np.asarray(points[0], dtype=float)
    radius = float(np.linalg.norm(np.asarray(points[1], dtype=float) - center))
    if not math.isfinite(radius) or radius <= 0.0:
        raise ValueError("manual circle radius must be positive")
    return [
        [float(center[0] + radius * math.cos(angle)), float(center[1] + radius * math.sin(angle))]
        for angle in np.linspace(0.0, 2.0 * math.pi, 72, endpoint=False)
    ]


def _automatic_values(result: dict[str, Any]) -> dict[str, Any]:
    diagnostics = result.get("diagnostics") or {}
    physical = (diagnostics.get("physicalOuterCircle") or {}).get("physicalCircle")
    pose = diagnostics.get("singleGroovePose") or {}
    datum = pose.get("datumMeasurement") or {}
    position = datum.get("position") or {}
    assessment = pose.get("targetAssessment") or {}
    refinement = diagnostics.get("grooveRefinement") or {}
    return {
        "circle": physical,
        "measuredYDownDeg": datum.get("measuredFromPositiveYClockwiseDeg"),
        "quadrant": (
            None if not position else f"{position.get('vertical')}_{position.get('horizontal')}"
        ),
        "targetToleranceStatus": assessment.get("toleranceStatus"),
        "openingIntersections": refinement.get("outerCircleIntersections"),
        "radialAxis": (
            {"from": datum.get("center"), "to": datum.get("grooveOpeningPoint")}
            if isinstance(datum.get("center"), dict) and isinstance(datum.get("grooveOpeningPoint"), dict)
            else None
        ),
        "errorCode": (result.get("error") or {}).get("code"),
        "errorStage": (result.get("error") or {}).get("stage"),
    }


def _comparison_record(item: dict[str, Any], entry: dict[str, Any], result: dict[str, Any], analysis: dict[str, Any]) -> dict[str, Any]:
    human_circle = analysis["circle"]["refinedRobustGeometricCircle"]
    human_datum = analysis["yDownTargetDiagnostic"]["datumMeasurement"] or {}
    human_position = human_datum.get("position") or {}
    human_angle = human_datum.get("measuredFromPositiveYClockwiseDeg")
    human_target = analysis["yDownTargetDiagnostic"]["targetAssessment"]
    automatic = _automatic_values(result)
    auto_circle = automatic["circle"]
    center_dx = center_dy = center_distance = radius_delta = radius_abs = None
    if isinstance(auto_circle, dict):
        center_dx = float(auto_circle["centerX"]) - float(human_circle["centerX"])
        center_dy = float(auto_circle["centerY"]) - float(human_circle["centerY"])
        center_distance = math.hypot(center_dx, center_dy)
        radius_delta = float(auto_circle["radiusPx"]) - float(human_circle["radiusPx"])
        radius_abs = abs(radius_delta)
    auto_angle = automatic["measuredYDownDeg"]
    angle_delta = (
        None if not isinstance(auto_angle, (int, float)) or not isinstance(human_angle, (int, float))
        else circular_delta_deg(float(auto_angle), float(human_angle))
    )
    return {
        "imageId": item["imageId"],
        "relativePath": item["relativePath"],
        "imageSha256": item["sha256"],
        "annotationRelativePath": entry["annotationRelativePath"],
        "annotationSha256": entry["annotationSha256"],
        "evaluationEligible": True,
        "ineligibleReasons": [],
        "human": {
            "circle": human_circle,
            "measuredYDownDeg": human_angle,
            "quadrant": None if not human_position else f"{human_position.get('vertical')}_{human_position.get('horizontal')}",
            "targetToleranceStatus": human_target.get("toleranceStatus"),
            "openingEndpointAzimuthsDeg": analysis["grooveRecognition"]["endpointAzimuthImageDeg"],
            "radialAxis": (analysis.get("measurement") or {}).get("radialAxis"),
        },
        "automatic": automatic,
        "difference": {
            "centerDxPx": center_dx, "centerDyPx": center_dy,
            "centerDistancePx": center_distance,
            "radiusSignedPx": radius_delta, "radiusAbsolutePx": radius_abs,
            "measuredAngleCircularDeg": angle_delta,
        },
    }


def _render_comparison(image_path: Path, record: dict[str, Any], output_path: Path) -> None:
    with Image.open(image_path) as source:
        image = source.convert("RGB")
    draw = ImageDraw.Draw(image)
    width = max(4, image.width // 1000)
    point_radius = width * 2
    font = ImageFont.load_default(size=max(18, image.width // 200))
    human = record["human"]
    automatic = record["automatic"]
    for circle, color in ((human.get("circle"), "#38d66b"), (automatic.get("circle"), "#35c7ff")):
        if isinstance(circle, dict):
            cx, cy, radius = circle["centerX"], circle["centerY"], circle["radiusPx"]
            draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), outline=color, width=width)
    for point in automatic.get("openingIntersections") or []:
        x, y = float(point["x"]), float(point["y"])
        draw.ellipse((x - point_radius, y - point_radius, x + point_radius, y + point_radius), fill="#ffe14f")
    human_boundary = human.get("grooveBoundaryPoints") or []
    if len(human_boundary) >= 2:
        draw.line([tuple(map(float, point)) for point in human_boundary], fill="#38d66b", width=width * 2)
    for axis, color in ((human.get("radialAxis"), "#38d66b"), (automatic.get("radialAxis"), "#ff5dce")):
        if isinstance(axis, dict) and isinstance(axis.get("from"), dict) and isinstance(axis.get("to"), dict):
            draw.line(
                (axis["from"]["x"], axis["from"]["y"], axis["to"]["x"], axis["to"]["y"]),
                fill=color, width=width * 2,
            )
    draw.rectangle((0, 0, min(image.width, 3000), max(125, image.height // 18)), fill="#111111")
    difference = record["difference"]
    draw.text((16, 12), f"{record['imageId']} HUMAN(green) vs AUTO(cyan/yellow)", fill="white", font=font)
    draw.text(
        (16, 56),
        f"circle center delta={difference['centerDistancePx']}px radius delta={difference['radiusSignedPx']}px",
        fill="white", font=font,
    )
    draw.text(
        (16, 96),
        f"angle human={human.get('measuredYDownDeg')} auto={automatic.get('measuredYDownDeg')} delta={difference['measuredAngleCircularDeg']}",
        fill="white", font=font,
    )
    image.thumbnail((1800, 1200), Image.Resampling.LANCZOS)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path, quality=92)


def evaluate_cases(
    manifest: dict[str, Any], results: list[dict[str, Any]], index: dict[str, Any],
    data_root: Path, annotation_root: Path, config_path: Path, output_dir: Path,
) -> dict[str, Any]:
    try:
        output_dir.resolve().relative_to(PROJECT_ROOT.resolve())
    except ValueError:
        pass
    else:
        raise ValueError("annotated-case evaluation outputs must stay outside Git")
    config = load_config(config_path)
    adapter = LegacyAEndFaceAdapter(config)
    source_hash = adapter.expected_hashes[adapter.paths.source]
    entries = {str(item["imageId"]): item for item in index.get("entries") or []}
    dataset_id = str(manifest.get("datasetId"))
    result_by_task = {str(item.get("taskId")): item for item in results}
    records: list[dict[str, Any]] = []
    for item in manifest.get("images") or []:
        entry = entries.get(str(item["imageId"]))
        result = result_by_task.get(f"{dataset_id}:{item['imageId']}")
        reasons: list[str] = []
        if entry is None:
            reasons.append("ANNOTATION_INDEX_ENTRY_MISSING")
        if result is None:
            reasons.append("DETECTION_RESULT_MISSING")
        if reasons:
            records.append({
                "imageId": item["imageId"], "relativePath": item["relativePath"],
                "evaluationEligible": False, "ineligibleReasons": reasons,
                "human": None, "automatic": None, "difference": None,
            })
            continue
        assert entry is not None and result is not None
        image_relative = safe_relative_path(str(item["relativePath"]))
        annotation_relative = safe_relative_path(str(entry["annotationRelativePath"]))
        image_path = data_root.resolve() / image_relative
        annotation_path = annotation_root.resolve() / annotation_relative
        if not annotation_path.is_file():
            reasons.append("ANNOTATION_FILE_MISSING")
            payload = {}
            annotation_hash = ""
        else:
            payload = json.loads(annotation_path.read_text(encoding="utf-8"))
            annotation_hash = sha256_file(annotation_path)
        image_hash = sha256_file(image_path)
        reasons.extend(annotation_eligibility(
            payload, entry, actual_image_sha256=image_hash,
            actual_annotation_sha256=annotation_hash,
        ))
        if int(payload.get("imageWidth") or -1) != int(item["width"]) or int(payload.get("imageHeight") or -1) != int(item["height"]):
            reasons.append("IMAGE_DIMENSION_MISMATCH")
        if reasons:
            records.append({
                "imageId": item["imageId"], "relativePath": item["relativePath"],
                "evaluationEligible": False, "ineligibleReasons": list(dict.fromkeys(reasons)),
                "human": None, "automatic": _automatic_values(result), "difference": None,
            })
            continue
        shapes = payload["shapes"]
        circle = next(shape for shape in shapes if shape.get("label") in CIRCLE_LABELS)
        groove = next(shape for shape in shapes if shape.get("label") == GROOVE_LABEL)
        try:
            analysis = analyze_manual_groove_geometry(
                _circle_points(circle), groove["points"], adapter.module.fit_circle,
                adapter.module.robust_fit_circle, DEFAULT_REVIEW_CONFIG,
                {
                    "schemaVersion": "slot-groove-target/1", "nominalDeg": 85.0,
                    "expectedQuadrant": "lower_left",
                    "physicalDatumDefinitionId": "detected-physical-circle-positive-y-down-ray/1",
                    "angleConventionId": "image-y-down-clockwise-signed/1",
                },
                circle_fit_source_sha256=source_hash,
            )
            if analysis["grooveRecognition"]["status"] != "accepted":
                raise ValueError(f"manual groove geometry rejected: {analysis['grooveRecognition']['rejectionReasons']}")
        except ValueError as exc:
            records.append({
                "imageId": item["imageId"], "relativePath": item["relativePath"],
                "evaluationEligible": False, "ineligibleReasons": [f"ANNOTATION_GEOMETRY_FAILED:{exc}"],
                "human": None, "automatic": _automatic_values(result), "difference": None,
            })
            continue
        record = _comparison_record(item, entry, result, analysis)
        record["human"]["grooveBoundaryPoints"] = groove["points"]
        records.append(record)
        _render_comparison(image_path, record, output_dir / "overlays" / f"{len(records):04d}.jpg")
    eligible = sum(item["evaluationEligible"] for item in records)
    static_repeatability = compute_static_repeatability(
        manifest, records,
        configured_min_repeats=int((config.get("repeatability") or {}).get("min_valid_repeats") or 20),
    )
    summary = {
        "schemaVersion": "annotated-real-case-comparison/1",
        "datasetId": manifest.get("datasetId"),
        "imageCount": len(records),
        "evaluationEligibleCount": eligible,
        "pendingOrRejectedCount": len(records) - eligible,
        "strictPass": eligible == len(records),
        "accuracyStatistics": None if eligible != len(records) else {
            "note": "per-image deltas are authoritative only for the reviewed dataset/split",
        },
        "staticRepeatability": static_repeatability,
        "records": records,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(output_dir / "comparison.json", summary)
    with (output_dir / "comparison.csv").open("w", newline="", encoding="utf-8") as handle:
        fields = [
            "image_id", "relative_path", "evaluation_eligible", "ineligible_reasons",
            "human_center_x", "human_center_y", "human_radius_px", "auto_center_x", "auto_center_y",
            "auto_radius_px", "center_distance_px", "radius_signed_px", "human_angle_deg",
            "auto_angle_deg", "angle_circular_delta_deg", "human_quadrant", "auto_quadrant",
            "human_target_status", "auto_target_status", "detection_error_code",
        ]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for record in records:
            human = record.get("human") or {}; auto = record.get("automatic") or {}; diff = record.get("difference") or {}
            hc = human.get("circle") or {}; ac = auto.get("circle") or {}
            writer.writerow({
                "image_id": record["imageId"], "relative_path": record["relativePath"],
                "evaluation_eligible": record["evaluationEligible"],
                "ineligible_reasons": "|".join(record["ineligibleReasons"]),
                "human_center_x": hc.get("centerX"), "human_center_y": hc.get("centerY"), "human_radius_px": hc.get("radiusPx"),
                "auto_center_x": ac.get("centerX"), "auto_center_y": ac.get("centerY"), "auto_radius_px": ac.get("radiusPx"),
                "center_distance_px": diff.get("centerDistancePx"), "radius_signed_px": diff.get("radiusSignedPx"),
                "human_angle_deg": human.get("measuredYDownDeg"), "auto_angle_deg": auto.get("measuredYDownDeg"),
                "angle_circular_delta_deg": diff.get("measuredAngleCircularDeg"),
                "human_quadrant": human.get("quadrant"), "auto_quadrant": auto.get("quadrant"),
                "human_target_status": human.get("targetToleranceStatus"), "auto_target_status": auto.get("targetToleranceStatus"),
                "detection_error_code": auto.get("errorCode"),
            })
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--results", required=True, type=Path)
    parser.add_argument("--annotation-index", required=True, type=Path)
    parser.add_argument("--data-root", required=True, type=Path)
    parser.add_argument("--annotation-root", required=True, type=Path)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    try:
        summary = evaluate_cases(
            json.loads(args.manifest.read_text(encoding="utf-8")), load_results(args.results),
            json.loads(args.annotation_index.read_text(encoding="utf-8")),
            args.data_root, args.annotation_root, args.config, args.output_dir,
        )
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(
        f"Compared {summary['imageCount']} cases: eligible={summary['evaluationEligibleCount']} "
        f"pending_or_rejected={summary['pendingOrRejectedCount']}"
    )
    return 3 if args.strict and not summary["strictPass"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
