import math
import json
from pathlib import Path
import unittest

import jsonschema
from tools.compare_groove_candidate_structure import summarize_candidate_structure


def _side(a, b, residual=0.5, coverage=0.9):
    return {
        "line": {"a": a, "b": b, "c": 1.0},
        "lineResidualPx": {"p95": residual},
        "lineInlierRatio": 0.9,
        "lineLongitudinalCoverage": coverage,
        "intersection": {"x": 10.0, "y": 20.0},
        "profileEvidence": {
            "radialCoverage": coverage,
            "edgeContrastProfile": [80.0, 82.0, 81.0],
            "edgeGradientProfile": [20.0, 21.0, 20.5],
        },
    }


class GrooveCandidateStructureTests(unittest.TestCase):
    def test_complete_square_opening_reports_two_straight_parallel_walls(self):
        refinement = {
            "status": "accepted",
            "startSide": _side(1.0, 0.0),
            "endSide": _side(-1.0, 0.0),
            "outerCircleIntersections": [[1.0, 2.0], [3.0, 4.0]],
            "openingWidthDeg": 12.0,
        }
        result = summarize_candidate_structure("c", {}, refinement)
        self.assertEqual(result["status"], "COMPLETE_TWO_WALL_GEOMETRY")
        self.assertAlmostEqual(result["parallelDifferenceDeg"], 0.0)
        self.assertTrue(result["endpointStructurePresent"])

    def test_curved_or_unstable_boundary_remains_diagnostic_failure(self):
        refinement = {
            "status": "failed",
            "startSide": _side(1.0, 0.0, residual=8.0),
            "endSide": None,
            "failedChecks": ["endSide_line_residual"],
        }
        result = summarize_candidate_structure("c", {}, refinement)
        self.assertEqual(result["status"], "PIXEL_STRUCTURE_INCOMPLETE")
        self.assertIn("endSide_line_residual", result["failedChecks"])
        self.assertFalse(result["endpointStructurePresent"])

    def test_nonparallel_lines_are_measured_without_becoming_truth(self):
        refinement = {
            "status": "accepted",
            "startSide": _side(1.0, 0.0),
            "endSide": _side(math.sqrt(0.5), math.sqrt(0.5)),
            "outerCircleIntersections": [[1.0, 2.0], [3.0, 4.0]],
        }
        result = summarize_candidate_structure("c", {}, refinement)
        self.assertAlmostEqual(result["parallelDifferenceDeg"], 45.0)
        self.assertFalse(result["humanTruthAppliedAtRuntime"])
        self.assertFalse(result["authoritative"])

    def test_missing_refinement_is_explicit(self):
        result = summarize_candidate_structure("c", {"radialDepthPx": 20.0}, None)
        self.assertEqual(result["status"], "PIXEL_STRUCTURE_NOT_EVALUATED")
        self.assertIn("refinement_not_available", result["failedChecks"])

    def test_comparison_contract_rejects_private_path_fields(self):
        report = {
            "schemaVersion": "groove-candidate-structure-comparison/1",
            "developmentOnly": True, "authoritative": False, "detectorModified": False,
            "humanTruthAppliedAtRuntime": False, "images": [],
        }
        schema = json.loads((Path(__file__).resolve().parents[1] / "contracts/groove-candidate-structure-comparison.schema.json").read_text())
        jsonschema.validate(report, schema)
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate({**report, "sourcePath": "forbidden-input-field"}, schema)


if __name__ == "__main__":
    unittest.main()
