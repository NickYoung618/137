from __future__ import annotations

import json
import math
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from tools.complete_labelme_circle import complete_labelme_circle

try:
    import jsonschema
except ImportError:
    jsonschema = None


ROOT = Path(__file__).resolve().parents[1]


def _payload(points):
    return {
        "version": "5.10.1",
        "flags": {},
        "shapes": [
            {
                "label": "outer_circle_visible_arc", "shape_type": "linestrip",
                "points": points, "flags": {}, "description": "manual visible arc",
            },
            {
                "label": "groove_axis", "shape_type": "line",
                "points": [[250.0, 250.0], [120.0, 150.0]], "flags": {},
            },
            {
                "label": "datum_axis", "shape_type": "line",
                "points": [[250.0, 250.0], [250.0, 50.0]], "flags": {},
            },
            {
                "label": "ignore_occlusion", "shape_type": "polygon",
                "points": [[300.0, 20.0], [480.0, 20.0], [480.0, 180.0]], "flags": {},
            },
        ],
        "imagePath": "source.bmp", "imageData": None,
        "imageHeight": 500, "imageWidth": 500,
    }


def _arc(point_count=20, coverage_deg=210.0, radius=80.0):
    angles = np.linspace(math.radians(30.0), math.radians(30.0 + coverage_deg), point_count)
    return [[250.0 + radius * math.cos(a), 250.0 + radius * math.sin(a)] for a in angles]


class LabelMeCircleCompletionTests(unittest.TestCase):
    def _files(self, root: Path, points):
        image = root / "source.bmp"
        Image.new("L", (500, 500), 120).save(image)
        annotation = root / "partial.json"
        annotation.write_text(json.dumps(_payload(points)), encoding="utf-8")
        return image, annotation

    def test_completes_closed_circle_with_derived_count_and_review_flags(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            image, annotation = self._files(root, _arc())
            completed = root / "completed.json"
            report_path = root / "report.json"
            preview = root / "preview.jpg"
            report = complete_labelme_circle(
                annotation, image, completed, report_path, preview,
            )
            payload = json.loads(completed.read_text(encoding="utf-8"))
            by_label = {shape["label"]: shape for shape in payload["shapes"]}
            self.assertEqual({"outer_circle_contour", "groove_axis", "datum_axis"}, set(by_label))
            contour = by_label["outer_circle_contour"]
            self.assertEqual("linestrip", contour["shape_type"])
            self.assertTrue(contour["flags"]["auto_completed"])
            self.assertFalse(contour["flags"]["human_verified"])
            self.assertEqual(contour["points"][0], contour["points"][-1])
            self.assertNotEqual(77, len(contour["points"]))
            self.assertEqual(len(contour["points"]), report["completed"]["pointCount"])
            expected_unique = round(
                2.0 * math.pi * report["fit"]["radiusPx"]
                / report["source"]["medianAdjacentSpacingPx"]
            )
            self.assertEqual(expected_unique, report["completed"]["uniquePointCount"])
            self.assertAlmostEqual(360.0, report["completed"]["angularCoverageDeg"], places=9)
            self.assertLess(report["completed"]["radialResidualPx"]["max"], 1e-6)
            self.assertTrue(preview.is_file())
            self.assertEqual(report, json.loads(report_path.read_text(encoding="utf-8")))

    def test_rejects_fewer_than_eight_points(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            image, annotation = self._files(root, _arc(point_count=7))
            with self.assertRaisesRegex(ValueError, "at least 8 finite points"):
                complete_labelme_circle(
                    annotation, image, root / "out.json", root / "report.json", root / "preview.jpg",
                )

    def test_rejects_non_circular_polyline(self):
        points = [
            [30.0, 30.0], [90.0, 450.0], [150.0, 30.0], [210.0, 450.0],
            [270.0, 30.0], [330.0, 450.0], [390.0, 30.0], [450.0, 450.0],
        ]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            image, annotation = self._files(root, points)
            with self.assertRaisesRegex(ValueError, "circle residual"):
                complete_labelme_circle(
                    annotation, image, root / "out.json", root / "report.json", root / "preview.jpg",
                )

    def test_rejects_insufficient_visible_arc_coverage(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            image, annotation = self._files(root, _arc(coverage_deg=50.0))
            with self.assertRaisesRegex(ValueError, "angular coverage"):
                complete_labelme_circle(
                    annotation, image, root / "out.json", root / "report.json", root / "preview.jpg",
                )

    def test_rejects_output_inside_git_worktree(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            image, annotation = self._files(root, _arc())
            with self.assertRaisesRegex(ValueError, "outside the Git worktree"):
                complete_labelme_circle(
                    annotation, image, ROOT / "outputs/forbidden-completed.json",
                    root / "report.json", root / "preview.jpg",
                )

    @unittest.skipIf(jsonschema is None, "jsonschema is installed by the explicit Schema gate")
    def test_config_and_report_match_versioned_schemas(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            image, annotation = self._files(root, _arc())
            report = complete_labelme_circle(
                annotation, image, root / "completed.json", root / "report.json", root / "preview.jpg",
                ROOT / "config/labelme_circle_completion.example.json",
            )
        config = json.loads((ROOT / "config/labelme_circle_completion.example.json").read_text())
        config_schema = json.loads((ROOT / "contracts/labelme-circle-completion-config.schema.json").read_text())
        report_schema = json.loads((ROOT / "contracts/labelme-circle-completion-report.schema.json").read_text())
        jsonschema.Draft202012Validator.check_schema(config_schema)
        jsonschema.Draft202012Validator.check_schema(report_schema)
        jsonschema.validate(config, config_schema)
        jsonschema.validate(report, report_schema)


if __name__ == "__main__":
    unittest.main()
