from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

try:
    import jsonschema
except ImportError:  # pragma: no cover - explicit schema gate covers this dependency.
    jsonschema = None

from algorithms.slot_pose.single_groove_pose import (
    DEFAULT_SINGLE_GROOVE_POSE_CONFIG_V3,
    build_closed_loop_guidance,
    build_single_groove_pose,
    merged_single_groove_pose_config,
)


def datum_at(angle_deg: float, *, required_region_passed: bool | None = None) -> dict:
    if required_region_passed is None:
        required_region_passed = 80.0 <= angle_deg <= 90.0
    return {
        "measuredFromPositiveYClockwiseDeg": angle_deg,
        "position": {
            "horizontal": "left" if angle_deg > 0.0 else "right",
            "vertical": "lower",
            "requiredRegionPassed": required_region_passed,
        },
    }


def refined_candidate(measured_deg: float) -> dict:
    midpoint_profile_deg = (90.0 + measured_deg) % 360.0
    return {
        "candidateId": "candidate-002",
        "centerDeg": midpoint_profile_deg,
        "startDeg": (midpoint_profile_deg - 5.0) % 360.0,
        "endDeg": (midpoint_profile_deg + 5.0) % 360.0,
        "refinedStartDeg": (midpoint_profile_deg - 5.0) % 360.0,
        "refinedEndDeg": (midpoint_profile_deg + 5.0) % 360.0,
        "grooveRefinement": {"status": "accepted"},
    }


class ClosedLoopGuidanceMathTests(unittest.TestCase):
    def setUp(self) -> None:
        self.target = copy.deepcopy(DEFAULT_SINGLE_GROOVE_POSE_CONFIG_V3["target"])

    def test_authoritative_examples_are_detection_success(self) -> None:
        cases = (
            (82.978, "DETECTED_IN_POSITION", 0.0, "NONE", True),
            (22.834, "DETECTED_NEEDS_ADJUSTMENT", 62.166, "CLOCKWISE", False),
            (-158.111, "DETECTED_NEEDS_ADJUSTMENT", -116.889, "COUNTERCLOCKWISE", False),
        )
        for current, status, correction, direction, within in cases:
            with self.subTest(current=current):
                result = build_closed_loop_guidance(
                    self.target, datum_at(current), geometry_valid=True,
                    plc_mapping_confirmed=False,
                )
                self.assertEqual("DETECTED", result["detectionStatus"])
                self.assertEqual(status, result["guidanceStatus"])
                self.assertAlmostEqual(correction, result["correctionDeg"], places=6)
                self.assertEqual(direction, result["rotationDirection"])
                self.assertEqual(within, result["withinTolerance"])
                self.assertEqual(result["correctionDeg"], result["imageFrameCorrectionDeg"])
                self.assertEqual("BLOCKED_MAPPING_UNCONFIRMED", result["plcExecution"]["status"])
                self.assertIsNone(result["plcExecution"]["mechanicalCorrectionDeg"])
                self.assertIsNone(result["plcExecution"]["plcCommand"])

    def test_deadband_is_inclusive_and_retains_raw_difference(self) -> None:
        for current in (80.0, 82.0, 85.0, 90.0):
            with self.subTest(current=current):
                result = build_closed_loop_guidance(
                    self.target, datum_at(current), geometry_valid=True,
                    plc_mapping_confirmed=False,
                )
                self.assertEqual(85.0 - current, result["correctionRawDeg"])
                self.assertEqual(0.0, result["correctionDeg"])
                self.assertEqual("NONE", result["rotationDirection"])
        for current in (79.999, 90.001):
            with self.subTest(current=current):
                result = build_closed_loop_guidance(
                    self.target, datum_at(current, required_region_passed=True),
                    geometry_valid=True, plc_mapping_confirmed=False,
                )
                self.assertEqual("DETECTED_NEEDS_ADJUSTMENT", result["guidanceStatus"])
                self.assertNotEqual(0.0, result["correctionDeg"])

    def test_shortest_wrap_and_exact_180_are_deterministic(self) -> None:
        wrapped = build_closed_loop_guidance(
            self.target, datum_at(-179.0), geometry_valid=True,
            plc_mapping_confirmed=False,
        )
        self.assertAlmostEqual(-96.0, wrapped["correctionDeg"])
        exact = build_closed_loop_guidance(
            self.target, datum_at(-95.0), geometry_valid=True,
            plc_mapping_confirmed=False,
        )
        self.assertEqual(-180.0, exact["correctionDeg"])
        self.assertEqual("COUNTERCLOCKWISE", exact["rotationDirection"])

    def test_current_pose_anywhere_is_not_a_detection_failure(self) -> None:
        for current in (-180.0, -90.0, 0.0, 45.0, 100.0, 179.999):
            with self.subTest(current=current):
                result = build_closed_loop_guidance(
                    self.target, datum_at(current, required_region_passed=False),
                    geometry_valid=True, plc_mapping_confirmed=False,
                )
                self.assertEqual("DETECTED", result["detectionStatus"])
                self.assertEqual("DETECTED_NEEDS_ADJUSTMENT", result["guidanceStatus"])

    def test_geometry_failure_is_unavailable_not_zero(self) -> None:
        result = build_closed_loop_guidance(
            self.target, None, geometry_valid=False, plc_mapping_confirmed=False,
        )
        self.assertEqual("DETECTION_FAILED", result["detectionStatus"])
        self.assertEqual("NOT_AVAILABLE", result["guidanceStatus"])
        for key in (
            "currentAngleDeg", "correctionRawDeg", "correctionDeg",
            "imageFrameCorrectionDeg", "rotationDirection", "withinTolerance",
        ):
            self.assertIsNone(result[key])

    def test_recapture_sequence_never_reuses_prior_correction(self) -> None:
        first = build_closed_loop_guidance(
            self.target, datum_at(22.834), geometry_valid=True,
            plc_mapping_confirmed=False,
        )
        second = build_closed_loop_guidance(
            self.target, datum_at(82.978), geometry_valid=True,
            plc_mapping_confirmed=False,
        )
        third = build_closed_loop_guidance(
            self.target, None, geometry_valid=False,
            plc_mapping_confirmed=False,
        )
        self.assertAlmostEqual(62.166, first["imageFrameCorrectionDeg"])
        self.assertEqual(0.0, second["imageFrameCorrectionDeg"])
        self.assertIsNone(third["imageFrameCorrectionDeg"])
        self.assertEqual("NOT_AVAILABLE", third["guidanceStatus"])


class ClosedLoopPoseTests(unittest.TestCase):
    def test_v3_target_and_coordinate_contract_cannot_be_silently_changed(self) -> None:
        for key, value in (
            ("nominal_deg", 84.0),
            ("accepted_min_deg", 79.0),
            ("physical_datum_definition_id", "another-ray"),
            ("angle_convention_id", "counterclockwise"),
        ):
            config = copy.deepcopy(DEFAULT_SINGLE_GROOVE_POSE_CONFIG_V3)
            config["target"][key] = value
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "single_groove_pose"):
                merged_single_groove_pose_config(config)

    def test_v3_pose_carries_guidance_without_plc_authority(self) -> None:
        pose = build_single_groove_pose(
            [refined_candidate(22.834)], (100.0, 100.0), 50.0,
            DEFAULT_SINGLE_GROOVE_POSE_CONFIG_V3,
            recognition_status="accepted", plc_mapping_confirmed=False,
        )
        self.assertEqual("slot-single-real-groove-pose/3", pose["schemaVersion"])
        self.assertTrue(pose["geometryValid"])
        self.assertEqual("DETECTED", pose["guidance"]["detectionStatus"])
        self.assertAlmostEqual(62.166, pose["guidance"]["imageFrameCorrectionDeg"], places=6)
        self.assertFalse(pose["role"]["mechanicalGuidanceAuthoritative"])

    def test_zero_or_multiple_candidates_fail_closed(self) -> None:
        for candidates, recognition_status in (
            ([], "failed"),
            ([refined_candidate(10.0), refined_candidate(20.0)], "ambiguous"),
        ):
            with self.subTest(count=len(candidates)):
                pose = build_single_groove_pose(
                    candidates, (100.0, 100.0), 50.0,
                    DEFAULT_SINGLE_GROOVE_POSE_CONFIG_V3,
                    recognition_status=recognition_status,
                )
                self.assertFalse(pose["geometryValid"])
                self.assertEqual("DETECTION_FAILED", pose["guidance"]["detectionStatus"])
                self.assertIsNone(pose["guidance"]["imageFrameCorrectionDeg"])

    @unittest.skipIf(jsonschema is None, "jsonschema is installed by the explicit Schema gate")
    def test_v3_pose_matches_versioned_schema(self) -> None:
        root = Path(__file__).resolve().parents[1]
        pose = build_single_groove_pose(
            [refined_candidate(82.978)], (100.0, 100.0), 50.0,
            DEFAULT_SINGLE_GROOVE_POSE_CONFIG_V3,
            recognition_status="accepted",
        )
        schema = json.loads(
            (root / "contracts/single-real-groove-pose-v3.schema.json").read_text(encoding="utf-8")
        )
        jsonschema.Draft202012Validator.check_schema(schema)
        jsonschema.validate(pose, schema)


if __name__ == "__main__":
    unittest.main()
