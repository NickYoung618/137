#!/usr/bin/env python3
"""Evaluate JSONL slot-pose results against controlled angle truth CSV."""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

try:
    from .dataset_common import write_json
except ImportError:
    from dataset_common import write_json


def circular_error_deg(estimate: float, truth: float) -> float:
    return (float(estimate) - float(truth) + 180.0) % 360.0 - 180.0


def percentile(values: list[float], quantile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = (len(ordered) - 1) * quantile
    low = math.floor(index)
    high = math.ceil(index)
    if low == high:
        return ordered[low]
    return ordered[low] * (high - index) + ordered[high] * (index - low)


def evaluate_results(results: list[dict[str, Any]], truth_rows: list[dict[str, str]]) -> dict[str, Any]:
    by_hash = {row["image_sha256"]: row for row in truth_rows}
    matched = []
    errors: list[float] = []
    timings: list[float] = []
    error_codes: Counter[str] = Counter()
    static_angles: dict[tuple[str, str], list[float]] = defaultdict(list)
    false_positive = false_negative = 0
    for payload in results:
        truth = by_hash.get(payload.get("image", {}).get("sha256"))
        if truth is None:
            continue
        matched.append(payload)
        expected_valid = truth.get("truth_valid", "true").lower() == "true"
        actual_valid = payload.get("result", {}).get("valid") is True
        if actual_valid and not expected_valid:
            false_positive += 1
        if expected_valid and not actual_valid:
            false_negative += 1
        if not actual_valid:
            error_codes[str(payload.get("error", {}).get("code", "UNKNOWN"))] += 1
        if actual_valid and expected_valid:
            angle = float(payload["result"]["signedRelativeRotationDeg"])
            error = circular_error_deg(angle, float(truth["truth_angle_deg"]))
            errors.append(error)
            static_angles[(truth["sample"], truth["position"])].append(angle)
        elapsed = payload.get("diagnostics", {}).get("elapsedMs")
        if isinstance(elapsed, (int, float)):
            timings.append(float(elapsed))

    absolute = [abs(item) for item in errors]
    static = []
    for (sample, position), values in sorted(static_angles.items()):
        static.append({
            "sample": sample, "position": position, "n": len(values),
            "rangeDeg": max(values) - min(values) if values else None,
            "standardDeviationDeg": statistics.stdev(values) if len(values) > 1 else 0.0,
            "status": "COMPLETE" if len(values) >= 20 else "INCOMPLETE",
        })
    sample_positions: dict[str, set[str]] = defaultdict(set)
    for row in truth_rows:
        sample_positions[row["sample"]].add(row["position"])
    data_complete = bool(truth_rows) and all(item["status"] == "COMPLETE" for item in static)
    dynamic_complete = all(len(positions) >= 2 for positions in sample_positions.values())
    return {
        "schemaVersion": "slot-pose-evaluation/1",
        "status": "COMPLETE" if data_complete and dynamic_complete else "INCOMPLETE",
        "truthCount": len(truth_rows), "resultCount": len(results), "matchedCount": len(matched),
        "successRate": (sum(1 for item in matched if item.get("result", {}).get("valid")) / len(matched)) if matched else None,
        "falseNegativeCount": false_negative, "falsePositiveCount": false_positive,
        "angleErrorDeg": {
            "n": len(errors), "mae": statistics.fmean(absolute) if absolute else None,
            "p95": percentile(absolute, 0.95), "max": max(absolute) if absolute else None,
        },
        "staticRepeatability": static,
        "dynamicStatus": "COMPLETE" if dynamic_complete else "INCOMPLETE",
        "errorCodeCounts": dict(sorted(error_codes.items())),
        "elapsedMs": {
            "n": len(timings), "mean": statistics.fmean(timings) if timings else None,
            "p50": percentile(timings, 0.5), "p95": percentile(timings, 0.95), "max": max(timings) if timings else None,
        },
        "thresholdEvaluation": "NOT_EVALUATED",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", required=True, type=Path, help="One result JSON object per line.")
    parser.add_argument("--truth", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        results = [json.loads(line) for line in args.results.read_text(encoding="utf-8").splitlines() if line.strip()]
        with args.truth.open(newline="", encoding="utf-8-sig") as handle:
            truth = list(csv.DictReader(handle))
        report = evaluate_results(results, truth)
        write_json(args.output, report)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}")
        return 2
    print(f"Wrote {args.output}: status={report['status']}, matched={report['matchedCount']}, angle_n={report['angleErrorDeg']['n']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
