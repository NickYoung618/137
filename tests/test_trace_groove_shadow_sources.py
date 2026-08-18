from __future__ import annotations

import json
import unittest

from tools.trace_groove_shadow_sources import (
    fixture_screening_counts, normalize_terminal_stage, trace_failure,
    validate_acceptance_manifest,
)


def payload(code: str, stage: str, *, raw: int, accepted: list[str], polar: float = 4.0) -> dict:
    assessments = [
        {
            "candidateId": f"candidate-{index + 1:03d}",
            "accepted": f"candidate-{index + 1:03d}" in accepted,
            "rejectionReasons": [] if f"candidate-{index + 1:03d}" in accepted else ["width_variation_too_high"],
            "grooveScore": 0.8,
        }
        for index in range(raw)
    ]
    return {
        "taskId": "task",
        "image": {"sha256": "a" * 64, "bytes": 10},
        "algorithm": {"configSha256": "b" * 64},
        "result": {
            "valid": False, "currentAngleDeg": None, "correctionRawDeg": None,
            "correctionDeg": None, "imageFrameCorrectionDeg": None,
            "rotationDirection": None, "mechanicalCorrectionDeg": None,
            "plcCommand": None, "plcExecutionAuthoritative": False,
        },
        "error": {"code": code, "stage": stage},
        "diagnostics": {
            "quality": {"polarScore": polar, "thresholds": {"min_polar_score": 3.0}},
            "grooveRecognition": {
                "rawCandidateCount": raw, "acceptedCount": len(accepted),
                "acceptedCandidateIds": accepted, "assessments": assessments,
            },
            "grooveRefinement": None,
            "grooveSourceConsistency": None,
        },
    }


class GrooveShadowTraceTests(unittest.TestCase):
    def test_fixture_screening_summary_distinguishes_lower_false_source_from_upper_risk(self) -> None:
        diagnostics = {
            "fixtureCandidateSourceScreening": {
                "candidates": [
                    {"candidateId": "a", "disposition": "LOWER_FIXTURE_FALSE_SOURCE"},
                    {"candidateId": "b", "disposition": "UPPER_FIXTURE_MIXED_OR_OCCLUDED_RISK"},
                    {"candidateId": "c", "disposition": "UPPER_FIXTURE_MIXED_OR_OCCLUDED_RISK"},
                ]
            }
        }
        self.assertEqual(
            {
                "LOWER_FIXTURE_FALSE_SOURCE": 1,
                "UPPER_FIXTURE_MIXED_OR_OCCLUDED_RISK": 2,
            },
            fixture_screening_counts(diagnostics),
        )

    def test_acceptance_manifest_requires_physical_separation_labels_and_frozen_hashes(self) -> None:
        manifest = {
            "datasetUse": "independent-acceptance",
            "frozenCodeCommit": "c" * 40,
            "frozenConfigSha256": "d" * 64,
            "physicalGroupingAuthority": "project-owner",
            "physicalGroupingProvenance": "new-parts-frozen-before-run",
            "images": [{
                "imageId": "new-part-101:0001",
                "sampleId": "new-part-101", "relativePath": "new/001.bmp",
                "sha256": "e" * 64,
                "humanSemanticClass": "REAL_GROOVE_COMPLETE_NEAR_FIXTURE_SHADOW",
            }],
        }
        result = validate_acceptance_manifest(
            manifest, observed_physical_ids={"observed-part-001"},
            expected_code_commit="c" * 40, expected_config_sha256="d" * 64,
        )
        self.assertEqual(1, result["imageCount"])
        self.assertTrue(result["physicallySeparated"])
        for mutation, message in (
            (("sampleId", "observed-part-001"), "overlap"),
            (("humanSemanticClass", None), "humanSemanticClass"),
            (("relativePath", "sealed/part-006/x.bmp"), "part-006"),
        ):
            broken = json.loads(json.dumps(manifest))
            key, value = mutation
            broken["images"][0][key] = value
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, message):
                validate_acceptance_manifest(
                    broken, observed_physical_ids={"observed-part-001"},
                    expected_code_commit="c" * 40, expected_config_sha256="d" * 64,
                )
        with self.assertRaisesRegex(ValueError, "code commit"):
            validate_acceptance_manifest(
                manifest, observed_physical_ids={"observed-part-001"},
                expected_code_commit="f" * 40, expected_config_sha256="d" * 64,
            )

    def test_candidate_absence_and_recognition_rejection_are_distinct(self) -> None:
        self.assertEqual(
            "candidate_generation",
            normalize_terminal_stage(payload("GROOVE_RECOGNITION_FAILED", "groove_recognition", raw=0, accepted=[])),
        )
        self.assertEqual(
            "groove_recognition",
            normalize_terminal_stage(payload("GROOVE_RECOGNITION_FAILED", "groove_recognition", raw=2, accepted=[])),
        )

    def test_ambiguous_candidates_are_all_retained_as_not_evaluated(self) -> None:
        item = payload(
            "GROOVE_RECOGNITION_AMBIGUOUS", "groove_recognition",
            raw=3, accepted=["candidate-001", "candidate-002"],
        )
        trace = trace_failure(item, {
            "failure_code": "GROOVE_RECOGNITION_AMBIGUOUS",
            "failure_stage": "groove_recognition", "source_class": "normal",
            "source_relative_path": "hidden.bmp", "task_id": "task",
            "image_sha256": "a" * 64,
        }, None)
        self.assertEqual("groove_ambiguity", trace["terminalStage"])
        accepted = [c for c in trace["candidateEvidence"] if c["coarseAccepted"]]
        self.assertEqual(2, len(accepted))
        self.assertTrue(all(c["physicalRefinementStatus"] == "not_evaluated" for c in accepted))
        self.assertIsNone(trace["humanSemanticClass"])

    def test_quality_failure_retains_local_evidence_and_is_fail_closed(self) -> None:
        item = payload("QUALITY_REJECTED", "quality", raw=2, accepted=["candidate-001"], polar=2.8)
        trace = trace_failure(item, {
            "failure_code": "QUALITY_REJECTED", "failure_stage": "quality",
            "source_class": "bad", "source_relative_path": "hidden.bmp",
            "task_id": "task", "image_sha256": "a" * 64,
        }, None)
        self.assertEqual("polar_quality", trace["terminalStage"])
        self.assertEqual(2.8, trace["polarQuality"]["score"])
        self.assertTrue(trace["safetyOutputsNull"])
        self.assertEqual("partial", trace["candidateEvidenceAvailability"])

    def test_upstream_failure_does_not_invent_candidates(self) -> None:
        item = payload("PHYSICAL_OUTER_CIRCLE_FAILED", "physical_outer_circle", raw=0, accepted=[])
        item["diagnostics"].pop("grooveRecognition")
        trace = trace_failure(item, {
            "failure_code": "PHYSICAL_OUTER_CIRCLE_FAILED", "failure_stage": "physical_outer_circle",
            "source_class": "normal", "source_relative_path": "hidden.bmp",
            "task_id": "task", "image_sha256": "a" * 64,
        }, None)
        self.assertEqual("upstream_outer_circle", trace["terminalStage"])
        self.assertEqual([], trace["candidateEvidence"])
        self.assertEqual("not_evaluated", trace["candidateEvidenceAvailability"])


if __name__ == "__main__":
    unittest.main()
