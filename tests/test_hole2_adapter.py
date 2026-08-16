import json
import math
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from algorithms.hole_2.main import (
    boundary_parallelism_deg,
    build_reference,
    detect_dimension_boundary,
    gaussian_blur,
    is_diameter_feature,
    sanitize_label,
)


class Hole2AdapterTests(unittest.TestCase):
    def test_known_corrupted_diameter_label_is_stable(self) -> None:
        self.assertEqual("Phi12_2", sanitize_label("��12.2"))
        self.assertEqual("Phi12_2", sanitize_label("ψ12.2"))
        self.assertTrue(is_diameter_feature("ψ12.2"))

    def test_linear_dimension_column_stays_stable(self) -> None:
        self.assertEqual("d7", sanitize_label("7"))

    def test_dimension_7_fits_two_independent_boundaries(self) -> None:
        image = np.full((140, 220), 25.0)
        for y in range(image.shape[0]):
            left = 50.0 + 0.04 * (y - 70)
            right = 160.0 - 0.03 * (y - 70)
            image[y, int(round(left)):int(round(right)) + 1] = 220.0
        image = gaussian_blur(image, 1.0)

        first = detect_dimension_boundary(
            image, (50.0, 70.0), (160.0, 70.0), "p1", polarity=100.0
        )
        second = detect_dimension_boundary(
            image, (50.0, 70.0), (160.0, 70.0), "p2", polarity=-100.0
        )

        self.assertIsNotNone(first)
        self.assertIsNotNone(second)
        self.assertGreaterEqual(first.point_count, 12)
        self.assertGreaterEqual(second.point_count, 12)
        self.assertLess(first.median_residual_px, 0.5)
        self.assertLess(second.median_residual_px, 0.5)
        distance = math.dist(first.feature_point, second.feature_point)
        self.assertAlmostEqual(110.55, distance, delta=0.75)
        self.assertLess(boundary_parallelism_deg(first.line, second.line), 3.0)

    def test_psi_linestrip_builds_circle_with_diameter_column(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            image_path = root / "reference.bmp"
            Image.fromarray(np.full((160, 160), 127, dtype=np.uint8)).save(image_path)
            angles = np.linspace(1.0, 5.2, 77)
            points = [
                [80.0 + 40.0 * math.cos(angle), 80.0 + 40.0 * math.sin(angle)]
                for angle in angles
            ]
            label_path = root / "annotation.json"
            label_path.write_text(json.dumps({
                "imagePath": image_path.name,
                "shapes": [{
                    "label": "ψ12.2",
                    "shape_type": "linestrip",
                    "points": points,
                }],
            }), encoding="utf-8")

            reference = build_reference(label_path, image_path)
            self.assertEqual(1, len(reference.shapes))
            shape = reference.shapes[0]
            self.assertEqual("Phi12_2", shape.sanitized)
            self.assertEqual("linestrip", shape.source_shape_type)
            self.assertTrue(shape.emits_diameter_px)
            self.assertIn("Phi12_2_r", shape.columns)
            self.assertIn("Phi12_2_diameter_px", shape.columns)
            self.assertAlmostEqual(40.0, shape.circle[2], places=5)


if __name__ == "__main__":
    unittest.main()
