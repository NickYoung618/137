from __future__ import annotations

import unittest

from algorithms.slot_pose.groove_resolution import resolve_groove_candidates


class GrooveResolutionTests(unittest.TestCase):
    def test_exactly_one_physical_survivor_is_selected_and_evidence_is_retained(self) -> None:
        candidates = [{"candidateId": "b"}, {"candidateId": "a"}]

        def refine(candidate: dict) -> dict:
            return {"status": "accepted" if candidate["candidateId"] == "a" else "failed",
                    "failedChecks": [] if candidate["candidateId"] == "a" else ["sidewall_missing"]}

        result = resolve_groove_candidates(candidates, refine, {"enabled": True, "max_candidates": 3})
        self.assertEqual("resolved", result["status"])
        self.assertEqual("a", result["selectedCandidateId"])
        self.assertEqual(2, len(result["attempts"]))
        self.assertEqual(["a"], [item["candidateId"] for item in result["survivors"]])

    def test_zero_multiple_and_over_limit_fail_closed(self) -> None:
        candidates = [{"candidateId": str(index)} for index in range(3)]
        for accepted_ids, expected in ((set(), "none_survived"), ({"0", "1"}, "multiple_survived")):
            result = resolve_groove_candidates(
                candidates[:2],
                lambda item: {"status": "accepted" if item["candidateId"] in accepted_ids else "failed"},
                {"enabled": True, "max_candidates": 3},
            )
            self.assertEqual(expected, result["status"])
            self.assertIsNone(result["selectedCandidateId"])
        over = resolve_groove_candidates(candidates, lambda _: {"status": "accepted"}, {"enabled": True, "max_candidates": 2})
        self.assertEqual("candidate_limit_exceeded", over["status"])
        self.assertEqual([], over["attempts"])

    def test_disabled_resolver_never_calls_refiner(self) -> None:
        called = []
        result = resolve_groove_candidates(
            [{"candidateId": "a"}, {"candidateId": "b"}],
            lambda item: called.append(item) or {"status": "accepted"},
            {"enabled": False, "max_candidates": 3},
        )
        self.assertEqual("disabled", result["status"])
        self.assertEqual([], called)


if __name__ == "__main__":
    unittest.main()
