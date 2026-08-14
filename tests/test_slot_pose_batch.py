from __future__ import annotations

import json
import csv
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from tests.test_slot_pose_contract import minimal_config
from tools.dataset_common import sha256_file
from tools.generate_synthetic_paired_notches import build_dataset
from tools.run_a2_acceptance import run_acceptance
from tools.run_slot_pose_batch import run_batch


class SlotPoseBatchTests(unittest.TestCase):
    def test_missing_image_does_not_interrupt_following_tasks(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            build_dataset(root, 137)
            manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
            valid_item = next(item for item in manifest["images"] if item["conditionId"] == "normal_base")
            missing = dict(valid_item)
            missing["imageId"] = "missing-image"
            missing["relativePath"] = "development/sample_paired/missing.png"
            manifest["images"] = [missing, valid_item]
            payloads = run_batch(manifest, root / "images", root / "config.json")
            self.assertEqual(2, len(payloads))
            self.assertEqual("INPUT_INVALID", payloads[0]["error"]["code"])
            self.assertFalse(payloads[0]["result"]["valid"])
            self.assertTrue(payloads[1]["result"]["valid"], payloads[1])
            self.assertNotEqual(payloads[0]["taskId"], payloads[1]["taskId"])

    def test_one_click_workflow_writes_separate_normal_and_bad_reports(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            normal_root = root / "normal"
            bad_root = root / "bad"
            normal_root.mkdir()
            bad_root.mkdir()
            normal_image = normal_root / "normal.bmp"
            bad_image = bad_root / "bad.bmp"
            Image.new("L", (16, 12), 100).save(normal_image)
            Image.new("L", (16, 12), 0).save(bad_image)
            grouping_path = root / "grouping.csv"
            grouping_rows = [
                {"relative_path": "normal.bmp", "dataset_class": "normal", "sample_id": "s1", "condition_id": "c1", "repeat_index": "1", "capture_timestamp": "", "capture_sequence": "1", "split": "development"},
                {"relative_path": "bad.bmp", "dataset_class": "bad", "sample_id": "b1", "condition_id": "bad", "repeat_index": "1", "capture_timestamp": "", "capture_sequence": "2", "split": "development"},
            ]
            with grouping_path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(grouping_rows[0]))
                writer.writeheader()
                writer.writerows(grouping_rows)
            truth_path = root / "truth.csv"
            truth_rows = [
                {"image_sha256": sha256_file(normal_image), "truth_valid": "true", "truth_angle_deg": "0", "truth_source": "fixture", "calibration_id": "fixture", "sample": "s1", "condition": "c1", "repeat": "1", "split": "development", "dataset_class": "normal"},
                {"image_sha256": sha256_file(bad_image), "truth_valid": "false", "truth_angle_deg": "", "truth_source": "fixture", "calibration_id": "fixture", "sample": "b1", "condition": "bad", "repeat": "1", "split": "development", "dataset_class": "bad"},
            ]
            with truth_path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(truth_rows[0]))
                writer.writeheader()
                writer.writerows(truth_rows)
            config_path = root / "config.json"
            config_path.write_text(json.dumps(minimal_config()), encoding="utf-8")
            output = root / "reports"
            result = run_acceptance(normal_root, bad_root, grouping_path, truth_path, config_path, output, 1, 1)
            self.assertEqual(1, result["normalImages"])
            self.assertEqual(1, result["badImages"])
            self.assertTrue((output / "normal-report.json").is_file())
            self.assertTrue((output / "bad-report.json").is_file())
            bad_report = json.loads((output / "bad-report.json").read_text(encoding="utf-8"))
            self.assertEqual(0, bad_report["falsePositiveCount"])


if __name__ == "__main__":
    unittest.main()
