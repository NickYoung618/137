from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from algorithms.slot_pose.contract import ERROR_CODES, build_result, load_config, signed_relative_angle, validate_result


def minimal_config() -> dict:
    digest = "0" * 64
    return {
        "schema_version": "slot-pose-config/1", "project": "137-housing-slot-pose", "config_id": "test",
        "legacy_asset": {
            "source_path": "/read-only/main.py", "source_sha256": digest,
            "annotation_path": "/read-only/annotation.json", "annotation_sha256": digest,
            "reference_path": "/read-only/reference.bmp", "reference_sha256": digest,
        },
        "pose": {
            "reference_frame": "IMAGE", "target_frame": "MACHINE",
            "mechanical_zero_image_deg": 0.0, "positive_direction": "cw", "conventions_confirmed": True,
            "target_semantics_confirmed": True,
            "valid_range_deg": [-180, 179.999], "production_plc_mapping_confirmed": False,
        },
        "detector": {},
    }


class SlotPoseContractTests(unittest.TestCase):
    def test_failure_is_fail_closed_and_traceable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            image = root / "a_face.bmp"
            Image.new("L", (16, 12), 100).save(image)
            config_path = root / "config.json"
            config = minimal_config()
            config_path.write_text(json.dumps(config), encoding="utf-8")
            payload = build_result(
                image, config_path, config, "task-1", {"candidateAzimuthImageDeg": 42.0},
                error_code="POSE_CONVENTION_UNCONFIRMED", error_message="pending", error_stage="pose_mapping",
            )
            validate_result(payload)
            self.assertFalse(payload["result"]["valid"])
            self.assertIsNone(payload["result"]["signedRelativeRotationDeg"])
            self.assertIsNone(payload["result"]["confidence"])
            self.assertEqual("failed", payload["technicalStatus"])
            self.assertEqual("POSE_CONVENTION_UNCONFIRMED", payload["error"]["code"])
            self.assertIn("sourceSha256", payload["algorithm"]["assets"])
            self.assertNotIn("plc", payload)

    def test_valid_result_and_angle_sign(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            image = root / "a.png"
            Image.new("L", (8, 8), 1).save(image)
            config = minimal_config()
            config_path = root / "config.json"
            config_path.write_text(json.dumps(config), encoding="utf-8")
            payload = build_result(image, config_path, config, "task-2", {}, angle_deg=-30.0, confidence=0.8)
            validate_result(payload)
            self.assertTrue(payload["result"]["valid"])
            self.assertEqual(30.0, signed_relative_angle(30.0, 0.0, "cw"))
            self.assertEqual(-30.0, signed_relative_angle(30.0, 0.0, "ccw"))
            self.assertEqual(-2.0, signed_relative_angle(179.0, -179.0, "cw"))

    def test_invalid_payload_cannot_reuse_old_angle(self) -> None:
        with self.assertRaises(ValueError):
            validate_result({
                "schemaVersion": "slot-pose-result/2", "taskId": "x", "createdAtUtc": "now",
                "result": {"valid": False, "signedRelativeRotationDeg": 12.0, "confidence": None, "unit": "deg"},
                "technicalStatus": "failed", "error": {"code": "QUALITY_REJECTED", "stage": "q"},
            })

    def test_stable_failure_inventory(self) -> None:
        self.assertTrue({
            "INPUT_INVALID", "ASSET_MISMATCH", "FACE_NOT_FOUND", "SLOT_NOT_FOUND",
            "SLOT_ROTATION_INCONSISTENT", "QUALITY_REJECTED", "POSE_CONVENTION_UNCONFIRMED",
            "ANGLE_OUT_OF_RANGE",
            "SLOT_PAIR_NOT_FOUND", "SLOT_PAIR_AMBIGUOUS", "RING_TRUNCATED",
            "TARGET_SEMANTICS_UNCONFIRMED",
            "ROLE_ASSIGNMENT_FAILED", "ROLE_ASSIGNMENT_AMBIGUOUS",
            "GROOVE_RECOGNITION_FAILED", "GROOVE_RECOGNITION_AMBIGUOUS",
            "PHYSICAL_OUTER_CIRCLE_FAILED",
            "DATUM_DEFINITION_UNCONFIRMED", "FEATURE_MAPPING_UNCONFIRMED", "OUTPUT_PURPOSE_UNCONFIRMED",
        }.issubset(ERROR_CODES))

    def test_old_config_defaults_to_legacy_but_unconfirmed_target(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "config.json"
            config = minimal_config()
            config["pose"].pop("target_semantics_confirmed")
            path.write_text(json.dumps(config), encoding="utf-8")
            loaded = load_config(path)
            self.assertEqual("legacy_single_notch", loaded["detector"]["diagnostic_mode"])
            self.assertFalse(loaded["pose"]["target_semantics_confirmed"])

    def test_invalid_diagnostic_mode_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "config.json"
            config = minimal_config()
            config["detector"]["diagnostic_mode"] = "automatic_guess"
            path.write_text(json.dumps(config), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "diagnostic_mode"):
                load_config(path)

    def test_normalized_face_search_roi_is_optional_and_strictly_validated(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "config.json"
            config = minimal_config()
            config["detector"]["face_search_roi_normalized"] = [0.1, 0.0, 0.8, 1.0]
            path.write_text(json.dumps(config), encoding="utf-8")
            self.assertEqual([0.1, 0.0, 0.8, 1.0], load_config(path)["detector"]["face_search_roi_normalized"])
            for invalid in ([0.8, 0.0, 0.1, 1.0], [-0.1, 0.0, 0.8, 1.0], [0.0, 0.0, 1.1, 1.0]):
                config["detector"]["face_search_roi_normalized"] = invalid
                path.write_text(json.dumps(config), encoding="utf-8")
                with self.subTest(invalid=invalid), self.assertRaisesRegex(ValueError, "face_search_roi_normalized"):
                    load_config(path)

    def test_multi_role_config_gets_safe_groove_defaults_and_rejects_invalid_thresholds(self) -> None:
        from tools.generate_synthetic_multi_notches import build_dataset

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            try:
                built = build_dataset(root, 137)
            except FileNotFoundError as exc:
                self.skipTest(f"historical source unavailable: {exc}")
            path = Path(built["config"])
            config = json.loads(path.read_text(encoding="utf-8"))
            config["detector"].pop("groove_recognition", None)
            path.write_text(json.dumps(config), encoding="utf-8")
            loaded = load_config(path)
            self.assertEqual("groove-geometry-v1", loaded["detector"]["groove_recognition"]["threshold_version"])
            self.assertEqual(
                "gyj-outer-boundary+slot-quality-v2",
                loaded["detector"]["physical_outer_circle"]["threshold_version"],
            )
            config["detector"]["groove_recognition"] = {"min_radial_depth_ratio": 2.0}
            path.write_text(json.dumps(config), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "min_radial_depth_ratio"):
                load_config(path)
            config["detector"]["groove_recognition"] = {}
            config["detector"]["physical_outer_circle"] = {"min_angular_coverage": 2.0}
            path.write_text(json.dumps(config), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "min_angular_coverage"):
                load_config(path)

    def test_valid_result_requires_confirmed_target_semantics(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            image = root / "a.png"
            Image.new("L", (8, 8), 1).save(image)
            config = minimal_config()
            config["pose"]["target_semantics_confirmed"] = False
            config_path = root / "config.json"
            config_path.write_text(json.dumps(config), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "target semantics"):
                build_result(image, config_path, config, "task", {}, angle_deg=1.0, confidence=0.8)


if __name__ == "__main__":
    unittest.main()
