#!/usr/bin/env python3
"""Create an external 020 experimental config without altering its base."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Any, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from algorithms.slot_pose.contract import load_config
from algorithms.slot_pose.fixture_shadow import merged_fixture_shadow_config
from algorithms.slot_pose.groove_refinement import merged_groove_refinement_config
from algorithms.slot_pose.sidewall_consistency import merged_sidewall_consistency_config


def prepare(base: dict[str, Any]) -> dict[str, Any]:
    copied = json.loads(json.dumps(base, allow_nan=False))
    detector = copied.get("detector")
    if not isinstance(detector, dict) or detector.get("diagnostic_mode") != "single_real_groove":
        raise ValueError("020 fixture shadow config requires diagnostic_mode=single_real_groove")
    detector["fixture_shadow_model"] = merged_fixture_shadow_config({
        **(detector.get("fixture_shadow_model") or {}),
        "enabled": True,
        # No human reference profiles exist yet. Do not let template subtraction
        # change candidates until external, reviewed profiles are supplied.
        "enable_overlap_decomposition": False,
    })
    detector["sidewall_source_consistency"] = merged_sidewall_consistency_config({
        **(detector.get("sidewall_source_consistency") or {}),
        "enabled": True,
    })
    detector["groove_refinement"] = merged_groove_refinement_config({
        **(detector.get("groove_refinement") or {}),
        "threshold_version": "groove-sidewall-subpixel-v2",
    })
    copied["config_id"] = f"{copied.get('config_id', 'slot-pose')}-020-experimental"
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
    print(f"Wrote default-off-derived 020 experimental config: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
