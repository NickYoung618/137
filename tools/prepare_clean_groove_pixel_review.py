#!/usr/bin/env python3
"""Prepare and validate independent clean-groove pixel review tasks.

Preparation hashes the existing AUTO LabelMe only for provenance.  It never
parses AUTO shapes and creates blank HUMAN annotation files outside Git.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Sequence

from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.dataset_common import safe_relative_path, sha256_file


SCHEMA_VERSION = "clean-groove-pixel-review/1"
SEMANTIC_AUTHORITY = "FINAL_HUMAN_CLARIFICATION_A"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
SEALED_SAMPLE_TOKEN = "normal:part-006:"

WALL_LEFT = "HUMAN_clean_groove_wall_left_support"
WALL_RIGHT = "HUMAN_clean_groove_wall_right_support"
ENDPOINT_LEFT = "HUMAN_clean_groove_mouth_endpoint_left"
ENDPOINT_RIGHT = "HUMAN_clean_groove_mouth_endpoint_right"
OUTER_ARC = "HUMAN_outer_circle_visible_arc"
OUTER_CENTER = "HUMAN_outer_circle_center"
ALLOWED_LABELS = {
    WALL_LEFT, WALL_RIGHT, ENDPOINT_LEFT, ENDPOINT_RIGHT, OUTER_ARC, OUTER_CENTER,
}


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _require_external(path: Path, *, what: str) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(PROJECT_ROOT.resolve())
    except ValueError:
        return resolved
    raise ValueError(f"{what} must be outside the Git worktree")


def _resolve_source(root: Path, relative_value: str) -> Path:
    relative = safe_relative_path(relative_value)
    path = (root / relative).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"source path escapes review bundle: {relative_value!r}") from exc
    if not path.is_file():
        raise ValueError(f"source file is missing: {relative.as_posix()}")
    return path


def _safe_name(image_id: str) -> str:
    value = re.sub(r"[^A-Za-z0-9._-]+", "-", image_id).strip("-.")
    if not value:
        raise ValueError("imageId cannot form a safe filename")
    return value


def _truth_policy() -> dict[str, bool]:
    return {
        "independentAnnotationRequired": True,
        "autoGeometryParsed": False,
        "autoCoordinatesCopied": False,
        "fixtureShadowBoundaryRequired": False,
        "accuracyEvaluationAllowed": False,
        "thresholdTuningAllowed": False,
        "runtimeInputAllowed": False,
        "plcInputAllowed": False,
    }


def _required_geometry() -> dict[str, Any]:
    return {
        "wallLeft": {"label": WALL_LEFT, "shapeType": "point", "minimumCount": 3},
        "wallRight": {"label": WALL_RIGHT, "shapeType": "point", "minimumCount": 3},
        "mouthEndpointLeft": {"label": ENDPOINT_LEFT, "shapeType": "point", "exactCount": 1},
        "mouthEndpointRight": {"label": ENDPOINT_RIGHT, "shapeType": "point", "exactCount": 1},
        "outerCircleVisibleArc": {
            "label": OUTER_ARC, "shapeType": "linestrip", "minimumPointCount": 8,
            "optional": True,
        },
        "outerCircleCenter": {
            "label": OUTER_CENTER, "shapeType": "point", "exactCount": 1,
            "optional": True,
        },
    }


def _blank_labelme(raw_path: Path, labelme_path: Path, *, width: int, height: int) -> dict[str, Any]:
    image_path = Path(os.path.relpath(raw_path, labelme_path.parent)).as_posix()
    return {
        "version": "5.6.0",
        "flags": {
            "human_verified": False,
            "independent_annotation": True,
            "copied_from_auto": False,
            "annotation_pending": True,
            "runtime_input_allowed": False,
            "threshold_tuning_allowed": False,
            "plc_input_allowed": False,
        },
        "shapes": [],
        "imagePath": image_path,
        "imageData": None,
        "imageHeight": height,
        "imageWidth": width,
        "description": (
            "Independent HUMAN pixel review. Draw three or more distributed point shapes on each "
            "clean groove wall and one point for each mouth endpoint. For this review, left/right mean "
            "the lower/higher image-x mouth endpoint respectively. Do not copy algorithm coordinates. "
            "An independent outer-circle visible arc or center may be added for later angle-accuracy review."
        ),
    }


def prepare_clean_groove_pixel_review(
    review_index_path: Path,
    image_ids: list[str],
    output_dir: Path,
    *,
    semantic_authority: str,
) -> dict[str, Any]:
    """Create blank, independent LabelMe tasks after source identity checks."""

    output_dir = _require_external(output_dir, what="clean-groove review output")
    if output_dir.exists():
        raise ValueError("clean-groove review output must not already exist")
    if semantic_authority != SEMANTIC_AUTHORITY:
        raise ValueError(f"semantic authority must be {SEMANTIC_AUTHORITY}")
    if not image_ids:
        raise ValueError("at least one imageId is required")
    if len(set(image_ids)) != len(image_ids):
        raise ValueError("duplicate imageId is not allowed")
    if any(SEALED_SAMPLE_TOKEN in image_id for image_id in image_ids):
        raise ValueError("sealed sample part-006 is forbidden")

    review_index_path = review_index_path.resolve()
    try:
        review = json.loads(review_index_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read review-index: {exc}") from exc
    if not isinstance(review, dict) or review.get("schemaVersion") != "slot-pose-prefill-review/2":
        raise ValueError("review-index must use slot-pose-prefill-review/2")
    policy = review.get("truthPolicy")
    if policy != {
        "autoShapesAreTruth": False,
        "runtimeInputAllowed": False,
        "humanMustReview": True,
    }:
        raise ValueError("unsafe review truthPolicy")
    source_entries = review.get("entries")
    if not isinstance(source_entries, list):
        raise ValueError("review-index entries must be an array")
    by_id: dict[str, dict[str, Any]] = {}
    for item in source_entries:
        if not isinstance(item, dict):
            raise ValueError("review-index entry must be an object")
        image_id = str(item.get("imageId") or "")
        if not image_id or image_id in by_id:
            raise ValueError("review-index contains missing or duplicate imageId")
        by_id[image_id] = item
    unknown = [image_id for image_id in image_ids if image_id not in by_id]
    if unknown:
        raise ValueError(f"unknown imageId: {unknown[0]}")

    review_root = review_index_path.parent
    prepared: list[tuple[Path, dict[str, Any], dict[str, Any]]] = []
    entries: list[dict[str, Any]] = []
    seen_names: set[str] = set()
    for image_id in image_ids:
        item = by_id[image_id]
        digest = str(item.get("imageSha256") or "").lower()
        auto_digest = str(item.get("autoLabelmeSha256") or "").lower()
        if not SHA256_RE.fullmatch(digest) or not SHA256_RE.fullmatch(auto_digest):
            raise ValueError("review-index contains invalid SHA-256")
        raw_path = _resolve_source(review_root, str(item.get("rawRelativePath") or ""))
        auto_path = _resolve_source(review_root, str(item.get("autoLabelmeRelativePath") or ""))
        if sha256_file(raw_path) != digest:
            raise ValueError(f"raw image SHA-256 mismatch for {image_id}")
        # Provenance only: intentionally hash bytes without parsing AUTO JSON or shapes.
        if sha256_file(auto_path) != auto_digest:
            raise ValueError(f"AUTO LabelMe SHA-256 mismatch for {image_id}")
        with Image.open(raw_path) as image:
            width, height = image.size
        if width < 1 or height < 1:
            raise ValueError(f"invalid raw image dimensions for {image_id}")
        safe_name = _safe_name(image_id)
        if safe_name in seen_names:
            raise ValueError("imageIds collide after filename normalization")
        seen_names.add(safe_name)
        relative_labelme = Path("labelme-independent") / f"{safe_name}.json"
        labelme_path = output_dir / relative_labelme
        labelme = _blank_labelme(raw_path, labelme_path, width=width, height=height)
        prepared.append((labelme_path, labelme, item))
        entries.append({
            "imageId": image_id,
            "sourceImageSha256": digest,
            "sourceRawRelativePath": str(item.get("rawRelativePath") or ""),
            "sourceAutoLabelmeSha256": auto_digest,
            "labelmeRelativePath": relative_labelme.as_posix(),
            "labelmeSha256": "0" * 64,
            "imageWidth": width,
            "imageHeight": height,
            "reviewStatus": "PENDING_HUMAN_ANNOTATION",
            "wallPixelTruthAvailable": False,
            "endpointPixelTruthAvailable": False,
            "outerCircleReferenceAvailable": False,
            "wallEndpointPixelReviewComplete": False,
            "poseAngleAccuracyReady": False,
            "geometryCounts": {
                "wallLeftSupportPoints": 0,
                "wallRightSupportPoints": 0,
                "mouthEndpointLeft": 0,
                "mouthEndpointRight": 0,
                "outerCircleVisibleArcPoints": 0,
                "outerCircleCenter": 0,
            },
            "outerCircleReferenceMode": "NONE",
            "validationErrors": [],
        })

    output_dir.mkdir(parents=True)
    for index, (labelme_path, labelme, _) in enumerate(prepared):
        _write_json(labelme_path, labelme)
        entries[index]["labelmeSha256"] = sha256_file(labelme_path)
    payload = {
        "schemaVersion": SCHEMA_VERSION,
        "artifactType": "PREPARATION",
        "lifecycleStatus": "PENDING_HUMAN_ANNOTATION",
        "semanticAuthority": semantic_authority,
        "sourceReviewIndexSha256": sha256_file(review_index_path),
        "sourceTaskManifestSha256": None,
        "counts": {
            "images": len(entries),
            "pending": len(entries),
            "wallEndpointComplete": 0,
            "poseAngleReady": 0,
        },
        "requiredHumanGeometry": _required_geometry(),
        "entries": entries,
        "truthPolicy": _truth_policy(),
    }
    _write_json(output_dir / "clean-groove-pixel-review.json", payload)
    return payload


def _coordinates(shape: dict[str, Any], *, width: int, height: int) -> list[tuple[float, float]]:
    points = shape.get("points")
    if not isinstance(points, list):
        raise ValueError("shape points must be an array")
    result: list[tuple[float, float]] = []
    for point in points:
        if not isinstance(point, list) or len(point) != 2:
            raise ValueError("shape point must contain exactly two coordinates")
        x, y = point
        if (
            isinstance(x, bool) or isinstance(y, bool)
            or not isinstance(x, (int, float)) or not isinstance(y, (int, float))
            or not math.isfinite(float(x)) or not math.isfinite(float(y))
        ):
            raise ValueError("shape coordinates must be finite numbers")
        if not (0 <= float(x) < width and 0 <= float(y) < height):
            raise ValueError("shape coordinate is outside image bounds")
        result.append((float(x), float(y)))
    return result


def _validate_labelme(path: Path, entry: dict[str, Any]) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read completed LabelMe {path.name}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("completed LabelMe must be an object")
    flags = payload.get("flags")
    if not isinstance(flags, dict):
        raise ValueError("completed LabelMe flags are required")
    if flags.get("copied_from_auto") is not False:
        raise ValueError("copied_from_auto must remain false")
    if flags.get("independent_annotation") is not True:
        raise ValueError("independent_annotation must remain true")
    if flags.get("human_verified") is not True:
        raise ValueError("human_verified must be true")
    if flags.get("annotation_pending") is not False:
        raise ValueError("annotation_pending must be false")
    for key in ("runtime_input_allowed", "threshold_tuning_allowed", "plc_input_allowed"):
        if flags.get(key) is not False:
            raise ValueError(f"{key} must remain false")
    width = entry["imageWidth"]
    height = entry["imageHeight"]
    if payload.get("imageWidth") != width or payload.get("imageHeight") != height:
        raise ValueError("completed LabelMe image dimensions changed")
    shapes = payload.get("shapes")
    if not isinstance(shapes, list):
        raise ValueError("completed LabelMe shapes must be an array")
    grouped: dict[str, list[list[tuple[float, float]]]] = {label: [] for label in ALLOWED_LABELS}
    for shape in shapes:
        if not isinstance(shape, dict):
            raise ValueError("shape must be an object")
        label = str(shape.get("label") or "")
        if label.startswith("AUTO_"):
            raise ValueError("AUTO_ shapes are forbidden in independent review")
        if label.startswith("HUMAN_fixture_shadow_overlap_on_detected_wall_"):
            raise ValueError("dormant fixture-overlap shapes are forbidden")
        if label not in ALLOWED_LABELS:
            raise ValueError(f"unsupported independent review label: {label}")
        expected_type = "linestrip" if label == OUTER_ARC else "point"
        if shape.get("shape_type") != expected_type:
            raise ValueError(f"{label} must use shape_type={expected_type}")
        points = _coordinates(shape, width=width, height=height)
        if expected_type == "point" and len(points) != 1:
            raise ValueError(f"{label} must contain exactly one point")
        if label == OUTER_ARC and len(points) < 8:
            raise ValueError("outer-circle visible arc requires at least 8 points")
        grouped[label].append(points)

    left_points = [points[0] for points in grouped[WALL_LEFT]]
    right_points = [points[0] for points in grouped[WALL_RIGHT]]
    if len(left_points) < 3 or len(set(left_points)) != len(left_points):
        raise ValueError("left wall requires at least 3 distinct support points")
    if len(right_points) < 3 or len(set(right_points)) != len(right_points):
        raise ValueError("right wall requires at least 3 distinct support points")
    if len(grouped[ENDPOINT_LEFT]) != 1 or len(grouped[ENDPOINT_RIGHT]) != 1:
        raise ValueError("left/right mouth endpoint each require exactly one point")
    if len(grouped[OUTER_ARC]) > 1 or len(grouped[OUTER_CENTER]) > 1:
        raise ValueError("outer-circle arc/center may each appear at most once")
    outer_arc_points = len(grouped[OUTER_ARC][0]) if grouped[OUTER_ARC] else 0
    outer_center_count = len(grouped[OUTER_CENTER])
    outer_available = bool(outer_arc_points or outer_center_count)
    if outer_arc_points and outer_center_count:
        outer_mode = "VISIBLE_ARC_AND_CENTER"
    elif outer_arc_points:
        outer_mode = "VISIBLE_ARC"
    elif outer_center_count:
        outer_mode = "CENTER"
    else:
        outer_mode = "NONE"
    return {
        "labelmeSha256": sha256_file(path),
        "reviewStatus": (
            "WALL_ENDPOINT_AND_OUTER_REFERENCE_COMPLETE"
            if outer_available else "WALL_ENDPOINT_COMPLETE"
        ),
        "wallPixelTruthAvailable": True,
        "endpointPixelTruthAvailable": True,
        "outerCircleReferenceAvailable": outer_available,
        "wallEndpointPixelReviewComplete": True,
        "poseAngleAccuracyReady": outer_available,
        "geometryCounts": {
            "wallLeftSupportPoints": len(left_points),
            "wallRightSupportPoints": len(right_points),
            "mouthEndpointLeft": 1,
            "mouthEndpointRight": 1,
            "outerCircleVisibleArcPoints": outer_arc_points,
            "outerCircleCenter": outer_center_count,
        },
        "outerCircleReferenceMode": outer_mode,
        "validationErrors": [],
    }


def validate_clean_groove_pixel_review(task_manifest_path: Path, output_path: Path) -> dict[str, Any]:
    """Validate completed HUMAN tasks and write a report only after all pass."""

    output_path = _require_external(output_path, what="clean-groove validation output")
    if output_path.exists():
        raise ValueError("clean-groove validation output must not already exist")
    task_manifest_path = task_manifest_path.resolve()
    try:
        task = json.loads(task_manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read clean-groove task manifest: {exc}") from exc
    if not isinstance(task, dict) or task.get("schemaVersion") != SCHEMA_VERSION:
        raise ValueError(f"task manifest must use {SCHEMA_VERSION}")
    if task.get("artifactType") != "PREPARATION":
        raise ValueError("validation input must be a PREPARATION artifact")
    if task.get("semanticAuthority") != SEMANTIC_AUTHORITY or task.get("truthPolicy") != _truth_policy():
        raise ValueError("task manifest has unsafe semantic authority or truthPolicy")
    entries = task.get("entries")
    if not isinstance(entries, list) or not entries:
        raise ValueError("task manifest entries must be a non-empty array")
    root = task_manifest_path.parent
    validated: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for source in entries:
        if not isinstance(source, dict):
            raise ValueError("task entry must be an object")
        image_id = str(source.get("imageId") or "")
        if not image_id or image_id in seen_ids:
            raise ValueError("task manifest contains missing or duplicate imageId")
        if SEALED_SAMPLE_TOKEN in image_id:
            raise ValueError("sealed sample part-006 is forbidden")
        seen_ids.add(image_id)
        labelme_path = _resolve_source(root, str(source.get("labelmeRelativePath") or ""))
        validation = _validate_labelme(labelme_path, source)
        validated.append({
            "imageId": image_id,
            "sourceImageSha256": source["sourceImageSha256"],
            "sourceRawRelativePath": source["sourceRawRelativePath"],
            "sourceAutoLabelmeSha256": source["sourceAutoLabelmeSha256"],
            "labelmeRelativePath": source["labelmeRelativePath"],
            "imageWidth": source["imageWidth"],
            "imageHeight": source["imageHeight"],
            **validation,
        })
    outer_count = sum(int(entry["poseAngleAccuracyReady"]) for entry in validated)
    report = {
        "schemaVersion": SCHEMA_VERSION,
        "artifactType": "VALIDATION",
        "lifecycleStatus": (
            "WALL_ENDPOINT_AND_OUTER_REFERENCE_COMPLETE"
            if outer_count == len(validated) else "WALL_ENDPOINT_COMPLETE"
        ),
        "semanticAuthority": SEMANTIC_AUTHORITY,
        "sourceReviewIndexSha256": task["sourceReviewIndexSha256"],
        "sourceTaskManifestSha256": sha256_file(task_manifest_path),
        "counts": {
            "images": len(validated),
            "pending": 0,
            "wallEndpointComplete": len(validated),
            "poseAngleReady": outer_count,
        },
        "requiredHumanGeometry": _required_geometry(),
        "entries": validated,
        "truthPolicy": _truth_policy(),
    }
    _write_json(output_path, report)
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare = subparsers.add_parser("prepare", help="create blank independent LabelMe tasks")
    prepare.add_argument("--review-index", required=True, type=Path)
    prepare.add_argument("--image-id", action="append", required=True)
    prepare.add_argument("--semantic-authority", required=True, choices=(SEMANTIC_AUTHORITY,))
    prepare.add_argument("--output-dir", required=True, type=Path)
    validate = subparsers.add_parser("validate", help="validate completed independent LabelMe tasks")
    validate.add_argument("--task-manifest", required=True, type=Path)
    validate.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "prepare":
            payload = prepare_clean_groove_pixel_review(
                args.review_index,
                args.image_id,
                args.output_dir,
                semantic_authority=args.semantic_authority,
            )
            print(f"Prepared {payload['counts']['images']} independent HUMAN tasks in {args.output_dir}")
        else:
            payload = validate_clean_groove_pixel_review(args.task_manifest, args.output)
            print(
                f"Validated {payload['counts']['wallEndpointComplete']} wall/endpoint tasks; "
                f"pose-angle references ready: {payload['counts']['poseAngleReady']}"
            )
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
