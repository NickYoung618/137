from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from tools.dataset_common import inspect_image
from tools.prepare_slot_pose_prefill_review import (
    COLORS,
    _review_text_lines,
    manifest_from_image_names,
    prepare_prefill_review,
)

try:
    import jsonschema
except ImportError:
    jsonschema = None


def result(sha: str, *, source_rejected: bool = False, valid: bool = False) -> dict:
    return {
        "taskId": "review:i1", "schemaVersion": "slot-pose-result/3",
        "image": {"sha256": sha},
        "result": {"valid": valid},
        "error": {"code": "GROOVE_SOURCE_INCONSISTENT" if source_rejected else "GROOVE_RECOGNITION_FAILED"},
        "diagnostics": {
            "face": {"centerX": 100.0, "centerY": 100.0, "radiusPx": 80.0},
            "physicalOuterCircle": {
                "status": "accepted",
                "physicalCircle": {"centerX": 100.0, "centerY": 100.0, "radiusPx": 80.0},
            },
            "rawCandidates": [
                {"candidateId": "candidate-001", "centerDeg": 31.0, "halfWidthDeg": 10.0, "prominence": 100.0, "deficitArea": 300.0},
                {"candidateId": "candidate-002", "centerDeg": 297.0, "halfWidthDeg": 12.0, "prominence": 150.0, "deficitArea": 1400.0},
                {"candidateId": "candidate-003", "centerDeg": 328.0, "halfWidthDeg": 11.0, "prominence": 99.0, "deficitArea": 280.0},
            ],
            "grooveRecognition": {"assessments": []},
            "fixtureShadowEvidence": {
                "candidateMatches": [
                    {
                        "templateId": "fixture-shadow-a", "candidateId": "candidate-001",
                        "status": "matched", "centerDistanceDeg": 0.1,
                    },
                    {
                        "templateId": "fixture-shadow-b", "candidateId": "candidate-003",
                        "status": "not_matched", "centerDistanceDeg": 0.4,
                    },
                ]
            },
            "grooveRefinement": {
                "status": "failed" if source_rejected else "accepted",
                "startSide": {"points": [[65.0, 35.0], [68.0, 45.0], [70.0, 55.0]]},
                "endSide": {"points": [[125.0, 35.0], [122.0, 45.0], [120.0, 55.0]]},
                "outerCircleIntersections": [{"x": 65.0, "y": 35.0}, {"x": 125.0, "y": 35.0}],
            },
        },
    }


class PrefillReviewTests(unittest.TestCase):
    def test_explicit_image_names_build_truth_free_unique_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); (root / "nested").mkdir()
            image = root / "nested" / "Pic_374.bmp"; Image.new("L", (20, 10), 3).save(image)
            manifest = manifest_from_image_names(root, ["Pic_374.bmp"])
            self.assertEqual("nested/Pic_374.bmp", manifest["images"][0]["relativePath"])
            self.assertNotIn("truth", json.dumps(manifest).lower())
            duplicate = root / "other"; duplicate.mkdir(); Image.new("L", (20, 10), 3).save(duplicate / "Pic_374.bmp")
            with self.assertRaisesRegex(ValueError, "matched 2"):
                manifest_from_image_names(root, ["Pic_374.bmp"])

    def test_generates_two_row_raw_simplified_contact_and_minimal_auto_labelme(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            data = root / "data"; data.mkdir()
            first_image = data / "frame-374.bmp"
            second_image = data / "frame-369.bmp"
            Image.new("L", (200, 200), 120).save(first_image)
            Image.new("L", (200, 200), 121).save(second_image)
            first_info, second_info = inspect_image(first_image), inspect_image(second_image)
            manifest = {
                "datasetId": "review", "images": [
                    {"imageId": "part-019-374", "relativePath": "frame-374.bmp", **first_info},
                    {"imageId": "part-019-369", "relativePath": "frame-369.bmp", **second_info},
                ],
            }
            output = root / "review"
            index = prepare_prefill_review(
                manifest, data,
                [result(first_info["sha256"], valid=True), result(second_info["sha256"], valid=True)],
                [
                    result(first_info["sha256"], source_rejected=True),
                    result(second_info["sha256"], source_rejected=True),
                ],
                output,
            )
            self.assertEqual(2, index["counts"]["images"])
            for name in (
                "raw/part-019-374.bmp", "raw/part-019-369.bmp",
                "simplified/part-019-374.png", "simplified/part-019-369.png",
                "contact-sheet.jpg", "review-index.json",
            ):
                self.assertTrue((output / name).is_file(), name)
            self.assertFalse((output / "overlay-019").exists())
            self.assertFalse((output / "overlay-020").exists())

            with Image.open(output / "simplified/part-019-374.png") as simplified:
                self.assertEqual((200, 200), simplified.size)
                colors = set(simplified.convert("RGB").get_flattened_data())
            for name in (
                "wall_left", "wall_right", "endpoint_left", "endpoint_right", "fixture",
            ):
                self.assertIn(tuple(bytes.fromhex(COLORS[name][1:])), colors, name)
            self.assertNotIn("circle", COLORS)
            self.assertNotIn("raw", COLORS)

            with Image.open(output / "contact-sheet.jpg") as contact:
                self.assertEqual(2, contact.width // 560)
                self.assertEqual(2, contact.height // 412)

            labelme = json.loads(
                (output / "labelme-auto/part-019-374.json").read_text(encoding="utf-8")
            )
            self.assertFalse(labelme["flags"]["human_verified"])
            self.assertFalse(labelme["flags"]["runtime_input_allowed"])
            labels = {shape["label"] for shape in labelme["shapes"]}
            self.assertEqual({
                "AUTO_fixture_shadow_candidate_a", "AUTO_fixture_shadow_candidate_b",
                "AUTO_detected_groove_wall_left", "AUTO_detected_groove_wall_right",
                "AUTO_detected_mouth_endpoint_left", "AUTO_detected_mouth_endpoint_right",
            }, labels)
            self.assertTrue(all(label.startswith("AUTO_") for label in labels))
            self.assertTrue(all(
                shape["flags"]["human_verified"] is False for shape in labelme["shapes"]
            ))
            fixtures = {
                shape["label"]: shape for shape in labelme["shapes"]
                if shape["label"].startswith("AUTO_fixture_shadow_candidate_")
            }
            self.assertEqual("polygon", fixtures["AUTO_fixture_shadow_candidate_a"]["shape_type"])
            self.assertTrue(
                fixtures["AUTO_fixture_shadow_candidate_a"]["flags"]["region_supported"]
            )
            self.assertEqual("line", fixtures["AUTO_fixture_shadow_candidate_b"]["shape_type"])
            self.assertFalse(
                fixtures["AUTO_fixture_shadow_candidate_b"]["flags"]["region_supported"]
            )
            self.assertTrue(all(
                shape["flags"]["candidate_only"] and
                shape["flags"]["display_color"] == COLORS["fixture"]
                for shape in fixtures.values()
            ))
            serialized = json.dumps(labelme).lower()
            for forbidden in ("fitted_outer_circle", "raw_dark_candidate", '"rectangle"', "human_truth"):
                self.assertNotIn(forbidden, serialized)

            entry = index["entries"][0]
            self.assertEqual("simplified/part-019-374.png", entry["simplifiedRelativePath"])
            self.assertNotIn("overlay019RelativePath", entry)
            self.assertNotIn("overlay020RelativePath", entry)
            self.assertTrue(entry["displaySummary"]["019Valid"])
            self.assertEqual(
                "GROOVE_SOURCE_INCONSISTENT", entry["displaySummary"]["020ErrorCode"],
            )
            lines = _review_text_lines(
                result(first_info["sha256"], valid=True),
                result(first_info["sha256"], source_rejected=True),
            )
            self.assertIn("019 valid=True", lines[0])
            self.assertIn("020 error=GROOVE_SOURCE_INCONSISTENT", lines[0])
            self.assertIn("020 fixture candidate != valid", lines)
            self.assertIn("HUMAN CONFIRMATION REQUIRED: real groove", lines)
            self.assertNotIn(str(root), json.dumps(index))
            if jsonschema is not None:
                schema = json.loads(
                    (Path(__file__).resolve().parents[1] / "contracts" / "slot-pose-prefill-review.schema.json")
                    .read_text(encoding="utf-8")
                )
                jsonschema.Draft202012Validator(schema).validate(index)
            labelme["flags"]["human_verified"] = True
            (output / "labelme-auto/part-019-374.json").write_text(
                json.dumps(labelme), encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "refusing to overwrite"):
                prepare_prefill_review(
                    manifest, data,
                    [result(first_info["sha256"]), result(second_info["sha256"])],
                    [
                        result(first_info["sha256"], source_rejected=True),
                        result(second_info["sha256"], source_rejected=True),
                    ],
                    output,
                )

    def test_hash_mismatch_rejects_before_writing_review(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            data = root / "data"; data.mkdir()
            image = data / "frame.bmp"; Image.new("L", (20, 20), 1).save(image)
            info = inspect_image(image)
            manifest = {"datasetId": "review", "images": [{"imageId": "i1", "relativePath": "frame.bmp", **info}]}
            bad = result("f" * 64)
            with self.assertRaisesRegex(ValueError, "result SHA"):
                prepare_prefill_review(manifest, data, [bad], [bad], root / "review")


if __name__ == "__main__":
    unittest.main()
