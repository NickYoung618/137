import json
import math
import tempfile
import unittest
from pathlib import Path

import numpy as np

from algorithms.hole_2.d7_reference_profile import (
    build_reference_profile_models,
    compare_audit_to_labelme,
    compare_formal_evidence_to_labelme,
    evaluate_reference_profile_candidate,
)


def _blur1d_rows(image: np.ndarray) -> np.ndarray:
    kernel = np.asarray([1, 4, 6, 4, 1], dtype=np.float64)
    kernel /= kernel.sum()
    padded = np.pad(image, ((2, 2), (0, 0)), mode="edge")
    return sum(kernel[index] * padded[index:index + image.shape[0]] for index in range(5))


def _neck_image(
    top: float,
    bottom: float,
    *,
    height: int = 150,
    width: int = 180,
    distractor: bool = False,
) -> np.ndarray:
    yy = np.arange(height, dtype=np.float64)[:, None]
    image = np.full((height, width), 184.0, dtype=np.float64)
    interior = (yy >= top) & (yy <= bottom)
    image[:] = np.where(interior, 116.0, image)
    for center in (top, bottom):
        image[np.abs(yy[:, 0] - center) <= 3.0, :] = 24.0
    if distractor:
        # Stronger isolated bands lack the material-context transition of the
        # true neck boundaries. A strongest-gradient-only detector picks them.
        for center in (top - 14.0, bottom + 14.0):
            image[np.abs(yy[:, 0] - center) <= 2.0, :] = 0.0
    image += np.linspace(-5.0, 5.0, width, dtype=np.float64)[None, :]
    return _blur1d_rows(image)


class D7ReferenceProfileTests(unittest.TestCase):
    def setUp(self):
        self.reference = _neck_image(40.25, 104.75)
        self.p1 = (90.0, 40.25)
        self.p2 = (90.0, 104.75)
        self.models = build_reference_profile_models(
            self.reference, self.p1, self.p2,
            profile_half_width_ref_px=18.0,
            tangent_half_width_ref_px=24.0,
            tangent_samples=17,
        )

    def test_reference_self_match_is_subpixel_and_does_not_update_formal_measurement(self):
        audit = evaluate_reference_profile_candidate(
            self.reference, self.models, self.p1, self.p2,
            target_scale=1.0, search_window_target_px=12.0,
            tangent_half_width_target_px=24.0, tangent_samples=17,
            min_support=10,
        )
        self.assertTrue(audit["candidateValid"], audit)
        self.assertFalse(audit["formalMeasurementUpdated"])
        self.assertAlmostEqual(64.5, audit["measurementTargetPx"], delta=0.5)
        self.assertAlmostEqual(0.0, audit["boundaryA"]["shiftMedianTargetPx"], delta=0.35)
        self.assertAlmostEqual(0.0, audit["boundaryB"]["shiftMedianTargetPx"], delta=0.35)

    def test_full_profile_context_rejects_stronger_neighbour_layer(self):
        target = _neck_image(43.10, 108.20, distractor=True)
        audit = evaluate_reference_profile_candidate(
            target, self.models, (90.0, 40.25), (90.0, 104.75),
            target_scale=1.0, search_window_target_px=20.0,
            tangent_half_width_target_px=24.0, tangent_samples=17,
            min_support=10,
        )
        self.assertTrue(audit["candidateValid"], audit)
        self.assertAlmostEqual(43.10, audit["boundaryA"]["featurePointTargetPx"][1], delta=0.8)
        self.assertAlmostEqual(108.20, audit["boundaryB"]["featurePointTargetPx"][1], delta=0.8)

    def test_reversed_photometric_context_fails_closed(self):
        target = 255.0 - _neck_image(43.0, 108.0)
        audit = evaluate_reference_profile_candidate(
            target, self.models, self.p1, self.p2,
            target_scale=1.0, search_window_target_px=20.0,
            tangent_half_width_target_px=24.0, tangent_samples=17,
            min_support=10,
        )
        self.assertFalse(audit["candidateValid"])
        self.assertIn("profile", audit["failureReason"])

    def test_flat_or_ambiguous_profile_fails_closed(self):
        flat = np.full_like(self.reference, 120.0)
        audit = evaluate_reference_profile_candidate(
            flat, self.models, self.p1, self.p2,
            target_scale=1.0, search_window_target_px=20.0,
            tangent_half_width_target_px=24.0, tangent_samples=17,
            min_support=10,
        )
        self.assertFalse(audit["candidateValid"])
        self.assertIsNone(audit["measurementTargetPx"])

    def test_labelme_comparison_reports_each_side_and_width(self):
        audit = evaluate_reference_profile_candidate(
            self.reference, self.models, self.p1, self.p2,
            target_scale=1.0, search_window_target_px=12.0,
            tangent_half_width_target_px=24.0, tangent_samples=17,
            min_support=10,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            label_path = Path(temp_dir) / "truth.json"
            label_path.write_text(json.dumps({"shapes": [
                {"label": "D7-A", "shape_type": "line", "points": [[50, 40.25], [130, 40.25]]},
                {"label": "D7-B", "shape_type": "line", "points": [[50, 104.75], [130, 104.75]]},
            ]}), encoding="utf-8")
            report = compare_audit_to_labelme(audit, label_path)
        self.assertAlmostEqual(0.0, report["sides"]["A"]["lineDistancePx"], delta=0.5)
        self.assertAlmostEqual(0.0, report["sides"]["B"]["lineDistancePx"], delta=0.5)
        self.assertAlmostEqual(0.0, report["measurementLengthErrorPx"], delta=0.5)

    def test_authoritative_two_endpoint_truth_is_not_misreported_as_boundary_lines(self):
        audit = evaluate_reference_profile_candidate(
            self.reference, self.models, self.p1, self.p2,
            target_scale=1.0, search_window_target_px=12.0,
            tangent_half_width_target_px=24.0, tangent_samples=17,
            min_support=10,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            label_path = Path(temp_dir) / "truth.json"
            label_path.write_text(json.dumps({"shapes": [{
                "label": "7", "shape_type": "line",
                "points": [list(self.p1), list(self.p2)],
            }]}), encoding="utf-8")
            report = compare_audit_to_labelme(audit, label_path)
        self.assertEqual("two_measurement_endpoints", report["truthGeometry"])
        self.assertIsNone(report["sides"]["A"]["lineDistancePx"])
        self.assertAlmostEqual(
            0.0, report["sides"]["A"]["featurePointDistancePx"], delta=0.5
        )

    def test_labelme_comparison_rejects_missing_side(self):
        audit = {
            "candidateValid": False,
            "formalMeasurementUpdated": False,
            "measurementTargetPx": None,
            "boundaryA": {}, "boundaryB": {},
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            label_path = Path(temp_dir) / "truth.json"
            label_path.write_text(json.dumps({"shapes": [
                {"label": "D7-A", "shape_type": "line", "points": [[0, 0], [1, 0]]},
            ]}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "D7-B"):
                compare_audit_to_labelme(audit, label_path)

    def test_formal_evidence_comparison_reports_outer_mid_inner_and_manual_phase(self):
        feature = {
            "measurementValid": True,
            "target": {
                "lengthPx": 65.0,
                "rawEdgeEvidence": {"boundaries": [
                    {
                        "side": "A",
                        "transitionPairsPx": [
                            [[40.0, 38.0], [40.0, 42.0]],
                            [[50.0, 38.0], [50.0, 42.0]],
                            [[60.0, 38.0], [60.0, 42.0]],
                        ],
                    },
                    {
                        "side": "B",
                        "transitionPairsPx": [
                            [[40.0, 107.0], [40.0, 103.0]],
                            [[50.0, 107.0], [50.0, 103.0]],
                            [[60.0, 107.0], [60.0, 103.0]],
                        ],
                    },
                ]},
                "fittedGeometry": {"boundaries": [
                    {"side": "A", "lineEquation": [0.0, 1.0, -40.0]},
                    {"side": "B", "lineEquation": [0.0, 1.0, -105.0]},
                ]},
            },
            "quality": {
                "d7.quality.candidate_p1_strip": {
                    "fittedLine": [0.0, 1.0, -40.0],
                    "layerStabilizationResidualGatePx": 3.0,
                },
                "d7.quality.candidate_p2_strip": {
                    "fittedLine": [0.0, 1.0, -105.0],
                    "layerStabilizationResidualGatePx": 3.0,
                },
            },
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            label_path = Path(temp_dir) / "truth.json"
            label_path.write_text(json.dumps({"shapes": [
                {"label": "D7-A", "shape_type": "line", "points": [[20, 41], [80, 41]]},
                {"label": "D7-B", "shape_type": "line", "points": [[20, 104], [80, 104]]},
            ]}), encoding="utf-8")
            report = compare_formal_evidence_to_labelme(feature, label_path)
        self.assertAlmostEqual(2.0, report["measurementLengthErrorPx"])
        for side in ("A", "B"):
            comparison = report["sides"][side]
            self.assertEqual(3, comparison["selectedPairCount"])
            self.assertAlmostEqual(
                0.75, comparison["manualPhaseFraction"]["median"], places=6
            )
            self.assertAlmostEqual(
                1.0, comparison["layers"]["midpoint"]["absoluteDistanceMedianPx"]
            )
            self.assertAlmostEqual(
                1.0, comparison["layers"]["inner"]["absoluteDistanceMedianPx"]
            )


if __name__ == "__main__":
    unittest.main()
