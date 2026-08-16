import os
import tempfile
import unittest
from pathlib import Path

from algorithms.hole_2.current_capture import (
    AUTHORITATIVE_REFERENCE_ANNOTATION_SHA256,
    AUTHORITATIVE_REFERENCE_IMAGE_SHA256,
    load_authoritative_reference,
)


class AuthoritativeManualReferenceTests(unittest.TestCase):
    def test_frozen_external_reference_has_exact_shapes_and_hashes(self):
        root = Path(os.environ.get(
            "HOLE2_CURRENT_E2E_DIR",
            "/home/ubuntu/disk/dzk/hole2-latest-truth-20260815",
        ))
        annotation = root / "端面标注样品.json"
        image = root / "Pic_2026_08_12_214449_1.bmp"
        if not annotation.is_file() or not image.is_file():
            self.skipTest("external manual measurement template is unavailable")
        model = load_authoritative_reference(annotation, image)
        self.assertEqual(
            AUTHORITATIVE_REFERENCE_ANNOTATION_SHA256,
            "018e3449c051c15f7946315bd0d7f21cd79f4d4983efca0d11c7d98f02bfffa6",
        )
        self.assertEqual(
            AUTHORITATIVE_REFERENCE_IMAGE_SHA256,
            "faf357c2e6e8e58d667f76a3d9ed4f4d51ab4d451c2661cf0efbc641405b2d8b",
        )
        shapes = {shape.sanitized: shape for shape in model.shapes}
        self.assertEqual({"d7", "Phi12_2"}, set(shapes))
        self.assertEqual(2, len(shapes["d7"].points))
        self.assertEqual(80, len(shapes["Phi12_2"].points))

    def test_retired_reference_cannot_enter_runtime(self):
        old_root = Path(os.environ.get(
            "HOLE2_ASSET_DIR",
            "/home/ubuntu/disk/gyj/HousingInspectionDemo/algorithms/hole_2",
        ))
        annotation = old_root / "annotation.json"
        image = old_root / "reference.bmp"
        if not annotation.is_file() or not image.is_file():
            self.skipTest("external old registration reference is unavailable")
        with self.assertRaisesRegex(ValueError, "authoritative reference annotation SHA-256"):
            load_authoritative_reference(annotation, image)

    def test_missing_or_modified_template_fails_before_detection(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            annotation = root / "template.json"
            image = root / "template.bmp"
            annotation.write_text("{}", encoding="utf-8")
            image.write_bytes(b"not a bitmap")
            with self.assertRaisesRegex(ValueError, "authoritative reference annotation SHA-256"):
                load_authoritative_reference(annotation, image)
            with self.assertRaisesRegex(FileNotFoundError, "authoritative reference annotation"):
                load_authoritative_reference(root / "missing.json", image)


if __name__ == "__main__":
    unittest.main()
