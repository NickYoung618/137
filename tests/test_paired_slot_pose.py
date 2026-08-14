from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from algorithms.slot_pose.main import run
from tools.generate_synthetic_paired_notches import build_dataset


class PairedSlotPoseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temporary.name)
        try:
            build_dataset(cls.root, 137)
        except FileNotFoundError as exc:
            cls.temporary.cleanup()
            raise unittest.SkipTest(f"historical source unavailable: {exc}") from exc
        cls.config = cls.root / "config.json"
        cls.images = cls.root / "images/development/sample_paired"
        with (cls.root / "ground_truth.csv").open(newline="", encoding="utf-8") as handle:
            cls.truth = {row["condition"]: row for row in csv.DictReader(handle)}

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temporary.cleanup()

    def _run_case(self, case_id: str) -> dict:
        return run(self.images / case_id / "repeat_001.png", self.config, f"paired:{case_id}")

    def test_controlled_positive_variants_match_centerline_truth(self) -> None:
        for case_id in ("normal_base", "normal_translate", "normal_scale_bright", "normal_wrap_pos", "normal_wrap_neg"):
            with self.subTest(case_id=case_id):
                payload = self._run_case(case_id)
                self.assertTrue(payload["result"]["valid"], payload)
                truth = float(self.truth[case_id]["truth_angle_deg"])
                error = (payload["result"]["signedRelativeRotationDeg"] - truth + 180.0) % 360.0 - 180.0
                self.assertLessEqual(abs(error), 1.0, payload)
                self.assertEqual("paired_notches_centerline", payload["diagnostics"]["diagnosticMode"])
                self.assertEqual(2, payload["diagnostics"]["candidateSummary"]["count"])
                self.assertTrue(payload["diagnostics"]["pairing"]["unique"])

    def test_missing_notch_and_ambiguous_pair_fail_closed(self) -> None:
        expected = {"bad_missing_notch": "SLOT_PAIR_NOT_FOUND", "bad_ambiguous": "SLOT_PAIR_AMBIGUOUS"}
        for case_id, error_code in expected.items():
            with self.subTest(case_id=case_id):
                payload = self._run_case(case_id)
                self.assertFalse(payload["result"]["valid"])
                self.assertIsNone(payload["result"]["signedRelativeRotationDeg"])
                self.assertEqual(error_code, payload["error"]["code"], payload)

    def test_cropped_ring_fails_closed(self) -> None:
        payload = self._run_case("bad_cropped")
        self.assertFalse(payload["result"]["valid"])
        self.assertIsNone(payload["result"]["signedRelativeRotationDeg"])
        self.assertIn(payload["error"]["code"], {"FACE_NOT_FOUND", "RING_TRUNCATED"})

    def test_unconfirmed_target_semantics_never_returns_machine_angle(self) -> None:
        config = json.loads(self.config.read_text(encoding="utf-8"))
        config["pose"]["target_semantics_confirmed"] = False
        path = self.root / "unconfirmed-config.json"
        path.write_text(json.dumps(config), encoding="utf-8")
        payload = run(self.images / "normal_base/repeat_001.png", path, "paired:unconfirmed")
        self.assertFalse(payload["result"]["valid"])
        self.assertIsNone(payload["result"]["signedRelativeRotationDeg"])
        self.assertEqual("TARGET_SEMANTICS_UNCONFIRMED", payload["error"]["code"])
        self.assertTrue(payload["diagnostics"]["pairing"]["unique"])


if __name__ == "__main__":
    unittest.main()
