#!/usr/bin/env python3
"""Run truth-free current-capture detection over external grouped image sets."""
from __future__ import annotations

import argparse
import json
import math
import os
import statistics
import sys
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any, Iterable

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from algorithms.hole_2.current_capture import run_current_capture, sha256_file


BATCH_SCHEMA_VERSION = "hole2-current-capture-batch-summary/2"
DEFAULT_EXTENSIONS = {".bmp", ".png", ".jpg", ".jpeg", ".tif", ".tiff"}


def _new_stats() -> dict[str, Any]:
    return {
        "total": 0,
        "executionSuccess": 0,
        "executionErrors": Counter(),
        "registrationValid": 0,
        "technicalComplete": 0,
        "featureValid": Counter(),
        "orientationCounts": Counter(),
        "qualityStates": Counter(),
        "registrationFailureReasons": Counter(),
        "candidateRejectionReasons": Counter(),
        "featureFailureReasons": Counter(),
        "timings": [],
    }


def _percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = fraction * (len(ordered) - 1)
    low = int(math.floor(position))
    high = int(math.ceil(position))
    if low == high:
        return float(ordered[low])
    weight = position - low
    return float(ordered[low] * (1.0 - weight) + ordered[high] * weight)


def _serialize_stats(stats: dict[str, Any]) -> dict[str, Any]:
    timings = stats["timings"]
    return {
        "total": stats["total"],
        "executionSuccess": stats["executionSuccess"],
        "executionErrors": dict(sorted(stats["executionErrors"].items())),
        "registrationValid": stats["registrationValid"],
        "technicalComplete": stats["technicalComplete"],
        "featureValid": {
            "7": stats["featureValid"]["7"],
            "Phi12.2": stats["featureValid"]["Phi12.2"],
        },
        "orientationCounts": dict(sorted(stats["orientationCounts"].items())),
        "qualityStates": dict(sorted(stats["qualityStates"].items())),
        "registrationFailureReasons": dict(sorted(stats["registrationFailureReasons"].items())),
        "candidateRejectionReasons": dict(sorted(stats["candidateRejectionReasons"].items())),
        "featureFailureReasons": dict(sorted(stats["featureFailureReasons"].items())),
        "timingMs": {
            "count": len(timings),
            "mean": None if not timings else float(statistics.fmean(timings)),
            "p50": _percentile(timings, 0.50),
            "p95": _percentile(timings, 0.95),
            "max": None if not timings else float(max(timings)),
        },
    }


class BatchAccumulator:
    """Streaming quality aggregation that never converts invalid results to success."""

    def __init__(self) -> None:
        self._overall = _new_stats()
        self._groups: dict[str, dict[str, Any]] = {}

    def add(self, record: dict[str, Any]) -> None:
        group = str(record["group"])
        group_stats = self._groups.setdefault(group, _new_stats())
        for stats in (self._overall, group_stats):
            self._add_to(stats, record)

    @staticmethod
    def _add_to(stats: dict[str, Any], record: dict[str, Any]) -> None:
        stats["total"] += 1
        error = record.get("executionError")
        if error:
            stats["executionErrors"][str(error).split(":", 1)[0]] += 1
            return
        stats["executionSuccess"] += 1
        result = record["result"]
        registration = result["registration"]
        status = result["qualityStatus"]
        stats["qualityStates"][status["state"]] += 1
        if status["technicalValid"]:
            stats["technicalComplete"] += 1
        if registration["registrationValid"]:
            stats["registrationValid"] += 1
        elif registration.get("failureReason"):
            stats["registrationFailureReasons"][registration["failureReason"]] += 1
        selected = registration.get("selected")
        if selected is not None and selected.get("orientationDeg") is not None:
            stats["orientationCounts"][str(selected["orientationDeg"])] += 1
        for candidate in registration.get("candidates", []):
            if candidate.get("valid"):
                continue
            for reason in candidate.get("failureReasons") or []:
                stats["candidateRejectionReasons"][reason] += 1
        for name in ("7", "Phi12.2"):
            feature = result["features"][name]
            if feature["measurementValid"]:
                stats["featureValid"][name] += 1
            elif feature.get("failureReason"):
                stats["featureFailureReasons"][f"{name}:{feature['failureReason']}"] += 1
        total_ms = result.get("timingMs", {}).get("total")
        if isinstance(total_ms, (int, float)) and math.isfinite(float(total_ms)):
            stats["timings"].append(float(total_ms))

    def as_dict(self) -> dict[str, Any]:
        return {
            "schemaVersion": BATCH_SCHEMA_VERSION,
            "overall": _serialize_stats(self._overall),
            "groups": {
                name: _serialize_stats(stats)
                for name, stats in sorted(self._groups.items())
            },
            "evidenceScope": (
                "external_batch_technical_quality_only_"
                "not_repeatability_mm_accuracy_or_production_ok_ng"
            ),
        }


def validate_batch_summary_contract(summary: dict[str, Any]) -> None:
    required = {"schemaVersion", "overall", "groups", "evidenceScope", "runtimeInputs"}
    missing = sorted(required - summary.keys())
    if missing:
        raise ValueError("batch summary missing required fields: " + ",".join(missing))
    if summary["schemaVersion"] != BATCH_SCHEMA_VERSION:
        raise ValueError("unsupported batch summary schemaVersion")
    if summary["evidenceScope"] != (
        "external_batch_technical_quality_only_"
        "not_repeatability_mm_accuracy_or_production_ok_ng"
    ):
        raise ValueError("invalid batch evidenceScope")
    expected_runtime_inputs = {
        "authoritativeReferenceAnnotation", "authoritativeReferenceImage",
        "configuration", "groups",
    }
    if set(summary["runtimeInputs"]) != expected_runtime_inputs:
        raise ValueError("batch runtimeInputs must contain only the authoritative reference")
    for name, stats in {"overall": summary["overall"], **summary["groups"]}.items():
        required_stats = {
            "total", "executionSuccess", "executionErrors", "registrationValid",
            "technicalComplete", "featureValid", "orientationCounts", "qualityStates",
            "registrationFailureReasons", "candidateRejectionReasons",
            "featureFailureReasons", "timingMs",
        }
        if not isinstance(stats, dict) or not required_stats <= stats.keys():
            raise ValueError(f"batch stats are incomplete: {name}")
        total = int(stats["total"])
        for key in ("executionSuccess", "registrationValid", "technicalComplete"):
            value = int(stats[key])
            if value < 0 or value > total:
                raise ValueError(f"batch stats count out of range: {name}.{key}")
        if set(stats["featureValid"]) != {"7", "Phi12.2"}:
            raise ValueError(f"batch featureValid keys are invalid: {name}")


def _parse_group(value: str) -> tuple[str, Path]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("group must use NAME=/external/directory")
    name, raw_path = value.split("=", 1)
    if not name.strip() or not raw_path.strip():
        raise argparse.ArgumentTypeError("group name and directory must be non-empty")
    return name.strip(), Path(raw_path).expanduser().resolve()


def _discover_images(
    groups: list[tuple[str, Path]],
    extensions: set[str],
    max_images_per_group: int | None,
) -> list[tuple[str, Path]]:
    items: list[tuple[str, Path]] = []
    for name, directory in groups:
        if not directory.is_dir():
            raise ValueError(f"group directory does not exist: {directory}")
        images = sorted(
            path for path in directory.rglob("*")
            if path.is_file() and path.suffix.lower() in extensions
        )
        if max_images_per_group is not None:
            images = images[:max_images_per_group]
        items.extend((name, path) for path in images)
    if not items:
        raise ValueError("no supported images found in batch groups")
    return items


def _execute(payload: tuple[str, str, str, str, str]) -> dict[str, Any]:
    group, image, reference_label, reference_image, config = payload
    try:
        result = run_current_capture(
            Path(reference_label), Path(reference_image), Path(image), Path(config)
        )
        return {
            "group": group,
            "imagePath": image,
            "executionError": None,
            "result": result,
        }
    except Exception as exc:  # Batch must retain every failure as evidence.
        return {
            "group": group,
            "imagePath": image,
            "executionError": f"{type(exc).__name__}:{exc}",
            "result": None,
        }


def _iter_records(
    payloads: list[tuple[str, str, str, str, str]], workers: int
) -> Iterable[dict[str, Any]]:
    if workers == 1:
        return map(_execute, payloads)
    executor = ProcessPoolExecutor(max_workers=workers)
    records = executor.map(_execute, payloads)

    def close_when_done() -> Iterable[dict[str, Any]]:
        try:
            yield from records
        finally:
            executor.shutdown(wait=True, cancel_futures=True)

    return close_when_done()


def _require_external_output(path: Path) -> Path:
    resolved = path.expanduser().resolve()
    try:
        resolved.relative_to(PROJECT_ROOT.resolve())
    except ValueError:
        return resolved
    raise ValueError("batch output directory must remain outside the Git worktree")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference-annotation", required=True,
                        help="Frozen authoritative manual 7/Phi12.2 annotation.")
    parser.add_argument("--reference-image", required=True,
                        help="New image paired with the authoritative annotation.")
    parser.add_argument("--config", required=True, help="Versioned registration config.")
    parser.add_argument(
        "--group", action="append", required=True, type=_parse_group,
        help="Repeatable external group in NAME=/directory form; no target annotation is accepted.",
    )
    parser.add_argument("--output-dir", required=True, help="External output directory.")
    parser.add_argument("--workers", type=int, default=max(1, min(4, os.cpu_count() or 1)))
    parser.add_argument("--max-images-per-group", type=int)
    args = parser.parse_args()
    if args.workers < 1:
        parser.error("--workers must be positive")
    if args.max_images_per_group is not None and args.max_images_per_group < 1:
        parser.error("--max-images-per-group must be positive")

    output_dir = _require_external_output(Path(args.output_dir))
    items = _discover_images(args.group, DEFAULT_EXTENSIONS, args.max_images_per_group)
    reference_label = str(Path(args.reference_annotation).expanduser().resolve())
    reference_image = str(Path(args.reference_image).expanduser().resolve())
    config = str(Path(args.config).expanduser().resolve())
    payloads = [(
        group, str(image), reference_label, reference_image, config,
    ) for group, image in items]
    output_dir.mkdir(parents=True, exist_ok=True)
    results_path = output_dir / "current-capture-results.jsonl"
    summary_path = output_dir / "quality-summary.json"
    accumulator = BatchAccumulator()
    with results_path.open("w", encoding="utf-8") as stream:
        for index, record in enumerate(_iter_records(payloads, args.workers), 1):
            accumulator.add(record)
            stream.write(json.dumps(record, ensure_ascii=False, allow_nan=False) + "\n")
            print(
                f"[{index}/{len(payloads)}] {record['group']} {record['imagePath']} "
                f"error={record['executionError']}"
            )
    summary = accumulator.as_dict()
    summary["runtimeInputs"] = {
        "authoritativeReferenceAnnotation": {"path": reference_label, "sha256": sha256_file(Path(reference_label))},
        "authoritativeReferenceImage": {"path": reference_image, "sha256": sha256_file(Path(reference_image))},
        "configuration": {"path": config, "sha256": sha256_file(Path(config))},
        "groups": [{"name": name, "path": str(path)} for name, path in args.group],
    }
    validate_batch_summary_contract(summary)
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    error_count = sum(summary["overall"]["executionErrors"].values())
    print(f"results -> {results_path}")
    print(f"summary -> {summary_path}")
    return 0 if error_count == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
