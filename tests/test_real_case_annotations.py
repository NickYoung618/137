from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from tools.dataset_common import inspect_image, sha256_file
from tools.evaluate_annotated_real_cases import (
    _comparison_record,
    _render_comparison,
    annotation_eligibility,
    compute_static_repeatability,
)
from tools.prepare_real_case_annotations import prepare_annotations

try:
    import jsonschema
except ImportError:
    jsonschema = None


class RealCaseAnnotationPreparationTests(unittest.TestCase):
    def test_templates_are_path_safe_blank_and_never_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            data = root / "images"
            data.mkdir()
            image = data / "frame.jpg"
            Image.new("L", (64, 48), 100).save(image)
            manifest = {
                "datasetId": "real-set", "datasetFingerprint": "a" * 64,
                "images": [{
                    "imageId": "case:1", "relativePath": "frame.jpg", "split": "development",
                    **inspect_image(image),
                }],
            }
            output = root / "annotations"
            index = prepare_annotations(manifest, data, output)
            self.assertEqual(1, index["counts"]["pending"])
            entry = index["entries"][0]
            self.assertNotIn(str(root), json.dumps(index))
            annotation = output / entry["annotationRelativePath"]
            payload = json.loads(annotation.read_text(encoding="utf-8"))
            self.assertEqual([], payload["shapes"])
            self.assertIsNone(payload["imageData"])
            self.assertFalse(payload["flags"]["formal_truth"])
            payload["flags"]["manual_marker"] = "preserve-me"
            annotation.write_text(json.dumps(payload), encoding="utf-8")
            prepare_annotations(manifest, data, output)
            preserved = json.loads(annotation.read_text(encoding="utf-8"))
            self.assertEqual("preserve-me", preserved["flags"]["manual_marker"])

    @unittest.skipIf(jsonschema is None, "jsonschema is installed by the explicit Schema gate")
    def test_new_annotation_schemas_are_valid(self) -> None:
        root = Path(__file__).resolve().parents[1] / "contracts"
        for name in (
            "slot-pose-annotation.schema.json",
            "real-case-annotation-index.schema.json",
            "annotated-real-case-comparison.schema.json",
        ):
            with self.subTest(name=name):
                schema = json.loads((root / name).read_text(encoding="utf-8"))
                jsonschema.Draft202012Validator.check_schema(schema)


class RealCaseAnnotationEligibilityTests(unittest.TestCase):
    def _payload(self) -> dict:
        return {
            "version": "5.0.1", "imagePath": "frame.jpg", "imageData": None,
            "imageWidth": 100, "imageHeight": 80,
            "flags": {
                "human_verified": True, "independent_from_algorithm": True,
                "formal_truth": True, "runtime_input_allowed": False,
                "annotation_version": "reviewed-v1",
                "annotator": "operator-a", "reviewer": "reviewer-b",
            },
            "shapes": [
                {"label": "physical_outer_circle_truth", "shape_type": "circle",
                 "points": [[50.0, 40.0], [80.0, 40.0]], "flags": {}},
                {"label": "target_groove_open_boundary_manual", "shape_type": "linestrip",
                 "points": [[22.0, 50.0], [25.0, 55.0], [30.0, 60.0], [40.0, 63.0],
                            [35.0, 58.0], [24.0, 52.0]], "flags": {}},
            ],
        }

    def _entry(self) -> dict:
        return {
            "reviewStatus": "reviewed", "humanVerified": True,
            "independentFromAlgorithm": True, "annotator": "operator-a", "reviewer": "reviewer-b",
            "imageSha256": "1" * 64, "annotationSha256": "2" * 64,
        }

    def test_reviewed_variable_points_pass_basic_contract(self) -> None:
        self.assertEqual([], annotation_eligibility(
            self._payload(), self._entry(), actual_image_sha256="1" * 64,
            actual_annotation_sha256="2" * 64,
        ))

    def test_missing_draft_prefill_hash_and_bad_geometry_are_rejected(self) -> None:
        cases = []
        payload = self._payload(); payload["flags"]["human_verified"] = False
        cases.append((payload, self._entry(), "HUMAN_VERIFICATION_REQUIRED"))
        payload = self._payload(); payload["flags"]["independent_from_algorithm"] = False
        cases.append((payload, self._entry(), "INDEPENDENT_ANNOTATION_REQUIRED"))
        payload = self._payload(); payload["shapes"][0]["label"] = "algorithm_suggestion_circle"
        cases.append((payload, self._entry(), "PHYSICAL_CIRCLE_TRUTH_REQUIRED"))
        payload = self._payload(); payload["shapes"][1]["points"] = payload["shapes"][1]["points"][:5]
        cases.append((payload, self._entry(), "GROOVE_POINT_COUNT"))
        entry = self._entry(); entry["reviewStatus"] = "template"
        cases.append((self._payload(), entry, "REVIEW_STATUS_NOT_REVIEWED"))
        cases.append((self._payload(), self._entry(), "IMAGE_HASH_MISMATCH"))
        for index, (payload, entry, reason) in enumerate(cases):
            with self.subTest(index=index, reason=reason):
                image_hash = "0" * 64 if reason == "IMAGE_HASH_MISMATCH" else "1" * 64
                reasons = annotation_eligibility(
                    payload, entry, actual_image_sha256=image_hash,
                    actual_annotation_sha256="2" * 64,
                )
                self.assertIn(reason, reasons)

    def test_static_repeatability_uses_circular_residuals_and_explicit_groups(self) -> None:
        manifest = {
            "policy": {"groupingExplicit": True, "expectedRepeatsPerGroup": 3},
            "images": [
                {"imageId": f"i{index}", "sampleId": "part-a", "position": "p1",
                 "conditionId": "fixed", "split": "validation"}
                for index in range(3)
            ],
        }
        records = [
            {"imageId": "i0", "evaluationEligible": True, "difference": {"measuredAngleCircularDeg": 179.0}},
            {"imageId": "i1", "evaluationEligible": True, "difference": {"measuredAngleCircularDeg": -179.0}},
            {"imageId": "i2", "evaluationEligible": True, "difference": {"measuredAngleCircularDeg": 180.0}},
        ]
        result = compute_static_repeatability(manifest, records, configured_min_repeats=20)
        self.assertEqual("EVALUATED", result["status"])
        self.assertAlmostEqual(2.0, result["groups"][0]["residualCircularRangeDeg"])
        manifest["policy"]["groupingExplicit"] = False
        blocked = compute_static_repeatability(manifest, records, configured_min_repeats=20)
        self.assertEqual("NOT_EVALUATED", blocked["status"])
        self.assertEqual("GROUPING_NOT_EXPLICIT", blocked["reason"])

    def test_comparison_uses_circular_angle_delta_and_keeps_missing_detection_null(self) -> None:
        item = {"imageId": "i0", "relativePath": "frame.png", "sha256": "1" * 64}
        entry = {"annotationRelativePath": "cases/i0.json", "annotationSha256": "2" * 64}
        analysis = {
            "circle": {"refinedRobustGeometricCircle": {"centerX": 120.0, "centerY": 220.0, "radiusPx": 40.0}},
            "yDownTargetDiagnostic": {
                "datumMeasurement": {
                    "measuredFromPositiveYClockwiseDeg": 179.0,
                    "position": {"vertical": "lower", "horizontal": "left"},
                },
                "targetAssessment": {"toleranceStatus": "FAIL"},
            },
            "grooveRecognition": {"endpointAzimuthImageDeg": [170.0, -172.0]},
            "measurement": {"radialAxis": None},
        }
        detected = {
            "error": {"code": "PLC_MAPPING_UNCONFIRMED", "stage": "pose_mapping"},
            "diagnostics": {
                "physicalOuterCircle": {"physicalCircle": {"centerX": 360.0, "centerY": 220.0, "radiusPx": 40.0}},
                "singleGroovePose": {
                    "datumMeasurement": {
                        "measuredFromPositiveYClockwiseDeg": -179.0,
                        "position": {"vertical": "lower", "horizontal": "left"},
                    },
                    "targetAssessment": {"toleranceStatus": "FAIL"},
                },
                "grooveRefinement": {"outerCircleIntersections": []},
            },
        }
        compared = _comparison_record(item, entry, detected, analysis)
        self.assertAlmostEqual(2.0, compared["difference"]["measuredAngleCircularDeg"])
        self.assertEqual("lower_left", compared["human"]["quadrant"])
        self.assertEqual("lower_left", compared["automatic"]["quadrant"])

        missing = _comparison_record(item, entry, {"diagnostics": {}}, analysis)
        self.assertIsNone(missing["difference"]["measuredAngleCircularDeg"])
        self.assertIsNone(missing["difference"]["centerDistancePx"])

    def test_comparison_overlay_separates_human_green_and_automatic_cyan(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            image_path = root / "frame.png"
            output_path = root / "comparison.png"
            Image.new("RGB", (500, 400), "black").save(image_path)
            record = {
                "imageId": "i0",
                "human": {
                    "circle": {"centerX": 120.0, "centerY": 220.0, "radiusPx": 40.0},
                    "measuredYDownDeg": 85.0, "radialAxis": None,
                    "grooveBoundaryPoints": [],
                },
                "automatic": {
                    "circle": {"centerX": 360.0, "centerY": 220.0, "radiusPx": 40.0},
                    "measuredYDownDeg": 84.8, "radialAxis": None,
                    "openingIntersections": [],
                },
                "difference": {
                    "centerDistancePx": 240.0, "radiusSignedPx": 0.0,
                    "measuredAngleCircularDeg": -0.2,
                },
            }
            _render_comparison(image_path, record, output_path)
            with Image.open(output_path) as rendered:
                self.assertEqual((56, 214, 107), rendered.getpixel((160, 220)))
                self.assertEqual((53, 199, 255), rendered.getpixel((400, 220)))


if __name__ == "__main__":
    unittest.main()
