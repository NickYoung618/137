from __future__ import annotations

import json
import math
import tempfile
import unittest
from pathlib import Path

from algorithms.end_face.contract import failure_result, json_safe, success_result, validate_result
from algorithms.end_face.quality import evaluate_quality, load_quality_policy


ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "config/end_face_quality.example.json"


class EndFaceContractTests(unittest.TestCase):
    def test_non_finite_values_are_strict_json_nulls(self) -> None:
        safe = json_safe({"nan": math.nan, "pos": math.inf, "neg": -math.inf, "ok": 1.25})
        self.assertEqual({"nan": None, "pos": None, "neg": None, "ok": 1.25}, safe)
        self.assertNotIn("NaN", json.dumps(safe, allow_nan=False))

    def test_invalid_feature_is_preserved_without_invalidating_localization(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            image = root / "target.bin"
            annotation = root / "annotation.json"
            reference = root / "reference.bin"
            image.write_bytes(b"image")
            annotation.write_text("{}", encoding="utf-8")
            reference.write_bytes(b"reference")
            measurements = {
                "transform.target_center_x_px": 4.0,
                "transform.target_center_y_px": 3.0,
                "transform.scale": 1.0,
                "transform.rotation_deg": 0.0,
                "feature.detect.source": "test_fallback",
                "feature.quality.measurement_valid": 0.0,
                "feature.quality.anomaly_reason": "test_invalid",
                "feature.radius_px": math.nan,
            }
            quality = evaluate_quality(
                measurements,
                "circle-alignment rotation_score=10.0, notch_check(Δ=0deg, prom=20.0)",
                (8, 6),
                load_quality_policy(POLICY_PATH),
                POLICY_PATH,
            )
            payload = success_result(
                task_id="contract-test",
                image=image,
                image_info={"bytes": 5, "sha256": "0" * 64, "format": "BIN", "width": 8, "height": 6, "mode": "L"},
                annotation=annotation,
                reference=reference,
                pixel_size=1.0,
                shift_method="circle-alignment rotation_score=10.0, notch_check(Δ=0deg, prom=20.0)",
                measurements=measurements,
                quality=quality,
                elapsed_ms=1.25,
            )
        self.assertTrue(payload["result"]["valid"])
        self.assertFalse(payload["result"]["measurementCompleteness"]["allValid"])
        self.assertFalse(payload["result"]["featureQuality"]["feature"]["coreValid"])
        self.assertIsNone(payload["result"]["measurements"]["feature.radius_px"])
        validate_result(payload)

    def test_failure_has_no_measurements(self) -> None:
        payload = failure_result(
            task_id="failed-test",
            image=Path("missing.bmp"),
            annotation=Path("missing.json"),
            error=ValueError("bad annotation"),
        )
        self.assertEqual("failed", payload["technicalStatus"])
        self.assertIsNone(payload["result"])
        self.assertEqual("DETECTION_FAILED", payload["error"]["code"])

    def test_v3_candidate_transition_cannot_contradict_independent_states(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            image = root / "target.bin"
            annotation = root / "annotation.json"
            reference = root / "reference.bin"
            image.write_bytes(b"image")
            annotation.write_text("{}", encoding="utf-8")
            reference.write_bytes(b"reference")
            measurements = {
                "transform.target_center_x_px": 4.0,
                "transform.target_center_y_px": 3.0,
                "transform.scale": 1.0,
                "transform.rotation_deg": 0.0,
            }
            quality = evaluate_quality(
                measurements,
                "circle-alignment rotation_score=10.0, notch_check(Δ=0deg, prom=20.0)",
                (8, 6),
                load_quality_policy(POLICY_PATH),
                POLICY_PATH,
            )
            payload = success_result(
                task_id="candidate-transition",
                image=image,
                image_info={"bytes": 5, "sha256": "0" * 64, "format": "BIN", "width": 8, "height": 6, "mode": "L"},
                annotation=annotation,
                reference=reference,
                pixel_size=1.0,
                shift_method="circle-alignment rotation_score=10.0, notch_check(Δ=0deg, prom=20.0)",
                measurements=measurements,
                quality=quality,
                short_line_candidates={
                    "19��": {
                        "feature": "19��",
                        "core": {"coreValid": False},
                        "candidate": {"candidateValid": True},
                        "transition": "recovered",
                    }
                },
                elapsed_ms=1.0,
            )
        validate_result(payload)
        payload["result"]["shortLineCandidates"]["19��"]["transition"] = "both_invalid"
        with self.assertRaises(ValueError):
            validate_result(payload)


if __name__ == "__main__":
    unittest.main()
