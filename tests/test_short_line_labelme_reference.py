from __future__ import annotations

import copy
import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest.mock import patch

import numpy as np
from PIL import Image

from algorithms.end_face import short_line_candidate as short_line_module
from algorithms.end_face.short_line_candidate import (
    LABELME_REFERENCE_SCHEMA_VERSION,
    ShortLineCandidateEvaluator,
    load_labelme_short_line_reference,
)
from tests.end_face_test_support import DEFAULT_CANDIDATE_CONFIG, draw_short_line, synthetic_candidate_case
from tools.inspect_short_line_labelme import main as inspect_main


def write_labelme_reference(
    root: Path,
    *,
    shapes: list[dict] | None = None,
    declared_size: tuple[int, int] = (128, 128),
) -> Path:
    reference = root / "a2-short-line-reference.bmp"
    pixels = draw_short_line((64.0, 64.0), 0.0, 48.0)
    Image.fromarray(np.clip(pixels, 0, 255).astype(np.uint8)).save(reference)
    annotation = root / "a2-short-lines.json"
    payload = {
        "version": "5.5.0",
        "flags": {},
        "shapes": shapes if shapes is not None else [
            {"label": "19", "shape_type": "line", "points": [[40.0, 64.0], [88.0, 64.0]], "flags": {}},
            {"label": "30", "shape_type": "line", "points": [[49.0, 100.0], [79.0, 100.0]], "flags": {}},
        ],
        "imagePath": reference.name,
        "imageData": "embedded-content-must-not-be-emitted",
        "imageHeight": declared_size[1],
        "imageWidth": declared_size[0],
    }
    annotation.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return annotation


class ShortLineLabelMeReferenceTests(unittest.TestCase):
    def test_revoked_annotation_fingerprint_is_rejected_before_use(self) -> None:
        revoked_sha = "a175dd831fbc94913f9b9c69a04f81b0be7b58c0355118551c4447b967b3271c"
        with tempfile.TemporaryDirectory() as temporary:
            annotation = write_labelme_reference(Path(temporary))
            annotation_resolved = annotation.resolve()
            real_sha = short_line_module._sha256_file

            def fingerprint(path: Path, chunk_size: int = 1024 * 1024) -> str:
                if path.resolve() == annotation_resolved:
                    return revoked_sha
                return real_sha(path, chunk_size)

            with patch.object(short_line_module, "_sha256_file", side_effect=fingerprint):
                with self.assertRaisesRegex(ValueError, "revoked"):
                    load_labelme_short_line_reference(annotation)
                with redirect_stderr(io.StringIO()) as stderr:
                    self.assertEqual(2, inspect_main(["--annotation", str(annotation)]))
                self.assertIn("revoked", stderr.getvalue())
                model, _, _, _ = synthetic_candidate_case()
                with self.assertRaisesRegex(ValueError, "revoked"):
                    ShortLineCandidateEvaluator(
                        model,
                        DEFAULT_CANDIDATE_CONFIG,
                        labelme_reference_path=annotation,
                    )

    def test_valid_reference_catalog_is_image_free_and_hash_traceable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            annotation = write_labelme_reference(root)
            reference = load_labelme_short_line_reference(annotation)
            catalog = reference.catalog()
            output = root / "catalog.json"
            self.assertEqual(0, inspect_main(["--annotation", str(annotation), "--output", str(output)]))
            written = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(LABELME_REFERENCE_SCHEMA_VERSION, catalog["schemaVersion"])
        self.assertEqual({"19", "30"}, set(catalog["features"]))
        self.assertTrue(catalog["imageDataIgnored"])
        self.assertNotIn("imageData", catalog)
        self.assertNotIn("embedded-content-must-not-be-emitted", json.dumps(catalog))
        self.assertEqual(64, len(catalog["annotationSha256"]))
        self.assertEqual(catalog, written)

    def test_missing_duplicate_wrong_type_out_of_bounds_and_size_mismatch_fail_closed(self) -> None:
        valid_19 = {"label": "19", "shape_type": "line", "points": [[40.0, 64.0], [88.0, 64.0]]}
        valid_30 = {"label": "30", "shape_type": "line", "points": [[49.0, 100.0], [79.0, 100.0]]}
        cases = [
            ([valid_19], (128, 128)),
            ([valid_19, valid_30, copy.deepcopy(valid_30)], (128, 128)),
            ([valid_19, {**valid_30, "shape_type": "linestrip"}], (128, 128)),
            ([valid_19, {**valid_30, "points": [[49.0, 100.0], [129.0, 100.0]]}], (128, 128)),
            ([valid_19, valid_30], (127, 128)),
        ]
        for index, (shapes, size) in enumerate(cases):
            with self.subTest(case=index), tempfile.TemporaryDirectory() as temporary:
                annotation = write_labelme_reference(Path(temporary), shapes=shapes, declared_size=size)
                with self.assertRaises(ValueError):
                    load_labelme_short_line_reference(annotation)

    def test_external_labelme_template_can_recover_when_desktop_template_has_no_texture(self) -> None:
        model, target, measurements, features = synthetic_candidate_case(
            target_midpoint=(64.0, 86.0), target_angle_deg=3.0, core_valid=False
        )
        model.reference_grad = np.zeros_like(model.reference_grad)
        measurements_before = copy.deepcopy(measurements)
        features_before = copy.deepcopy(features)
        desktop = ShortLineCandidateEvaluator(model, DEFAULT_CANDIDATE_CONFIG).evaluate_gray(
            target, measurements, features
        )["19��"]
        with tempfile.TemporaryDirectory() as temporary:
            annotation = write_labelme_reference(Path(temporary))
            evaluator = ShortLineCandidateEvaluator(
                model,
                DEFAULT_CANDIDATE_CONFIG,
                labelme_reference_path=annotation,
            )
            external = evaluator.evaluate_gray(target, measurements, features)["19��"]
            provenance = evaluator.provenance

        self.assertFalse(desktop["candidate"]["candidateValid"])
        self.assertIn("template_texture", desktop["diagnostic"]["failedChecks"])
        self.assertTrue(external["candidate"]["candidateValid"], external["diagnostic"])
        self.assertEqual("recovered", external["transition"])
        self.assertEqual("external_labelme", provenance["referenceMode"])
        self.assertEqual(LABELME_REFERENCE_SCHEMA_VERSION, provenance["referenceSchemaVersion"])
        self.assertEqual(64, len(provenance["referenceAnnotationSha256"]))
        self.assertEqual(measurements_before, measurements)
        self.assertEqual(features_before, features)


if __name__ == "__main__":
    unittest.main()
