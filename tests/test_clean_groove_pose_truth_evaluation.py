from __future__ import annotations

import copy
import json
import math
import tempfile
import unittest
from pathlib import Path

from tools.clean_groove_pose_truth_evaluation import (
    PROJECT_ROOT,
    build_clean_groove_pose_truth_evaluation,
    current_angle_deg,
    image_guidance,
    wrap_180_deg,
)
from tools.dataset_common import sha256_file

try:
    import jsonschema
except ImportError:
    jsonschema = None


def _point(center: tuple[float, float], radius: float, current_deg: float) -> list[float]:
    angle = math.radians(current_deg)
    return [center[0] - radius * math.sin(angle), center[1] + radius * math.cos(angle)]


def _arc(center=(250.0, 250.0), radius=180.0, *, start=-120.0, span=240.0, count=25):
    return [
        [
            center[0] + radius * math.cos(math.radians(start + span * index / (count - 1))),
            center[1] + radius * math.sin(math.radians(start + span * index / (count - 1))),
        ]
        for index in range(count)
    ]


def _shape(label: str, points: list[list[float]], shape_type: str = "point") -> dict[str, object]:
    return {"label": label, "shape_type": shape_type, "points": points, "flags": {}}


class CleanGroovePoseTruthEvaluationTests(unittest.TestCase):
    def _fixture(
        self,
        root: Path,
        *,
        current: float = 22.0,
        candidate_current: float = 23.0,
        arc_points: list[list[float]] | None = None,
        image_id: str = "normal:part-008:fixed-pose:0005",
    ) -> tuple[Path, Path]:
        center = (250.0, 250.0)
        radius = 180.0
        half_width = 4.0
        left_endpoint = _point(center, radius, current + half_width)
        right_endpoint = _point(center, radius, current - half_width)
        labelme_dir = root / "labelme-independent"
        labelme_dir.mkdir(parents=True)
        shapes = [
            _shape("HUMAN_clean_groove_wall_left_support", [[80, 180]]),
            _shape("HUMAN_clean_groove_wall_left_support", [[82, 200]]),
            _shape("HUMAN_clean_groove_wall_left_support", [[84, 220]]),
            _shape("HUMAN_clean_groove_wall_right_support", [[110, 180]]),
            _shape("HUMAN_clean_groove_wall_right_support", [[112, 200]]),
            _shape("HUMAN_clean_groove_wall_right_support", [[114, 220]]),
            _shape("HUMAN_clean_groove_mouth_endpoint_left", [left_endpoint]),
            _shape("HUMAN_clean_groove_mouth_endpoint_right", [right_endpoint]),
            _shape("HUMAN_outer_circle_visible_arc", arc_points or _arc(), "linestrip"),
        ]
        labelme = {
            "version": "5.0.0",
            "flags": {
                "human_verified": True,
                "independent_annotation": True,
                "copied_from_auto": False,
                "annotation_pending": False,
                "runtime_input_allowed": False,
                "threshold_tuning_allowed": False,
                "plc_input_allowed": False,
            },
            "imagePath": "../raw/frame.bmp",
            "imageData": None,
            "imageWidth": 500,
            "imageHeight": 500,
            "shapes": shapes,
        }
        labelme_path = labelme_dir / "frame.json"
        labelme_path.write_text(json.dumps(labelme), encoding="utf-8")
        image_sha = "1" * 64
        validation = {
            "schemaVersion": "clean-groove-pixel-review/1",
            "artifactType": "VALIDATION",
            "lifecycleStatus": "WALL_ENDPOINT_AND_OUTER_REFERENCE_COMPLETE",
            "semanticAuthority": "FINAL_HUMAN_CLARIFICATION_A",
            "counts": {"images": 1, "pending": 0, "wallEndpointComplete": 1, "poseAngleReady": 1},
            "entries": [{
                "imageId": image_id,
                "sourceImageSha256": image_sha,
                "labelmeRelativePath": "labelme-independent/frame.json",
                "imageWidth": 500,
                "imageHeight": 500,
                "labelmeSha256": sha256_file(labelme_path),
                "reviewStatus": "WALL_ENDPOINT_AND_OUTER_REFERENCE_COMPLETE",
                "wallPixelTruthAvailable": True,
                "endpointPixelTruthAvailable": True,
                "outerCircleReferenceAvailable": True,
                "wallEndpointPixelReviewComplete": True,
                "poseAngleAccuracyReady": True,
                "outerCircleReferenceMode": "VISIBLE_ARC",
                "geometryCounts": {
                    "wallLeftSupportPoints": 3,
                    "wallRightSupportPoints": 3,
                    "mouthEndpointLeft": 1,
                    "mouthEndpointRight": 1,
                    "outerCircleVisibleArcPoints": len(arc_points or _arc()),
                    "outerCircleCenter": 0,
                },
                "validationErrors": [],
            }],
            "truthPolicy": {
                "independentAnnotationRequired": True,
                "autoGeometryParsed": False,
                "autoCoordinatesCopied": False,
                "fixtureShadowBoundaryRequired": False,
                "accuracyEvaluationAllowed": False,
                "thresholdTuningAllowed": False,
                "runtimeInputAllowed": False,
                "plcInputAllowed": False,
            },
        }
        validation_path = root / "validation.json"
        validation_path.write_text(json.dumps(validation), encoding="utf-8")

        auto_left = _point(center, radius, candidate_current + half_width)
        auto_right = _point(center, radius, candidate_current - half_width)
        intersections = sorted((auto_left, auto_right), key=lambda item: item[0])
        result = {
            "schemaVersion": "slot-pose-result/v2",
            "image": {"sha256": image_sha, "width": 500, "height": 500},
            "result": {
                "valid": False,
                "detectionStatus": "DETECTION_FAILED",
                "guidanceStatus": "NOT_AVAILABLE",
                "currentAngleDeg": None,
                "correctionDeg": None,
                "plcCommand": None,
            },
            "diagnostics": {
                "physicalOuterCircle": {
                    "status": "accepted",
                    "physicalCircle": {"centerX": center[0], "centerY": center[1], "radiusPx": radius},
                },
                "grooveRefinement": {
                    "physicalRefinementStatus": "accepted",
                    "outerCircleIntersections": [
                        {"x": intersections[0][0], "y": intersections[0][1]},
                        {"x": intersections[1][0], "y": intersections[1][1]},
                    ],
                    "sourceConsistency": {
                        "status": "rejected",
                        "failedChecks": ["edge_contrast_asymmetry"],
                    },
                },
            },
        }
        results_path = root / "results.jsonl"
        results_path.write_text(json.dumps(result) + "\n", encoding="utf-8")
        return validation_path, results_path

    def test_evaluates_circle_angle_error_guidance_and_schema(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            validation, results = self._fixture(root, current=22.0, candidate_current=23.0)
            report = build_clean_groove_pose_truth_evaluation(validation, results, root / "report.json")
            entry = report["entries"][0]
            self.assertEqual("EVALUATED", entry["evaluationStatus"])
            self.assertTrue(entry["humanCircle"]["usable"])
            self.assertAlmostEqual(22.0, entry["finalPose"]["humanCurrentAngleDeg"], places=9)
            self.assertAlmostEqual(23.0, entry["finalPose"]["candidateCurrentAngleDeg"], places=9)
            self.assertAlmostEqual(1.0, entry["finalPose"]["candidateMinusHumanErrorDeg"], places=9)
            self.assertAlmostEqual(63.0, entry["finalPose"]["humanGuidance"]["correctionDeg"], places=9)
            self.assertEqual("CLOCKWISE", entry["finalPose"]["humanGuidance"]["rotationDirection"])
            self.assertTrue(entry["finalPose"]["candidateGeometryWithinMvpWindow"])
            self.assertFalse(report["policy"]["authoritative"])
            self.assertFalse(report["policy"]["posePromotionAllowed"])
            if jsonschema is not None:
                schema = json.loads((PROJECT_ROOT / "contracts/clean-groove-pose-truth-evaluation.schema.json").read_text())
                jsonschema.Draft202012Validator(schema).validate(report)

    def test_angle_math_wrap_deadband_and_direction(self) -> None:
        center = (100.0, 100.0)
        for current, expected_correction, direction in (
            (82.978, 0.0, "NONE"),
            (22.834, 62.166, "CLOCKWISE"),
            (-158.111, -116.889, "COUNTERCLOCKWISE"),
            (80.0, 0.0, "NONE"),
            (90.0, 0.0, "NONE"),
        ):
            point = _point(center, 80.0, current)
            measured = current_angle_deg(center, point)
            guidance = image_guidance(measured, point=point, center=center)
            self.assertAlmostEqual(current, measured, places=9)
            self.assertAlmostEqual(expected_correction, guidance["correctionDeg"], places=9)
            self.assertEqual(direction, guidance["rotationDirection"])
        self.assertEqual(-180.0, wrap_180_deg(180.0))
        self.assertAlmostEqual(-2.0, wrap_180_deg(358.0))

    def test_short_arc_is_diagnostic_only_and_final_fields_are_null(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            validation, results = self._fixture(root, arc_points=_arc(start=210.0, span=30.0, count=13))
            report = build_clean_groove_pose_truth_evaluation(validation, results, root / "report.json")
            entry = report["entries"][0]
            self.assertEqual("NOT_EVALUATED", entry["evaluationStatus"])
            self.assertIn("INSUFFICIENT_ARC_COVERAGE", entry["blockers"])
            self.assertFalse(entry["humanCircle"]["usable"])
            self.assertIsNotNone(entry["diagnosticOnly"]["humanCurrentAngleFromInitialKasaDeg"])
            self.assertIsNone(entry["circleComparison"])
            self.assertIsNone(entry["finalPose"])

    def test_duplicate_arc_points_do_not_satisfy_independent_point_gate(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            distinct = _arc(start=-120.0, span=240.0, count=7)
            repeated = distinct + [distinct[0], distinct[1]]
            validation, results = self._fixture(root, arc_points=repeated)
            report = build_clean_groove_pose_truth_evaluation(validation, results, root / "report.json")
            entry = report["entries"][0]
            self.assertEqual("NOT_EVALUATED", entry["evaluationStatus"])
            self.assertIn("INSUFFICIENT_ARC_UNIQUE_POINT_COUNT", entry["blockers"])
            self.assertIsNone(entry["finalPose"])

    @unittest.skipIf(jsonschema is None, "jsonschema not installed")
    def test_schema_rejects_status_that_claims_evaluation_without_final_pose(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            validation, results = self._fixture(root)
            report = build_clean_groove_pose_truth_evaluation(validation, results, root / "report.json")
            report["entries"][0]["evaluationStatus"] = "NOT_EVALUATED"
            schema = json.loads((PROJECT_ROOT / "contracts/clean-groove-pose-truth-evaluation.schema.json").read_text())
            with self.assertRaises(jsonschema.ValidationError):
                jsonschema.Draft202012Validator(schema).validate(report)

    def test_residual_and_leave_one_out_instability_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            noisy = _arc(count=25)
            for index, point in enumerate(noisy):
                if index % 2:
                    point[0] += 40.0
            validation, results = self._fixture(root, arc_points=noisy)
            report = build_clean_groove_pose_truth_evaluation(validation, results, root / "report.json")
            entry = report["entries"][0]
            self.assertEqual("NOT_EVALUATED", entry["evaluationStatus"])
            self.assertTrue(any(code.startswith("CIRCLE_") for code in entry["blockers"]))
            self.assertIsNone(entry["finalPose"])

    def test_rejects_upstream_identity_sealed_and_unsafe_output(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            validation, results = self._fixture(root)
            row = json.loads(results.read_text())
            del row["diagnostics"]["physicalOuterCircle"]
            results.write_text(json.dumps(row) + "\n")
            with self.assertRaisesRegex(ValueError, "physical outer circle"):
                build_clean_groove_pose_truth_evaluation(validation, results, root / "report.json")

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            validation, results = self._fixture(root, image_id="normal:part-006:fixed-pose:0001")
            with self.assertRaisesRegex(ValueError, "sealed sample"):
                build_clean_groove_pose_truth_evaluation(validation, results, root / "report.json")

        internal = PROJECT_ROOT / ".must-not-create-pose-truth-evaluation.json"
        self.assertFalse(internal.exists())
        with self.assertRaisesRegex(ValueError, "outside the Git worktree"):
            build_clean_groove_pose_truth_evaluation(Path("missing"), Path("missing"), internal)
        self.assertFalse(internal.exists())

    def test_labelme_sha_and_runtime_sha_fail_before_output(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            validation, results = self._fixture(root)
            payload = json.loads(validation.read_text())
            payload["entries"][0]["labelmeSha256"] = "0" * 64
            validation.write_text(json.dumps(payload))
            with self.assertRaisesRegex(ValueError, "LabelMe SHA-256 mismatch"):
                build_clean_groove_pose_truth_evaluation(validation, results, root / "report.json")

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            validation, results = self._fixture(root)
            results.write_text(results.read_text() + results.read_text())
            with self.assertRaisesRegex(ValueError, "duplicate runtime image SHA"):
                build_clean_groove_pose_truth_evaluation(validation, results, root / "report.json")


if __name__ == "__main__":
    unittest.main()
