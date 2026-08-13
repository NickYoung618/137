#!/usr/bin/env python3
"""Generate small concentric A-face/notch fixtures for adapter regression only."""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

try:
    from .dataset_common import sha256_file, write_json
except ImportError:
    from dataset_common import sha256_file, write_json


DEFAULT_SOURCE = Path("/home/ubuntu/disk/gyj/HousingInspectionDemo/algorithms/a_end_face/main.py")


def circle_points(cx: float, cy: float, radius: float, count: int = 180) -> list[list[float]]:
    return [
        [cx + radius * math.cos(2.0 * math.pi * i / count), cy + radius * math.sin(2.0 * math.pi * i / count)]
        for i in range(count)
    ]


def make_face(angle_deg: float, seed: int, size: int = 512, noisy: bool = True) -> Image.Image:
    rng = np.random.default_rng(seed)
    cx = cy = size / 2.0
    outer = 180.0
    inner = 86.0
    image = Image.new("L", (size, size), 8)
    draw = ImageDraw.Draw(image)
    draw.ellipse((cx - outer, cy - outer, cx + outer, cy + outer), fill=188, outline=230, width=3)
    for radius, color, width in ((145, 112, 4), (118, 220, 3), (102, 105, 3)):
        draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), outline=color, width=width)
    draw.ellipse((cx - inner, cy - inner, cx + inner, cy + inner), fill=18, outline=225, width=3)
    angle = math.radians(angle_deg)
    half = math.radians(11.0)
    polygon = []
    for radius, theta in ((145, angle - half), (184, angle - half), (184, angle + half), (145, angle + half)):
        polygon.append((cx + radius * math.cos(theta), cy + radius * math.sin(theta)))
    draw.polygon(polygon, fill=12)
    # One weak asymmetric mark keeps polar phase correlation observable without
    # becoming a second notch candidate.
    mark_angle = angle + math.radians(95.0)
    mx = cx + 132 * math.cos(mark_angle)
    my = cy + 132 * math.sin(mark_angle)
    draw.ellipse((mx - 5, my - 5, mx + 5, my + 5), fill=70)
    if noisy:
        array = np.asarray(image, dtype=np.float32)
        array += rng.normal(0.0, 1.2, array.shape)
        image = Image.fromarray(np.clip(array, 0, 255).astype(np.uint8), mode="L")
    return image


def reference_annotation(reference_name: str, size: int = 512) -> dict:
    center = size / 2.0
    return {
        "version": "5.0.1",
        "flags": {},
        "shapes": [
            {"label": "synthetic_inner", "points": circle_points(center, center, 86), "group_id": None, "shape_type": "linestrip", "flags": {}},
            {"label": "synthetic_outer", "points": circle_points(center, center, 180), "group_id": None, "shape_type": "linestrip", "flags": {}},
        ],
        "imagePath": reference_name,
        "imageData": None,
        "imageHeight": size,
        "imageWidth": size,
    }


def build_dataset(output_dir: Path, angles: list[float], repeats: int, seed: int, source: Path) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    dataset_root = output_dir / "synthetic"
    dataset_root.mkdir(parents=True, exist_ok=True)
    reference = output_dir / "reference.png"
    make_face(0.0, seed, noisy=False).save(reference)
    annotation = output_dir / "reference_label.json"
    write_json(annotation, reference_annotation(reference.name))

    truth_rows: list[dict[str, object]] = []
    for angle_index, angle in enumerate(angles):
        label = f"angle_{angle:+07.2f}".replace("+", "pos_").replace("-", "neg_").replace(".", "p")
        group = dataset_root / "sample_synthetic" / label
        group.mkdir(parents=True, exist_ok=True)
        for repeat in range(repeats):
            image_path = group / f"repeat_{repeat + 1:03d}.png"
            make_face(angle, seed + angle_index * 1000 + repeat + 1).save(image_path)
            relative = image_path.relative_to(dataset_root).as_posix()
            image_hash = sha256_file(image_path)
            truth_rows.append({
                "relative_path": relative,
                "image_sha256": image_hash,
                "sample": "sample_synthetic",
                "position": label,
                "repeat": repeat + 1,
                "truth_angle_deg": angle,
                "truth_valid": "true",
                "truth_source": "synthetic_configured_geometry",
            })
            slot_json = image_path.with_suffix(".slot.json")
            center = 256.0
            endpoint = [center + 180 * math.cos(math.radians(angle)), center + 180 * math.sin(math.radians(angle))]
            write_json(slot_json, {
                "schemaVersion": "slot-pose-annotation/1", "imagePath": relative,
                "imageSha256": image_hash, "sampleId": "sample_synthetic", "position": label,
                "repeatIndex": repeat + 1, "face": {"centerX": center, "centerY": center, "radiusPx": 180},
                "slotPolygon": None, "slotCenterline": [[center, center], endpoint],
                "truthAngleDeg": angle, "truthSource": "synthetic_configured_geometry",
                "calibrationId": "synthetic-image-cw-v1", "split": "development",
            })

    truth_path = output_dir / "ground_truth.csv"
    with truth_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(truth_rows[0]))
        writer.writeheader()
        writer.writerows(truth_rows)

    source = source.resolve()
    config = {
        "schema_version": "slot-pose-config/1",
        "project": "137-housing-slot-pose",
        "config_id": "synthetic-slot-pose-cw-v1",
        "legacy_asset": {
            "source_path": str(source), "source_sha256": sha256_file(source),
            "annotation_path": str(annotation.resolve()), "annotation_sha256": sha256_file(annotation),
            "reference_path": str(reference.resolve()), "reference_sha256": sha256_file(reference),
        },
        "pose": {
            "reference_frame": "SYNTHETIC_IMAGE", "target_frame": "SYNTHETIC_MECHANICAL",
            "mechanical_zero_image_deg": 0.0, "positive_direction": "cw", "conventions_confirmed": True,
            "valid_range_deg": [-180.0, 179.999999], "production_plc_mapping_confirmed": False,
        },
        "detector": {
            "min_notch_prominence": 12.0, "min_polar_score": 2.0,
            "max_rotation_disagreement_deg": 8.0, "min_scale": 0.8, "max_scale": 1.2,
        },
        "calibration": {"mm_per_px": None},
        "feature_mappings": [{
            "feature_code": "A_FACE_SLOT_SIGNED_ROTATION", "name": "synthetic angle",
            "source_column": "signed_relative_rotation_deg", "source_unit": "deg", "output_unit": "deg",
            "scale": 1.0, "repeatability_tier": "ANGLE_PENDING", "enabled": True,
        }],
        "repeatability": {
            "metric": "range", "min_valid_repeats": 20, "min_dynamic_positions": 2,
            "tiers": {"ANGLE_PENDING": {"unit": "deg", "limit": None}},
        },
    }
    config_path = output_dir / "synthetic-config.json"
    write_json(config_path, config)
    return {"images": len(truth_rows), "dataset_root": str(dataset_root), "truth": str(truth_path), "config": str(config_path)}


def parse_angles(value: str) -> list[float]:
    values = [float(item) for item in value.split(",") if item.strip()]
    if not values:
        raise argparse.ArgumentTypeError("at least one angle is required")
    return values


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--angles", type=parse_angles, default=parse_angles("-170,-90,-30,0,30,90,170"))
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--seed", type=int, default=137)
    parser.add_argument("--legacy-source", type=Path, default=DEFAULT_SOURCE)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.repeats <= 0:
        print("ERROR: repeats must be positive")
        return 2
    try:
        result = build_dataset(args.output_dir.resolve(), args.angles, args.repeats, args.seed, args.legacy_source)
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}")
        return 2
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
