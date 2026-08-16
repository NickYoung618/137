import os
import json
import tempfile
import unittest
from pathlib import Path

import jsonschema

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
        image = asset_root / "Pic_2026_08_12_214449_1.bmp"
        annotation = asset_root / "端面标注样品.json"
        required = [image, annotation]
        if not all(path.is_file() for path in required):
            self.skipTest("external confirmed current-capture/reference assets are unavailable")

        with tempfile.TemporaryDirectory(prefix="hole2-current-e2e-") as tmp:
            result = run_current_capture(
                annotation,
                image,
                image,
                Path("config/current_capture_registration.v1.json"),
            )
            result_path = Path(tmp) / "result.json"
            write_result(result_path, result)
            result_schema = json.loads(Path(
                "specs/017-manual-measurement-template/contracts/current-capture-result-v2.schema.json"
            ).read_text(encoding="utf-8"))
            jsonschema.Draft202012Validator(result_schema).validate(result)

            self.assertEqual("complete", result["qualityStatus"]["state"], result)
            self.assertEqual(0, result["registration"]["selected"]["orientationDeg"])
            self.assertEqual({0}, {candidate["orientationDeg"] for candidate in result["registration"]["candidates"]})
            self.assertEqual(
                {"dx": 0.0, "dy": 0.0, "scale": 1.0, "thetaDeg": 0.0},
                result["registration"]["transform"],
            )
            inverse = result["registration"]["inverseTransform"]
            self.assertIsNotNone(inverse)
            self.assertTrue(result["features"]["7"]["measurementValid"])
            self.assertTrue(result["features"]["Phi12.2"]["measurementValid"])
            self.assertTrue(result["authoritativeReference"]["templateSelfCheck"])
            self.assertEqual(
                "authoritative_reference_px_to_target_px",
                result["authoritativeReference"]["transformDirection"],
            )
            d7_target = result["features"]["7"]["target"]
            phi_target = result["features"]["Phi12.2"]["target"]
            self.assertEqual(
                "perpendicular_distance", d7_target["measurementAnnotation"]["type"]
            )
            self.assertEqual(2, len(d7_target["fittedGeometry"]["boundaries"]))
            self.assertTrue(all(
                boundary["transitionPairsPx"]
                for boundary in d7_target["rawEdgeEvidence"]["boundaries"]
            ))
            self.assertFalse(phi_target["fittedGeometry"]["isDetectedContour"])
            self.assertEqual(
                {"reference_left"},
                {
                    segment["side"]
                    for segment in phi_target["rawEdgeEvidence"]["arcSegments"]
                },
            )
            self.assertTrue(result["features"]["Phi12.2"]["evidenceComplete"])
            self.assertEqual(
                "complete", result["features"]["Phi12.2"]["evidenceAuditStatus"]
            )
            self.assertEqual(
                "hole2-v6-current-capture-paired-transition-outer-contour-lines",
                result["features"]["7"]["sourceDetector"],
            )
            self.assertEqual(
                "hole2-v6-current-capture-reference-arc-with-opposite-arc-audit",
                result["features"]["Phi12.2"]["sourceDetector"],
            )
            self.assertEqual({
                "authoritative_reference_annotation", "authoritative_reference_image",
                "target_image", "configuration",
            }, {item["role"] for item in result["runtimeInputs"]})

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
