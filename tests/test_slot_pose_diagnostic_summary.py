from __future__ import annotations

import unittest

from tools.summarize_slot_pose_diagnostics import build_summary, candidate_clusters


def record(image_id: str, angles: list[float], *, error: str = "ROLE_ASSIGNMENT_FAILED", elapsed: float = 100.0) -> dict:
    return {
        "imageId": image_id,
        "result": {"valid": False, "errorCode": error},
        "face": {"centerX": 10.0, "centerY": 10.0, "radiusPx": 8.0},
        "angularProfile": {"completeRing": True},
        "candidateSummary": {"count": len(angles)},
        "candidates": [
            {
                "candidateId": f"candidate-{index + 1:03d}", "centerDeg": angle,
                "halfWidthDeg": 4.0, "prominence": 40.0 + index, "rank": index + 1,
            }
            for index, angle in enumerate(angles)
        ],
        "grooveRecognition": {
            "status": "accepted",
            "assessments": [{"candidateId": "candidate-001", "accepted": True, "rejectionReasons": []}],
        },
        "grooveCandidates": [
            {
                "candidateId": "candidate-001", "centerDeg": angles[0], "halfWidthDeg": 4.0,
                "prominence": 40.0, "rank": 1,
            }
        ] if angles else [],
        "singleGroovePose": {
            "status": "accepted" if angles else "failed",
            "geometryValid": bool(angles),
            "imageMeasurement": None if not angles else {
                "azimuthDeg": (angles[0] + 90.0) % 360.0,
                "quadrant": "upper_right",
            },
        },
        "roleSuggestion": {"status": "ambiguous_or_rejected", "selectedRoleCandidateIds": None},
        "elapsedMs": elapsed,
    }


class SlotPoseDiagnosticSummaryTests(unittest.TestCase):
    def test_radial_u_ownership_summary_counts_decisions_without_private_truth(self) -> None:
        released = record("released", [175.0], error="NONE")
        released["result"]["valid"] = True
        released["sidewallSourceConsistencyAdjudication"] = {
            "schemaVersion": "source-consistency-adjudication/5",
            "decision": "ACCEPTED_OVERRIDE",
            "sourceSeparationBasis": "radial_u_contour_ownership",
            "originalFailedChecks": ["edge_contrast_asymmetry"],
            "failedChecks": [], "imagePoseReleaseAllowed": True,
        }
        denied = record("denied", [175.0], error="GROOVE_SOURCE_INCONSISTENT")
        denied["sidewallSourceConsistencyAdjudication"] = {
            "schemaVersion": "source-consistency-adjudication/5",
            "decision": "REJECTED", "sourceSeparationBasis": None,
            "originalFailedChecks": ["edge_contrast_asymmetry"],
            "failedChecks": ["radial_u_contour_ownership_verified"],
            "imagePoseReleaseAllowed": False,
        }
        run = build_summary([("v8", {"records": [released, denied]})], 5.0)["runs"][0]
        summary = run["sourceConsistencyAdjudication"]
        self.assertEqual({"ACCEPTED_OVERRIDE": 1, "REJECTED": 1}, summary["decisionCounts"])
        self.assertEqual({"radial_u_contour_ownership": 1, "not_verified": 1},
                         summary["sourceSeparationBasisCounts"])
        self.assertEqual({"radial_u_contour_ownership_verified": 1},
                         summary["proofFailureCounts"])
        self.assertNotIn("imageId", summary)

    def test_polar_quality_adjudication_keeps_original_and_effective_counts_separate(self) -> None:
        released = record("released", [175.0], error="NONE")
        released["result"]["valid"] = True
        released["polarQualityAdjudication"] = {
            "decision": "ACCEPTED_OVERRIDE",
            "originalFailedChecks": ["polar_score"],
            "effectiveFailedChecks": [],
            "failedChecks": [],
            "imagePoseReleaseAllowed": True,
        }
        denied = record("denied", [175.0], error="QUALITY_REJECTED")
        denied["polarQualityAdjudication"] = {
            "decision": "REJECTED",
            "originalFailedChecks": ["polar_score"],
            "effectiveFailedChecks": ["polar_score"],
            "failedChecks": ["fixture_source_exclusion_verified"],
            "imagePoseReleaseAllowed": False,
        }
        run = build_summary([("v6", {"records": [released, denied]})], 5.0)["runs"][0]
        summary = run["polarQualityAdjudication"]
        self.assertEqual({"ACCEPTED_OVERRIDE": 1, "REJECTED": 1}, summary["decisionCounts"])
        self.assertEqual({"polar_score": 2}, summary["originalFailureCounts"])
        self.assertEqual({"polar_score": 1}, summary["effectiveFailureCounts"])
        self.assertEqual({"fixture_source_exclusion_verified": 1}, summary["proofFailureCounts"])
        self.assertEqual(1, summary["imagePoseReleaseAllowedCount"])

    def test_wraparound_candidates_form_one_stable_cluster(self) -> None:
        records = [record("a", [359.0, 90.0]), record("b", [1.0, 91.0]), record("c", [0.0])]
        clusters = candidate_clusters(records, 5.0)
        self.assertEqual(2, len(clusters))
        wrap = min(clusters, key=lambda item: abs(((item["circularMeanDeg"] + 180.0) % 360.0) - 180.0))
        self.assertEqual(3, wrap["frameSupport"])
        self.assertTrue(wrap["stableDiagnosticFeature"])
        self.assertLess(wrap["circularRangeDeg"], 3.0)
        self.assertFalse(wrap["authoritativeRole"])

    def test_summary_separates_circle_ring_candidates_roles_errors_and_latency(self) -> None:
        records = [record("a", [10.0], elapsed=100.0), record("b", [11.0], elapsed=200.0)]
        records[1]["angularProfile"] = {"completeRing": False}
        records[1]["candidateSummary"] = None
        records[1]["candidates"] = []
        records[1]["grooveCandidates"] = []
        summary = build_summary([("roi", {"records": records})], 5.0)
        run = summary["runs"][0]
        self.assertEqual({"1": 1, "0": 1}, run["candidateCountDistribution"])
        self.assertEqual(2, run["circleEstimateAvailable"]["count"])
        self.assertEqual(0, run["physicalOuterCircleAccepted"]["count"])
        self.assertEqual(1, run["completeRingAccepted"]["count"])
        self.assertEqual(1, run["candidateExtractionCompleted"]["count"])
        self.assertEqual({"1": 1, "0": 1}, run["grooveCandidateCountDistribution"])
        self.assertEqual({"accepted": 2}, run["grooveRecognitionStatusCounts"])
        self.assertEqual({"ROLE_ASSIGNMENT_FAILED": 2}, run["errorCodeCounts"])
        self.assertEqual(150.0, run["elapsedMs"]["p50"])
        self.assertEqual(195.0, run["elapsedMs"]["p95"])
        self.assertEqual(1, run["candidateIdTracks"][0]["angleModeCount"])
        self.assertFalse(run["candidateIdTracks"][0]["authoritativeRole"])
        self.assertFalse(summary["roleSuggestionsAreAuthoritative"])

    def test_single_groove_image_success_is_separate_from_datum_blocked_mechanical_result(self) -> None:
        records = [
            record("a", [291.0], error="DATUM_DEFINITION_UNCONFIRMED"),
            record("b", [292.0], error="DATUM_DEFINITION_UNCONFIRMED"),
        ]
        for item in records:
            item["grooveRecognition"]["assessments"].extend([
                {"candidateId": "shadow-1", "accepted": False, "rejectionReasons": ["width_variation_too_high"]},
                {"candidateId": "shadow-2", "accepted": False, "rejectionReasons": ["radial_depth_too_small"]},
            ])
        run = build_summary([("single", {"records": records})], 5.0)["runs"][0]
        self.assertEqual(2, run["singleGrooveGeometryValid"]["count"])
        self.assertEqual(2, run["imageGrooveAzimuthAvailable"]["count"])
        self.assertEqual(2, run["mechanicalGuidanceBlockedByDatum"]["count"])
        self.assertEqual(0, run["formalValid"]["count"])
        self.assertEqual({"upper_right": 2}, run["singleGrooveQuadrantCounts"])
        self.assertEqual(4, run["rejectedDarkCandidateCount"])

    def test_v2_summary_separates_refinement_target_and_plc_block(self) -> None:
        passed = record("a", [175.0], error="PLC_MAPPING_UNCONFIRMED")
        passed["grooveRefinement"] = {
            "schemaVersion": "slot-groove-subpixel-opening/2",
            "thresholdVersion": "groove-sidewall-subpixel-v2",
            "status": "accepted", "failedChecks": [], "elapsedMs": 12.0,
            "openingMidpointProfileDeg": 175.0,
            "startSide": {
                "lineInlierRatio": 0.8, "lineLongitudinalCoverage": 0.75,
                "supportMargin": 3, "lineResidualPx": {"p95": 1.2},
                "wallFamilyStrategyVersion": "shared-longitudinal-wall-family-v2",
                "wallFamilyStatus": "accepted", "rawHypothesisCount": 5,
                "physicalSourceFamilyCount": 3, "eligiblePhysicalSourceFamilyCount": 1,
                "radialAlignmentDeltaDeg": 2.5,
                "wallFamilySelectionElapsedMs": 1.25,
            },
            "endSide": {
                "lineInlierRatio": 0.9, "lineLongitudinalCoverage": 0.85,
                "supportMargin": None, "lineResidualPx": {"p95": 1.0},
            },
        }
        passed["singleGroovePose"].update({
            "schemaVersion": "slot-single-real-groove-pose/2",
            "datumMeasurement": {
                "measuredFromPositiveYClockwiseDeg": 85.0,
                "position": {"requiredRegionPassed": True},
            },
            "targetAssessment": {
                "status": "EVALUATED", "toleranceStatus": "PASS",
                "positionGatePassed": True, "angleTolerancePassed": True,
                "imageFrameCorrectionDeg": 0.0, "mechanicalCorrectionDeg": None,
                "blockers": ["PLC_MAPPING_UNCONFIRMED"],
            },
        })
        failed = record("b", [113.0], error="GROOVE_REFINEMENT_FAILED")
        failed["grooveRefinement"] = {"status": "failed", "failedChecks": ["startSide_line_residual"]}
        failed["singleGroovePose"] = {
            "schemaVersion": "slot-single-real-groove-pose/2", "status": "failed",
            "geometryValid": False, "imageMeasurement": None, "datumMeasurement": None,
            "targetAssessment": {"status": "NOT_EVALUATED", "toleranceStatus": "NOT_EVALUATED"},
        }
        run = build_summary([("v2", {"records": [passed, failed]})], 5.0)["runs"][0]
        self.assertEqual({"accepted": 1, "failed": 1}, run["grooveRefinementStatusCounts"])
        self.assertEqual({"startSide_line_residual": 1}, run["grooveRefinementFailureCounts"])
        self.assertEqual(1, run["yDownDatumAngleAvailable"]["count"])
        self.assertEqual({"NOT_EVALUATED": 1, "PASS": 1}, run["targetToleranceStatusCounts"])
        self.assertEqual(1, run["targetPositionGatePassed"]["count"])
        self.assertEqual(1, run["imageFrameCorrectionAvailable"]["count"])
        self.assertEqual(1, run["plcGuidanceBlocked"]["count"])
        self.assertEqual({"slot-groove-subpixel-opening/2": 1, "unknown": 1}, run["grooveRefinementSchemaCounts"])
        self.assertEqual(12.0, run["grooveRefinementElapsedMs"]["p95"])
        self.assertEqual(0.8, run["grooveSidewallEvidence"]["lineInlierRatio"]["min"])
        wall = run["grooveSidewallEvidence"]
        self.assertEqual(5.0, wall["rawHypothesisCount"]["p95"])
        self.assertEqual(1.0, wall["eligiblePhysicalSourceFamilyCount"]["p95"])
        self.assertEqual(1.25, wall["wallFamilySelectionElapsedMs"]["p95"])
        self.assertEqual(
            {"accepted": 1, "not_available": 1}, wall["wallFamilyStatusCounts"],
        )

    def test_v3_summary_counts_guidance_without_calling_adjustment_a_failure(self) -> None:
        in_position = record("a", [175.0], error="NONE")
        adjustment = record("b", [67.834], error="NONE")
        failed = record("c", [], error="GROOVE_RECOGNITION_FAILED")
        for item, status, current, correction, direction in (
            (in_position, "DETECTED_IN_POSITION", 82.978, 0.0, "NONE"),
            (adjustment, "DETECTED_NEEDS_ADJUSTMENT", 22.834, 62.166, "CLOCKWISE"),
            (failed, "NOT_AVAILABLE", None, None, None),
        ):
            detected = current is not None
            item["result"]["valid"] = detected
            item["guidance"] = {
                "detectionStatus": "DETECTED" if detected else "DETECTION_FAILED",
                "guidanceStatus": status,
                "currentAngleDeg": current,
                "imageFrameCorrectionDeg": correction,
                "rotationDirection": direction,
                "plcExecutionStatus": "BLOCKED_MAPPING_UNCONFIRMED",
            }
        run = build_summary([("v3", {"records": [in_position, adjustment, failed]})], 5.0)["runs"][0]
        self.assertEqual({"DETECTED": 2, "DETECTION_FAILED": 1}, run["detectionStatusCounts"])
        self.assertEqual({
            "DETECTED_IN_POSITION": 1,
            "DETECTED_NEEDS_ADJUSTMENT": 1,
            "NOT_AVAILABLE": 1,
        }, run["guidanceStatusCounts"])
        self.assertEqual({"CLOCKWISE": 1, "NONE": 1, "not_available": 1}, run["rotationDirectionCounts"])
        self.assertEqual(2, run["closedLoopImageFrameCorrectionAvailable"]["count"])
        self.assertEqual("NOT_EVALUATED", run["staticRepeatabilityEvaluation"]["status"])

    def test_locator_candidates_and_paired_circle_deltas_are_summarized(self) -> None:
        first = record("a", [10.0])
        second = record("a", [10.0])
        first["circleLocalization"] = {
            "status": "accepted",
            "componentProposals": [{"status": "eligible"}, {"status": "rejected"}],
            "circleCandidates": [{"candidateId": "circle-candidate-001"}],
            "timingMs": {"totalLocalization": 350.0},
        }
        first["physicalOuterCircle"] = {
            "status": "accepted", "physicalCircle": {"centerX": 10.0, "centerY": 10.0, "radiusPx": 8.0},
            "failedChecks": [],
        }
        second["physicalOuterCircle"] = {
            "status": "accepted", "physicalCircle": {"centerX": 10.3, "centerY": 10.4, "radiusPx": 8.2},
            "failedChecks": [],
        }
        summary = build_summary([("full", {"records": [first]}), ("roi", {"records": [second]})], 5.0)
        run = summary["runs"][0]
        self.assertEqual({"accepted": 1}, run["circleLocalizationStatusCounts"])
        self.assertEqual({2: 1}, run["componentProposalCountDistribution"])
        self.assertEqual({1: 1}, run["eligibleComponentProposalCountDistribution"])
        self.assertEqual(350.0, run["localizationElapsedMs"]["p95"])
        comparison = summary["pairedCircleComparisons"][0]
        self.assertEqual(1, comparison["matchedAcceptedCircleCount"])
        self.assertAlmostEqual(0.5, comparison["centerDistancePx"]["max"])
        self.assertAlmostEqual(0.2, comparison["radiusAbsoluteDifferencePx"]["max"])

    def test_paired_refinement_comparison_uses_circular_delta_and_only_accepted_pairs(self) -> None:
        first = record("a", [10.0])
        second = record("a", [10.0])
        first["grooveRefinement"] = {
            "status": "accepted", "openingMidpointProfileDeg": 359.9,
            "schemaVersion": "slot-groove-subpixel-opening/1",
        }
        second["grooveRefinement"] = {
            "status": "accepted", "openingMidpointProfileDeg": 0.1,
            "schemaVersion": "slot-groove-subpixel-opening/2",
        }
        summary = build_summary([("v1", {"records": [first]}), ("v2", {"records": [second]})], 5.0)
        comparison = summary["pairedRefinementComparisons"][0]
        self.assertEqual(1, comparison["matchedAcceptedRefinementCount"])
        self.assertAlmostEqual(0.2, comparison["midpointCircularDeltaDeg"]["maxAbsolute"])


if __name__ == "__main__":
    unittest.main()
