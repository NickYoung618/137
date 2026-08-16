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

    def test_cross_angle_groups_use_truth_residual_not_raw_angle_range(self) -> None:
        truth = []
        results = []
        for index, (condition, angle, estimate) in enumerate((("p1", -170.0, -169.0), ("p2", 90.0, 91.0))):
            digest = chr(ord("a") + index)
            truth.append({
                "image_sha256": digest, "truth_valid": "true", "truth_angle_deg": str(angle),
                "sample": "s", "condition": condition, "dataset_class": "normal",
            })
            results.append(result(digest, estimate))
        report = evaluate_results(results, truth)
        residual = report["normal"]["crossConditionResidual"][0]
        self.assertAlmostEqual(0.0, residual["residualMeanRangeDeg"])
        self.assertNotEqual(260.0, residual["residualMeanRangeDeg"])

    def test_static_repeatability_unwraps_across_180_boundary(self) -> None:
        truth = [
            {"image_sha256": "a", "truth_valid": "true", "truth_angle_deg": "179", "sample": "s", "condition": "wrap", "dataset_class": "normal"},
            {"image_sha256": "b", "truth_valid": "true", "truth_angle_deg": "179", "sample": "s", "condition": "wrap", "dataset_class": "normal"},
        ]
        report = evaluate_results([result("a", 179.5), result("b", -179.5)], truth)
        self.assertAlmostEqual(1.0, report["normal"]["staticRepeatability"][0]["rangeDeg"])

    def test_bad_image_valid_result_is_false_positive_and_failure_is_not_zero(self) -> None:
        truth = [
            {"image_sha256": "a", "truth_valid": "false", "truth_angle_deg": "", "sample": "s", "condition": "bad", "dataset_class": "bad"},
            {"image_sha256": "b", "truth_valid": "false", "truth_angle_deg": "", "sample": "s", "condition": "bad", "dataset_class": "bad"},
        ]
        report = evaluate_results([result("a", 0.0), result("b", None)], truth)
        bad = report["bad"]
        self.assertEqual(1, bad["falsePositiveCount"])
        self.assertEqual(0.5, bad["falsePositiveRate"])
        self.assertEqual(1, bad["invalidCount"])
        self.assertEqual(0, report["angleErrorDeg"]["n"])
        self.assertEqual("CONDITIONAL", bad["poseFalsePositiveMetric"]["status"])

    def test_authoritative_pose_usability_is_not_inferred_from_bad_class(self) -> None:
        truth = [
            {"image_sha256": "a", "truth_valid": "false", "truth_angle_deg": "", "sample": "s",
             "condition": "bad", "dataset_class": "bad", "pose_usable": "", "authority": "", "provenance": ""},
            {"image_sha256": "b", "truth_valid": "false", "truth_angle_deg": "", "sample": "s",
             "condition": "bad", "dataset_class": "bad", "pose_usable": "false",
             "authority": "pose-owner", "provenance": "review-7"},
        ]
        report = evaluate_results([result("a", 10.0), result("b", 20.0)], truth)
        metric = report["bad"]["poseFalsePositiveMetric"]
        self.assertEqual("PARTIAL", metric["status"])
        self.assertEqual(1, metric["labeledCount"])
        self.assertEqual(1, metric["falsePositiveCount"])
        self.assertEqual(1.0, metric["falsePositiveRate"])
        self.assertEqual(1, metric["unknownCount"])


if __name__ == "__main__":
    unittest.main()
