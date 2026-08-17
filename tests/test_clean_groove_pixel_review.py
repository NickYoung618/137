from __future__ import annotations

import json
import math
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from tools.dataset_common import sha256_file
from tools.prepare_clean_groove_pixel_review import (
    PROJECT_ROOT,
    main,
    prepare_clean_groove_pixel_review,
    validate_clean_groove_pixel_review,
)

try:
    import jsonschema
except ImportError:
    jsonschema = None


IMAGE_IDS = (
    "normal:part-008:fixed-pose:0005",
    "normal:part-008:fixed-pose:0007",
)


def _point(label: str, x: float, y: float) -> dict[str, object]:
    return {
        "label": label,
        "points": [[x, y]],
        "group_id": None,
        "description": "independent human point",
        "shape_type": "point",
        "flags": {},
    }


class CleanGroovePixelReviewTests(unittest.TestCase):
    def _source_bundle(self, root: Path) -> Path:
        raw_dir = root / "raw"
        auto_dir = root / "labelme-auto"
        raw_dir.mkdir(parents=True)
        auto_dir.mkdir()
        entries: list[dict[str, object]] = []
        for index, image_id in enumerate(IMAGE_IDS, start=1):
            raw = raw_dir / f"frame-{index}.bmp"
            Image.new("L", (32, 24), color=80 + index).save(raw)
            auto = auto_dir / f"frame-{index}.json"
            # Deliberately not JSON: preparation is allowed to hash this file but
            # must never parse or copy its AUTO geometry.
            auto.write_bytes(b"AUTO GEOMETRY MUST NOT BE PARSED")
            entries.append({
                "imageId": image_id,
                "relativeImagePath": f"A2/normal/frame-{index}.bmp",
                "imageSha256": sha256_file(raw),
                "rawRelativePath": f"raw/frame-{index}.bmp",
                "simplifiedRelativePath": f"simplified/frame-{index}.jpg",
                "simplifiedSha256": "a" * 64,
                "autoLabelmeRelativePath": f"labelme-auto/frame-{index}.json",
                "autoLabelmeSha256": sha256_file(auto),
                "humanVerified": False,
                "displaySummary": {"019Valid": True, "020ErrorCode": "NONE"},
                "reviewQuestions": ["q1", "q2", "q3", "q4"],
            })
        review_index = {
            "schemaVersion": "slot-pose-prefill-review/2",
            "datasetId": "a2-review-fixture",
            "counts": {"images": 2, "humanVerified": 0, "pending": 2},
            "entries": entries,
            "truthPolicy": {
                "autoShapesAreTruth": False,
                "runtimeInputAllowed": False,
                "humanMustReview": True,
            },
        }
        path = root / "review-index.json"
        path.write_text(json.dumps(review_index), encoding="utf-8")
        return path

    def _prepare(self, root: Path) -> tuple[Path, dict[str, object]]:
        source = root / "source"
        source.mkdir()
        review_index = self._source_bundle(source)
        output = root / "clean-review"
        payload = prepare_clean_groove_pixel_review(
            review_index, list(IMAGE_IDS), output,
            semantic_authority="FINAL_HUMAN_CLARIFICATION_A",
        )
        return output, payload

    def _complete_shapes(self, *, outer: str | None = None) -> list[dict[str, object]]:
        shapes = [
            _point("HUMAN_clean_groove_wall_left_support", 4, 4),
            _point("HUMAN_clean_groove_wall_left_support", 5, 8),
            _point("HUMAN_clean_groove_wall_left_support", 6, 12),
            _point("HUMAN_clean_groove_wall_right_support", 16, 4),
            _point("HUMAN_clean_groove_wall_right_support", 17, 8),
            _point("HUMAN_clean_groove_wall_right_support", 18, 12),
            _point("HUMAN_clean_groove_mouth_endpoint_left", 4, 3),
            _point("HUMAN_clean_groove_mouth_endpoint_right", 16, 3),
        ]
        if outer == "arc":
            shapes.append({
                "label": "HUMAN_outer_circle_visible_arc",
                "points": [[2 + value, 20 - value / 4] for value in range(8)],
                "group_id": None,
                "description": "independent visible outer-circle arc",
                "shape_type": "linestrip",
                "flags": {},
            })
        elif outer == "center":
            shapes.append(_point("HUMAN_outer_circle_center", 16, 12))
        return shapes

    def _mark_complete(self, path: Path, *, outer: str | None = None) -> None:
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["shapes"] = self._complete_shapes(outer=outer)
        payload["flags"]["human_verified"] = True
        payload["flags"]["annotation_pending"] = False
        path.write_text(json.dumps(payload), encoding="utf-8")

    def test_prepare_creates_blank_independent_tasks_without_parsing_auto(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output, payload = self._prepare(Path(temporary))
            self.assertEqual("clean-groove-pixel-review/1", payload["schemaVersion"])
            self.assertEqual("PREPARATION", payload["artifactType"])
            self.assertEqual(2, payload["counts"]["pending"])
            self.assertFalse(payload["truthPolicy"]["autoGeometryParsed"])
            self.assertFalse(payload["truthPolicy"]["autoCoordinatesCopied"])
            self.assertFalse(payload["truthPolicy"]["runtimeInputAllowed"])
            for entry in payload["entries"]:
                task = json.loads(
                    (output / entry["labelmeRelativePath"]).read_text(encoding="utf-8")
                )
                self.assertEqual([], task["shapes"])
                self.assertIsNone(task["imageData"])
                self.assertTrue(task["flags"]["independent_annotation"])
                self.assertFalse(task["flags"]["copied_from_auto"])
                self.assertFalse(task["flags"]["human_verified"])
                self.assertNotIn("AUTO_", json.dumps(task))
            if jsonschema is not None:
                schema = json.loads(
                    (PROJECT_ROOT / "contracts" / "clean-groove-pixel-review.schema.json")
                    .read_text(encoding="utf-8")
                )
                jsonschema.Draft202012Validator(schema).validate(payload)

    def test_prepare_rejects_identity_hash_path_and_policy_failures(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            source.mkdir()
            review_index = self._source_bundle(source)
            with self.assertRaisesRegex(ValueError, "duplicate imageId"):
                prepare_clean_groove_pixel_review(
                    review_index, [IMAGE_IDS[0], IMAGE_IDS[0]], root / "duplicate",
                    semantic_authority="FINAL_HUMAN_CLARIFICATION_A",
                )
            with self.assertRaisesRegex(ValueError, "unknown imageId"):
                prepare_clean_groove_pixel_review(
                    review_index, ["normal:part-999:fixed-pose:0001"], root / "unknown",
                    semantic_authority="FINAL_HUMAN_CLARIFICATION_A",
                )
            with self.assertRaisesRegex(ValueError, "sealed sample"):
                prepare_clean_groove_pixel_review(
                    review_index, ["normal:part-006:fixed-pose:0001"], root / "sealed",
                    semantic_authority="FINAL_HUMAN_CLARIFICATION_A",
                )
            source_payload = json.loads(review_index.read_text(encoding="utf-8"))
            source_payload["truthPolicy"]["autoShapesAreTruth"] = True
            review_index.write_text(json.dumps(source_payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "unsafe review truthPolicy"):
                prepare_clean_groove_pixel_review(
                    review_index, [IMAGE_IDS[0]], root / "unsafe-policy",
                    semantic_authority="FINAL_HUMAN_CLARIFICATION_A",
                )

    def test_prepare_rejects_sha_mismatch_existing_or_git_internal_output(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            source.mkdir()
            review_index = self._source_bundle(source)
            (source / "raw" / "frame-1.bmp").write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "raw image SHA-256 mismatch"):
                prepare_clean_groove_pixel_review(
                    review_index, [IMAGE_IDS[0]], root / "bad-sha",
                    semantic_authority="FINAL_HUMAN_CLARIFICATION_A",
                )
            output = root / "exists"
            output.mkdir()
            with self.assertRaisesRegex(ValueError, "must not already exist"):
                prepare_clean_groove_pixel_review(
                    review_index, [IMAGE_IDS[1]], output,
                    semantic_authority="FINAL_HUMAN_CLARIFICATION_A",
                )
        internal = PROJECT_ROOT / ".must-not-create-clean-groove-review"
        self.assertFalse(internal.exists())
        with self.assertRaisesRegex(ValueError, "outside the Git worktree"):
            prepare_clean_groove_pixel_review(
                Path("missing.json"), [IMAGE_IDS[0]], internal,
                semantic_authority="FINAL_HUMAN_CLARIFICATION_A",
            )
        self.assertFalse(internal.exists())

    def test_validate_wall_endpoints_then_optional_outer_reference(self) -> None:
        for outer, expected_ready in ((None, False), ("arc", True), ("center", True)):
            with self.subTest(outer=outer), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                output, task = self._prepare(root)
                for entry in task["entries"]:
                    self._mark_complete(output / entry["labelmeRelativePath"], outer=outer)
                report_path = root / "validation.json"
                report = validate_clean_groove_pixel_review(
                    output / "clean-groove-pixel-review.json", report_path,
                )
                self.assertTrue(report["counts"]["wallEndpointComplete"] == 2)
                self.assertEqual(2 if expected_ready else 0, report["counts"]["poseAngleReady"])
                for entry in report["entries"]:
                    self.assertTrue(entry["wallPixelTruthAvailable"])
                    self.assertTrue(entry["endpointPixelTruthAvailable"])
                    self.assertTrue(entry["wallEndpointPixelReviewComplete"])
                    self.assertEqual(expected_ready, entry["outerCircleReferenceAvailable"])
                    self.assertEqual(expected_ready, entry["poseAngleAccuracyReady"])
                self.assertFalse(report["truthPolicy"]["accuracyEvaluationAllowed"])
                self.assertFalse(report["truthPolicy"]["thresholdTuningAllowed"])
                self.assertFalse(report["truthPolicy"]["runtimeInputAllowed"])
                self.assertTrue(report_path.is_file())
                if jsonschema is not None:
                    schema = json.loads(
                        (PROJECT_ROOT / "contracts" / "clean-groove-pixel-review.schema.json")
                        .read_text(encoding="utf-8")
                    )
                    jsonschema.Draft202012Validator(schema).validate(report)

    def test_validate_rejects_incomplete_or_forbidden_geometry_without_report(self) -> None:
        invalid_mutations = {
            "too_few_wall_points": lambda shapes: shapes.pop(0),
            "duplicate_wall_point": lambda shapes: shapes.__setitem__(1, _point(
                "HUMAN_clean_groove_wall_left_support", 4, 4
            )),
            "missing_endpoint": lambda shapes: shapes.pop(6),
            "auto_shape": lambda shapes: shapes.append(_point("AUTO_detected_wall", 1, 1)),
            "fixture_overlap": lambda shapes: shapes.append(_point(
                "HUMAN_fixture_shadow_overlap_on_detected_wall_left", 1, 1
            )),
            "out_of_bounds": lambda shapes: shapes.__setitem__(0, _point(
                "HUMAN_clean_groove_wall_left_support", 99, 4
            )),
            "wrong_shape_type": lambda shapes: shapes[0].__setitem__("shape_type", "line"),
        }
        for name, mutate in invalid_mutations.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                output, task = self._prepare(root)
                for entry in task["entries"]:
                    path = output / entry["labelmeRelativePath"]
                    self._mark_complete(path)
                first = output / task["entries"][0]["labelmeRelativePath"]
                payload = json.loads(first.read_text(encoding="utf-8"))
                mutate(payload["shapes"])
                first.write_text(json.dumps(payload), encoding="utf-8")
                report = root / "must-not-exist.json"
                with self.assertRaises(ValueError):
                    validate_clean_groove_pixel_review(
                        output / "clean-groove-pixel-review.json", report,
                    )
                self.assertFalse(report.exists())

    def test_validate_rejects_nonfinite_and_auto_copy_attestation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output, task = self._prepare(root)
            for entry in task["entries"]:
                self._mark_complete(output / entry["labelmeRelativePath"])
            first = output / task["entries"][0]["labelmeRelativePath"]
            payload = json.loads(first.read_text(encoding="utf-8"))
            payload["flags"]["copied_from_auto"] = True
            payload["shapes"][0]["points"][0][0] = math.inf
            first.write_text(json.dumps(payload, allow_nan=True), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "copied_from_auto|finite"):
                validate_clean_groove_pixel_review(
                    output / "clean-groove-pixel-review.json", root / "invalid.json",
                )

    def test_contract_schema_is_draft_2020_12(self) -> None:
        schema = json.loads(
            (PROJECT_ROOT / "contracts" / "clean-groove-pixel-review.schema.json")
            .read_text(encoding="utf-8")
        )
        if jsonschema is not None:
            jsonschema.Draft202012Validator.check_schema(schema)

    def test_prepare_and_validate_cli(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            source.mkdir()
            review_index = self._source_bundle(source)
            output = root / "cli-review"
            self.assertEqual(0, main([
                "prepare", "--review-index", str(review_index),
                "--image-id", IMAGE_IDS[0], "--image-id", IMAGE_IDS[1],
                "--semantic-authority", "FINAL_HUMAN_CLARIFICATION_A",
                "--output-dir", str(output),
            ]))
            task = json.loads(
                (output / "clean-groove-pixel-review.json").read_text(encoding="utf-8")
            )
            for entry in task["entries"]:
                self._mark_complete(output / entry["labelmeRelativePath"])
            report = root / "cli-validation.json"
            self.assertEqual(0, main([
                "validate", "--task-manifest",
                str(output / "clean-groove-pixel-review.json"),
                "--output", str(report),
            ]))
            self.assertTrue(report.is_file())


if __name__ == "__main__":
    unittest.main()
