from __future__ import annotations

import math
import json
import unittest
from pathlib import Path

try:
    import jsonschema
except ImportError:
    jsonschema = None

from algorithms.slot_pose.groove_shadow_discrimination import (
    build_candidate_source_evidence,
    classify_groove_shadow_sources,
    merged_groove_shadow_source_config,
)


def candidate(candidate_id: str, *, refinement: str, source: str,
              mixed: bool = False, value: float = 1.0) -> dict:
    return {
        "candidateId": candidate_id,
        "coarseRecognition": {"status": "accepted", "failedChecks": []},
        "coarseMetrics": {"grooveScore": value},
        "physicalRefinement": {
            "status": refinement,
            "failedChecks": [] if refinement == "accepted" else ["sidewall_consensus_failed"],
        },
        "sourceConsistency": {
            "status": source,
            "failedChecks": [] if source == "accepted" else ["source_profile_mismatch"],
        },
        "mixedOrOccludedEvidence": mixed,
    }


class GrooveShadowDiscriminationTests(unittest.TestCase):
    @unittest.skipIf(jsonschema is None, "jsonschema is optional")
    def test_runtime_diagnostic_matches_strict_schema(self) -> None:
        result = classify_groove_shadow_sources(
            [candidate("real", refinement="accepted", source="accepted"),
             candidate("shadow", refinement="failed", source="not_evaluated")],
            enabled=True, upstream_accepted=True, polar_quality_accepted=True,
            existing_pose_chain_allowed=True, terminal_stage="valid",
            locked_gate_versions={"recognition": "v1"},
        )
        schema = json.loads(
            (Path(__file__).parents[1] / "contracts" / "groove-shadow-source-diagnostic.schema.json")
            .read_text(encoding="utf-8")
        )
        jsonschema.Draft202012Validator(schema).validate(result)

    def test_runtime_evidence_builder_keeps_coarse_physical_and_source_provenance(self) -> None:
        recognition = {"assessments": [
            {"candidateId": "real", "accepted": True, "rejectionReasons": [], "grooveScore": 0.9},
            {"candidateId": "shadow", "accepted": True, "rejectionReasons": [], "grooveScore": 0.8},
        ]}
        resolution = {"attempts": [
            {"candidateId": "real", "refinement": {
                "status": "accepted", "failedChecks": [],
                "startSide": {}, "endSide": {}, "outerCircleIntersections": [{}, {}],
                "sourceConsistency": {"status": "accepted", "failedChecks": [], "metrics": {"profile": 0.1}},
            }},
            {"candidateId": "shadow", "refinement": {
                "status": "failed", "physicalRefinementStatus": "accepted",
                "failedChecks": ["source_consistency:normalized_profile_dissimilar"],
                "sourceConsistency": {"status": "rejected", "failedChecks": ["normalized_profile_dissimilar"]},
            }},
        ]}
        evidence = build_candidate_source_evidence(recognition, resolution=resolution)
        self.assertEqual(["real", "shadow"], [item["candidateId"] for item in evidence])
        self.assertEqual("accepted", evidence[0]["sourceConsistency"]["status"])
        self.assertTrue(evidence[1]["mixedOrOccludedEvidence"])

    def test_config_is_default_off_strict_and_has_no_numeric_thresholds(self) -> None:
        config = merged_groove_shadow_source_config(None)
        self.assertFalse(config["enabled"])
        self.assertEqual(
            {"schema_version", "enabled", "strategy_version"}, set(config)
        )
        with self.assertRaisesRegex(ValueError, "unsupported fields"):
            merged_groove_shadow_source_config({"shadow_score": 0.5})

    def test_unique_survivor_with_explicitly_rejected_competitor_is_complete(self) -> None:
        result = classify_groove_shadow_sources(
            [candidate("real", refinement="accepted", source="accepted"),
             candidate("shadow", refinement="failed", source="not_evaluated")],
            enabled=True, upstream_accepted=True, polar_quality_accepted=True,
            existing_pose_chain_allowed=True, terminal_stage="valid",
        )
        self.assertEqual("accepted", result["status"])
        self.assertEqual("REAL_GROOVE_COMPLETE_NEAR_FIXTURE_SHADOW", result["classification"])
        self.assertEqual("real", result["selectedCandidateId"])
        self.assertTrue(result["poseChainAllowed"])

    def test_low_polar_keeps_local_class_but_never_releases_pose(self) -> None:
        result = classify_groove_shadow_sources(
            [candidate("real", refinement="accepted", source="accepted"),
             candidate("shadow", refinement="failed", source="not_evaluated")],
            enabled=True, upstream_accepted=True, polar_quality_accepted=False,
            existing_pose_chain_allowed=False, terminal_stage="polar_quality",
        )
        self.assertEqual("REAL_GROOVE_COMPLETE_NEAR_FIXTURE_SHADOW", result["classification"])
        self.assertEqual("rejected", result["status"])
        self.assertFalse(result["poseChainAllowed"])
        self.assertIn("global_polar_quality_failed", result["failedChecks"])

    def test_mixed_multiple_missing_and_overflow_fail_closed(self) -> None:
        mixed = classify_groove_shadow_sources(
            [candidate("x", refinement="failed", source="not_evaluated", mixed=True)],
            enabled=True, upstream_accepted=True, polar_quality_accepted=True,
            existing_pose_chain_allowed=False, terminal_stage="groove_refinement",
        )
        self.assertEqual("REAL_GROOVE_SHADOW_MIXED_OR_OCCLUDED", mixed["classification"])
        self.assertFalse(mixed["poseChainAllowed"])

        multiple = classify_groove_shadow_sources(
            [candidate("a", refinement="accepted", source="accepted"),
             candidate("b", refinement="accepted", source="accepted")],
            enabled=True, upstream_accepted=True, polar_quality_accepted=True,
            existing_pose_chain_allowed=False, terminal_stage="groove_ambiguity",
        )
        self.assertEqual("INDETERMINATE", multiple["classification"])
        self.assertIn("multiple_physical_survivors", multiple["failedChecks"])

        missing = classify_groove_shadow_sources(
            [candidate("a", refinement="not_evaluated", source="not_evaluated")],
            enabled=True, upstream_accepted=True, polar_quality_accepted=True,
            existing_pose_chain_allowed=False, terminal_stage="groove_ambiguity",
        )
        self.assertEqual("not_evaluated", missing["status"])
        self.assertFalse(missing["poseChainAllowed"])

        overflow = classify_groove_shadow_sources(
            [candidate(str(i), refinement="failed", source="not_evaluated") for i in range(4)],
            enabled=True, upstream_accepted=True, polar_quality_accepted=True,
            existing_pose_chain_allowed=False, terminal_stage="groove_ambiguity",
        )
        self.assertIn("candidate_capacity_exceeded", overflow["failedChecks"])

    def test_reordering_id_and_rotation_metadata_do_not_change_decision(self) -> None:
        evidence = [candidate("a", refinement="accepted", source="accepted"),
                    candidate("b", refinement="failed", source="not_evaluated")]
        first = classify_groove_shadow_sources(
            evidence, enabled=True, upstream_accepted=True, polar_quality_accepted=True,
            existing_pose_chain_allowed=True, terminal_stage="valid",
        )
        renamed = [{
            **item,
            "candidateId": {"a": "z", "b": "y"}[item["candidateId"]],
            "rotationDiagnosticDeg": 137.0,
            "coarseMetrics": {
                key: (value * 0.8 if isinstance(value, (int, float)) else value)
                for key, value in item["coarseMetrics"].items()
            },
        } for item in reversed(evidence)]
        second = classify_groove_shadow_sources(
            renamed, enabled=True, upstream_accepted=True, polar_quality_accepted=True,
            existing_pose_chain_allowed=True, terminal_stage="valid",
        )
        for field in ("status", "classification", "poseChainAllowed", "passedChecks", "failedChecks"):
            self.assertEqual(first[field], second[field])

    def test_nonfinite_evidence_is_indeterminate(self) -> None:
        bad = candidate("a", refinement="accepted", source="accepted", value=math.nan)
        result = classify_groove_shadow_sources(
            [bad, candidate("b", refinement="failed", source="not_evaluated")],
            enabled=True, upstream_accepted=True, polar_quality_accepted=True,
            existing_pose_chain_allowed=True, terminal_stage="valid",
        )
        self.assertEqual("INDETERMINATE", result["classification"])
        self.assertFalse(result["poseChainAllowed"])
        self.assertIn("nonfinite_candidate_evidence", result["failedChecks"])


if __name__ == "__main__":
    unittest.main()
