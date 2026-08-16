from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

try:
    import jsonschema
except ImportError:
    jsonschema = None

from algorithms.slot_pose.paired_capture import (
    DEFAULT_PAIRED_CONFIG,
    build_paired_result,
    extract_frame_candidates,
    load_paired_config,
    validate_paired_manifest,
    wrap_180,
    wrap_360,
)
from tools.run_paired_slot_pose import run_paired


def candidate(
    candidate_id: str,
    angle: float,
    *,
    accepted: bool = True,
    half_width: float = 6.0,
    prominence: float = 140.0,
    deficit: float = 1400.0,
) -> dict:
    return {
        "candidateId": candidate_id,
        "centerDeg": angle,
        "halfWidthDeg": half_width,
        "prominence": prominence,
        "deficitArea": deficit,
        "accepted": accepted,
        "grooveScore": 0.8 if accepted else 0.2,
        "rejectionReasons": [] if accepted else ["fixture_like"],
    }


def frame(sha_char: str, items: list[dict], *, valid: bool = False) -> dict:
    raw = [{key: value for key, value in item.items() if key not in {"accepted", "grooveScore", "rejectionReasons"}} for item in items]
    assessments = [{
        "candidateId": item["candidateId"],
        "accepted": item["accepted"],
        "grooveScore": item["grooveScore"],
        "rejectionReasons": item["rejectionReasons"],
    } for item in items]
    accepted = [dict(item) for item in items if item["accepted"]]
    diagnostics = {
        "rawCandidates": raw,
        "grooveRecognition": {"assessments": assessments},
        "grooveCandidates": accepted,
    }
    if len(accepted) == 1:
        diagnostics["singleGroovePose"] = {
            "geometryValid": True,
            "role": {"candidateId": accepted[0]["candidateId"]},
            "imageMeasurement": {
                "profileAzimuthXRightClockwiseDeg": accepted[0]["centerDeg"],
            },
        }
    return {
        "schemaVersion": "slot-pose-result/3",
        "image": {"sha256": sha_char * 64},
        "result": {"valid": valid},
        "error": None if valid else {"code": "GROOVE_RECOGNITION_FAILED"},
        "diagnostics": diagnostics,
    }


def pair(
    *,
    status: str = "CONFIRMED",
    rotation: float | None = 60.0,
    direction: str | None = "CLOCKWISE",
    tolerance: float | None = 1.0,
) -> dict:
    return {
        "sampleId": "normal:part-101",
        "pairId": "normal:part-101:pair-001",
        "rotation": {
            "parameterStatus": status,
            "nominalRotationDeg": rotation,
            "rotationDirection": direction,
            "rotationToleranceDeg": tolerance,
            "conventionId": "image-x-right-y-down-clockwise/1",
        },
        "captures": [
            {"captureIndex": 1, "relativePath": "A2/1.bmp", "imageSha256": "a" * 64},
            {"captureIndex": 2, "relativePath": "A2/2.bmp", "imageSha256": "b" * 64},
        ],
    }


def enabled_config(**updates: object) -> dict:
    config = json.loads(json.dumps(DEFAULT_PAIRED_CONFIG))
    config["enabled"] = True
    config.update(updates)
    return config


class PairedCaptureContractTests(unittest.TestCase):
    def test_angle_wrapping_is_deterministic(self) -> None:
        self.assertEqual(1.0, wrap_360(361.0))
        self.assertEqual(359.0, wrap_360(-1.0))
        self.assertEqual(-2.0, wrap_180(358.0))
        self.assertEqual(-180.0, wrap_180(180.0))

    def test_manifest_requires_same_sample_exact_indices_and_confirmed_values(self) -> None:
        manifest = {"schemaVersion": "paired-capture-manifest/1", "datasetId": "x", "pairs": [pair()]}
        validate_paired_manifest(manifest)
        broken = json.loads(json.dumps(manifest))
        broken["pairs"][0]["captures"][1]["captureIndex"] = 1
        with self.assertRaisesRegex(ValueError, "captureIndex"):
            validate_paired_manifest(broken)
        broken = json.loads(json.dumps(manifest))
        broken["pairs"][0]["rotation"]["nominalRotationDeg"] = None
        with self.assertRaisesRegex(ValueError, "CONFIRMED"):
            validate_paired_manifest(broken)
        broken = json.loads(json.dumps(manifest)); broken["pairs"][0]["rotation"]["guess"] = 1
        with self.assertRaisesRegex(ValueError, "unknown"):
            validate_paired_manifest(broken)

    def test_unconfirmed_null_parameters_are_valid_contract(self) -> None:
        manifest = {
            "schemaVersion": "paired-capture-manifest/1", "datasetId": "x",
            "pairs": [pair(status="UNCONFIRMED", rotation=None, direction=None, tolerance=None)],
        }
        validate_paired_manifest(manifest)

    def test_cli_service_correlates_by_sha_and_rejects_missing_frame(self) -> None:
        manifest = {"schemaVersion": "paired-capture-manifest/1", "datasetId": "x", "pairs": [pair()]}
        first = frame("a", [candidate("g1", 20.0)])
        second = frame("b", [candidate("g2", 80.0)])
        outputs = run_paired(manifest, {"a" * 64: first, "b" * 64: second}, enabled_config())
        self.assertEqual(1, len(outputs))
        self.assertTrue(outputs[0]["valid"])
        with self.assertRaisesRegex(ValueError, "missing single-frame"):
            run_paired(manifest, {"a" * 64: first}, enabled_config())

    def test_unknown_single_frame_contract_fails_closed(self) -> None:
        first = frame("a", [candidate("g1", 20.0)])
        first["schemaVersion"] = "unknown/9"
        result = build_paired_result(
            pair(), first, frame("b", [candidate("g2", 80.0)]), enabled_config(),
        )
        self.assertFalse(result["valid"])
        self.assertEqual("PAIR_INPUT_INVALID", result["error"]["code"])

    def test_config_defaults_disabled_and_rejects_unknown_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "config.json"
            path.write_text(json.dumps(DEFAULT_PAIRED_CONFIG), encoding="utf-8")
            self.assertFalse(load_paired_config(path)["enabled"])
            bad = dict(DEFAULT_PAIRED_CONFIG, surprise=True)
            path.write_text(json.dumps(bad), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "unknown"):
                load_paired_config(path)

    @unittest.skipIf(jsonschema is None, "jsonschema is installed by the explicit Schema gate")
    def test_schemas_are_valid(self) -> None:
        root = Path(__file__).resolve().parents[1] / "contracts"
        for name in (
            "paired-capture-manifest.schema.json",
            "paired-slot-pose-config.schema.json",
            "paired-slot-pose-result.schema.json",
        ):
            with self.subTest(name=name):
                schema = json.loads((root / name).read_text(encoding="utf-8"))
                jsonschema.Draft202012Validator.check_schema(schema)
        manifest = {"schemaVersion": "paired-capture-manifest/1", "datasetId": "x", "pairs": [pair()]}
        jsonschema.Draft202012Validator(
            json.loads((root / "paired-capture-manifest.schema.json").read_text(encoding="utf-8"))
        ).validate(manifest)
        jsonschema.Draft202012Validator(
            json.loads((root / "paired-slot-pose-config.schema.json").read_text(encoding="utf-8"))
        ).validate(DEFAULT_PAIRED_CONFIG)
        detected = build_paired_result(
            pair(), frame("a", [candidate("g1", 20.0)]),
            frame("b", [candidate("g2", 80.0)]), enabled_config(),
        )
        jsonschema.Draft202012Validator(
            json.loads((root / "paired-slot-pose-result.schema.json").read_text(encoding="utf-8"))
        ).validate(detected)


class CandidateExtractionTests(unittest.TestCase):
    def test_keeps_raw_accepted_and_rejected_candidates(self) -> None:
        payload = frame("a", [candidate("real", 20.0), candidate("shadow", 31.0, accepted=False)])
        extracted = extract_frame_candidates(payload, 1)
        self.assertEqual(["real", "shadow"], [item["candidateId"] for item in extracted])
        self.assertTrue(extracted[0]["usable"])
        self.assertFalse(extracted[1]["usable"])
        self.assertEqual(["fixture_like"], extracted[1]["rejectionReasons"])

    def test_subpixel_opening_midpoint_overrides_raw_dark_center(self) -> None:
        payload = frame("a", [candidate("real", 30.0)])
        payload["diagnostics"]["grooveCandidates"][0].update({
            "refinedStartDeg": 358.0, "refinedEndDeg": 2.0,
        })
        payload["diagnostics"].pop("singleGroovePose")
        extracted = extract_frame_candidates(payload, 1)
        self.assertEqual(30.0, extracted[0]["rawImageProfileAngleDeg"])
        self.assertEqual(0.0, extracted[0]["imageProfileAngleDeg"])
        self.assertEqual("refined_opening_midpoint", extracted[0]["angleSource"])

    def test_coarse_acceptance_without_subpixel_geometry_is_not_output_usable(self) -> None:
        payload = frame("a", [candidate("real", 30.0)])
        payload["diagnostics"].pop("singleGroovePose")
        extracted = extract_frame_candidates(payload, 1)
        self.assertFalse(extracted[0]["usable"])
        self.assertIn("subpixel_geometry_not_available", extracted[0]["rejectionReasons"])


class PairedCaptureMatchingTests(unittest.TestCase):
    def test_clockwise_rotation_matches_real_and_rejects_fixed_shadows(self) -> None:
        first = frame("a", [
            candidate("shadow-a1", 31.0, accepted=False, deficit=300),
            candidate("real-1", 140.0),
            candidate("shadow-b1", 328.0, accepted=False, deficit=280),
        ])
        second = frame("b", [
            candidate("shadow-a2", 31.0, accepted=False, deficit=300),
            candidate("real-2", 200.0),
            candidate("shadow-b2", 328.0, accepted=False, deficit=280),
        ])
        result = build_paired_result(pair(), first, second, enabled_config())
        self.assertTrue(result["valid"])
        self.assertEqual("real-1", result["selectedMatch"]["firstCandidateId"])
        self.assertEqual("real-2", result["selectedMatch"]["secondCandidateId"])
        self.assertAlmostEqual(0.0, result["selectedMatch"]["angularResidualDeg"])

    def test_counterclockwise_and_wraparound(self) -> None:
        first = frame("a", [candidate("g1", 5.0)])
        second = frame("b", [candidate("g2", 335.0)])
        result = build_paired_result(
            pair(rotation=30.0, direction="COUNTERCLOCKWISE"), first, second, enabled_config(),
        )
        self.assertTrue(result["valid"])
        self.assertAlmostEqual(0.0, result["selectedMatch"]["angularResidualDeg"])

    def test_real_groove_near_fixture_angles_is_not_masked(self) -> None:
        for first_angle in (31.0, 328.0):
            with self.subTest(first_angle=first_angle):
                first = frame("a", [candidate("g1", first_angle)])
                second = frame("b", [candidate("g2", wrap_360(first_angle + 70.0))])
                result = build_paired_result(
                    pair(rotation=70.0), first, second, enabled_config(),
                )
                self.assertTrue(result["valid"])

    def test_one_unobstructed_frame_is_enough_and_output_is_second_posture(self) -> None:
        first = frame("a", [candidate("g1", 115.0, accepted=True)])
        second = frame("b", [candidate("g2", 175.0, accepted=False)])
        result = build_paired_result(pair(), first, second, enabled_config())
        self.assertTrue(result["valid"])
        self.assertEqual("CAPTURE_1_PROPAGATED", result["measurementSource"])
        self.assertAlmostEqual(85.0, result["currentAngleDeg"])
        self.assertTrue(result["withinTolerance"])
        self.assertEqual(0.0, result["correctionDeg"])

    def test_second_frame_direct_measurement_is_preferred(self) -> None:
        first = frame("a", [candidate("g1", 52.0, accepted=False)])
        second = frame("b", [candidate("g2", 112.0, accepted=True)])
        result = build_paired_result(pair(), first, second, enabled_config())
        self.assertTrue(result["valid"])
        self.assertEqual("CAPTURE_2_DIRECT", result["measurementSource"])
        self.assertAlmostEqual(22.0, result["currentAngleDeg"])
        self.assertAlmostEqual(63.0, result["correctionDeg"])
        self.assertEqual("CLOCKWISE", result["rotationDirection"])

    def test_no_usable_measurement_fails_closed(self) -> None:
        result = build_paired_result(
            pair(),
            frame("a", [candidate("g1", 20.0, accepted=False)]),
            frame("b", [candidate("g2", 80.0, accepted=False)]),
            enabled_config(),
        )
        self.assertFalse(result["valid"])
        self.assertEqual("PAIR_NO_UNOBSTRUCTED_MEASUREMENT", result["error"]["code"])
        self.assertIsNone(result["correctionDeg"])

    def test_equal_matches_are_ambiguous(self) -> None:
        first = frame("a", [candidate("g1", 20.0), candidate("g1b", 20.2)])
        second = frame("b", [candidate("g2", 80.0)])
        result = build_paired_result(pair(), first, second, enabled_config(minMatchMarginDeg=1.0))
        self.assertFalse(result["valid"])
        self.assertEqual("PAIR_MATCH_AMBIGUOUS", result["error"]["code"])

    def test_rotation_residual_and_shape_difference_reject(self) -> None:
        first = frame("a", [candidate("g1", 20.0, half_width=5.0)])
        second = frame("b", [candidate("g2", 95.0, half_width=20.0)])
        result = build_paired_result(pair(), first, second, enabled_config())
        self.assertFalse(result["valid"])
        self.assertEqual("PAIR_MATCH_NOT_FOUND", result["error"]["code"])
        self.assertTrue(result["hypotheses"][0]["failedChecks"])

    def test_rotation_tolerance_is_applied_to_circular_residual(self) -> None:
        accepted = build_paired_result(
            pair(tolerance=1.0), frame("a", [candidate("g1", 20.0)]),
            frame("b", [candidate("g2", 82.5)]), enabled_config(),
        )
        self.assertTrue(accepted["valid"])
        self.assertAlmostEqual(2.5, accepted["selectedMatch"]["angularResidualDeg"])
        rejected = build_paired_result(
            pair(tolerance=1.0), frame("a", [candidate("g1", 20.0)]),
            frame("b", [candidate("g2", 84.0)]), enabled_config(),
        )
        self.assertEqual("PAIR_MATCH_NOT_FOUND", rejected["error"]["code"])

    def test_paired_guidance_preserves_closed_80_90_deadband_and_shortest_sign(self) -> None:
        for current, expected_correction, expected_direction in (
            (80.0, 0.0, "NONE"), (90.0, 0.0, "NONE"),
            (22.834, 62.166, "CLOCKWISE"), (-158.111, -116.889, "COUNTERCLOCKWISE"),
        ):
            with self.subTest(current=current):
                second_profile = wrap_360(current + 90.0)
                first_profile = wrap_360(second_profile - 60.0)
                result = build_paired_result(
                    pair(), frame("a", [candidate("g1", first_profile)]),
                    frame("b", [candidate("g2", second_profile)]), enabled_config(),
                )
                self.assertTrue(result["valid"])
                self.assertAlmostEqual(expected_correction, result["correctionDeg"], places=6)
                self.assertEqual(expected_direction, result["rotationDirection"])

    def test_unconfirmed_is_diagnostic_even_with_provisional_values(self) -> None:
        result = build_paired_result(
            pair(status="UNCONFIRMED"),
            frame("a", [candidate("g1", 20.0)]),
            frame("b", [candidate("g2", 80.0)]),
            enabled_config(),
        )
        self.assertFalse(result["valid"])
        self.assertEqual("DIAGNOSTIC_ONLY", result["status"])
        self.assertEqual("PAIR_PARAMETERS_UNCONFIRMED", result["error"]["code"])
        self.assertIsNone(result["currentAngleDeg"])
        self.assertTrue(result["hypotheses"])

    def test_disabled_experiment_does_not_match(self) -> None:
        result = build_paired_result(
            pair(), frame("a", [candidate("g1", 20.0)]), frame("b", [candidate("g2", 80.0)]),
            DEFAULT_PAIRED_CONFIG,
        )
        self.assertEqual("EXPERIMENT_DISABLED", result["status"])
        self.assertFalse(result["valid"])
        self.assertEqual([], result["hypotheses"])

    def test_too_small_rotation_and_candidate_overflow_fail(self) -> None:
        small = build_paired_result(
            pair(rotation=1.0), frame("a", [candidate("g1", 20.0)]),
            frame("b", [candidate("g2", 21.0)]), enabled_config(),
        )
        self.assertEqual("PAIR_ROTATION_NOT_DISCRIMINATING", small["error"]["code"])
        overflow_items = [candidate(f"g{i}", float(i)) for i in range(17)]
        overflow = build_paired_result(
            pair(), frame("a", overflow_items), frame("b", [candidate("g2", 80.0)]), enabled_config(),
        )
        self.assertEqual("PAIR_CANDIDATE_LIMIT", overflow["error"]["code"])


if __name__ == "__main__":
    unittest.main()
