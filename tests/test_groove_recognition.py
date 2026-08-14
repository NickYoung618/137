from __future__ import annotations

import unittest

import numpy as np

from algorithms.slot_pose.angular_profile import NotchCandidate
from algorithms.slot_pose.groove_recognition import DEFAULT_GROOVE_RECOGNITION_CONFIG, recognize_grooves


def candidate(candidate_id: str, center: float, half_width: float = 5.0) -> NotchCandidate:
    return NotchCandidate(
        candidate_id=candidate_id,
        center_deg=center % 360.0,
        half_width_deg=half_width,
        start_deg=(center - half_width) % 360.0,
        end_deg=(center + half_width) % 360.0,
        wraps_boundary=(center - half_width) % 360.0 > (center + half_width) % 360.0,
        prominence=100.0,
        deficit_area=1000.0,
        rank=1,
    )


def polar_fixture(
    center: float,
    *,
    half_width: float = 5.0,
    start_row: int = 15,
    end_row: int = 80,
    darkness: float = 130.0,
    fan_out_deg: float = 0.0,
    center_drift_deg: float = 0.0,
) -> np.ndarray:
    rows, columns = 81, 720
    polar = np.full((rows, columns), 190.0, dtype=np.float64)
    step = 360.0 / columns
    for row in range(max(0, start_row), min(rows, end_row + 1)):
        progress = (row - start_row) / max(1, end_row - start_row)
        row_half = half_width + fan_out_deg * progress
        row_center = center + center_drift_deg * progress
        offsets = np.arange(columns) * step
        delta = (offsets - row_center + 180.0) % 360.0 - 180.0
        polar[row, np.abs(delta) <= row_half] = 190.0 - darkness
    return polar


class GrooveRecognitionTests(unittest.TestCase):
    def test_true_groove_is_accepted_with_explainable_evidence(self) -> None:
        result = recognize_grooves(
            polar_fixture(90.0), [candidate("candidate-001", 90.0)], 180.0, 120.0,
            DEFAULT_GROOVE_RECOGNITION_CONFIG, 1,
        )
        assessment = result["assessments"][0]
        self.assertEqual("accepted", result["status"])
        self.assertTrue(assessment["accepted"])
        self.assertGreater(assessment["radialDepthPx"], 35.0)
        self.assertGreater(assessment["pairedEdgeSupport"], 0.9)
        self.assertEqual([], assessment["rejectionReasons"])
        self.assertEqual("groove-geometry-v1", assessment["thresholdVersion"])

    def test_shadow_and_shallow_fixture_contact_are_rejected(self) -> None:
        cases = {
            "shadow": polar_fixture(45.0, start_row=10, end_row=55),
            "fixture": polar_fixture(45.0, start_row=68, end_row=80, fan_out_deg=15.0, center_drift_deg=10.0),
        }
        for name, polar in cases.items():
            with self.subTest(name=name):
                result = recognize_grooves(
                    polar, [candidate("candidate-001", 45.0)], 180.0, 120.0,
                    DEFAULT_GROOVE_RECOGNITION_CONFIG, 1,
                )
                assessment = result["assessments"][0]
                self.assertFalse(assessment["accepted"])
                self.assertEqual("failed", result["status"])
                self.assertTrue(assessment["rejectionReasons"])

    def test_multiple_and_wraparound_grooves_are_accepted(self) -> None:
        polar = polar_fixture(0.0)
        second = polar_fixture(175.0)
        polar = np.minimum(polar, second)
        result = recognize_grooves(
            polar, [candidate("candidate-001", 0.0), candidate("candidate-002", 175.0)],
            180.0, 120.0, DEFAULT_GROOVE_RECOGNITION_CONFIG, 2,
        )
        self.assertEqual("accepted", result["status"])
        self.assertEqual(["candidate-001", "candidate-002"], result["acceptedCandidateIds"])
        self.assertTrue(candidate("candidate-001", 0.0).wraps_boundary)

    def test_weak_candidate_can_be_ambiguous_and_never_fills_required_count(self) -> None:
        config = {**DEFAULT_GROOVE_RECOGNITION_CONFIG, "min_groove_score": 0.95, "ambiguity_margin": 0.08}
        result = recognize_grooves(
            polar_fixture(90.0), [candidate("candidate-001", 90.0)], 180.0, 120.0, config, 1,
        )
        self.assertEqual("ambiguous", result["status"])
        self.assertFalse(result["assessments"][0]["accepted"])
        self.assertEqual([], result["acceptedCandidateIds"])
        insufficient = recognize_grooves(
            polar_fixture(90.0), [candidate("candidate-001", 90.0)], 180.0, 120.0,
            DEFAULT_GROOVE_RECOGNITION_CONFIG, 2,
        )
        self.assertEqual("failed", insufficient["status"])


if __name__ == "__main__":
    unittest.main()
