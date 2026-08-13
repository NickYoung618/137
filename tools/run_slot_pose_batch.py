#!/usr/bin/env python3
"""Run the slot-pose CLI contract over every image in a validated manifest."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from algorithms.slot_pose.main import run
from tools.dataset_common import safe_relative_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--data-root", required=True, type=Path)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        lines = []
        for item in manifest.get("images", []):
            relative = safe_relative_path(str(item["relativePath"]))
            payload = run(
                args.data_root.resolve() / relative,
                args.config.resolve(),
                f"{manifest.get('datasetId', 'dataset')}:{item['imageId']}",
            )
            lines.append(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}")
        return 2
    valid = sum(json.loads(line)["result"]["valid"] for line in lines)
    print(f"Wrote {args.output}: results={len(lines)}, valid={valid}, invalid={len(lines) - valid}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
