#!/usr/bin/env python3
"""Validate dataset structure, image metadata and hashes against a manifest."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

try:
    from .dataset_common import MANIFEST_SCHEMA_VERSION, inspect_image, safe_relative_path, write_json
except ImportError:  # Direct script execution.
    from dataset_common import MANIFEST_SCHEMA_VERSION, inspect_image, safe_relative_path, write_json


def add_issue(issues: list[dict], code: str, message: str, image_id: str | None = None) -> None:
    item = {"code": code, "message": message}
    if image_id is not None:
        item["imageId"] = image_id
    issues.append(item)


def validate_config(config: dict, issues: list[dict]) -> None:
    calibration = config.get("calibration", {})
    mm_per_px = calibration.get("mm_per_px")
    if mm_per_px is not None and (not isinstance(mm_per_px, (int, float)) or mm_per_px <= 0):
        add_issue(issues, "CONFIG_MM_PER_PX", "calibration.mm_per_px must be null or positive")

    features = config.get("feature_mappings", [])
    codes: set[str] = set()
    columns: set[str] = set()
    for feature in features:
        code = feature.get("feature_code")
        column = feature.get("source_column")
        if not code or code in codes:
            add_issue(issues, "CONFIG_FEATURE_CODE", f"missing or duplicate feature_code: {code!r}")
        if not column or column in columns:
            add_issue(issues, "CONFIG_SOURCE_COLUMN", f"missing or duplicate source_column: {column!r}")
        codes.add(code)
        columns.add(column)


def validate_manifest(
    manifest: dict,
    data_root: Path,
    verify_hash: bool = True,
    config: dict | None = None,
) -> dict:
    errors: list[dict] = []
    warnings: list[dict] = []
    if manifest.get("schemaVersion") != MANIFEST_SCHEMA_VERSION:
        add_issue(errors, "SCHEMA_VERSION", f"expected {MANIFEST_SCHEMA_VERSION!r}")

    images = manifest.get("images")
    if not isinstance(images, list) or not images:
        add_issue(errors, "IMAGES_EMPTY", "manifest.images must be a non-empty list")
        images = []

    seen_paths: set[str] = set()
    seen_ids: set[str] = set()
    groups: dict[tuple[str, str], list[int]] = defaultdict(list)
    sample_splits: dict[str, set[str]] = defaultdict(set)
    checked = 0
    for item in images:
        image_id = str(item.get("imageId", ""))
        relative_value = str(item.get("relativePath", ""))
        if not image_id or image_id in seen_ids:
            add_issue(errors, "IMAGE_ID", f"missing or duplicate imageId: {image_id!r}", image_id)
        seen_ids.add(image_id)
        if relative_value in seen_paths:
            add_issue(errors, "DUPLICATE_PATH", f"duplicate path: {relative_value}", image_id)
        seen_paths.add(relative_value)
        try:
            relative = safe_relative_path(relative_value)
        except ValueError as exc:
            add_issue(errors, "UNSAFE_PATH", str(exc), image_id)
            continue
        path = data_root / relative
        if not path.is_file():
            add_issue(errors, "FILE_MISSING", f"file not found: {relative_value}", image_id)
            continue
        try:
            actual = inspect_image(path)
        except (OSError, ValueError) as exc:
            add_issue(errors, "IMAGE_UNREADABLE", f"{relative_value}: {exc}", image_id)
            continue
        checked += 1
        for key in ("bytes", "format", "width", "height", "mode"):
            if item.get(key) != actual[key]:
                add_issue(
                    errors,
                    "METADATA_MISMATCH",
                    f"{relative_value}: {key} expected={item.get(key)!r} actual={actual[key]!r}",
                    image_id,
                )
        if verify_hash and item.get("sha256") != actual["sha256"]:
            add_issue(errors, "HASH_MISMATCH", f"{relative_value}: SHA-256 mismatch", image_id)
        sample = str(item.get("sampleId", ""))
        position = str(item.get("position", ""))
        repeat = item.get("repeatIndex")
        if not sample or not position or not isinstance(repeat, int) or repeat <= 0:
            add_issue(errors, "GROUP_METADATA", f"invalid sample/position/repeat for {relative_value}", image_id)
        else:
            groups[(sample, position)].append(repeat)
            split = str(item.get("split", "unassigned"))
            if split != "unassigned":
                sample_splits[sample].add(split)

    for sample, splits in sorted(sample_splits.items()):
        if len(splits) > 1:
            add_issue(errors, "SPLIT_LEAKAGE", f"physical sample {sample!r} appears in splits {sorted(splits)}")

    expected = manifest.get("policy", {}).get("expectedRepeatsPerGroup")
    for (sample, position), repeats in sorted(groups.items()):
        ordered = sorted(repeats)
        if len(set(ordered)) != len(ordered):
            add_issue(errors, "REPEAT_DUPLICATE", f"{sample}/{position}: duplicate repeatIndex")
        if ordered != list(range(1, len(ordered) + 1)):
            add_issue(errors, "REPEAT_GAP", f"{sample}/{position}: repeatIndex must be contiguous from 1")
        if isinstance(expected, int) and len(ordered) != expected:
            add_issue(errors, "REPEAT_COUNT", f"{sample}/{position}: expected {expected}, found {len(ordered)}")

    if manifest.get("reference") and manifest["reference"].get("relativePath") is None:
        add_issue(warnings, "EXTERNAL_REFERENCE", "reference is outside data root; only its fingerprint is recorded")
    if config is not None:
        validate_config(config, errors)

    return {
        "schemaVersion": "inspection-dataset-validation/1",
        "datasetId": manifest.get("datasetId"),
        "valid": not errors,
        "imageCount": len(images),
        "checkedImageCount": checked,
        "groupCount": len(groups),
        "hashVerification": verify_hash,
        "errors": errors,
        "warnings": warnings,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--data-root", required=True, type=Path)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--no-hash", action="store_true", help="Skip SHA-256 verification.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        config = json.loads(args.config.read_text(encoding="utf-8")) if args.config else None
        report = validate_manifest(manifest, args.data_root.resolve(), not args.no_hash, config)
        if args.report:
            write_json(args.report, report)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"ERROR: {exc}")
        return 2
    status = "VALID" if report["valid"] else "INVALID"
    print(
        f"{status}: dataset={report['datasetId']}, images={report['checkedImageCount']}/"
        f"{report['imageCount']}, groups={report['groupCount']}, "
        f"errors={len(report['errors'])}, warnings={len(report['warnings'])}"
    )
    for issue in report["errors"]:
        print(f"ERROR {issue['code']}: {issue['message']}")
    for issue in report["warnings"]:
        print(f"WARN  {issue['code']}: {issue['message']}")
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
