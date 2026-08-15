import unittest

from tools.batch_current_capture import BatchAccumulator, validate_batch_summary_contract


def _record(group: str, *, valid: bool, orientation: int | None = 270):
    reason = None if valid else "no_valid_candidate"
    result = {
        "qualityStatus": {
            "technicalValid": valid,
            "state": "complete" if valid else "registration_invalid",
            "failureReasons": [] if valid else [f"registration:{reason}"],
        },
        "registration": {
            "registrationValid": valid,
            "failureReason": reason,
            "selected": None if orientation is None else {"orientationDeg": orientation},
            "candidates": [{
                "valid": valid,
                "failureReasons": [] if valid else ["support_count_below_gate"],
            }],
        },
        "features": {
            "7": {"measurementValid": valid, "failureReason": reason},
            "Phi12.2": {"measurementValid": valid, "failureReason": reason},
        },
        "timingMs": {"total": 100.0 if valid else 80.0},
    }
    return {"group": group, "imagePath": f"/{group}.bmp", "result": result, "executionError": None}


class CurrentCaptureBatchTests(unittest.TestCase):
    def test_grouped_summary_keeps_invalid_results_and_reasons(self):
        accumulator = BatchAccumulator()
        accumulator.add(_record("normal", valid=True))
        accumulator.add(_record("defective", valid=False, orientation=None))
        summary = accumulator.as_dict()
        self.assertEqual(2, summary["overall"]["total"])
        self.assertEqual(1, summary["overall"]["technicalComplete"])
        self.assertEqual(1, summary["groups"]["normal"]["technicalComplete"])
        self.assertEqual(0, summary["groups"]["defective"]["technicalComplete"])
        self.assertEqual(
            1,
            summary["groups"]["defective"]["registrationFailureReasons"]["no_valid_candidate"],
        )
        self.assertEqual(
            1,
            summary["overall"]["candidateRejectionReasons"]["support_count_below_gate"],
        )
        summary["runtimeInputs"] = {
            "authoritativeReferenceAnnotation": {}, "authoritativeReferenceImage": {},
            "configuration": {}, "groups": [],
        }
        validate_batch_summary_contract(summary)


if __name__ == "__main__":
    unittest.main()
