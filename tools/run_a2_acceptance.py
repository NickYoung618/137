#!/usr/bin/env python3
"""Run the external A2 manifest, batch, truth, and split-report workflow."""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

try:
    from .dataset_common import write_json
    from .evaluate_slot_pose import evaluate_results
    from .make_manifest import build_manifest
    from .run_slot_pose_batch import run_batch
    from .validate_dataset import validate_manifest
except ImportError:
    from dataset_common import write_json
    from evaluate_slot_pose import evaluate_results
    from make_manifest import build_manifest
    from run_slot_pose_batch import run_batch
    from validate_dataset import validate_manifest


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def _grouping_by_class(rows: list[dict[str, str]], dataset_class: str) -> dict[str, dict[str, str]]:
    selected: dict[str, dict[str, str]] = {}
    for row in rows:
        if str(row.get("dataset_class", "")).strip().lower() != dataset_class:
            continue
        relative = str(row.get("relative_path", "")).strip()
        if not relative or relative in selected:
            raise ValueError(f"{dataset_class} grouping relative_path is missing or duplicated: {relative!r}")
        selected[relative] = row
    if not selected:
        raise ValueError(f"grouping CSV has no {dataset_class} rows")
    return selected


def run_acceptance(
    normal_root: Path,
    bad_root: Path,
    grouping_path: Path,
    truth_path: Path,
    config_path: Path,
    output_dir: Path,
    expected_normal_repeats: int = 20,
    expected_bad_repeats: int = 1,
) -> dict:
    grouping_rows = _read_csv(grouping_path)
    truth_rows = _read_csv(truth_path)
    sample_splits: dict[str, set[str]] = defaultdict(set)
    lineage_splits: dict[str, set[str]] = defaultdict(set)
    for row in grouping_rows:
        split = str(row.get("split", "unassigned"))
        sample_splits[str(row.get("sample_id", ""))].add(split)
        lineage = str(row.get("source_image_sha256", "")).strip()
        if lineage:
            lineage_splits[lineage].add(split)
    if any(len(splits) > 1 for splits in sample_splits.values()):
        raise ValueError("one or more physical samples cross dataset splits")
    if any(len(splits) > 1 for splits in lineage_splits.values()):
        raise ValueError("one or more source-image lineages cross dataset splits")
    truth_hashes = [str(row.get("image_sha256", "")).strip() for row in truth_rows]
    if len(truth_hashes) != len(set(truth_hashes)):
        raise ValueError("truth CSV contains duplicate image_sha256 values")
    normal_grouping = _grouping_by_class(grouping_rows, "normal")
    bad_grouping = _grouping_by_class(grouping_rows, "bad")
    normal_truth = [row for row in truth_rows if row.get("dataset_class", "").strip().lower() == "normal"]
    bad_truth = [row for row in truth_rows if row.get("dataset_class", "").strip().lower() == "bad"]
    normal_manifest = build_manifest(
        normal_root, "a2-normal", "slot_pose", expected_normal_repeats, "unknown", "unknown",
        grouping_records=normal_grouping, dataset_class="normal",
    )
    bad_manifest = build_manifest(
        bad_root, "a2-bad", "slot_pose", expected_bad_repeats, "unknown", "unknown",
        grouping_records=bad_grouping, dataset_class="bad",
    )
    config = json.loads(config_path.read_text(encoding="utf-8"))
    normal_validation = validate_manifest(normal_manifest, normal_root.resolve(), config=config, truth_rows=normal_truth)
    bad_validation = validate_manifest(bad_manifest, bad_root.resolve(), config=config, truth_rows=bad_truth)
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(output_dir / "normal-manifest.json", normal_manifest)
    write_json(output_dir / "bad-manifest.json", bad_manifest)
    write_json(output_dir / "normal-validation.json", normal_validation)
    write_json(output_dir / "bad-validation.json", bad_validation)
    if not normal_validation["valid"] or not bad_validation["valid"]:
        raise ValueError("manifest/truth validation failed; see validation reports")

    normal_results = run_batch(normal_manifest, normal_root, config_path)
    bad_results = run_batch(bad_manifest, bad_root, config_path)
    for name, payloads in (("normal-results.jsonl", normal_results), ("bad-results.jsonl", bad_results)):
        content = "\n".join(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) for payload in payloads)
        (output_dir / name).write_text(content + ("\n" if content else ""), encoding="utf-8")
    report = evaluate_results(normal_results + bad_results, truth_rows)
    write_json(output_dir / "evaluation.json", report)
    write_json(output_dir / "normal-report.json", report["normal"])
    write_json(output_dir / "bad-report.json", report["bad"])
    return {
        "normalImages": len(normal_results), "badImages": len(bad_results),
        "normalValidRate": report["normal"]["validRate"],
        "badFalsePositiveRate": report["bad"]["falsePositiveRate"],
        "outputDir": str(output_dir),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--normal-root", required=True, type=Path)
    parser.add_argument("--bad-root", required=True, type=Path)
    parser.add_argument("--grouping", required=True, type=Path)
    parser.add_argument("--truth", required=True, type=Path)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--expected-normal-repeats", type=int, default=20)
    parser.add_argument("--expected-bad-repeats", type=int, default=1)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        result = run_acceptance(
            args.normal_root, args.bad_root, args.grouping, args.truth, args.config, args.output_dir,
            args.expected_normal_repeats, args.expected_bad_repeats,
        )
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}")
        return 2
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
