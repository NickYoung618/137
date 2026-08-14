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


def circular_mean_deg(values: list[float]) -> float | None:
    if not values:
        return None
    radians = [math.radians(value) for value in values]
    sine = statistics.fmean(math.sin(value) for value in radians)
    cosine = statistics.fmean(math.cos(value) for value in radians)
    if abs(sine) < 1e-12 and abs(cosine) < 1e-12:
        return None
    return math.degrees(math.atan2(sine, cosine))


def circular_describe(values: list[float]) -> dict[str, float | int | None]:
    center = circular_mean_deg(values)
    if center is None:
        return {"n": len(values), "meanDeg": None, "rangeDeg": None, "standardDeviationDeg": None}
    unwrapped = [center + circular_error_deg(value, center) for value in values]
    return {
        "n": len(values),
        "meanDeg": center,
        "rangeDeg": max(unwrapped) - min(unwrapped),
        "standardDeviationDeg": statistics.stdev(unwrapped) if len(unwrapped) > 1 else 0.0,
    }


def timing_summary(values: list[float]) -> dict[str, float | int | None]:
    return {
        "n": len(values), "mean": statistics.fmean(values) if values else None,
        "p50": percentile(values, 0.5), "p95": percentile(values, 0.95),
        "max": max(values) if values else None,
    }


def evaluate_results(results: list[dict[str, Any]], truth_rows: list[dict[str, str]]) -> dict[str, Any]:
    by_hash = {row["image_sha256"]: row for row in truth_rows}
    matched: list[dict[str, Any]] = []
    normal_errors: list[float] = []
    normal_timings: list[float] = []
    bad_timings: list[float] = []
    normal_error_codes: Counter[str] = Counter()
    bad_error_codes: Counter[str] = Counter()
    static_errors: dict[tuple[str, str], list[float]] = defaultdict(list)
    normal_matched = bad_matched = normal_valid = 0
    false_positive = false_negative = 0
    for payload in results:
        truth = by_hash.get(payload.get("image", {}).get("sha256"))
        if truth is None:
            continue
        matched.append(payload)
        expected_valid = truth.get("truth_valid", "true").lower() == "true"
        dataset_class = truth.get("dataset_class", "normal" if expected_valid else "bad").strip().lower()
        is_bad = dataset_class == "bad" or not expected_valid
        actual_valid = payload.get("result", {}).get("valid") is True
        if is_bad:
            bad_matched += 1
        else:
            normal_matched += 1
        if actual_valid and is_bad:
            false_positive += 1
        if not is_bad and expected_valid and not actual_valid:
            false_negative += 1
        if not actual_valid:
            target_counter = bad_error_codes if is_bad else normal_error_codes
            target_counter[str(payload.get("error", {}).get("code", "UNKNOWN"))] += 1
        if actual_valid and not is_bad:
            normal_valid += 1
        if actual_valid and expected_valid and not is_bad and truth.get("truth_angle_deg", "") != "":
            angle = float(payload["result"]["signedRelativeRotationDeg"])
            error = circular_error_deg(angle, float(truth["truth_angle_deg"]))
            normal_errors.append(error)
            condition = truth.get("condition") or truth.get("position") or "unknown_condition"
            static_errors[(truth.get("sample", "unknown_sample"), condition)].append(error)
        elapsed = payload.get("diagnostics", {}).get("elapsedMs")
        if isinstance(elapsed, (int, float)):
            (bad_timings if is_bad else normal_timings).append(float(elapsed))

    absolute = [abs(item) for item in normal_errors]
    static: list[dict[str, Any]] = []
    sample_condition_means: dict[str, list[float]] = defaultdict(list)
    for (sample, condition), values in sorted(static_errors.items()):
        stats = circular_describe(values)
        static.append({
            "sample": sample, "condition": condition, "position": condition, **stats,
            "status": "COMPLETE" if len(values) >= 20 else "INCOMPLETE",
        })
        if stats["meanDeg"] is not None:
            sample_condition_means[sample].append(float(stats["meanDeg"]))
    cross_condition = []
    for sample, residual_means in sorted(sample_condition_means.items()):
        stats = circular_describe(residual_means)
        cross_condition.append({
            "sample": sample, "conditionCount": len(residual_means),
            "residualMeanRangeDeg": stats["rangeDeg"],
            "residualMeanStandardDeviationDeg": stats["standardDeviationDeg"],
            "status": "COMPLETE" if len(residual_means) >= 2 else "INCOMPLETE",
        })
    sample_positions: dict[str, set[str]] = defaultdict(set)
    for row in truth_rows:
        expected_valid = row.get("truth_valid", "true").lower() == "true"
        if row.get("dataset_class", "normal" if expected_valid else "bad").lower() != "bad" and expected_valid:
            sample_positions[row.get("sample", "unknown_sample")].add(row.get("condition") or row.get("position", "unknown_condition"))
    data_complete = bool(static) and all(item["status"] == "COMPLETE" for item in static)
    dynamic_complete = bool(sample_positions) and all(len(positions) >= 2 for positions in sample_positions.values())
    normal_report = {
        "schemaVersion": "slot-pose-normal-evaluation/1",
        "status": "COMPLETE" if data_complete and dynamic_complete else "INCOMPLETE",
        "matchedCount": normal_matched,
        "validCount": normal_valid,
        "validRate": normal_valid / normal_matched if normal_matched else None,
        "falseNegativeCount": false_negative,
        "angleErrorDeg": {
            "n": len(normal_errors), "mae": statistics.fmean(absolute) if absolute else None,
            "p95": percentile(absolute, 0.95), "max": max(absolute) if absolute else None,
        },
        "staticRepeatability": static,
        "crossConditionResidual": cross_condition,
        "errorCodeCounts": dict(sorted(normal_error_codes.items())),
        "elapsedMs": timing_summary(normal_timings),
        "thresholdEvaluation": "NOT_EVALUATED",
    }
    bad_report = {
        "schemaVersion": "slot-pose-bad-image-evaluation/1",
        "status": "COMPLETE" if bad_matched else "INCOMPLETE",
        "matchedCount": bad_matched,
        "falsePositiveCount": false_positive,
        "misguidanceCount": false_positive,
        "falsePositiveRate": false_positive / bad_matched if bad_matched else None,
        "invalidCount": bad_matched - false_positive,
        "errorCodeCounts": dict(sorted(bad_error_codes.items())),
        "elapsedMs": timing_summary(bad_timings),
        "thresholdEvaluation": "NOT_EVALUATED",
    }
    return {
        "schemaVersion": "slot-pose-evaluation/1",
        "status": "COMPLETE" if data_complete and dynamic_complete else "INCOMPLETE",
        "truthCount": len(truth_rows), "resultCount": len(results), "matchedCount": len(matched),
        "successRate": normal_valid / normal_matched if normal_matched else None,
        "falseNegativeCount": false_negative, "falsePositiveCount": false_positive,
        "angleErrorDeg": normal_report["angleErrorDeg"],
        "staticRepeatability": static,
        "dynamicStatus": "COMPLETE" if dynamic_complete else "INCOMPLETE",
        "crossConditionResidual": cross_condition,
        "errorCodeCounts": dict(sorted((normal_error_codes + bad_error_codes).items())),
        "elapsedMs": timing_summary(normal_timings + bad_timings),
        "thresholdEvaluation": "NOT_EVALUATED",
        "normal": normal_report,
        "bad": bad_report,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", required=True, type=Path, help="One result JSON object per line.")
    parser.add_argument("--truth", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--normal-output", type=Path)
    parser.add_argument("--bad-output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        results = [json.loads(line) for line in args.results.read_text(encoding="utf-8").splitlines() if line.strip()]
        with args.truth.open(newline="", encoding="utf-8-sig") as handle:
            truth = list(csv.DictReader(handle))
        report = evaluate_results(results, truth)
        write_json(args.output, report)
        if args.normal_output:
            write_json(args.normal_output, report["normal"])
        if args.bad_output:
            write_json(args.bad_output, report["bad"])
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}")
        return 2
    print(f"Wrote {args.output}: status={report['status']}, matched={report['matchedCount']}, angle_n={report['angleErrorDeg']['n']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
