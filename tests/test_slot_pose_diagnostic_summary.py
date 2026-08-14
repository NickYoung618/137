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


if __name__ == "__main__":
    unittest.main()
