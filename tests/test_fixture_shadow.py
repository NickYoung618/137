from __future__ import annotations

import unittest

import numpy as np

from algorithms.slot_pose.fixture_shadow import (
    DEFAULT_FIXTURE_SHADOW_CONFIG,
    analyze_fixture_shadows,
    build_fixture_overlap_evaluation_candidates,
    merged_fixture_shadow_config,
)
from tests.test_slot_pose_contract import minimal_single_groove_config
from tools.prepare_slot_pose_fixture_shadow_config import prepare


def candidate(identifier: str, center: float, *, half: float = 11.0,
              prominence: float = 100.0, area: float = 300.0) -> dict:
    return {
        "candidateId": identifier,
        "centerDeg": center % 360.0,
        "halfWidthDeg": half,
        "startDeg": (center - half) % 360.0,
        "endDeg": (center + half) % 360.0,
        "wrapsBoundary": (center - half) % 360.0 > (center + half) % 360.0,
        "prominence": prominence,
        "deficitArea": area,
        "rank": 1,
    }


def profile_with_runs(runs: list[tuple[float, float, float]], count: int = 720) -> np.ndarray:
    angles = np.arange(count, dtype=float) * 360.0 / count
    values = np.full(count, 205.0)
    for center, half, depth in runs:
        delta = np.abs((angles - center + 180.0) % 360.0 - 180.0)
        values -= depth * np.exp(-0.5 * (delta / max(half / 2.5, 0.25)) ** 2)
    return values


class FixtureShadowTests(unittest.TestCase):
    def enabled(self, **updates: object) -> dict:
        return merged_fixture_shadow_config({
            **DEFAULT_FIXTURE_SHADOW_CONFIG,
            "enabled": True,
            **updates,
        })

    def with_synthetic_reference(self, **updates: object) -> dict:
        raw = [
            candidate("shadow-a", 31.4, area=310.0),
            candidate("shadow-b", 327.7, area=280.0),
        ]
        pure = analyze_fixture_shadows(
            profile_with_runs([(31.4, 11.0, 95.0), (327.7, 11.0, 92.0)]),
            raw,
            self.enabled(),
        )
        templates = []
        for template in DEFAULT_FIXTURE_SHADOW_CONFIG["templates"]:
            match = next(
                item for item in pure["candidateMatches"]
                if item["templateId"] == template["template_id"]
                and item["status"] == "matched"
            )
            templates.append({
                **template,
                "intensity_profile": match["normalizedIntensityProfile"],
                "gradient_profile": match["normalizedGradientProfile"],
                "template_source": "synthetic-test-only",
                "human_verified": True,
            })
        return self.enabled(
            enable_overlap_decomposition=True,
            min_residual_level=0.05,
            min_residual_width_deg=0.5,
            templates=templates,
            **updates,
        )

    def test_fixed_angles_are_evidence_not_an_ignore_mask(self) -> None:
        raw = [
            candidate("candidate-a", 31.4, area=310.0),
            candidate("candidate-groove", 31.8, half=7.0, prominence=150.0, area=1400.0),
            candidate("candidate-b", 327.7, area=280.0),
        ]
        result = analyze_fixture_shadows(
            profile_with_runs([(31.4, 11.0, 95.0), (327.7, 11.0, 92.0)]),
            raw,
            self.enabled(),
        )
        self.assertEqual([item["candidateId"] for item in raw], result["rawCandidateIds"])
        self.assertEqual(len(raw), result["rawCandidateCount"])
        self.assertFalse(result["candidateSuppressionApplied"])
        self.assertEqual([], result["suppressedCandidateIds"])
        self.assertIn("candidate-groove", result["rawCandidateIds"])

    def test_pair_is_complete_only_with_two_distinct_similar_matches(self) -> None:
        raw = [
            candidate("shadow-a", 31.4, area=310.0),
            candidate("groove", 210.0, half=8.0, prominence=150.0, area=1450.0),
            candidate("shadow-b", 327.7, area=280.0),
        ]
        result = analyze_fixture_shadows(
            profile_with_runs([(31.4, 11.0, 95.0), (210.0, 8.0, 145.0), (327.7, 11.0, 92.0)]),
            raw,
            self.enabled(),
        )
        self.assertEqual("complete", result["pairEvidence"]["status"], result)
        self.assertEqual({"shadow-a", "shadow-b"}, set(result["pairEvidence"]["selectedCandidateIds"]))
        for item in result["candidateMatches"]:
            self.assertIn("rawIntensityProfile", item)
            self.assertIn("normalizedIntensityProfile", item)
            self.assertIn("normalizedGradientProfile", item)

        missing = analyze_fixture_shadows(
            profile_with_runs([(31.4, 11.0, 95.0)]),
            [raw[0]],
            self.enabled(),
        )
        self.assertEqual("incomplete", missing["pairEvidence"]["status"])
        self.assertIsNone(missing["pairEvidence"]["selectedCandidateIds"])

    def test_overlap_decomposition_requires_reference_profiles_and_is_bounded(self) -> None:
        raw = [candidate("merged", 31.4, half=18.0, prominence=155.0, area=1500.0)]
        no_reference = self.enabled(enable_overlap_decomposition=False)
        result = analyze_fixture_shadows(
            profile_with_runs([(31.4, 11.0, 95.0), (42.0, 6.0, 130.0)]),
            raw,
            no_reference,
        )
        self.assertEqual("disabled", result["overlapDecomposition"]["status"])
        self.assertEqual([], result["residualCandidates"])
        self.assertEqual(["merged"], result["rawCandidateIds"])

    def test_overlap_residual_near_both_fixture_angles_is_not_masked(self) -> None:
        raw = [
            candidate("shadow-a", 31.4, area=310.0),
            candidate("shadow-b", 327.7, area=280.0),
        ]
        for groove_center in (36.0, 334.0):
            with self.subTest(groove_center=groove_center):
                result = analyze_fixture_shadows(
                    profile_with_runs([
                        (31.4, 11.0, 95.0),
                        (327.7, 11.0, 92.0),
                        (groove_center, 2.0, 80.0),
                    ]),
                    raw,
                    self.with_synthetic_reference(),
                )
                self.assertEqual("unique", result["overlapDecomposition"]["status"], result)
                self.assertEqual(1, len(result["residualCandidates"]))
                self.assertEqual(["shadow-a", "shadow-b"], result["rawCandidateIds"])
                residual = result["residualCandidates"][0]
                self.assertIn("hypothesisSource", residual)
                self.assertEqual("fixture_plus_groove_residual", residual["hypothesisSource"]["modelKind"])
                evaluation = build_fixture_overlap_evaluation_candidates(raw, result)
                self.assertTrue(evaluation["replacementApplied"])
                self.assertIn(residual["candidateId"], {
                    item["candidateId"] for item in evaluation["candidates"]
                })
                self.assertNotIn(
                    residual["hypothesisSource"]["sourceCandidateId"],
                    {item["candidateId"] for item in evaluation["candidates"]},
                )

    def test_overlap_zero_multiple_and_overflow_do_not_emit_residual_candidates(self) -> None:
        raw = [
            candidate("shadow-a", 31.4, area=310.0),
            candidate("shadow-b", 327.7, area=280.0),
        ]
        pure = analyze_fixture_shadows(
            profile_with_runs([(31.4, 11.0, 95.0), (327.7, 11.0, 92.0)]),
            raw,
            self.with_synthetic_reference(),
        )
        self.assertEqual("none", pure["overlapDecomposition"]["status"])
        self.assertEqual([], pure["residualCandidates"])

        missing_pair = analyze_fixture_shadows(
            profile_with_runs([(31.4, 11.0, 95.0), (36.0, 2.0, 80.0)]),
            [raw[0]],
            self.with_synthetic_reference(),
        )
        self.assertEqual("template_incomplete", missing_pair["overlapDecomposition"]["status"])
        self.assertEqual([], missing_pair["residualCandidates"])

        multiple = analyze_fixture_shadows(
            profile_with_runs([
                (31.4, 11.0, 95.0), (327.7, 11.0, 92.0),
                (36.0, 2.0, 80.0), (334.0, 2.0, 80.0),
            ]),
            raw,
            self.with_synthetic_reference(),
        )
        self.assertEqual("ambiguous", multiple["overlapDecomposition"]["status"])
        self.assertEqual([], multiple["residualCandidates"])
        evaluation = build_fixture_overlap_evaluation_candidates(raw, multiple)
        self.assertFalse(evaluation["replacementApplied"])
        self.assertEqual(["shadow-a", "shadow-b"], [
            item["candidateId"] for item in evaluation["candidates"]
        ])

        overflow = analyze_fixture_shadows(
            profile_with_runs([
                (31.4, 11.0, 95.0), (327.7, 11.0, 92.0),
                (36.0, 2.0, 80.0), (334.0, 2.0, 80.0),
            ]),
            raw,
            self.with_synthetic_reference(max_overlap_hypotheses=1),
        )
        self.assertEqual("overflow", overflow["overlapDecomposition"]["status"])
        self.assertEqual([], overflow["residualCandidates"])

    def test_invalid_reference_profile_and_hypothesis_limit_are_rejected(self) -> None:
        invalid = {
            **DEFAULT_FIXTURE_SHADOW_CONFIG,
            "enabled": True,
            "max_overlap_hypotheses": 99,
        }
        with self.assertRaisesRegex(ValueError, "max_overlap_hypotheses"):
            merged_fixture_shadow_config(invalid)
        mismatched = {
            **DEFAULT_FIXTURE_SHADOW_CONFIG,
            "enabled": True,
            "templates": [
                {**DEFAULT_FIXTURE_SHADOW_CONFIG["templates"][0], "intensity_profile": [0.0, 1.0]},
                DEFAULT_FIXTURE_SHADOW_CONFIG["templates"][1],
            ],
        }
        with self.assertRaisesRegex(ValueError, "profile"):
            merged_fixture_shadow_config(mismatched)
        unverified = self.with_synthetic_reference()
        unverified["templates"][0]["human_verified"] = False
        with self.assertRaisesRegex(ValueError, "human-verified"):
            merged_fixture_shadow_config(unverified)

    def test_external_materializer_enables_evidence_and_source_gate_but_not_subtraction(self) -> None:
        base = minimal_single_groove_config()
        configured = prepare(base)
        self.assertNotIn("fixture_shadow_model", base["detector"])
        self.assertTrue(configured["detector"]["fixture_shadow_model"]["enabled"])
        self.assertFalse(
            configured["detector"]["fixture_shadow_model"]["enable_overlap_decomposition"]
        )
        self.assertTrue(configured["detector"]["sidewall_source_consistency"]["enabled"])
        self.assertEqual(
            "groove-sidewall-subpixel-v2",
            configured["detector"]["groove_refinement"]["threshold_version"],
        )


if __name__ == "__main__":
    unittest.main()
