from __future__ import annotations

import json
import math
import unittest
from pathlib import Path

import jsonschema
import numpy as np

from tools.analyze_manual_circle_edge_families import (
    EXPECTED_HEIGHT, EXPECTED_LABEL, EXPECTED_WIDTH,
    fit_manual_circle, project_radial_evidence, validate_labelme,
)


class ManualCircleEdgeFamilyAnalysisTests(unittest.TestCase):
    @staticmethod
    def _points() -> list[list[float]]:
        return [
            [2736.0 + 1200.0 * math.cos(angle), 1824.0 + 1200.0 * math.sin(angle)]
            for angle in np.linspace(math.radians(40.0), math.radians(310.0), 88)
        ]

    def test_labelme_contract_and_manual_circle_leave_one_out_are_recomputed(self) -> None:
        payload = {
            "imageWidth": EXPECTED_WIDTH, "imageHeight": EXPECTED_HEIGHT,
            "shapes": [{"label": EXPECTED_LABEL, "shape_type": "linestrip", "points": self._points()}],
        }
        points = validate_labelme(payload)
        manual, loo = fit_manual_circle(points)
        self.assertEqual((88, 2), points.shape)
        self.assertAlmostEqual(2736.0, manual["centerX"], places=5)
        self.assertAlmostEqual(1824.0, manual["centerY"], places=5)
        self.assertAlmostEqual(1200.0, manual["radiusPx"], places=5)
        self.assertAlmostEqual(270.0, manual["arcCoverageDeg"], places=5)
        self.assertEqual(88, loo["fitCount"])
        self.assertLess(loo["maxCenterShiftPx"], 1e-4)

        for mutation in (
            {**payload, "imageWidth": 10},
            {**payload, "shapes": [{**payload["shapes"][0], "label": "wrong"}]},
            {**payload, "shapes": [{**payload["shapes"][0], "points": self._points()[:-1]}]},
        ):
            with self.assertRaises(ValueError):
                validate_labelme(mutation)

    def test_projection_reports_all_peaks_legacy_selection_and_missing_without_truth_input_to_runtime(self) -> None:
        size = 256
        yy, xx = np.indices((size, size))
        radius = np.hypot(xx - 128.0, yy - 128.0)
        gray = np.where(radius <= 80.0, 210.0, 10.0)
        projection, rays = project_radial_evidence(
            gray, (128.0, 128.0, 80.0), (128.0, 128.0, 80.0),
            ray_count=72, truth_gate_px=8.0,
        )
        self.assertEqual(72, projection["rayCount"])
        self.assertEqual(72, len(rays))
        self.assertGreater(projection["truthPeakPresentCount"], 60)
        self.assertGreater(projection["legacySelectedTruthCount"], 60)
        self.assertTrue(all(len(item["gradientPeaks"]) <= 8 for item in rays))

    def test_schema_has_no_private_paths_and_runtime_does_not_import_manual_tool(self) -> None:
        root = Path(__file__).resolve().parents[1]
        schema = json.loads((root / "contracts/manual-circle-edge-family-analysis.schema.json").read_text())
        jsonschema.Draft202012Validator.check_schema(schema)
        for relative in ("algorithms/slot_pose/physical_outer_circle.py", "algorithms/slot_pose/legacy_adapter.py"):
            self.assertNotIn("analyze_manual_circle_edge_families", (root / relative).read_text())


if __name__ == "__main__":
    unittest.main()
