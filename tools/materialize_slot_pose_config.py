#!/usr/bin/env python3
"""Materialize runtime defaults and emit a path-independent effective config identity."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from algorithms.slot_pose.contract import (
    config_sha256, effective_config_identity, effective_config_sha256, load_config,
)
from tools.dataset_common import write_json


def materialize(config_path: Path) -> dict:
    loaded = load_config(config_path)
    return {
        "schemaVersion": "slot-pose-effective-config-materialization/1",
        "sourceConfigSha256": config_sha256(config_path),
        "effectiveConfigSha256": effective_config_sha256(loaded),
        "effectiveConfig": effective_config_identity(loaded),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        payload = materialize(args.config)
        write_json(args.output, payload)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(f"Wrote {args.output}: effective={payload['effectiveConfigSha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
