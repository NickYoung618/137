#!/usr/bin/env python3
"""Run annotation-independent main-housing registration diagnostics.

This tool intentionally has no LabelMe argument and emits no measurement or
short-line candidate status. It is safe to run while corrected 19/30 truth is
unavailable.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from collections.abc import Mapping
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from algorithms.end_face import CORE_SOURCE_SHA256, core
from algorithms.end_face.main_housing_registration import MainHousingRegistrar, REGISTRATION_VERSION
from algorithms.end_face.short_line_candidate import (
    CANDIDATE_SOURCE_V2,
    candidate_config_sha256,
    load_candidate_config,
)
from tools.dataset_common import inspect_image, safe_relative_path, sha256_file
from tools.evaluate_end_face_batch import BatchInputError, load_validated_manifest


DIAGNOSTIC_SCHEMA_VERSION = "a-end-face-main-housing-registration-diagnostic/1"
SUMMARY_SCHEMA_VERSION = "a-end-face-main-housing-registration-summary/1"
DEFAULT_CONFIG = PROJECT_ROOT / "config/end_face_short_line_candidate.v2.json"


def write_strict_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _image_input(path: Path) -> dict[str, Any]:
    return {"path": str(path), **inspect_image(path)}


def _algorithm(config_path: Path, config: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "registrationVersion": REGISTRATION_VERSION,
        "coreSourceSha256": CORE_SOURCE_SHA256,
        "candidateConfigPath": str(config_path),
        "candidateConfigSha256": candidate_config_sha256(config),
    }


def _load_registrar(
    reference_path: Path,
    config_path: Path,
) -> tuple[MainHousingRegistrar, dict[str, Any], dict[str, Any]]:
    config = load_candidate_config(config_path)
    if config.get("candidateId") != CANDIDATE_SOURCE_V2:
        raise ValueError("registration diagnostics require the main-housing-registration-v2 config")
    if sha256_file(Path(core.__file__).resolve()) != CORE_SOURCE_SHA256:
        raise ValueError("immutable A-end-face core source fingerprint mismatch")
    reference_info = _image_input(reference_path)
    registrar = MainHousingRegistrar(core.load_detection_gray(reference_path), config["registration"])
    return registrar, reference_info, _algorithm(config_path, config)


def _diagnose(
    registrar: MainHousingRegistrar,
    reference_info: Mapping[str, Any],
    algorithm: Mapping[str, Any],
    target_path: Path,
    *,
    image_id: str | None = None,
) -> dict[str, Any]:
    target_info: dict[str, Any] = {"path": str(target_path)}
    try:
        target_info = _image_input(target_path)
        registration = registrar.register(core.load_detection_gray(target_path))
        error = None
        technical_status = "succeeded"
        registration_payload: dict[str, Any] | None = registration.to_dict()
    except (OSError, ValueError) as exc:
        registration_payload = None
        technical_status = "failed"
        error = {"code": "REGISTRATION_DIAGNOSTIC_FAILED", "message": str(exc)}
    input_payload: dict[str, Any] = {
        "referenceImage": dict(reference_info),
        "targetImage": target_info,
    }
    if image_id is not None:
        input_payload["imageId"] = image_id
    return {
        "schemaVersion": DIAGNOSTIC_SCHEMA_VERSION,
        "technicalStatus": technical_status,
        "input": input_payload,
        "algorithm": dict(algorithm),
        "registration": registration_payload,
        "error": error,
    }


def diagnose_single(args: argparse.Namespace) -> int:
    reference_path = args.reference_image.resolve()
    target_path = args.target_image.resolve()
    config_path = args.candidate_config.resolve()
    registrar, reference_info, algorithm = _load_registrar(reference_path, config_path)
    record = _diagnose(registrar, reference_info, algorithm, target_path)
    output = args.output.resolve()
    write_strict_json(output, record)
    print(f"registration diagnostic -> {output}")
    return 0 if record["technicalStatus"] == "succeeded" else 1


def _count(total: int, value: int) -> dict[str, Any]:
    return {"total": total, "valid": value, "invalid": total - value}


def diagnose_batch(args: argparse.Namespace) -> int:
    manifest_path = args.manifest.resolve()
    data_root = args.data_root.resolve()
    manifest = load_validated_manifest(manifest_path, data_root)
    config_path = args.candidate_config.resolve()
    registrar, reference_info, algorithm = _load_registrar(args.reference_image.resolve(), config_path)
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    records_path = output_dir / "registration-diagnostics.jsonl"

    technical_succeeded = 0
    registration_valid = 0
    failure_reasons: Counter[str] = Counter()
    records: list[dict[str, Any]] = []
    for item in manifest["images"]:
        target_path = data_root / safe_relative_path(str(item["relativePath"]))
        record = _diagnose(
            registrar,
            reference_info,
            algorithm,
            target_path,
            image_id=str(item["imageId"]),
        )
        records.append(record)
        succeeded = record["technicalStatus"] == "succeeded"
        technical_succeeded += int(succeeded)
        registration = record.get("registration")
        valid = isinstance(registration, Mapping) and registration.get("valid") is True
        registration_valid += int(valid)
        if succeeded and isinstance(registration, Mapping) and not valid:
            failure_reasons[str(registration.get("failureReason") or "unspecified")] += 1
        elif not succeeded:
            error = record.get("error")
            code = error.get("code") if isinstance(error, Mapping) else None
            failure_reasons[str(code or "technical_failure")] += 1

    with records_path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n")

    total = len(records)
    summary = {
        "schemaVersion": SUMMARY_SCHEMA_VERSION,
        "dataset": {
            "datasetId": manifest.get("datasetId"),
            "datasetFingerprint": manifest.get("datasetFingerprint"),
            "manifestSha256": sha256_file(manifest_path),
        },
        "algorithm": algorithm,
        "referenceImage": reference_info,
        "imageCount": total,
        "technical": _count(total, technical_succeeded),
        "registration": _count(total, registration_valid),
        "failureReasons": dict(sorted(failure_reasons.items())),
        "diagnosticsJsonlSha256": sha256_file(records_path),
    }
    summary_path = output_dir / "registration-summary.json"
    write_strict_json(summary_path, summary)
    print(
        f"images={total} technical={technical_succeeded} "
        f"registration-valid={registration_valid}"
    )
    print(f"diagnostics -> {records_path}")
    print(f"summary -> {summary_path}")
    return 0 if technical_succeeded == total else 1


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    single = subparsers.add_parser("single", help="Diagnose one external target image.")
    single.add_argument("--reference-image", required=True, type=Path)
    single.add_argument("--target-image", required=True, type=Path)
    single.add_argument("--candidate-config", type=Path, default=DEFAULT_CONFIG)
    single.add_argument("--output", required=True, type=Path)
    single.set_defaults(handler=diagnose_single)

    batch = subparsers.add_parser("batch", help="Diagnose every image in a validated external Manifest.")
    batch.add_argument("--reference-image", required=True, type=Path)
    batch.add_argument("--manifest", required=True, type=Path)
    batch.add_argument("--data-root", required=True, type=Path)
    batch.add_argument("--candidate-config", type=Path, default=DEFAULT_CONFIG)
    batch.add_argument("--output-dir", required=True, type=Path)
    batch.set_defaults(handler=diagnose_batch)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        return int(args.handler(args))
    except (BatchInputError, OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
