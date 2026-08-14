from __future__ import annotations

import unittest

from algorithms.slot_pose.angular_profile import NotchCandidate
from algorithms.slot_pose.role_assignment import assign_roles, validate_role_config


def candidate(identifier: str, center: float) -> NotchCandidate:
    return NotchCandidate(identifier, center, 5.0, center - 5.0, center + 5.0, False, 80.0, 100.0, 1)


def role_config(datum_definition: str = "opposed_candidates_axis") -> dict:
    assignments = {
        "datum_primary": {"expected_reference_azimuth_deg": 90.0, "max_deviation_deg": 12.0},
        "target_left": {"expected_reference_azimuth_deg": 175.0, "max_deviation_deg": 12.0},
    }
    if datum_definition == "opposed_candidates_axis":
        assignments["datum_secondary"] = {"expected_reference_azimuth_deg": 270.0, "max_deviation_deg": 12.0}
    return {
        "datum_definition": datum_definition,
        "assignments": assignments,
        "min_score_margin": 0.1,
        "max_opposition_error_deg": 8.0,
        "drawing_nominal_angle_deg": 85.0,
        "drawing_tolerance_deg": 5.0,
    }


class RoleAssignmentTests(unittest.TestCase):
    def test_extra_candidates_do_not_force_exactly_two(self) -> None:
        result = assign_roles([
            candidate("top", 90.0), candidate("target", 175.0), candidate("bottom", 270.0),
            candidate("unrelated", 330.0),
        ], role_config())
        self.assertTrue(result["unique"], result)
        self.assertEqual({
            "datum_primary": "top", "target_left": "target", "datum_secondary": "bottom",
        }, result["selectedRoleCandidateIds"])
        self.assertAlmostEqual(85.0, result["drawingAngle"]["includedAngleDeg"])
        self.assertEqual("NOT_EVALUATED", result["drawingAngle"]["toleranceStatus"])

    def test_expected_windows_follow_global_rotation_across_wrap(self) -> None:
        result = assign_roles([
            candidate("top", 269.0), candidate("target", 354.0), candidate("bottom", 89.0),
        ], role_config(), expected_offset_deg=179.0)
        self.assertTrue(result["unique"], result)
        self.assertAlmostEqual(85.0, result["drawingAngle"]["clockwiseAngleDeg"])

    def test_ambiguous_target_and_missing_role_fail_closed(self) -> None:
        ambiguous = assign_roles([
            candidate("top", 90.0), candidate("target-a", 174.0), candidate("target-b", 176.0),
            candidate("bottom", 270.0),
        ], role_config())
        self.assertFalse(ambiguous["unique"])
        self.assertIn("role_assignment_not_unique", ambiguous["failedChecks"])
        missing = assign_roles([candidate("top", 90.0), candidate("target", 175.0)], role_config())
        self.assertFalse(missing["unique"])
        self.assertIn("candidate_count_below_role_count", missing["failedChecks"])

    def test_datum_definition_is_explicit_and_opposition_is_checked(self) -> None:
        single = assign_roles([candidate("top", 90.0), candidate("target", 175.0)], role_config("single_candidate_ray"))
        self.assertTrue(single["unique"], single)
        opposed = assign_roles([
            candidate("top", 90.0), candidate("target", 175.0), candidate("bottom", 260.0),
        ], role_config())
        self.assertFalse(opposed["unique"])
        self.assertIn("datum_opposition", opposed["failedChecks"])

    def test_invalid_role_configuration_is_rejected(self) -> None:
        config = role_config()
        del config["assignments"]["target_left"]
        with self.assertRaises(ValueError):
            validate_role_config(config)


if __name__ == "__main__":
    unittest.main()
