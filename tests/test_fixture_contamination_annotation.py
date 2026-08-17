from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from tools.prepare_fixture_contamination_annotation import (
    main,
    prepare_fixture_contamination_annotation,
)

try:
    import jsonschema
except ImportError:
    jsonschema = None


EXPECTED_DORMANT_TEXT = (
    "DORMANT/INAPPLICABLE after definitive human clarification A"
)


class FixtureContaminationAnnotationDormantTests(unittest.TestCase):
    def test_function_rejects_before_reading_source_or_creating_output(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / "must-not-exist"
            with self.assertRaisesRegex(ValueError, EXPECTED_DORMANT_TEXT):
                prepare_fixture_contamination_annotation(
                    root / "missing-review-index.json",
                    ["normal:part-008:fixed-pose:0005"],
                    output,
                    same_real_square_groove="YES",
                    fully_visible_unoccluded="YES",
                    endpoints_on_outer_shoulders="YES",
                    fixture_shadow_overlap="PARTIAL",
                )
            self.assertFalse(output.exists())

    def test_cli_rejects_every_invocation_without_writing_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / "must-not-exist"
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                return_code = main([
                    "--review-index", str(root / "missing-review-index.json"),
                    "--image-id", "normal:part-008:fixed-pose:0007",
                    "--same-real-square-groove", "YES",
                    "--fully-visible-unoccluded", "YES",
                    "--endpoints-on-outer-shoulders", "YES",
                    "--fixture-shadow-overlap", "PARTIAL",
                    "--output-dir", str(output),
                ])
            self.assertEqual(2, return_code)
            self.assertIn(EXPECTED_DORMANT_TEXT, stderr.getvalue())
            self.assertIn("groove walls are clean", stderr.getvalue())
            self.assertFalse(output.exists())

    def test_historical_schema_is_explicitly_dormant_and_audit_only(self) -> None:
        schema_path = (
            Path(__file__).resolve().parents[1]
            / "contracts"
            / "fixture-contamination-review.schema.json"
        )
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        lifecycle_note = str(schema.get("$comment") or "")
        self.assertIn("DORMANT_INAPPLICABLE_AFTER_CLARIFICATION_A", lifecycle_note)
        self.assertIn("historical audit only", lifecycle_note)
        if jsonschema is not None:
            jsonschema.Draft202012Validator.check_schema(schema)


if __name__ == "__main__":
    unittest.main()
