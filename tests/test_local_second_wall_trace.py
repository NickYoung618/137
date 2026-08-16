from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.extract_local_second_wall_trace import build_trace_export, main

try:
    import jsonschema
except ImportError:
    jsonschema = None


def payload(name: str) -> dict:
    digest = "a" * 64
    return {
        "image": {"path": f"/private/source/{name}"},
        "algorithm": {
            "version": "0.14.0", "configSha256": digest,
            "effectiveConfigSha256": "b" * 64,
        },
        "result": {"valid": False},
        "error": {"code": "GROOVE_SOURCE_INCONSISTENT"},
        "diagnostics": {
            "localSecondWallDiagnostic": {
                "schemaVersion": "local-second-wall-diagnostic/2",
                "status": "SOURCE_INCONSISTENT", "errorCode": "SOURCE_INCONSISTENT",
                "localInterval": {"startDeg": 285.0, "endDeg": 309.0},
                "sideSearchCandidates": [{
                    "searchCandidateId": "rising-wall-search-001", "seedDeg": 290.0,
                    "intersectionAngleDeg": 309.0, "rejectionStage": None,
                    "mergeClusterId": "rising-merge-cluster-001",
                }],
                "sideSearchMergeClusters": [{
                    "clusterId": "rising-merge-cluster-001",
                    "memberSearchCandidateIds": ["rising-wall-search-001"],
                }],
                "hypotheses": [{"hypothesisId": "local-wall-hypothesis-001"}],
            }
        },
    }


class LocalSecondWallTraceTests(unittest.TestCase):
    def test_export_is_path_free_truth_free_and_selects_exact_basenames(self) -> None:
        output = build_trace_export(
            [payload("Pic_374.bmp"), payload("Pic_369.bmp"), payload("other.bmp")],
            ["Pic_374.bmp", "Pic_369.bmp"],
        )
        self.assertEqual(2, output["caseCount"])
        self.assertEqual(["Pic_374.bmp", "Pic_369.bmp"], [item["imageName"] for item in output["cases"]])
        serialized = json.dumps(output)
        self.assertNotIn("/private/source", serialized)
        self.assertNotIn("imageData", serialized)
        self.assertFalse(output["privacy"]["containsHumanTruth"])
        self.assertFalse(output["interpretation"]["thresholdTuningAllowed"])
        if jsonschema is not None:
            root = Path(__file__).resolve().parents[1]
            schema = json.loads(
                (root / "contracts/local-second-wall-trace-export.schema.json").read_text(encoding="utf-8")
            )
            jsonschema.Draft202012Validator.check_schema(schema)
            jsonschema.validate(output, schema)

    def test_missing_or_duplicate_basename_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "missing"):
            build_trace_export([payload("Pic_374.bmp")], ["Pic_369.bmp"])
        with self.assertRaisesRegex(ValueError, "duplicate"):
            build_trace_export([payload("Pic_374.bmp"), payload("Pic_374.bmp")], ["Pic_374.bmp"])

    def test_cli_refuses_git_internal_output(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            results = Path(temporary) / "results.jsonl"
            results.write_text(json.dumps(payload("Pic_374.bmp")) + "\n", encoding="utf-8")
            internal = Path(__file__).resolve().parents[1] / "forbidden-trace.json"
            import sys
            prior = sys.argv
            try:
                sys.argv = [
                    "extract_local_second_wall_trace.py", "--results", str(results),
                    "--image-name", "Pic_374.bmp", "--output", str(internal),
                ]
                self.assertEqual(2, main())
            finally:
                sys.argv = prior
            self.assertFalse(internal.exists())


if __name__ == "__main__":
    unittest.main()
