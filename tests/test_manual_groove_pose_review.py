from __future__ import annotations

import json
import math
import base64
import io
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from tools.review_labelme_groove_pose import (
    DEFAULT_REVIEW_CONFIG,
    analyze_manual_groove_geometry,
    assess_target,
    review_labelme_groove_pose,
)

try:
    import jsonschema
except ImportError:
    jsonschema = None


ROOT = Path(__file__).resolve().parents[1]


def _point(center, radius, heading_deg):
    angle = math.radians(heading_deg)
    return [center[0] + radius * math.sin(angle), center[1] - radius * math.cos(angle)]


def _arc(center=(250.0, 250.0), radius=180.0, count=73):
    return [_point(center, radius, -120.0 + 240.0 * index / (count - 1)) for index in range(count)]


def _boundary(center=(250.0, 250.0), radius=180.0, start=350.0, end=10.0, count=11, depth=45.0):
    delta = (end - start + 180.0) % 360.0 - 180.0
    points = []
    for index in range(count):
        fraction = index / (count - 1)
        heading = (start + delta * fraction) % 360.0
        local_radius = radius - depth * math.sin(math.pi * fraction)
        points.append(_point(center, local_radius, heading))
    return points


def _fit_circle(points):
    values = np.asarray(points, dtype=float)
    x, y = values[:, 0], values[:, 1]
    matrix = np.column_stack((x, y, np.ones(len(values))))
    target = -(x * x + y * y)
    d, e, f = np.linalg.lstsq(matrix, target, rcond=None)[0]
    center_x, center_y = -d / 2.0, -e / 2.0
    return float(center_x), float(center_y), math.sqrt(max(0.0, center_x * center_x + center_y * center_y - f))


def _robust_fit(points, fallback):
    return _fit_circle(points)


def _target(*, confirmed=False, expected_quadrant="lower_left"):
    return {
        "schemaVersion": "slot-groove-target/1",
        "nominalDeg": 85.0,
        "expectedQuadrant": expected_quadrant,
        "physicalDatumDefinitionId": "fixture-datum-v1" if confirmed else None,
        "angleConventionId": "image-up-clockwise-v1" if confirmed else None,
    }


class ManualGrooveGeometryTests(unittest.TestCase):
    def _analyze(self, circle=None, groove=None, target=None):
        return analyze_manual_groove_geometry(
            circle or _arc(), groove or _boundary(), _fit_circle, _robust_fit,
            DEFAULT_REVIEW_CONFIG, target or _target(), circle_fit_source_sha256="a" * 64,
        )

    def test_variable_point_counts_are_valid_without_fixed_77_or_34(self):
        result = self._analyze(_arc(count=61), _boundary(count=9))
        self.assertEqual("accepted", result["grooveRecognition"]["status"])
        self.assertEqual(61, result["circle"]["pointCount"])
        self.assertEqual(9, result["grooveRecognition"]["pointCount"])
        self.assertAlmostEqual(0.0, result["measurement"]["openingCenterAzimuthImageDeg"], places=6)
        self.assertEqual("upper_axis", result["measurement"]["quadrant"])

    def test_fewer_points_and_nonfinite_coordinates_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "at least 8 finite points"):
            self._analyze(_arc(count=7), _boundary())
        with self.assertRaisesRegex(ValueError, "at least 6 finite points"):
            self._analyze(_arc(), _boundary(count=5))
        groove = _boundary()
        groove[3][0] = float("nan")
        with self.assertRaisesRegex(ValueError, "finite points"):
            self._analyze(_arc(), groove)

    def test_endpoint_reversal_preserves_opening_midpoint_axis_and_width(self):
        forward = self._analyze(groove=_boundary(start=20.0, end=42.0))
        reverse = self._analyze(groove=list(reversed(_boundary(start=20.0, end=42.0))))
        for key in ("openingCenterAzimuthImageDeg", "openingWidthDeg"):
            self.assertAlmostEqual(forward["measurement"][key], reverse["measurement"][key], places=9)
        for coordinate in ("x", "y"):
            self.assertAlmostEqual(
                forward["measurement"]["openingCenterOnCircle"][coordinate],
                reverse["measurement"]["openingCenterOnCircle"][coordinate],
                places=9,
            )

    def test_wraparound_endpoints_have_zero_degree_midpoint_not_180(self):
        result = self._analyze(groove=_boundary(start=350.0, end=10.0))
        self.assertAlmostEqual(0.0, result["measurement"]["openingCenterAzimuthImageDeg"], places=6)
        self.assertAlmostEqual(20.0, result["measurement"]["openingWidthDeg"], places=6)

    def test_non_inward_shadow_and_far_endpoint_are_rejected(self):
        shadow = self._analyze(groove=_boundary(depth=2.0))
        self.assertEqual("rejected", shadow["grooveRecognition"]["status"])
        self.assertIn("insufficient_inward_depth", shadow["grooveRecognition"]["rejectionReasons"])
        far = _boundary()
        far[0] = _point((250.0, 250.0), 130.0, 350.0)
        rejected = self._analyze(groove=far)
        self.assertIn("endpoint_not_on_outer_circle", rejected["grooveRecognition"]["rejectionReasons"])

    def test_discontinuous_boundary_is_rejected(self):
        groove = _boundary()
        groove[len(groove) // 2] = [250.0, 250.0]
        result = self._analyze(groove=groove)
        self.assertIn("boundary_discontinuity", result["grooveRecognition"]["rejectionReasons"])

    def test_target_and_measurement_are_separate_until_datum_is_confirmed(self):
        result = self._analyze(groove=_boundary(start=10.0, end=32.0), target=_target())
        target = result["targetAssessment"]
        self.assertEqual("NOT_EVALUATED", target["status"])
        self.assertIsNone(target["signedMeasurementMinusTargetDeg"])
        self.assertIsNone(target["mechanicalCorrectionDeg"])
        self.assertFalse(target["quadrantMatches"])

        comparable = assess_target(82.0, "lower_left", _target(confirmed=True))
        self.assertEqual("COMPARABLE", comparable["status"])
        self.assertAlmostEqual(-3.0, comparable["signedMeasurementMinusTargetDeg"])
        self.assertAlmostEqual(3.0, comparable["absoluteDeviationDeg"])
        self.assertIsNone(comparable["mechanicalCorrectionDeg"])

    def test_manual_truth_module_is_not_imported_by_runtime(self):
        for relative in ("algorithms/slot_pose/main.py", "algorithms/slot_pose/legacy_adapter.py"):
            source = (ROOT / relative).read_text(encoding="utf-8")
            self.assertNotIn("review_labelme_groove_pose", source)
            self.assertNotIn("manual-half-circle-with-groove", source)


class ManualGrooveReviewCliTests(unittest.TestCase):
    def test_writes_external_semantic_copy_report_and_preview_without_overwriting_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            image_path = root / "source.bmp"
            Image.new("L", (500, 500), 100).save(image_path)
            annotation = root / "manual.json"
            annotation.write_text(json.dumps({
                "version": "5.10.1", "flags": {}, "imagePath": "source.bmp", "imageData": None,
                "imageWidth": 500, "imageHeight": 500,
                "shapes": [
                    {"label": "circle-source", "shape_type": "linestrip", "points": _arc(), "flags": {}},
                    {"label": "groove-source", "shape_type": "linestrip", "points": _boundary(), "flags": {}},
                ],
            }), encoding="utf-8")
            original = annotation.read_bytes()
            report_path = root / "pose-review.json"
            semantic_path = root / "semantic-copy.json"
            preview_path = root / "pose-preview.jpg"
            report = review_labelme_groove_pose(
                annotation, image_path, ROOT / "config/inspection.example.json",
                report_path, semantic_path, preview_path,
                circle_label="circle-source", groove_label="groove-source", target_contract=_target(),
            )
            self.assertEqual(original, annotation.read_bytes())
            self.assertEqual("MANUAL_GEOMETRY_ACCEPTED_TARGET_NOT_EVALUATED", report["status"])
            self.assertTrue(report_path.is_file())
            self.assertTrue(preview_path.is_file())
            semantic = json.loads(semantic_path.read_text(encoding="utf-8"))
            self.assertEqual(
                {"physical_outer_circle_visible_arc_manual", "target_groove_open_boundary_manual"},
                {shape["label"] for shape in semantic["shapes"]},
            )
            self.assertFalse(semantic["flags"]["runtime_input_allowed"])
            self.assertFalse(semantic["flags"]["formal_truth"])
            self.assertIsNone(report["targetAssessment"]["mechanicalCorrectionDeg"])

    @unittest.skipIf(jsonschema is None, "jsonschema is installed by the explicit Schema gate")
    def test_report_matches_versioned_schema(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            image_path = root / "source.bmp"
            Image.new("L", (500, 500), 100).save(image_path)
            annotation = root / "manual.json"
            annotation.write_text(json.dumps({
                "version": "5.10.1", "flags": {}, "imagePath": "source.bmp", "imageData": None,
                "imageWidth": 500, "imageHeight": 500,
                "shapes": [
                    {"label": "arc", "shape_type": "linestrip", "points": _arc(), "flags": {}},
                    {"label": "groove", "shape_type": "linestrip", "points": _boundary(), "flags": {}},
                ],
            }), encoding="utf-8")
            report = review_labelme_groove_pose(
                annotation, image_path, ROOT / "config/inspection.example.json",
                root / "report.json", root / "semantic.json", root / "preview.jpg",
                circle_label="arc", groove_label="groove", target_contract=_target(),
            )
            schema = json.loads((ROOT / "contracts/manual-groove-pose-review.schema.json").read_text(encoding="utf-8"))
            jsonschema.Draft202012Validator.check_schema(schema)
            jsonschema.validate(report, schema)

    def test_accepts_embedded_labelme_image_without_external_image_argument(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            buffer = io.BytesIO()
            Image.new("L", (500, 500), 100).save(buffer, format="PNG")
            annotation = root / "embedded.json"
            annotation.write_text(json.dumps({
                "version": "5.10.1", "flags": {}, "imagePath": "embedded.png",
                "imageData": base64.b64encode(buffer.getvalue()).decode("ascii"),
                "imageWidth": 500, "imageHeight": 500,
                "shapes": [
                    {"label": "arc", "shape_type": "linestrip", "points": _arc(), "flags": {}},
                    {"label": "groove", "shape_type": "linestrip", "points": _boundary(), "flags": {}},
                ],
            }), encoding="utf-8")
            report = review_labelme_groove_pose(
                annotation, None, ROOT / "config/inspection.example.json",
                root / "report.json", root / "semantic.json", root / "preview.jpg",
                circle_label="arc", groove_label="groove", target_contract=_target(),
            )
            self.assertEqual("labelme_imageData", report["source"]["imageSource"])


if __name__ == "__main__":
    unittest.main()
