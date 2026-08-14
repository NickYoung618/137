#!/usr/bin/env python3
"""Create a portable, hash-verifiable manifest for an external image dataset."""

from __future__ import annotations

import argparse
import csv
import hashlib
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

try:
    from .dataset_common import IMAGE_SUFFIXES, MANIFEST_SCHEMA_VERSION, inspect_image, natural_key, write_json
except ImportError:  # Direct script execution.
    from dataset_common import IMAGE_SUFFIXES, MANIFEST_SCHEMA_VERSION, inspect_image, natural_key, write_json


DATASET_SPLITS = {"development", "tuning", "validation", "acceptance"}


def infer_group(relative_path: Path, default_sample: str, default_position: str) -> tuple[str, str, str]:
    parents = relative_path.parts[:-1]
    split = parents[0] if parents and parents[0] in DATASET_SPLITS else "unassigned"
    if len(parents) >= 2:
        return parents[-2], parents[-1], split
    if len(parents) == 1:
        return default_sample, parents[0], split
    return default_sample, default_position, split


def build_manifest(
    input_root: Path,
    dataset_id: str,
    task: str,
    expected_repeats: int,
    default_sample: str,
    default_position: str,
    reference_image: Path | None = None,
    grouping_records: dict[str, dict] | None = None,
    dataset_class: str = "normal",
) -> dict:
    input_root = input_root.resolve()
    if not input_root.is_dir():
        raise ValueError(f"input root is not a directory: {input_root}")
    if expected_repeats <= 0:
        raise ValueError("expected repeats must be positive")
    if dataset_class not in {"normal", "bad"}:
        raise ValueError("dataset_class must be 'normal' or 'bad'")

    paths = sorted(
        (path for path in input_root.rglob("*") if path.is_file() and path.suffix.casefold() in IMAGE_SUFFIXES),
        key=lambda path: natural_key(path.relative_to(input_root).as_posix()),
    )
    if not paths:
        raise ValueError(f"no supported images found under {input_root}")

    groups: dict[tuple[str, str, str], list[tuple[Path, dict]]] = defaultdict(list)
    for path in paths:
        relative = path.relative_to(input_root)
        relative_value = relative.as_posix()
        metadata = dict((grouping_records or {}).get(relative_value, {}))
        if grouping_records is not None and not metadata:
            raise ValueError(f"grouping record missing for image: {relative_value}")
        inferred_sample, inferred_position, inferred_split = infer_group(relative, default_sample, default_position)
        sample = str(metadata.get("sample_id") or inferred_sample)
        position = str(metadata.get("condition_id") or metadata.get("position") or inferred_position)
        split = str(metadata.get("split") or inferred_split)
        groups[(sample, position, split)].append((path, metadata))

    images: list[dict] = []
    fingerprint = hashlib.sha256()
    for (sample_id, position, split), group_items in sorted(groups.items()):
        for generated_repeat, (path, metadata) in enumerate(group_items, start=1):
            repeat_index = int(metadata.get("repeat_index") or generated_repeat)
            relative = path.relative_to(input_root).as_posix()
            info = inspect_image(path)
            record = {
                "imageId": f"{sample_id}:{position}:{repeat_index:04d}",
                "relativePath": relative,
                "sampleId": sample_id,
                "position": position,
                "conditionId": position,
                "datasetClass": str(metadata.get("dataset_class") or dataset_class),
                "split": split,
                "repeatIndex": repeat_index,
                "captureTimestamp": metadata.get("capture_timestamp") or None,
                "captureSequence": int(metadata["capture_sequence"]) if metadata.get("capture_sequence") else None,
                "sourceImageSha256": metadata.get("source_image_sha256") or None,
                **info,
            }
            images.append(record)
            fingerprint.update(relative.encode("utf-8"))
            fingerprint.update(b"\0")
            fingerprint.update(info["sha256"].encode("ascii"))
            fingerprint.update(b"\n")

    reference = None
    if reference_image is not None:
        reference_image = reference_image.resolve()
        if not reference_image.is_file():
            raise ValueError(f"reference image does not exist: {reference_image}")
        reference_info = inspect_image(reference_image)
        try:
            reference_path = reference_image.relative_to(input_root).as_posix()
        except ValueError:
            reference_path = None
        reference = {
            "relativePath": reference_path,
            "fileName": reference_image.name,
            **reference_info,
        }

    return {
        "schemaVersion": MANIFEST_SCHEMA_VERSION,
        "datasetId": dataset_id,
        "task": task,
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "sourceRootHint": input_root.name,
        "datasetFingerprint": fingerprint.hexdigest(),
        "policy": {
            "expectedRepeatsPerGroup": expected_repeats,
            "allowedImageSuffixes": sorted(IMAGE_SUFFIXES),
            "rawImagesAreExternal": True,
            "groupingExplicit": grouping_records is not None,
        },
        "reference": reference,
        "images": images,
}


def load_grouping_csv(path: Path) -> dict[str, dict]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    records: dict[str, dict] = {}
    for row in rows:
        relative = str(row.get("relative_path", "")).strip()
        if not relative or relative in records:
            raise ValueError(f"grouping relative_path is missing or duplicated: {relative!r}")
        records[relative] = row
    if not records:
        raise ValueError("grouping CSV is empty")
    return records


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="External dataset root.")
    parser.add_argument("--output", required=True, type=Path, help="Manifest JSON to create.")
    parser.add_argument("--dataset-id", required=True)
    parser.add_argument("--task", required=True, help="Stable task name, for example hole_2 or slot_pose.")
    parser.add_argument("--expected-repeats", type=int, default=20)
    parser.add_argument("--default-sample", default="sample_1")
    parser.add_argument("--default-position", default="pos_1")
    parser.add_argument("--reference-image", type=Path)
    parser.add_argument("--grouping", type=Path, help="Explicit capture grouping CSV keyed by relative_path.")
    parser.add_argument("--dataset-class", choices=("normal", "bad"), default="normal")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        grouping = load_grouping_csv(args.grouping) if args.grouping else None
        manifest = build_manifest(
            args.input,
            args.dataset_id,
            args.task,
            args.expected_repeats,
            args.default_sample,
            args.default_position,
            args.reference_image,
            grouping,
            args.dataset_class,
        )
        write_json(args.output, manifest)
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}")
        return 2
    groups = {(item["sampleId"], item["position"]) for item in manifest["images"]}
    print(
        f"Wrote {args.output}: images={len(manifest['images'])}, groups={len(groups)}, "
        f"fingerprint={manifest['datasetFingerprint']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
