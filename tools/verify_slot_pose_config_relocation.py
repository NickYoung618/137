#!/usr/bin/env python3
"""Replay frozen results with a relocated config and verify behavioral equivalence."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from collections import Counter
from collections.abc import Sequence
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from algorithms.slot_pose.contract import (
    build_result,
    effective_config_sha256,
    load_config,
    sha256_file,
)
from algorithms.slot_pose.legacy_adapter import (
    LegacyAdapterError,
    LegacyAEndFaceAdapter,
)
from algorithms.slot_pose.main import run_loaded

IGNORED_KEYS = {"createdAtUtc", "elapsedMs", "timingMs"}


def _normalized(value: Any, path: tuple[str, ...] = ()) -> Any:
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            if key in IGNORED_KEYS or path == ("algorithm",) and key == "configSha256":
                continue
            result[key] = _normalized(item, path + (key,))
        return result
    if isinstance(value, list):
        return [_normalized(item, path + (str(index),)) for index, item in enumerate(value)]
    return value


def verify_relocation(
    baseline_paths: list[Path], portable_config_path: Path, output_dir: Path
) -> dict[str, Any]:
    output_dir = output_dir.resolve()
    try:
        output_dir.relative_to(ROOT.resolve())
    except ValueError:
        pass
    else:
        raise ValueError("output directory must be outside the Git working tree")
    if output_dir.exists() or output_dir.is_symlink():
        raise FileExistsError(f"output directory already exists: {output_dir}")
    output_dir.mkdir(parents=True)
    try:
        config_path = portable_config_path.resolve()
        config = load_config(config_path)
        effective = effective_config_sha256(config)
        adapter = LegacyAEndFaceAdapter(config)
        adapter.verify_assets()
        total = 0
        matched = 0
        mismatches: list[dict[str, Any]] = []
        valid = 0
        errors: Counter[str] = Counter()
        output_hashes: dict[str, str] = {}
        started = time.perf_counter()
        seen_images: set[str] = set()
        for baseline_path in baseline_paths:
            baselines = [
                json.loads(line) for line in baseline_path.read_text(encoding="utf-8").splitlines() if line
            ]
            current: list[dict[str, Any]] = []
            for baseline in baselines:
                total += 1
                image = baseline["image"]
                image_sha = str(image["sha256"])
                if image_sha in seen_images:
                    raise ValueError(f"duplicate baseline image SHA-256: {image_sha}")
                seen_images.add(image_sha)
                baseline_effective = baseline.get("algorithm", {}).get("effectiveConfigSha256")
                if baseline_effective != effective:
                    raise ValueError("baseline and portable effective configuration SHA-256 differ")
                image_path = Path(image["path"])
                if not image_path.is_file() or sha256_file(image_path) != image_sha:
                    raise ValueError(f"baseline image is missing or changed: {image_path}")
                try:
                    result = run_loaded(
                        image_path, config_path, config, adapter, str(baseline["taskId"])
                    )
                except LegacyAdapterError as exc:
                    result = build_result(
                        image_path,
                        config_path,
                        config,
                        str(baseline["taskId"]),
                        exc.diagnostics,
                        error_code=exc.code,
                        error_message=str(exc),
                        error_stage=exc.stage,
                    )
                current.append(result)
                if result["result"]["valid"]:
                    valid += 1
                else:
                    errors[result["error"]["code"]] += 1
                if _normalized(baseline) == _normalized(result):
                    matched += 1
                elif len(mismatches) < 20:
                    mismatches.append({
                        "taskId": baseline["taskId"],
                        "imageSha256": image_sha,
                        "baselineValid": baseline["result"]["valid"],
                        "portableValid": result["result"]["valid"],
                        "baselineError": None if baseline["error"] is None else baseline["error"]["code"],
                        "portableError": None if result["error"] is None else result["error"]["code"],
                    })
            output_path = output_dir / baseline_path.name
            output_path.write_text(
                "\n".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) for row in current)
                + ("\n" if current else ""),
                encoding="utf-8",
            )
            output_hashes[baseline_path.name] = sha256_file(output_path)
        adapter.verify_assets()
        report = {
            "schemaVersion": "slot-pose-config-relocation-equivalence/1",
            "portableConfigSha256": sha256_file(config_path),
            "effectiveConfigSha256": effective,
            "comparisonPolicy": {
                "ignoredRootFields": ["createdAtUtc"],
                "ignoredAlgorithmFields": ["configSha256"],
                "ignoredRecursiveFields": ["elapsedMs", "timingMs"],
                "allOtherFields": "exact",
            },
            "baselineFiles": [
                {"path": str(path.resolve()), "sha256": sha256_file(path.resolve())}
                for path in baseline_paths
            ],
            "total": total,
            "matched": matched,
            "mismatchCount": total - matched,
            "mismatchExamples": mismatches,
            "valid": valid,
            "invalid": total - valid,
            "errorCounts": dict(sorted(errors.items())),
            "outputSha256": output_hashes,
            "elapsedSeconds": time.perf_counter() - started,
            "equivalent": matched == total,
            "accuracyEvaluated": False,
            "plcAuthorized": False,
        }
        (output_dir / "equivalence-report.json").write_text(
            json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return report
    except Exception:
        shutil.rmtree(output_dir, ignore_errors=True)
        raise


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", action="append", required=True, type=Path)
    parser.add_argument("--portable-config", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        report = verify_relocation(args.baseline, args.portable_config, args.output_dir)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if report["equivalent"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
