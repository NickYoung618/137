from __future__ import annotations

import copy
import json
import math
import statistics
import time
import unittest
from pathlib import Path

try:
    import jsonschema
except ImportError:
    jsonschema = None

from algorithms.slot_pose.polar_quality_adjudication import (
    DEFAULT_POLAR_QUALITY_ADJUDICATION_CONFIG,
    adjudicate_polar_quality,
    merged_polar_quality_adjudication_config,
)


def complete_evidence(*, score: float = 2.88, failures: list[str] | None = None) -> dict:
    failures = ["polar_score"] if failures is None else list(failures)
    return {
        "quality": {
            "polarScore": score,
            "thresholds": {"min_polar_score": 3.0},
            "failedChecks": failures,
        },
        "physicalOuterCircle": {
            "status": "accepted",
            "failedChecks": [],
            "edgeFamilySelection": {
                "status": "selected",
                "qualifiedFamilyCount": 1,
                "selectedFamilyId": "edge-family-001",
                "failedChecks": [],
            },
        },
        "grooveRecognition": {
            "status": "accepted",
            "acceptedCount": 1,
            "acceptedCandidateIds": ["candidate-005"],
        },
        "grooveRefinement": {
            "status": "accepted",
            "coarseCandidateId": "candidate-005",
            "failedChecks": [],
            "startSide": {
                "points": [[1.0, 2.0], [2.0, 3.0]],
                "supportPointCount": 2,
            },
            "endSide": {
                "points": [[4.0, 5.0], [5.0, 6.0]],
                "supportPointCount": 2,
            },
            "outerCircleIntersections": [
                {"x": 10.0, "y": 20.0},
                {"x": 30.0, "y": 40.0},
            ],
            "sourceConsistency": {
                "status": "accepted",
                "failedChecks": [],
            },
            "fixtureSourceExclusion": {
                "schemaVersion": "fixture-groove-source-exclusion/1",
                "status": "verified",
                "fixtureBodiesVerified": True,
                "twoSidewallsComplete": True,
                "grooveFloorEvidence": {
                    "schemaVersion": "groove-floor-evidence/1",
                    "status": "accepted",
                    "trackCount": 5,
                    "acceptedTrackCount": 5,
                    "fixedAngleApplied": False,
                    "manualTruthAppliedAtRuntime": False,
                    "failedChecks": [],
                },
                "uContourComplete": True,
                "fixtureSourceExcluded": True,
                "candidateSelectionUsedFixedAngle": False,
                "failedChecks": [],
            },
        },
        "singleGroovePose": {
            "status": "accepted",
            "acceptedGrooveCount": 1,
            "geometryValid": True,
            "role": {
                "status": "unique_detected",
                "candidateId": "candidate-005",
            },
            "imageMeasurement": {
                "azimuthDeg": 262.8,
                "midpointSource": "subpixel_sidewall_outer_circle_intersections",
            },
        },
    }


class PolarQualityAdjudicationTests(unittest.TestCase):
    def enabled_config(self) -> dict:
        return {**DEFAULT_POLAR_QUALITY_ADJUDICATION_CONFIG, "enabled": True}

    def test_sole_polar_failure_with_complete_proof_is_overridden_without_mutation(self) -> None:
        evidence = complete_evidence()
        before = copy.deepcopy(evidence)
        result = adjudicate_polar_quality(evidence, self.enabled_config())
        self.assertEqual(before, evidence)
        self.assertEqual("ACCEPTED_OVERRIDE", result["decision"])
        self.assertEqual(["polar_score"], result["originalFailedChecks"])
        self.assertEqual([], result["effectiveFailedChecks"])
        self.assertEqual(2.88, result["originalPolarScore"])
        self.assertEqual(3.0, result["originalPolarThreshold"])
        self.assertTrue(result["imagePoseReleaseAllowed"])
        self.assertTrue(all(item["passed"] for item in result["checks"]))
        self.assertFalse(result["plcAllowed"])
        self.assertFalse(result["manualTruthAppliedAtRuntime"])
        self.assertFalse(result["fixedAngleApplied"])

    def test_no_failure_and_threshold_equality_are_not_needed(self) -> None:
        for evidence in (
            complete_evidence(score=3.1, failures=[]),
            complete_evidence(score=3.0, failures=[]),
        ):
            with self.subTest(score=evidence["quality"]["polarScore"]):
                result = adjudicate_polar_quality(evidence, self.enabled_config())
                self.assertEqual("NOT_NEEDED", result["decision"])
                self.assertEqual([], result["effectiveFailedChecks"])
                self.assertFalse(result["imagePoseReleaseAllowed"])

    def test_disabled_or_omitted_config_preserves_legacy_no_diagnostic(self) -> None:
        evidence = complete_evidence()
        self.assertIsNone(adjudicate_polar_quality(evidence, None))
        self.assertIsNone(adjudicate_polar_quality(
            evidence, DEFAULT_POLAR_QUALITY_ADJUDICATION_CONFIG,
        ))

    def test_configuration_is_strict_default_off_and_development_only(self) -> None:
        merged = merged_polar_quality_adjudication_config(None)
        self.assertFalse(merged["enabled"])
        for mutation in (
            {"unexpected": True},
            {"enabled": 1},
            {"development_only": False},
            {"schema_version": "polar-quality-adjudication/2"},
            {"strategy_version": "unknown"},
        ):
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                merged_polar_quality_adjudication_config(mutation)

    def test_second_failure_is_authoritative(self) -> None:
        evidence = complete_evidence(failures=["polar_score", "scale"])
        result = adjudicate_polar_quality(evidence, self.enabled_config())
        self.assertEqual("REJECTED", result["decision"])
        self.assertEqual(["polar_score", "scale"], result["effectiveFailedChecks"])
        self.assertIn("sole_polar_failure", result["failedChecks"])
        self.assertFalse(result["imagePoseReleaseAllowed"])

    def test_each_required_proof_fails_closed(self) -> None:
        mutations = {
            "circle": lambda e: e["physicalOuterCircle"].update(status="failed"),
            "family": lambda e: e["physicalOuterCircle"]["edgeFamilySelection"].update(
                qualifiedFamilyCount=2,
            ),
            "recognition": lambda e: e["grooveRecognition"].update(acceptedCount=2),
            "pose": lambda e: e["singleGroovePose"].update(status="failed"),
            "start_wall": lambda e: e["grooveRefinement"].pop("startSide"),
            "end_wall": lambda e: e["grooveRefinement"].pop("endSide"),
            "endpoints": lambda e: e["grooveRefinement"].update(
                outerCircleIntersections=[{"x": 1.0, "y": math.nan}],
            ),
            "floor": lambda e: e["grooveRefinement"]["fixtureSourceExclusion"][
                "grooveFloorEvidence"
            ].update(acceptedTrackCount=4),
            "source": lambda e: e["grooveRefinement"]["sourceConsistency"].update(
                status="rejected", failedChecks=["edge_contrast_asymmetry"],
            ),
            "fixture": lambda e: e["grooveRefinement"]["fixtureSourceExclusion"].update(
                fixtureSourceExcluded=False,
            ),
            "manual_truth": lambda e: e["grooveRefinement"]["fixtureSourceExclusion"][
                "grooveFloorEvidence"
            ].update(manualTruthAppliedAtRuntime=True),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name):
                evidence = complete_evidence()
                mutate(evidence)
                result = adjudicate_polar_quality(evidence, self.enabled_config())
                self.assertIn(result["decision"], {"REJECTED", "NOT_EVALUATED"})
                self.assertEqual(["polar_score"], result["effectiveFailedChecks"])
                self.assertFalse(result["imagePoseReleaseAllowed"])
                self.assertTrue(result["failedChecks"])

    def test_reordered_mapping_fields_are_deterministic(self) -> None:
        evidence = complete_evidence()
        reordered = {key: evidence[key] for key in reversed(list(evidence))}
        first = adjudicate_polar_quality(evidence, self.enabled_config())
        second = adjudicate_polar_quality(reordered, self.enabled_config())
        self.assertEqual(first, second)

    def test_decision_is_constant_size_and_has_no_image_dependency(self) -> None:
        source = (
            Path(__file__).resolve().parents[1]
            / "algorithms" / "slot_pose" / "polar_quality_adjudication.py"
        ).read_text(encoding="utf-8")
        for forbidden in (
            "import numpy", "from PIL", "import cv2", "polar_resample(",
            "load_detection_gray(", "robust_fit_circle(", "refine_groove_opening(",
        ):
            self.assertNotIn(forbidden, source)

        evidence = complete_evidence()
        config = self.enabled_config()
        elapsed = []
        for _ in range(500):
            started = time.perf_counter_ns()
            adjudicate_polar_quality(evidence, config)
            elapsed.append((time.perf_counter_ns() - started) / 1_000_000.0)
        p95 = statistics.quantiles(elapsed, n=100, method="inclusive")[94]
        self.assertLessEqual(p95, 5.0)

    def test_malformed_score_failure_relationship_is_not_evaluated(self) -> None:
        for score, failures in (
            (math.nan, ["polar_score"]),
            (3.1, ["polar_score"]),
            (2.8, []),
            (2.8, ["polar_score", "polar_score"]),
            (2.8, ["polar_score", 7]),
        ):
            with self.subTest(score=score, failures=failures):
                result = adjudicate_polar_quality(
                    complete_evidence(score=score, failures=failures), self.enabled_config(),
                )
                self.assertEqual("NOT_EVALUATED", result["decision"])
                self.assertFalse(result["imagePoseReleaseAllowed"])
                self.assertTrue(result["effectiveFailedChecks"])

        missing = adjudicate_polar_quality(None, self.enabled_config())
        self.assertEqual("NOT_EVALUATED", missing["decision"])
        self.assertEqual(
            ["polar_quality_adjudication_not_evaluated"],
            missing["effectiveFailedChecks"],
        )

    @unittest.skipIf(jsonschema is None, "jsonschema is installed by the explicit Schema gate")
    def test_output_matches_dedicated_schema(self) -> None:
        schema = json.loads(
            (Path(__file__).resolve().parents[1] / "contracts"
             / "polar-quality-adjudication-diagnostic.schema.json").read_text(
                encoding="utf-8",
            )
        )
        jsonschema.Draft202012Validator.check_schema(schema)
        for evidence in (
            complete_evidence(),
            complete_evidence(score=3.0, failures=[]),
            complete_evidence(failures=["polar_score", "scale"]),
            complete_evidence(score=math.nan),
        ):
            jsonschema.validate(
                adjudicate_polar_quality(evidence, self.enabled_config()), schema,
            )


if __name__ == "__main__":
    unittest.main()
