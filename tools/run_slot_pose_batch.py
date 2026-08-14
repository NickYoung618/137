#!/usr/bin/env python3
"""Run the slot-pose CLI contract over every image in a validated manifest."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from algorithms.slot_pose.contract import (
    ALGORITHM_NAME,
    ALGORITHM_VERSION,
    SCHEMA_VERSION,
    config_sha256,
    load_config,
    validate_result,
)
from algorithms.slot_pose.main import run
from tools.dataset_common import safe_relative_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--data-root", required=True, type=Path)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def _manifest_input_failure(item: dict, image_path: Path, config_path: Path, config: dict, task_id: str, exc: Exception) -> dict:
    assets = config["legacy_asset"]
    pose = config["pose"]
    payload = {
        "schemaVersion": SCHEMA_VERSION,
        "taskId": task_id,
        "createdAtUtc": datetime.now(timezone.utc).isoformat(),
        "image": {
            "path": str(image_path),
            "sha256": item["sha256"],
            "bytes": int(item["bytes"]),
            "format": item["format"],
            "width": int(item["width"]),
            "height": int(item["height"]),
            "mode": item["mode"],
        },
        "algorithm": {
            "name": ALGORITHM_NAME, "version": ALGORITHM_VERSION,
            "configSha256": config_sha256(config_path), "configId": config["config_id"],
            "assets": {
                "sourceSha256": assets["source_sha256"],
                "annotationSha256": assets["annotation_sha256"],
                "referenceSha256": assets["reference_sha256"],
            },
        },
        "result": {
            "signedRelativeRotationDeg": None, "unit": "deg", "confidence": None, "valid": False,
            "referenceFrame": pose["reference_frame"], "targetFrame": pose["target_frame"],
            "positiveDirection": pose.get("positive_direction"),
        },
        "technicalStatus": "failed",
        "error": {"code": "INPUT_INVALID", "message": str(exc), "stage": "batch_input"},
        "diagnostics": {
            "poseConventionsConfirmed": bool(pose.get("conventions_confirmed", False)),
            "targetSemanticsConfirmed": bool(pose.get("target_semantics_confirmed", False)),
            "productionPlcMappingConfirmed": bool(pose.get("production_plc_mapping_confirmed", False)),
            "failClosed": True,
        },
    }
    validate_result(payload)
    return payload


def run_batch(manifest: dict, data_root: Path, config_path: Path) -> list[dict]:
    config_path = config_path.resolve()
    config = load_config(config_path)
    payloads: list[dict] = []
    for item in manifest.get("images", []):
        relative = safe_relative_path(str(item["relativePath"]))
        image_path = data_root.resolve() / relative
        task_id = f"{manifest.get('datasetId', 'dataset')}:{item['imageId']}"
        try:
            payload = run(image_path, config_path, task_id)
        except (OSError, ValueError, KeyError) as exc:
            payload = _manifest_input_failure(item, image_path, config_path, config, task_id, exc)
        payloads.append(payload)
    return payloads


def main() -> int:
    args = parse_args()
    try:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        payloads = run_batch(manifest, args.data_root, args.config)
        lines = [json.dumps(payload, ensure_ascii=False, separators=(",", ":")) for payload in payloads]
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
