#!/usr/bin/env python3
"""Match two-capture slot candidates from existing single-frame result JSONL."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from algorithms.slot_pose.paired_capture import (
    build_paired_result,
    load_paired_config,
    validate_paired_manifest,
)


def load_results(path: Path) -> dict[str, dict[str, Any]]:
    by_sha: dict[str, dict[str, Any]] = {}
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        payload = json.loads(line)
        sha = (payload.get("image") or {}).get("sha256")
        if not isinstance(sha, str) or len(sha) != 64:
            raise ValueError(f"single result line {line_number} has no image SHA-256")
        if sha in by_sha:
            raise ValueError(f"duplicate single result image SHA-256: {sha}")
        by_sha[sha] = payload
    return by_sha


def run_paired(
    manifest: dict[str, Any], results_by_sha: dict[str, dict[str, Any]], config: dict[str, Any],
) -> list[dict[str, Any]]:
    validate_paired_manifest(manifest)
    outputs = []
    for pair in manifest["pairs"]:
        captures = {item["captureIndex"]: item for item in pair["captures"]}
        missing = [index for index in (1, 2) if captures[index]["imageSha256"] not in results_by_sha]
        if missing:
            raise ValueError(f"pair {pair['pairId']} missing single-frame results for captureIndex {missing}")
        outputs.append(build_paired_result(
            pair,
            results_by_sha[captures[1]["imageSha256"]],
            results_by_sha[captures[2]["imageSha256"]],
            config,
        ))
    return outputs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--single-results", required=True, type=Path)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        config = load_paired_config(args.config)
        outputs = run_paired(manifest, load_results(args.single_results), config)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            "\n".join(
                json.dumps(item, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
                for item in outputs
            )
            + ("\n" if outputs else ""), encoding="utf-8",
        )
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    counts: dict[str, int] = {}
    for item in outputs:
        counts[item["status"]] = counts.get(item["status"], 0) + 1
    print(f"Wrote {args.output}: pairs={len(outputs)} status={counts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
