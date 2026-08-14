from __future__ import annotations

import unittest

import numpy as np

from algorithms.slot_pose.angular_profile import (
    NotchCandidate,
    assess_pairs,
    circular_delta_deg,
    circular_midpoint_deg,
    extract_dark_candidates,
)


PROFILE_CONFIG = {
    "n_angles": 360,
    "n_radii": 10,
    "shell_width_px": 30.0,
    "smoothing_window": 3,
    "mad_multiplier": 3.0,
    "min_prominence": 12.0,
    "min_half_width_deg": 2.0,
    "max_half_width_deg": 20.0,
}

PAIRING_CONFIG = {
    "min_candidates": 2,
    "max_candidates": 6,
    "min_separation_deg": 30.0,
    "max_separation_deg": 50.0,
    "expected_separation_deg": 40.0,
    "min_width_ratio": 0.6,
    "min_prominence_ratio": 0.6,
    "min_pair_score": 0.7,
    "min_score_margin": 0.1,
}


def profile_with_dips(*dips: tuple[float, float, float]) -> np.ndarray:
    profile = np.full(360, 200.0)
    for center, half_width, value in dips:
        for index in range(360):
            if abs(circular_delta_deg(float(index), center)) <= half_width:
                profile[index] = value
    return profile


def candidate(identifier: str, center: float, width: float = 5.0, prominence: float = 80.0) -> NotchCandidate:
    return NotchCandidate(identifier, center, width, center - width, center + width, False, prominence, 100.0, 1)


class AngularProfileTests(unittest.TestCase):
    def test_circular_delta_and_midpoint_cross_wrap(self) -> None:
        self.assertEqual(2.0, circular_delta_deg(-179.0, 179.0))
        self.assertAlmostEqual(0.0, circular_midpoint_deg(350.0, 10.0))

    def test_extracts_all_candidates_and_quality_summary(self) -> None:
        candidates, summary = extract_dark_candidates(
            profile_with_dips((20.0, 5.0, 90.0), (60.0, 6.0, 100.0)), PROFILE_CONFIG,
        )
        self.assertEqual(2, len(candidates))
        self.assertAlmostEqual(20.0, candidates[0].center_deg, delta=0.5)
        self.assertAlmostEqual(5.5, candidates[0].half_width_deg, delta=1.0)
        self.assertGreater(candidates[0].prominence, 90.0)
        self.assertEqual("candidate-001", candidates[0].candidate_id)
        self.assertEqual(2, summary["count"])
        self.assertIsNotNone(summary["prominenceGap"])

    def test_wraparound_dark_run_is_one_candidate(self) -> None:
        candidates, _ = extract_dark_candidates(profile_with_dips((0.0, 6.0, 80.0)), PROFILE_CONFIG)
        self.assertEqual(1, len(candidates))
        self.assertTrue(candidates[0].wraps_boundary)
        self.assertLess(abs(circular_delta_deg(candidates[0].center_deg, 0.0)), 0.6)

    def test_selects_unique_pair_and_centerline(self) -> None:
        result = assess_pairs([candidate("a", 350.0), candidate("b", 30.0)], PAIRING_CONFIG)
        self.assertTrue(result["unique"], result)
        self.assertAlmostEqual(10.0, result["centerlineDeg"])
        self.assertAlmostEqual(40.0, result["separationDeg"])

    def test_missing_candidate_fails(self) -> None:
        result = assess_pairs([candidate("a", 10.0)], PAIRING_CONFIG)
        self.assertFalse(result["unique"])
        self.assertIn("candidate_count_too_low", result["failedChecks"])

    def test_equal_alternative_pairs_are_ambiguous(self) -> None:
        result = assess_pairs(
            [candidate("a", 10.0), candidate("b", 50.0), candidate("c", 90.0)], PAIRING_CONFIG,
        )
        self.assertFalse(result["unique"], result)
        self.assertIn("pair_not_unique", result["failedChecks"])
        self.assertAlmostEqual(0.0, result["scoreMargin"])

    def test_width_or_prominence_mismatch_rejects_pair(self) -> None:
        result = assess_pairs(
            [candidate("a", 10.0, width=5.0, prominence=80.0), candidate("b", 50.0, width=2.0, prominence=20.0)],
            PAIRING_CONFIG,
        )
        self.assertFalse(result["unique"])
        failed = result["assessments"][0]["failedChecks"]
        self.assertIn("width_ratio", failed)
        self.assertIn("prominence_ratio", failed)


if __name__ == "__main__":
    unittest.main()
