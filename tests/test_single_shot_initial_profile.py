import copy
import hashlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

import jsonschema

from algorithms.slot_pose.sidewall_consistency import DEFAULT_SIDEWALL_CONSISTENCY_CONFIG
from algorithms.slot_pose.single_groove_pose import build_closed_loop_guidance


ROOT = Path(__file__).resolve().parents[1]


def base_config() -> dict:
    return {
        "schema_version": "slot-pose-config/1",
        "config_id": "test-single-shot-base",
        "legacy_asset": {
            "source_mode": "bundled_module",
            "bundled_module": "algorithms.end_face.core",
            "source_sha256": "f" * 64,
            "upstream_source_sha256": "e" * 64,
        },
        "pose": {"production_plc_mapping_confirmed": False},
        "detector": {
            "diagnostic_mode": "single_real_groove",
            "sidewall_source_consistency": {
                **copy.deepcopy(DEFAULT_SIDEWALL_CONSISTENCY_CONFIG),
                "enabled": True,
            },
            "source_consistency_adjudication": {
                "schema_version": "source-consistency-adjudication/1",
                "enabled": False,
                "threshold_version": "endpoint-structure-runtime-adjudication-v1",
                "development_only": True,
                "max_endpoint_structure_difference": 0.05,
            },
            "groove_refinement": {"threshold_version": "groove-sidewall-subpixel-v2"},
            "single_groove_pose": {
                "schema_version": "single-real-groove-pose-config/3",
                "output_schema_version": "slot-single-real-groove-pose/3",
                "image_angle_schema_version": "slot-groove-image-angle/2",
                "datum_angle_schema_version": "slot-groove-y-down-angle/1",
                "expected_accepted_groove_count": 1,
                "target": {
                    "schema_version": "slot-groove-target/3",
                    "nominal_deg": 85.0,
                    "tolerance_deg": 5.0,
                    "accepted_min_deg": 80.0,
                    "accepted_max_deg": 90.0,
                    "required_horizontal_position": "left",
                    "required_vertical_position": "lower_or_axis",
                    "physical_datum_definition_id": "detected-physical-circle-positive-y-down-ray/1",
                    "angle_convention_id": "image-y-down-clockwise-signed/1",
                },
            },
        },
    }


class SingleShotInitialProfileTests(unittest.TestCase):
    @staticmethod
    def _datum(angle: float, *, in_region: bool = True) -> dict:
        return {
            "measuredFromPositiveYClockwiseDeg": angle,
            "position": {"requiredRegionPassed": in_region},
        }

    def test_materializes_only_the_verified_single_shot_chain(self) -> None:
        from tools.prepare_single_shot_initial_config import build_initial_config

        configured = build_initial_config(base_config())
        detector = configured["detector"]
        self.assertEqual("single_real_groove", detector["diagnostic_mode"])
        self.assertTrue(detector["sidewall_source_consistency"]["enabled"])
        self.assertEqual(
            DEFAULT_SIDEWALL_CONSISTENCY_CONFIG["max_contrast_normalized_difference"],
            detector["sidewall_source_consistency"]["max_contrast_normalized_difference"],
        )
        self.assertTrue(detector["source_consistency_adjudication"]["enabled"])
        self.assertTrue(detector["source_consistency_adjudication"]["development_only"])
        self.assertEqual(
            {
                "schema_version": "groove-ambiguity-resolution/1",
                "enabled": True,
                "max_candidates": 3,
            },
            detector["ambiguity_resolution"],
        )
        self.assertFalse(configured["pose"]["production_plc_mapping_confirmed"])
        self.assertEqual("bundled_module", configured["legacy_asset"]["source_mode"])

    def test_rejects_mode_target_plc_external_source_and_changed_original_gate(self) -> None:
        from tools.prepare_single_shot_initial_config import build_initial_config

        mutations = (
            (("detector", "diagnostic_mode"), "multi_notch_roles", "single_real_groove"),
            (("detector", "single_groove_pose", "target", "nominal_deg"), 84.0, "85"),
            (("pose", "production_plc_mapping_confirmed"), True, "PLC"),
            (("legacy_asset", "source_mode"), "external_file", "bundled"),
            (("detector", "sidewall_source_consistency", "max_contrast_normalized_difference"), 0.19, "contrast"),
        )
        for keys, value, message in mutations:
            with self.subTest(keys=keys):
                candidate = base_config()
                target = candidate
                for key in keys[:-1]:
                    target = target[key]
                target[keys[-1]] = value
                with self.assertRaisesRegex(ValueError, message):
                    build_initial_config(candidate)

    def test_report_schema_and_policy_are_explicit(self) -> None:
        from tools.prepare_single_shot_initial_config import build_initial_config, build_profile_report

        source = base_config()
        configured = build_initial_config(source)
        source_bytes = json.dumps(source, ensure_ascii=False, sort_keys=True).encode()
        output_bytes = json.dumps(configured, ensure_ascii=False, sort_keys=True).encode()
        report = build_profile_report(
            source_config_sha256=hashlib.sha256(source_bytes).hexdigest(),
            output_config_sha256=hashlib.sha256(output_bytes).hexdigest(),
        )
        schema = json.loads((ROOT / "contracts/single-shot-initial-profile.schema.json").read_text())
        jsonschema.validate(report, schema)
        self.assertTrue(report["policies"]["imageGuidanceAllowed"])
        self.assertFalse(report["policies"]["pairedCaptureRequired"])
        self.assertFalse(report["policies"]["plcAllowed"])
        self.assertFalse(report["policies"]["manualTruthAppliedAtRuntime"])
        self.assertTrue(report["policies"]["occlusionFailsClosed"])
        self.assertTrue(report["ambiguityResolution"]["enabled"])
        self.assertEqual(3, report["ambiguityResolution"]["maxCandidates"])

    def test_v3_explicitly_enables_global_circle_family_and_preserves_v2(self) -> None:
        from tools.prepare_single_shot_initial_config import (
            build_initial_config, build_initial_config_v3, build_profile_report_v3,
        )

        source = base_config()
        v2 = build_initial_config(source)
        self.assertNotIn("physical_outer_circle", v2["detector"])
        v3 = build_initial_config_v3(source)
        physical = v3["detector"]["physical_outer_circle"]
        self.assertEqual("single-real-groove-85deg-global-circle-family-v3", v3["config_id"])
        self.assertTrue(physical["edge_family_selection"]["enabled"])
        self.assertEqual(5.0, physical["max_residual_p95_px"])
        self.assertEqual(0.75, physical["min_inlier_ratio"])
        self.assertFalse(v3["pose"]["production_plc_mapping_confirmed"])
        self.assertEqual(
            DEFAULT_SIDEWALL_CONSISTENCY_CONFIG["max_contrast_normalized_difference"],
            v3["detector"]["sidewall_source_consistency"]["max_contrast_normalized_difference"],
        )
        report = build_profile_report_v3(
            source_config_sha256="a" * 64, output_config_sha256="b" * 64,
        )
        schema = json.loads(
            (ROOT / "contracts/single-shot-initial-profile-v3.schema.json").read_text()
        )
        jsonschema.validate(report, schema)
        self.assertEqual("single-shot-initial-profile/3", report["schemaVersion"])
        self.assertTrue(report["circleEdgeFamilySelection"]["uniqueFamilyRequired"])
        self.assertTrue(report["circleEdgeFamilySelection"]["originalQualityGatesPreserved"])
        self.assertFalse(report["circleEdgeFamilySelection"]["fixedAngleMaskApplied"])

    def test_v4_enables_family_consensus_without_mutating_v3(self) -> None:
        from tools.prepare_single_shot_initial_config import (
            build_initial_config_v3, build_initial_config_v4, build_profile_report_v4,
        )

        source = base_config()
        v3 = build_initial_config_v3(source)
        v4 = build_initial_config_v4(source)
        self.assertEqual(
            "deterministic-three-point-global-circle-v1",
            v3["detector"]["physical_outer_circle"]["edge_family_selection"]["strategy_version"],
        )
        self.assertEqual(
            "deterministic-family-consensus-circle-v2",
            v4["detector"]["physical_outer_circle"]["edge_family_selection"]["strategy_version"],
        )
        self.assertEqual("single-real-groove-85deg-circle-family-consensus-v4", v4["config_id"])
        reviewed = build_initial_config_v3(source)
        reviewed["detector"]["reviewed_extension"] = {"enabled": True}
        upgraded = build_initial_config_v4(reviewed)
        self.assertEqual({"enabled": True}, upgraded["detector"]["reviewed_extension"])
        self.assertEqual(
            "deterministic-three-point-global-circle-v1",
            reviewed["detector"]["physical_outer_circle"]["edge_family_selection"]["strategy_version"],
        )
        report = build_profile_report_v4(
            source_config_sha256="a" * 64, output_config_sha256="b" * 64,
        )
        schema = json.loads(
            (ROOT / "contracts/single-shot-initial-profile-v4.schema.json").read_text()
        )
        jsonschema.validate(report, schema)

    def test_v5_enables_sidewall_source_family_without_mutating_v4(self) -> None:
        from tools.prepare_single_shot_initial_config import (
            build_initial_config_v4, build_initial_config_v5, build_profile_report_v5,
        )

        source = base_config()
        v4 = build_initial_config_v4(source)
        v5 = build_initial_config_v5(v4)
        self.assertNotIn(
            "wall_edge_family", v4["detector"]["groove_refinement"],
        )
        family = v5["detector"]["groove_refinement"]["wall_edge_family"]
        self.assertEqual("groove-wall-edge-family/2", family["schema_version"])
        self.assertEqual("shared-longitudinal-wall-family-v2", family["strategy_version"])
        self.assertTrue(family["enabled"])
        self.assertEqual("single-real-groove-85deg-sidewall-family-dedup-v5", v5["config_id"])
        report = build_profile_report_v5(
            source_config_sha256="a" * 64, output_config_sha256="b" * 64,
        )
        self.assertEqual("single-shot-initial-profile/5", report["schemaVersion"])
        self.assertTrue(report["wallSourceFamilySelection"]["completeLinkRequired"])
        self.assertTrue(report["wallSourceFamilySelection"]["fixtureSourceExclusionRequired"])
        self.assertTrue(report["wallSourceFamilySelection"]["radialSidewallEvidenceRequired"])
        self.assertEqual(
            "source-consistency-adjudication/3",
            v5["detector"]["source_consistency_adjudication"]["schema_version"],
        )
        self.assertFalse(report["wallSourceFamilySelection"]["manualTruthAppliedAtRuntime"])
        schema = json.loads(
            (ROOT / "contracts/single-shot-initial-profile-v5.schema.json").read_text(
                encoding="utf-8"
            )
        )
        jsonschema.Draft202012Validator(schema).validate(report)

    def test_v6_enables_only_versioned_polar_quality_adjudication_without_mutating_v5(self) -> None:
        from tools.prepare_single_shot_initial_config import (
            build_initial_config_v5, build_initial_config_v6, build_profile_report_v6,
        )

        source = base_config()
        v5 = build_initial_config_v5(source)
        v6 = build_initial_config_v6(v5)
        self.assertNotIn("polar_quality_adjudication", v5["detector"])
        decision = v6["detector"]["polar_quality_adjudication"]
        self.assertTrue(decision["enabled"])
        self.assertEqual("polar-quality-adjudication/1", decision["schema_version"])
        self.assertEqual(
            DEFAULT_SIDEWALL_CONSISTENCY_CONFIG["max_contrast_normalized_difference"],
            v6["detector"]["sidewall_source_consistency"]["max_contrast_normalized_difference"],
        )
        self.assertEqual(3.0, v6["detector"].get("min_polar_score", 3.0))
        self.assertFalse(v6["pose"]["production_plc_mapping_confirmed"])
        self.assertTrue(v6["detector"]["fixture_shadow_model"]["enabled"])
        self.assertTrue(v6["detector"]["groove_shadow_source_discrimination"]["enabled"])
        report = build_profile_report_v6(
            source_config_sha256="a" * 64, output_config_sha256="b" * 64,
        )
        self.assertEqual("single-shot-initial-profile/6", report["schemaVersion"])
        self.assertTrue(report["polarQualityAdjudication"]["solePolarFailureOnly"])
        self.assertTrue(report["polarQualityAdjudication"]["originalPolarThresholdPreserved"])
        self.assertFalse(report["polarQualityAdjudication"]["plcAllowed"])
        schema = json.loads(
            (ROOT / "contracts/single-shot-initial-profile-v6.schema.json").read_text(
                encoding="utf-8"
            )
        )
        jsonschema.Draft202012Validator(schema).validate(report)

    def test_single_shot_guidance_wrap_direction_and_deadband(self) -> None:
        target = base_config()["detector"]["single_groove_pose"]["target"]
        examples = (
            (82.978, "DETECTED_IN_POSITION", 0.0, "NONE"),
            (22.834, "DETECTED_NEEDS_ADJUSTMENT", 62.166, "CLOCKWISE"),
            (-158.111, "DETECTED_NEEDS_ADJUSTMENT", -116.889, "COUNTERCLOCKWISE"),
            (80.0, "DETECTED_IN_POSITION", 0.0, "NONE"),
            (90.0, "DETECTED_IN_POSITION", 0.0, "NONE"),
        )
        for current, status, correction, direction in examples:
            with self.subTest(current=current):
                result = build_closed_loop_guidance(
                    target, self._datum(current), geometry_valid=True,
                    plc_mapping_confirmed=False,
                )
                self.assertEqual("DETECTED", result["detectionStatus"])
                self.assertEqual(status, result["guidanceStatus"])
                self.assertAlmostEqual(correction, result["correctionDeg"], places=9)
                self.assertEqual(direction, result["rotationDirection"])
                self.assertIsNone(result["plcExecution"]["plcCommand"])
                self.assertIsNone(result["plcExecution"]["mechanicalCorrectionDeg"])

    def test_untrusted_or_partially_observed_geometry_has_no_guidance(self) -> None:
        target = base_config()["detector"]["single_groove_pose"]["target"]
        for datum in (None, self._datum(29.5)):
            with self.subTest(datum=datum):
                result = build_closed_loop_guidance(
                    target, datum, geometry_valid=False, plc_mapping_confirmed=False,
                )
                self.assertEqual("DETECTION_FAILED", result["detectionStatus"])
                self.assertEqual("NOT_AVAILABLE", result["guidanceStatus"])
                for field in (
                    "currentAngleDeg", "correctionRawDeg", "correctionDeg",
                    "imageFrameCorrectionDeg", "rotationDirection", "withinTolerance",
                ):
                    self.assertIsNone(result[field], field)
                self.assertIsNone(result["plcExecution"]["plcCommand"])

    def test_cli_writes_only_git_external_outputs(self) -> None:
        tool = ROOT / "tools/prepare_single_shot_initial_config.py"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            source = root / "base.json"
            output = root / "initial.json"
            report = root / "profile.json"
            source.write_text(json.dumps(base_config()), encoding="utf-8")
            completed = subprocess.run(
                ["python", str(tool), "--base-config", str(source), "--output", str(output), "--report", str(report)],
                cwd=ROOT, text=True, capture_output=True, check=False,
            )
            self.assertEqual(0, completed.returncode, completed.stderr)
            self.assertTrue(output.is_file())
            self.assertTrue(report.is_file())
        rejected = subprocess.run(
            ["python", str(tool), "--base-config", str(ROOT / "config/inspection.example.json"),
             "--output", str(ROOT / "single-shot-initial.invalid.json"),
             "--report", str(ROOT / "single-shot-initial-profile.invalid.json")],
            cwd=ROOT, text=True, capture_output=True, check=False,
        )
        self.assertEqual(2, rejected.returncode)
        self.assertIn("outside", rejected.stderr)
        self.assertFalse((ROOT / "single-shot-initial.invalid.json").exists())
        self.assertFalse((ROOT / "single-shot-initial-profile.invalid.json").exists())


if __name__ == "__main__":
    unittest.main()
