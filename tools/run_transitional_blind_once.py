#!/usr/bin/env python3
"""Run a locked transitional blind Manifest once and write an immutable execution record."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Callable

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.dataset_common import sha256_file, write_json
from tools.evaluation_governance import stable_json_sha256, utc_now
from tools.run_slot_pose_batch import run_batch


def run_once(
    manifest: dict,
    lock: dict,
    data_root: Path,
    config_path: Path,
    output_dir: Path,
    *,
    runner: Callable[[dict, Path, Path], list[dict]] = run_batch,
) -> dict:
    claim_path = output_dir / "execution-claim.json"
    results_path = output_dir / "results-once.jsonl"
    record_path = output_dir / "execution-record.json"
    if claim_path.exists() or results_path.exists() or record_path.exists():
        raise ValueError("transitional blind execution already exists; refusing a second run")
    if lock.get("blindStatus") != "NON_STRICT_TRANSITIONAL" or lock.get("maxExecutionCount") != 1 or lock.get("executionCount") != 0:
        raise ValueError("invalid transitional blind execution policy")
    if stable_json_sha256(manifest) != lock.get("blindManifestSha256"):
        raise ValueError("blind Manifest identity does not match lock")
    actual_hashes = sorted(str(item.get("sourceImageSha256") or item.get("sha256")) for item in manifest.get("images", []))
    if actual_hashes != sorted(lock.get("selectedImageSha256s") or []):
        raise ValueError("blind Manifest image hashes do not match lock")
    if {str(item.get("sampleId")) for item in manifest.get("images", [])} != {str(lock.get("selectedSampleId"))}:
        raise ValueError("blind Manifest contains an unexpected physical sample")
    output_dir.mkdir(parents=True, exist_ok=True)
    claim = {
        "schemaVersion": "a2-transitional-blind-execution-claim/1",
        "selectedSampleId": lock["selectedSampleId"],
        "blindManifestSha256": lock["blindManifestSha256"],
        "lockPayloadSha256": lock["lockPayloadSha256"],
        "attemptNumber": 1,
        "claimedAtUtc": utc_now(),
        "strictUnseenClaimed": False,
    }
    try:
        with claim_path.open("x", encoding="utf-8") as handle:
            json.dump(claim, handle, ensure_ascii=False, indent=2, allow_nan=False)
            handle.write("\n")
    except FileExistsError as exc:
        raise ValueError("transitional blind execution already exists; refusing a second run") from exc
    payloads = runner(manifest, data_root, config_path)
    content = "\n".join(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) for payload in payloads)
    results_path.write_text(content + ("\n" if content else ""), encoding="utf-8")
    record = {
        "schemaVersion": "a2-transitional-blind-execution/1",
        "blindStatus": "NON_STRICT_TRANSITIONAL",
        "strictUnseenClaimed": False,
        "selectedSampleId": lock["selectedSampleId"],
        "blindManifestSha256": lock["blindManifestSha256"],
        "lockPayloadSha256": lock["lockPayloadSha256"],
        "configFileSha256": sha256_file(config_path),
        "resultsFileSha256": sha256_file(results_path),
        "resultCount": len(payloads),
        "validCount": sum((payload.get("result") or {}).get("valid") is True for payload in payloads),
        "executionCount": 1,
        "executedAtUtc": utc_now(),
        "absolutePathsStored": False,
    }
    write_json(record_path, record)
    return record


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--lock", required=True, type=Path)
    parser.add_argument("--data-root", required=True, type=Path)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        lock = json.loads(args.lock.read_text(encoding="utf-8"))
        record = run_once(manifest, lock, args.data_root, args.config, args.output_dir)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}")
        return 2
    print(
        f"Executed transitional blind once: sample={record['selectedSampleId']} "
        f"results={record['resultCount']} valid={record['validCount']} output={args.output_dir}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
