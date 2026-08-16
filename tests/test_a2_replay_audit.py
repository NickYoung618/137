from __future__ import annotations

import unittest

from tools.audit_slot_pose_replay import audit_replay


def payload(digest: str, valid: bool, guidance: str, direction: str | None, error: str | None = None) -> dict:
    detected = valid
    current = 85.0 if guidance == "DETECTED_IN_POSITION" else (20.0 if valid else None)
    correction = 0.0 if guidance == "DETECTED_IN_POSITION" else (65.0 if valid else None)
    return {
        "schemaVersion": "slot-pose-result/3", "taskId": f"set:{digest}", "createdAtUtc": "2026-08-15T00:00:00Z",
        "image": {"sha256": digest},
        "result": {
            "valid": valid, "signedRelativeRotationDeg": correction, "unit": "deg",
            "confidence": 0.8 if valid else None, "referenceFrame": "DETECTED_PHYSICAL_OUTER_CIRCLE_POSITIVE_Y_DOWN",
            "targetFrame": "IMAGE_FRAME_TARGET_85_DEG", "positiveDirection": "cw",
            "detectionStatus": "DETECTED" if detected else "DETECTION_FAILED", "guidanceStatus": guidance,
            "currentAngleDeg": current, "targetAngleDeg": 85.0, "toleranceDeg": 5.0,
            "correctionRawDeg": correction, "correctionDeg": correction, "imageFrameCorrectionDeg": correction,
            "rotationDirection": direction, "withinTolerance": (guidance == "DETECTED_IN_POSITION") if valid else None,
            "mechanicalCorrectionDeg": None, "plcCommand": None,
            "plcExecutionStatus": "BLOCKED_MAPPING_UNCONFIRMED", "plcExecutionAuthoritative": False,
            "plcBlockers": ["PLC_MAPPING_UNCONFIRMED"],
        },
        "technicalStatus": "succeeded" if valid else "failed",
        "error": None if valid else {"code": error, "message": error, "stage": "quality_gate"},
        "diagnostics": {"elapsedMs": 10.0, "singleGroovePose": {"guidance": {
            "detectionStatus": "DETECTED", "guidanceStatus": "DETECTED_IN_POSITION", "rotationDirection": "NONE",
        }}},
    }


class ReplayAuditTests(unittest.TestCase):
    def test_final_counts_ignore_intermediate_quality_geometry(self) -> None:
        manifest = {"datasetId": "set", "policy": {"groupingExplicit": False}, "images": [
            {"imageId": "a", "relativePath": "normal/a.bmp", "sha256": "a", "datasetClass": "normal", "split": "acceptance", "sampleId": "s", "conditionId": "c"},
            {"imageId": "b", "relativePath": "normal/b.bmp", "sha256": "b", "datasetClass": "normal", "split": "acceptance", "sampleId": "s", "conditionId": "c"},
            {"imageId": "c", "relativePath": "bad/c.bmp", "sha256": "c", "datasetClass": "bad", "split": "acceptance", "sampleId": "q", "conditionId": "c", "poseUsable": None},
        ]}
        results = [
            payload("a", True, "DETECTED_NEEDS_ADJUSTMENT", "CLOCKWISE"),
            payload("b", True, "DETECTED_IN_POSITION", "NONE"),
            payload("c", False, "NOT_AVAILABLE", None, "QUALITY_REJECTED"),
        ]
        report = audit_replay(manifest, results)
        self.assertEqual("PASSED", report["status"])
        self.assertEqual({"true": 2, "false": 1}, report["finalOutcome"]["validCounts"])
        self.assertEqual({"DETECTED_NEEDS_ADJUSTMENT": 1, "DETECTED_IN_POSITION": 1, "NOT_AVAILABLE": 1}, report["finalOutcome"]["guidanceStatusCounts"])
        self.assertEqual({"CLOCKWISE": 1, "NONE": 1, "not_available": 1}, report["finalOutcome"]["rotationDirectionCounts"])
        self.assertEqual("NOT_EVALUATED", report["repeatability"]["status"])
        self.assertEqual("BLOCKED", report["poseUsabilityMetric"]["status"])
        self.assertEqual(2, report["byDatasetClass"]["normal"]["validCount"])
        self.assertIn("finalDetected", report["stageFunnel"])
        self.assertIn("bad_reason_and_pose_usability", {
            item["annotationType"] for item in report["annotationQueue"]
        })

    def test_inconsistent_final_state_fails_audit(self) -> None:
        manifest = {"datasetId": "set", "policy": {}, "images": [
            {"imageId": "a", "relativePath": "a.bmp", "sha256": "a", "datasetClass": "normal", "split": "test"},
        ]}
        broken = payload("a", True, "DETECTED_NEEDS_ADJUSTMENT", "CLOCKWISE")
        broken["result"]["detectionStatus"] = "DETECTION_FAILED"
        report = audit_replay(manifest, [broken])
        self.assertEqual("FAILED", report["status"])
        self.assertTrue(report["consistencyErrors"])

    def test_repeatability_requires_explicit_groups_and_at_least_twenty_frames(self) -> None:
        manifest = {"datasetId": "set", "policy": {"groupingExplicit": True}, "images": [
            {"imageId": "a", "relativePath": "a.bmp", "sha256": "a", "datasetClass": "normal", "split": "validation", "sampleId": "part", "conditionId": "same"},
            {"imageId": "b", "relativePath": "b.bmp", "sha256": "b", "datasetClass": "normal", "split": "validation", "sampleId": "part", "conditionId": "same"},
        ]}
        first = payload("a", True, "DETECTED_NEEDS_ADJUSTMENT", "COUNTERCLOCKWISE")
        second = payload("b", True, "DETECTED_NEEDS_ADJUSTMENT", "COUNTERCLOCKWISE")
        first["result"].update({"currentAngleDeg": 179.5, "correctionRawDeg": -94.5, "correctionDeg": -94.5,
                                "imageFrameCorrectionDeg": -94.5, "signedRelativeRotationDeg": -94.5})
        second["result"].update({"currentAngleDeg": -179.5, "correctionRawDeg": -95.5, "correctionDeg": -95.5,
                                 "imageFrameCorrectionDeg": -95.5, "signedRelativeRotationDeg": -95.5})
        report = audit_replay(manifest, [first, second])
        self.assertEqual("NOT_EVALUATED", report["repeatability"]["status"])
        self.assertEqual(20, report["repeatability"]["minimumFrames"])

        images = []
        results = []
        for index in range(20):
            digest = f"repeat-{index}"
            images.append({"imageId": digest, "relativePath": f"r/{index}.bmp", "sha256": digest,
                           "datasetClass": "normal", "split": "validation", "sampleId": "part", "conditionId": "same"})
            repeated = payload(digest, True, "DETECTED_NEEDS_ADJUSTMENT", "COUNTERCLOCKWISE")
            repeated["result"].update({"currentAngleDeg": 179.5 if index % 2 == 0 else -179.5,
                                       "correctionRawDeg": -94.5, "correctionDeg": -94.5,
                                       "imageFrameCorrectionDeg": -94.5, "signedRelativeRotationDeg": -94.5})
            results.append(repeated)
        complete = audit_replay({"datasetId": "set", "policy": {"groupingExplicit": True}, "images": images}, results)
        self.assertEqual("EVALUATED", complete["repeatability"]["status"])
        self.assertAlmostEqual(1.0, complete["repeatability"]["groups"][0]["circularRangeDeg"])

    def test_700_record_json_audit_is_bounded_and_does_not_read_images(self) -> None:
        images = []
        results = []
        for index in range(700):
            digest = f"digest-{index}"
            images.append({"imageId": digest, "relativePath": f"f/{index}.bmp", "sha256": digest,
                           "datasetClass": "normal", "split": "acceptance"})
            results.append(payload(digest, True, "DETECTED_NEEDS_ADJUSTMENT", "CLOCKWISE"))
        report = audit_replay({"datasetId": "perf", "policy": {}, "images": images}, results)
        self.assertEqual("PASSED", report["status"])
        self.assertLess(report["auditWallMs"], 5000.0)
        self.assertFalse(report["imagesRead"])


if __name__ == "__main__":
    unittest.main()
