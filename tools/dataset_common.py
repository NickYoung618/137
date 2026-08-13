#!/usr/bin/env python3
"""Shared helpers for portable image dataset manifests."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from PIL import Image


IMAGE_SUFFIXES = {".bmp", ".png", ".jpg", ".jpeg", ".tif", ".tiff"}
MANIFEST_SCHEMA_VERSION = "inspection-dataset-manifest/1"


def natural_key(value: str) -> list[object]:
    return [int(part) if part.isdigit() else part.casefold() for part in re.split(r"(\d+)", value)]


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inspect_image(path: Path) -> dict[str, Any]:
    with Image.open(path) as image:
        width, height = image.size
        image_format = image.format or path.suffix.removeprefix(".").upper()
        mode = image.mode
    return {
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
        "format": image_format,
        "width": width,
        "height": height,
        "mode": mode,
    }


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def safe_relative_path(value: str) -> Path:
    candidate = Path(value)
    if candidate.is_absolute() or not value or any(part in {"", ".", ".."} for part in candidate.parts):
        raise ValueError(f"unsafe relative path: {value!r}")
    return candidate
