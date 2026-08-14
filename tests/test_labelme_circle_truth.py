from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from tools.build_labelme_circle_truth import build_truth


class LabelMeCircleTruthTests(unittest.TestCase):
    def test_builds_reviewed_path_safe_manual_circle_truth(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            Image.new("L", (100, 80), 0).save(root / "source.bmp")
            annotation = root / "source.json"
            annotation.write_text(json.dumps({
                "imagePath": "source.bmp", "imageWidth": 100, "imageHeight": 80,
                "flags": {"human_verified": True, "independent_from_algorithm": True},
                "shapes": [{
                    "label": "physical_outer_circle_truth", "shape_type": "circle",
                    "points": [[50.0, 40.0], [70.0, 40.0]],
                }],
            }), encoding="utf-8")
            result = build_truth(
                annotation, root, annotator="operator-a", reviewer="quality-b", truth_version="a2-circle-v1",
            )
            self.assertEqual("HUMAN_REVIEWED", result["status"])
            self.assertEqual(20.0, result["circle"]["radiusPx"])
            self.assertFalse(Path(result["image"]["relativePath"]).is_absolute())
            self.assertNotEqual(result["source"]["annotator"], result["source"]["reviewer"])

    def test_rejects_unreviewed_or_algorithm_dependent_annotation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            Image.new("L", (20, 20), 0).save(root / "source.bmp")
            annotation = root / "source.json"
            annotation.write_text(json.dumps({
                "imagePath": "source.bmp", "imageWidth": 20, "imageHeight": 20,
                "flags": {"human_verified": True, "independent_from_algorithm": False},
                "shapes": [{
                    "label": "physical_outer_circle_truth", "shape_type": "circle",
                    "points": [[10.0, 10.0], [15.0, 10.0]],
                }],
            }), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "independent_from_algorithm"):
                build_truth(annotation, root, annotator="a", reviewer="b", truth_version="v1")


if __name__ == "__main__":
    unittest.main()
