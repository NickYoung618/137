from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

try:
    import jsonschema
except ImportError:  # Installed transiently by the Schema gate.
    jsonschema = None

from tests.end_face_test_support import DEFAULT_CANDIDATE_CONFIG
from tests.test_short_line_comparison import comparison_record
from algorithms.end_face.contract import failure_result, success_result
from algorithms.end_face.quality import evaluate_quality, load_quality_policy
from algorithms.end_face.short_line_candidate import load_labelme_short_line_reference
from tests.test_short_line_labelme_reference import write_labelme_reference
from tools.compare_short_line_candidates import summarize_comparisons


ROOT = Path(__file__).resolve().parents[1]


@unittest.skipIf(jsonschema is None, "jsonschema is installed by the explicit Schema gate")
class EndFaceSchemaTests(unittest.TestCase):
    def validate(self, schema_name: str, payload: dict) -> None:
        schema = json.loads((ROOT / "contracts" / schema_name).read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator.check_schema(schema)
        jsonschema.validate(payload, schema)

    def test_candidate_config_schema(self) -> None:
        self.validate("a-end-face-short-line-candidate-config.schema.json", DEFAULT_CANDIDATE_CONFIG)

    def test_labelme_short_line_reference_catalog_schema(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            catalog = load_labelme_short_line_reference(
                write_labelme_reference(Path(temporary))
            ).catalog()
        self.validate("a-end-face-labelme-short-line-reference.schema.json", catalog)

    def test_result_v3_success_and_failure_schema(self) -> None:
        policy_path = ROOT / "config/end_face_quality.example.json"
        measurements = {
            "transform.target_center_x_px": 4.0,
            "transform.target_center_y_px": 3.0,
            "transform.scale": 1.0,
            "transform.rotation_deg": 0.0,
        }
        quality = evaluate_quality(
            measurements,
            "circle-alignment rotation_score=10.0, notch_check(Δ=0deg, prom=20.0)",
            (8, 6),
            load_quality_policy(policy_path),
            policy_path,
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            image = root / "image.bin"
            annotation = root / "annotation.json"
            reference = root / "reference.bin"
            image.write_bytes(b"image")
            annotation.write_text("{}", encoding="utf-8")
            reference.write_bytes(b"reference")
            success = success_result(
                task_id="schema-success",
                image=image,
                image_info={"bytes": 5, "sha256": "0" * 64, "format": "BIN", "width": 8, "height": 6, "mode": "L"},
                annotation=annotation,
                reference=reference,
                pixel_size=1.0,
                shift_method="circle-alignment rotation_score=10.0, notch_check(Δ=0deg, prom=20.0)",
                measurements=measurements,
                quality=quality,
                elapsed_ms=1.0,
            )
            failure = failure_result(
                task_id="schema-failure",
                image=image,
                annotation=annotation,
                error=ValueError("synthetic"),
            )
        self.validate("a-end-face-result.schema.json", success)
        self.validate("a-end-face-result.schema.json", failure)

    def test_comparison_and_summary_schemas(self) -> None:
        record = comparison_record("schema", "recovered", "both_invalid")
        self.validate("a-end-face-short-line-comparison.schema.json", record)
        self.validate(
            "a-end-face-short-line-batch-summary.schema.json",
            summarize_comparisons([record], {"datasetId": "schema"}),
        )


if __name__ == "__main__":
    unittest.main()
