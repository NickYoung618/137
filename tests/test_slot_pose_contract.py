from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from PIL import Image

try:
    import jsonschema
except ImportError:
    jsonschema = None

from algorithms.slot_pose.contract import (
    ERROR_CODES, build_result, effective_config_identity, effective_config_sha256,
    load_config, signed_relative_angle, validate_result,
)
from algorithms.slot_pose.single_groove_pose import (
    DEFAULT_SINGLE_GROOVE_POSE_CONFIG_V3,
    build_closed_loop_guidance,
)


def minimal_config() -> dict:
    digest = "0" * 64
    return {
        "schema_version": "slot-pose-config/1", "project": "137-housing-slot-pose", "config_id": "test",
        "legacy_asset": {
            "source_path": "/read-only/main.py", "source_sha256": digest,
            "annotation_path": "/read-only/annotation.json", "annotation_sha256": digest,
            "reference_path": "/read-only/reference.bmp", "reference_sha256": digest,
        },
        "pose": {
            "reference_frame": "IMAGE", "target_frame": "MACHINE",
            "mechanical_zero_image_deg": 0.0, "positive_direction": "cw", "conventions_confirmed": True,
            "target_semantics_confirmed": True,
            "valid_range_deg": [-180, 179.999], "production_plc_mapping_confirmed": False,
        },
        "detector": {},
    }


def minimal_single_groove_config() -> dict:
    config = minimal_config()
    config["detector"] = {
        "diagnostic_mode": "single_real_groove",
        "min_notch_prominence": 1.0,
        "min_polar_score": 1.0,
        "max_rotation_disagreement_deg": 5.0,
        "min_scale": 0.8,
        "max_scale": 1.2,
        "profile": {
            "n_angles": 360, "n_radii": 10, "shell_width_px": 30.0,
            "smoothing_window": 7, "mad_multiplier": 3.0, "min_prominence": 12.0,
            "min_half_width_deg": 1.0, "max_half_width_deg": 30.0,
        },
        "single_groove_pose": DEFAULT_SINGLE_GROOVE_POSE_CONFIG_V3,
    }
    return config


class SlotPoseContractTests(unittest.TestCase):
    def test_config_relative_assets_resolve_from_config_not_cwd(self) -> None:
        with tempfile.TemporaryDirectory() as temporary, tempfile.TemporaryDirectory() as elsewhere:
            root = Path(temporary)
            config = minimal_config()
            config["legacy_asset"].update({
                "path_mode": "config_relative_v1",
                "source_path": "assets/core.py",
                "annotation_path": "assets/annotation.json",
                "reference_path": "assets/reference.bmp",
            })
            path = root / "配置 目录" / "config.json"
            path.parent.mkdir()
            path.write_text(json.dumps(config), encoding="utf-8")
            prior = Path.cwd()
            try:
                os.chdir(elsewhere)
                loaded = load_config(path)
            finally:
                os.chdir(prior)
            for field, name in (
                ("source_path", "core.py"),
                ("annotation_path", "annotation.json"),
                ("reference_path", "reference.bmp"),
            ):
                self.assertEqual(path.parent / "assets" / name, Path(loaded["legacy_asset"][field]))

    def test_config_relative_assets_reject_absolute_traversal_windows_and_symlink_escape(self) -> None:
        with tempfile.TemporaryDirectory() as temporary, tempfile.TemporaryDirectory() as outside:
            root = Path(temporary)
            path = root / "config.json"
            base = minimal_config()
            base["legacy_asset"]["path_mode"] = "config_relative_v1"
            invalid = ["/tmp/annotation.json", "../annotation.json", "assets/../annotation.json", r"C:\\asset.json", r"\\server\\asset.json"]
            for value in invalid:
                with self.subTest(value=value):
                    config = json.loads(json.dumps(base))
                    config["legacy_asset"]["annotation_path"] = value
                    path.write_text(json.dumps(config), encoding="utf-8")
                    with self.assertRaisesRegex(ValueError, "annotation_path"):
                        load_config(path)
            (root / "escape").symlink_to(Path(outside), target_is_directory=True)
            config = json.loads(json.dumps(base))
            config["legacy_asset"]["annotation_path"] = "escape/annotation.json"
            path.write_text(json.dumps(config), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "outside"):
                load_config(path)

    def test_omitted_path_mode_preserves_legacy_path_values_and_effective_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "config.json"
            config = minimal_config()
            path.write_text(json.dumps(config), encoding="utf-8")
            loaded = load_config(path)
            self.assertEqual("legacy", loaded["legacy_asset"]["path_mode"])
            self.assertEqual(config["legacy_asset"]["annotation_path"], loaded["legacy_asset"]["annotation_path"])
            portable = json.loads(json.dumps(config))
            portable["legacy_asset"]["path_mode"] = "config_relative_v1"
            portable["legacy_asset"]["source_path"] = "assets/core.py"
            portable["legacy_asset"]["annotation_path"] = "assets/annotation.json"
            portable["legacy_asset"]["reference_path"] = "assets/reference.bmp"
            portable_path = Path(temporary) / "portable.json"
            portable_path.write_text(json.dumps(portable), encoding="utf-8")
            self.assertEqual(
                effective_config_identity(loaded),
                effective_config_identity(load_config(portable_path)),
            )

    def test_028_recovery_configs_are_strict_default_off_and_dependency_gated(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "config.json"
            config = minimal_single_groove_config()
            config["detector"]["ambiguity_resolution"] = {"enabled": True}
            config["detector"]["sidewall_source_consistency"] = {"enabled": True}
            config["detector"]["groove_refinement"] = {
                "threshold_version": "groove-sidewall-subpixel-v2",
                "wall_edge_family": {"enabled": True},
            }
            config["detector"]["groove_recognition_recovery"] = {"enabled": True}
            config["detector"]["groove_shadow_source_discrimination"] = {
                "schema_version": "groove-shadow-source-discrimination/2",
                "enabled": True,
                "strategy_version": "fixture-role-u-contour-source-evidence/2",
            }
            config["detector"]["source_consistency_adjudication"] = {
                "schema_version": "source-consistency-adjudication/2",
                "enabled": True,
                "strategy_version": "locked-noncontrast-gates-v2",
                "development_only": True,
            }
            path.write_text(json.dumps(config), encoding="utf-8")
            loaded = load_config(path)
            self.assertTrue(loaded["detector"]["groove_recognition_recovery"]["enabled"])
            self.assertTrue(loaded["detector"]["groove_refinement"]["wall_edge_family"]["enabled"])
            self.assertEqual(
                "source-consistency-adjudication/2",
                loaded["detector"]["source_consistency_adjudication"]["schema_version"],
            )

            config["detector"]["groove_recognition_recovery"]["unsafe_threshold"] = 0.1
            path.write_text(json.dumps(config), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "unsupported fields"):
                load_config(path)

    def test_groove_shadow_source_discrimination_is_default_off_and_strictly_gated(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            omitted = minimal_single_groove_config()
            omitted_path = root / "omitted.json"
            omitted_path.write_text(json.dumps(omitted), encoding="utf-8")
            loaded = load_config(omitted_path)
            self.assertNotIn("groove_shadow_source_discrimination", loaded["detector"])

            unsupported = minimal_single_groove_config()
            unsupported["detector"]["groove_shadow_source_discrimination"] = {
                "enabled": False, "shadow_threshold": 0.5,
            }
            unsupported_path = root / "unsupported.json"
            unsupported_path.write_text(json.dumps(unsupported), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "unsupported fields"):
                load_config(unsupported_path)

            enabled = minimal_single_groove_config()
            enabled["detector"]["groove_shadow_source_discrimination"] = {"enabled": True}
            enabled_path = root / "enabled.json"
            enabled_path.write_text(json.dumps(enabled), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "requires ambiguity_resolution"):
                load_config(enabled_path)

            enabled["detector"]["ambiguity_resolution"] = {"enabled": True}
            enabled_path.write_text(json.dumps(enabled), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "requires sidewall_source_consistency"):
                load_config(enabled_path)

            enabled["detector"]["sidewall_source_consistency"] = {"enabled": True}
            enabled_path.write_text(json.dumps(enabled), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "requires groove refinement v2"):
                load_config(enabled_path)

            enabled["detector"]["groove_refinement"] = {
                "threshold_version": "groove-sidewall-subpixel-v2"
            }
            enabled_path.write_text(json.dumps(enabled), encoding="utf-8")
            configured = load_config(enabled_path)
            self.assertTrue(configured["detector"]["groove_shadow_source_discrimination"]["enabled"])

            enabled["detector"]["groove_shadow_source_discrimination"] = {
                "schema_version": "groove-shadow-source-discrimination/2",
                "enabled": True,
                "strategy_version": "fixture-role-u-contour-source-evidence/2",
            }
            enabled_path.write_text(json.dumps(enabled), encoding="utf-8")
            configured_v2 = load_config(enabled_path)
            self.assertEqual(
                "groove-shadow-source-discrimination/2",
                configured_v2["detector"]["groove_shadow_source_discrimination"]["schema_version"],
            )

            enabled["detector"]["source_consistency_adjudication"] = {"enabled": True}
            enabled_path.write_text(json.dumps(enabled), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "forbids source_consistency_adjudication"):
                load_config(enabled_path)

    def test_bundled_core_source_does_not_require_external_source_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "config.json"
            config = minimal_config()
            config["legacy_asset"].pop("source_path")
            config["legacy_asset"].update({
                "source_mode": "bundled_module",
                "bundled_module": "algorithms.end_face.core",
                "upstream_source_sha256": "1" * 64,
            })
            path.write_text(json.dumps(config), encoding="utf-8")
            loaded = load_config(path)
            self.assertEqual("bundled_module", loaded["legacy_asset"]["source_mode"])
            self.assertNotIn("source_path", loaded["legacy_asset"])

    def test_legacy_external_source_still_requires_source_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "config.json"
            config = minimal_config()
            config["legacy_asset"].pop("source_path")
            path.write_text(json.dumps(config), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "source_path"):
                load_config(path)

    def test_bundled_core_module_identity_is_fixed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "config.json"
            config = minimal_config()
            config["legacy_asset"].update({
                "source_mode": "bundled_module",
                "bundled_module": "another.project.module",
                "upstream_source_sha256": "1" * 64,
            })
            path.write_text(json.dumps(config), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "bundled_module"):
                load_config(path)

    def test_fixture_shadow_extensions_default_off_and_are_path_identity_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "config.json"
            path.write_text(json.dumps(minimal_single_groove_config()), encoding="utf-8")
            loaded = load_config(path)
            fixture = loaded["detector"]["fixture_shadow_model"]
            source = loaded["detector"]["sidewall_source_consistency"]
            self.assertFalse(fixture["enabled"])
            self.assertFalse(fixture["enable_overlap_decomposition"])
            self.assertFalse(source["enabled"])
            identity = effective_config_identity(loaded)
            self.assertIn("fixture_shadow_model", identity["detector"])
            self.assertIn("sidewall_source_consistency", identity["detector"])

    def test_fixture_shadow_extensions_are_restricted_and_strictly_validated(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            legacy = minimal_config()
            legacy["detector"]["fixture_shadow_model"] = {"enabled": True}
            path = root / "legacy.json"
            path.write_text(json.dumps(legacy), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "single_real_groove"):
                load_config(path)

            single = minimal_single_groove_config()
            single["detector"]["sidewall_source_consistency"] = {
                "enabled": True,
                "max_contrast_normalized_difference": 1.5,
            }
            path = root / "invalid.json"
            path.write_text(json.dumps(single), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "max_contrast"):
                load_config(path)

    def test_source_consistency_requires_refinement_v2_when_enabled(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "config.json"
            config = minimal_single_groove_config()
            config["detector"]["sidewall_source_consistency"] = {"enabled": True}
            path.write_text(json.dumps(config), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "refinement v2"):
                load_config(path)

    def test_source_adjudication_is_explicit_default_off_and_strictly_gated(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            omitted = minimal_single_groove_config()
            omitted_path = root / "omitted.json"
            omitted_path.write_text(json.dumps(omitted), encoding="utf-8")
            loaded = load_config(omitted_path)
            self.assertNotIn("source_consistency_adjudication", loaded["detector"])

            legacy = minimal_config()
            legacy["detector"]["source_consistency_adjudication"] = {"enabled": True}
            legacy_path = root / "legacy.json"
            legacy_path.write_text(json.dumps(legacy), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "single_real_groove"):
                load_config(legacy_path)

            without_source = minimal_single_groove_config()
            without_source["detector"]["groove_refinement"] = {
                "threshold_version": "groove-sidewall-subpixel-v2",
            }
            without_source["detector"]["source_consistency_adjudication"] = {"enabled": True}
            without_source_path = root / "without-source.json"
            without_source_path.write_text(json.dumps(without_source), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "requires sidewall_source_consistency"):
                load_config(without_source_path)

            valid = minimal_single_groove_config()
            valid["detector"]["groove_refinement"] = {
                "threshold_version": "groove-sidewall-subpixel-v2",
            }
            valid["detector"]["sidewall_source_consistency"] = {"enabled": True}
            valid["detector"]["source_consistency_adjudication"] = {"enabled": True}
            valid_path = root / "valid.json"
            valid_path.write_text(json.dumps(valid), encoding="utf-8")
            configured = load_config(valid_path)
            adjudication = configured["detector"]["source_consistency_adjudication"]
            self.assertTrue(adjudication["enabled"])
            self.assertTrue(adjudication["development_only"])
            self.assertEqual(0.05, adjudication["max_endpoint_structure_difference"])
            self.assertIn("source_consistency_adjudication", effective_config_identity(configured)["detector"])

            for mutation, message in (
                ({"unexpected": True}, "unknown fields"),
                ({"development_only": False}, "development_only"),
                ({"max_endpoint_structure_difference": float("nan")}, "must be in"),
            ):
                invalid = json.loads(json.dumps(valid))
                invalid["detector"]["source_consistency_adjudication"].update(mutation)
                invalid_path = root / f"invalid-{next(iter(mutation))}.json"
                invalid_path.write_text(json.dumps(invalid), encoding="utf-8")
                with self.subTest(mutation=mutation), self.assertRaisesRegex(ValueError, message):
                    load_config(invalid_path)

    def test_local_second_wall_is_explicit_default_off_and_strictly_gated(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            omitted = minimal_single_groove_config()
            omitted_path = root / "omitted.json"
            omitted_path.write_text(json.dumps(omitted), encoding="utf-8")
            loaded = load_config(omitted_path)
            self.assertNotIn("local_second_wall_diagnostic", loaded["detector"])

            enabled = minimal_single_groove_config()
            enabled["detector"]["local_second_wall_diagnostic"] = {"enabled": True}
            enabled_path = root / "without-source.json"
            enabled_path.write_text(json.dumps(enabled), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "requires sidewall_source_consistency"):
                load_config(enabled_path)

            enabled["detector"]["sidewall_source_consistency"] = {"enabled": True}
            enabled["detector"]["groove_refinement"] = {
                "threshold_version": "groove-sidewall-subpixel-v2",
            }
            valid_path = root / "valid.json"
            valid_path.write_text(json.dumps(enabled), encoding="utf-8")
            configured = load_config(valid_path)
            self.assertTrue(configured["detector"]["local_second_wall_diagnostic"]["enabled"])

            enabled["detector"]["local_second_wall_diagnostic"]["unexpected"] = True
            invalid_path = root / "invalid.json"
            invalid_path.write_text(json.dumps(enabled), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "unknown fields"):
                load_config(invalid_path)

    def test_effective_config_hash_ignores_paths_and_explicit_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            omitted = minimal_config()
            omitted["config_id"] = "omitted"
            omitted["pose"].pop("target_semantics_confirmed")
            explicit = minimal_config()
            explicit["config_id"] = "explicit"
            explicit["pose"]["target_semantics_confirmed"] = False
            explicit["detector"]["diagnostic_mode"] = "legacy_single_notch"
            explicit["legacy_asset"]["source_path"] = "/different/machine/main.py"
            paths = []
            for name, config in (("omitted.json", omitted), ("explicit.json", explicit)):
                path = root / name
                path.write_text(json.dumps(config, indent=2 if name.startswith("explicit") else None), encoding="utf-8")
                paths.append(path)
            loaded = [load_config(path) for path in paths]
            self.assertNotEqual(paths[0].read_bytes(), paths[1].read_bytes())
            self.assertEqual(effective_config_identity(loaded[0]), effective_config_identity(loaded[1]))
            self.assertEqual(effective_config_sha256(loaded[0]), effective_config_sha256(loaded[1]))
            self.assertNotIn("/different/machine", json.dumps(effective_config_identity(loaded[1])))

    def test_v3_validity_is_image_guidance_not_plc_authority(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            image = root / "a.png"
            Image.new("L", (8, 8), 1).save(image)
            config = minimal_config()
            config["pose"].update({
                "conventions_confirmed": False,
                "target_semantics_confirmed": True,
                "production_plc_mapping_confirmed": False,
            })
            config["detector"] = {
                "diagnostic_mode": "single_real_groove",
                "single_groove_pose": DEFAULT_SINGLE_GROOVE_POSE_CONFIG_V3,
            }
            config_path = root / "config.json"
            config_path.write_text(json.dumps(config), encoding="utf-8")
            guidance = build_closed_loop_guidance(
                DEFAULT_SINGLE_GROOVE_POSE_CONFIG_V3["target"],
                {
                    "measuredFromPositiveYClockwiseDeg": 22.834,
                    "position": {"requiredRegionPassed": False},
                },
                geometry_valid=True,
                plc_mapping_confirmed=False,
            )
            diagnostics = {"singleGroovePose": {"guidance": guidance}}
            payload = build_result(
                image, config_path, config, "v3:adjust", diagnostics,
                angle_deg=62.166, confidence=0.9,
            )
            validate_result(payload)
            if jsonschema is not None:
                schema = json.loads(
                    (Path(__file__).parents[1] / "contracts" / "slot-pose-result.schema.json")
                    .read_text(encoding="utf-8")
                )
                jsonschema.Draft202012Validator(schema).validate(payload)
            self.assertEqual("slot-pose-result/3", payload["schemaVersion"])
            self.assertTrue(payload["result"]["valid"])
            self.assertEqual("DETECTED_NEEDS_ADJUSTMENT", payload["result"]["guidanceStatus"])
            self.assertAlmostEqual(62.166, payload["result"]["imageFrameCorrectionDeg"])
            self.assertEqual("CLOCKWISE", payload["result"]["rotationDirection"])
            self.assertEqual("BLOCKED_MAPPING_UNCONFIRMED", payload["result"]["plcExecutionStatus"])
            self.assertIsNone(payload["result"]["mechanicalCorrectionDeg"])
            self.assertIsNone(payload["result"]["plcCommand"])
            self.assertIsNone(payload["error"])

    def test_v3_detection_failure_clears_all_guidance_values(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            image = root / "a.png"
            Image.new("L", (8, 8), 1).save(image)
            config = minimal_config()
            config["detector"] = {
                "diagnostic_mode": "single_real_groove",
                "single_groove_pose": DEFAULT_SINGLE_GROOVE_POSE_CONFIG_V3,
            }
            config_path = root / "config.json"
            config_path.write_text(json.dumps(config), encoding="utf-8")
            payload = build_result(
                image, config_path, config, "v3:failed", {},
                error_code="GROOVE_RECOGNITION_FAILED",
                error_stage="groove_recognition",
            )
            validate_result(payload)
            self.assertFalse(payload["result"]["valid"])
            self.assertEqual("DETECTION_FAILED", payload["result"]["detectionStatus"])
            self.assertEqual("NOT_AVAILABLE", payload["result"]["guidanceStatus"])
            self.assertIsNone(payload["result"]["imageFrameCorrectionDeg"])
            self.assertIsNone(payload["result"]["rotationDirection"])

    def test_failure_is_fail_closed_and_traceable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            image = root / "a_face.bmp"
            Image.new("L", (16, 12), 100).save(image)
            config_path = root / "config.json"
            config = minimal_config()
            config_path.write_text(json.dumps(config), encoding="utf-8")
            payload = build_result(
                image, config_path, config, "task-1", {"candidateAzimuthImageDeg": 42.0},
                error_code="POSE_CONVENTION_UNCONFIRMED", error_message="pending", error_stage="pose_mapping",
            )
            validate_result(payload)
            self.assertFalse(payload["result"]["valid"])
            self.assertIsNone(payload["result"]["signedRelativeRotationDeg"])
            self.assertIsNone(payload["result"]["confidence"])
            self.assertEqual("failed", payload["technicalStatus"])
            self.assertEqual("POSE_CONVENTION_UNCONFIRMED", payload["error"]["code"])
            self.assertIn("sourceSha256", payload["algorithm"]["assets"])
            self.assertNotIn("plc", payload)

    def test_valid_result_and_angle_sign(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            image = root / "a.png"
            Image.new("L", (8, 8), 1).save(image)
            config = minimal_config()
            config_path = root / "config.json"
            config_path.write_text(json.dumps(config), encoding="utf-8")
            payload = build_result(image, config_path, config, "task-2", {}, angle_deg=-30.0, confidence=0.8)
            validate_result(payload)
            self.assertTrue(payload["result"]["valid"])
            self.assertEqual(30.0, signed_relative_angle(30.0, 0.0, "cw"))
            self.assertEqual(-30.0, signed_relative_angle(30.0, 0.0, "ccw"))
            self.assertEqual(-2.0, signed_relative_angle(179.0, -179.0, "cw"))

    def test_invalid_payload_cannot_reuse_old_angle(self) -> None:
        with self.assertRaises(ValueError):
            validate_result({
                "schemaVersion": "slot-pose-result/2", "taskId": "x", "createdAtUtc": "now",
                "result": {"valid": False, "signedRelativeRotationDeg": 12.0, "confidence": None, "unit": "deg"},
                "technicalStatus": "failed", "error": {"code": "QUALITY_REJECTED", "stage": "q"},
            })

    def test_stable_failure_inventory(self) -> None:
        self.assertTrue({
            "INPUT_INVALID", "ASSET_MISMATCH", "FACE_NOT_FOUND", "SLOT_NOT_FOUND",
            "SLOT_ROTATION_INCONSISTENT", "QUALITY_REJECTED", "POSE_CONVENTION_UNCONFIRMED",
            "ANGLE_OUT_OF_RANGE",
            "SLOT_PAIR_NOT_FOUND", "SLOT_PAIR_AMBIGUOUS", "RING_TRUNCATED",
            "TARGET_SEMANTICS_UNCONFIRMED",
            "ROLE_ASSIGNMENT_FAILED", "ROLE_ASSIGNMENT_AMBIGUOUS",
            "GROOVE_RECOGNITION_FAILED", "GROOVE_RECOGNITION_AMBIGUOUS",
            "GROOVE_SOURCE_INCONSISTENT", "FIXTURE_SHADOW_TEMPLATE_INCOMPLETE",
            "PHYSICAL_OUTER_CIRCLE_FAILED", "HOUSING_CIRCLE_NOT_FOUND", "HOUSING_CIRCLE_AMBIGUOUS",
            "DATUM_DEFINITION_UNCONFIRMED", "FEATURE_MAPPING_UNCONFIRMED", "OUTPUT_PURPOSE_UNCONFIRMED",
            "PLC_MAPPING_UNCONFIRMED", "GROOVE_REFINEMENT_FAILED",
        }.issubset(ERROR_CODES))

    def test_old_config_defaults_to_legacy_but_unconfirmed_target(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "config.json"
            config = minimal_config()
            config["pose"].pop("target_semantics_confirmed")
            path.write_text(json.dumps(config), encoding="utf-8")
            loaded = load_config(path)
            self.assertEqual("legacy_single_notch", loaded["detector"]["diagnostic_mode"])
            self.assertFalse(loaded["pose"]["target_semantics_confirmed"])

    def test_invalid_diagnostic_mode_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "config.json"
            config = minimal_config()
            config["detector"]["diagnostic_mode"] = "automatic_guess"
            path.write_text(json.dumps(config), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "diagnostic_mode"):
                load_config(path)

    def test_disabled_full_frame_locator_is_strictly_validated_in_legacy_mode(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "config.json"
            config = minimal_config()
            config["detector"]["full_frame_circle_locator"] = {
                "schema_version": "full-frame-circle-locator/1", "enabled": False,
                "unexpected_typo": True,
            }
            path.write_text(json.dumps(config), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "unknown fields"):
                load_config(path)

    def test_normalized_face_search_roi_is_optional_and_strictly_validated(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "config.json"
            config = minimal_config()
            config["detector"]["face_search_roi_normalized"] = [0.1, 0.0, 0.8, 1.0]
            path.write_text(json.dumps(config), encoding="utf-8")
            self.assertEqual([0.1, 0.0, 0.8, 1.0], load_config(path)["detector"]["face_search_roi_normalized"])
            for invalid in ([0.8, 0.0, 0.1, 1.0], [-0.1, 0.0, 0.8, 1.0], [0.0, 0.0, 1.1, 1.0]):
                config["detector"]["face_search_roi_normalized"] = invalid
                path.write_text(json.dumps(config), encoding="utf-8")
                with self.subTest(invalid=invalid), self.assertRaisesRegex(ValueError, "face_search_roi_normalized"):
                    load_config(path)

    def test_multi_role_config_gets_safe_groove_defaults_and_rejects_invalid_thresholds(self) -> None:
        from tools.generate_synthetic_multi_notches import build_dataset

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            try:
                built = build_dataset(root, 137)
            except FileNotFoundError as exc:
                self.skipTest(f"historical source unavailable: {exc}")
            path = Path(built["config"])
            config = json.loads(path.read_text(encoding="utf-8"))
            config["detector"].pop("groove_recognition", None)
            path.write_text(json.dumps(config), encoding="utf-8")
            loaded = load_config(path)
            self.assertEqual("groove-geometry-v1", loaded["detector"]["groove_recognition"]["threshold_version"])
            self.assertEqual(
                "gyj-outer-boundary+slot-quality-v2",
                loaded["detector"]["physical_outer_circle"]["threshold_version"],
            )
            config["detector"]["groove_recognition"] = {"min_radial_depth_ratio": 2.0}
            path.write_text(json.dumps(config), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "min_radial_depth_ratio"):
                load_config(path)
            config["detector"]["groove_recognition"] = {}
            config["detector"]["physical_outer_circle"] = {"min_angular_coverage": 2.0}
            path.write_text(json.dumps(config), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "min_angular_coverage"):
                load_config(path)

    def test_valid_result_requires_confirmed_target_semantics(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            image = root / "a.png"
            Image.new("L", (8, 8), 1).save(image)
            config = minimal_config()
            config["pose"]["target_semantics_confirmed"] = False
            config_path = root / "config.json"
            config_path.write_text(json.dumps(config), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "target semantics"):
                build_result(image, config_path, config, "task", {}, angle_deg=1.0, confidence=0.8)

    def test_full_frame_locator_is_strict_single_mode_and_mutually_exclusive_with_roi(self) -> None:
        from tools.generate_synthetic_multi_notches import build_dataset

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            try:
                built = build_dataset(root, 137)
            except FileNotFoundError as exc:
                self.skipTest(f"historical source unavailable: {exc}")
            path = Path(built["config"])
            config = json.loads(path.read_text(encoding="utf-8"))
            config["detector"]["diagnostic_mode"] = "single_real_groove"
            from algorithms.slot_pose.single_groove_pose import DEFAULT_SINGLE_GROOVE_POSE_CONFIG
            config["detector"]["single_groove_pose"] = DEFAULT_SINGLE_GROOVE_POSE_CONFIG
            config["detector"]["full_frame_circle_locator"] = {
                "enabled": True,
                "schema_version": "full-frame-circle-locator/1",
            }
            path.write_text(json.dumps(config), encoding="utf-8")
            loaded = load_config(path)
            self.assertTrue(loaded["detector"]["full_frame_circle_locator"]["enabled"])
            config["detector"]["face_search_roi_normalized"] = [0.0, 0.0, 0.8, 1.0]
            path.write_text(json.dumps(config), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "mutually exclusive"):
                load_config(path)
            config["detector"].pop("face_search_roi_normalized")
            config["detector"]["diagnostic_mode"] = "multi_notch_roles"
            path.write_text(json.dumps(config), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "single_real_groove"):
                load_config(path)

    def test_v2_groove_refinement_consensus_config_is_strict_and_finite(self) -> None:
        from tools.generate_synthetic_multi_notches import build_dataset

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            try:
                built = build_dataset(root, 137)
            except FileNotFoundError as exc:
                self.skipTest(f"historical source unavailable: {exc}")
            path = Path(built["config"])
            config = json.loads(path.read_text(encoding="utf-8"))
            config["detector"]["diagnostic_mode"] = "single_real_groove"
            from algorithms.slot_pose.single_groove_pose import DEFAULT_SINGLE_GROOVE_POSE_CONFIG_V2
            config["detector"]["single_groove_pose"] = DEFAULT_SINGLE_GROOVE_POSE_CONFIG_V2
            config["detector"]["groove_refinement"] = {
                "threshold_version": "groove-sidewall-subpixel-v2",
            }
            path.write_text(json.dumps(config), encoding="utf-8")
            loaded = load_config(path)
            refinement = loaded["detector"]["groove_refinement"]
            self.assertEqual("groove-sidewall-subpixel-v2", refinement["threshold_version"])
            self.assertEqual(0.5, refinement["line_consensus_min_inlier_ratio"])
            self.assertEqual(0.7, refinement["line_consensus_min_span_ratio"])

            invalid_cases = {
                "threshold_version": "unknown-refiner",
                "line_consensus_min_inlier_ratio": float("nan"),
                "line_consensus_min_span_ratio": 1.1,
                "line_consensus_min_pair_separation_ratio": 0.0,
                "line_consensus_model_merge_deg": -1.0,
                "line_consensus_min_support_margin": 0,
                "line_consensus_max_refit_hypotheses": 1,
            }
            for key, value in invalid_cases.items():
                config["detector"]["groove_refinement"] = {
                    "threshold_version": "groove-sidewall-subpixel-v2", key: value,
                }
                path.write_text(json.dumps(config), encoding="utf-8")
                with self.subTest(key=key), self.assertRaisesRegex(ValueError, "groove_refinement"):
                    load_config(path)

    def test_robustness_extensions_default_off_and_are_path_independent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "config.json"
            config = minimal_single_groove_config()
            path.write_text(json.dumps(config), encoding="utf-8")
            loaded = load_config(path)
            dark = loaded["detector"]["dark_candidate_robustness"]
            sectors = loaded["detector"]["physical_outer_circle"]["sector_robustness"]
            self.assertEqual("angular-dark-candidate-robustness/1", dark["schema_version"])
            self.assertFalse(dark["enabled"])
            self.assertEqual([0.05, 0.1], dark["quantile_levels"])
            self.assertEqual("physical-circle-sector-robustness/1", sectors["schema_version"])
            self.assertFalse(sectors["enabled"])
            identity = effective_config_identity(loaded)
            self.assertFalse(identity["detector"]["dark_candidate_robustness"]["enabled"])
            self.assertNotIn("/read-only", json.dumps(identity))

    def test_circle_edge_family_selection_defaults_off_and_is_strictly_validated(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "config.json"
            config = minimal_single_groove_config()
            path.write_text(json.dumps(config), encoding="utf-8")
            loaded = load_config(path)
            selection = loaded["detector"]["physical_outer_circle"]["edge_family_selection"]
            self.assertEqual("physical-circle-edge-family-selection/1", selection["schema_version"])
            self.assertFalse(selection["enabled"])
            self.assertEqual(8, selection["max_peaks_per_ray"])
            self.assertEqual(0.95, selection["min_background_persistence_ratio"])
            self.assertEqual(
                "deterministic-three-point-global-circle-v1",
                selection["strategy_version"],
            )
            self.assertIn("edge_family_selection", effective_config_identity(loaded)["detector"]["physical_outer_circle"])

            invalid_cases = [
                {"schema_version": "unknown"},
                {"strategy_version": "unknown-strategy"},
                {"enabled": 1},
                {"max_peaks_per_ray": 0},
                {"min_gradient": float("nan")},
                {"min_separation_px": 0.0},
                {"min_background_persistence_ratio": 1.1},
                {"min_seed_votes": 0},
                {"max_seed_count": 2},
                {"max_hypotheses": 0},
                {"max_families": 0},
                {"refinement_iterations": 0},
                {"assignment_residual_px": -1.0},
                {"min_support_ratio": 1.1},
                {"min_angular_coverage": 0.0},
                {"max_preliminary_residual_p95_px": 0.0},
                {"dedup_center_px": 0.0},
                {"dedup_radius_px": 0.0},
                {"min_support_overlap_ratio": -0.1},
                {"min_assignment_overlap_ratio": 1.1},
                {"unexpected": True},
            ]
            for extension in invalid_cases:
                config = minimal_single_groove_config()
                config["detector"]["physical_outer_circle"] = {
                    "edge_family_selection": extension,
                }
                path.write_text(json.dumps(config), encoding="utf-8")
                with self.subTest(extension=extension), self.assertRaisesRegex(
                    ValueError, "edge_family_selection",
                ):
                    load_config(path)

    def test_robustness_extensions_reject_invalid_or_unsafe_combinations(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "config.json"
            invalid_dark = [
                {"schema_version": "unknown", "enabled": False},
                {"enabled": True, "quantile_levels": [0.1, 0.1]},
                {"enabled": True, "quantile_levels": [0.0]},
                {"enabled": True, "quantile_levels": [0.1, 0.2], "max_hypotheses": 2},
                {"enabled": True, "dedup_center_deg": float("nan")},
            ]
            for extension in invalid_dark:
                config = minimal_single_groove_config()
                config["detector"]["dark_candidate_robustness"] = extension
                path.write_text(json.dumps(config), encoding="utf-8")
                with self.subTest(dark=extension), self.assertRaisesRegex(
                    ValueError, "dark_candidate_robustness",
                ):
                    load_config(path)

            invalid_sectors = [
                {"schema_version": "unknown", "enabled": False},
                {"enabled": True, "sector_bin_count": 4, "max_excluded_sector_count": 4},
                {"enabled": True, "sector_bin_count": 36, "max_excluded_sector_count": 4,
                 "min_retained_angular_coverage": 0.95},
                {"enabled": True, "max_refit_center_delta_px": float("inf")},
                {"enabled": 1},
            ]
            for extension in invalid_sectors:
                config = minimal_single_groove_config()
                config["detector"]["physical_outer_circle"] = {"sector_robustness": extension}
                path.write_text(json.dumps(config), encoding="utf-8")
                with self.subTest(sector=extension), self.assertRaisesRegex(
                    ValueError, "sector_robustness",
                ):
                    load_config(path)

    def test_robustness_cannot_be_enabled_outside_single_real_groove(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "config.json"
            config = minimal_config()
            config["detector"]["dark_candidate_robustness"] = {"enabled": True}
            path.write_text(json.dumps(config), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "single_real_groove"):
                load_config(path)
            config = minimal_config()
            config["detector"].update({
                "diagnostic_mode": "multi_notch_roles",
                "profile": minimal_single_groove_config()["detector"]["profile"],
                "role_assignment": {
                    "datum_definition": "single_candidate_ray",
                    "assignments": {
                        "datum_primary": {"expected_reference_azimuth_deg": 0.0, "max_deviation_deg": 20.0},
                        "target_left": {"expected_reference_azimuth_deg": 90.0, "max_deviation_deg": 20.0},
                    },
                    "min_score_margin": 0.1,
                    "max_opposition_error_deg": 20.0,
                },
                "physical_outer_circle": {"sector_robustness": {"enabled": True}},
            })
            path.write_text(json.dumps(config), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "single_real_groove"):
                load_config(path)

    @unittest.skipIf(jsonschema is None, "jsonschema is installed by the explicit Schema gate")
    def test_robustness_extensions_match_config_schema(self) -> None:
        schema = json.loads(
            (Path(__file__).resolve().parents[1] / "contracts/slot-pose-config.schema.json")
            .read_text(encoding="utf-8")
        )
        jsonschema.Draft202012Validator.check_schema(schema)
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "config.json"
            path.write_text(json.dumps(minimal_single_groove_config()), encoding="utf-8")
            loaded = load_config(path)
        jsonschema.validate(loaded, schema)

    def test_experimental_config_materializer_never_mutates_base_or_legacy_mode(self) -> None:
        from tools.prepare_slot_pose_robustness_config import prepare

        base = minimal_single_groove_config()
        original = json.loads(json.dumps(base))
        experimental = prepare(base)
        self.assertEqual(original, base)
        self.assertTrue(experimental["detector"]["dark_candidate_robustness"]["enabled"])
        self.assertTrue(
            experimental["detector"]["physical_outer_circle"]["sector_robustness"]["enabled"]
        )
        self.assertTrue(experimental["config_id"].endswith("-019-experimental"))
        legacy = minimal_config()
        with self.assertRaisesRegex(ValueError, "single_real_groove"):
            prepare(legacy)


if __name__ == "__main__":
    unittest.main()
