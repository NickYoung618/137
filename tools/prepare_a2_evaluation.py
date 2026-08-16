#!/usr/bin/env python3
"""Materialize a single-root A2 Manifest and strict static-group eligibility."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.dataset_common import write_json
from tools.evaluation_governance import prepare_dataset, read_csv


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", required=True, type=Path)
    parser.add_argument("--inventory", required=True, type=Path)
    parser.add_argument("--grouping", required=True, type=Path)
    parser.add_argument("--semantics", type=Path)
    parser.add_argument("--metadata-manifest", type=Path, help="Existing trusted Manifest metadata for image-free dry-runs.")
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--verify-images", action="store_true")
    parser.add_argument("--minimum-frames", type=int, default=20)
    parser.add_argument("--dataset-id", default="a2-canonical-grouped")
    return parser.parse_args(argv)


def _write_eligibility_csv(path: Path, groups: list[dict]) -> None:
    fields = ["sample_id", "condition_id", "dataset_class", "purpose", "frame_count", "status", "authoritative", "exclusion_reasons"]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for item in groups:
            writer.writerow({
                "sample_id": item["sampleId"], "condition_id": item["conditionId"],
                "dataset_class": item["datasetClass"], "purpose": item.get("purpose"),
                "frame_count": item["frameCount"], "status": item["status"],
                "authoritative": str(item["authoritative"]).lower(),
                "exclusion_reasons": "|".join(item["exclusionReasons"]),
            })


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        inventory = read_csv(args.inventory)
        grouping = read_csv(args.grouping)
        semantics = read_csv(args.semantics) if args.semantics else None
        metadata = json.loads(args.metadata_manifest.read_text(encoding="utf-8")) if args.metadata_manifest else None
        manifest, eligibility, report = prepare_dataset(
            args.data_root, inventory, grouping, semantics_records=semantics,
            metadata_manifest=metadata, verify_images=args.verify_images,
            minimum_frames=args.minimum_frames, dataset_id=args.dataset_id,
        )
        args.output_dir.mkdir(parents=True, exist_ok=True)
        write_json(args.output_dir / "manifest.json", manifest)
        write_json(args.output_dir / "static-group-eligibility.json", eligibility)
        write_json(args.output_dir / "preparation-report.json", report)
        _write_eligibility_csv(args.output_dir / "static-group-eligibility.csv", eligibility["groups"])
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}")
        return 2
    print(
        f"Prepared {len(manifest['images'])} listed images: "
        f"eligible_groups={eligibility['summary']['eligibleGroupCount']} "
        f"excluded_groups={eligibility['summary']['excludedGroupCount']} output={args.output_dir}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
