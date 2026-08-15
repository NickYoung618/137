from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from tools.dataset_common import inspect_image
from tools.render_slot_pose_review import contact_sheet_layout, render_review


class SlotPoseReviewTests(unittest.TestCase):
    def test_final_result_overrides_pre_quality_guidance(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            image_path = root / "quality-rejected.jpg"
            Image.new("RGB", (160, 120), 128).save(image_path, quality=95)
            manifest = {
                "datasetId": "authority",
                "images": [{
                    "imageId": "sample:0001", "relativePath": image_path.name,
                    "datasetClass": "normal", **inspect_image(image_path),
                }],
            }
            intermediate = {
                "detectionStatus": "DETECTED", "guidanceStatus": "DETECTED_IN_POSITION",
                "currentAngleDeg": 85.0, "targetAngleDeg": 85.0, "toleranceDeg": 5.0,
                "correctionRawDeg": 0.0, "correctionDeg": 0.0,
                "imageFrameCorrectionDeg": 0.0, "rotationDirection": "NONE",
                "withinTolerance": True,
                "plcExecution": {"status": "BLOCKED_MAPPING_UNCONFIRMED"},
            }
            final = {
                "valid": False, "signedRelativeRotationDeg": None,
                "detectionStatus": "DETECTION_FAILED", "guidanceStatus": "NOT_AVAILABLE",
                "currentAngleDeg": None, "targetAngleDeg": 85.0, "toleranceDeg": 5.0,
                "correctionRawDeg": None, "correctionDeg": None,
                "imageFrameCorrectionDeg": None, "rotationDirection": None,
                "withinTolerance": None, "mechanicalCorrectionDeg": None,
                "plcCommand": None, "plcExecutionStatus": "BLOCKED_MAPPING_UNCONFIRMED",
                "plcExecutionAuthoritative": False, "plcBlockers": ["PLC_MAPPING_UNCONFIRMED"],
            }
            result = {
                "taskId": "authority:sample:0001", "result": final,
                "error": {"code": "QUALITY_REJECTED", "stage": "quality_gate"},
                "diagnostics": {
                    "singleGroovePose": {"geometryValid": True, "guidance": intermediate},
                },
            }
            summary = render_review(manifest, [result], root, root / "review")
            self.assertEqual({"DETECTION_FAILED": 1}, summary["detectionStatusCounts"])
            self.assertEqual({"NOT_AVAILABLE": 1}, summary["guidanceStatusCounts"])
            self.assertEqual({"not_available": 1}, summary["rotationDirectionCounts"])
            record = summary["records"][0]
            self.assertTrue(record["failClosed"])
            self.assertEqual("DETECTION_FAILED", record["guidance"]["detectionStatus"])
            self.assertEqual("DETECTED", record["intermediateGuidance"]["detectionStatus"])

    def test_contact_sheet_layout_stays_within_jpeg_limit(self) -> None:
        columns, rows, width, height = contact_sheet_layout(700)
        self.assertGreaterEqual(columns, 5)
        self.assertEqual(700, columns * (rows - 1) + min(columns, 700 - columns * (rows - 1)))
        self.assertLessEqual(width, 65_000)
        self.assertLessEqual(height, 65_000)

    def test_v3_review_separates_adjustment_from_detection_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            images = []
            results = []
            cases = (
                ("in-position", True, "DETECTED", "DETECTED_IN_POSITION", 82.978, 0.0, "NONE", None),
                ("adjust", True, "DETECTED", "DETECTED_NEEDS_ADJUSTMENT", 22.834, 62.166, "CLOCKWISE", None),
                ("failed", False, "DETECTION_FAILED", "NOT_AVAILABLE", None, None, None, "GROOVE_RECOGNITION_FAILED"),
            )
            for index, (name, valid, detection, guidance_status, current, correction, direction, error_code) in enumerate(cases, start=1):
                relative = f"frames/{name}.jpg"
                image_path = root / relative
                image_path.parent.mkdir(exist_ok=True)
                Image.new("RGB", (160, 120), 128).save(image_path, quality=95)
                info = inspect_image(image_path)
                image_id = f"sample:{index:04d}"
                images.append({"imageId": image_id, "relativePath": relative, "datasetClass": "normal", **info})
                guidance = {
                    "detectionStatus": detection,
                    "guidanceStatus": guidance_status,
                    "currentAngleDeg": current,
                    "targetAngleDeg": 85.0,
                    "toleranceDeg": 5.0,
                    "correctionRawDeg": None if current is None else (85.0 - current + 180.0) % 360.0 - 180.0,
                    "correctionDeg": correction,
                    "imageFrameCorrectionDeg": correction,
                    "rotationDirection": direction,
                    "withinTolerance": None if current is None else guidance_status == "DETECTED_IN_POSITION",
                    "plcExecution": {
                        "status": "BLOCKED_MAPPING_UNCONFIRMED",
                        "mechanicalCorrectionDeg": None,
                        "plcCommand": None,
                    },
                }
                results.append({
                    "taskId": f"closed-loop-review:{image_id}",
                    "result": {"valid": valid, "signedRelativeRotationDeg": correction},
                    "error": None if error_code is None else {"code": error_code, "stage": "groove_recognition"},
                    "diagnostics": {
                        "singleGroovePose": {
                            "schemaVersion": "slot-single-real-groove-pose/3",
                            "status": "accepted" if valid else "failed",
                            "geometryValid": valid,
                            "imageMeasurement": None,
                            "datumMeasurement": None,
                            "guidance": guidance,
                        },
                        "elapsedMs": 10.0,
                    },
                })
            manifest = {"datasetId": "closed-loop-review", "images": images}
            output = root / "review-v3"
            summary = render_review(manifest, results, root, output)
            self.assertEqual("slot-pose-review/2", summary["schemaVersion"])
            self.assertEqual({"DETECTED": 2, "DETECTION_FAILED": 1}, summary["detectionStatusCounts"])
            self.assertEqual({
                "DETECTED_IN_POSITION": 1,
                "DETECTED_NEEDS_ADJUSTMENT": 1,
                "NOT_AVAILABLE": 1,
            }, summary["guidanceStatusCounts"])
            self.assertEqual({"CLOCKWISE": 1, "NONE": 1, "not_available": 1}, summary["rotationDirectionCounts"])
            self.assertFalse(summary["records"][0]["failClosed"])
            self.assertFalse(summary["records"][1]["failClosed"])
            self.assertTrue(summary["records"][2]["failClosed"])
            guidance_csv = (output / "guidance.csv").read_text(encoding="utf-8")
            self.assertIn("DETECTED_NEEDS_ADJUSTMENT", guidance_csv)
            self.assertIn("CLOCKWISE", guidance_csv)
            failures_csv = (output / "failures.csv").read_text(encoding="utf-8")
            self.assertIn("frames/failed.jpg", failures_csv)
            self.assertNotIn("frames/adjust.jpg", failures_csv)

    def test_review_is_path_safe_and_marks_role_as_non_authoritative(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            image_path = root / "nested" / "frame.jpg"
            image_path.parent.mkdir()
            Image.new("RGB", (120, 100), 128).save(image_path, quality=95)
            image_info = inspect_image(image_path)
            manifest = {
                "datasetId": "review-set",
                "images": [{
                    "imageId": "sample:unknown:0001", "relativePath": "nested/frame.jpg",
                    "datasetClass": "normal", **image_info,
                }],
            }
            result = {
                "taskId": "review-set:sample:unknown:0001",
                "result": {"valid": False, "signedRelativeRotationDeg": None},
                "error": {"code": "DATUM_DEFINITION_UNCONFIRMED", "stage": "pose_mapping"},
                "diagnostics": {
                    "circleLocalization": {
                        "status": "accepted", "selectedCandidateId": "circle-candidate-001",
                        "componentProposals": [{
                            "proposalId": "proposal-001", "status": "eligible",
                            "bboxNormalized": [0.1, 0.1, 0.9, 0.9],
                        }],
                        "circleCandidates": [{
                            "candidateId": "circle-candidate-001", "rank": 1, "score": 0.9,
                            "coarsePhysicalCircle": {"centerX": 60.0, "centerY": 50.0, "radiusPx": 34.0},
                        }],
                    },
                    "face": {"centerX": 60.0, "centerY": 50.0, "radiusPx": 35.0},
                    "candidateSummary": {"count": 2},
                    "candidates": [
                        {"candidateId": "candidate-001", "rank": 1, "centerDeg": 90.0,
                         "halfWidthDeg": 4.0, "prominence": 40.0, "startDeg": 86.0,
                         "endDeg": 94.0, "wrapsBoundary": False},
                        {"candidateId": "candidate-002", "rank": 2, "centerDeg": 175.0,
                         "halfWidthDeg": 5.0, "prominence": 35.0, "startDeg": 170.0,
                         "endDeg": 180.0, "wrapsBoundary": False},
                    ],
                    "rawCandidates": [
                        {"candidateId": "candidate-001", "rank": 1, "centerDeg": 90.0,
                         "halfWidthDeg": 4.0, "prominence": 40.0, "startDeg": 86.0,
                         "endDeg": 94.0, "wrapsBoundary": False},
                        {"candidateId": "candidate-002", "rank": 2, "centerDeg": 175.0,
                         "halfWidthDeg": 5.0, "prominence": 35.0, "startDeg": 170.0,
                         "endDeg": 180.0, "wrapsBoundary": False},
                    ],
                    "grooveRecognition": {
                        "status": "failed", "acceptedCount": 1,
                        "assessments": [
                            {"candidateId": "candidate-001", "grooveScore": 0.9, "accepted": True,
                             "rejectionReasons": [], "radialDepthPx": 20.0, "tangentialWidthPx": 8.0,
                             "pairedEdgeSupport": 0.9, "contourContinuity": 0.9,
                             "thresholdVersion": "groove-geometry-v1"},
                            {"candidateId": "candidate-002", "grooveScore": 0.3, "accepted": False,
                             "rejectionReasons": ["radial_depth_too_small"], "radialDepthPx": 2.0,
                             "tangentialWidthPx": 9.0, "pairedEdgeSupport": 0.2,
                             "contourContinuity": 0.4, "thresholdVersion": "groove-geometry-v1"},
                        ],
                    },
                    "grooveCandidates": [
                        {"candidateId": "candidate-001", "rank": 1, "centerDeg": 90.0,
                         "halfWidthDeg": 4.0, "prominence": 40.0, "startDeg": 86.0,
                         "endDeg": 94.0, "wrapsBoundary": False},
                    ],
                    "singleGroovePose": {
                        "schemaVersion": "slot-single-real-groove-pose/2",
                        "status": "accepted", "geometryValid": True,
                        "imageMeasurement": {"azimuthDeg": 5.0, "quadrant": "lower_left"},
                        "datumMeasurement": {
                            "measuredFromPositiveYClockwiseDeg": 85.0,
                            "position": {"horizontal": "left", "vertical": "lower", "requiredRegionPassed": True},
                        },
                        "targetAssessment": {
                            "status": "EVALUATED", "toleranceStatus": "PASS",
                            "positionGatePassed": True, "angleTolerancePassed": True,
                            "imageFrameCorrectionDeg": 0.0, "mechanicalCorrectionDeg": None,
                            "blockers": ["PLC_MAPPING_UNCONFIRMED"],
                        },
                    },
                    "grooveRefinement": {
                        "schemaVersion": "slot-groove-subpixel-opening/2",
                        "thresholdVersion": "groove-sidewall-subpixel-v2",
                        "status": "accepted", "openingEndpointProfileDeg": [170.0, 180.0],
                        "openingMidpointProfileDeg": 175.0,
                        "outerCircleIntersections": [{"x": 30.0, "y": 55.0}, {"x": 25.0, "y": 50.0}],
                        "elapsedMs": 12.5,
                        "startSide": {
                            "detectedPointCount": 4, "supportPointCount": 3, "rejectedPointCount": 1,
                            "lineFitStrategy": "deterministic-consensus-tls-v2",
                            "lineInlierRatio": 0.75, "lineLongitudinalCoverage": 0.8,
                            "rawLineHypothesisCount": 5, "refitLineHypothesisCount": 4,
                            "lineHypothesisCount": 1, "bestModelId": "side-model-001",
                            "secondModelId": None, "bestSupportCount": 3,
                            "secondSupportCount": None, "supportMargin": None,
                            "line": {"a": 1.0, "b": 0.0, "c": -30.0},
                            "lineResidualPx": {"median": 0.2, "p95": 0.7, "max": 0.9},
                            "detectedPoints": [[30.0, 45.0], [30.0, 48.0], [30.0, 51.0], [34.0, 55.0]],
                            "points": [[30.0, 45.0], [30.0, 48.0], [30.0, 51.0]],
                            "rejectedPoints": [[34.0, 55.0]],
                        },
                        "endSide": {
                            "detectedPointCount": 4, "supportPointCount": 3, "rejectedPointCount": 1,
                            "lineFitStrategy": "deterministic-consensus-tls-v2",
                            "lineInlierRatio": 0.75, "lineLongitudinalCoverage": 0.82,
                            "rawLineHypothesisCount": 6, "refitLineHypothesisCount": 4,
                            "lineHypothesisCount": 1, "bestModelId": "side-model-001",
                            "secondModelId": None, "bestSupportCount": 3,
                            "secondSupportCount": None, "supportMargin": None,
                            "line": {"a": 0.0, "b": 1.0, "c": -50.0},
                            "lineResidualPx": {"median": 0.3, "p95": 0.8, "max": 1.0},
                            "detectedPoints": [[25.0, 50.0], [28.0, 50.0], [31.0, 50.0], [35.0, 54.0]],
                            "points": [[25.0, 50.0], [28.0, 50.0], [31.0, 50.0]],
                            "rejectedPoints": [[35.0, 54.0]],
                        },
                    },
                    "roleAssignment": {
                        "unique": True,
                        "selectedRoleCandidateIds": {
                            "datum_primary": "candidate-001", "target_left": "candidate-002",
                        },
                        "selectedRoleAzimuthsDeg": {"datum_primary": 90.0, "target_left": 175.0},
                        "bestScore": 0.95, "secondBestScore": None, "scoreMargin": 0.95,
                        "failedChecks": [], "drawingAngle": {"includedAngleDeg": 85.0},
                    },
                    "quality": {
                        "confidenceComponents": [0.9, 0.8],
                        "thresholds": {"role_assignment": {"drawing_nominal_angle_deg": 85.0}},
                    },
                    "angularProfile": {"completeRing": True},
                    "slot": {"polarRotationDeg": 1.5},
                    "elapsedMs": 123.0,
                },
            }
            output = root / "review"
            summary = render_review(manifest, [result], root, output)
            self.assertFalse(summary["roleSuggestionsAreAuthoritative"])
            record = summary["records"][0]
            self.assertEqual("unique_diagnostic_hypothesis", record["roleSuggestion"]["status"])
            self.assertFalse(record["roleSuggestion"]["authoritative"])
            self.assertTrue(record["failClosed"])
            self.assertIsNone(record["result"]["signedRelativeRotationDeg"])
            self.assertAlmostEqual(0.8, record["diagnosticConfidence"])
            self.assertEqual(123.0, record["elapsedMs"])
            self.assertTrue(record["angularProfile"]["completeRing"])
            self.assertEqual([], record["singleRayRoleHypotheses"])
            self.assertEqual(1, len(record["grooveCandidates"]))
            self.assertTrue(record["singleGroovePose"]["geometryValid"])
            self.assertEqual(5.0, record["singleGroovePose"]["imageMeasurement"]["azimuthDeg"])
            self.assertEqual(85.0, record["yDownTargetDiagnostic"]["measuredDeg"])
            self.assertEqual("PASS", record["yDownTargetDiagnostic"]["toleranceStatus"])
            self.assertEqual("accepted", record["grooveRefinement"]["status"])
            self.assertEqual("accepted", record["circleLocalization"]["status"])
            self.assertEqual({"accepted": 1}, summary["circleLocalizationStatusCounts"])
            self.assertNotIn(str(root), json.dumps(summary))
            self.assertTrue((output / "overlays/0001.jpg").is_file())
            self.assertTrue((output / "contact-sheet.jpg").is_file())
            candidates_csv = (output / "candidates.csv").read_text(encoding="utf-8")
            self.assertIn("candidate-001", candidates_csv)
            self.assertIn("radial_depth_too_small", candidates_csv)
            circle_candidates_csv = (output / "circle-candidates.csv").read_text(encoding="utf-8")
            self.assertIn("proposal-001", circle_candidates_csv)
            self.assertIn("circle-candidate-001", circle_candidates_csv)
            sidewall_csv = (output / "sidewall-models.csv").read_text(encoding="utf-8")
            self.assertIn("deterministic-consensus-tls-v2", sidewall_csv)
            self.assertIn("startSide", sidewall_csv)
            self.assertIn("rejected_point_count", sidewall_csv)
            failures = (output / "failures.csv").read_text(encoding="utf-8")
            self.assertIn("nested/frame.jpg", failures)
            self.assertIn("DATUM_DEFINITION_UNCONFIRMED", failures)
            self.assertIn("measured_y_down_deg", failures)


if __name__ == "__main__":
    unittest.main()
