from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from algorithms.slot_pose.main import run
from algorithms.slot_pose.groove_refinement import DEFAULT_GROOVE_REFINEMENT_CONFIG
from algorithms.slot_pose.single_groove_pose import DEFAULT_SINGLE_GROOVE_POSE_CONFIG_V3
from tools.dataset_common import sha256_file
from tools.generate_synthetic_multi_notches import build_dataset as build_multi_dataset
from tools.generate_synthetic_paired_notches import make_paired_face
from tools.generate_synthetic_slot_pose import DEFAULT_SOURCE, build_dataset


ROOT = Path(__file__).resolve().parents[1]


class SlotPoseCliTests(unittest.TestCase):
    def test_v3_strict_cli_succeeds_when_image_guidance_is_valid_but_plc_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            try:
                built = build_multi_dataset(root, 137)
            except FileNotFoundError as exc:
                self.skipTest(f"historical source unavailable: {exc}")
            config_path = Path(built["config"])
            config = json.loads(config_path.read_text(encoding="utf-8"))
            reference = root / "reference.png"
            image = root / "closed-loop.png"
            make_paired_face(0.0, 901, notch_centers=[300.0], shadow_centers=[80.0, 170.0], noise=0.0).save(reference)
            make_paired_face(0.0, 902, notch_centers=[300.0], shadow_centers=[80.0, 170.0], noise=0.8).save(image)
            config["legacy_asset"]["reference_sha256"] = sha256_file(reference)
            config["detector"]["diagnostic_mode"] = "single_real_groove"
            config["detector"]["single_groove_pose"] = DEFAULT_SINGLE_GROOVE_POSE_CONFIG_V3
            config["detector"]["groove_refinement"] = {
                **DEFAULT_GROOVE_REFINEMENT_CONFIG,
                "threshold_version": "groove-sidewall-subpixel-v2",
            }
            config["pose"].update({
                "target_semantics_confirmed": True,
                "conventions_confirmed": False,
                "mechanical_zero_image_deg": None,
                "positive_direction": None,
                "production_plc_mapping_confirmed": False,
            })
            config_path.write_text(json.dumps(config), encoding="utf-8")
            completed = subprocess.run([
                sys.executable, str(ROOT / "algorithms/slot_pose/main.py"),
                "--image", str(image), "--config", str(config_path), "--strict",
            ], check=False, capture_output=True, text=True)
            self.assertEqual(0, completed.returncode, completed.stderr)
            payload = json.loads(completed.stdout)
            self.assertTrue(payload["result"]["valid"])
            self.assertEqual("DETECTED", payload["result"]["detectionStatus"])
            self.assertIsNotNone(payload["result"]["imageFrameCorrectionDeg"])
            self.assertEqual("BLOCKED_MAPPING_UNCONFIRMED", payload["result"]["plcExecutionStatus"])
            self.assertIsNone(payload["result"]["plcCommand"])

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
