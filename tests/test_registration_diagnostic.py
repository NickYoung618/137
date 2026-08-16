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
from tools.diagnose_main_housing_registration import (
    circular_distribution,
    linear_distribution,
    main as diagnostic_main,
    summarize_registration_stability,
)
from tools.make_manifest import build_manifest
from tools.dataset_common import write_json


ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_RESULT_KEYS = {
    "candidateValid",
    "transition",
    "recovered",
    "coreValid",
    "measurements",
    "localization",
    "measurementCompleteness",
    "completeness",
}


class RegistrationDiagnosticTests(unittest.TestCase):
    @staticmethod
    def _registration_record(
        *,
        center: tuple[float, float] = (250.0, 200.0),
        radius: float | None = 100.0,
        scale: float = 1.0,
        rotation: float = 0.0,
        width: int = 1000,
        height: int = 500,
        selected_index: int = 7,
        valid: bool = True,
        technical_status: str = "succeeded",
    ) -> dict:
        hypotheses = [] if radius is None else [{
            "componentIndex": selected_index,
            "radiusPx": radius,
            "edgeCoverageRatio": 0.8,
            "circularResidualRatio": 0.01,
        }]
        return {
            "technicalStatus": technical_status,
            "input": {"targetImage": {"width": width, "height": height}},
            "registration": {
                "valid": valid,
                "selectedIndex": selected_index,
                "selectionMargin": 0.2,
                "transform": {
                    "targetCenterPx": list(center),
                    "scale": scale,
                    "rotationDeg": rotation,
                },
                "rotationScore": 0.9,
                "rotationMargin": 0.1,
                "hypotheses": hypotheses,
            },
        }

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

    def test_linear_distribution_has_deterministic_known_values(self) -> None:
        distribution = linear_distribution([1.0, 2.0, 3.0, float("nan"), True])
        self.assertEqual(3, distribution["count"])
        self.assertEqual(1.0, distribution["minimum"])
        self.assertEqual(3.0, distribution["maximum"])
        self.assertEqual(2.0, distribution["mean"])
        self.assertEqual(2.0, distribution["median"])
        self.assertAlmostEqual(1.1, distribution["p05"], places=12)
        self.assertAlmostEqual(2.9, distribution["p95"], places=12)
        self.assertEqual(1.0, distribution["medianAbsoluteDeviation"])

    def test_circular_distribution_handles_wrap_and_single_frame(self) -> None:
        wrapped = circular_distribution([179.0, -179.0])
        self.assertEqual(2, wrapped["count"])
        self.assertLessEqual(abs(abs(wrapped["circularMeanDeg"]) - 180.0), 1e-9)
        self.assertGreater(wrapped["resultantLength"], 0.99)
        self.assertLessEqual(wrapped["maximumAbsoluteDeviationDeg"], 1.1)
        single = circular_distribution([42.0])
        self.assertEqual(42.0, single["circularMeanDeg"])
        self.assertEqual(1.0, single["resultantLength"])
        self.assertEqual(0.0, single["circularStdDeg"])
        self.assertEqual(0.0, single["maximumAbsoluteDeviationDeg"])

    def test_stability_extracts_valid_geometry_and_normalizes_per_frame(self) -> None:
        records = [
            self._registration_record(center=(250.0, 200.0), radius=100.0, scale=1.0, rotation=179.0),
            self._registration_record(
                center=(600.0, 300.0),
                radius=200.0,
                scale=1.1,
                rotation=-179.0,
                width=1200,
                height=600,
            ),
        ]
        stability = summarize_registration_stability(records)
        self.assertEqual(2, stability["eligibleRecordCount"])
        self.assertEqual(2, stability["targetCenterXPx"]["count"])
        self.assertEqual(425.0, stability["targetCenterXPx"]["mean"])
        self.assertEqual(0.375, stability["targetCenterXRatio"]["mean"])
        self.assertAlmostEqual((0.2 + (1.0 / 3.0)) / 2.0, stability["targetRadiusRatio"]["mean"])
        self.assertEqual(2, stability["edgeCoverageRatio"]["count"])
        self.assertGreater(stability["rotationDeg"]["resultantLength"], 0.99)

    def test_stability_empty_mixed_missing_and_nonfinite_values_are_safe(self) -> None:
        invalid = self._registration_record(valid=False)
        technical_failure = self._registration_record(technical_status="failed")
        empty = summarize_registration_stability([invalid, technical_failure])
        self.assertEqual(0, empty["eligibleRecordCount"])
        for name, distribution in empty.items():
            if name == "eligibleRecordCount":
                continue
            self.assertEqual(0, distribution["count"], name)
            for field, value in distribution.items():
                if field != "count":
                    self.assertIsNone(value, f"{name}.{field}")

        complete = self._registration_record()
        partial = self._registration_record(
            center=(float("nan"), 100.0),
            radius=None,
            scale=float("inf"),
            rotation=float("nan"),
        )
        mixed = summarize_registration_stability([complete, partial, invalid])
        self.assertEqual(2, mixed["eligibleRecordCount"])
        self.assertEqual(1, mixed["targetCenterXPx"]["count"])
        self.assertEqual(2, mixed["targetCenterYPx"]["count"])
        self.assertEqual(1, mixed["targetRadiusPx"]["count"])
        self.assertEqual(1, mixed["scale"]["count"])
        self.assertEqual(1, mixed["rotationDeg"]["count"])
        json.dumps(mixed, allow_nan=False)

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
        self.assertEqual("a-end-face-main-housing-registration-summary/2", summary["schemaVersion"])
        self.assertEqual(1, summary["registration"]["valid"])
        self.assertEqual(1, summary["stability"]["eligibleRecordCount"])
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
            (ROOT / "contracts/a-end-face-main-housing-registration-summary-v2.schema.json").read_text(encoding="utf-8")
        )
        historical_schema = json.loads(
            (ROOT / "contracts/a-end-face-main-housing-registration-summary.schema.json").read_text(encoding="utf-8")
        )
        jsonschema.Draft202012Validator.check_schema(diagnostic_schema)
        jsonschema.Draft202012Validator.check_schema(summary_schema)
        self.assertEqual("a-end-face-main-housing-registration-summary/1", historical_schema["$id"])
        jsonschema.validate(diagnostic, diagnostic_schema)
        jsonschema.validate(summary, summary_schema)

    @unittest.skipIf(jsonschema is None, "jsonschema is installed by the explicit Schema gate")
    def test_all_registration_invalid_batch_has_schema_valid_empty_stability(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            reference, data_root, target, config = self._assets(root)
            Image.new("L", (640, 420), 0).save(target)
            manifest = build_manifest(data_root, "synthetic-invalid-registration", "a_end_face", 1, "sample", "pos")
            manifest_path = root / "manifest.json"
            write_json(manifest_path, manifest)
            output_dir = root / "output"
            self.assertEqual(0, diagnostic_main([
                "batch",
                "--reference-image", str(reference),
                "--manifest", str(manifest_path),
                "--data-root", str(data_root),
                "--candidate-config", str(config),
                "--output-dir", str(output_dir),
            ]))
            summary = json.loads((output_dir / "registration-summary.json").read_text(encoding="utf-8"))
        schema = json.loads(
            (ROOT / "contracts/a-end-face-main-housing-registration-summary-v2.schema.json").read_text(encoding="utf-8")
        )
        self.assertEqual(0, summary["registration"]["valid"])
        self.assertEqual(0, summary["stability"]["eligibleRecordCount"])
        for name, distribution in summary["stability"].items():
            if name != "eligibleRecordCount":
                self.assertEqual(0, distribution["count"], name)
        jsonschema.validate(summary, schema)
        self._assert_registration_only(summary)

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
