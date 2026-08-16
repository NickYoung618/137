#!/usr/bin/env python3
"""Evaluate authoritative multi-group static repeatability from Manifest/results JSON."""

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
from tools.evaluation_governance import build_static_repeatability


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--results", required=True, type=Path)
    parser.add_argument("--eligibility", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser.parse_args(argv)


def _read_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _write_groups_csv(path: Path, groups: list[dict]) -> None:
    fields = [
        "sample_id", "condition_id", "dataset_class", "purpose", "frame_count", "eligibility_status",
        "exclusion_reasons", "valid_count", "failed_count", "valid_rate", "guidance_class",
        "angle_n", "angle_mean_deg", "angle_range_deg", "angle_std_deg", "angle_p95_abs_residual_deg",
        "circle_center_x_range_px", "circle_center_y_range_px", "radius_range_px",
        "groove_opening_x_range_px", "groove_opening_y_range_px", "elapsed_p50_ms", "elapsed_p95_ms", "elapsed_max_ms",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for item in groups:
            writer.writerow({
                "sample_id": item["sampleId"], "condition_id": item["conditionId"], "dataset_class": item["datasetClass"],
                "purpose": item["purpose"], "frame_count": item["frameCount"], "eligibility_status": item["eligibilityStatus"],
                "exclusion_reasons": "|".join(item["exclusionReasons"]), "valid_count": item["detection"]["validCount"],
                "failed_count": item["detection"]["failedCount"], "valid_rate": item["detection"]["validRate"],
                "guidance_class": item["guidanceClass"], "angle_n": item["angle"]["n"], "angle_mean_deg": item["angle"]["mean"],
                "angle_range_deg": item["angle"]["range"], "angle_std_deg": item["angle"]["standardDeviation"],
                "angle_p95_abs_residual_deg": item["angle"]["p95AbsoluteResidual"],
                "circle_center_x_range_px": item["geometry"]["circleCenterX"]["range"],
                "circle_center_y_range_px": item["geometry"]["circleCenterY"]["range"],
                "radius_range_px": item["geometry"]["circleRadius"]["range"],
                "groove_opening_x_range_px": item["geometry"]["grooveOpeningX"]["range"],
                "groove_opening_y_range_px": item["geometry"]["grooveOpeningY"]["range"],
                "elapsed_p50_ms": item["timing"]["p50"], "elapsed_p95_ms": item["timing"]["p95"],
                "elapsed_max_ms": item["timing"]["max"],
            })


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        eligibility = json.loads(args.eligibility.read_text(encoding="utf-8"))
        results = _read_jsonl(args.results)
        report = build_static_repeatability(manifest, results, eligibility)
        args.output_dir.mkdir(parents=True, exist_ok=True)
        write_json(args.output_dir / "static-repeatability.json", report)
        _write_groups_csv(args.output_dir / "static-groups.csv", report["groups"])
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}")
        return 2
    print(
        f"Evaluated groups={len(report['groups'])} eligible={report['summary']['eligibleGroupCount']} "
        f"excluded={report['summary']['excludedGroupCount']} coverage={report['summary']['guidanceCoverage']['status']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
