#!/usr/bin/env python3
"""Prepare truth-safe LabelMe requests for local fixture-shadow contamination."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.dataset_common import safe_relative_path, sha256_file


SCHEMA_VERSION = "fixture-contamination-review/1"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
ALLOWED_HUMAN_LABELS = [
    "HUMAN_fixture_shadow_overlap_on_detected_wall_left",
    "HUMAN_fixture_shadow_overlap_on_detected_wall_right",
]
REQUIRED_AUTO_LABELS = {
    "AUTO_detected_groove_wall_left",
    "AUTO_detected_groove_wall_right",
    "AUTO_detected_mouth_endpoint_left",
    "AUTO_detected_mouth_endpoint_right",
}


def _require_external(path: Path) -> None:
    try:
        path.resolve().relative_to(PROJECT_ROOT.resolve())
    except ValueError:
        return
    raise ValueError("fixture contamination output must be outside the Git worktree")


def _load_object(path: Path, name: str) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{name} must be a JSON object")
    return payload


def _resolve_bundle_path(bundle_root: Path, value: Any, name: str) -> Path:
    relative = safe_relative_path(str(value or ""))
    resolved = (bundle_root / relative).resolve()
    try:
        resolved.relative_to(bundle_root.resolve())
    except ValueError as exc:
        raise ValueError(f"{name} escapes the review bundle") from exc
    return resolved


def _json_text(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def _text_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _safe_id(value: str) -> str:
    return "".join(char if char.isalnum() or char in "._-" else "-" for char in value)


def _validate_exact_semantics(
    *,
    same_real_square_groove: str,
    fully_visible_unoccluded: str,
    endpoints_on_outer_shoulders: str,
    fixture_shadow_overlap: str,
) -> None:
    if (
        same_real_square_groove,
        fully_visible_unoccluded,
        endpoints_on_outer_shoulders,
        fixture_shadow_overlap,
    ) != ("YES", "YES", "YES", "PARTIAL"):
        raise ValueError(
            "this action requires the exact semantic response YES/YES/YES/PARTIAL"
        )


def prepare_fixture_contamination_annotation(
    review_index_path: Path,
    image_ids: list[str],
    output_dir: Path,
    *,
    same_real_square_groove: str,
    fully_visible_unoccluded: str,
    endpoints_on_outer_shoulders: str,
    fixture_shadow_overlap: str,
) -> dict[str, Any]:
    _validate_exact_semantics(
        same_real_square_groove=same_real_square_groove,
        fully_visible_unoccluded=fully_visible_unoccluded,
        endpoints_on_outer_shoulders=endpoints_on_outer_shoulders,
        fixture_shadow_overlap=fixture_shadow_overlap,
    )
    if not image_ids:
        raise ValueError("at least one --image-id is required")
    if len(set(image_ids)) != len(image_ids):
        raise ValueError("duplicate imageId selection")
    output_dir = output_dir.resolve()
    _require_external(output_dir)
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError("fixture contamination output directory must be empty")

    review_index_path = review_index_path.resolve()
    review_index = _load_object(review_index_path, "review index")
    if review_index.get("schemaVersion") != "slot-pose-prefill-review/2":
        raise ValueError("unsupported review index schemaVersion")
    truth_policy = review_index.get("truthPolicy")
    if not isinstance(truth_policy, dict) or (
        truth_policy.get("autoShapesAreTruth") is not False
        or truth_policy.get("runtimeInputAllowed") is not False
        or truth_policy.get("humanMustReview") is not True
    ):
        raise ValueError("review index truth policy is unsafe")
    source_entries = review_index.get("entries")
    if not isinstance(source_entries, list):
        raise ValueError("review index entries must be an array")
    by_id: dict[str, dict[str, Any]] = {}
    for item in source_entries:
        if not isinstance(item, dict) or not str(item.get("imageId") or ""):
            raise ValueError("review index entry imageId is required")
        image_id = str(item["imageId"])
        if image_id in by_id:
            raise ValueError(f"duplicate review index imageId: {image_id}")
        by_id[image_id] = item

    bundle_root = review_index_path.parent
    prepared: list[tuple[Path, str]] = []
    report_entries: list[dict[str, Any]] = []
    derived_names: set[str] = set()
    for image_id in image_ids:
        item = by_id.get(image_id)
        if item is None:
            raise ValueError(f"unknown imageId: {image_id}")
        image_sha = str(item.get("imageSha256") or "").lower()
        auto_sha = str(item.get("autoLabelmeSha256") or "").lower()
        if not SHA256_RE.fullmatch(image_sha) or not SHA256_RE.fullmatch(auto_sha):
            raise ValueError(f"invalid source SHA-256 for imageId: {image_id}")
        raw_path = _resolve_bundle_path(
            bundle_root, item.get("rawRelativePath"), "rawRelativePath",
        )
        auto_path = _resolve_bundle_path(
            bundle_root, item.get("autoLabelmeRelativePath"), "autoLabelmeRelativePath",
        )
        if not raw_path.is_file() or sha256_file(raw_path) != image_sha:
            raise ValueError(f"raw image SHA mismatch: {image_id}")
        if not auto_path.is_file() or sha256_file(auto_path) != auto_sha:
            raise ValueError(f"AUTO LabelMe SHA mismatch: {image_id}")
        auto = _load_object(auto_path, "AUTO LabelMe")
        shapes = auto.get("shapes")
        if not isinstance(shapes, list):
            raise ValueError(f"AUTO LabelMe shapes must be an array: {image_id}")
        if bool((auto.get("flags") or {}).get("human_verified")) or any(
            not isinstance(shape, dict)
            or not str(shape.get("label") or "").startswith("AUTO_")
            for shape in shapes
        ):
            raise ValueError(f"existing HUMAN content is not allowed: {image_id}")
        labels = {str(shape.get("label")) for shape in shapes}
        missing = sorted(REQUIRED_AUTO_LABELS - labels)
        if missing:
            raise ValueError(f"AUTO LabelMe missing required shapes {missing}: {image_id}")

        safe_id = _safe_id(image_id)
        if not safe_id or safe_id in derived_names:
            raise ValueError(f"derived LabelMe name collision: {image_id}")
        derived_names.add(safe_id)
        relative_output = Path("labelme-contamination") / f"{safe_id}.json"
        derived_path = output_dir / relative_output
        derived = copy.deepcopy(auto)
        derived_flags = derived.get("flags")
        if not isinstance(derived_flags, dict):
            derived_flags = {}
            derived["flags"] = derived_flags
        derived_flags.update({
            "human_verified": False,
            "formal_truth": False,
            "runtime_input_allowed": False,
            "semantic_review_applied": True,
            "real_groove_identity_confirmed": True,
            "both_sides_fully_visible_unoccluded_confirmed": True,
            "mouth_endpoints_on_real_shoulders_confirmed": True,
            "partial_fixture_shadow_contamination_confirmed": True,
            "auto_lines_are_pixel_truth": False,
            "clean_accuracy_evaluation_allowed": False,
            "threshold_tuning_allowed": False,
            "fixture_contamination_annotation_pending": True,
        })
        derived["description"] = (
            "Semantic review confirms groove identity and shoulder endpoints, but not clean pixel truth. "
            "Add only HUMAN_fixture_shadow_overlap_on_detected_wall_left/right linestrips over "
            "the actually contaminated subsegments."
        )
        derived["imagePath"] = os.path.relpath(
            raw_path, start=derived_path.parent,
        ).replace(os.sep, "/")
        derived_text = _json_text(derived)
        prepared.append((derived_path, derived_text))
        report_entries.append({
            "imageId": image_id,
            "sourceImageSha256": image_sha,
            "sourceAutoLabelmeSha256": auto_sha,
            "answers": {
                "detectedWallsSameRealSquareGroove": "YES",
                "grooveSidesFullyVisibleUnoccluded": "YES",
                "endpointsOnRealOuterCircleShoulders": "YES",
                "anyMarkedLineOnFixtureShadow": "YES",
                "fixtureShadowContaminationExtent": "PARTIAL",
            },
            "semanticConclusions": {
                "realGrooveIdentityConfirmed": True,
                "endpointSemanticsConfirmed": True,
                "pixelTruthAvailable": False,
                "wholeAutoWallConfirmedClean": False,
            },
            "annotationRequest": {
                "derivedLabelmeRelativePath": relative_output.as_posix(),
                "derivedLabelmeSha256": _text_sha256(derived_text),
                "allowedHumanLabels": list(ALLOWED_HUMAN_LABELS),
                "requiredShapeType": "linestrip",
                "minimumHumanSegments": 1,
                "affectedWall": "UNCONFIRMED",
                "supportPointOverlap": "UNCONFIRMED",
                "endpointOverlap": "UNCONFIRMED",
            },
        })

    report = {
        "schemaVersion": SCHEMA_VERSION,
        "sourceReviewIndexSha256": sha256_file(review_index_path),
        "entries": report_entries,
        "truthPolicy": {
            "semanticReviewOnly": True,
            "autoLinesArePixelTruth": False,
            "cleanAccuracyEvaluationAllowed": False,
            "thresholdTuningAllowed": False,
            "runtimeInputAllowed": False,
            "plcInputAllowed": False,
        },
    }
    for path, text in prepared:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    report_path = output_dir / "fixture-contamination-review.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(_json_text(report), encoding="utf-8")
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review-index", required=True, type=Path)
    parser.add_argument("--image-id", action="append", required=True)
    parser.add_argument("--same-real-square-groove", required=True, choices=("YES", "NO", "UNSURE"))
    parser.add_argument("--fully-visible-unoccluded", required=True, choices=("YES", "NO", "UNSURE"))
    parser.add_argument("--endpoints-on-outer-shoulders", required=True, choices=("YES", "NO", "UNSURE"))
    parser.add_argument("--fixture-shadow-overlap", required=True, choices=("NONE", "PARTIAL", "ENTIRE", "UNKNOWN"))
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        report = prepare_fixture_contamination_annotation(
            args.review_index,
            args.image_id,
            args.output_dir,
            same_real_square_groove=args.same_real_square_groove,
            fully_visible_unoccluded=args.fully_visible_unoccluded,
            endpoints_on_outer_shoulders=args.endpoints_on_outer_shoulders,
            fixture_shadow_overlap=args.fixture_shadow_overlap,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(
        f"Prepared {len(report['entries'])} fixture-contamination annotation requests; "
        "pixelTruthAvailable=false thresholdTuningAllowed=false"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
