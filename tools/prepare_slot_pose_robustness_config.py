#!/usr/bin/env python3
"""Create an external, explicitly experimental 019 config without touching its base."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from algorithms.slot_pose.angular_profile import merged_dark_candidate_robustness_config
from algorithms.slot_pose.physical_outer_circle import merged_physical_outer_circle_config
from algorithms.slot_pose.contract import load_config


def prepare(base: dict, *, enable_circle: bool = True, enable_dark: bool = True) -> dict:
    copied = json.loads(json.dumps(base, allow_nan=False))
    detector = copied.get("detector")
    if not isinstance(detector, dict) or detector.get("diagnostic_mode") != "single_real_groove":
        raise ValueError("019 robustness config requires detector.diagnostic_mode=single_real_groove")
    if enable_dark:
        detector["dark_candidate_robustness"] = merged_dark_candidate_robustness_config({
            **(detector.get("dark_candidate_robustness") or {}), "enabled": True,
        })
    physical = merged_physical_outer_circle_config(detector.get("physical_outer_circle"))
    if enable_circle:
        physical["sector_robustness"] = {
            **physical["sector_robustness"], "enabled": True,
        }
        physical = merged_physical_outer_circle_config(physical)
    detector["physical_outer_circle"] = physical
    copied["config_id"] = f"{copied.get('config_id', 'slot-pose')}-019-experimental"
    return copied


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.base.resolve() == args.output.resolve():
        raise ValueError("experimental output must not overwrite the base config")
    base = json.loads(args.base.read_text(encoding="utf-8"))
    configured = prepare(base)
    with tempfile.TemporaryDirectory() as temporary:
        validation_path = Path(temporary) / "experimental-config.json"
        validation_path.write_text(
            json.dumps(configured, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
            encoding="utf-8",
        )
        load_config(validation_path)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(configured, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote experimental config: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
