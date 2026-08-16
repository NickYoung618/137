from __future__ import annotations

import unittest

from algorithms.slot_pose.sidewall_consistency import (
    DEFAULT_SIDEWALL_CONSISTENCY_CONFIG,
    assess_sidewall_source_consistency,
    merged_sidewall_consistency_config,
)


def side(contrast: float, gradient: float, profile: list[float],
         *, coverage: float = 0.9, raw_shift: float = 0.0) -> dict:
    raw = [40.0 + 170.0 * value + raw_shift for value in profile]
    return {
        "edgeContrastMedian": contrast,
        "edgeGradientMedianPerPx": gradient,
        "lineLongitudinalCoverage": coverage,
        "profileEvidence": {
            "radialPositionsNormalized": [0.0, 0.25, 0.5, 0.75, 1.0],
            "edgeContrastProfile": [contrast] * 5,
            "edgeGradientProfile": [gradient] * 5,
            "rawCanonicalGrayProfile": raw,
            "normalizedCanonicalGrayProfile": profile,
            "metalLevelMedian": 210.0 + raw_shift,
            "grooveLevelMedian": 40.0 + raw_shift,
            "radialCoverage": coverage,
        },
    }


def refinement(start: dict, end: dict) -> dict:
    return {
        "status": "accepted",
        "startSide": start,
        "endSide": end,
        "openingEndpointProfileDeg": [286.0, 309.0],
        "openingWidthDeg": 23.0,
    }


class SidewallSourceConsistencyTests(unittest.TestCase):
    def enabled(self, **updates: object) -> dict:
        return merged_sidewall_consistency_config({
            **DEFAULT_SIDEWALL_CONSISTENCY_CONFIG,
            "enabled": True,
            **updates,
        })

    def test_same_source_profiles_pass_with_auditable_hard_checks(self) -> None:
        profile = [1.0, 0.95, 0.8, 0.45, 0.1, 0.0, 0.0]
        result = assess_sidewall_source_consistency(
            refinement(side(199.0, 25.0, profile), side(201.0, 24.5, profile)),
            self.enabled(),
        )
        self.assertEqual("accepted", result["status"], result)
        self.assertEqual([], result["failedChecks"])
        self.assertIn("contrastNormalizedDifference", result["metrics"])
        self.assertIn("normalizedProfileMae", result["metrics"])
        self.assertTrue(all(check["passed"] for check in result["checks"]))

    def test_part019_mixed_source_contrast_is_rejected_even_when_both_edges_are_strong(self) -> None:
        profile = [1.0, 0.95, 0.8, 0.45, 0.1, 0.0, 0.0]
        result = assess_sidewall_source_consistency(
            refinement(side(194.33, 25.0, profile), side(236.90, 25.5, profile)),
            self.enabled(max_contrast_normalized_difference=0.12),
        )
        self.assertEqual("rejected", result["status"], result)
        self.assertIn("edge_contrast_asymmetry", result["failedChecks"])
        self.assertGreater(result["metrics"]["contrastNormalizedDifference"], 0.12)

    def test_profile_depth_and_endpoint_structure_are_independent_hard_gates(self) -> None:
        falling = [1.0, 0.95, 0.8, 0.45, 0.1, 0.0, 0.0]
        alien = [0.0, 0.0, 0.1, 0.4, 0.8, 0.95, 1.0]
        result = assess_sidewall_source_consistency(
            refinement(
                side(200.0, 25.0, falling, coverage=0.95),
                side(201.0, 25.0, alien, coverage=0.55, raw_shift=35.0),
            ),
            self.enabled(),
        )
        self.assertEqual("rejected", result["status"])
        self.assertIn("normalized_profile_dissimilar", result["failedChecks"])
        self.assertIn("radial_coverage_inconsistent", result["failedChecks"])
        self.assertIn("endpoint_structure_inconsistent", result["failedChecks"])

    def test_disabled_is_backward_compatible_and_invalid_values_are_rejected(self) -> None:
        result = assess_sidewall_source_consistency({}, None)
        self.assertEqual("disabled", result["status"])
        with self.assertRaisesRegex(ValueError, "max_contrast"):
            merged_sidewall_consistency_config({
                **DEFAULT_SIDEWALL_CONSISTENCY_CONFIG,
                "max_contrast_normalized_difference": 1.5,
            })


if __name__ == "__main__":
    unittest.main()
