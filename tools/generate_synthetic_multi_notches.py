#!/usr/bin/env python3
"""Generate compact multi-notch role fixtures; angles are diagnostic drawing geometry."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.dataset_common import sha256_file, write_json
from tools.generate_synthetic_paired_notches import make_paired_face
from tools.generate_synthetic_slot_pose import DEFAULT_SOURCE, reference_annotation


REFERENCE_ROLES = [90.0, 175.0, 270.0, 330.0]


def _rotated(angles: list[float], rotation: float) -> list[float]:
    return [(angle + rotation) % 360.0 for angle in angles]


def build_dataset(output_dir: Path, seed: int, source: Path = DEFAULT_SOURCE) -> dict[str, str]:
    output_dir = output_dir.resolve()
    images = output_dir / "images"
    images.mkdir(parents=True, exist_ok=True)
    reference = output_dir / "reference.png"
    make_paired_face(0.0, seed, noise=0.0, notch_centers=REFERENCE_ROLES).save(reference)
    annotation = output_dir / "reference_label.json"
    write_json(annotation, reference_annotation(reference.name))
    cases = {
        "normal_base": (0.0, REFERENCE_ROLES, {}),
        "normal_translate": (30.0, _rotated(REFERENCE_ROLES, 30.0), {"offset": (7.0, -5.0)}),
        "normal_wrap": (179.0, _rotated(REFERENCE_ROLES, 179.0), {"noise": 1.5}),
        "bad_missing_target": (0.0, [90.0, 270.0, 330.0], {}),
        "bad_ambiguous_target": (0.0, [90.0, 168.0, 182.0, 270.0, 330.0], {}),
    }
    for index, (name, (_, centers, options)) in enumerate(cases.items(), start=1):
        make_paired_face(0.0, seed + index, notch_centers=centers, **options).save(images / f"{name}.png")
    source = source.resolve()
    config = {
        "schema_version": "slot-pose-config/1", "project": "137-housing-slot-pose",
        "config_id": "synthetic-multi-notch-role-v1",
        "legacy_asset": {
            "source_path": str(source), "source_sha256": sha256_file(source),
            "annotation_path": str(annotation), "annotation_sha256": sha256_file(annotation),
            "reference_path": str(reference), "reference_sha256": sha256_file(reference),
        },
        "pose": {
            "reference_frame": "SYNTHETIC_IMAGE", "target_frame": "SYNTHETIC_MECHANICAL",
            "mechanical_zero_image_deg": None, "positive_direction": None,
            "conventions_confirmed": False, "target_semantics_confirmed": False,
            "drawing_datum_definition_confirmed": False,
            "a2_drawing_feature_mapping_confirmed": False,
            "output_purpose": None, "valid_range_deg": None,
            "production_plc_mapping_confirmed": False,
        },
        "detector": {
            "diagnostic_mode": "multi_notch_roles", "min_notch_prominence": 12.0,
            "min_polar_score": 2.0, "max_rotation_disagreement_deg": 8.0,
            "min_scale": 0.8, "max_scale": 1.2,
            "profile": {
                "n_angles": 1440, "n_radii": 10, "shell_width_px": 30.0,
                "smoothing_window": 7, "mad_multiplier": 3.0, "min_prominence": 12.0,
                "min_half_width_deg": 2.0, "max_half_width_deg": 12.0,
            },
            "role_assignment": {
                "datum_definition": "opposed_candidates_axis", "min_score_margin": 0.08,
                "max_opposition_error_deg": 8.0, "drawing_nominal_angle_deg": 85.0,
                "drawing_tolerance_deg": 5.0,
                "assignments": {
                    "datum_primary": {"expected_reference_azimuth_deg": 90.0, "max_deviation_deg": 12.0},
                    "target_left": {"expected_reference_azimuth_deg": 175.0, "max_deviation_deg": 12.0},
                    "datum_secondary": {"expected_reference_azimuth_deg": 270.0, "max_deviation_deg": 12.0},
                },
            },
        },
        "calibration": {"mm_per_px": None}, "feature_mappings": [],
        "repeatability": {"min_valid_repeats": 20, "min_dynamic_positions": 2},
    }
    config_path = output_dir / "config.json"
    write_json(config_path, config)
    truth = {
        name: {"globalRotationDeg": rotation, "includedAngleDeg": 85.0 if name.startswith("normal") else None}
        for name, (rotation, _, _) in cases.items()
    }
    write_json(output_dir / "diagnostic_truth.json", truth)
    return {"images": str(images), "config": str(config_path), "truth": str(output_dir / "diagnostic_truth.json")}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--seed", type=int, default=137)
    parser.add_argument("--legacy-source", type=Path, default=DEFAULT_SOURCE)
    args = parser.parse_args()
    try:
        result = build_dataset(args.output_dir, args.seed, args.legacy_source)
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}")
        return 2
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
