#!/usr/bin/env python3
"""Combine one truth-anchor report with manifest-driven unlabeled diagnostics.

This offline tool does not read images or target annotations and does not run the
detector.  Unlabeled measurements are repeatability diagnostics, never accuracy
truth or production dispositions.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _external_path(path: Path, label: str) -> Path:
    resolved = path.expanduser().resolve()
    repository = PROJECT_ROOT.resolve()
    if resolved == repository or repository in resolved.parents:
        raise ValueError(f"{label} must remain outside the Git worktree")
    return resolved


def _load_jsonl(paths: Iterable[Path]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in paths:
        with path.open("r", encoding="utf-8") as stream:
            for line_number, line in enumerate(stream, 1):
                if not line.strip():
                    continue
                value = json.loads(line)
                if not isinstance(value, dict) or not value.get("imagePath"):
                    raise ValueError(f"invalid record at {path}:{line_number}")
                records.append(value)
    if not records:
        raise ValueError("study JSONL inputs are empty")
    return records


def map_manifest(
    records: list[dict[str, Any]], manifest: dict[str, Any]
) -> list[dict[str, Any]]:
    """Map every record exactly once using an explicit external manifest."""
    frames = manifest.get("frames") if isinstance(manifest, dict) else None
    if not isinstance(frames, list) or not frames:
        raise ValueError("manifest.frames must be a non-empty list")

    manifest_by_name: dict[str, dict[str, str]] = {}
    for index, item in enumerate(frames):
        if not isinstance(item, dict):
            raise ValueError(f"manifest frame {index} must be an object")
        name = Path(str(item.get("fileName", ""))).name
        if not name:
            raise ValueError(f"manifest frame {index} requires fileName")
        if name in manifest_by_name:
            raise ValueError(f"duplicate manifest fileName: {name}")
        normalized: dict[str, str] = {"fileName": name}
        for field in ("population", "role", "captureGroupId"):
            value = str(item.get(field, "")).strip()
            if not value:
                raise ValueError(f"manifest frame {name} requires {field}")
            normalized[field] = value
        manifest_by_name[name] = normalized

    record_by_name: dict[str, dict[str, Any]] = {}
    for record in records:
        name = Path(str(record["imagePath"])).name
        if name in record_by_name:
            raise ValueError(f"duplicate JSONL image basename: {name}")
        record_by_name[name] = record

    missing = sorted(set(record_by_name) - set(manifest_by_name))
    if missing:
        raise ValueError(f"unmapped JSONL frames: {missing}")
    unused = sorted(set(manifest_by_name) - set(record_by_name))
    if unused:
        raise ValueError(f"manifest frames absent from JSONL: {unused}")

    mapped: list[dict[str, Any]] = []
    for record in records:
        name = Path(str(record["imagePath"])).name
        mapped.append({"record": record, **manifest_by_name[name]})
    return mapped


def _feature(record: dict[str, Any], name: str) -> dict[str, Any]:
    return (((record.get("result") or {}).get("features") or {}).get(name) or {})


def _feature_value(feature: dict[str, Any], name: str) -> float | None:
    if not feature.get("measurementValid"):
        return None
    target = feature.get("target") or {}
    key = "lengthPx" if name == "7" else "diameterPx"
    try:
        value = float(target[key])
    except (KeyError, TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def _count_text(values: Iterable[object]) -> dict[str, int]:
    return dict(sorted(Counter(str(value) for value in values if value not in (None, "")).items()))


def _distribution(values: list[float]) -> dict[str, float | int | None]:
    if not values:
        return {
            "count": 0,
            "medianPx": None,
            "minimumPx": None,
            "maximumPx": None,
            "rangePx": None,
            "medianAbsoluteDeviationPx": None,
        }
    median = float(statistics.median(values))
    return {
        "count": len(values),
        "medianPx": median,
        "minimumPx": float(min(values)),
        "maximumPx": float(max(values)),
        "rangePx": float(max(values) - min(values)),
        "medianAbsoluteDeviationPx": float(
            statistics.median(abs(value - median) for value in values)
        ),
    }


def _static_repeatability(values: list[float], minimum_group_frames: int) -> dict[str, Any]:
    enough = len(values) >= minimum_group_frames
    mean = float(statistics.fmean(values)) if values else None
    sample_deviation = float(statistics.stdev(values)) if len(values) >= 2 else None
    median = float(statistics.median(values)) if values else None
    mad = (
        float(statistics.median(abs(value - median) for value in values))
        if median is not None
        else None
    )
    return {
        "evaluationStatus": "EVALUATED" if enough else "INCOMPLETE",
        "unit": "px",
        "validFrameCount": len(values),
        "requiredValidFrames": minimum_group_frames,
        "meanPx": mean,
        "sampleStandardDeviationPx": sample_deviation,
        "sixSigmaPx": None if sample_deviation is None else 6.0 * sample_deviation,
        "rangePx": None if not values else float(max(values) - min(values)),
        "medianAbsoluteDeviationPx": mad,
        "threshold": None,
        "disposition": "diagnostic_only_no_pass_fail_threshold",
    }


def _feature_group(
    items: list[dict[str, Any]], feature_name: str, minimum_group_frames: int
) -> dict[str, Any]:
    rows: list[tuple[dict[str, Any], dict[str, Any], float | None]] = []
    for item in items:
        feature = _feature(item["record"], feature_name)
        rows.append((item, feature, _feature_value(feature, feature_name)))
    values = [value for _item, _feature_item, value in rows if value is not None]
    distribution = _distribution(values)
    median = distribution["medianPx"]
    frames = []
    for item, feature, value in rows:
        frames.append(
            {
                "fileName": item["fileName"],
                "role": item["role"],
                "measurementValid": bool(feature.get("measurementValid")),
                "valuePx": value,
                "absoluteDeviationFromGroupMedianPx": (
                    None if value is None or median is None else abs(value - float(median))
                ),
                "failureReason": feature.get("failureReason"),
                "sourceDetector": feature.get("sourceDetector"),
                "recoveryPass": feature.get("recoveryPass"),
            }
        )
    frames.sort(
        key=lambda row: (
            row["absoluteDeviationFromGroupMedianPx"] is None,
            -(row["absoluteDeviationFromGroupMedianPx"] or 0.0),
            row["fileName"],
        )
    )
    return {
        "validCount": len(values),
        "invalidCount": len(items) - len(values),
        **distribution,
        "repeatabilityEvaluable": len(items) >= minimum_group_frames and len(values) >= minimum_group_frames,
        "minimumGroupFrames": minimum_group_frames,
        "staticRepeatability": _static_repeatability(values, minimum_group_frames),
        "failureReasons": _count_text(
            feature.get("failureReason") for _item, feature, value in rows if value is None
        ),
        "sourceDetectors": _count_text(feature.get("sourceDetector") for _item, feature, _value in rows),
        "recoveryPasses": _count_text(feature.get("recoveryPass") for _item, feature, _value in rows),
        "frames": frames,
    }


def _cohort(items: list[dict[str, Any]]) -> dict[str, Any]:
    records = [item["record"] for item in items]
    registration_valid = sum(
        bool(((record.get("result") or {}).get("registration") or {}).get("registrationValid"))
        for record in records
    )
    feature_valid = {
        name: sum(bool(_feature(record, name).get("measurementValid")) for record in records)
        for name in ("7", "Phi12.2")
    }
    both = sum(
        bool(_feature(record, "7").get("measurementValid"))
        and bool(_feature(record, "Phi12.2").get("measurementValid"))
        for record in records
    )
    return {
        "total": len(records),
        "executionSuccess": sum(record.get("executionError") in (None, "") for record in records),
        "registrationValid": registration_valid,
        "registrationInvalid": len(records) - registration_valid,
        "featureValid": feature_valid,
        "featureInvalid": {name: len(records) - count for name, count in feature_valid.items()},
        "bothMeasurementsValid": both,
        "failureReasons": {
            name: _count_text(
                _feature(record, name).get("failureReason")
                for record in records
                if not _feature(record, name).get("measurementValid")
            )
            for name in ("7", "Phi12.2")
        },
        "evidenceScope": "status_and_quality_diagnostic_not_accuracy",
    }


def _accuracy_anchor(truth_report: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(truth_report, dict) or "status" not in truth_report:
        raise ValueError("truth report must contain status")
    features = {}
    for name, error_key in (("7", "lengthAbsoluteErrorPx"), ("Phi12.2", "diameterAbsoluteErrorPx")):
        item = truth_report.get(name)
        if not isinstance(item, dict):
            raise ValueError(f"truth report must contain {name}")
        features[name] = {
            error_key: item.get(error_key),
            "maximumAllowedPx": item.get("maximumAllowedPx"),
            "passed": bool(item.get("passed")),
        }
    return {
        "status": str(truth_report["status"]),
        "truthHashes": truth_report.get("truthHashes"),
        **features,
        "evidenceScope": "single_truth_only",
    }


def analyze_study(
    mapped: list[dict[str, Any]],
    truth_report: dict[str, Any],
    *,
    minimum_group_frames: int = 20,
) -> dict[str, Any]:
    if minimum_group_frames < 2:
        raise ValueError("minimum_group_frames must be at least 2")
    cohort_items: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    capture_items: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for item in mapped:
        cohort_items[(item["population"], item["role"])].append(item)
        capture_items[(item["population"], item["captureGroupId"])].append(item)

    cohorts = {
        f"{population}/{role}": _cohort(items)
        for (population, role), items in sorted(cohort_items.items())
    }
    capture_groups = []
    for (population, capture_group_id), items in sorted(capture_items.items()):
        capture_groups.append(
            {
                "population": population,
                "captureGroupId": capture_group_id,
                "roles": sorted({item["role"] for item in items}),
                "frameCount": len(items),
                "features": {
                    name: _feature_group(items, name, minimum_group_frames)
                    for name in ("7", "Phi12.2")
                },
                "evidenceScope": "diagnostic_not_accuracy",
            }
        )
    return {
        "schemaVersion": "hole2-single-truth-repeatability-study/1",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "accuracyAnchor": _accuracy_anchor(truth_report),
        "cohorts": cohorts,
        "captureGroups": capture_groups,
        "evidenceBoundary": {
            "absoluteAccuracy": "accuracyAnchor only",
            "unlabeledFrames": "status, image-quality provenance, and within-capture repeatability only",
            "pseudoTruthCreated": False,
            "millimetreConversion": False,
            "productionDisposition": "not_evaluated",
            "normalAndDefectiveCombined": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jsonl", action="append", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--truth-report", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--minimum-group-frames", type=int, default=20)
    args = parser.parse_args()
    try:
        output = _external_path(args.output, "study output")
        records = _load_jsonl(args.jsonl)
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        truth = json.loads(args.truth_report.read_text(encoding="utf-8"))
        report = analyze_study(
            map_manifest(records, manifest),
            truth,
            minimum_group_frames=args.minimum_group_frames,
        )
        report["runtimeInputs"] = {
            "jsonl": [str(path.expanduser().resolve()) for path in args.jsonl],
            "manifest": str(args.manifest.expanduser().resolve()),
            "truthReport": str(args.truth_report.expanduser().resolve()),
        }
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(f"single-truth study -> {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
