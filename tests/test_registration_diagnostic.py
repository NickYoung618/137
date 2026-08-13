from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

try:
    import jsonschema
except ImportError:
    jsonschema = None

from tests.test_main_housing_registration import housing_image
from algorithms.end_face import CORE_SOURCE_SHA256
from tools.diagnose_main_housing_registration import main as diagnostic_main
from tools.make_manifest import build_manifest
from tools.dataset_common import write_json


ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_RESULT_KEYS = {"candidateValid", "transition", "recovered", "coreValid", "measurements"}


class RegistrationDiagnosticTests(unittest.TestCase):
    def _assets(self, root: Path) -> tuple[Path, Path, Path, Path]:
        reference = root / "reference.bmp"
        data_root = root / "targets"
        data_root.mkdir()
        target = data_root / "frame-001.bmp"
        Image.fromarray(housing_image((190.0, 210.0), 140.0).astype("uint8")).save(reference)
        Image.fromarray(housing_image((245.0, 205.0), 140.0).astype("uint8")).save(target)
        config = json.loads((ROOT / "config/end_face_short_line_candidate.v2.json").read_text(encoding="utf-8"))
        config = copy.deepcopy(config)
        config["registration"]["minimumDiameterPx"] = 100.0
        config_path = root / "candidate-v2.json"
        config_path.write_text(json.dumps(config), encoding="utf-8")
        return reference, data_root, target, config_path

    def _assert_registration_only(self, payload: object) -> None:
        serialized = json.dumps(payload, ensure_ascii=False, allow_nan=False)
        for forbidden in FORBIDDEN_RESULT_KEYS:
            self.assertNotIn(f'"{forbidden}"', serialized)

    def test_single_emits_strict_registration_only_json(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            reference, _, target, config = self._assets(root)
            output = root / "diagnostic.json"
            code = diagnostic_main([
                "single",
                "--reference-image", str(reference),
                "--target-image", str(target),
                "--candidate-config", str(config),
                "--output", str(output),
            ])
            payload = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(0, code)
        self.assertEqual("succeeded", payload["technicalStatus"])
        self.assertEqual(CORE_SOURCE_SHA256, payload["algorithm"]["coreSourceSha256"])
        self.assertTrue(payload["registration"]["valid"])
        self._assert_registration_only(payload)

    def test_batch_emits_jsonl_and_summary_without_candidate_semantics(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            reference, data_root, _, config = self._assets(root)
            manifest = build_manifest(data_root, "synthetic-registration", "a_end_face", 1, "sample", "pos")
            manifest_path = root / "manifest.json"
            write_json(manifest_path, manifest)
            output_dir = root / "output"
            code = diagnostic_main([
                "batch",
                "--reference-image", str(reference),
                "--manifest", str(manifest_path),
                "--data-root", str(data_root),
                "--candidate-config", str(config),
                "--output-dir", str(output_dir),
            ])
            records = [json.loads(line) for line in (output_dir / "registration-diagnostics.jsonl").read_text(encoding="utf-8").splitlines()]
            summary = json.loads((output_dir / "registration-summary.json").read_text(encoding="utf-8"))
        self.assertEqual(0, code)
        self.assertEqual(1, len(records))
        self.assertEqual(CORE_SOURCE_SHA256, summary["algorithm"]["coreSourceSha256"])
        self.assertEqual(1, summary["registration"]["valid"])
        self._assert_registration_only(records)
        self._assert_registration_only(summary)

    @unittest.skipIf(jsonschema is None, "jsonschema is installed by the explicit Schema gate")
    def test_single_and_batch_outputs_match_schemas(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            reference, data_root, target, config = self._assets(root)
            single_output = root / "diagnostic.json"
            self.assertEqual(0, diagnostic_main([
                "single",
                "--reference-image", str(reference),
                "--target-image", str(target),
                "--candidate-config", str(config),
                "--output", str(single_output),
            ]))
            manifest = build_manifest(data_root, "synthetic-registration", "a_end_face", 1, "sample", "pos")
            manifest_path = root / "manifest.json"
            write_json(manifest_path, manifest)
            output_dir = root / "batch-output"
            self.assertEqual(0, diagnostic_main([
                "batch",
                "--reference-image", str(reference),
                "--manifest", str(manifest_path),
                "--data-root", str(data_root),
                "--candidate-config", str(config),
                "--output-dir", str(output_dir),
            ]))
            diagnostic = json.loads(single_output.read_text(encoding="utf-8"))
            summary = json.loads((output_dir / "registration-summary.json").read_text(encoding="utf-8"))
        diagnostic_schema = json.loads(
            (ROOT / "contracts/a-end-face-main-housing-registration-diagnostic.schema.json").read_text(encoding="utf-8")
        )
        summary_schema = json.loads(
            (ROOT / "contracts/a-end-face-main-housing-registration-summary.schema.json").read_text(encoding="utf-8")
        )
        jsonschema.Draft202012Validator.check_schema(diagnostic_schema)
        jsonschema.Draft202012Validator.check_schema(summary_schema)
        jsonschema.validate(diagnostic, diagnostic_schema)
        jsonschema.validate(summary, summary_schema)

    @unittest.skipIf(jsonschema is None, "jsonschema is installed by the explicit Schema gate")
    def test_unreadable_target_emits_schema_valid_technical_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            reference, _, _, config = self._assets(root)
            target = root / "not-an-image.bmp"
            target.write_bytes(b"not an image")
            output = root / "diagnostic.json"
            code = diagnostic_main([
                "single",
                "--reference-image", str(reference),
                "--target-image", str(target),
                "--candidate-config", str(config),
                "--output", str(output),
            ])
            payload = json.loads(output.read_text(encoding="utf-8"))
        schema = json.loads(
            (ROOT / "contracts/a-end-face-main-housing-registration-diagnostic.schema.json").read_text(encoding="utf-8")
        )
        self.assertEqual(1, code)
        self.assertEqual("failed", payload["technicalStatus"])
        self.assertIsNone(payload["registration"])
        jsonschema.validate(payload, schema)
        self._assert_registration_only(payload)


if __name__ == "__main__":
    unittest.main()
