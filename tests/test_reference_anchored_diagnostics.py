from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from tools.dataset_common import inspect_image, sha256_file
from tools.export_reference_anchored_diagnostics import (
    PROJECT_ROOT,
    build_development_reference,
    export_diagnostics,
)

try:
    import jsonschema
except ImportError:
    jsonschema = None


def manual_review(image_hash: str, annotation_hash: str, fit_hash: str) -> dict:
    return {
        "schemaVersion": "manual-groove-pose-review/1",
        "source": {
            "imageSha256": image_hash, "annotationSha256": annotation_hash,
        },
        "algorithm": {"circleFitSourceSha256": fit_hash, "runtimeInputAllowed": False},
        "circle": {
            "status": "accepted", "pointCount": 134, "angularCoverageDeg": 236.0,
            "refinedRobustGeometricCircle": {"centerX": 50.0, "centerY": 40.0, "radiusPx": 30.0},
            "refinedResidualPx": {"median": 1.0, "p95": 2.0, "max": 3.0},
        },
        "measurement": {"openingCenterAzimuthImageDeg": 269.0, "quadrant": "upper_left"},
        "yDownTargetDiagnostic": {
            "datumMeasurement": {"measuredFromPositiveYClockwiseDeg": 179.0},
            "targetAssessment": {"targetContract": {"nominalDeg": 85.0, "toleranceDeg": 5.0}},
        },
    }


def comparison(image_hash: str, annotation_hash: str, fit_hash: str) -> dict:
    return {
        "schemaVersion": "slot-pose-reference-comparison/1", "status": "COMPARED",
        "referenceStatus": "DEVELOPMENT_REFERENCE",
        "source": {
            "imageSha256": image_hash, "annotationSha256": annotation_hash,
            "circleFitSourceSha256": fit_hash, "manualRecordSha256": "d" * 64,
            "runtimeRecordSha256": "e" * 64,
        },
        "circleDelta": {"centerDistancePx": 2.0, "radiusAbsolutePx": 1.0},
        "grooveOpeningDelta": {"automaticMinusManualCircularDeg": 0.01, "absoluteCircularDeg": 0.01},
        "productionAccuracyClaimed": False, "runtimeInputAllowed": False,
    }


def result(dataset: str, image_id: str, image_hash: str, *, geometry: bool = True) -> dict:
    diagnostics = {
        "physicalOuterCircle": {
            "status": "accepted",
            "physicalCircle": {"centerX": 50.0, "centerY": 40.0, "radiusPx": 30.0},
        },
        "grooveRefinement": {
            "status": "accepted" if geometry else "failed",
            "outerCircleIntersections": (
                [{"x": 20.0, "y": 40.0}, {"x": 22.0, "y": 50.0}] if geometry else None
            ),
            "startSide": ({"points": [[21.0, 41.0], [22.0, 42.0]], "rejectedPoints": [[23.0, 43.0]]} if geometry else None),
            "endSide": ({"points": [[24.0, 48.0], [23.0, 49.0]], "rejectedPoints": []} if geometry else None),
        },
        "singleGroovePose": {
            "geometryValid": geometry,
            "datumMeasurement": None if not geometry else {
                "measuredFromPositiveYClockwiseDeg": -179.0,
                "grooveOpeningPoint": {"x": 21.0, "y": 45.0},
                "center": {"x": 50.0, "y": 40.0},
                "position": {"horizontal": "left", "vertical": "lower"},
            },
            "targetAssessment": {
                "toleranceStatus": "PASS" if geometry else "NOT_EVALUATED",
                "positionGatePassed": True if geometry else None,
                "angleTolerancePassed": True if geometry else None,
            },
        },
    }
    return {
        "taskId": f"{dataset}:{image_id}", "image": {"sha256": image_hash},
        "result": {"valid": False, "signedRelativeRotationDeg": None},
        "error": {"code": "PLC_MAPPING_UNCONFIRMED" if geometry else "GROOVE_REFINEMENT_FAILED", "stage": "pose_mapping" if geometry else "groove_refinement"},
        "diagnostics": diagnostics,
    }


class ReferenceAnchoredDiagnosticsTests(unittest.TestCase):
    def test_runtime_does_not_import_reference_or_auto_annotation_exporter(self) -> None:
        runtime_sources = "\n".join(
            path.read_text(encoding="utf-8")
            for path in sorted((PROJECT_ROOT / "algorithms/slot_pose").glob("*.py"))
        )
        self.assertNotIn("export_reference_anchored_diagnostics", runtime_sources)
        self.assertNotIn("slot-pose-development-reference/1", runtime_sources)
        self.assertNotIn("observedCircularDeltaToReferenceDeg", runtime_sources)

    def test_reference_is_hash_locked_and_offline_only(self) -> None:
        reference = build_development_reference(
            manual_review("a" * 64, "b" * 64, "c" * 64),
            comparison("a" * 64, "b" * 64, "c" * 64),
        )
        self.assertEqual("DEVELOPMENT_REFERENCE_ONLY", reference["scope"])
        self.assertFalse(reference["runtimeInputAllowed"])
        self.assertFalse(reference["productionAccuracyClaimed"])
        self.assertEqual(179.0, reference["manualMeasurements"]["yDownSignedDeg"])
        bad = comparison("f" * 64, "b" * 64, "c" * 64)
        with self.assertRaisesRegex(ValueError, "image hash"):
            build_development_reference(manual_review("a" * 64, "b" * 64, "c" * 64), bad)

    def test_exports_one_auto_labelme_per_image_without_truth_leakage(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); data = root / "images"; data.mkdir()
            paths = []
            for name in ("a.png", "b.png"):
                path = data / name; Image.new("L", (100, 80), 100).save(path); paths.append(path)
            manifest = {
                "datasetId": "set-1", "datasetFingerprint": "1" * 64,
                "policy": {"groupingExplicit": False},
                "images": [
                    {"imageId": f"i{index}", "relativePath": path.name, **inspect_image(path)}
                    for index, path in enumerate(paths, start=1)
                ],
            }
            results = [
                result("set-1", "i1", sha256_file(paths[0]), geometry=True),
                result("set-1", "i2", sha256_file(paths[1]), geometry=False),
            ]
            results[0]["diagnostics"]["singleGroovePose"]["guidance"] = {
                "detectionStatus": "DETECTED",
                "guidanceStatus": "DETECTED_NEEDS_ADJUSTMENT",
                "currentAngleDeg": -179.0,
                "targetAngleDeg": 85.0,
                "toleranceDeg": 5.0,
                "correctionRawDeg": -96.0,
                "correctionDeg": -96.0,
                "imageFrameCorrectionDeg": -96.0,
                "rotationDirection": "COUNTERCLOCKWISE",
                "withinTolerance": False,
                "plcExecution": {
                    "status": "BLOCKED_MAPPING_UNCONFIRMED",
                    "mechanicalCorrectionDeg": None,
                    "plcCommand": None,
                },
            }
            reference = build_development_reference(
                manual_review("a" * 64, "b" * 64, "c" * 64),
                comparison("a" * 64, "b" * 64, "c" * 64),
            )
            output = root / "export"
            index = export_diagnostics(manifest, results, data, reference, output)
            self.assertEqual("reference-anchored-slot-pose-diagnostics/2", index["schemaVersion"])
            self.assertEqual(2, index["imageCount"])
            self.assertEqual("NOT_EVALUATED", index["evaluation"]["accuracyStatus"])
            self.assertEqual("NOT_EVALUATED", index["evaluation"]["staticRepeatabilityStatus"])
            self.assertAlmostEqual(2.0, index["records"][0]["observedCircularDeltaToReferenceDeg"])
            self.assertEqual("DETECTED_NEEDS_ADJUSTMENT", index["records"][0]["guidanceStatus"])
            self.assertEqual(-96.0, index["records"][0]["imageFrameCorrectionDeg"])
            self.assertEqual("COUNTERCLOCKWISE", index["records"][0]["rotationDirection"])
            self.assertIsNone(index["records"][0]["formalMechanicalAngleDeg"])
            self.assertIsNone(index["records"][1]["measuredYDownDeg"])
            self.assertIsNone(index["records"][1]["observedCircularDeltaToReferenceDeg"])
            diagnostics = sorted((output / "labelme-auto").glob("*.json"))
            self.assertEqual(2, len(diagnostics))
            success = json.loads(diagnostics[0].read_text())
            self.assertIsNone(success["imageData"])
            self.assertFalse(success["flags"]["formal_truth"])
            self.assertTrue(success["flags"]["algorithm_generated"])
            self.assertFalse(Path(success["imagePath"]).is_absolute())
            labels = [shape["label"] for shape in success["shapes"]]
            self.assertTrue(labels)
            self.assertTrue(all(label.startswith("AUTO_") for label in labels))
            self.assertNotIn("physical_outer_circle_truth", labels)
            self.assertNotIn("target_groove_open_boundary_manual", labels)
            shapes_by_label = {shape["label"]: shape for shape in success["shapes"]}
            self.assertEqual(
                [[50.0, 40.0], [80.0, 40.0]],
                shapes_by_label["AUTO_detected_physical_outer_circle"]["points"],
            )
            self.assertEqual(
                [[20.0, 40.0], [22.0, 50.0]],
                shapes_by_label["AUTO_detected_groove_opening"]["points"],
            )
            self.assertEqual(
                [[50.0, 40.0], [21.0, 45.0]],
                shapes_by_label["AUTO_detected_groove_radial_axis"]["points"],
            )
            self.assertEqual(
                [[21.0, 41.0], [22.0, 42.0]],
                shapes_by_label["AUTO_startSide_inliers"]["points"],
            )
            failure = json.loads(diagnostics[1].read_text())
            self.assertTrue(any(shape["label"] == "AUTO_detected_physical_outer_circle" for shape in failure["shapes"]))
            self.assertFalse(any("groove_opening" in shape["label"] for shape in failure["shapes"]))
            self.assertTrue((output / "diagnostics.csv").is_file())
            if jsonschema is not None:
                schema = json.loads(
                    (PROJECT_ROOT / "contracts/reference-anchored-diagnostics.schema.json").read_text()
                )
                for payload in (reference, index, success, failure):
                    jsonschema.validate(payload, schema)

    def test_missing_duplicate_hash_and_unsafe_output_fail_before_export(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); data = root / "images"; data.mkdir()
            image = data / "a.png"; Image.new("L", (20, 20), 1).save(image)
            info = inspect_image(image)
            manifest = {"datasetId": "d", "images": [{"imageId": "i", "relativePath": "a.png", **info}]}
            reference = build_development_reference(
                manual_review("a" * 64, "b" * 64, "c" * 64),
                comparison("a" * 64, "b" * 64, "c" * 64),
            )
            good = result("d", "i", info["sha256"])
            with self.assertRaisesRegex(ValueError, "missing result"):
                export_diagnostics(manifest, [], data, reference, root / "missing")
            with self.assertRaisesRegex(ValueError, "duplicate taskId"):
                export_diagnostics(manifest, [good, good], data, reference, root / "duplicate")
            bad = json.loads(json.dumps(good)); bad["image"]["sha256"] = "f" * 64
            with self.assertRaisesRegex(ValueError, "result image hash"):
                export_diagnostics(manifest, [bad], data, reference, root / "bad-hash")
            with self.assertRaisesRegex(ValueError, "outside the Git worktree"):
                export_diagnostics(manifest, [good], data, reference, PROJECT_ROOT / "forbidden-output")
            traversed = json.loads(json.dumps(manifest)); traversed["images"][0]["relativePath"] = "../a.png"
            with self.assertRaisesRegex(ValueError, "relative path"):
                export_diagnostics(traversed, [good], data, reference, root / "traversed")

    @unittest.skipIf(jsonschema is None, "jsonschema is installed by the explicit Schema gate")
    def test_reference_index_and_auto_labelme_match_schema(self) -> None:
        schema = json.loads((PROJECT_ROOT / "contracts/reference-anchored-diagnostics.schema.json").read_text())
        jsonschema.Draft202012Validator.check_schema(schema)


if __name__ == "__main__":
    unittest.main()
