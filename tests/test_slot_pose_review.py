from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from tools.dataset_common import inspect_image
from tools.render_slot_pose_review import render_review


class SlotPoseReviewTests(unittest.TestCase):
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
                        "status": "accepted", "openingEndpointProfileDeg": [170.0, 180.0],
                        "openingMidpointProfileDeg": 175.0,
                        "outerCircleIntersections": [{"x": 30.0, "y": 55.0}, {"x": 25.0, "y": 50.0}],
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
            failures = (output / "failures.csv").read_text(encoding="utf-8")
            self.assertIn("nested/frame.jpg", failures)
            self.assertIn("DATUM_DEFINITION_UNCONFIRMED", failures)
            self.assertIn("measured_y_down_deg", failures)


if __name__ == "__main__":
    unittest.main()
