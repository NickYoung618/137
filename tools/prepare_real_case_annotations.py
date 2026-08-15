#!/usr/bin/env python3
"""Prepare Git-external, truth-empty LabelMe work items for real images."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.dataset_common import safe_relative_path, sha256_file, write_json


def _require_external(path: Path) -> None:
    try:
        path.resolve().relative_to(PROJECT_ROOT.resolve())
    except ValueError:
        return
    raise ValueError("real-case annotations must be generated outside the Git worktree")


def _safe_stem(image_id: str, relative: Path, index: int) -> str:
    base = re.sub(r"[^A-Za-z0-9._-]+", "-", f"{index:04d}-{image_id}-{relative.stem}").strip("-.")
    return base[:160] or f"case-{index:04d}"


def _blank_labelme(item: dict[str, Any], relative: Path) -> dict[str, Any]:
    return {
        "version": "5.0.1",
        "flags": {
            "human_verified": False,
            "independent_from_algorithm": False,
            "formal_truth": False,
            "runtime_input_allowed": False,
            "annotation_version": "template-v1",
            "annotator": None,
            "reviewer": None,
        },
        "shapes": [],
        "imagePath": relative.as_posix(),
        "imageData": None,
        "imageHeight": int(item["height"]),
        "imageWidth": int(item["width"]),
    }


def prepare_annotations(manifest: dict[str, Any], data_root: Path, output_dir: Path) -> dict[str, Any]:
    output_dir = output_dir.resolve()
    _require_external(output_dir)
    data_root = data_root.resolve()
    annotations_dir = output_dir / "labelme"
    annotations_dir.mkdir(parents=True, exist_ok=True)
    entries: list[dict[str, Any]] = []
    for index, item in enumerate(manifest.get("images") or [], start=1):
        relative = safe_relative_path(str(item["relativePath"]))
        image_path = data_root / relative
        if not image_path.is_file():
            raise ValueError(f"missing image: {relative.as_posix()}")
        actual_image_hash = sha256_file(image_path)
        if actual_image_hash != item.get("sha256"):
            raise ValueError(f"image hash mismatch: {relative.as_posix()}")
        annotation_relative = Path("labelme") / f"{_safe_stem(str(item['imageId']), relative, index)}.json"
        annotation_path = output_dir / annotation_relative
        if not annotation_path.exists():
            write_json(annotation_path, _blank_labelme(item, relative))
        payload = json.loads(annotation_path.read_text(encoding="utf-8"))
        flags = payload.get("flags") if isinstance(payload.get("flags"), dict) else {}
        changed = False
        for key, value in (("annotator", None), ("reviewer", None)):
            if key not in flags:
                flags[key] = value
                changed = True
        if changed:
            payload["flags"] = flags
            write_json(annotation_path, payload)
        reviewed = (
            flags.get("human_verified") is True
            and flags.get("independent_from_algorithm") is True
            and flags.get("formal_truth") is True
        )
        entries.append({
            "imageId": item["imageId"],
            "relativeImagePath": relative.as_posix(),
            "imageSha256": actual_image_hash,
            "annotationRelativePath": annotation_relative.as_posix(),
            "annotationSha256": sha256_file(annotation_path),
            "annotationVersion": str(flags.get("annotation_version") or "unknown"),
            "annotator": flags.get("annotator"),
            "reviewer": flags.get("reviewer"),
            "reviewStatus": "reviewed" if reviewed else "template",
            "humanVerified": flags.get("human_verified") is True,
            "independentFromAlgorithm": flags.get("independent_from_algorithm") is True,
            "split": item.get("split") or "unassigned",
            "rejectionReasons": [] if reviewed else ["ANNOTATION_PENDING"],
        })
    reviewed_count = sum(item["reviewStatus"] == "reviewed" for item in entries)
    index_payload = {
        "schemaVersion": "real-case-annotation-index/1",
        "datasetId": manifest.get("datasetId"),
        "datasetFingerprint": manifest.get("datasetFingerprint"),
        "createdAtUtc": datetime.now(timezone.utc).isoformat(),
        "counts": {
            "total": len(entries), "reviewed": reviewed_count,
            "pending": len(entries) - reviewed_count,
        },
        "entries": entries,
    }
    write_json(output_dir / "annotation-index.json", index_payload)
    return index_payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--data-root", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    try:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        result = prepare_annotations(manifest, args.data_root, args.output_dir)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(
        f"Prepared {result['counts']['total']} cases: reviewed={result['counts']['reviewed']} "
        f"pending={result['counts']['pending']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
