#!/usr/bin/env python3
"""Evaluate static and dynamic repeatability from measurement CSV rows."""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

try:
    from .dataset_common import write_json
except ImportError:  # Direct script execution.
    from dataset_common import write_json


STAT_FIELDS = [
    "feature_code",
    "feature_name",
    "sample_id",
    "position",
    "unit",
    "n",
    "mean",
    "standard_deviation",
    "six_sigma",
    "min",
    "max",
    "range",
    "repeatability_tier",
    "tier_limit",
    "tier_status",
    "data_status",
]


def finite_number(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def describe(values: Iterable[float]) -> dict[str, float | int | None]:
    data = list(values)
    if not data:
        return {key: None for key in ("mean", "standard_deviation", "six_sigma", "min", "max", "range")} | {"n": 0}
    deviation = statistics.stdev(data) if len(data) >= 2 else 0.0
    return {
        "n": len(data),
        "mean": statistics.fmean(data),
        "standard_deviation": deviation,
        "six_sigma": 6.0 * deviation,
        "min": min(data),
        "max": max(data),
        "range": max(data) - min(data),
    }


def convert_value(raw: float, feature: dict, mm_per_px: float | None) -> tuple[float, str, bool]:
    scale = float(feature.get("scale", 1.0))
    source_unit = feature.get("source_unit", "px")
    output_unit = feature.get("output_unit", source_unit)
    scaled = raw * scale
    if source_unit in {"px", "ref_px"} and output_unit == "mm":
        if mm_per_px is None:
            return scaled, "px", False
        return scaled * mm_per_px, "mm", True
    return scaled, output_unit, True


def tier_result(stats: dict, feature: dict, config: dict, unit: str, enough_data: bool) -> tuple[object, object, str]:
    tier_name = feature.get("repeatability_tier")
    tier = config.get("repeatability", {}).get("tiers", {}).get(tier_name, {})
    limit = tier.get("limit")
    tier_unit = tier.get("unit")
    if not enough_data:
        return tier_name, limit, "INCOMPLETE"
    if limit is None or tier_unit != unit:
        return tier_name, limit, "NOT_EVALUATED"
    metric = config.get("repeatability", {}).get("metric", "range")
    measured = stats.get(metric)
    if measured is None:
        return tier_name, limit, "NOT_EVALUATED"
    return tier_name, limit, "PASS" if float(measured) <= float(limit) else "FAIL"


def evaluate(rows: list[dict[str, str]], config: dict, sample_column: str, position_column: str) -> tuple[list[dict], list[dict]]:
    mm_per_px = finite_number(config.get("calibration", {}).get("mm_per_px"))
    repeatability = config.get("repeatability", {})
    min_repeats = int(repeatability.get("min_valid_repeats", 20))
    min_positions = int(repeatability.get("min_dynamic_positions", 2))
    static_values: dict[tuple[str, str, str], list[tuple[float, str]]] = defaultdict(list)

    for row in rows:
        sample = row.get(sample_column, "") or "unknown_sample"
        position = row.get(position_column, "") or "unknown_position"
        for feature in config.get("feature_mappings", []):
            if not feature.get("enabled", True):
                continue
            raw = finite_number(row.get(feature.get("source_column", "")))
            if raw is None:
                continue
            value, unit, _calibrated = convert_value(raw, feature, mm_per_px)
            static_values[(feature["feature_code"], sample, position)].append((value, unit))

    features = {item["feature_code"]: item for item in config.get("feature_mappings", [])}
    static_rows: list[dict] = []
    position_means: dict[tuple[str, str], list[tuple[str, float, str]]] = defaultdict(list)
    for (feature_code, sample, position), values_and_units in sorted(static_values.items()):
        values = [item[0] for item in values_and_units]
        unit = values_and_units[0][1]
        stats = describe(values)
        enough = int(stats["n"] or 0) >= min_repeats
        feature = features[feature_code]
        tier_name, tier_limit, tier_status = tier_result(stats, feature, config, unit, enough)
        static_rows.append(
            {
                "feature_code": feature_code,
                "feature_name": feature.get("name", feature_code),
                "sample_id": sample,
                "position": position,
                "unit": unit,
                **stats,
                "repeatability_tier": tier_name,
                "tier_limit": tier_limit,
                "tier_status": tier_status,
                "data_status": "COMPLETE" if enough else "INCOMPLETE",
            }
        )
        if stats["mean"] is not None:
            position_means[(feature_code, sample)].append((position, float(stats["mean"]), unit))

    dynamic_rows: list[dict] = []
    for (feature_code, sample), position_data in sorted(position_means.items()):
        stats = describe(item[1] for item in position_data)
        unit = position_data[0][2]
        enough = int(stats["n"] or 0) >= min_positions
        feature = features[feature_code]
        tier_name, tier_limit, tier_status = tier_result(stats, feature, config, unit, enough)
        dynamic_rows.append(
            {
                "feature_code": feature_code,
                "feature_name": feature.get("name", feature_code),
                "sample_id": sample,
                "position": "position_means",
                "unit": unit,
                **stats,
                "repeatability_tier": tier_name,
                "tier_limit": tier_limit,
                "tier_status": tier_status,
                "data_status": "COMPLETE" if enough else "INCOMPLETE",
            }
        )
    return static_rows, dynamic_rows


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=STAT_FIELDS)
        writer.writeheader()
        for row in rows:
            formatted = {}
            for field in STAT_FIELDS:
                value = row.get(field)
                formatted[field] = f"{value:.9f}" if isinstance(value, float) else value
            writer.writerow(formatted)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--measurements", required=True, type=Path)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--sample-column", default="sample")
    parser.add_argument("--position-column", default="position")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        config = json.loads(args.config.read_text(encoding="utf-8"))
        with args.measurements.open(newline="", encoding="utf-8-sig") as handle:
            rows = list(csv.DictReader(handle))
        static_rows, dynamic_rows = evaluate(rows, config, args.sample_column, args.position_column)
        write_csv(args.output_dir / "static_repeatability.csv", static_rows)
        write_csv(args.output_dir / "dynamic_repeatability.csv", dynamic_rows)
        report = {
            "schemaVersion": "inspection-repeatability-report/1",
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "measurementSource": str(args.measurements),
            "configSource": str(args.config),
            "calibration": config.get("calibration", {}),
            "definitions": {
                "static": "variation of repeated images for one sample at one fixed position",
                "dynamic": "variation of position means for one sample after position changes",
                "standardDeviation": "sample standard deviation (n-1)",
                "sixSigma": "6 × sample standard deviation",
            },
            "inputRowCount": len(rows),
            "static": static_rows,
            "dynamic": dynamic_rows,
        }
        write_json(args.output_dir / "repeatability_report.json", report)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}")
        return 2
    print(
        f"Wrote {args.output_dir}: input_rows={len(rows)}, "
        f"static_groups={len(static_rows)}, dynamic_groups={len(dynamic_rows)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
