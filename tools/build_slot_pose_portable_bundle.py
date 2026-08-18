#!/usr/bin/env python3
"""Build a deterministic, self-contained slot-pose runtime asset bundle."""

from __future__ import annotations

import argparse
import copy
import gzip
import importlib.util
import io
import json
import os
import re
import shutil
import sys
import tarfile
import tempfile
from collections.abc import Sequence
from pathlib import Path, PurePosixPath
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
HEX40 = re.compile(r"^[0-9a-f]{40}$")
BUNDLE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


def _inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def _require_external_new_target(path: Path, label: str) -> None:
    if _inside(path, ROOT):
        raise ValueError(f"{label} must be outside the Git working tree: {path}")
    if path.exists() or path.is_symlink():
        raise FileExistsError(f"{label} already exists: {path}")


def _canonical_json(value: Any) -> str:
    return json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n"


def _entry(root: Path, relative: str, role: str) -> dict[str, Any]:
    path = root / relative
    return {
        "path": relative,
        "role": role,
        "sizeBytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def _verify_annotation_reference(annotation: Path, reference: Path) -> None:
    try:
        payload = json.loads(annotation.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"annotation is not readable JSON: {annotation}") from exc
    image_path = payload.get("imagePath")
    if not isinstance(image_path, str) or not image_path.strip():
        raise ValueError("annotation.imagePath must name the locked reference image")
    pure = PurePosixPath(image_path)
    if pure.is_absolute() or len(pure.parts) != 1 or pure.name != reference.name:
        raise ValueError(
            "annotation.imagePath must already be the colocated reference basename; "
            "portable packaging will not rewrite locked annotation bytes"
        )


def _bundled_source_path() -> Path:
    spec = importlib.util.find_spec(BUNDLED_LEGACY_MODULE)
    if spec is None or not spec.origin:
        raise ValueError(f"cannot resolve bundled module {BUNDLED_LEGACY_MODULE}")
    return Path(spec.origin).resolve()


def _readme(bundle_id: str, branch: str, commit: str) -> str:
    return (
        f"# {bundle_id}\n\n"
        f"Algorithm branch: `{branch}`  \n"
        f"Algorithm commit: `{commit}`\n\n"
        "This directory contains every non-code runtime asset required by the locked "
        "slot-pose configuration. Keep the files together and do not edit them.\n\n"
        "Verify from the repository checkout:\n\n"
        "```bash\n"
        f"git checkout {commit}\n"
        "python tools/verify_slot_pose_portable_bundle.py --bundle-dir /path/to/"
        f"{bundle_id}\n"
        "```\n\n"
        "Use `config.json` with the existing replay command. The bundle may be moved; "
        "asset paths resolve from `config.json`, not from the shell working directory. "
        "PLC execution remains unauthorized.\n"
    )


def _write_deterministic_archive(bundle_root: Path, archive_path: Path, bundle_id: str) -> None:
    files = sorted(path for path in bundle_root.rglob("*") if path.is_file())
    with (
        archive_path.open("wb") as raw,
        gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0, compresslevel=9) as zipped,
        tarfile.open(fileobj=zipped, mode="w", format=tarfile.USTAR_FORMAT) as archive,
    ):
        for path in files:
            relative = path.relative_to(bundle_root).as_posix()
            info = tarfile.TarInfo(f"{bundle_id}/{relative}")
            data = path.read_bytes()
            info.size = len(data)
            info.mode = 0o644
            info.uid = 0
            info.gid = 0
            info.uname = ""
            info.gname = ""
            info.mtime = 0
            archive.addfile(info, fileobj=io.BytesIO(data))


def build_bundle(
    source_config_path: Path,
    output_dir: Path,
    archive_path: Path,
    *,
    bundle_id: str,
    branch: str,
    commit: str,
) -> dict[str, Any]:
    source_config_path = source_config_path.resolve()
    output_dir = output_dir.resolve()
    archive_path = archive_path.resolve()
    if not BUNDLE_ID.fullmatch(bundle_id):
        raise ValueError("bundle_id must contain only portable filename characters")
    if not branch.strip() or not HEX40.fullmatch(commit):
        raise ValueError("branch and lowercase 40-character commit are required")
    _require_external_new_target(output_dir, "output directory")
    _require_external_new_target(archive_path, "archive")
    if _inside(archive_path, output_dir):
        raise ValueError("archive must not be placed inside the output directory")
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    archive_path.parent.mkdir(parents=True, exist_ok=True)

    raw = json.loads(source_config_path.read_text(encoding="utf-8"))
    source = load_config(source_config_path)
    asset = source["legacy_asset"]
    if asset.get("source_mode") != "bundled_module" or asset.get("bundled_module") != BUNDLED_LEGACY_MODULE:
        raise ValueError("portable bundle requires the repository bundled algorithm module")
    bundled_source = _bundled_source_path()
    if sha256_file(bundled_source) != asset["source_sha256"]:
        raise ValueError("bundled algorithm source SHA-256 does not match reviewed configuration")
    annotation = Path(asset["annotation_path"])
    reference = Path(asset["reference_path"])
    for path, expected, label in (
        (annotation, asset["annotation_sha256"], "annotation"),
        (reference, asset["reference_sha256"], "reference"),
    ):
        if not path.is_file() or sha256_file(path) != expected:
            raise ValueError(f"{label} asset is missing or does not match reviewed SHA-256")
    _verify_annotation_reference(annotation, reference)

    portable_raw = copy.deepcopy(raw)
    portable_asset = portable_raw["legacy_asset"]
    portable_asset["path_mode"] = PORTABLE_ASSET_PATH_MODE
    portable_asset["annotation_path"] = "assets/annotation.json"
    portable_asset["reference_path"] = "assets/reference.bmp"
    portable_asset.pop("source_path", None)

    staging = Path(tempfile.mkdtemp(prefix=f".{bundle_id}.", dir=output_dir.parent))
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{archive_path.name}.", suffix=".tmp", dir=archive_path.parent
    )
    os.close(descriptor)
    archive_temp = Path(temporary_name)
    archive_temp.unlink()
    try:
        (staging / "assets").mkdir()
        shutil.copyfile(annotation, staging / "assets/annotation.json")
        shutil.copyfile(reference, staging / "assets/reference.bmp")
        (staging / "config.json").write_text(_canonical_json(portable_raw), encoding="utf-8")
        (staging / "README.md").write_text(_readme(bundle_id, branch, commit), encoding="utf-8")

        portable = load_config(staging / "config.json")
        source_effective = effective_config_sha256(source)
        portable_effective = effective_config_sha256(portable)
        if portable_effective != source_effective:
            raise ValueError("portable configuration changed effective algorithm identity")
        files = [_entry(staging, path, role) for path, role in sorted(REQUIRED_PAYLOAD.items())]
        manifest = {
            "schemaVersion": SCHEMA_VERSION,
            "bundleId": bundle_id,
            "algorithm": {
                "branch": branch,
                "commit": commit,
                "bundledModule": BUNDLED_LEGACY_MODULE,
                "sourceSha256": asset["source_sha256"],
            },
            "configuration": {
                "path": "config.json",
                "sourceConfigSha256": sha256_file(source_config_path),
                "portableConfigSha256": sha256_file(staging / "config.json"),
                "effectiveConfigSha256": portable_effective,
            },
            "archive": {"format": "tar.gz", "reproducibilityVersion": REPRODUCIBILITY_VERSION},
            "files": files,
        }
        (staging / "manifest.json").write_text(_canonical_json(manifest), encoding="utf-8")
        checksummed = [entry["path"] for entry in files] + ["manifest.json"]
        sums = "".join(f"{sha256_file(staging / path)}  {path}\n" for path in sorted(checksummed))
        (staging / "SHA256SUMS").write_text(sums, encoding="utf-8")

        from tools.verify_slot_pose_portable_bundle import verify_bundle

        verification = verify_bundle(staging)
        _write_deterministic_archive(staging, archive_temp, bundle_id)
        os.replace(staging, output_dir)
        os.replace(archive_temp, archive_path)
        return {
            **verification,
            "bundleDir": str(output_dir),
            "archivePath": str(archive_path),
            "archiveSha256": sha256_file(archive_path),
        }
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        archive_temp.unlink(missing_ok=True)
        raise


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-config", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--archive", required=True, type=Path)
    parser.add_argument("--bundle-id", required=True)
    parser.add_argument("--branch", required=True)
    parser.add_argument("--commit", required=True)
    args = parser.parse_args(argv)
    try:
        report = build_bundle(
            args.source_config,
            args.output_dir,
            args.archive,
            bundle_id=args.bundle_id,
            branch=args.branch,
            commit=args.commit,
        )
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
