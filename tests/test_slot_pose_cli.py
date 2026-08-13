from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from algorithms.slot_pose.main import run


ROOT = Path(__file__).resolve().parents[1]


class SlotPoseCliTests(unittest.TestCase):
    def test_default_reference_is_diagnostic_only(self) -> None:
        config = ROOT / "config/inspection.example.json"
        image = Path(json.loads(config.read_text(encoding="utf-8"))["legacy_asset"]["reference_path"])
        payload = run(image, config, "reference-fail-closed-test")
        self.assertFalse(payload["result"]["valid"])
        self.assertIsNone(payload["result"]["signedRelativeRotationDeg"])
        self.assertEqual("POSE_CONVENTION_UNCONFIRMED", payload["error"]["code"])
        self.assertAlmostEqual(247.2167307, payload["diagnostics"]["referenceNotch"]["azimuthImageDeg"], places=3)


if __name__ == "__main__":
    unittest.main()
