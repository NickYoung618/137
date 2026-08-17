#!/usr/bin/env python3
"""Build a deterministic Git-external review subset from frozen manifests/results."""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain an object")
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def build_subset(
    manifests: list[dict[str, Any]],
    result_groups: list[list[dict[str, Any]]],
    image_ids: list[str],
    dataset_id: str,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    if len(manifests) != len(result_groups):
        raise ValueError("manifest/result group counts differ")
    wanted = list(dict.fromkeys(image_ids))
    if len(wanted) != len(image_ids) or not wanted:
        raise ValueError("image IDs must be non-empty and unique")

    image_index: dict[str, tuple[str, dict[str, Any]]] = {}
    result_index: dict[str, dict[str, Any]] = {}
    for manifest, results in zip(manifests, result_groups):
        source_dataset = str(manifest.get("datasetId") or "")
        if not source_dataset:
            raise ValueError("source datasetId is required")
        for item in manifest.get("images") or []:
            image_id = str(item.get("imageId") or "")
            if image_id in image_index:
                raise ValueError(f"duplicate source imageId: {image_id}")
            image_index[image_id] = (source_dataset, item)
        for result in results:
            task_id = str(result.get("taskId") or "")
            if task_id in result_index:
                raise ValueError(f"duplicate source taskId: {task_id}")
            result_index[task_id] = result

    images = []
    outputs = []
    lineage = []
    for image_id in wanted:
        if image_id not in image_index:
            raise ValueError(f"missing imageId: {image_id}")
        source_dataset, item = image_index[image_id]
        source_task = f"{source_dataset}:{image_id}"
        if source_task not in result_index:
            raise ValueError(f"missing result: {source_task}")

        images.append(copy.deepcopy(item))
        result = copy.deepcopy(result_index[source_task])
        result["taskId"] = f"{dataset_id}:{image_id}"
        outputs.append(result)
        lineage.append(
            {
                "imageId": image_id,
                "sourceDatasetId": source_dataset,
                "sourceTaskId": source_task,
                "imageSha256": item["sha256"],
            }
        )

    manifest = {
        "schemaVersion": manifests[0]["schemaVersion"],
        "datasetId": dataset_id,
        "images": images,
    }
    report = {
        "schemaVersion": "slot-pose-representative-subset/1",
        "datasetId": dataset_id,
        "selectionMethod": "EXPLICIT_IMAGE_ID_ONLY",
        "algorithmResultsUsedForSelection": False,
        "imageCount": len(images),
        "lineage": lineage,
    }
    return manifest, outputs, report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", action="append", required=True, type=Path)
    parser.add_argument("--results", action="append", required=True, type=Path)
    parser.add_argument("--image-id", action="append", required=True)
    parser.add_argument("--dataset-id", required=True)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    try:
        manifest, results, report = build_subset(
            [_read_json(path) for path in args.manifest],
            [_read_jsonl(path) for path in args.results],
            args.image_id,
            args.dataset_id,
        )
        args.output_dir.mkdir(parents=True, exist_ok=True)
        (args.output_dir / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        (args.output_dir / "results.jsonl").write_text(
            "\n".join(
                json.dumps(
                    item,
                    ensure_ascii=False,
                    separators=(",", ":"),
                    allow_nan=False,
                )
                for item in results
            )
            + "\n",
            encoding="utf-8",
        )
        (args.output_dir / "selection-report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(f"Prepared {len(results)} explicit representatives in {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
