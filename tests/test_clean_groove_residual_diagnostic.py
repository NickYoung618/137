from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from tools.compare_clean_groove_pixel_truth import (
    PROJECT_ROOT,
    build_clean_groove_residual_diagnostic,
    circular_difference_deg,
    percentile,
)
from tools.dataset_common import sha256_file

try:
    import jsonschema
except ImportError:
    jsonschema = None


def _point(label: str, x: float, y: float) -> dict[str, object]:
    return {"label": label, "shape_type": "point", "points": [[x, y]], "flags": {}}


class CleanGrooveResidualDiagnosticTests(unittest.TestCase):
    def _fixture(self, root: Path, *, image_id: str = "normal:part-008:fixed-pose:0005") -> tuple[Path, Path]:
        labelme_dir = root / "labelme-independent"
        labelme_dir.mkdir(parents=True)
        labelme = {
            "version": "5.0.0", "flags": {"human_verified": True, "annotation_pending": False,
            "independent_annotation": True, "copied_from_auto": False},
            "imagePath": "../raw/frame.bmp", "imageData": None, "imageWidth": 100, "imageHeight": 100,
            "shapes": [
                _point("HUMAN_clean_groove_wall_left_support", 10, 20),
                _point("HUMAN_clean_groove_wall_left_support", 10, 30),
                _point("HUMAN_clean_groove_wall_left_support", 10, 40),
                _point("HUMAN_clean_groove_wall_right_support", 30, 20),
                _point("HUMAN_clean_groove_wall_right_support", 30, 30),
                _point("HUMAN_clean_groove_wall_right_support", 30, 40),
                _point("HUMAN_clean_groove_mouth_endpoint_left", 10, 10),
                _point("HUMAN_clean_groove_mouth_endpoint_right", 30, 10),
            ],
        }
        labelme_path = labelme_dir / "frame.json"
        labelme_path.write_text(json.dumps(labelme), encoding="utf-8")
        image_sha = "1" * 64
        validation = {
            "schemaVersion": "clean-groove-pixel-review/1", "artifactType": "VALIDATION",
            "lifecycleStatus": "WALL_ENDPOINT_COMPLETE", "counts": {"images": 1, "pending": 0,
            "wallEndpointComplete": 1, "poseAngleAccuracyReady": 0},
            "entries": [{"imageId": image_id, "sourceImageSha256": image_sha,
                "labelmeRelativePath": "labelme-independent/frame.json", "imageWidth": 100, "imageHeight": 100,
                "labelmeSha256": sha256_file(labelme_path), "reviewStatus": "WALL_ENDPOINT_COMPLETE",
                "wallPixelTruthAvailable": True, "endpointPixelTruthAvailable": True,
                "outerCircleReferenceAvailable": False, "wallEndpointPixelReviewComplete": True,
                "poseAngleAccuracyReady": False, "geometryCounts": {"wallLeftSupportPoints": 3,
                "wallRightSupportPoints": 3, "mouthEndpointLeft": 1, "mouthEndpointRight": 1,
                "outerCircleVisibleArcPoints": 0, "outerCircleCenter": 0},
                "outerCircleReferenceMode": "NONE", "validationErrors": []}],
            "truthPolicy": {"accuracyEvaluationAllowed": False, "thresholdTuningAllowed": False,
                "runtimeInputAllowed": False, "plcInputAllowed": False},
        }
        validation_path = root / "validation.json"
        validation_path.write_text(json.dumps(validation), encoding="utf-8")
        source_consistency = {
            "schemaVersion": "groove-sidewall-source-consistency/1", "thresholdVersion": "v1",
            "enabled": True, "status": "rejected",
            "metrics": {"contrastNormalizedDifference": 0.18, "gradientNormalizedDifference": 0.2,
                "normalizedProfileMae": 0.02, "normalizedProfileCorrelation": 0.99,
                "radialCoverageDifference": 0.01, "endpointStructureDifference": 0.02},
            "checks": [
                {"checkId": "edge_contrast_asymmetry", "metric": "contrastNormalizedDifference",
                 "value": 0.18, "threshold": 0.12, "thresholdKind": "max", "margin": -0.06, "passed": False},
                {"checkId": "endpoint_structure_inconsistent", "metric": "endpointStructureDifference",
                 "value": 0.02, "threshold": 0.15, "thresholdKind": "max", "margin": 0.13, "passed": True},
            ], "failedChecks": ["edge_contrast_asymmetry"],
        }
        result = {"schemaVersion": "slot-pose-result/v2", "image": {"sha256": image_sha, "width": 100, "height": 100},
            "result": {"valid": False}, "diagnostics": {
                "physicalOuterCircle": {"status": "accepted", "physicalCircle": {"centerX": 20, "centerY": 80, "radiusPx": 70}},
                "grooveRefinement": {"status": "failed", "physicalRefinementStatus": "accepted",
                    "outerCircleIntersections": [{"x": 31, "y": 11}, {"x": 9, "y": 11}],
                    "startSide": {"line": {"a": 1, "b": 0, "c": -31}, "points": [[31, 20], [31, 30], [31, 40]]},
                    "endSide": {"line": {"a": 1, "b": 0, "c": -9}, "points": [[9, 20], [9, 30], [9, 40]]},
                    "sourceConsistency": source_consistency},
                "grooveSourceConsistency": source_consistency}}
        results_path = root / "results.jsonl"
        results_path.write_text(json.dumps(result) + "\n", encoding="utf-8")
        return validation_path, results_path

    def test_reports_wall_endpoint_and_conditional_direction_residuals(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            validation, results = self._fixture(root)
            output = root / "diagnostic.json"
            report = build_clean_groove_residual_diagnostic(validation, results, output)
            entry = report["entries"][0]
            self.assertEqual([1.0, 1.0, 1.0], entry["walls"]["left"]["humanToAutoLinePx"]["values"])
            self.assertAlmostEqual(1.0, entry["walls"]["right"]["humanToAutoLinePx"]["median"])
            self.assertAlmostEqual(0.0, entry["walls"]["left"]["unorientedLineAngleDifferenceDeg"])
            self.assertAlmostEqual(2 ** 0.5, entry["mouth"]["leftEndpointErrorPx"])
            self.assertAlmostEqual(1.0, entry["mouth"]["midpointErrorPx"])
            self.assertAlmostEqual(2.0, entry["mouth"]["widthDifferencePx"])
            self.assertTrue(entry["conditionalDirection"]["conditionalOnRuntimeCircleCenter"])
            self.assertTrue(entry["sourceConsistency"]["contrastOnlyFalseRejectionObserved"])
            self.assertFalse(report["policy"]["outerCircleErrorEvaluated"])
            self.assertFalse(report["policy"]["poseAngleAccuracyEvaluated"])
            self.assertNotIn("humanPoints", json.dumps(report))
            if jsonschema is not None:
                schema = json.loads((PROJECT_ROOT / "contracts" / "clean-groove-residual-diagnostic.schema.json").read_text())
                jsonschema.Draft202012Validator(schema).validate(report)

    def test_math_handles_percentile_and_circular_wrap(self) -> None:
        self.assertAlmostEqual(2.9, percentile([1.0, 2.0, 3.0], 95.0))
        self.assertAlmostEqual(2.0, circular_difference_deg(-179.0, 179.0))
        self.assertAlmostEqual(-2.0, circular_difference_deg(179.0, -179.0))

    def test_rejects_identity_state_geometry_and_output_failures(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            validation, results = self._fixture(root)
            payload = json.loads(validation.read_text())
            payload["entries"][0]["labelmeSha256"] = "0" * 64
            validation.write_text(json.dumps(payload))
            with self.assertRaisesRegex(ValueError, "LabelMe SHA-256 mismatch"):
                build_clean_groove_residual_diagnostic(validation, results, root / "bad.json")

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            validation, results = self._fixture(root)
            payload = json.loads(validation.read_text())
            payload["lifecycleStatus"] = "PENDING_HUMAN_ANNOTATION"
            validation.write_text(json.dumps(payload))
            with self.assertRaisesRegex(ValueError, "WALL_ENDPOINT_COMPLETE"):
                build_clean_groove_residual_diagnostic(validation, results, root / "bad.json")

        internal = PROJECT_ROOT / ".must-not-create-clean-residual.json"
        self.assertFalse(internal.exists())
        with self.assertRaisesRegex(ValueError, "outside the Git worktree"):
            build_clean_groove_residual_diagnostic(Path("missing"), Path("missing"), internal)
        self.assertFalse(internal.exists())

    def test_rejects_sealed_duplicate_sha_and_missing_circle(self) -> None:
        for mutation, message in (("sealed", "sealed sample"), ("duplicate", "duplicate runtime image SHA"),
                                  ("circle", "physical outer circle")):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                validation, results = self._fixture(root, image_id=(
                    "normal:part-006:fixed-pose:0001" if mutation == "sealed" else
                    "normal:part-008:fixed-pose:0005"))
                if mutation == "duplicate":
                    line = results.read_text()
                    results.write_text(line + line)
                if mutation == "circle":
                    row = json.loads(results.read_text())
                    del row["diagnostics"]["physicalOuterCircle"]
                    results.write_text(json.dumps(row) + "\n")
                with self.assertRaisesRegex(ValueError, message):
                    build_clean_groove_residual_diagnostic(validation, results, root / "bad.json")


if __name__ == "__main__":
    unittest.main()
