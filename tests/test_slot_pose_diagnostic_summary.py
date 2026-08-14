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
        summary = build_summary([("roi", {"records": records})], 5.0)
        run = summary["runs"][0]
        self.assertEqual({"1": 1, "0": 1}, run["candidateCountDistribution"])
        self.assertEqual(2, run["circleEstimateAvailable"]["count"])
        self.assertEqual(1, run["completeRingAccepted"]["count"])
        self.assertEqual(1, run["candidateExtractionCompleted"]["count"])
        self.assertEqual({"ROLE_ASSIGNMENT_FAILED": 2}, run["errorCodeCounts"])
        self.assertEqual(150.0, run["elapsedMs"]["p50"])
        self.assertEqual(195.0, run["elapsedMs"]["p95"])
        self.assertEqual(1, run["candidateIdTracks"][0]["angleModeCount"])
        self.assertFalse(run["candidateIdTracks"][0]["authoritativeRole"])
        self.assertFalse(summary["roleSuggestionsAreAuthoritative"])


if __name__ == "__main__":
    unittest.main()
