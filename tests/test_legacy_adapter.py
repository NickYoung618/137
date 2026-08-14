from __future__ import annotations

import copy
import json
import math
import time
import unittest
from pathlib import Path

import numpy as np

from algorithms.slot_pose.contract import load_config, sha256_file
from algorithms.slot_pose.legacy_adapter import (
    LegacyAEndFaceAdapter,
    LegacyAdapterError,
    REQUIRED_FUNCTIONS,
    apply_normalized_face_search_roi,
)


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/inspection.example.json"


class LegacyAdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = load_config(CONFIG)
        missing = [
            cls.config["legacy_asset"][key]
            for key in ("source_path", "annotation_path", "reference_path")
            if not Path(cls.config["legacy_asset"][key]).is_file()
        ]
        if missing:
            raise unittest.SkipTest(f"server historical assets are unavailable on this host: {missing}")

    def test_asset_hash_mismatch_fails_before_import(self) -> None:
        config = copy.deepcopy(self.config)
        config["legacy_asset"]["source_sha256"] = "0" * 64
        with self.assertRaises(LegacyAdapterError) as caught:
            LegacyAEndFaceAdapter(config)
        self.assertEqual("ASSET_MISMATCH", caught.exception.code)

    def test_normalized_face_search_roi_masks_only_alignment_input(self) -> None:
        image = np.arange(80, dtype=np.uint8).reshape(8, 10)
        masked = apply_normalized_face_search_roi(image, [0.2, 0.25, 0.8, 0.75])
        np.testing.assert_array_equal(masked[2:6, 2:8], image[2:6, 2:8])
        self.assertEqual(0, int(masked[:2].sum()))
        self.assertEqual(0, int(masked[:, :2].sum()))
        self.assertEqual(0, int(masked[6:].sum()))
        self.assertEqual(0, int(masked[:, 8:].sum()))
        self.assertGreater(int(image.sum()), int(masked.sum()))

    def test_reference_baseline_and_source_remains_unchanged(self) -> None:
        source = Path(self.config["legacy_asset"]["source_path"])
        before = sha256_file(source)
        adapter = LegacyAEndFaceAdapter(self.config)
        started = time.perf_counter()
        output = adapter.estimate(Path(self.config["legacy_asset"]["reference_path"]))
        elapsed = time.perf_counter() - started
        after = sha256_file(source)
        self.assertEqual(before, after)
        self.assertEqual(list(REQUIRED_FUNCTIONS), output["diagnostics"]["functionInventory"])
        slot = output["diagnostics"]["slot"]
        self.assertAlmostEqual(247.2167307, output["diagnostics"]["referenceNotch"]["azimuthImageDeg"], places=3)
        self.assertAlmostEqual(247.0943426, output["candidate_image_deg"], places=3)
        self.assertAlmostEqual(0.0, slot["polarRotationDeg"], delta=0.2)
        self.assertAlmostEqual(0.0, slot["notchRotationDeg"], delta=0.2)
        self.assertGreater(slot["prominence"], 100.0)
        self.assertLess(elapsed, 8.0)

    def test_existing_quality_outputs_drive_fail_closed_gate(self) -> None:
        config = copy.deepcopy(self.config)
        config["detector"]["min_notch_prominence"] = 1000.0
        adapter = LegacyAEndFaceAdapter(config)
        with self.assertRaises(LegacyAdapterError) as caught:
            adapter.estimate(Path(config["legacy_asset"]["reference_path"]))
        self.assertEqual("QUALITY_REJECTED", caught.exception.code)
        self.assertIn("notch_prominence", caught.exception.diagnostics["quality"]["failedChecks"])


if __name__ == "__main__":
    unittest.main()
