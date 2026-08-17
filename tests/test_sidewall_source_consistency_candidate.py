from __future__ import annotations

import copy
import unittest

from algorithms.slot_pose.sidewall_consistency_candidate import (
    DEFAULT_SIDEWALL_CONSISTENCY_CANDIDATE_CONFIG,
    assess_sidewall_consistency_candidate,
    merged_sidewall_consistency_candidate_config,
)


def _source(*, endpoint: float = 0.02, failed: list[str] | None = None) -> dict:
    failed = ["edge_contrast_asymmetry"] if failed is None else failed
    check_ids = ["edge_contrast_asymmetry", "edge_gradient_asymmetry", "normalized_profile_dissimilar",
                 "normalized_profile_uncorrelated", "radial_coverage_inconsistent", "endpoint_structure_inconsistent"]
    return {"status": "rejected", "metrics": {"endpointStructureDifference": endpoint},
            "failedChecks": failed,
            "checks": [{"checkId": check_id, "passed": check_id not in failed} for check_id in check_ids]}


class SidewallSourceConsistencyCandidateTests(unittest.TestCase):
    def test_supports_contrast_only_with_strict_endpoint_structure(self) -> None:
        config = copy.deepcopy(DEFAULT_SIDEWALL_CONSISTENCY_CANDIDATE_CONFIG)
        config["enabled"] = True
        result = assess_sidewall_consistency_candidate(_source(endpoint=0.0229), config)
        self.assertEqual("CANDIDATE_SUPPORTED", result["status"])
        self.assertFalse(result["authoritative"])
        self.assertFalse(result["posePromotionAllowed"])
        self.assertFalse(result["manualTruthAppliedAtRuntime"])
        self.assertTrue(result["developmentOnly"])

    def test_rejects_known_mixed_pair_and_multiple_failure(self) -> None:
        config = {**DEFAULT_SIDEWALL_CONSISTENCY_CANDIDATE_CONFIG, "enabled": True}
        self.assertEqual("CANDIDATE_REJECTED",
                         assess_sidewall_consistency_candidate(_source(endpoint=0.076), config)["status"])
        self.assertEqual("CANDIDATE_REJECTED", assess_sidewall_consistency_candidate(
            _source(failed=["edge_contrast_asymmetry", "edge_gradient_asymmetry"]), config)["status"])

    def test_missing_or_disabled_does_not_evaluate(self) -> None:
        self.assertIsNone(assess_sidewall_consistency_candidate(_source(), None))
        self.assertIsNone(assess_sidewall_consistency_candidate(
            _source(), DEFAULT_SIDEWALL_CONSISTENCY_CANDIDATE_CONFIG))
        incomplete = _source()
        incomplete["metrics"] = {}
        config = {**DEFAULT_SIDEWALL_CONSISTENCY_CANDIDATE_CONFIG, "enabled": True}
        self.assertEqual("NOT_EVALUATED", assess_sidewall_consistency_candidate(incomplete, config)["status"])

    def test_configuration_is_strict_and_development_only(self) -> None:
        merged = merged_sidewall_consistency_candidate_config({"enabled": True})
        self.assertEqual("sidewall-source-consistency-candidate/1", merged["schema_version"])
        for key, value in (("max_endpoint_structure_difference", 1.1), ("development_only", False)):
            with self.subTest(key=key):
                with self.assertRaises(ValueError):
                    merged_sidewall_consistency_candidate_config({key: value})


if __name__ == "__main__":
    unittest.main()
