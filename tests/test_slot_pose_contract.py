from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from algorithms.slot_pose.contract import ERROR_CODES, build_result, signed_relative_angle, validate_result


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
        }.issubset(ERROR_CODES))


if __name__ == "__main__":
    unittest.main()
