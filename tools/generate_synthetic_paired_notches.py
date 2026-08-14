#!/usr/bin/env python3
"""Generate small paired-notch fixtures with independent centerline truth."""

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
    from .generate_synthetic_slot_pose import DEFAULT_SOURCE, circle_points, reference_annotation
    from .make_manifest import build_manifest
except ImportError:
    from dataset_common import sha256_file, write_json
    from generate_synthetic_slot_pose import DEFAULT_SOURCE, circle_points, reference_annotation
    from make_manifest import build_manifest


def _wedge(center: tuple[float, float], inner: float, outer: float, angle_deg: float, half_width_deg: float) -> list[tuple[float, float]]:
    cx, cy = center
    low = math.radians(angle_deg - half_width_deg)
    high = math.radians(angle_deg + half_width_deg)
    return [
        (cx + inner * math.cos(low), cy + inner * math.sin(low)),
        (cx + outer * math.cos(low), cy + outer * math.sin(low)),
        (cx + outer * math.cos(high), cy + outer * math.sin(high)),
        (cx + inner * math.cos(high), cy + inner * math.sin(high)),
    ]


def make_paired_face(
    centerline_deg: float,
    seed: int,
    *,
    size: int = 512,
    offset: tuple[float, float] = (0.0, 0.0),
    scale: float = 1.0,
    brightness: float = 1.0,
    noise: float = 1.0,
    notch_centers: list[float] | None = None,
    shadow_centers: list[float] | None = None,
    fixture_contact_centers: list[float] | None = None,
    weak_notch_centers: list[float] | None = None,
) -> Image.Image:
    rng = np.random.default_rng(seed)
    center = (size / 2.0 + offset[0], size / 2.0 + offset[1])
    outer = 180.0 * scale
    inner = 86.0 * scale
    image = Image.new("L", (size, size), 8)
    draw = ImageDraw.Draw(image)
    cx, cy = center
    draw.ellipse((cx - outer, cy - outer, cx + outer, cy + outer), fill=188, outline=230, width=3)
    for radius, color, width in ((145, 112, 4), (118, 220, 3), (102, 105, 3)):
        radius *= scale
        draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), outline=color, width=width)
    draw.ellipse((cx - inner, cy - inner, cx + inner, cy + inner), fill=18, outline=225, width=3)
    centers = notch_centers if notch_centers is not None else [centerline_deg - 20.0, centerline_deg + 20.0]
    for notch_center in centers:
        draw.polygon(_wedge(center, 145.0 * scale, 184.0 * scale, notch_center, 5.5), fill=12)
    for shadow_center in shadow_centers or []:
        draw.polygon(_wedge(center, 145.0 * scale, 165.0 * scale, shadow_center, 5.5), fill=45)
    for fixture_center in fixture_contact_centers or []:
        draw.polygon(_wedge(center, 170.0 * scale, 184.0 * scale, fixture_center, 5.5), fill=12)
    for weak_center in weak_notch_centers or []:
        draw.polygon(_wedge(center, 145.0 * scale, 184.0 * scale, weak_center, 5.5), fill=160)
    mark_angle = math.radians(centerline_deg + 103.0)
    mark_radius = 130.0 * scale
    mx = cx + mark_radius * math.cos(mark_angle)
    my = cy + mark_radius * math.sin(mark_angle)
    draw.ellipse((mx - 7, my - 4, mx + 7, my + 4), fill=55)
    array = np.asarray(image, dtype=np.float32) * float(brightness)
    if noise > 0.0:
        array += rng.normal(0.0, noise, array.shape)
    return Image.fromarray(np.clip(array, 0, 255).astype(np.uint8), mode="L")


def build_dataset(output_dir: Path, seed: int, source: Path = DEFAULT_SOURCE) -> dict:
    output_dir = output_dir.resolve()
    images_root = output_dir / "images"
    images_root.mkdir(parents=True, exist_ok=True)
    reference = output_dir / "reference.png"
    make_paired_face(0.0, seed, noise=0.0).save(reference)
    annotation = output_dir / "reference_label.json"
    write_json(annotation, reference_annotation(reference.name))

    cases = [
        ("normal_base", 0.0, {}, True),
        ("normal_translate", 30.0, {"offset": (7.0, -5.0)}, True),
        ("normal_scale_bright", 90.0, {"scale": 0.96, "brightness": 1.12, "noise": 1.8}, True),
        ("normal_wrap_pos", 179.0, {"noise": 1.5}, True),
        ("normal_wrap_neg", -179.0, {"brightness": 0.9, "noise": 1.5}, True),
        ("bad_missing_notch", 20.0, {"notch_centers": [0.0]}, False),
        ("bad_ambiguous", 40.0, {"notch_centers": [0.0, 40.0, 80.0]}, False),
        ("bad_cropped", 0.0, {"offset": (120.0, 0.0)}, False),
    ]
    truth_rows: list[dict[str, object]] = []
    for index, (case_id, truth_angle, options, truth_valid) in enumerate(cases, start=1):
        directory = images_root / "development" / "sample_paired" / case_id
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / "repeat_001.png"
        make_paired_face(truth_angle, seed + index, **options).save(path)
        truth_rows.append({
            "image_sha256": sha256_file(path),
            "truth_valid": str(truth_valid).lower(),
            "truth_angle_deg": truth_angle if truth_valid else "",
            "truth_source": "synthetic_paired_geometry" if truth_valid else "synthetic_negative_case",
            "calibration_id": "synthetic-image-cw-v1",
            "sample": "sample_paired",
            "condition": case_id,
            "repeat": 1,
            "split": "development",
            "dataset_class": "normal" if truth_valid else "bad",
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
        "config_id": "synthetic-paired-notch-cw-v1",
        "legacy_asset": {
            "source_path": str(source), "source_sha256": sha256_file(source),
            "annotation_path": str(annotation), "annotation_sha256": sha256_file(annotation),
            "reference_path": str(reference), "reference_sha256": sha256_file(reference),
        },
        "pose": {
            "reference_frame": "SYNTHETIC_IMAGE", "target_frame": "SYNTHETIC_MECHANICAL",
            "mechanical_zero_image_deg": 0.0, "positive_direction": "cw",
            "conventions_confirmed": True, "target_semantics_confirmed": True,
            "valid_range_deg": [-180.0, 179.999999], "production_plc_mapping_confirmed": False,
        },
        "detector": {
            "diagnostic_mode": "paired_notches_centerline",
            "min_notch_prominence": 12.0, "min_polar_score": 2.0,
            "max_rotation_disagreement_deg": 8.0, "min_scale": 0.8, "max_scale": 1.2,
            "max_polar_pair_disagreement_deg": 8.0,
            "profile": {
                "n_angles": 1440, "n_radii": 10, "shell_width_px": 30.0,
                "smoothing_window": 7, "mad_multiplier": 3.0, "min_prominence": 12.0,
                "min_half_width_deg": 2.0, "max_half_width_deg": 12.0,
            },
            "pairing": {
                "min_candidates": 2, "max_candidates": 6,
                "min_separation_deg": 30.0, "max_separation_deg": 50.0,
                "expected_separation_deg": 40.0, "min_width_ratio": 0.6,
                "min_prominence_ratio": 0.6, "min_pair_score": 0.7, "min_score_margin": 0.1,
            },
        },
        "calibration": {"mm_per_px": None},
        "feature_mappings": [],
        "repeatability": {"min_valid_repeats": 20, "min_dynamic_positions": 2},
    }
    config_path = output_dir / "config.json"
    write_json(config_path, config)
    manifest = build_manifest(images_root, "synthetic-paired-notch", "slot_pose", 1, "sample_paired", "unknown")
    truth_by_hash = {str(row["image_sha256"]): row for row in truth_rows}
    for item in manifest["images"]:
        truth = truth_by_hash[item["sha256"]]
        item["datasetClass"] = truth["dataset_class"]
        item["conditionId"] = truth["condition"]
    manifest_path = output_dir / "manifest.json"
    write_json(manifest_path, manifest)
    return {
        "images": len(cases), "images_root": str(images_root), "manifest": str(manifest_path),
        "truth": str(truth_path), "config": str(config_path),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--seed", type=int, default=137)
    parser.add_argument("--legacy-source", type=Path, default=DEFAULT_SOURCE)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        result = build_dataset(args.output_dir, args.seed, args.legacy_source)
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}")
        return 2
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
