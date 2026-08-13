from __future__ import annotations

import unittest

from tools.evaluate_slot_pose import circular_error_deg, evaluate_results


def result(digest: str, angle: float | None, elapsed: float = 10.0) -> dict:
    return {
        "image": {"sha256": digest},
        "result": {"valid": angle is not None, "signedRelativeRotationDeg": angle},
        "error": None if angle is not None else {"code": "SLOT_NOT_FOUND"},
        "diagnostics": {"elapsedMs": elapsed},
    }


class SlotPoseEvaluationTests(unittest.TestCase):
    def test_circular_error_wrap(self) -> None:
        self.assertAlmostEqual(2.0, circular_error_deg(-179.0, 179.0))

    def test_incomplete_data_and_error_metrics(self) -> None:
        truth = [
            {"image_sha256": "a", "truth_valid": "true", "truth_angle_deg": "179", "sample": "s", "position": "p1"},
            {"image_sha256": "b", "truth_valid": "true", "truth_angle_deg": "10", "sample": "s", "position": "p2"},
        ]
        report = evaluate_results([result("a", -179.0), result("b", None)], truth)
        self.assertEqual("INCOMPLETE", report["status"])
        self.assertEqual(1, report["falseNegativeCount"])
        self.assertAlmostEqual(2.0, report["angleErrorDeg"]["mae"])
        self.assertEqual({"SLOT_NOT_FOUND": 1}, report["errorCodeCounts"])


if __name__ == "__main__":
    unittest.main()
