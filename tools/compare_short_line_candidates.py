#!/usr/bin/env python3
"""Compare the immutable core with the versioned 19/30 candidate on external images."""

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

from algorithms.end_face import CORE_SOURCE_SHA256, core
from algorithms.end_face.contract import sha256_file
from algorithms.end_face.quality import canonical_feature_label
from algorithms.end_face.short_line_candidate import ShortLineCandidateEvaluator, load_candidate_config
from tools.dataset_common import safe_relative_path
from tools.evaluate_end_face_batch import BatchInputError, load_validated_manifest, read_results_jsonl, write_strict_json


COMPARISON_SCHEMA_VERSION = "a-end-face-short-line-comparison/1"
SUMMARY_SCHEMA_VERSION = "a-end-face-short-line-batch-summary/1"
SUPPORTED_BASELINES = {"a-end-face-result/2", "a-end-face-result/3"}
PRIORITY_FEATURES = ("19", "30", "46", "M78", "80", "86")
DEFAULT_CANDIDATE_CONFIG = PROJECT_ROOT / "config/end_face_short_line_candidate.v1.json"


class ComparisonInputError(ValueError):
    pass


def preflight_comparison_inputs(
    manifest_path: Path,
    data_root: Path,
    results_jsonl: Path,
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    """Validate every image/hash and the complete task mapping before diagnosis."""
    try:
        manifest = load_validated_manifest(manifest_path.resolve(), data_root.resolve())
        results = read_results_jsonl(results_jsonl.resolve())
    except (BatchInputError, OSError, ValueError) as exc:
        raise ComparisonInputError(str(exc)) from exc
    result_by_task: dict[str, dict[str, Any]] = {}
    for line_number, payload in enumerate(results, start=1):
        schema_version = payload.get("schemaVersion")
        if schema_version not in SUPPORTED_BASELINES:
            raise ComparisonInputError(
                f"baseline line {line_number} has unsupported schemaVersion: {schema_version!r}"
            )
        task_id = payload.get("taskId")
        if not isinstance(task_id, str) or not task_id:
            raise ComparisonInputError(f"baseline line {line_number} has no taskId")
        if task_id in result_by_task:
            raise ComparisonInputError(f"duplicate baseline taskId: {task_id}")
        result_by_task[task_id] = payload
    manifest_ids = [str(item.get("imageId") or "") for item in manifest["images"]]
    if len(set(manifest_ids)) != len(manifest_ids):
        raise ComparisonInputError("Manifest imageId values must be unique")
    missing = sorted(set(manifest_ids) - set(result_by_task))
    extra = sorted(set(result_by_task) - set(manifest_ids))
    if missing or extra:
        raise ComparisonInputError(f"Manifest/baseline task set mismatch: missing={missing}, extra={extra}")
    return manifest, result_by_task


def _core_feature_status(feature_quality: Mapping[str, Any]) -> dict[str, Any]:
    status: dict[str, Any] = {}
    for raw_label, value in feature_quality.items():
        if not isinstance(value, Mapping):
            continue
        canonical = str(value.get("canonicalFeature") or canonical_feature_label(str(raw_label)))
        if canonical not in PRIORITY_FEATURES:
            continue
        if canonical in status:
            raise ComparisonInputError(f"duplicate canonical core feature in one baseline result: {canonical}")
        status[canonical] = {
            "coreValid": value.get("coreValid") is True,
            "source": value.get("source"),
            "reason": value.get("reason"),
            "rawFeature": str(raw_label),
        }
    return status


def _metric_summary(values: list[float]) -> dict[str, Any]:
    return {
        "count": len(values),
        "mean": sum(values) / len(values) if values else None,
        "min": min(values) if values else None,
        "max": max(values) if values else None,
    }


def summarize_comparisons(
    records: Iterable[Mapping[str, Any]],
    dataset: Mapping[str, Any],
) -> dict[str, Any]:
    materialized = list(records)
    compared = 0
    baseline_failed = 0
    candidate_stats: dict[str, dict[str, Any]] = {}
    priority_stats: dict[str, dict[str, Any]] = {}

    for record in materialized:
        if record.get("technicalStatus") == "compared":
            compared += 1
        else:
            baseline_failed += 1
        features = record.get("features") if isinstance(record.get("features"), Mapping) else {}
        for raw_label, comparison in features.items():
            if not isinstance(comparison, Mapping):
                continue
            canonical = str(comparison.get("canonicalFeature") or canonical_feature_label(str(raw_label)))
            if canonical not in {"19", "30"}:
                continue
            stats = candidate_stats.setdefault(canonical, {
                "total": 0,
                "coreValid": 0,
                "candidateValid": 0,
                "transitions": Counter({name: 0 for name in ("both_valid", "recovered", "regressed", "both_invalid")}),
                "failedChecks": Counter(),
                "failureCategories": Counter(),
                "midpointDistancePx": [],
                "angleDeltaDeg": [],
                "endpointRmsPx": [],
            })
            stats["total"] += 1
            core_result = comparison.get("core") if isinstance(comparison.get("core"), Mapping) else {}
            candidate = comparison.get("candidate") if isinstance(comparison.get("candidate"), Mapping) else {}
            stats["coreValid"] += int(core_result.get("coreValid") is True)
            stats["candidateValid"] += int(candidate.get("candidateValid") is True)
            transition = str(comparison.get("transition") or "both_invalid")
            if transition not in stats["transitions"]:
                raise ComparisonInputError(f"unsupported short-line transition: {transition}")
            stats["transitions"][transition] += 1
            diagnostic = comparison.get("diagnostic") if isinstance(comparison.get("diagnostic"), Mapping) else {}
            for failed_check in diagnostic.get("failedChecks", []):
                stats["failedChecks"][str(failed_check)] += 1
            for category in diagnostic.get("failureCategories", []):
                stats["failureCategories"][str(category)] += 1
            delta = candidate.get("deltaFromCore") if isinstance(candidate.get("deltaFromCore"), Mapping) else {}
            for source_key, destination_key in (
                ("midpointDistancePx", "midpointDistancePx"),
                ("angleDeg", "angleDeltaDeg"),
                ("endpointRmsPx", "endpointRmsPx"),
            ):
                value = delta.get(source_key)
                if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value)):
                    stats[destination_key].append(float(value))

        core_status = record.get("coreFeatureStatus") if isinstance(record.get("coreFeatureStatus"), Mapping) else {}
        for canonical in PRIORITY_FEATURES:
            value = core_status.get(canonical)
            if not isinstance(value, Mapping):
                continue
            stats = priority_stats.setdefault(canonical, {
                "total": 0,
                "valid": 0,
                "invalid": 0,
                "sources": Counter(),
                "reasons": Counter(),
            })
            stats["total"] += 1
            valid = value.get("coreValid") is True
            stats["valid"] += int(valid)
            stats["invalid"] += int(not valid)
            stats["sources"][str(value.get("source") or "unspecified")] += 1
            if not valid:
                stats["reasons"][str(value.get("reason") or "unspecified")] += 1

    serialized_candidates: dict[str, Any] = {}
    for canonical in sorted(candidate_stats):
        stats = candidate_stats[canonical]
        serialized_candidates[canonical] = {
            "total": stats["total"],
            "coreValid": stats["coreValid"],
            "candidateValid": stats["candidateValid"],
            "transitions": dict(sorted(stats["transitions"].items())),
            "failedChecks": dict(sorted(stats["failedChecks"].items())),
            "failureCategories": dict(sorted(stats["failureCategories"].items())),
            "deltaMetrics": {
                "midpointDistancePx": _metric_summary(stats["midpointDistancePx"]),
                "angleDeltaDeg": _metric_summary(stats["angleDeltaDeg"]),
                "endpointRmsPx": _metric_summary(stats["endpointRmsPx"]),
            },
        }
    serialized_priority = {
        canonical: {
            "total": stats["total"],
            "valid": stats["valid"],
            "invalid": stats["invalid"],
            "sources": dict(sorted(stats["sources"].items())),
            "reasons": dict(sorted(stats["reasons"].items())),
        }
        for canonical, stats in sorted(priority_stats.items())
    }
    total_regressed = sum(
        value["transitions"].get("regressed", 0) for value in serialized_candidates.values()
    )
    total_recovered = sum(
        value["transitions"].get("recovered", 0) for value in serialized_candidates.values()
    )
    return {
        "schemaVersion": SUMMARY_SCHEMA_VERSION,
        "dataset": {
            "datasetId": dataset.get("datasetId"),
            "datasetFingerprint": dataset.get("datasetFingerprint"),
            "manifestSha256": dataset.get("manifestSha256"),
            "comparisonJsonlSha256": dataset.get("comparisonJsonlSha256"),
            "coreSourceSha256": dataset.get("coreSourceSha256"),
            "candidateConfigSha256": dataset.get("candidateConfigSha256"),
        },
        "imageCount": len(materialized),
        "comparisonStatus": {
            "compared": compared,
            "baselineFailed": baseline_failed,
        },
        "candidateFeatures": serialized_candidates,
        "priorityCoreFeatures": serialized_priority,
        "acceptance": {
            "noRegression": total_regressed == 0,
            "hasEvidenceBackedRecovery": total_recovered > 0,
            "regressedCount": total_regressed,
            "recoveredCount": total_recovered,
        },
    }


def read_comparison_jsonl(path: Path) -> list[dict[str, Any]]:
    try:
        return read_results_jsonl(path)
    except BatchInputError as exc:
        raise ComparisonInputError(str(exc)) from exc


def _baseline_failed_record(
    task_id: str,
    item: Mapping[str, Any],
    baseline: Mapping[str, Any],
    provenance: Mapping[str, Any],
) -> dict[str, Any]:
    baseline_error = baseline.get("error") if isinstance(baseline.get("error"), Mapping) else {}
    return {
        "schemaVersion": COMPARISON_SCHEMA_VERSION,
        "taskId": task_id,
        "technicalStatus": "baseline_failed",
        "input": {
            "relativePath": item.get("relativePath"),
            "sha256": item.get("sha256"),
            "width": item.get("width"),
            "height": item.get("height"),
        },
        "provenance": dict(provenance),
        "baselineSchemaVersion": baseline.get("schemaVersion"),
        "coreFeatureStatus": {},
        "features": None,
        "error": {
            "code": "BASELINE_FAILED",
            "message": str(baseline_error.get("message") or "baseline technical execution failed"),
        },
    }


def compare_batch(args: argparse.Namespace) -> int:
    manifest_path = args.manifest.resolve()
    data_root = args.data_root.resolve()
    results_path = args.results_jsonl.resolve()
    manifest, result_by_task = preflight_comparison_inputs(manifest_path, data_root, results_path)
    annotation = args.annotation.resolve()
    if not annotation.is_file():
        raise ComparisonInputError(f"annotation does not exist: {annotation}")
    if sha256_file(Path(core.__file__).resolve()) != CORE_SOURCE_SHA256:
        raise ComparisonInputError("immutable desktop A-end-face core SHA-256 mismatch")
    reference_model = core.build_reference_model(annotation)
    candidate_path = args.candidate_config.resolve()
    evaluator = ShortLineCandidateEvaluator(
        reference_model,
        load_candidate_config(candidate_path),
        candidate_path,
    )
    provenance = {
        "annotationSha256": sha256_file(annotation),
        "referenceSha256": sha256_file(reference_model.reference_path),
        "coreSourceSha256": CORE_SOURCE_SHA256,
        "candidateId": evaluator.provenance["candidateId"],
        "candidateAlgorithmVersion": evaluator.provenance["algorithmVersion"],
        "candidateConfigSha256": evaluator.provenance["configSha256"],
    }
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    comparison_path = output_dir / "short-line-comparison.jsonl"
    records: list[dict[str, Any]] = []
    with comparison_path.open("w", encoding="utf-8") as handle:
        for item in manifest["images"]:
            task_id = str(item["imageId"])
            baseline = result_by_task[task_id]
            if baseline.get("technicalStatus") != "succeeded" or not isinstance(baseline.get("result"), Mapping):
                record = _baseline_failed_record(task_id, item, baseline, provenance)
            else:
                result = baseline["result"]
                feature_quality = result.get("featureQuality") if isinstance(result.get("featureQuality"), Mapping) else {}
                measurements = result.get("measurements") if isinstance(result.get("measurements"), Mapping) else {}
                image = data_root / safe_relative_path(str(item["relativePath"]))
                comparisons = evaluator.evaluate_image(image, measurements, feature_quality)
                record = {
                    "schemaVersion": COMPARISON_SCHEMA_VERSION,
                    "taskId": task_id,
                    "technicalStatus": "compared",
                    "input": {
                        "relativePath": item.get("relativePath"),
                        "sha256": item.get("sha256"),
                        "width": item.get("width"),
                        "height": item.get("height"),
                    },
                    "provenance": dict(provenance),
                    "baselineSchemaVersion": baseline.get("schemaVersion"),
                    "coreFeatureStatus": _core_feature_status(feature_quality),
                    "features": comparisons,
                    "error": None,
                }
            records.append(record)
            handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n")
    dataset = {
        "datasetId": manifest.get("datasetId"),
        "datasetFingerprint": manifest.get("datasetFingerprint"),
        "manifestSha256": sha256_file(manifest_path),
        "comparisonJsonlSha256": sha256_file(comparison_path),
        "coreSourceSha256": CORE_SOURCE_SHA256,
        "candidateConfigSha256": evaluator.provenance["configSha256"],
    }
    summary = summarize_comparisons(records, dataset)
    summary_path = output_dir / "short-line-summary.json"
    write_strict_json(summary_path, summary)
    print(
        f"images={summary['imageCount']} compared={summary['comparisonStatus']['compared']} "
        f"recovered={summary['acceptance']['recoveredCount']} regressed={summary['acceptance']['regressedCount']}"
    )
    print(f"comparison -> {comparison_path}")
    print(f"summary -> {summary_path}")
    return 1 if summary["comparisonStatus"]["baselineFailed"] else 0


def summarize_jsonl(args: argparse.Namespace) -> int:
    comparison_path = args.comparison_jsonl.resolve()
    records = read_comparison_jsonl(comparison_path)
    candidate_sha = None
    core_sha = None
    if records and isinstance(records[0].get("provenance"), Mapping):
        candidate_sha = records[0]["provenance"].get("candidateConfigSha256")
        core_sha = records[0]["provenance"].get("coreSourceSha256")
    dataset = {
        "datasetId": args.dataset_id,
        "datasetFingerprint": args.dataset_fingerprint,
        "manifestSha256": args.manifest_sha256,
        "comparisonJsonlSha256": sha256_file(comparison_path),
        "coreSourceSha256": core_sha,
        "candidateConfigSha256": candidate_sha,
    }
    write_strict_json(args.output.resolve(), summarize_comparisons(records, dataset))
    print(f"summary -> {args.output.resolve()}")
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    compare_parser = subparsers.add_parser("compare", help="Compare v2/v3 baselines with the candidate on external images.")
    compare_parser.add_argument("--manifest", required=True, type=Path)
    compare_parser.add_argument("--data-root", required=True, type=Path)
    compare_parser.add_argument("--annotation", required=True, type=Path)
    compare_parser.add_argument("--results-jsonl", required=True, type=Path)
    compare_parser.add_argument("--candidate-config", type=Path, default=DEFAULT_CANDIDATE_CONFIG)
    compare_parser.add_argument("--output-dir", required=True, type=Path)
    compare_parser.set_defaults(handler=compare_batch)

    summary_parser = subparsers.add_parser("summarize", help="Rebuild comparison statistics without image access.")
    summary_parser.add_argument("--comparison-jsonl", required=True, type=Path)
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
    except (ComparisonInputError, OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
