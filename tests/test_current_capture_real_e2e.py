import os
import tempfile
import unittest
from pathlib import Path

from algorithms.hole_2.current_capture import run_current_capture, write_result
from tools.evaluate_current_capture import evaluate_current_capture


IMAGE_SHA256 = "faf357c2e6e8e58d667f76a3d9ed4f4d51ab4d451c2661cf0efbc641405b2d8b"
ANNOTATION_SHA256 = "018e3449c051c15f7946315bd0d7f21cd79f4d4983efca0d11c7d98f02bfffa6"


class CurrentCaptureRealE2ETests(unittest.TestCase):
    def test_latest_truth_external_capture_detection_then_labelme_acceptance(self):
        asset_root = Path(os.environ.get(
            "HOLE2_CURRENT_E2E_DIR",
            "/home/ubuntu/disk/dzk/hole2-latest-truth-20260815",
        ))
        reference_root = Path(os.environ.get(
            "HOLE2_ASSET_DIR",
            "/home/ubuntu/disk/gyj/HousingInspectionDemo/algorithms/hole_2",
        ))
        image = asset_root / "Pic_2026_08_12_214449_1.bmp"
        annotation = asset_root / "端面标注样品.json"
        required = [image, annotation, reference_root / "annotation.json", reference_root / "reference.bmp"]
        if not all(path.is_file() for path in required):
            self.skipTest("external confirmed current-capture/reference assets are unavailable")

        with tempfile.TemporaryDirectory(prefix="hole2-current-e2e-") as tmp:
            result = run_current_capture(
                reference_root / "annotation.json",
                reference_root / "reference.bmp",
                image,
                Path("config/current_capture_registration.v1.json"),
            )
            result_path = Path(tmp) / "result.json"
            write_result(result_path, result)

            self.assertEqual("complete", result["qualityStatus"]["state"], result)
            self.assertEqual(270, result["registration"]["selected"]["orientationDeg"])
            self.assertEqual(
                {0, 90, 180, 270},
                {candidate["orientationDeg"] for candidate in result["registration"]["candidates"]},
            )
            inverse = result["registration"]["inverseTransform"]
            self.assertIsNotNone(inverse)
            self.assertTrue(result["features"]["7"]["measurementValid"])
            self.assertTrue(result["features"]["Phi12.2"]["measurementValid"])
            self.assertNotIn("target_annotation", {item["role"] for item in result["runtimeInputs"]})

            report = evaluate_current_capture(
                result_path, image, annotation, IMAGE_SHA256, ANNOTATION_SHA256
            )
            self.assertEqual("evaluated", report["status"])
            self.assertEqual(
                "complete", report["detectionSummary"]["qualityStatus"]["state"]
            )
            self.assertLessEqual(report["metrics"]["7"]["endpointMaxErrorPx"], 2.0)
            self.assertLessEqual(report["metrics"]["7"]["lengthAbsoluteErrorPx"], 2.0)
            self.assertLess(report["metrics"]["Phi12.2"]["centerErrorPx"], 3.0)
            self.assertLessEqual(report["metrics"]["Phi12.2"]["diameterAbsoluteErrorPx"], 1.0)
            self.assertLess(
                report["metrics"]["Phi12.2"]["truthPointToPredictedCircleResidualPx"]["p95"],
                3.0,
            )


if __name__ == "__main__":
    unittest.main()
