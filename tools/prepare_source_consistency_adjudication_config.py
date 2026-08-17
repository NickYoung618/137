#!/usr/bin/env python3
"""Materialize a Git-external, default-off-safe 022 experimental config."""

from __future__ import annotations

import argparse
import copy
import json
import math
import sys
from pathlib import Path
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from algorithms.slot_pose.sidewall_consistency import (
    DEFAULT_SIDEWALL_CONSISTENCY_CONFIG,
    merged_sidewall_consistency_config,
)
from algorithms.slot_pose.source_consistency_adjudication import (
    merged_source_consistency_adjudication_config,
)
from tools.dataset_common import sha256_file, write_json

def build_experimental_config(base: dict[str, Any]) -> dict[str, Any]:
    configured = copy.deepcopy(base)
    detector = configured.get("detector")
    if not isinstance(detector, dict) or detector.get("diagnostic_mode") != "single_real_groove":
        raise ValueError("022 adjudication requires detector.diagnostic_mode=single_real_groove")
    source = merged_sidewall_consistency_config(detector.get("sidewall_source_consistency"))
    if not source["enabled"]:
        raise ValueError("022 adjudication requires sidewall_source_consistency enabled")
    original_contrast = float(DEFAULT_SIDEWALL_CONSISTENCY_CONFIG["max_contrast_normalized_difference"])
    if not math.isclose(
        float(source["max_contrast_normalized_difference"]), original_contrast,
        rel_tol=0.0, abs_tol=0.0,
    ):
        raise ValueError("022 adjudication refuses a changed original contrast threshold")
    refinement = detector.get("groove_refinement")
    if not isinstance(refinement, dict) or refinement.get("threshold_version") != "groove-sidewall-subpixel-v2":
        raise ValueError("022 adjudication requires groove refinement v2")
    detector["sidewall_source_consistency"] = source
    detector["source_consistency_adjudication"] = merged_source_consistency_adjudication_config({
        **(detector.get("source_consistency_adjudication") or {}),
        "enabled": True,
    })
    return configured


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-config", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        output = args.output.resolve()
        if output.is_relative_to(REPOSITORY_ROOT):
            raise ValueError("experimental output must remain outside the Git worktree")
        base = json.loads(args.base_config.read_text(encoding="utf-8"))
        if not isinstance(base, dict):
            raise ValueError("base config must be an object")
        write_json(output, build_experimental_config(base))
        print(f"Wrote {output} sha256={sha256_file(output)}")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
