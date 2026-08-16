#!/usr/bin/env python3
"""Freeze one complete A2 physical sample using a result-independent deterministic rule."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.dataset_common import sha256_file, write_json
from tools.evaluation_governance import build_development_manifest, freeze_transitional_blind


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--eligibility", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    manifest_path = args.output_dir / "transitional-blind-manifest.json"
    development_path = args.output_dir / "development-manifest.json"
    lock_path = args.output_dir / "transitional-blind-lock.json"
    sums_path = args.output_dir / "SHA256SUMS"
    try:
        if any(path.exists() for path in (manifest_path, development_path, lock_path, sums_path)):
            raise ValueError("transitional blind lock already exists; refusing to overwrite or reselect")
        source_manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        eligibility = json.loads(args.eligibility.read_text(encoding="utf-8"))
        blind_manifest, lock = freeze_transitional_blind(source_manifest, eligibility)
        development_manifest = build_development_manifest(source_manifest, lock)
        args.output_dir.mkdir(parents=True, exist_ok=True)
        write_json(manifest_path, blind_manifest)
        write_json(development_path, development_manifest)
        write_json(lock_path, lock)
        sums_path.write_text(
            f"{sha256_file(manifest_path)}  {manifest_path.name}\n"
            f"{sha256_file(development_path)}  {development_path.name}\n"
            f"{sha256_file(lock_path)}  {lock_path.name}\n",
            encoding="ascii",
        )
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}")
        return 2
    print(
        f"Frozen sample={lock['selectedSampleId']} conditions={','.join(lock['selectedConditionIds'])} "
        f"images={lock['selectedImageCount']} status={lock['blindStatus']} output={args.output_dir}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
