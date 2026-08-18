from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from algorithms.slot_pose.contract import load_config
from algorithms.slot_pose.legacy_adapter import LegacyAdapterError
from algorithms.slot_pose.main import run
from algorithms.slot_pose.groove_refinement import DEFAULT_GROOVE_REFINEMENT_CONFIG
from algorithms.slot_pose.single_groove_pose import (
    DEFAULT_SINGLE_GROOVE_POSE_CONFIG,
    DEFAULT_SINGLE_GROOVE_POSE_CONFIG_V2,
    DEFAULT_SINGLE_GROOVE_POSE_CONFIG_V3,
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


def rejected_source_consistency(
    endpoint_structure_difference: float,
    *,
    failed_checks: list[str] | None = None,
) -> dict:
    failed_checks = ["edge_contrast_asymmetry"] if failed_checks is None else failed_checks
    definitions = [
        ("edge_contrast_asymmetry", "contrastNormalizedDifference", 0.18, 0.12, "max"),
        ("edge_gradient_asymmetry", "gradientNormalizedDifference", 0.30, 0.35, "max"),
        ("normalized_profile_dissimilar", "normalizedProfileMae", 0.03, 0.22, "max"),
        ("normalized_profile_uncorrelated", "normalizedProfileCorrelation", 0.99, 0.75, "min"),
        ("radial_coverage_inconsistent", "radialCoverageDifference", 0.03, 0.20, "max"),
        (
            "endpoint_structure_inconsistent", "endpointStructureDifference",
            endpoint_structure_difference, 0.15, "max",
        ),
    ]
    return {
        "schemaVersion": "groove-sidewall-source-consistency/1",
        "thresholdVersion": "sidewall-source-consistency-v1",
        "enabled": True,
        "status": "rejected",
        "metrics": {metric: value for _, metric, value, _, _ in definitions},
        "checks": [
            {
                "checkId": check_id,
                "metric": metric,
                "value": value,
                "threshold": threshold,
                "thresholdKind": kind,
                "margin": threshold - value if kind == "max" else value - threshold,
                "passed": check_id not in failed_checks,
            }
            for check_id, metric, value, threshold, kind in definitions
        ],
        "failedChecks": list(failed_checks),
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
            "algorithms/slot_pose/groove_shadow_discrimination.py",
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


class SingleGrooveYDownV2Tests(unittest.TestCase):
    def _pose(self, measured_deg: float, *, center_override: float | None = None) -> dict:
        midpoint_profile = (measured_deg + 90.0) % 360.0
        candidate = accepted_candidate(
            "candidate-001", midpoint_profile if center_override is None else center_override,
        )
        candidate.update({
            "refinedStartDeg": (midpoint_profile - 5.0) % 360.0,
            "refinedEndDeg": (midpoint_profile + 5.0) % 360.0,
            "grooveRefinement": {"schemaVersion": "slot-groove-subpixel-opening/1", "status": "accepted"},
        })
        return build_single_groove_pose(
            [candidate], (100.0, 100.0), 50.0,
            DEFAULT_SINGLE_GROOVE_POSE_CONFIG_V2,
            recognition_status="accepted", plc_mapping_confirmed=False,
        )

    def test_boundary_midpoint_not_weighted_dark_center_defines_measurement(self) -> None:
        result = self._pose(85.0, center_override=120.0)
        self.assertEqual("slot-single-real-groove-pose/2", result["schemaVersion"])
        measurement = result["datumMeasurement"]
        self.assertAlmostEqual(175.0, measurement["grooveOpening"]["midpointProfileDeg"])
        self.assertAlmostEqual(85.0, measurement["measuredFromPositiveYClockwiseDeg"])
        self.assertAlmostEqual(-50.0 * __import__("math").sin(__import__("math").radians(85.0)), measurement["offset"]["dx"], places=9)
        self.assertEqual("left", measurement["position"]["horizontal"])
        self.assertEqual("lower", measurement["position"]["vertical"])
        self.assertTrue(measurement["position"]["requiredRegionPassed"])

    def test_closed_tolerance_and_position_gate(self) -> None:
        expected = {
            80.0: "PASS", 85.0: "PASS", 90.0: "PASS",
            79.9: "FAIL", 90.1: "FAIL", -85.0: "FAIL", 100.0: "FAIL",
        }
        for measured, status in expected.items():
            with self.subTest(measured=measured):
                result = self._pose(measured)
                assessment = result["targetAssessment"]
                self.assertEqual("EVALUATED", assessment["status"])
                self.assertEqual(status, assessment["toleranceStatus"])
                self.assertIsNone(assessment["mechanicalCorrectionDeg"])
                self.assertIn("PLC_MAPPING_UNCONFIRMED", assessment["blockers"])
        right_lower = self._pose(-85.0)["datumMeasurement"]
        self.assertEqual("right", right_lower["position"]["horizontal"])
        self.assertEqual("lower", right_lower["position"]["vertical"])
        self.assertFalse(right_lower["position"]["requiredRegionPassed"])

    def test_axes_wrap_deviation_and_correction_signs(self) -> None:
        cases = {
            0.0: (0.0, "axis", "lower"),
            90.0: (90.0, "left", "axis"),
            -90.0: (-90.0, "right", "axis"),
            -180.0: (-180.0, "axis", "upper"),
        }
        for source, (expected, horizontal, vertical) in cases.items():
            with self.subTest(source=source):
                result = self._pose(source)
                measurement = result["datumMeasurement"]
                self.assertAlmostEqual(expected, measurement["measuredFromPositiveYClockwiseDeg"])
                self.assertEqual(horizontal, measurement["position"]["horizontal"])
                self.assertEqual(vertical, measurement["position"]["vertical"])
        slow = self._pose(82.0)["targetAssessment"]
        fast = self._pose(88.0)["targetAssessment"]
        self.assertAlmostEqual(-3.0, slow["signedMeasurementMinusTargetDeg"])
        self.assertAlmostEqual(3.0, slow["imageFrameCorrectionDeg"])
        self.assertEqual("clockwise", slow["imageFrameCorrectionDirection"])
        self.assertAlmostEqual(3.0, fast["signedMeasurementMinusTargetDeg"])
        self.assertAlmostEqual(-3.0, fast["imageFrameCorrectionDeg"])
        self.assertEqual("counter_clockwise", fast["imageFrameCorrectionDirection"])

    @unittest.skipIf(jsonschema is None, "jsonschema is installed by the explicit Schema gate")
    def test_v2_diagnostic_matches_its_own_schema(self) -> None:
        root = Path(__file__).resolve().parents[1]
        result = self._pose(85.0)
        schema = json.loads((root / "contracts/single-real-groove-pose-v2.schema.json").read_text(encoding="utf-8"))
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
            0.0, 905, notch_centers=[175.0], shadow_centers=[40.0, 300.0], noise=0.4,
        ).save(cls.images / "one-real-left-lower.png")
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

    def test_multi_threshold_mode_does_not_turn_zero_or_multiple_grooves_into_guidance(self) -> None:
        config = json.loads(self.config.read_text(encoding="utf-8"))
        config["config_id"] = "synthetic-multi-threshold-fail-closed"
        config["detector"]["dark_candidate_robustness"] = {"enabled": True}
        path = self.root / "multi-threshold-fail-closed.json"
        write_json(path, config)
        for name in ("zero-real-two-shadows.png", "two-real-one-shadow.png"):
            with self.subTest(name=name):
                payload = run(self.images / name, path, f"single:robust:{name}")
                self.assertFalse(payload["result"]["valid"])
                self.assertIn(payload["error"]["code"], {
                    "GROOVE_RECOGNITION_FAILED", "GROOVE_RECOGNITION_AMBIGUOUS",
                })
                self.assertIsNone(payload["result"]["signedRelativeRotationDeg"])

    def test_full_frame_locator_failure_stops_all_groove_and_angle_stages(self) -> None:
        config = json.loads(self.config.read_text(encoding="utf-8"))
        config["config_id"] = "synthetic-full-frame-locator-not-found"
        config["detector"].pop("face_search_roi_normalized", None)
        config["detector"]["full_frame_circle_locator"] = {
            "schema_version": "full-frame-circle-locator/1",
            "enabled": True,
            "allowed_center_normalized": [0.0, 0.0, 0.1, 0.1],
            "min_radius_to_min_image_dim": 0.1,
            "max_radius_to_min_image_dim": 0.49,
        }
        path = self.root / "full-frame-not-found.json"
        write_json(path, config)
        payload = run(self.images / "one-real-two-shadows.png", path, "single:locator-not-found")
        self.assertFalse(payload["result"]["valid"])
        self.assertIsNone(payload["result"]["signedRelativeRotationDeg"])
        self.assertEqual("HOUSING_CIRCLE_NOT_FOUND", payload["error"]["code"])
        self.assertEqual("not_found", payload["diagnostics"]["circleLocalization"]["status"])
        self.assertNotIn("angularProfile", payload["diagnostics"])
        self.assertNotIn("grooveRecognition", payload["diagnostics"])
        self.assertNotIn("singleGroovePose", payload["diagnostics"])

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

    def test_v2_runtime_refines_sidewalls_evaluates_target_and_blocks_plc(self) -> None:
        config = json.loads(self.config.read_text(encoding="utf-8"))
        config["config_id"] = "synthetic-single-real-groove-y-down-v2"
        config["detector"]["single_groove_pose"] = DEFAULT_SINGLE_GROOVE_POSE_CONFIG_V2
        config["detector"]["groove_refinement"] = {
            **DEFAULT_GROOVE_REFINEMENT_CONFIG,
            "threshold_version": "groove-sidewall-subpixel-v2",
        }
        config["pose"].update({
            "drawing_datum_definition_confirmed": True,
            "a2_drawing_feature_mapping_confirmed": True,
            "output_purpose": "mechanical_correction",
            "target_semantics_confirmed": True,
            "conventions_confirmed": True,
            "mechanical_zero_image_deg": 0.0,
            "positive_direction": "cw",
            "valid_range_deg": [-180.0, 179.999],
            "production_plc_mapping_confirmed": False,
        })
        path = self.root / "single-v2.json"
        write_json(path, config)
        payload = run(self.images / "one-real-left-lower.png", path, "single:v2")
        self.assertFalse(payload["result"]["valid"], payload)
        self.assertIsNone(payload["result"]["signedRelativeRotationDeg"])
        self.assertEqual("PLC_MAPPING_UNCONFIRMED", payload["error"]["code"], payload)
        diagnostics = payload["diagnostics"]
        self.assertEqual("accepted", diagnostics["grooveRefinement"]["status"])
        self.assertEqual("slot-groove-subpixel-opening/2", diagnostics["grooveRefinement"]["schemaVersion"])
        self.assertEqual(
            "deterministic-consensus-tls-v2",
            diagnostics["grooveRefinement"]["startSide"]["lineFitStrategy"],
        )
        pose = diagnostics["singleGroovePose"]
        self.assertEqual("slot-single-real-groove-pose/2", pose["schemaVersion"])
        self.assertEqual("EVALUATED", pose["targetAssessment"]["status"])
        self.assertEqual("PASS", pose["targetAssessment"]["toleranceStatus"])
        self.assertIsNotNone(pose["datumMeasurement"]["measuredFromPositiveYClockwiseDeg"])
        self.assertIsNone(pose["targetAssessment"]["mechanicalCorrectionDeg"])

    def test_v3_runtime_keeps_reliable_adjustment_valid_while_plc_is_blocked(self) -> None:
        config = json.loads(self.config.read_text(encoding="utf-8"))
        config["config_id"] = "synthetic-single-real-groove-closed-loop-v3"
        config["detector"]["single_groove_pose"] = DEFAULT_SINGLE_GROOVE_POSE_CONFIG_V3
        config["detector"]["groove_refinement"] = {
            **DEFAULT_GROOVE_REFINEMENT_CONFIG,
            "threshold_version": "groove-sidewall-subpixel-v2",
        }
        config["pose"].update({
            "target_semantics_confirmed": True,
            "conventions_confirmed": False,
            "mechanical_zero_image_deg": None,
            "positive_direction": None,
            "production_plc_mapping_confirmed": False,
        })
        path = self.root / "single-v3.json"
        write_json(path, config)
        payload = run(self.images / "one-real-two-shadows.png", path, "single:v3")
        self.assertEqual("slot-pose-result/3", payload["schemaVersion"])
        self.assertTrue(payload["result"]["valid"], payload)
        self.assertEqual("DETECTED", payload["result"]["detectionStatus"])
        self.assertIn(payload["result"]["guidanceStatus"], {
            "DETECTED_NEEDS_ADJUSTMENT", "DETECTED_IN_POSITION",
        })
        self.assertIsNotNone(payload["result"]["imageFrameCorrectionDeg"])
        self.assertEqual(
            payload["result"]["imageFrameCorrectionDeg"],
            payload["result"]["signedRelativeRotationDeg"],
        )
        self.assertEqual("BLOCKED_MAPPING_UNCONFIRMED", payload["result"]["plcExecutionStatus"])
        self.assertIsNone(payload["result"]["mechanicalCorrectionDeg"])
        self.assertIsNone(payload["result"]["plcCommand"])
        self.assertIsNone(payload["error"])
        diagnostics = payload["diagnostics"]
        self.assertEqual(1, diagnostics["grooveRecognition"]["acceptedCount"])
        self.assertEqual(2, sum(
            not item["accepted"] for item in diagnostics["grooveRecognition"]["assessments"]
        ))
        self.assertEqual("accepted", diagnostics["grooveRefinement"]["status"])
        self.assertEqual("slot-single-real-groove-pose/3", diagnostics["singleGroovePose"]["schemaVersion"])

    def test_v3_source_inconsistency_is_explicit_and_clears_guidance(self) -> None:
        config = json.loads(self.config.read_text(encoding="utf-8"))
        config["detector"]["single_groove_pose"] = DEFAULT_SINGLE_GROOVE_POSE_CONFIG_V3
        config["detector"]["groove_refinement"] = {
            **DEFAULT_GROOVE_REFINEMENT_CONFIG,
            "threshold_version": "groove-sidewall-subpixel-v2",
        }
        config["detector"]["sidewall_source_consistency"] = {"enabled": True}
        path = self.root / "single-v3-source-inconsistent.json"
        write_json(path, config)
        rejected = {
            "schemaVersion": "groove-sidewall-source-consistency/1",
            "thresholdVersion": "sidewall-source-consistency-v1",
            "enabled": True,
            "status": "rejected",
            "metrics": {"contrastNormalizedDifference": 0.18},
            "checks": [],
            "failedChecks": ["edge_contrast_asymmetry"],
        }
        with patch(
            "algorithms.slot_pose.legacy_adapter.assess_sidewall_source_consistency",
            return_value=rejected,
        ):
            payload = run(self.images / "one-real-two-shadows.png", path, "single:v3:source")
        self.assertFalse(payload["result"]["valid"])
        self.assertEqual("GROOVE_SOURCE_INCONSISTENT", payload["error"]["code"])
        self.assertEqual("groove_source_consistency", payload["error"]["stage"])
        self.assertIsNone(payload["result"]["imageFrameCorrectionDeg"])
        self.assertEqual("rejected", payload["diagnostics"]["grooveSourceConsistency"]["status"])
        self.assertNotIn("sidewallSourceConsistencyCandidate", payload["diagnostics"])

    def test_default_off_source_candidate_never_promotes_failed_pose(self) -> None:
        config = json.loads(self.config.read_text(encoding="utf-8"))
        config["detector"]["single_groove_pose"] = DEFAULT_SINGLE_GROOVE_POSE_CONFIG_V3
        config["detector"]["groove_refinement"] = {
            **DEFAULT_GROOVE_REFINEMENT_CONFIG,
            "threshold_version": "groove-sidewall-subpixel-v2",
        }
        config["detector"]["sidewall_source_consistency"] = {"enabled": True}
        config["detector"]["sidewall_source_consistency_candidate"] = {"enabled": True}
        path = self.root / "single-v3-source-candidate.json"
        write_json(path, config)
        check_ids = [
            "edge_contrast_asymmetry", "edge_gradient_asymmetry",
            "normalized_profile_dissimilar", "normalized_profile_uncorrelated",
            "radial_coverage_inconsistent", "endpoint_structure_inconsistent",
        ]
        rejected = {
            "schemaVersion": "groove-sidewall-source-consistency/1",
            "thresholdVersion": "sidewall-source-consistency-v1", "enabled": True,
            "status": "rejected", "metrics": {"endpointStructureDifference": 0.02},
            "checks": [{"checkId": check_id, "passed": check_id != "edge_contrast_asymmetry"}
                       for check_id in check_ids],
            "failedChecks": ["edge_contrast_asymmetry"],
        }
        with patch(
            "algorithms.slot_pose.legacy_adapter.assess_sidewall_source_consistency",
            return_value=rejected,
        ):
            payload = run(self.images / "one-real-two-shadows.png", path, "single:v3:candidate")
        self.assertFalse(payload["result"]["valid"])
        self.assertEqual("GROOVE_SOURCE_INCONSISTENT", payload["error"]["code"])
        self.assertIsNone(payload["result"]["currentAngleDeg"])
        self.assertIsNone(payload["result"]["imageFrameCorrectionDeg"])
        self.assertIsNone(payload["result"]["plcCommand"])
        candidate = payload["diagnostics"]["sidewallSourceConsistencyCandidate"]
        self.assertEqual("CANDIDATE_SUPPORTED", candidate["status"])
        self.assertFalse(candidate["authoritative"])
        self.assertFalse(candidate["posePromotionAllowed"])

    def test_source_adjudication_override_releases_image_guidance_but_never_plc(self) -> None:
        config = json.loads(self.config.read_text(encoding="utf-8"))
        config["detector"]["single_groove_pose"] = DEFAULT_SINGLE_GROOVE_POSE_CONFIG_V3
        config["detector"]["groove_refinement"] = {
            **DEFAULT_GROOVE_REFINEMENT_CONFIG,
            "threshold_version": "groove-sidewall-subpixel-v2",
        }
        config["detector"]["sidewall_source_consistency"] = {"enabled": True}
        config["detector"]["source_consistency_adjudication"] = {"enabled": True}
        path = self.root / "single-v3-source-adjudication.json"
        write_json(path, config)
        source = rejected_source_consistency(0.0203)
        source_before = json.loads(json.dumps(source))
        with patch(
            "algorithms.slot_pose.legacy_adapter.assess_sidewall_source_consistency",
            return_value=source,
        ):
            payload = run(self.images / "one-real-two-shadows.png", path, "single:v3:adjudicated")
        self.assertEqual(source_before, source)
        self.assertTrue(payload["result"]["valid"], payload)
        self.assertEqual("DETECTED", payload["result"]["detectionStatus"])
        self.assertIn(payload["result"]["guidanceStatus"], {
            "DETECTED_NEEDS_ADJUSTMENT", "DETECTED_IN_POSITION",
        })
        self.assertIsNotNone(payload["result"]["currentAngleDeg"])
        self.assertIsNotNone(payload["result"]["imageFrameCorrectionDeg"])
        self.assertEqual("BLOCKED_MAPPING_UNCONFIRMED", payload["result"]["plcExecutionStatus"])
        self.assertIsNone(payload["result"]["mechanicalCorrectionDeg"])
        self.assertIsNone(payload["result"]["plcCommand"])
        self.assertIsNone(payload["error"])
        diagnostics = payload["diagnostics"]
        self.assertEqual("rejected", diagnostics["grooveSourceConsistency"]["status"])
        adjudication = diagnostics["sidewallSourceConsistencyAdjudication"]
        self.assertEqual("ACCEPTED_OVERRIDE", adjudication["decision"])
        self.assertEqual("accepted", adjudication["effectiveStatus"])
        self.assertTrue(adjudication["imagePoseReleaseAllowed"])
        self.assertFalse(adjudication["plcAllowed"])
        self.assertEqual(
            adjudication,
            diagnostics["grooveRefinement"]["sourceConsistencyAdjudication"],
        )

    def test_source_adjudication_keeps_known_mixed_and_multi_failure_pairs_closed(self) -> None:
        config = json.loads(self.config.read_text(encoding="utf-8"))
        config["detector"]["single_groove_pose"] = DEFAULT_SINGLE_GROOVE_POSE_CONFIG_V3
        config["detector"]["groove_refinement"] = {
            **DEFAULT_GROOVE_REFINEMENT_CONFIG,
            "threshold_version": "groove-sidewall-subpixel-v2",
        }
        config["detector"]["sidewall_source_consistency"] = {"enabled": True}
        config["detector"]["source_consistency_adjudication"] = {"enabled": True}
        path = self.root / "single-v3-source-adjudication-negative.json"
        write_json(path, config)
        cases = (
            ("mixed", rejected_source_consistency(0.0764)),
            (
                "multiple",
                rejected_source_consistency(
                    0.02,
                    failed_checks=["edge_contrast_asymmetry", "edge_gradient_asymmetry"],
                ),
            ),
        )
        for name, source in cases:
            with self.subTest(name=name), patch(
                "algorithms.slot_pose.legacy_adapter.assess_sidewall_source_consistency",
                return_value=source,
            ):
                payload = run(self.images / "one-real-two-shadows.png", path, f"single:v3:{name}")
            self.assertFalse(payload["result"]["valid"])
            self.assertEqual("GROOVE_SOURCE_INCONSISTENT", payload["error"]["code"])
            self.assertIsNone(payload["result"]["currentAngleDeg"])
            self.assertIsNone(payload["result"]["imageFrameCorrectionDeg"])
            self.assertIsNone(payload["result"]["plcCommand"])
            adjudication = payload["diagnostics"]["sidewallSourceConsistencyAdjudication"]
            self.assertEqual("REJECTED", adjudication["decision"])
            self.assertFalse(adjudication["imagePoseReleaseAllowed"])

    def test_source_candidate_requires_v2_refinement_contract(self) -> None:
        config = json.loads(self.config.read_text(encoding="utf-8"))
        config["detector"]["single_groove_pose"] = DEFAULT_SINGLE_GROOVE_POSE_CONFIG
        config["detector"]["sidewall_source_consistency"] = {"enabled": True}
        config["detector"]["sidewall_source_consistency_candidate"] = {"enabled": True}
        path = self.root / "single-v1-source-candidate-invalid.json"
        write_json(path, config)
        with self.assertRaisesRegex(ValueError, "requires groove refinement v2"):
            load_config(path)

    def test_unique_local_second_wall_diagnostic_cannot_promote_failed_pose(self) -> None:
        config = json.loads(self.config.read_text(encoding="utf-8"))
        config["detector"]["single_groove_pose"] = DEFAULT_SINGLE_GROOVE_POSE_CONFIG_V3
        config["detector"]["groove_refinement"] = {
            **DEFAULT_GROOVE_REFINEMENT_CONFIG,
            "threshold_version": "groove-sidewall-subpixel-v2",
        }
        config["detector"]["sidewall_source_consistency"] = {"enabled": True}
        config["detector"]["local_second_wall_diagnostic"] = {"enabled": True}
        path = self.root / "single-v3-local-wall-diagnostic.json"
        write_json(path, config)
        rejected = {
            "schemaVersion": "groove-sidewall-source-consistency/1",
            "thresholdVersion": "sidewall-source-consistency-v1",
            "enabled": True, "status": "rejected",
            "metrics": {"contrastNormalizedDifference": 0.18}, "checks": [],
            "failedChecks": ["edge_contrast_asymmetry"],
        }
        diagnostic = {
            "schemaVersion": "local-second-wall-diagnostic/4",
            "thresholdVersion": "local-second-wall-diagnostic-v1",
            "enabled": True, "status": "PARTIALLY_OBSERVED",
            "failureStage": "single_wall_observability",
            "errorCode": "PARTIAL_GROOVE_OBSERVATION",
            "authoritative": False, "posePromotionAllowed": False,
            "anchorEvidence": [],
            "searchDomains": [],
            "sideSearchCandidates": [],
            "sideSearchMergeClusters": [], "searchOutcomeSummary": {},
            "rawHypotheses": [], "hypothesisMergeClusters": [],
            "hypotheses": [{
                "hypothesisId": "local-wall-hypothesis-001",
                "failedChecks": ["sidewall_source_consistency"],
            }],
            "canonicalWallPairs": [],
            "experimentalCandidate": None,
            "partialObservation": {
                "observedWallClusterIds": ["falling-wall-cluster-001"],
                "observedWallCandidateCount": 1,
                "completeSameSourceOpeningObserved": False,
                "trueGrooveWallIdentityConfirmed": False,
                "humanConfirmationAppliedAtRuntime": False,
                "oppositeWallObservability": "UNCONFIRMED",
                "reason": "SINGLE_WALL_CLUSTER",
            },
        }
        with (
            patch(
                "algorithms.slot_pose.legacy_adapter.assess_sidewall_source_consistency",
                return_value=rejected,
            ),
            patch(
                "algorithms.slot_pose.legacy_adapter.diagnose_local_second_wall",
                return_value=diagnostic,
            ) as search,
        ):
            payload = run(self.images / "one-real-two-shadows.png", path, "single:v3:local-wall")
        search.assert_called_once()
        self.assertFalse(payload["result"]["valid"])
        self.assertEqual("GROOVE_SOURCE_INCONSISTENT", payload["error"]["code"])
        self.assertIsNone(payload["result"]["imageFrameCorrectionDeg"])
        self.assertEqual("PARTIALLY_OBSERVED", payload["diagnostics"]["localSecondWallDiagnostic"]["status"])
        self.assertFalse(payload["diagnostics"]["localSecondWallDiagnostic"]["posePromotionAllowed"])
        self.assertIsNone(payload["diagnostics"]["localSecondWallDiagnostic"]["experimentalCandidate"])

    def test_complete_two_wall_pose_keeps_image_guidance_and_plc_block(self) -> None:
        config = json.loads(self.config.read_text(encoding="utf-8"))
        config["detector"]["single_groove_pose"] = DEFAULT_SINGLE_GROOVE_POSE_CONFIG_V3
        config["detector"]["groove_refinement"] = {
            **DEFAULT_GROOVE_REFINEMENT_CONFIG,
            "threshold_version": "groove-sidewall-subpixel-v2",
        }
        config["pose"].update({
            "target_semantics_confirmed": True,
            "conventions_confirmed": False,
            "mechanical_zero_image_deg": None,
            "positive_direction": None,
            "production_plc_mapping_confirmed": False,
        })
        path = self.root / "single-v3-complete-two-wall-regression.json"
        write_json(path, config)
        payload = run(self.images / "one-real-two-shadows.png", path, "single:v3:complete")
        self.assertTrue(payload["result"]["valid"], payload)
        self.assertEqual("DETECTED", payload["result"]["detectionStatus"])
        self.assertEqual(85.0, payload["result"]["targetAngleDeg"])
        self.assertEqual(5.0, payload["result"]["toleranceDeg"])
        self.assertIsNotNone(payload["result"]["currentAngleDeg"])
        self.assertIsNotNone(payload["result"]["imageFrameCorrectionDeg"])
        self.assertIn(payload["result"]["rotationDirection"], {
            "CLOCKWISE", "COUNTERCLOCKWISE", "NONE",
        })
        self.assertIsNone(payload["result"]["mechanicalCorrectionDeg"])
        self.assertIsNone(payload["result"]["plcCommand"])

    def test_v3_zero_or_multiple_grooves_are_detection_failures(self) -> None:
        config = json.loads(self.config.read_text(encoding="utf-8"))
        config["detector"]["single_groove_pose"] = DEFAULT_SINGLE_GROOVE_POSE_CONFIG_V3
        config["detector"]["groove_refinement"] = {
            **DEFAULT_GROOVE_REFINEMENT_CONFIG,
            "threshold_version": "groove-sidewall-subpixel-v2",
        }
        path = self.root / "single-v3-failure.json"
        write_json(path, config)
        for name, error_code in (
            ("zero-real-two-shadows.png", "GROOVE_RECOGNITION_FAILED"),
            ("two-real-one-shadow.png", "GROOVE_RECOGNITION_AMBIGUOUS"),
        ):
            with self.subTest(name=name):
                payload = run(self.images / name, path, f"single:v3:{name}")
                self.assertEqual("slot-pose-result/3", payload["schemaVersion"])
                self.assertFalse(payload["result"]["valid"])
                self.assertEqual("DETECTION_FAILED", payload["result"]["detectionStatus"])
                self.assertEqual("NOT_AVAILABLE", payload["result"]["guidanceStatus"])
                self.assertIsNone(payload["result"]["imageFrameCorrectionDeg"])
                self.assertEqual(error_code, payload["error"]["code"])

    def test_v3_circle_family_failures_never_release_pose_or_plc_fields(self) -> None:
        config = json.loads(self.config.read_text(encoding="utf-8"))
        config["detector"]["single_groove_pose"] = DEFAULT_SINGLE_GROOVE_POSE_CONFIG_V3
        path = self.root / "single-v3-circle-family-failure.json"
        write_json(path, config)
        cases = (
            ("PHYSICAL_OUTER_CIRCLE_FAILED", ["no_qualified_edge_family"]),
            ("HOUSING_CIRCLE_AMBIGUOUS", ["ambiguous_edge_families"]),
            ("HOUSING_CIRCLE_AMBIGUOUS", ["family_search_overflow"]),
        )
        for code, failed_checks in cases:
            error = LegacyAdapterError(
                code, "physical_outer_circle", "synthetic circle-family failure",
                {"physicalOuterCircle": {"status": "failed", "failedChecks": failed_checks}},
            )
            with self.subTest(code=code, failed_checks=failed_checks), patch(
                "algorithms.slot_pose.legacy_adapter.LegacyAEndFaceAdapter.estimate",
                side_effect=error,
            ):
                payload = run(
                    self.images / "one-real-two-shadows.png", path,
                    f"single:v3:circle-family:{failed_checks[0]}",
                )
            self.assertFalse(payload["result"]["valid"])
            self.assertEqual(code, payload["error"]["code"])
            for field in (
                "currentAngleDeg", "correctionRawDeg", "correctionDeg",
                "imageFrameCorrectionDeg", "rotationDirection", "withinTolerance",
                "mechanicalCorrectionDeg", "plcCommand",
            ):
                self.assertIsNone(payload["result"][field], field)

    def test_v3_optional_ambiguity_resolution_requires_unique_physical_refinement(self) -> None:
        config = json.loads(self.config.read_text(encoding="utf-8"))
        config["detector"]["single_groove_pose"] = DEFAULT_SINGLE_GROOVE_POSE_CONFIG_V3
        config["detector"]["groove_refinement"] = {
            **DEFAULT_GROOVE_REFINEMENT_CONFIG, "threshold_version": "groove-sidewall-subpixel-v2",
        }
        config["detector"]["ambiguity_resolution"] = {
            "schema_version": "groove-ambiguity-resolution/1", "enabled": True, "max_candidates": 3,
        }
        path = self.root / "single-v3-resolver.json"
        write_json(path, config)
        calls = []

        def fake_refinement(_gray, _center, _radius, candidate, *_args, **_kwargs):
            calls.append(candidate["candidateId"])
            accepted = len(calls) == 1
            return {
                "schemaVersion": "slot-groove-subpixel-opening/2", "status": "accepted" if accepted else "failed",
                "openingEndpointProfileDeg": [candidate["startDeg"], candidate["endDeg"]] if accepted else None,
                "openingMidpointProfileDeg": candidate["centerDeg"] if accepted else None,
                "failedChecks": [] if accepted else ["sidewall_missing"],
            }

        with patch("algorithms.slot_pose.legacy_adapter.refine_groove_opening", side_effect=fake_refinement):
            payload = run(self.images / "two-real-one-shadow.png", path, "single:v3:resolver")
        self.assertTrue(payload["result"]["valid"], payload)
        self.assertEqual("resolved", payload["diagnostics"]["grooveResolution"]["status"])
        self.assertEqual(2, len(payload["diagnostics"]["grooveResolution"]["attempts"]))
        self.assertEqual(1, len(payload["diagnostics"]["grooveCandidates"]))

    def test_v3_shadow_source_diagnostic_reuses_unique_physical_survivor(self) -> None:
        config = json.loads(self.config.read_text(encoding="utf-8"))
        config["detector"]["single_groove_pose"] = DEFAULT_SINGLE_GROOVE_POSE_CONFIG_V3
        config["detector"]["groove_refinement"] = {
            **DEFAULT_GROOVE_REFINEMENT_CONFIG,
            "threshold_version": "groove-sidewall-subpixel-v2",
        }
        config["detector"]["ambiguity_resolution"] = {"enabled": True}
        config["detector"]["sidewall_source_consistency"] = {"enabled": True}
        config["detector"]["groove_shadow_source_discrimination"] = {"enabled": True}
        path = self.root / "single-v3-shadow-source.json"
        write_json(path, config)
        calls = []

        def fake_refinement(_gray, _center, _radius, candidate, *_args, **_kwargs):
            calls.append(candidate["candidateId"])
            accepted = len(calls) == 1
            return {
                "schemaVersion": "slot-groove-subpixel-opening/2",
                "status": "accepted" if accepted else "failed",
                "coarseCandidateId": candidate["candidateId"],
                "openingEndpointProfileDeg": (
                    [candidate["startDeg"], candidate["endDeg"]] if accepted else None
                ),
                "openingMidpointProfileDeg": candidate["centerDeg"] if accepted else None,
                "startSide": {} if accepted else None,
                "endSide": {} if accepted else None,
                "outerCircleIntersections": [{}, {}] if accepted else None,
                "failedChecks": [] if accepted else ["endSide_consensus_not_found"],
            }

        def fake_source(refinement, _config):
            return {
                "status": "accepted" if refinement["status"] == "accepted" else "not_evaluated",
                "failedChecks": [], "metrics": {},
            }

        with (
            patch("algorithms.slot_pose.legacy_adapter.refine_groove_opening", side_effect=fake_refinement),
            patch("algorithms.slot_pose.legacy_adapter.assess_sidewall_source_consistency", side_effect=fake_source),
        ):
            payload = run(self.images / "two-real-one-shadow.png", path, "single:v3:shadow-source")
        self.assertTrue(payload["result"]["valid"], payload)
        diagnostic = payload["diagnostics"]["grooveShadowSourceDiscrimination"]
        self.assertEqual("REAL_GROOVE_COMPLETE_NEAR_FIXTURE_SHADOW", diagnostic["classification"])
        self.assertTrue(diagnostic["poseChainAllowed"])
        self.assertEqual(2, diagnostic["candidateCount"])
        self.assertIsNone(payload["result"]["plcCommand"])

    def test_v3_shadow_source_mixed_wall_evidence_stays_fail_closed(self) -> None:
        config = json.loads(self.config.read_text(encoding="utf-8"))
        config["detector"]["single_groove_pose"] = DEFAULT_SINGLE_GROOVE_POSE_CONFIG_V3
        config["detector"]["groove_refinement"] = {
            **DEFAULT_GROOVE_REFINEMENT_CONFIG,
            "threshold_version": "groove-sidewall-subpixel-v2",
        }
        config["detector"]["ambiguity_resolution"] = {"enabled": True}
        config["detector"]["sidewall_source_consistency"] = {"enabled": True}
        config["detector"]["groove_shadow_source_discrimination"] = {"enabled": True}
        path = self.root / "single-v3-shadow-source-mixed.json"
        write_json(path, config)

        def accepted_refinement(_gray, _center, _radius, candidate, *_args, **_kwargs):
            return {
                "schemaVersion": "slot-groove-subpixel-opening/2", "status": "accepted",
                "coarseCandidateId": candidate["candidateId"],
                "openingEndpointProfileDeg": [candidate["startDeg"], candidate["endDeg"]],
                "openingMidpointProfileDeg": candidate["centerDeg"],
                "startSide": {}, "endSide": {}, "outerCircleIntersections": [{}, {}],
                "failedChecks": [],
            }

        with (
            patch("algorithms.slot_pose.legacy_adapter.refine_groove_opening", side_effect=accepted_refinement),
            patch(
                "algorithms.slot_pose.legacy_adapter.assess_sidewall_source_consistency",
                return_value={
                    "status": "rejected", "failedChecks": ["normalized_profile_dissimilar"],
                    "metrics": {"normalizedProfileMae": 0.4},
                },
            ),
        ):
            payload = run(self.images / "two-real-one-shadow.png", path, "single:v3:shadow-mixed")
        self.assertFalse(payload["result"]["valid"])
        self.assertEqual("GROOVE_SOURCE_INCONSISTENT", payload["error"]["code"])
        diagnostic = payload["diagnostics"]["grooveShadowSourceDiscrimination"]
        self.assertEqual("REAL_GROOVE_SHADOW_MIXED_OR_OCCLUDED", diagnostic["classification"])
        self.assertFalse(diagnostic["poseChainAllowed"])
        for field in (
            "currentAngleDeg", "correctionRawDeg", "correctionDeg",
            "imageFrameCorrectionDeg", "rotationDirection", "mechanicalCorrectionDeg", "plcCommand",
        ):
            self.assertIsNone(payload["result"][field], field)

    def test_provisional_candidate_with_zero_physical_survivors_fails_at_refinement(self) -> None:
        config = json.loads(self.config.read_text(encoding="utf-8"))
        config["detector"]["single_groove_pose"] = DEFAULT_SINGLE_GROOVE_POSE_CONFIG_V3
        config["detector"]["groove_refinement"] = {
            **DEFAULT_GROOVE_REFINEMENT_CONFIG,
            "threshold_version": "groove-sidewall-subpixel-v2",
        }
        config["detector"]["ambiguity_resolution"] = {"enabled": True}
        config["detector"]["groove_recognition_recovery"] = {"enabled": True}
        path = self.root / "single-v3-provisional-zero-survivors.json"
        write_json(path, config)
        candidate = {**accepted_candidate("candidate-provisional", 300.0), "provisionalRecognition": True}
        recognition = {
            "status": "accepted", "rawCandidateCount": 1, "acceptedCount": 0,
            "acceptedCandidateIds": [], "provisionalCandidateIds": [candidate["candidateId"]],
            "effectiveCandidateIds": [candidate["candidateId"]], "assessments": [],
        }
        failed_refinement = {
            "schemaVersion": "slot-groove-subpixel-opening/2", "status": "failed",
            "openingEndpointProfileDeg": None, "openingMidpointProfileDeg": None,
            "startSide": None, "endSide": None, "outerCircleIntersections": None,
            "failedChecks": ["endSide_wall_family_not_found"],
        }
        with (
            patch(
                "algorithms.slot_pose.legacy_adapter.LegacyAEndFaceAdapter._recognize_target_grooves",
                return_value=(recognition, [candidate]),
            ),
            patch("algorithms.slot_pose.legacy_adapter.refine_groove_opening", return_value=failed_refinement),
        ):
            payload = run(self.images / "one-real-two-shadows.png", path, "single:v3:provisional-zero")
        self.assertFalse(payload["result"]["valid"])
        self.assertEqual("GROOVE_REFINEMENT_FAILED", payload["error"]["code"])
        self.assertEqual("groove_refinement", payload["error"]["stage"])
        self.assertIn("endSide_wall_family_not_found", payload["error"]["message"])
        self.assertIsNone(payload["result"]["currentAngleDeg"])
        self.assertIsNone(payload["result"]["plcCommand"])
        self.assertFalse(payload["result"]["plcExecutionAuthoritative"])

    def test_two_provisional_physical_survivors_are_explicitly_ambiguous(self) -> None:
        config = json.loads(self.config.read_text(encoding="utf-8"))
        config["detector"]["single_groove_pose"] = DEFAULT_SINGLE_GROOVE_POSE_CONFIG_V3
        config["detector"]["groove_refinement"] = {
            **DEFAULT_GROOVE_REFINEMENT_CONFIG,
            "threshold_version": "groove-sidewall-subpixel-v2",
        }
        config["detector"]["ambiguity_resolution"] = {"enabled": True}
        config["detector"]["groove_recognition_recovery"] = {"enabled": True}
        path = self.root / "single-v3-provisional-multiple-survivors.json"
        write_json(path, config)
        candidates = [
            {**accepted_candidate("candidate-provisional-a", 300.0), "provisionalRecognition": True},
            {**accepted_candidate("candidate-provisional-b", 30.0), "provisionalRecognition": True},
        ]
        recognition = {
            "status": "ambiguous", "rawCandidateCount": 2, "acceptedCount": 0,
            "acceptedCandidateIds": [],
            "provisionalCandidateIds": [item["candidateId"] for item in candidates],
            "effectiveCandidateIds": [item["candidateId"] for item in candidates],
            "assessments": [],
        }

        def accepted_refinement(_gray, _center, _radius, candidate, *_args, **_kwargs):
            return {
                "schemaVersion": "slot-groove-subpixel-opening/2", "status": "accepted",
                "coarseCandidateId": candidate["candidateId"],
                "openingEndpointProfileDeg": [candidate["startDeg"], candidate["endDeg"]],
                "openingMidpointProfileDeg": candidate["centerDeg"],
                "startSide": {}, "endSide": {}, "outerCircleIntersections": [{}, {}],
                "failedChecks": [],
            }

        verified_exclusion = {
            "schemaVersion": "fixture-groove-source-exclusion/1", "status": "verified",
            "fixtureBodiesVerified": True, "uContourComplete": True,
            "fixtureSourceExcluded": True, "candidateSelectionUsedFixedAngle": False,
            "failedChecks": [],
        }
        with (
            patch(
                "algorithms.slot_pose.legacy_adapter.LegacyAEndFaceAdapter._recognize_target_grooves",
                return_value=(recognition, candidates),
            ),
            patch("algorithms.slot_pose.legacy_adapter.refine_groove_opening", side_effect=accepted_refinement),
            patch(
                "algorithms.slot_pose.legacy_adapter.build_fixture_source_exclusion",
                return_value=verified_exclusion,
            ),
        ):
            payload = run(self.images / "two-real-one-shadow.png", path, "single:v3:provisional-multiple")
        self.assertFalse(payload["result"]["valid"])
        self.assertEqual("GROOVE_RECOGNITION_AMBIGUOUS", payload["error"]["code"])
        self.assertEqual("multiple_survived", payload["diagnostics"]["grooveResolution"]["status"])
        for field in (
            "currentAngleDeg", "correctionRawDeg", "correctionDeg",
            "imageFrameCorrectionDeg", "rotationDirection", "mechanicalCorrectionDeg", "plcCommand",
        ):
            self.assertIsNone(payload["result"][field], field)
        self.assertFalse(payload["result"]["plcExecutionAuthoritative"])

    def test_v2_refinement_quality_failure_is_explicit_and_never_uses_coarse_angle(self) -> None:
        config = json.loads(self.config.read_text(encoding="utf-8"))
        config["config_id"] = "synthetic-single-real-groove-refinement-failure"
        config["detector"]["single_groove_pose"] = DEFAULT_SINGLE_GROOVE_POSE_CONFIG_V2
        config["detector"]["groove_refinement"] = {
            **DEFAULT_GROOVE_REFINEMENT_CONFIG,
            "max_line_residual_p95_px": 1e-6,
        }
        path = self.root / "single-v2-refinement-failure.json"
        write_json(path, config)
        payload = run(self.images / "one-real-left-lower.png", path, "single:v2:refinement-failure")
        self.assertEqual("GROOVE_REFINEMENT_FAILED", payload["error"]["code"], payload)
        self.assertEqual("groove_refinement", payload["error"]["stage"])
        self.assertIn("line_residual", payload["error"]["message"])
        self.assertIsNone(payload["result"]["signedRelativeRotationDeg"])
        self.assertIsNone(payload["diagnostics"]["singleGroovePose"]["datumMeasurement"])
        self.assertEqual(
            "NOT_EVALUATED",
            payload["diagnostics"]["singleGroovePose"]["targetAssessment"]["status"],
        )

    def test_v2_config_rejects_silent_target_or_version_changes(self) -> None:
        from algorithms.slot_pose.single_groove_pose import merged_single_groove_pose_config

        for mutate in (
            lambda cfg: cfg["target"].__setitem__("nominal_deg", -85.0),
            lambda cfg: cfg.__setitem__("output_schema_version", "slot-single-real-groove-pose/1"),
            lambda cfg: cfg.__setitem__("unexpected", True),
        ):
            config = json.loads(json.dumps(DEFAULT_SINGLE_GROOVE_POSE_CONFIG_V2))
            mutate(config)
            with self.subTest(config=config), self.assertRaisesRegex(ValueError, "single_groove_pose"):
                merged_single_groove_pose_config(config)

        runtime_config = json.loads(self.config.read_text(encoding="utf-8"))
        runtime_config["detector"]["single_groove_pose"] = DEFAULT_SINGLE_GROOVE_POSE_CONFIG_V2
        runtime_config["detector"]["groove_refinement"] = {
            **DEFAULT_GROOVE_REFINEMENT_CONFIG,
            "max_line_residual_p95_px": 0.0,
        }
        path = self.root / "invalid-groove-refinement.json"
        write_json(path, runtime_config)
        with self.assertRaisesRegex(ValueError, "groove_refinement"):
            load_config(path)


if __name__ == "__main__":
    unittest.main()
