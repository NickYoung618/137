from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from algorithms.slot_pose.main import run
from tools.generate_synthetic_slot_pose import DEFAULT_SOURCE, build_dataset


ROOT = Path(__file__).resolve().parents[1]


class SlotPoseCliTests(unittest.TestCase):
    def test_default_reference_is_diagnostic_only(self) -> None:
        config = ROOT / "config/inspection.example.json"
        image = Path(json.loads(config.read_text(encoding="utf-8"))["legacy_asset"]["reference_path"])
        if not image.is_file():
            self.skipTest(f"server historical reference is unavailable on this host: {image}")
        payload = run(image, config, "reference-fail-closed-test")
        self.assertFalse(payload["result"]["valid"])
        self.assertIsNone(payload["result"]["signedRelativeRotationDeg"])
        self.assertEqual("TARGET_SEMANTICS_UNCONFIRMED", payload["error"]["code"])
        self.assertAlmostEqual(247.2167307, payload["diagnostics"]["referenceNotch"]["azimuthImageDeg"], places=3)

    def test_strict_unconfirmed_and_invalid_config_exit_codes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            if not DEFAULT_SOURCE.is_file():
                self.skipTest(f"historical source unavailable: {DEFAULT_SOURCE}")
            build_dataset(root, [0.0], 1, 137, DEFAULT_SOURCE)
            image = root / "synthetic/sample_synthetic/angle_pos_000p00/repeat_001.png"
            config = json.loads((root / "synthetic-config.json").read_text(encoding="utf-8"))
            config["pose"]["target_semantics_confirmed"] = False
            unconfirmed = root / "unconfirmed.json"
            unconfirmed.write_text(json.dumps(config), encoding="utf-8")
            command = [
                sys.executable, str(ROOT / "algorithms/slot_pose/main.py"), "--image", str(image),
                "--config", str(unconfirmed), "--strict",
            ]
            completed = subprocess.run(command, check=False, capture_output=True, text=True)
            self.assertEqual(1, completed.returncode, completed.stderr)
            payload = json.loads(completed.stdout)
            self.assertEqual("TARGET_SEMANTICS_UNCONFIRMED", payload["error"]["code"])
            config["detector"]["diagnostic_mode"] = "automatic_guess"
            invalid = root / "invalid.json"
            invalid.write_text(json.dumps(config), encoding="utf-8")
            command[command.index(str(unconfirmed))] = str(invalid)
            completed = subprocess.run(command, check=False, capture_output=True, text=True)
            self.assertEqual(2, completed.returncode)
            self.assertIn("diagnostic_mode", completed.stderr)


if __name__ == "__main__":
    unittest.main()
