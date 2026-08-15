from __future__ import annotations

import copy
import json
import math
import unittest
from pathlib import Path

from tools.compare_pose_reference import compare_pose_reference


def manual_record() -> dict:
    return {
        "algorithm": {
            "circleFitSourceSha256": "a" * 64,
            "delegatedCircleFitFunctions": ["fit_circle", "robust_fit_circle", "geometric_circle_fit"],
            "runtimeInputAllowed": False,
        },
        "source": {"imageSha256": "b" * 64, "annotationSha256": "c" * 64},
        "circle": {
            "status": "accepted", "pointCount": 134, "angularCoverageDeg": 236.4,
            "refinedRobustGeometricCircle": {"centerX": 100.0, "centerY": 200.0, "radiusPx": 1000.0},
            "refinedResidualPx": {"median": 1.0, "p95": 2.0, "max": 3.0},
        },
        "grooveRecognition": {"status": "accepted"},
        "measurement": {"openingCenterAzimuthImageDeg": 25.0},
    }


def runtime_record() -> dict:
    return {
        "image": {"sha256": "b" * 64},
        "algorithm": {"assets": {"sourceSha256": "a" * 64}},
        "diagnostics": {
            "physicalOuterCircle": {
                "status": "accepted",
                "physicalCircle": {"centerX": 103.0, "centerY": 204.0, "radiusPx": 998.0},
            },
            "grooveRecognition": {"acceptedCount": 1},
            "grooveRefinement": {
                "status": "accepted", "openingMidpointProfileDeg": 294.5,
                "openingEndpointProfileDeg": [285.0, 304.0],
            },
            "singleGroovePose": {
                "schemaVersion": "slot-single-real-groove-pose/2", "status": "accepted",
                "imageMeasurement": {"azimuthDeg": 24.5},
            },
        },
    }


class PoseReferenceComparisonTests(unittest.TestCase):
    def test_same_image_decomposes_circle_and_boundary_midpoint_error(self) -> None:
        result = compare_pose_reference(manual_record(), runtime_record())
        self.assertEqual("slot-pose-reference-comparison/1", result["schemaVersion"])
        self.assertEqual("COMPARED", result["status"])
        self.assertEqual("DEVELOPMENT_REFERENCE", result["referenceStatus"])
        self.assertAlmostEqual(3.0, result["circleDelta"]["centerDxPx"])
        self.assertAlmostEqual(4.0, result["circleDelta"]["centerDyPx"])
        self.assertAlmostEqual(5.0, result["circleDelta"]["centerDistancePx"])
        self.assertAlmostEqual(-2.0, result["circleDelta"]["radiusSignedPx"])
        self.assertAlmostEqual(2.0, result["circleDelta"]["radiusAbsolutePx"])
        self.assertAlmostEqual(math.degrees(math.asin(0.005)), result["circleDelta"]["centerErrorAngularUpperBoundDeg"])
        self.assertAlmostEqual(-0.5, result["grooveOpeningDelta"]["automaticMinusManualCircularDeg"])
        self.assertFalse(result["productionAccuracyClaimed"])

    def test_mismatched_image_or_algorithm_source_is_rejected(self) -> None:
        for field in ("image", "source"):
            runtime = runtime_record()
            if field == "image":
                runtime["image"]["sha256"] = "d" * 64
            else:
                runtime["algorithm"]["assets"]["sourceSha256"] = "d" * 64
            with self.subTest(field=field), self.assertRaises(ValueError):
                compare_pose_reference(manual_record(), runtime)

    def test_missing_circle_nonunique_groove_or_failed_refinement_is_rejected(self) -> None:
        mutations = (
            lambda item: item["diagnostics"]["physicalOuterCircle"].__setitem__("status", "failed"),
            lambda item: item["diagnostics"]["grooveRecognition"].__setitem__("acceptedCount", 2),
            lambda item: item["diagnostics"]["grooveRefinement"].__setitem__("status", "failed"),
            lambda item: item["diagnostics"]["singleGroovePose"].__setitem__("status", "failed"),
        )
        for mutate in mutations:
            runtime = runtime_record()
            mutate(runtime)
            with self.subTest(runtime=runtime), self.assertRaises(ValueError):
                compare_pose_reference(manual_record(), runtime)

    def test_nonfinite_values_and_runtime_truth_import_are_rejected(self) -> None:
        runtime = runtime_record()
        runtime["diagnostics"]["physicalOuterCircle"]["physicalCircle"]["centerX"] = math.nan
        with self.assertRaises(ValueError):
            compare_pose_reference(manual_record(), runtime)
        root = Path(__file__).resolve().parents[1]
        for relative in ("algorithms/slot_pose/legacy_adapter.py", "algorithms/slot_pose/single_groove_pose.py"):
            self.assertNotIn("compare_pose_reference", (root / relative).read_text(encoding="utf-8"))

    def test_comparison_schema_is_valid_json_and_matches_when_jsonschema_available(self) -> None:
        root = Path(__file__).resolve().parents[1]
        schema = json.loads((root / "contracts/pose-reference-comparison.schema.json").read_text(encoding="utf-8"))
        self.assertEqual("slot-pose-reference-comparison/1", schema["$id"])
        try:
            import jsonschema
        except ImportError:
            return
        jsonschema.Draft202012Validator.check_schema(schema)
        jsonschema.validate(compare_pose_reference(manual_record(), runtime_record()), schema)


if __name__ == "__main__":
    unittest.main()
