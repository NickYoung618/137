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
            self.assertEqual(2, len(record["singleRayRoleHypotheses"]))
            self.assertAlmostEqual(0.0, record["singleRayRoleHypotheses"][0]["drawingNominalDeviationDeg"])
            self.assertFalse(record["singleRayRoleHypotheses"][0]["authoritative"])
            self.assertNotIn(str(root), json.dumps(summary))
            self.assertTrue((output / "overlays/0001.jpg").is_file())
            self.assertTrue((output / "contact-sheet.jpg").is_file())
            self.assertIn("candidate-001", (output / "candidates.csv").read_text(encoding="utf-8"))
            failures = (output / "failures.csv").read_text(encoding="utf-8")
            self.assertIn("nested/frame.jpg", failures)
            self.assertIn("DATUM_DEFINITION_UNCONFIRMED", failures)


if __name__ == "__main__":
    unittest.main()
