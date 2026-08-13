#!/usr/bin/env python3
"""Batch A-end-face detection and deterministic quality aggregation."""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from algorithms.end_face.adapter import EndFaceInspector
from algorithms.end_face.contract import sha256_file
from tools.dataset_common import safe_relative_path
from tools.validate_dataset import validate_manifest


BATCH_SCHEMA_VERSION = "a-end-face-batch-quality-summary/1"
DEFAULT_POLICY = PROJECT_ROOT / "config/end_face_quality.example.json"
DEFAULT_CANDIDATE = PROJECT_ROOT / "config/end_face_short_line_candidate.v1.json"


class BatchInputError(ValueError):
    pass


def load_validated_manifest(manifest_path: Path, data_root: Path) -> dict[str, Any]:
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BatchInputError(f"cannot read Manifest: {exc}") from exc
    if manifest.get("task") != "a_end_face":
        raise BatchInputError("Manifest task must be 'a_end_face'")
    report = validate_manifest(manifest, data_root.resolve(), verify_hash=True)
    if not report["valid"]:
        codes = ", ".join(str(item["code"]) for item in report["errors"])
        raise BatchInputError(f"Manifest validation failed before detection: {codes}")
    return manifest


def _count_rate(valid: int, total: int) -> dict[str, Any]:
    return {
        "total": total,
        "valid": valid,
        "invalid": total - valid,
        "validRate": (valid / total) if total else None,
    }


def _finite_nonnegative(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) and number >= 0 else None


def summarize_results(results: Iterable[Mapping[str, Any]], dataset: Mapping[str, Any]) -> dict[str, Any]:
    materialized = list(results)
    technical_valid = 0
    localization_valid = 0
    measurement_valid = 0
    elapsed_values: list[float] = []
    feature_stats: dict[str, dict[str, Any]] = {}

    for payload in materialized:
        succeeded = payload.get("technicalStatus") == "succeeded"
        technical_valid += int(succeeded)
        result = payload.get("result") if isinstance(payload.get("result"), Mapping) else {}
        localization = result.get("localization") if isinstance(result.get("localization"), Mapping) else {}
        completeness = (
            result.get("measurementCompleteness")
            if isinstance(result.get("measurementCompleteness"), Mapping)
            else {}
        )
        localization_valid += int(succeeded and localization.get("valid") is True)
        measurement_valid += int(succeeded and completeness.get("allValid") is True)

        execution = payload.get("execution") if isinstance(payload.get("execution"), Mapping) else {}
        elapsed = _finite_nonnegative(execution.get("elapsedMs"))
        if elapsed is not None:
            elapsed_values.append(elapsed)

        features = result.get("featureQuality") if isinstance(result.get("featureQuality"), Mapping) else {}
        for label, feature in features.items():
            if not isinstance(feature, Mapping):
                continue
            canonical_label = str(feature.get("canonicalFeature") or label)
            stats = feature_stats.setdefault(canonical_label, {
                "total": 0,
                "valid": 0,
                "invalid": 0,
                "invalidRate": None,
                "classifications": Counter(),
                "sources": Counter(),
                "reasons": Counter(),
                "rawLabels": Counter(),
            })
            stats["total"] += 1
            core_valid = feature.get("coreValid") is True
            stats["valid"] += int(core_valid)
            stats["invalid"] += int(not core_valid)
            classification = feature.get("classification")
            source = feature.get("source")
            reason = feature.get("reason")
            stats["classifications"][str(classification or "unspecified")] += 1
            stats["sources"][str(source or "unspecified")] += 1
            stats["rawLabels"][str(label)] += 1
            if not core_valid:
                stats["reasons"][str(reason or "unspecified")] += 1

    serialized_features: dict[str, Any] = {}
    for label in sorted(feature_stats):
        stats = feature_stats[label]
        serialized_features[label] = {
            "total": stats["total"],
            "valid": stats["valid"],
            "invalid": stats["invalid"],
            "invalidRate": stats["invalid"] / stats["total"] if stats["total"] else None,
            "classifications": dict(sorted(stats["classifications"].items())),
            "sources": dict(sorted(stats["sources"].items())),
            "reasons": dict(sorted(stats["reasons"].items())),
            "rawLabels": dict(sorted(stats["rawLabels"].items())),
        }

    total = len(materialized)
    timing = {
        "count": len(elapsed_values),
        "meanMs": sum(elapsed_values) / len(elapsed_values) if elapsed_values else None,
        "minMs": min(elapsed_values) if elapsed_values else None,
        "maxMs": max(elapsed_values) if elapsed_values else None,
    }
    return {
        "schemaVersion": BATCH_SCHEMA_VERSION,
        "dataset": {
            "datasetId": dataset.get("datasetId"),
            "datasetFingerprint": dataset.get("datasetFingerprint"),
            "manifestSha256": dataset.get("manifestSha256"),
        },
        "imageCount": total,
        "technical": _count_rate(technical_valid, total),
        "localization": _count_rate(localization_valid, total),
        "measurementCompleteness": _count_rate(measurement_valid, total),
        "timing": timing,
        "features": serialized_features,
    }


def read_results_jsonl(path: Path) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise BatchInputError(f"invalid JSONL at line {line_number}: {exc}") from exc
            if not isinstance(value, dict):
                raise BatchInputError(f"JSONL line {line_number} must be an object")
            results.append(value)
    if not results:
        raise BatchInputError("results JSONL is empty")
    return results


def write_strict_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def detect_batch(args: argparse.Namespace) -> int:
    manifest_path = args.manifest.resolve()
    data_root = args.data_root.resolve()
    manifest = load_validated_manifest(manifest_path, data_root)
    inspector = EndFaceInspector(
        args.annotation,
        args.quality_policy,
        args.pixel_size,
        args.short_line_candidate_config,
    )
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    results_path = output_dir / "results.jsonl"
    technical_failures = 0
    with results_path.open("w", encoding="utf-8") as handle:
        for item in manifest["images"]:
            image = data_root / safe_relative_path(str(item["relativePath"]))
            payload = inspector.inspect(image, task_id=str(item["imageId"]))
            technical_failures += int(payload["technicalStatus"] != "succeeded")
            handle.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n")
    results = read_results_jsonl(results_path)
    dataset = {
        "datasetId": manifest.get("datasetId"),
        "datasetFingerprint": manifest.get("datasetFingerprint"),
        "manifestSha256": sha256_file(manifest_path),
    }
    summary = summarize_results(results, dataset)
    write_strict_json(output_dir / "quality-summary.json", summary)
    print(
        f"images={summary['imageCount']} technical={summary['technical']['valid']} "
        f"localization={summary['localization']['valid']} "
        f"measurement-complete={summary['measurementCompleteness']['valid']}"
    )
    print(f"results -> {results_path}")
    print(f"summary -> {output_dir / 'quality-summary.json'}")
    return 1 if technical_failures else 0


def summarize_jsonl(args: argparse.Namespace) -> int:
    results = read_results_jsonl(args.results_jsonl.resolve())
    dataset = {
        "datasetId": args.dataset_id,
        "datasetFingerprint": args.dataset_fingerprint,
        "manifestSha256": args.manifest_sha256,
    }
    summary = summarize_results(results, dataset)
    write_strict_json(args.output.resolve(), summary)
    print(f"summary -> {args.output.resolve()}")
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    detect_parser = subparsers.add_parser("detect", help="Validate a Manifest and detect every external image.")
    detect_parser.add_argument("--manifest", required=True, type=Path)
    detect_parser.add_argument("--data-root", required=True, type=Path)
    detect_parser.add_argument("--annotation", required=True, type=Path)
    detect_parser.add_argument("--quality-policy", type=Path, default=DEFAULT_POLICY)
    detect_parser.add_argument("--pixel-size", type=float, default=1.0)
    detect_parser.add_argument("--short-line-candidate-config", type=Path, default=DEFAULT_CANDIDATE)
    detect_parser.add_argument("--output-dir", required=True, type=Path)
    detect_parser.set_defaults(handler=detect_batch)

    summary_parser = subparsers.add_parser("summarize", help="Recompute quality statistics without image access.")
    summary_parser.add_argument("--results-jsonl", required=True, type=Path)
    summary_parser.add_argument("--output", required=True, type=Path)
    summary_parser.add_argument("--dataset-id")
    summary_parser.add_argument("--dataset-fingerprint")
    summary_parser.add_argument("--manifest-sha256")
    summary_parser.set_defaults(handler=summarize_jsonl)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        return int(args.handler(args))
    except (BatchInputError, OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
