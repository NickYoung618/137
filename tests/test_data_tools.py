from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from PIL import Image

from tools.evaluate_repeatability import evaluate
from tools.make_manifest import build_manifest
from tools.validate_dataset import validate_manifest


class DataToolTests(unittest.TestCase):
    def test_manifest_validation_and_repeatability(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for position, values in {"pos_1": (10, 11), "pos_2": (12, 13)}.items():
                directory = root / "sample_1" / position
                directory.mkdir(parents=True)
                for index, value in enumerate(values, start=1):
                    Image.new("L", (8, 6), value).save(directory / f"image_{index:03d}.bmp")

            manifest = build_manifest(root, "unit-data", "unit", 2, "sample_1", "pos_1")
            report = validate_manifest(manifest, root)
            self.assertTrue(report["valid"], report)
            self.assertEqual(4, report["checkedImageCount"])
            self.assertEqual(2, report["groupCount"])

            config = {
                "calibration": {"mm_per_px": 0.1},
                "feature_mappings": [
                    {
                        "feature_code": "F1",
                        "name": "feature",
                        "source_column": "value_px",
                        "source_unit": "px",
                        "output_unit": "mm",
                        "scale": 1,
                        "repeatability_tier": "R0.10"
                    }
                ],
                "repeatability": {
                    "metric": "range",
                    "min_valid_repeats": 2,
                    "min_dynamic_positions": 2,
                    "tiers": {"R0.10": {"unit": "mm", "limit": 0.1}}
                }
            }
            rows = [
                {"sample": "sample_1", "position": "pos_1", "value_px": "10"},
                {"sample": "sample_1", "position": "pos_1", "value_px": "10.5"},
                {"sample": "sample_1", "position": "pos_2", "value_px": "11"},
                {"sample": "sample_1", "position": "pos_2", "value_px": "11.5"}
            ]
            static, dynamic = evaluate(rows, config, "sample", "position")
            self.assertEqual(2, len(static))
            self.assertEqual("PASS", static[0]["tier_status"])
            self.assertEqual(1, len(dynamic))
            self.assertEqual("COMPLETE", dynamic[0]["data_status"])

    def test_same_physical_sample_cannot_cross_splits(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for split in ("development", "validation"):
                directory = root / split / "sample_1" / "pos_1"
                directory.mkdir(parents=True)
                Image.new("L", (8, 6), 10).save(directory / f"{split}.bmp")
            manifest = build_manifest(root, "split-leak", "slot_pose", 2, "sample_1", "pos_1")
            report = validate_manifest(manifest, root)
            self.assertFalse(report["valid"])
            self.assertIn("SPLIT_LEAKAGE", {item["code"] for item in report["errors"]})

    def test_explicit_grouping_and_truth_must_match_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            image = root / "frame_001.bmp"
            Image.new("L", (8, 6), 10).save(image)
            grouping = {
                "frame_001.bmp": {
                    "sample_id": "physical_7", "condition_id": "angle_a", "repeat_index": "3",
                    "capture_sequence": "103", "capture_timestamp": "2026-08-14T01:02:03Z",
                    "split": "validation", "dataset_class": "normal",
                }
            }
            manifest = build_manifest(root, "explicit", "slot_pose", 1, "ignored", "ignored", grouping_records=grouping)
            item = manifest["images"][0]
            self.assertTrue(manifest["policy"]["groupingExplicit"])
            self.assertEqual("physical_7", item["sampleId"])
            self.assertEqual("angle_a", item["conditionId"])
            self.assertEqual(3, item["repeatIndex"])
            truth = [{
                "image_sha256": item["sha256"], "truth_valid": "true", "truth_angle_deg": "10",
                "truth_source": "indexer", "calibration_id": "cal-1", "sample": "physical_7",
                "condition": "wrong_condition", "repeat": "3", "split": "validation", "dataset_class": "normal",
            }]
            report = validate_manifest(manifest, root, truth_rows=truth)
            self.assertFalse(report["valid"])
            self.assertIn("TRUTH_GROUP_MISMATCH", {issue["code"] for issue in report["errors"]})

    def test_file_count_does_not_manufacture_twenty_frame_groups(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for index in range(2):
                Image.new("L", (8, 6), 10).save(root / f"frame_{index:03d}.bmp")
            manifest = build_manifest(root, "ungrouped", "slot_pose", 20, "unknown_sample", "unknown_condition")
            self.assertFalse(manifest["policy"]["groupingExplicit"])
            self.assertEqual([1, 2], [item["repeatIndex"] for item in manifest["images"]])
            report = validate_manifest(manifest, root)
            self.assertIn("REPEAT_COUNT", {issue["code"] for issue in report["errors"]})


if __name__ == "__main__":
    unittest.main()
