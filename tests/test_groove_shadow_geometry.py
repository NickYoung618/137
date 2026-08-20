from __future__ import annotations

import unittest

import numpy as np

from algorithms.end_face.core import bilinear_sample
from algorithms.slot_pose.groove_shadow_geometry import (
    assess_groove_floor_evidence,
    assess_candidate_fixture_overlap,
    assess_relative_shadow_geometry,
    build_fixture_source_exclusion,
    detect_stationary_fixture_sectors,
)


def candidate(identifier: str, center: float, half_width: float) -> dict:
    return {
        "candidateId": identifier,
        "centerDeg": center % 360.0,
        "halfWidthDeg": half_width,
        "startDeg": (center - half_width) % 360.0,
        "endDeg": (center + half_width) % 360.0,
    }


class GrooveShadowGeometryTests(unittest.TestCase):
    @staticmethod
    def verified_fixture() -> dict:
        return {
            "schemaVersion": "stationary-two-body-fixture-evidence/1",
            "status": "verified", "fixtureBodiesVerified": True,
            "sectors": [
                {"sectorId": "upper", "role": "upper_fixture", "centerDeg": 310.0, "spanDeg": 40.0},
                {"sectorId": "lower", "role": "lower_fixture", "centerDeg": 30.0, "spanDeg": 46.0},
            ],
        }

    def test_two_exterior_textured_bodies_are_verified_without_fixed_angles(self) -> None:
        image = np.zeros((240, 240), dtype=float)
        yy, xx = np.mgrid[:240, :240]
        center = (120.0, 120.0)
        radial = np.hypot(xx - center[0], yy - center[1])
        angle = np.degrees(np.arctan2(yy - center[1], xx - center[0])) % 360.0
        upper = (np.abs((angle - 320.0 + 180.0) % 360.0 - 180.0) <= 20.0)
        lower = (np.abs((angle - 40.0 + 180.0) % 360.0 - 180.0) <= 24.0)
        exterior = (radial >= 62.0) & (radial <= 105.0)
        texture = 55.0 + 8.0 * np.sin(radial * 0.7)
        image[exterior & (upper | lower)] = texture[exterior & (upper | lower)]
        result = detect_stationary_fixture_sectors(
            image, center, 60.0, angular_sample_count=360,
        )
        self.assertEqual("verified", result["status"], result)
        self.assertTrue(result["fixtureBodiesVerified"])
        self.assertEqual(2, len(result["sectors"]))
        self.assertEqual({"upper_fixture", "lower_fixture"}, {
            item["role"] for item in result["sectors"]
        })

    def test_zero_one_or_three_exterior_bodies_are_not_verified(self) -> None:
        blank = np.zeros((200, 200), dtype=float)
        result = detect_stationary_fixture_sectors(blank, (100.0, 100.0), 50.0)
        self.assertEqual("not_evaluated", result["status"])
        self.assertFalse(result["fixtureBodiesVerified"])

    def test_lower_body_is_false_source_risk_but_never_occlusion_risk(self) -> None:
        result = assess_candidate_fixture_overlap(
            candidate("lower-dark-region", 34.0, 8.0), self.verified_fixture(),
        )
        self.assertEqual("evaluated", result["status"])
        self.assertEqual("lower_fixture", result["overlapRole"])
        self.assertTrue(result["lowerFixtureFalseSourceRisk"])
        self.assertFalse(result["upperFixtureOcclusionRisk"])
        self.assertFalse(result["candidateSelectionUsedFixedAngle"])

    def test_upper_body_alone_carries_occlusion_risk(self) -> None:
        result = assess_candidate_fixture_overlap(
            candidate("near-upper", 315.0, 6.0), self.verified_fixture(),
        )
        self.assertEqual("upper_fixture", result["overlapRole"])
        self.assertFalse(result["lowerFixtureFalseSourceRisk"])
        self.assertTrue(result["upperFixtureOcclusionRisk"])

    def test_two_walls_without_independent_floor_never_release_recovery(self) -> None:
        refinement = {
            "status": "accepted", "startSide": {}, "endSide": {},
            "outerCircleIntersections": [{"x": 1, "y": 2}, {"x": 3, "y": 4}],
        }
        result = build_fixture_source_exclusion(
            candidate("outside", 180.0, 5.0), self.verified_fixture(), refinement,
        )
        self.assertFalse(result["uContourComplete"])
        self.assertFalse(result["fixtureSourceExcluded"])
        self.assertIn("groove_floor_not_complete", result["failedChecks"])

    def test_complete_u_contour_outside_both_bodies_can_exclude_fixture_source(self) -> None:
        refinement = {
            "status": "accepted", "startSide": {}, "endSide": {},
            "outerCircleIntersections": [{"x": 1, "y": 2}, {"x": 3, "y": 4}],
        }
        floor = {"schemaVersion": "groove-floor-evidence/1", "status": "accepted", "failedChecks": []}
        result = build_fixture_source_exclusion(
            candidate("outside", 180.0, 5.0), self.verified_fixture(), refinement,
            groove_floor_evidence=floor,
        )
        self.assertEqual("verified", result["status"])
        self.assertTrue(result["uContourComplete"])
        self.assertTrue(result["fixtureSourceExcluded"])

        near_upper = build_fixture_source_exclusion(
            candidate("near-upper", 315.0, 6.0), self.verified_fixture(), refinement,
            groove_floor_evidence=floor,
        )
        self.assertTrue(near_upper["fixtureSourceExcluded"])
        self.assertNotIn("upper_fixture_shadow_overlap", near_upper["failedChecks"])

        lower = build_fixture_source_exclusion(
            candidate("lower", 34.0, 6.0), self.verified_fixture(), refinement,
            groove_floor_evidence=floor,
        )
        self.assertFalse(lower["fixtureSourceExcluded"])
        self.assertIn("lower_fixture_false_candidate", lower["failedChecks"])

    def test_radial_recovered_u_contour_between_bodies_excludes_fixture_source(self) -> None:
        side = {
            "lineFitStrategy": "shared-longitudinal-wall-family-v2",
            "radialAlignmentPassed": True,
        }
        refinement = {
            "status": "accepted", "startSide": side,
            "endSide": {**side, "lineFitStrategy": "deterministic-consensus-tls-v2-preserved"},
            "outerCircleIntersections": [{"x": 1, "y": 2}, {"x": 3, "y": 4}],
        }
        floor = {"schemaVersion": "groove-floor-evidence/1", "status": "accepted", "failedChecks": []}
        result = build_fixture_source_exclusion(
            candidate("between", 350.0, 25.0), self.verified_fixture(), refinement,
            groove_floor_evidence=floor,
        )
        self.assertEqual("fixture-groove-source-exclusion/2", result["schemaVersion"])
        self.assertEqual("verified", result["status"], result)
        self.assertTrue(result["radialSidewallsVerified"])
        self.assertTrue(result["fixtureSourceExcluded"])

        incomplete = build_fixture_source_exclusion(
            candidate("between", 350.0, 25.0), self.verified_fixture(),
            {**refinement, "endSide": {**refinement["endSide"], "radialAlignmentPassed": False}},
            groove_floor_evidence=floor,
        )
        self.assertEqual("rejected", incomplete["status"])
        self.assertIn("multiple_fixture_overlap", incomplete["failedChecks"])

    def test_partial_floor_near_both_bodies_uses_visible_boundary_ownership(self) -> None:
        refinement = {
            "status": "accepted", "startSide": {}, "endSide": {},
            "outerCircleIntersections": [{"x": 1, "y": 2}, {"x": 3, "y": 4}],
        }
        floor = {
            "schemaVersion": "groove-floor-evidence/1", "status": "rejected",
            "acceptedTrackCount": 3,
            "tracks": [
                {"offsetFraction": -0.65, "status": "accepted", "failedChecks": []},
                {"offsetFraction": -0.30, "status": "accepted", "failedChecks": []},
                {"offsetFraction": 0.0, "status": "accepted", "failedChecks": []},
                {"offsetFraction": 0.30, "status": "failed", "failedChecks": ["floor_edge_not_unique"]},
                {"offsetFraction": 0.65, "status": "failed", "failedChecks": ["floor_edge_not_unique"]},
            ],
            "failedChecks": ["floor_track_support_incomplete"],
        }
        source = {
            "status": "rejected",
            "checks": [
                {"checkId": check_id, "passed": passed}
                for check_id, passed in (
                    ("edge_contrast_asymmetry", False),
                    ("edge_gradient_asymmetry", True),
                    ("normalized_profile_dissimilar", True),
                    ("normalized_profile_uncorrelated", True),
                    ("radial_coverage_inconsistent", True),
                    ("endpoint_structure_inconsistent", True),
                )
            ],
        }
        result = build_fixture_source_exclusion(
            candidate("between", 350.0, 25.0), self.verified_fixture(), refinement,
            groove_floor_evidence=floor, source_consistency_evidence=source,
        )
        self.assertEqual("fixture-groove-source-exclusion/3", result["schemaVersion"])
        self.assertEqual("verified", result["status"], result)
        self.assertTrue(result["visibleBoundaryOwnershipVerified"])
        self.assertTrue(result["centralFloorTrackPresent"])
        self.assertFalse(result["uContourComplete"])

        upper = build_fixture_source_exclusion(
            candidate("upper", 315.0, 6.0), self.verified_fixture(), refinement,
            groove_floor_evidence=floor, source_consistency_evidence=source,
        )
        self.assertEqual("rejected", upper["status"])
        self.assertFalse(upper.get("visibleBoundaryOwnershipVerified", False))

    def test_curved_five_track_floor_is_accepted_but_straight_shadow_edge_is_not(self) -> None:
        yy, xx = np.mgrid[:260, :260]
        center = (130.0, 130.0)
        radius = np.hypot(xx - center[0], yy - center[1])
        angle = np.degrees(np.arctan2(yy - center[1], xx - center[0])) % 360.0
        delta = np.abs((angle - 180.0 + 180.0) % 360.0 - 180.0)
        inward_depth = 90.0 - radius
        floor_depth = 25.0 - 14.0 * (delta / 10.0) ** 2
        curved = np.full((260, 260), 190.0)
        curved[(delta <= 9.0) & (inward_depth >= 0.0) & (inward_depth <= floor_depth)] = 35.0
        target = {**candidate("groove", 180.0, 10.0), "radialDepthPx": 25.0}
        accepted = assess_groove_floor_evidence(
            curved, center, 90.0, target, bilinear_sample,
        )
        self.assertEqual("accepted", accepted["status"], accepted)

        straight = np.full((260, 260), 190.0)
        straight[(delta <= 9.0) & (inward_depth >= 0.0) & (inward_depth <= 20.0)] = 35.0
        rejected = assess_groove_floor_evidence(
            straight, center, 90.0, target, bilinear_sample,
        )
        self.assertEqual("rejected", rejected["status"])
        self.assertIn("curved_floor_depth", rejected["failedChecks"])

    def test_relative_overlap_and_nearby_evidence_are_rotation_invariant(self) -> None:
        base = [candidate("target", 358.0, 5.0), candidate("overlap", 3.0, 4.0),
                candidate("far", 90.0, 3.0)]
        rotated = [candidate(item["candidateId"], item["centerDeg"] + 73.0,
                             item["halfWidthDeg"]) for item in base]
        first = assess_relative_shadow_geometry(base, "target", search_margin_deg=8.0)
        second = assess_relative_shadow_geometry(rotated, "target", search_margin_deg=8.0)
        self.assertTrue(first["overlapEvidence"])
        self.assertEqual(first["overlappingCandidateCount"], second["overlappingCandidateCount"])
        self.assertEqual(first["nearbyCandidateCount"], second["nearbyCandidateCount"])
        self.assertAlmostEqual(
            first["nearestBoundaryGapDeg"], second["nearestBoundaryGapDeg"], places=9,
        )

    def test_order_and_irrelevant_metadata_do_not_change_geometry(self) -> None:
        items = [candidate("target", 120.0, 6.0), candidate("near", 136.0, 3.0)]
        first = assess_relative_shadow_geometry(items, "target", search_margin_deg=8.0)
        items[0]["filename"] = "must-not-be-used.bmp"
        second = assess_relative_shadow_geometry(list(reversed(items)), "target", search_margin_deg=8.0)
        self.assertEqual(first, second)

    def test_missing_duplicate_or_nonfinite_target_fails_closed(self) -> None:
        self.assertEqual("not_evaluated", assess_relative_shadow_geometry(
            [candidate("other", 20.0, 2.0)], "target", search_margin_deg=8.0,
        )["status"])
        duplicate = [candidate("target", 20.0, 2.0), candidate("target", 30.0, 2.0)]
        self.assertEqual("not_evaluated", assess_relative_shadow_geometry(
            duplicate, "target", search_margin_deg=8.0,
        )["status"])
        bad = candidate("target", 20.0, 2.0)
        bad["centerDeg"] = float("nan")
        self.assertEqual("not_evaluated", assess_relative_shadow_geometry(
            [bad], "target", search_margin_deg=8.0,
        )["status"])


if __name__ == "__main__":
    unittest.main()
