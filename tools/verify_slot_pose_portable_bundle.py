#!/usr/bin/env python3
"""Independently verify a self-contained slot-pose runtime asset bundle."""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from collections.abc import Sequence
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from algorithms.slot_pose.contract import (
    BUNDLED_LEGACY_MODULE,
    PORTABLE_ASSET_PATH_MODE,
    effective_config_sha256,
    load_config,
    sha256_file,
)

SCHEMA_VERSION = "slot-pose-portable-bundle/1"
REPRODUCIBILITY_VERSION = "normalized-tar-gzip/1"
REQUIRED_PAYLOAD = {
    "config.json": "runtime_config",
    "assets/annotation.json": "annotation",
    "assets/reference.bmp": "reference_image",
    "README.md": "operator_instructions",
}
EXPECTED_ALL_FILES = set(REQUIRED_PAYLOAD) | {"manifest.json", "SHA256SUMS"}
SHA256 = re.compile(r"^[0-9a-f]{64}$")
HEX40 = re.compile(r"^[0-9a-f]{40}$")
BUNDLE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


def _safe_relative(value: Any, label: str) -> PurePosixPath:
    if not isinstance(value, str) or not value or value != value.strip() or "\\" in value:
        raise ValueError(f"{label} is not a normalized portable relative path")
    posix = PurePosixPath(value)
    windows = PureWindowsPath(value)
    if posix.is_absolute() or windows.is_absolute() or windows.drive:
        raise ValueError(f"{label} must be relative")
    if any(part in {"", ".", ".."} for part in posix.parts):
        raise ValueError(f"{label} contains traversal")
    return posix


def _confined_file(root: Path, relative: Any, label: str) -> Path:
    posix = _safe_relative(relative, label)
    path = (root / Path(*posix.parts)).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"{label} resolves outside bundle") from exc
    if not path.is_file() or path.is_symlink():
        raise ValueError(f"{label} is missing, not regular, or is a symlink")
    return path


def _require_sha(value: Any, label: str) -> str:
    if not isinstance(value, str) or not SHA256.fullmatch(value):
        raise ValueError(f"{label} is not a lowercase SHA-256")
    return value


def _validate_manifest(manifest: Any) -> dict[str, Any]:
    if not isinstance(manifest, dict) or set(manifest) != {
        "schemaVersion", "bundleId", "algorithm", "configuration", "archive", "files",
    }:
        raise ValueError("manifest root fields are invalid")
    if manifest["schemaVersion"] != SCHEMA_VERSION:
        raise ValueError("manifest schemaVersion is unsupported")
    if not isinstance(manifest["bundleId"], str) or not BUNDLE_ID.fullmatch(manifest["bundleId"]):
        raise ValueError("manifest bundleId is invalid")
    algorithm = manifest["algorithm"]
    if not isinstance(algorithm, dict) or set(algorithm) != {
        "branch", "commit", "bundledModule", "sourceSha256",
    }:
        raise ValueError("manifest algorithm fields are invalid")
    if not isinstance(algorithm["branch"], str) or not algorithm["branch"].strip():
        raise ValueError("manifest branch is invalid")
    if not isinstance(algorithm["commit"], str) or not HEX40.fullmatch(algorithm["commit"]):
        raise ValueError("manifest commit is invalid")
    if algorithm["bundledModule"] != BUNDLED_LEGACY_MODULE:
        raise ValueError("manifest bundled module is invalid")
    _require_sha(algorithm["sourceSha256"], "algorithm.sourceSha256")
    configuration = manifest["configuration"]
    if not isinstance(configuration, dict) or set(configuration) != {
        "path", "sourceConfigSha256", "portableConfigSha256", "effectiveConfigSha256",
    }:
        raise ValueError("manifest configuration fields are invalid")
    if configuration["path"] != "config.json":
        raise ValueError("manifest configuration path is invalid")
    for key in ("sourceConfigSha256", "portableConfigSha256", "effectiveConfigSha256"):
        _require_sha(configuration[key], f"configuration.{key}")
    if manifest["archive"] != {
        "format": "tar.gz", "reproducibilityVersion": REPRODUCIBILITY_VERSION,
    }:
        raise ValueError("manifest archive contract is invalid")
    files = manifest["files"]
    if not isinstance(files, list) or len(files) != len(REQUIRED_PAYLOAD):
        raise ValueError("manifest files must enumerate the four payload files")
    seen: dict[str, str] = {}
    for entry in files:
        if not isinstance(entry, dict) or set(entry) != {"path", "role", "sizeBytes", "sha256"}:
            raise ValueError("manifest file entry fields are invalid")
        relative = _safe_relative(entry["path"], "manifest file path").as_posix()
        if relative in seen:
            raise ValueError("manifest file paths must be unique")
        if isinstance(entry["sizeBytes"], bool) or not isinstance(entry["sizeBytes"], int) or entry["sizeBytes"] < 0:
            raise ValueError("manifest file size is invalid")
        _require_sha(entry["sha256"], f"files[{relative}].sha256")
        seen[relative] = entry["role"]
    if seen != REQUIRED_PAYLOAD:
        raise ValueError("manifest file paths/roles do not match the portable bundle contract")
    return manifest


def _parse_sums(path: Path) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if "  " not in line:
            raise ValueError("SHA256SUMS line is malformed")
        digest, relative = line.split("  ", 1)
        _require_sha(digest, "SHA256SUMS digest")
        relative = _safe_relative(relative, "SHA256SUMS path").as_posix()
        if relative in parsed:
            raise ValueError("SHA256SUMS contains duplicate paths")
        parsed[relative] = digest
    return parsed


def verify_bundle(bundle_dir: Path) -> dict[str, Any]:
    root = bundle_dir.resolve()
    if not root.is_dir():
        raise ValueError(f"bundle directory does not exist: {root}")
    actual_files: set[str] = set()
    for path in root.rglob("*"):
        if path.is_symlink():
            raise ValueError(f"bundle must not contain symlinks: {path}")
        if path.is_file():
            actual_files.add(path.relative_to(root).as_posix())
    if actual_files != EXPECTED_ALL_FILES:
        raise ValueError(f"bundle file inventory mismatch: {sorted(actual_files ^ EXPECTED_ALL_FILES)}")

    manifest_path = _confined_file(root, "manifest.json", "manifest")
    manifest = _validate_manifest(json.loads(manifest_path.read_text(encoding="utf-8")))
    entries = {entry["path"]: entry for entry in manifest["files"]}
    for relative, entry in entries.items():
        path = _confined_file(root, relative, f"payload {relative}")
        if path.stat().st_size != entry["sizeBytes"] or sha256_file(path) != entry["sha256"]:
            raise ValueError(f"payload integrity mismatch: {relative}")
    sums = _parse_sums(_confined_file(root, "SHA256SUMS", "checksum list"))
    expected_sums = set(REQUIRED_PAYLOAD) | {"manifest.json"}
    if set(sums) != expected_sums:
        raise ValueError("SHA256SUMS inventory mismatch")
    for relative, expected in sums.items():
        if sha256_file(_confined_file(root, relative, f"checksum target {relative}")) != expected:
            raise ValueError(f"SHA256SUMS mismatch: {relative}")

    raw_config = json.loads((root / "config.json").read_text(encoding="utf-8"))
    asset = raw_config.get("legacy_asset", {})
    if asset.get("path_mode") != PORTABLE_ASSET_PATH_MODE:
        raise ValueError("portable config must use config_relative_v1")
    if asset.get("source_mode") != "bundled_module" or asset.get("bundled_module") != BUNDLED_LEGACY_MODULE:
        raise ValueError("portable config must use bundled algorithm source")
    if asset.get("annotation_path") != "assets/annotation.json" or asset.get("reference_path") != "assets/reference.bmp":
        raise ValueError("portable config asset paths are not canonical")
    text_payload = "\n".join(
        (root / relative).read_text(encoding="utf-8")
        for relative in ("config.json", "manifest.json", "README.md")
    ).lower()
    for forbidden in ("/home/", "\\users\\", "file://"):
        if forbidden in text_payload:
            raise ValueError("portable text payload contains an external absolute path")

    config = load_config(root / "config.json")
    configuration = manifest["configuration"]
    if sha256_file(root / "config.json") != configuration["portableConfigSha256"]:
        raise ValueError("portable configuration SHA-256 mismatch")
    effective = effective_config_sha256(config)
    if effective != configuration["effectiveConfigSha256"]:
        raise ValueError("effective configuration SHA-256 mismatch")
    if asset["source_sha256"] != manifest["algorithm"]["sourceSha256"]:
        raise ValueError("source SHA-256 differs between config and manifest")
    spec = importlib.util.find_spec(BUNDLED_LEGACY_MODULE)
    if spec is None or not spec.origin or sha256_file(Path(spec.origin)) != asset["source_sha256"]:
        raise ValueError("checked-out bundled algorithm source does not match package")

    annotation = Path(config["legacy_asset"]["annotation_path"])
    reference = Path(config["legacy_asset"]["reference_path"])
    annotation_payload = json.loads(annotation.read_text(encoding="utf-8"))
    image_path = annotation_payload.get("imagePath")
    if image_path != reference.name or (annotation.parent / image_path).resolve() != reference:
        raise ValueError("annotation does not resolve to the packaged reference image")
    if sha256_file(annotation) != asset["annotation_sha256"] or sha256_file(reference) != asset["reference_sha256"]:
        raise ValueError("portable asset SHA-256 differs from config locks")
    return {
        "schemaVersion": "slot-pose-portable-bundle-verification/1",
        "valid": True,
        "bundleId": manifest["bundleId"],
        "algorithmCommit": manifest["algorithm"]["commit"],
        "portableConfigSha256": configuration["portableConfigSha256"],
        "effectiveConfigSha256": effective,
        "verifiedFileCount": len(actual_files),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        report = verify_bundle(args.bundle_dir)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
