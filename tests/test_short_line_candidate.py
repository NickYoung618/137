from __future__ import annotations

import copy
import math
import tempfile
import unittest
from pathlib import Path

from algorithms.end_face.short_line_candidate import (
    ShortLineCandidateEvaluator,
    candidate_config_sha256,
    load_candidate_config,
    validate_candidate_config,
)
from tests.end_face_test_support import DEFAULT_CANDIDATE_CONFIG, synthetic_candidate_case, write_candidate_config


class ShortLineCandidateTests(unittest.TestCase):
    def test_candidate_configuration_is_versioned_finite_and_canonical(self) -> None:
        validate_candidate_config(DEFAULT_CANDIDATE_CONFIG)
        self.assertEqual(candidate_config_sha256(DEFAULT_CANDIDATE_CONFIG), candidate_config_sha256(copy.deepcopy(DEFAULT_CANDIDATE_CONFIG)))
        invalid = copy.deepcopy(DEFAULT_CANDIDATE_CONFIG)
        invalid["features"] = ["19", "46"]
        with self.assertRaises(ValueError):
            validate_candidate_config(invalid)
        invalid = copy.deepcopy(DEFAULT_CANDIDATE_CONFIG)
        invalid["gates"]["minimumCorrelation"] = math.nan
        with self.assertRaises(ValueError):
            validate_candidate_config(invalid)

    def test_load_candidate_config_records_the_source_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "candidate.json"
            write_candidate_config(path)
            loaded = load_candidate_config(path)
        self.assertEqual("reference-gradient-registration-v1", loaded["candidateId"])

    def test_core_diagnostic_exposes_roi_profile_peak_boundary_and_fallback(self) -> None:
        model, target, measurements, features = synthetic_candidate_case(core_valid=False)
        evaluator = ShortLineCandidateEvaluator(model, DEFAULT_CANDIDATE_CONFIG)
        result = evaluator.evaluate_gray(target, measurements, features)["19��"]
        diagnostic = result["diagnostic"]
        self.assertEqual("short-line-diagnostic/1", diagnostic["diagnosticVersion"])
        self.assertIn("contrastP95P05", diagnostic["roi"])
        self.assertIn("gradientP90", diagnostic["roi"])
        self.assertEqual([-12.0, 12.0], diagnostic["coreSearch"]["searchBoundsPx"])
        self.assertIn("peak", diagnostic["coreSearch"])
        self.assertIn("threshold", diagnostic["coreSearch"])
        self.assertIn("peakAtBoundary", diagnostic["coreSearch"])
        self.assertEqual("short_line_lateral_edge_not_found", diagnostic["coreSearch"]["coreFallbackReason"])

    def test_candidate_recovers_image_derived_position_and_orientation(self) -> None:
        model, target, measurements, features = synthetic_candidate_case(
            target_midpoint=(64.0, 69.0), target_angle_deg=3.0
        )
        measurements_before = copy.deepcopy(measurements)
        features_before = copy.deepcopy(features)
        result = ShortLineCandidateEvaluator(model, DEFAULT_CANDIDATE_CONFIG).evaluate_gray(
            target, measurements, features
        )["19��"]
        self.assertEqual(measurements_before, measurements)
        self.assertEqual(features_before, features)
        self.assertTrue(result["candidate"]["candidateValid"], result["diagnostic"])
        geometry = result["candidate"]["target"]
        midpoint = ((geometry["x1"] + geometry["x2"]) * 0.5, (geometry["y1"] + geometry["y2"]) * 0.5)
        self.assertAlmostEqual(64.0, midpoint[0], delta=1.5)
        self.assertAlmostEqual(69.0, midpoint[1], delta=1.5)
        self.assertAlmostEqual(3.0, geometry["angleDeg"], delta=1.5)
        self.assertEqual("both_valid", result["transition"])
        self.assertTrue(result["core"]["coreValid"])

    def test_blank_low_contrast_and_search_boundary_are_not_promoted(self) -> None:
        cases = [
            synthetic_candidate_case(foreground=31),
            synthetic_candidate_case(target_midpoint=(64.0, 88.0), target_angle_deg=0.0),
        ]
        for model, target, measurements, features in cases:
            with self.subTest(target_midpoint=target.shape):
                result = ShortLineCandidateEvaluator(model, DEFAULT_CANDIDATE_CONFIG).evaluate_gray(
                    target, measurements, features
                )["19��"]
                self.assertFalse(result["candidate"]["candidateValid"], result)
                self.assertTrue(result["diagnostic"]["failedChecks"])
                self.assertIsNone(result["candidate"]["target"])

    def test_competing_separated_peak_is_rejected(self) -> None:
        model, target, measurements, features = synthetic_candidate_case(
            target_midpoint=(64.0, 58.0),
            target_angle_deg=0.0,
            extra_midpoints=((64.0, 70.0),),
        )
        result = ShortLineCandidateEvaluator(model, DEFAULT_CANDIDATE_CONFIG).evaluate_gray(
            target, measurements, features
        )["19��"]
        self.assertFalse(result["candidate"]["candidateValid"], result)
        self.assertIn("separated_peak_gap", result["diagnostic"]["failedChecks"])
        self.assertIn("competing_peak", result["diagnostic"]["failureCategories"])


if __name__ == "__main__":
    unittest.main()
