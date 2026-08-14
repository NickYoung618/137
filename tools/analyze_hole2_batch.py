#!/usr/bin/env python3
"""Analyze external hole-2 JSONL without inferring repeat groups from filenames."""
from __future__ import annotations

import argparse
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict) or "imagePath" not in value:
                raise ValueError(f"invalid record at line {line_number}")
            records.append(value)
    if not records:
        raise ValueError("results JSONL is empty")
    return records


def build_explicit_groups(
    records: list[dict[str, Any]],
    *,
    group_size: int | None,
    manifest: dict[str, Any] | None,
) -> list[str]:
    """Return one explicit group label per record; filenames never define groups."""
    if (group_size is None) == (manifest is None):
        raise ValueError("provide exactly one explicit grouping source: group_size or manifest")
    if group_size is not None:
        if group_size < 1:
            raise ValueError("explicit group_size must be positive")
        counters: dict[str, int] = defaultdict(int)
        labels: list[str] = []
        for record in records:
            batch = str(record.get("group", "unassigned"))
            chunk = counters[batch] // group_size
            labels.append(f"{batch}/explicit-{chunk:04d}")
            counters[batch] += 1
        return labels

    images = manifest.get("images") if isinstance(manifest, dict) else None
    if not isinstance(images, list) or not images:
        raise ValueError("manifest.images must be a non-empty list")
    by_basename: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in images:
        relative = str(item.get("relativePath", ""))
        by_basename[Path(relative).name].append(item)
    labels = []
    for record in records:
        matches = by_basename.get(Path(str(record["imagePath"])).name, [])
        if len(matches) != 1:
            raise ValueError(f"manifest mapping is not unique for {record['imagePath']}")
        item = matches[0]
        sample = str(item.get("sampleId", ""))
        position = str(item.get("position", ""))
        if not sample or not position:
            raise ValueError("manifest group requires sampleId and position")
        labels.append(f"{sample}/{position}")
    return labels


def _feature(record: dict[str, Any], name: str) -> dict[str, Any]:
    result = record.get("result") or {}
    return (result.get("features") or {}).get(name) or {}


def _valid_state(record: dict[str, Any], state: str) -> bool:
    result = record.get("result") or {}
    if state == "registration":
        return bool((result.get("registration") or {}).get("registrationValid"))
    return bool(_feature(record, state).get("measurementValid"))


def _failure_runs(records: list[dict[str, Any]], groups: list[str], state: str) -> list[dict[str, Any]]:
    runs: list[dict[str, Any]] = []
    current: list[int] = []
    current_group: str | None = None
    for index, (record, group) in enumerate(zip(records, groups)):
        failed = not _valid_state(record, state)
        if failed and (current_group is None or current_group == group):
            current.append(index)
            current_group = group
            continue
        if current:
            runs.append(_run_record(records, current, current_group or ""))
        current = [index] if failed else []
        current_group = group if failed else None
    if current:
        runs.append(_run_record(records, current, current_group or ""))
    return runs


def _run_record(records: list[dict[str, Any]], indices: list[int], group: str) -> dict[str, Any]:
    return {
        "group": group,
        "count": len(indices),
        "startIndex": indices[0],
        "endIndex": indices[-1],
        "startImagePath": str(records[indices[0]]["imagePath"]),
        "endImagePath": str(records[indices[-1]]["imagePath"]),
    }


def _distribution(values: list[float]) -> dict[str, Any]:
    if not values:
        return {"count": 0, "mean": None, "median": None, "range": None, "stdev": None}
    return {
        "count": len(values),
        "mean": float(statistics.fmean(values)),
        "median": float(statistics.median(values)),
        "range": float(max(values) - min(values)),
        "stdev": float(statistics.pstdev(values)),
    }


def analyze_records(
    records: list[dict[str, Any]],
    groups: list[str],
    *,
    ratio_baseline: float | None,
    ratio_thresholds: list[float],
) -> dict[str, Any]:
    if len(records) != len(groups):
        raise ValueError("record/group count mismatch")
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    ratios: list[dict[str, Any]] = []
    for record, group in zip(records, groups):
        grouped[group].append(record)
        d7 = _feature(record, "7")
        phi = _feature(record, "Phi12.2")
        if d7.get("measurementValid") and phi.get("measurementValid"):
            length = float(d7["target"]["lengthPx"])
            diameter = float(phi["target"]["diameterPx"])
            if math.isfinite(length) and math.isfinite(diameter) and diameter > 0.0:
                ratio = length / diameter
                ratios.append({"imagePath": record["imagePath"], "ratio": ratio})
    repeatability = []
    for name, items in grouped.items():
        d7_values = [float(_feature(item, "7")["target"]["lengthPx"])
                     for item in items if _feature(item, "7").get("measurementValid")]
        phi_values = [float(_feature(item, "Phi12.2")["target"]["diameterPx"])
                      for item in items if _feature(item, "Phi12.2").get("measurementValid")]
        repeatability.append({
            "group": name, "count": len(items),
            "7LengthPx": _distribution(d7_values),
            "Phi12.2DiameterPx": _distribution(phi_values),
        })
    deviation_counts: dict[str, int] = {}
    if ratio_baseline is not None:
        for threshold in ratio_thresholds:
            deviation_counts[str(threshold)] = sum(
                abs(item["ratio"] - ratio_baseline) > threshold for item in ratios
            )
        for item in ratios:
            item["absoluteDeviation"] = abs(item["ratio"] - ratio_baseline)
    return {
        "schemaVersion": "hole2-batch-diagnostics/1",
        "groupingEvidence": "explicit_group_size_or_manifest_only",
        "recordCount": len(records),
        "consecutiveFailureRuns": {
            state: _failure_runs(
                records,
                [str(record.get("group", "unassigned")) for record in records],
                state,
            )
            for state in ("registration", "7", "Phi12.2")
        },
        "repeatabilityGroups": repeatability,
        "geometryConsistency": {
            "ratioDefinition": "target_7_length_px/target_Phi12.2_diameter_px",
            "baseline": ratio_baseline,
            "bothValidCount": len(ratios),
            "absoluteDeviationCounts": deviation_counts,
            "records": ratios,
        },
        "evidenceScope": "diagnostic_only_no_target_annotation_no_production_ok_ng",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-jsonl", required=True, type=Path)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--group-size", type=int, help="Explicit ordered repeat group size.")
    group.add_argument("--manifest", type=Path, help="Manifest with sampleId/position grouping.")
    parser.add_argument("--ratio-baseline", type=float)
    parser.add_argument("--ratio-threshold", action="append", type=float, default=[])
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    repository_root = Path(__file__).resolve().parents[1]
    output_path = args.output.expanduser().resolve()
    if output_path == repository_root or repository_root in output_path.parents:
        raise ValueError("diagnostic output must remain outside the Git worktree")
    records = _load_jsonl(args.results_jsonl)
    manifest = None if args.manifest is None else json.loads(args.manifest.read_text(encoding="utf-8"))
    labels = build_explicit_groups(records, group_size=args.group_size, manifest=manifest)
    report = analyze_records(
        records, labels, ratio_baseline=args.ratio_baseline,
        ratio_thresholds=args.ratio_threshold,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"diagnostics -> {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
