from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from algorithms.slot_pose.contract import load_config
from algorithms.slot_pose.main import run
from algorithms.slot_pose.single_groove_pose import (
    DEFAULT_SINGLE_GROOVE_POSE_CONFIG,
    build_single_groove_pose,
)
from tools.dataset_common import sha256_file, write_json
from tools.generate_synthetic_multi_notches import build_dataset
from tools.generate_synthetic_paired_notches import make_paired_face

try:
    import jsonschema
except ImportError:
    jsonschema = None


def accepted_candidate(candidate_id: str, center_deg: float, score: float = 0.9) -> dict:
    return {
        "candidateId": candidate_id,
        "centerDeg": center_deg % 360.0,
        "halfWidthDeg": 5.0,
        "startDeg": (center_deg - 5.0) % 360.0,
        "endDeg": (center_deg + 5.0) % 360.0,
        "wrapsBoundary": (center_deg - 5.0) % 360.0 > (center_deg + 5.0) % 360.0,
        "prominence": 80.0,
        "deficitArea": 500.0,
        "rank": 1,
        "grooveScore": score,
        "accepted": True,
        "rejectionReasons": [],
        "thresholdVersion": "groove-geometry-v1",
    }


class SingleGroovePoseGeometryTests(unittest.TestCase):
    def test_exactly_one_groove_outputs_versioned_image_pose_but_no_target_deviation(self) -> None:
        result = build_single_groove_pose(
            [accepted_candidate("candidate-002", 300.0)],
            (100.0, 100.0),
            50.0,
            DEFAULT_SINGLE_GROOVE_POSE_CONFIG,
            recognition_status="accepted",
        )
        self.assertEqual("slot-single-real-groove-pose/1", result["schemaVersion"])
        self.assertEqual("accepted", result["status"])
        self.assertTrue(result["geometryValid"])
        self.assertEqual("candidate-002", result["role"]["candidateId"])
        measurement = result["imageMeasurement"]
        self.assertEqual("slot-groove-image-angle/1", measurement["schemaVersion"])
        self.assertAlmostEqual(30.0, measurement["azimuthDeg"])
        self.assertEqual("upper_right", measurement["quadrant"])
        self.assertEqual("NOT_EVALUATED", result["targetAssessment"]["status"])
        self.assertIsNone(result["targetAssessment"]["quadrantMatches"])
        self.assertIsNone(result["targetAssessment"]["signedMeasurementMinusTargetDeg"])
        self.assertIsNone(result["targetAssessment"]["mechanicalCorrectionDeg"])

    def test_image_up_zero_wrap_and_exact_cardinality_fail_closed(self) -> None:
        wrapped = build_single_groove_pose(
            [accepted_candidate("candidate-001", 270.0)],
            (50.0, 50.0),
            40.0,
            DEFAULT_SINGLE_GROOVE_POSE_CONFIG,
            recognition_status="accepted",
        )
        self.assertAlmostEqual(0.0, wrapped["imageMeasurement"]["azimuthDeg"])
        self.assertEqual("upper_axis", wrapped["imageMeasurement"]["quadrant"])

        missing = build_single_groove_pose(
            [], (50.0, 50.0), 40.0, DEFAULT_SINGLE_GROOVE_POSE_CONFIG,
            recognition_status="failed",
        )
        self.assertEqual("failed", missing["status"])
        self.assertFalse(missing["geometryValid"])
        self.assertIsNone(missing["imageMeasurement"])

        multiple = build_single_groove_pose(
            [accepted_candidate("candidate-001", 270.0), accepted_candidate("candidate-002", 30.0)],
            (50.0, 50.0), 40.0, DEFAULT_SINGLE_GROOVE_POSE_CONFIG,
            recognition_status="accepted",
        )
        self.assertEqual("ambiguous", multiple["status"])
        self.assertFalse(multiple["geometryValid"])
        self.assertIsNone(multiple["imageMeasurement"])

    def test_runtime_module_has_no_manual_truth_dependency(self) -> None:
        root = Path(__file__).resolve().parents[1]
        for relative in (
            "algorithms/slot_pose/single_groove_pose.py",
            "algorithms/slot_pose/legacy_adapter.py",
            "algorithms/slot_pose/main.py",
        ):
            source = (root / relative).read_text(encoding="utf-8")
            self.assertNotIn("review_labelme_groove_pose", source)
            self.assertNotIn("manual-half-circle-with-groove", source)
            self.assertNotIn("label1", source)
            self.assertNotIn("label2", source)

    @unittest.skipIf(jsonschema is None, "jsonschema is installed by the explicit Schema gate")
    def test_versioned_diagnostic_matches_schema(self) -> None:
        root = Path(__file__).resolve().parents[1]
        result = build_single_groove_pose(
            [accepted_candidate("candidate-001", 300.0)],
            (100.0, 100.0), 50.0, DEFAULT_SINGLE_GROOVE_POSE_CONFIG,
            recognition_status="accepted",
        )
        schema = json.loads((root / "contracts/single-real-groove-pose.schema.json").read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator.check_schema(schema)
        jsonschema.validate(result, schema)


class SingleGrooveRuntimeIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temporary.name)
        try:
            built = build_dataset(cls.root, 137)
        except FileNotFoundError as exc:
            cls.temporary.cleanup()
            raise unittest.SkipTest(f"historical source unavailable: {exc}") from exc
        config_path = Path(built["config"])
        config = json.loads(config_path.read_text(encoding="utf-8"))
        reference = cls.root / "reference.png"
        make_paired_face(
            0.0, 901, notch_centers=[300.0], shadow_centers=[80.0, 170.0], noise=0.0,
        ).save(reference)
        config["legacy_asset"]["reference_sha256"] = sha256_file(reference)
        config["detector"]["diagnostic_mode"] = "single_real_groove"
        config["detector"]["single_groove_pose"] = DEFAULT_SINGLE_GROOVE_POSE_CONFIG
        config["pose"].update({
            "drawing_datum_definition_confirmed": False,
            "a2_drawing_feature_mapping_confirmed": True,
            "output_purpose": None,
            "target_semantics_confirmed": True,
            "conventions_confirmed": False,
            "mechanical_zero_image_deg": None,
            "positive_direction": None,
        })
        write_json(config_path, config)
        cls.config = config_path
        cls.images = cls.root / "single-images"
        cls.images.mkdir()
        make_paired_face(
            0.0, 902, notch_centers=[300.0], shadow_centers=[80.0, 170.0], noise=0.8,
        ).save(cls.images / "one-real-two-shadows.png")
        make_paired_face(
            0.0, 903, notch_centers=[], shadow_centers=[80.0, 170.0], noise=0.8,
        ).save(cls.images / "zero-real-two-shadows.png")
        make_paired_face(
            0.0, 904, notch_centers=[300.0, 30.0], shadow_centers=[170.0], noise=0.8,
        ).save(cls.images / "two-real-one-shadow.png")

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temporary.cleanup()

    def test_one_real_groove_plus_two_shadows_is_image_pose_success_and_mechanical_block(self) -> None:
        payload = run(self.images / "one-real-two-shadows.png", self.config, "single:normal")
        self.assertFalse(payload["result"]["valid"])
        self.assertIsNone(payload["result"]["signedRelativeRotationDeg"])
        self.assertEqual("DATUM_DEFINITION_UNCONFIRMED", payload["error"]["code"])
        diagnostics = payload["diagnostics"]
        self.assertEqual("single_real_groove", diagnostics["diagnosticMode"])
        self.assertEqual(3, diagnostics["grooveRecognition"]["rawCandidateCount"])
        self.assertEqual(1, diagnostics["grooveRecognition"]["acceptedCount"])
        self.assertEqual(2, sum(
            not item["accepted"] for item in diagnostics["grooveRecognition"]["assessments"]
        ))
        self.assertEqual("accepted", diagnostics["singleGroovePose"]["status"])
        self.assertTrue(diagnostics["singleGroovePose"]["geometryValid"])
        self.assertIsNotNone(diagnostics["singleGroovePose"]["imageMeasurement"]["azimuthDeg"])
        self.assertNotIn("roleAssignment", diagnostics)

    def test_zero_and_multiple_real_grooves_fail_before_mechanical_mapping(self) -> None:
        cases = {
            "zero-real-two-shadows.png": "GROOVE_RECOGNITION_FAILED",
            "two-real-one-shadow.png": "GROOVE_RECOGNITION_AMBIGUOUS",
        }
        for name, expected in cases.items():
            with self.subTest(name=name):
                payload = run(self.images / name, self.config, f"single:{name}")
                self.assertFalse(payload["result"]["valid"])
                self.assertEqual(expected, payload["error"]["code"], payload)
                self.assertIsNone(payload["result"]["signedRelativeRotationDeg"])
                self.assertFalse(payload["diagnostics"]["singleGroovePose"]["geometryValid"])

    def test_config_contract_requires_versioned_exactly_one_policy(self) -> None:
        loaded = load_config(self.config)
        self.assertEqual("single_real_groove", loaded["detector"]["diagnostic_mode"])
        self.assertEqual(1, loaded["detector"]["single_groove_pose"]["expected_accepted_groove_count"])
        for key, value in (
            ("expected_accepted_groove_count", 2),
            ("schema_version", "unversioned"),
            ("unexpected_typo", True),
        ):
            config = json.loads(self.config.read_text(encoding="utf-8"))
            config["detector"]["single_groove_pose"][key] = value
            path = self.root / f"invalid-{key}.json"
            path.write_text(json.dumps(config), encoding="utf-8")
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "single_groove_pose"):
                load_config(path)


if __name__ == "__main__":
    unittest.main()
