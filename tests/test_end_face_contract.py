from __future__ import annotations

import json
import math
import tempfile
import unittest
from pathlib import Path

from algorithms.end_face.contract import failure_result, json_safe, success_result, validate_result


class EndFaceContractTests(unittest.TestCase):
    def test_non_finite_values_are_strict_json_nulls(self) -> None:
        safe = json_safe({"nan": math.nan, "pos": math.inf, "neg": -math.inf, "ok": 1.25})
        self.assertEqual({"nan": None, "pos": None, "neg": None, "ok": 1.25}, safe)
        self.assertNotIn("NaN", json.dumps(safe, allow_nan=False))

    def test_invalid_quality_features_make_result_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            image = root / "target.bin"
            annotation = root / "annotation.json"
            reference = root / "reference.bin"
            image.write_bytes(b"image")
            annotation.write_text("{}", encoding="utf-8")
            reference.write_bytes(b"reference")
            payload = success_result(
                task_id="contract-test",
                image=image,
                annotation=annotation,
                reference=reference,
                pixel_size=1.0,
                shift_method="unit-test",
                measurements={"feature.quality.measurement_valid": 0.0, "feature.radius_px": math.nan},
            )
        self.assertFalse(payload["result"]["valid"])
        self.assertEqual(["feature"], payload["result"]["invalidFeatures"])
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


if __name__ == "__main__":
    unittest.main()
