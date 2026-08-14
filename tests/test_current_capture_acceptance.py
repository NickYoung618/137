import hashlib
import json
import math
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from tools.evaluate_current_capture import evaluate_current_capture


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _truth(radius=25.0):
    points = [
        [80.0 + radius * math.cos(a), 70.0 + radius * math.sin(a)]
        for a in [2.0 * math.pi * i / 77 for i in range(77)]
    ]
    return {
        "imagePath": "target.bmp",
        "shapes": [
            {"label": "7", "shape_type": "line", "points": [[20.0, 30.0], [70.0, 30.0]]},
            {"label": "Φ12.2", "shape_type": "linestrip", "points": points},
        ],
    }


def _result(target_sha: str):
    return {
        "schemaVersion": "hole2-current-capture-result/1",
        "algorithmVersion": "test/1",
        "configVersion": "test-v1",
        "runtimeInputs": [
            {"role": "reference_annotation", "path": "old.json", "sha256": "1" * 64},
            {"role": "reference_image", "path": "old.bmp", "sha256": "2" * 64},
            {"role": "target_image", "path": "target.bmp", "sha256": target_sha},
            {"role": "configuration", "path": "config.json", "sha256": "3" * 64},
        ],
        "registration": {
            "registrationValid": True, "failureReason": None,
            "primaryFailureReason": None, "registrationRecoveryPass": None,
            "candidates": [
                {"orientationDeg": value, "score": 10.0 if value == 270 else 1.0,
                 "valid": value == 270, "failureReasons": [] if value == 270 else ["support_count_below_gate"],
                 "supportCount": 6 if value == 270 else 1, "spatialCoverage": 1.0 if value == 270 else 0.0,
                 "medianResidualPx": 1.0 if value == 270 else None,
                 "maxResidualPx": 2.0 if value == 270 else None}
                for value in (0, 90, 180, 270)
            ],
            "selected": {"orientationDeg": 270, "score": 10.0},
            "transform": {"dx": 0.0, "dy": 0.0, "scale": 1.0, "thetaDeg": 0.0},
            "inverseTransform": {"dx": 0.0, "dy": 0.0, "scale": 1.0, "thetaDeg": 0.0},
            "transformDirection": "reference_px_to_target_px",
            "inverseTransformDirection": "target_px_to_reference_px",
            "referenceImageSize": [160, 140], "targetImageSize": [160, 140],
        },
        "features": {
            "7": {
                "featureCode": "HOLE2-DIM-7", "measurementValid": True,
                "qualityStatus": "valid",
                "failureReason": None, "sourceDetector": "test", "recoveryPass": None,
                "reference": {},
                "target": {"pointsPx": [[70.0, 30.0], [20.0, 30.0]], "lengthPx": 50.0},
                "quality": {},
            },
            "Phi12.2": {
                "featureCode": "HOLE2-DIA-12_2", "measurementValid": True,
                "qualityStatus": "valid",
                "failureReason": None, "sourceDetector": "test", "recoveryPass": None,
                "reference": {},
                "target": {"centerPx": [80.0, 70.0], "radiusPx": 25.0, "diameterPx": 50.0},
                "quality": {},
            },
        },
        "referenceMeasurements": {}, "v6Measurements": {},
        "qualityStatus": {
            "technicalValid": True, "state": "complete",
            "failureReasons": [], "productionDisposition": "not_evaluated",
        },
        "geometryConsistency": {
            "evaluated": True, "rejected": False, "failureReason": None,
            "ratioSource": "old_reference_annotation_geometry",
            "referenceRatio": 1.0, "targetRatio": 1.0,
            "absoluteDeviation": 0.0, "maximumAbsoluteDeviation": 0.08,
            "outputAdjustmentApplied": False,
        },
        "timingMs": {"total": 1.0},
        "evidenceScope": "single_image_pixel_geometry_only_not_repeatability_mm_accuracy_or_production_ok_ng",
        "errors": [],
    }


class CurrentCaptureAcceptanceTests(unittest.TestCase):
    def _assets(self, root: Path):
        image_path = root / "target.bmp"
        Image.new("L", (160, 140), 100).save(image_path)
        truth_path = root / "target.json"
        truth_path.write_text(json.dumps(_truth()), encoding="utf-8")
        result_path = root / "result.json"
        result_path.write_text(json.dumps(_result(_sha(image_path))), encoding="utf-8")
        return image_path, truth_path, result_path

    def test_exact_geometry_reports_zero_unordered_endpoint_and_circle_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            image_path, truth_path, result_path = self._assets(Path(tmp))
            report = evaluate_current_capture(
                result_path, image_path, truth_path, _sha(image_path), _sha(truth_path)
            )
            self.assertEqual("evaluated", report["status"])
            self.assertAlmostEqual(0.0, report["metrics"]["7"]["endpointMeanErrorPx"], places=6)
            self.assertAlmostEqual(0.0, report["metrics"]["7"]["lengthAbsoluteErrorPx"], places=6)
            self.assertAlmostEqual(0.0, report["metrics"]["Phi12.2"]["centerErrorPx"], places=6)
            self.assertAlmostEqual(0.0, report["metrics"]["Phi12.2"]["diameterAbsoluteErrorPx"], places=6)
            summary = report["detectionSummary"]
            self.assertEqual(270, summary["registration"]["selectedOrientationDeg"])
            self.assertEqual("complete", summary["qualityStatus"]["state"])
            self.assertEqual(4, len(summary["registration"]["candidates"]))
            self.assertEqual("support_count_below_gate", summary["registration"]["candidates"][0]["failureReasons"][0])
            self.assertEqual("test/1", summary["algorithmVersion"])
            self.assertNotIn("pass", json.dumps(report).lower())

    def test_hash_mismatch_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            image_path, truth_path, result_path = self._assets(Path(tmp))
            with self.assertRaisesRegex(ValueError, "image SHA-256"):
                evaluate_current_capture(result_path, image_path, truth_path, "0" * 64, _sha(truth_path))

    def test_truth_shape_type_and_point_count_are_strict(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            image_path, truth_path, result_path = self._assets(root)
            truth = _truth()
            truth["shapes"][1]["points"] = truth["shapes"][1]["points"][:-1]
            truth_path.write_text(json.dumps(truth), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "77 points"):
                evaluate_current_capture(result_path, image_path, truth_path, _sha(image_path), _sha(truth_path))

    def test_runtime_truth_leakage_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            image_path, truth_path, result_path = self._assets(root)
            result = json.loads(result_path.read_text(encoding="utf-8"))
            result["runtimeInputs"][0]["path"] = str(truth_path)
            result_path.write_text(json.dumps(result), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "target annotation leaked"):
                evaluate_current_capture(result_path, image_path, truth_path, _sha(image_path), _sha(truth_path))


if __name__ == "__main__":
    unittest.main()
