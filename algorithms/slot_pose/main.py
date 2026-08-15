#!/usr/bin/env python3
"""Estimate one A-face slot pose by adapting the read-only historical core."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from algorithms.slot_pose.contract import build_result, load_config
from algorithms.slot_pose.legacy_adapter import LegacyAEndFaceAdapter, LegacyAdapterError


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True, type=Path)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--task-id")
    parser.add_argument("--out", default="-", help="Output JSON path or '-' for stdout.")
    parser.add_argument("--strict", action="store_true", help="Return 1 when pose is invalid.")
    return parser.parse_args()


def run(image_path: Path, config_path: Path, task_id: str | None = None) -> dict:
    if not image_path.is_file():
        raise ValueError(f"input image does not exist: {image_path}")
    config = load_config(config_path)
    try:
        adapter = LegacyAEndFaceAdapter(config)
    except LegacyAdapterError as exc:
        return build_result(
            image_path, config_path, config, task_id, exc.diagnostics,
            error_code=exc.code, error_message=str(exc), error_stage=exc.stage,
        )
    return run_loaded(image_path, config_path, config, adapter, task_id)


def run_loaded(
    image_path: Path,
    config_path: Path,
    config: dict,
    adapter: LegacyAEndFaceAdapter,
    task_id: str | None = None,
) -> dict:
    """Run one image with a pre-verified adapter/reference model."""
    diagnostics: dict = {}
    try:
        estimate = adapter.estimate(image_path.resolve())
        diagnostics = estimate["diagnostics"]
        angle = adapter.mechanical_angle(estimate["candidate_image_deg"])
        return build_result(
            image_path, config_path, config, task_id, diagnostics,
            angle_deg=angle, confidence=float(estimate["confidence"]),
        )
    except LegacyAdapterError as exc:
        try:
            adapter.verify_assets()
        except LegacyAdapterError as asset_exc:
            exc = asset_exc
        diagnostics = exc.diagnostics or diagnostics
        return build_result(
            image_path, config_path, config, task_id, diagnostics,
            error_code=exc.code, error_message=str(exc), error_stage=exc.stage,
        )
    except Exception as exc:
        return build_result(
            image_path, config_path, config, task_id, diagnostics,
            error_code="INTERNAL_ERROR", error_message=str(exc), error_stage="internal",
        )


def main() -> int:
    args = parse_args()
    try:
        payload = run(args.image, args.config, args.task_id)
        content = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
        if args.out == "-":
            print(content, end="")
        else:
            output = Path(args.out)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(content, encoding="utf-8")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 1 if args.strict and not payload["result"]["valid"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
