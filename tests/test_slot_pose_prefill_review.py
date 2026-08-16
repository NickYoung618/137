from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from tools.dataset_common import inspect_image
from tools.prepare_slot_pose_prefill_review import manifest_from_image_names, prepare_prefill_review

try:
    import jsonschema
except ImportError:
    jsonschema = None


def result(sha: str, *, source_rejected: bool = False) -> dict:
    return {
        "taskId": "review:i1", "schemaVersion": "slot-pose-result/3",
        "image": {"sha256": sha},
        "result": {"valid": False},
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
                "matches": [
                    {"templateId": "fixture-shadow-a", "candidateId": "candidate-001", "status": "matched"},
                    {"templateId": "fixture-shadow-b", "candidateId": "candidate-003", "status": "matched"},
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

    def test_generates_external_raw_overlays_contact_and_auto_labelme(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            data = root / "data"; data.mkdir()
            image = data / "frame.bmp"
            Image.new("L", (200, 200), 120).save(image)
            info = inspect_image(image)
            manifest = {
                "datasetId": "review", "images": [{
                    "imageId": "i1", "relativePath": "frame.bmp", **info,
                }],
            }
            output = root / "review"
            index = prepare_prefill_review(
                manifest, data, [result(info["sha256"])],
                [result(info["sha256"], source_rejected=True)], output,
            )
            self.assertEqual(1, index["counts"]["images"])
            for name in ("raw/i1.bmp", "overlay-019/i1.jpg", "overlay-020/i1.jpg", "contact-sheet.jpg", "review-index.json"):
                self.assertTrue((output / name).is_file(), name)
            labelme = json.loads((output / "labelme-auto/i1.json").read_text(encoding="utf-8"))
            self.assertFalse(labelme["flags"]["human_verified"])
            self.assertFalse(labelme["flags"]["runtime_input_allowed"])
            labels = {shape["label"] for shape in labelme["shapes"]}
            self.assertIn("AUTO_fitted_outer_circle", labels)
            self.assertIn("AUTO_fixture_shadow_candidate_a", labels)
            self.assertIn("AUTO_fixture_shadow_candidate_b", labels)
            self.assertIn("AUTO_detected_groove_wall_left", labels)
            self.assertIn("AUTO_detected_groove_wall_right", labels)
            self.assertIn("AUTO_detected_mouth_endpoint_left", labels)
            self.assertIn("AUTO_detected_mouth_endpoint_right", labels)
            self.assertTrue(all(label.startswith("AUTO_") for label in labels))
            self.assertNotIn(str(root), json.dumps(index))
            if jsonschema is not None:
                schema = json.loads(
                    (Path(__file__).resolve().parents[1] / "contracts" / "slot-pose-prefill-review.schema.json")
                    .read_text(encoding="utf-8")
                )
                jsonschema.Draft202012Validator(schema).validate(index)
            labelme["flags"]["human_verified"] = True
            (output / "labelme-auto/i1.json").write_text(json.dumps(labelme), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "refusing to overwrite"):
                prepare_prefill_review(
                    manifest, data, [result(info["sha256"])],
                    [result(info["sha256"], source_rejected=True)], output,
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
