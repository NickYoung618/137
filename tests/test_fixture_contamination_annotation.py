from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.dataset_common import sha256_file, write_json
from tools.prepare_fixture_contamination_annotation import (
    prepare_fixture_contamination_annotation,
)

try:
    import jsonschema
except ImportError:
    jsonschema = None


def auto_labelme(image_name: str) -> dict:
    def shape(label: str, points: list[list[float]], shape_type: str) -> dict:
        return {
            "label": label,
            "points": points,
            "group_id": None,
            "description": "AUTO suggestion",
            "shape_type": shape_type,
            "flags": {
                "auto_generated": True,
                "human_verified": False,
                "runtime_input_allowed": False,
            },
            "mask": None,
        }

    return {
        "version": "5.0.1",
        "flags": {
            "human_verified": False,
            "formal_truth": False,
            "runtime_input_allowed": False,
        },
        "shapes": [
            shape("AUTO_detected_groove_wall_left", [[1.0, 1.0], [2.0, 8.0]], "linestrip"),
            shape("AUTO_detected_groove_wall_right", [[8.0, 1.0], [7.0, 8.0]], "linestrip"),
            shape("AUTO_detected_mouth_endpoint_left", [[1.0, 1.0]], "point"),
            shape("AUTO_detected_mouth_endpoint_right", [[8.0, 1.0]], "point"),
        ],
        "imagePath": f"../raw/{image_name}",
        "imageData": None,
        "imageHeight": 10,
        "imageWidth": 10,
    }


class FixtureContaminationAnnotationTests(unittest.TestCase):
    def make_review_bundle(self, root: Path) -> tuple[Path, list[dict]]:
        (root / "raw").mkdir(parents=True)
        (root / "labelme-auto").mkdir()
        entries = []
        for index in (5, 7):
            image_id = f"normal:part-008:fixed-pose:{index:04d}"
            image_name = f"frame-{index:04d}.bmp"
            raw = root / "raw" / image_name
            raw.write_bytes(f"image-{index}".encode("ascii"))
            auto = root / "labelme-auto" / f"frame-{index:04d}.json"
            write_json(auto, auto_labelme(image_name))
            entries.append({
                "imageId": image_id,
                "relativeImagePath": f"A2/normal/{image_name}",
                "imageSha256": sha256_file(raw),
                "rawRelativePath": f"raw/{image_name}",
                "autoLabelmeRelativePath": f"labelme-auto/{auto.name}",
                "autoLabelmeSha256": sha256_file(auto),
                "humanVerified": False,
            })
        index_path = root / "review-index.json"
        write_json(index_path, {
            "schemaVersion": "slot-pose-prefill-review/2",
            "datasetId": "review",
            "entries": entries,
            "truthPolicy": {
                "autoShapesAreTruth": False,
                "runtimeInputAllowed": False,
                "humanMustReview": True,
            },
        })
        return index_path, entries

    def prepare(self, review_index: Path, image_ids: list[str], output: Path) -> dict:
        return prepare_fixture_contamination_annotation(
            review_index,
            image_ids,
            output,
            same_real_square_groove="YES",
            fully_visible_unoccluded="YES",
            endpoints_on_outer_shoulders="YES",
            fixture_shadow_overlap="PARTIAL",
        )

    def test_preserves_exact_semantics_and_auto_points_without_creating_human_truth(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            review_index, entries = self.make_review_bundle(root / "bundle")
            output = root / "contamination-review"
            report = self.prepare(
                review_index, [entry["imageId"] for entry in entries], output,
            )

            self.assertEqual("fixture-contamination-review/1", report["schemaVersion"])
            self.assertEqual(2, len(report["entries"]))
            for report_entry, source_entry in zip(report["entries"], entries):
                self.assertEqual({
                    "detectedWallsSameRealSquareGroove": "YES",
                    "grooveSidesFullyVisibleUnoccluded": "YES",
                    "endpointsOnRealOuterCircleShoulders": "YES",
                    "anyMarkedLineOnFixtureShadow": "YES",
                    "fixtureShadowContaminationExtent": "PARTIAL",
                }, report_entry["answers"])
                self.assertTrue(report_entry["semanticConclusions"]["realGrooveIdentityConfirmed"])
                self.assertTrue(report_entry["semanticConclusions"]["endpointSemanticsConfirmed"])
                self.assertFalse(report_entry["semanticConclusions"]["pixelTruthAvailable"])
                request = report_entry["annotationRequest"]
                self.assertEqual("UNCONFIRMED", request["affectedWall"])
                self.assertEqual("UNCONFIRMED", request["supportPointOverlap"])
                self.assertEqual("UNCONFIRMED", request["endpointOverlap"])
                self.assertEqual([
                    "HUMAN_fixture_shadow_overlap_on_detected_wall_left",
                    "HUMAN_fixture_shadow_overlap_on_detected_wall_right",
                ], request["allowedHumanLabels"])

                source = json.loads(
                    (review_index.parent / source_entry["autoLabelmeRelativePath"])
                    .read_text(encoding="utf-8")
                )
                derived = json.loads(
                    (output / request["derivedLabelmeRelativePath"]).read_text(encoding="utf-8")
                )
                self.assertEqual(source["shapes"], derived["shapes"])
                self.assertTrue(all(
                    shape["label"].startswith("AUTO_") for shape in derived["shapes"]
                ))
                self.assertFalse(derived["flags"]["auto_lines_are_pixel_truth"])
                self.assertFalse(derived["flags"]["threshold_tuning_allowed"])
                self.assertTrue(derived["flags"]["fixture_contamination_annotation_pending"])

            self.assertFalse(report["truthPolicy"]["autoLinesArePixelTruth"])
            self.assertFalse(report["truthPolicy"]["cleanAccuracyEvaluationAllowed"])
            self.assertFalse(report["truthPolicy"]["thresholdTuningAllowed"])
            self.assertFalse(report["truthPolicy"]["runtimeInputAllowed"])
            self.assertTrue((output / "fixture-contamination-review.json").is_file())
            if jsonschema is not None:
                schema = json.loads(
                    (Path(__file__).resolve().parents[1] / "contracts" /
                     "fixture-contamination-review.schema.json").read_text(encoding="utf-8")
                )
                jsonschema.Draft202012Validator.check_schema(schema)
                jsonschema.validate(report, schema)

    def test_rejects_unknown_identity_duplicate_selection_and_nonpartial_semantics(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            review_index, entries = self.make_review_bundle(root / "bundle")
            with self.assertRaisesRegex(ValueError, "unknown imageId"):
                self.prepare(review_index, ["normal:missing"], root / "unknown")
            with self.assertRaisesRegex(ValueError, "duplicate imageId"):
                self.prepare(
                    review_index, [entries[0]["imageId"], entries[0]["imageId"]],
                    root / "duplicate",
                )
            with self.assertRaisesRegex(ValueError, "exact semantic response"):
                prepare_fixture_contamination_annotation(
                    review_index, [entries[0]["imageId"]], root / "wrong-semantics",
                    same_real_square_groove="YES",
                    fully_visible_unoccluded="YES",
                    endpoints_on_outer_shoulders="YES",
                    fixture_shadow_overlap="NONE",
                )

    def test_rejects_hash_mismatch_human_content_and_git_internal_output(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            review_index, entries = self.make_review_bundle(root / "bundle")
            first = entries[0]
            auto_path = review_index.parent / first["autoLabelmeRelativePath"]
            auto_path.write_text(auto_path.read_text(encoding="utf-8") + " ", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "AUTO LabelMe SHA mismatch"):
                self.prepare(review_index, [first["imageId"]], root / "hash-mismatch")

            review_index, entries = self.make_review_bundle(root / "human-bundle")
            first = entries[0]
            auto_path = review_index.parent / first["autoLabelmeRelativePath"]
            payload = json.loads(auto_path.read_text(encoding="utf-8"))
            payload["shapes"].append({
                "label": "HUMAN_fixture_shadow_overlap_on_detected_wall_left",
                "points": [[1.0, 1.0], [1.5, 2.0]],
                "shape_type": "linestrip",
                "flags": {"human_verified": True},
            })
            write_json(auto_path, payload)
            first["autoLabelmeSha256"] = sha256_file(auto_path)
            write_json(review_index, {
                "schemaVersion": "slot-pose-prefill-review/2",
                "datasetId": "review",
                "entries": entries,
                "truthPolicy": {
                    "autoShapesAreTruth": False,
                    "runtimeInputAllowed": False,
                    "humanMustReview": True,
                },
            })
            with self.assertRaisesRegex(ValueError, "existing HUMAN"):
                self.prepare(review_index, [first["imageId"]], root / "human-content")

            project = Path(__file__).resolve().parents[1]
            with self.assertRaisesRegex(ValueError, "outside the Git worktree"):
                self.prepare(review_index, [entries[1]["imageId"]], project / "forbidden-output")


if __name__ == "__main__":
    unittest.main()
