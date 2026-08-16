from __future__ import annotations

import json
import unittest
from pathlib import Path

import numpy as np

from algorithms.slot_pose.groove_refinement import refine_groove_opening
from algorithms.slot_pose.local_second_wall import (
    DEFAULT_LOCAL_SECOND_WALL_CONFIG,
    _build_search_domains,
    _canonical_pair_id,
    _cluster_side_searches,
    diagnose_local_second_wall,
    merged_local_second_wall_config,
)
from algorithms.slot_pose.sidewall_consistency import DEFAULT_SIDEWALL_CONSISTENCY_CONFIG
from tests.test_groove_refinement import (
    bilinear_sample,
    candidate,
    groove_image,
    parabolic_peak,
    v2_config,
)

try:
    import jsonschema
except ImportError:
    jsonschema = None


CENTER = (260.35, 251.65)
RADIUS = 185.4


def diagnostic_config(**overrides: object) -> dict:
    return {**DEFAULT_LOCAL_SECOND_WALL_CONFIG, "enabled": True, **overrides}


def source_config(**overrides: object) -> dict:
    return {
        **DEFAULT_SIDEWALL_CONSISTENCY_CONFIG,
        "enabled": True,
        "max_contrast_normalized_difference": 0.30,
        **overrides,
    }


def refine(image: np.ndarray, start: float, end: float) -> dict:
    result = refine_groove_opening(
        image, CENTER, RADIUS, candidate(start, end),
        bilinear_sample, parabolic_peak, v2_config(),
    )
    if result["status"] != "accepted":
        raise AssertionError(result)
    return result


def union_dark_grooves(intervals: list[tuple[float, float]]) -> np.ndarray:
    return dark_features([(start, end, 110.0, 170.0) for start, end in intervals])


def dark_features(features: list[tuple[float, float, float, float]]) -> np.ndarray:
    yy, xx = np.mgrid[:520, :520].astype(float)
    radial = np.hypot(xx - CENTER[0], yy - CENTER[1])
    angle = np.degrees(np.arctan2(yy - CENTER[1], xx - CENTER[0])) % 360.0
    image = np.full(radial.shape, 25.0, dtype=float)
    image[radial <= RADIUS] = 210.0
    for start, end, depth, contrast in features:
        inside = ((angle - start) % 360.0) <= ((end - start) % 360.0)
        mask = (radial <= RADIUS) & (radial >= RADIUS - depth) & inside
        image[mask] = np.minimum(image[mask], 210.0 - contrast)
    for _ in range(2):
        image = (
            np.roll(image, 1, 0) + 2 * image + np.roll(image, -1, 0)
            + np.roll(image, 1, 1) + np.roll(image, -1, 1)
        ) / 6.0
    return image


class LocalSecondWallTests(unittest.TestCase):
    def test_bidirectional_config_is_strict_and_physically_bounded(self) -> None:
        merged = merged_local_second_wall_config(None)
        self.assertEqual("local-second-wall-diagnostic/2", merged["schema_version"])
        self.assertEqual("local-second-wall-diagnostic-v2", merged["threshold_version"])
        self.assertLessEqual(merged["outward_search_extent_deg"], merged["max_wall_separation_deg"])
        self.assertLessEqual(merged["inward_search_extent_deg"], merged["max_wall_separation_deg"])
        for key, value in (
            ("outward_search_extent_deg", 31.0),
            ("inward_search_extent_deg", 31.0),
        ):
            with self.subTest(key=key):
                with self.assertRaisesRegex(ValueError, "physical wall separation"):
                    merged_local_second_wall_config({**merged, key: value})
        with self.assertRaisesRegex(ValueError, "max_total_search_jobs"):
            merged_local_second_wall_config({**merged, "max_total_search_jobs": 7})

    def test_search_domains_cover_start_end_inward_outward_and_wrap(self) -> None:
        config = diagnostic_config(
            inward_search_extent_deg=30.0,
            outward_search_extent_deg=30.0,
        )
        domains = _build_search_domains(
            350.0, 20.0, {"startSide": 350.0, "endSide": 10.0}, config,
        )
        self.assertEqual({
            "startSide-inward", "startSide-outward",
            "endSide-inward", "endSide-outward",
        }, {item["domainId"] for item in domains})
        by_id = {item["domainId"]: item for item in domains}
        self.assertAlmostEqual(0.0, by_id["startSide-inward"]["endDeg"])
        self.assertAlmostEqual(320.0, by_id["startSide-outward"]["endDeg"])
        self.assertAlmostEqual(0.0, by_id["endSide-inward"]["endDeg"])
        self.assertAlmostEqual(40.0, by_id["endSide-outward"]["endDeg"])
        self.assertTrue(by_id["startSide-inward"]["wrapsBoundary"])
        self.assertFalse(by_id["endSide-outward"]["wrapsBoundary"])
        end_wrap = _build_search_domains(
            335.0, 20.0, {"startSide": 335.0, "endSide": 355.0}, config,
        )
        self.assertTrue({item["domainId"]: item for item in end_wrap}["endSide-outward"]["wrapsBoundary"])
        self.assertTrue(all(item["seedCount"] <= config["max_seeds_per_domain"] for item in domains))

    def test_runtime_search_job_limit_fails_closed_before_sampling(self) -> None:
        image = groove_image(170.18, 179.72, center=CENTER, radius=RADIUS)
        initial = refine(image, 170.0, 180.0)
        output = diagnose_local_second_wall(
            image, CENTER, RADIUS, candidate(168.0, 182.0), initial,
            bilinear_sample, parabolic_peak, v2_config(), source_config(),
            diagnostic_config(max_total_search_jobs=8),
        )
        self.assertEqual("LOCAL_SECOND_WALL_NOT_FOUND", output["errorCode"])
        self.assertEqual(["search_job_limit_exceeded"], output["failedChecks"])
        self.assertEqual([], output["sideSearchCandidates"])

    def test_canonical_pair_id_is_endpoint_order_independent(self) -> None:
        self.assertEqual(
            _canonical_pair_id("falling-wall-cluster-002", "rising-wall-cluster-001"),
            _canonical_pair_id("rising-wall-cluster-001", "falling-wall-cluster-002"),
        )

    def test_true_wall_outside_start_boundary_is_generated(self) -> None:
        image = groove_image(170.18, 179.72, center=CENTER, radius=RADIUS)
        true_refinement = refine(image, 170.0, 180.0)
        fixture_image = groove_image(195.0, 205.0, center=CENTER, radius=RADIUS, contrast=75.0)
        fixture_refinement = refine(fixture_image, 195.0, 205.0)
        mixed = {
            **true_refinement,
            "startSide": true_refinement["endSide"],
            "endSide": fixture_refinement["endSide"],
            "openingEndpointProfileDeg": [
                true_refinement["openingEndpointProfileDeg"][1],
                fixture_refinement["openingEndpointProfileDeg"][1],
            ],
            "outerCircleIntersections": [
                true_refinement["outerCircleIntersections"][1],
                fixture_refinement["outerCircleIntersections"][1],
            ],
        }
        output = diagnose_local_second_wall(
            image, CENTER, RADIUS, candidate(179.5, 206.0), mixed,
            bilinear_sample, parabolic_peak, v2_config(), source_config(), diagnostic_config(),
        )
        self.assertEqual("local-second-wall-diagnostic/4", output["schemaVersion"])
        self.assertEqual("UNIQUE_DIAGNOSTIC", output["status"], output)
        measured = output["experimentalCandidate"]["openingEndpointProfileDeg"]
        self.assertAlmostEqual(170.18, measured[0], delta=0.15)
        self.assertAlmostEqual(179.72, measured[1], delta=0.15)
        true_cluster_ids = set(output["experimentalCandidate"]["wallClusterIds"])
        self.assertTrue(any(
            item["direction"] == "OUTWARD" and item["anchorSide"] == "startSide"
            for item in output["searchDomains"]
        ))
        self.assertTrue(any(
            true_cluster_ids.intersection({item["clusterId"]})
            and "startSide-outward" in item["memberDomainIds"]
            for item in output["sideSearchMergeClusters"]
        ))

    def test_true_wall_outside_end_boundary_is_generated(self) -> None:
        image = groove_image(195.18, 204.72, center=CENTER, radius=RADIUS)
        true_refinement = refine(image, 195.0, 205.0)
        fixture_image = groove_image(170.0, 180.0, center=CENTER, radius=RADIUS, contrast=75.0)
        fixture_refinement = refine(fixture_image, 170.0, 180.0)
        mixed = {
            **true_refinement,
            "startSide": fixture_refinement["startSide"],
            "endSide": true_refinement["startSide"],
            "openingEndpointProfileDeg": [
                fixture_refinement["openingEndpointProfileDeg"][0],
                true_refinement["openingEndpointProfileDeg"][0],
            ],
            "outerCircleIntersections": [
                fixture_refinement["outerCircleIntersections"][0],
                true_refinement["outerCircleIntersections"][0],
            ],
        }
        output = diagnose_local_second_wall(
            image, CENTER, RADIUS, candidate(169.0, 196.0), mixed,
            bilinear_sample, parabolic_peak, v2_config(), source_config(), diagnostic_config(),
        )
        self.assertEqual("UNIQUE_DIAGNOSTIC", output["status"], output)
        measured = output["experimentalCandidate"]["openingEndpointProfileDeg"]
        self.assertAlmostEqual(195.18, measured[0], delta=0.15)
        self.assertAlmostEqual(204.72, measured[1], delta=0.15)
        self.assertTrue(any(
            item["direction"] == "OUTWARD" and item["anchorSide"] == "endSide"
            for item in output["searchDomains"]
        ))

    def test_default_is_disabled_strict_and_does_not_claim_pose(self) -> None:
        merged = merged_local_second_wall_config(None)
        self.assertFalse(merged["enabled"])
        with self.assertRaisesRegex(ValueError, "unknown fields"):
            merged_local_second_wall_config({"surprise": 1})
        image = groove_image(170.18, 179.72, center=CENTER, radius=RADIUS)
        initial = refine(image, 170.0, 180.0)
        output = diagnose_local_second_wall(
            image, CENTER, RADIUS, candidate(168.0, 182.0), initial,
            bilinear_sample, parabolic_peak, v2_config(), source_config(), None,
        )
        self.assertEqual("DISABLED", output["status"])
        self.assertFalse(output["authoritative"])
        self.assertFalse(output["posePromotionAllowed"])
        self.assertIsNone(output["experimentalCandidate"])

        missing = diagnose_local_second_wall(
            image, CENTER, RADIUS, candidate(168.0, 182.0), {"status": "failed"},
            bilinear_sample, parabolic_peak, v2_config(), source_config(), diagnostic_config(),
        )
        self.assertEqual("CANDIDATE_MISSING", missing["errorCode"])
        self.assertEqual("candidate_anchor", missing["failureStage"])

    def test_same_square_opening_has_one_auditable_experimental_recovery(self) -> None:
        image = groove_image(170.18, 179.72, center=CENTER, radius=RADIUS)
        initial = refine(image, 170.0, 180.0)
        output = diagnose_local_second_wall(
            image, CENTER, RADIUS, candidate(168.0, 182.0), initial,
            bilinear_sample, parabolic_peak, v2_config(), source_config(), diagnostic_config(),
        )
        self.assertEqual("UNIQUE_DIAGNOSTIC", output["status"], output)
        self.assertEqual(1, output["passedHypothesisCount"])
        self.assertTrue(output["sideSearchCandidates"])
        self.assertTrue(all("failedChecks" in item for item in output["sideSearchCandidates"]))
        self.assertEqual(2, len(output["anchorEvidence"]))
        self.assertTrue(all(item["lineSegment"] is not None for item in output["anchorEvidence"]))
        self.assertEqual("coarse_raw_dark_candidate", output["localInterval"]["source"])
        self.assertTrue(all(
            "searchWindowDeg" in item and "rejectionStage" in item
            and "fitToSeedDeltaDeg" in item and "lineSegment" in item
            and "mergeDisposition" in item
            for item in output["sideSearchCandidates"]
        ))
        accepted_search_ids = {
            item["searchCandidateId"] for item in output["sideSearchCandidates"]
            if item["searchStatus"] == "accepted"
        }
        clustered_search_ids = {
            candidate_id
            for cluster in output["sideSearchMergeClusters"]
            for candidate_id in cluster["memberSearchCandidateIds"]
        }
        self.assertEqual(accepted_search_ids, clustered_search_ids)
        self.assertEqual(
            len(output["rawHypotheses"]),
            sum(item["memberCount"] for item in output["hypothesisMergeClusters"]),
        )
        self.assertEqual(len(output["hypotheses"]), len(output["hypothesisMergeClusters"]))
        pair_ids = [item["canonicalPairId"] for item in output["canonicalWallPairs"]]
        self.assertEqual(len(pair_ids), len(set(pair_ids)))
        self.assertTrue(all(
            cluster["memberCount"] == 1 and cluster["suppressedRawHypothesisIds"] == []
            for cluster in output["hypothesisMergeClusters"]
        ))
        self.assertEqual([], output["hypotheses"][0]["failedChecks"])
        self.assertTrue(all(check["hardGate"] for check in output["hypotheses"][0]["checks"]))
        self.assertEqual(
            {"candidate_origin", "local_geometry", "mouth_endpoint", "opening_structure", "sidewall_source"},
            {check["layer"] for check in output["hypotheses"][0]["checks"]},
        )
        self.assertAlmostEqual(170.18, output["experimentalCandidate"]["openingEndpointProfileDeg"][0], delta=0.15)
        self.assertAlmostEqual(179.72, output["experimentalCandidate"]["openingEndpointProfileDeg"][1], delta=0.15)
        self.assertFalse(output["experimentalCandidate"]["authoritative"])
        self.assertFalse(output["experimentalCandidate"]["posePromotionAllowed"])

    def test_cross_to_neighbor_fixture_is_rejected_while_same_opening_survives(self) -> None:
        true_image = groove_image(170.18, 179.72, center=CENTER, radius=RADIUS)
        fixture_image = groove_image(195.0, 205.0, center=CENTER, radius=RADIUS, contrast=80.0)
        true_refinement = refine(true_image, 170.0, 180.0)
        fixture_refinement = refine(fixture_image, 195.0, 205.0)
        mixed = {
            **true_refinement,
            "endSide": fixture_refinement["endSide"],
            "openingEndpointProfileDeg": [
                true_refinement["openingEndpointProfileDeg"][0],
                fixture_refinement["openingEndpointProfileDeg"][1],
            ],
        }
        image = union_dark_grooves([(170.18, 179.72), (195.0, 205.0)])
        output = diagnose_local_second_wall(
            image, CENTER, RADIUS, candidate(168.0, 207.0), mixed,
            bilinear_sample, parabolic_peak, v2_config(), source_config(), diagnostic_config(),
        )
        mixed_hypotheses = [
            item for item in output["hypotheses"]
            if item["openingWidthDeg"] > 20.0
        ]
        self.assertTrue(mixed_hypotheses, output)
        self.assertTrue(all(not item["passed"] for item in mixed_hypotheses))
        self.assertTrue(all(
            any(check["hardGate"] and not check["passed"] for check in item["checks"])
            for item in mixed_hypotheses
        ))
        self.assertTrue(any(
            "local_dark_opening_continuity" in item["failedChecks"]
            or any(reason.startswith("source_consistency:") for reason in item["failedChecks"])
            for item in mixed_hypotheses
        ))

    def test_multiple_square_openings_remain_ambiguous(self) -> None:
        image = union_dark_grooves([(170.0, 178.0), (184.0, 192.0)])
        first, second = refine(image, 170.0, 178.0), refine(image, 184.0, 192.0)
        mixed = {
            **first,
            "endSide": second["endSide"],
            "openingEndpointProfileDeg": [
                first["openingEndpointProfileDeg"][0], second["openingEndpointProfileDeg"][1],
            ],
        }
        output = diagnose_local_second_wall(
            image, CENTER, RADIUS, candidate(168.0, 194.0), mixed,
            bilinear_sample, parabolic_peak, v2_config(), source_config(), diagnostic_config(),
        )
        self.assertEqual("MULTIPLE_LOCAL_OPENINGS", output["status"], output)
        self.assertEqual("MULTIPLE_LOCAL_OPENINGS", output["errorCode"])
        self.assertGreaterEqual(output["passedHypothesisCount"], 2)
        self.assertIsNone(output["experimentalCandidate"])
        self.assertEqual(["multiple_same_opening_second_walls"], output["failedChecks"])

    def test_side_merge_trace_preserves_members_and_does_not_merge_distinct_angles(self) -> None:
        candidates = []
        for index, angle in enumerate((10.0, 10.3, 11.0), start=1):
            candidates.append({
                "searchCandidateId": f"rising-wall-search-{index:03d}",
                "searchStatus": "accepted", "seedDeg": angle,
                "polarity": "rising", "intersectionAngleDeg": angle,
            })
        representatives, clusters = _cluster_side_searches(candidates, "rising", 0.5)
        self.assertEqual(2, len(representatives))
        self.assertEqual([2, 1], [item["memberCount"] for item in clusters])
        self.assertEqual(
            {item["searchCandidateId"] for item in candidates},
            {value for item in clusters for value in item["memberSearchCandidateIds"]},
        )
        self.assertEqual("REPRESENTATIVE", candidates[0]["mergeDisposition"])
        self.assertEqual("SUPPRESSED_MEMBER", candidates[1]["mergeDisposition"])
        self.assertEqual("REPRESENTATIVE", candidates[2]["mergeDisposition"])

    def test_no_second_wall_in_local_interval_fails_closed(self) -> None:
        image = groove_image(170.0, 210.0, center=CENTER, radius=RADIUS)
        initial = refine(image, 170.0, 210.0)
        output = diagnose_local_second_wall(
            image, CENTER, RADIUS, candidate(168.0, 205.0), initial,
            bilinear_sample, parabolic_peak, v2_config(), source_config(), diagnostic_config(),
        )
        self.assertEqual("LOCAL_SECOND_WALL_NOT_FOUND", output["status"], output)
        self.assertEqual(0, output["passedHypothesisCount"])
        self.assertIsNone(output["experimentalCandidate"])
        self.assertEqual("LOCAL_SECOND_WALL_NOT_FOUND", output["errorCode"])
        self.assertEqual("local_second_wall_search", output["failureStage"])

    def test_geometry_survives_but_profile_mismatch_is_partially_observed(self) -> None:
        image = groove_image(170.18, 179.72, center=CENTER, radius=RADIUS)
        initial = refine(image, 170.0, 180.0)
        strict_source = source_config(
            max_contrast_normalized_difference=0.0,
            max_gradient_normalized_difference=0.0,
            max_normalized_profile_mae=0.0,
            min_normalized_profile_correlation=1.0,
            max_radial_coverage_difference=0.0,
            max_endpoint_structure_difference=0.0,
        )
        output = diagnose_local_second_wall(
            image, CENTER, RADIUS, candidate(168.0, 182.0), initial,
            bilinear_sample, parabolic_peak, v2_config(), strict_source, diagnostic_config(),
        )
        self.assertEqual("local-second-wall-diagnostic/4", output["schemaVersion"])
        self.assertEqual("PARTIALLY_OBSERVED", output["status"], output)
        self.assertEqual("PARTIAL_GROOVE_OBSERVATION", output["errorCode"])
        self.assertEqual("single_wall_observability", output["failureStage"])
        self.assertIsNone(output["experimentalCandidate"])
        partial = output["partialObservation"]
        self.assertGreaterEqual(partial["observedWallCandidateCount"], 1)
        self.assertEqual(
            partial["observedWallCandidateCount"], len(partial["observedWallClusterIds"]),
        )
        self.assertFalse(partial["completeSameSourceOpeningObserved"])
        self.assertFalse(partial["trueGrooveWallIdentityConfirmed"])
        self.assertFalse(partial["humanConfirmationAppliedAtRuntime"])
        self.assertEqual("UNCONFIRMED", partial["oppositeWallObservability"])
        self.assertIn(partial["reason"], {"SINGLE_WALL_CLUSTER", "NO_SAME_SOURCE_WALL_PAIR"})
        self.assertTrue(any(
            "reuses_rejected_initial_pair" in item["failedChecks"]
            for item in output["hypotheses"]
        ))

    def test_runtime_wall_candidate_limit_fails_closed(self) -> None:
        image = union_dark_grooves([(170.0, 178.0), (184.0, 192.0)])
        first, second = refine(image, 170.0, 178.0), refine(image, 184.0, 192.0)
        mixed = {
            **first,
            "endSide": second["endSide"],
            "openingEndpointProfileDeg": [
                first["openingEndpointProfileDeg"][0], second["openingEndpointProfileDeg"][1],
            ],
        }
        output = diagnose_local_second_wall(
            image, CENTER, RADIUS, candidate(168.0, 194.0), mixed,
            bilinear_sample, parabolic_peak, v2_config(), source_config(),
            diagnostic_config(max_wall_candidates=2),
        )
        self.assertEqual("MULTIPLE_LOCAL_OPENINGS", output["errorCode"])
        self.assertEqual(["wall_candidate_limit_exceeded"], output["failedChecks"])
        self.assertIsNone(output["experimentalCandidate"])

    def test_real_square_opening_near_fixture_prior_angles_is_not_screened(self) -> None:
        for start, end in ((26.0, 36.0), (323.0, 333.0)):
            with self.subTest(start=start):
                image = groove_image(start, end, center=CENTER, radius=RADIUS)
                initial = refine(image, start, end)
                output = diagnose_local_second_wall(
                    image, CENTER, RADIUS, candidate(start - 2.0, end + 2.0), initial,
                    bilinear_sample, parabolic_peak, v2_config(), source_config(), diagnostic_config(),
                )
                self.assertEqual("UNIQUE_DIAGNOSTIC", output["status"], output)

    def test_arbitrary_rotation_exposure_and_blur_preserve_subpixel_endpoint_accuracy(self) -> None:
        for midpoint in (1.0, 47.0, 123.0, 237.0, 359.0):
            start, end = (midpoint - 5.0) % 360.0, (midpoint + 5.0) % 360.0
            image = groove_image(start, end, center=CENTER, radius=RADIUS)
            image = np.clip(image * 0.72 + 35.0, 0.0, 255.0)
            image = (
                np.roll(image, 1, 0) + 2 * image + np.roll(image, -1, 0)
                + np.roll(image, 1, 1) + np.roll(image, -1, 1)
            ) / 6.0
            initial = refine(image, start, end)
            output = diagnose_local_second_wall(
                image, CENTER, RADIUS, candidate(start - 2.0, end + 2.0), initial,
                bilinear_sample, parabolic_peak, v2_config(), source_config(), diagnostic_config(),
            )
            self.assertEqual("UNIQUE_DIAGNOSTIC", output["status"], output)
            measured = output["experimentalCandidate"]["openingEndpointProfileDeg"]
            self.assertLess(abs((measured[0] - start + 180.0) % 360.0 - 180.0), 0.15)
            self.assertLess(abs((measured[1] - end + 180.0) % 360.0 - 180.0), 0.15)
            measured_midpoint = (measured[0] + ((measured[1] - measured[0]) % 360.0) / 2.0) % 360.0
            self.assertLess(abs((measured_midpoint - midpoint + 180.0) % 360.0 - 180.0), 0.10)

    def test_asymmetric_partial_fixture_overlap_cannot_form_authoritative_cross_pair(self) -> None:
        true_image = groove_image(170.0, 180.0, center=CENTER, radius=RADIUS)
        true_refinement = refine(true_image, 170.0, 180.0)
        for fixture_contrast in (55.0, 95.0, 135.0):
            with self.subTest(fixture_contrast=fixture_contrast):
                fixture_reference = groove_image(
                    178.0, 202.0, center=CENTER, radius=RADIUS,
                    depth=110.0, contrast=fixture_contrast,
                )
                fixture_refinement = refine(fixture_reference, 178.0, 202.0)
                mixed = {
                    **true_refinement,
                    "endSide": fixture_refinement["endSide"],
                    "openingEndpointProfileDeg": [
                        true_refinement["openingEndpointProfileDeg"][0],
                        fixture_refinement["openingEndpointProfileDeg"][1],
                    ],
                }
                image = dark_features([
                    (170.0, 180.0, 110.0, 170.0),
                    (178.0, 202.0, 42.0, fixture_contrast),
                    (214.0, 228.0, 28.0, min(170.0, fixture_contrast + 25.0)),
                ])
                output = diagnose_local_second_wall(
                    image, CENTER, RADIUS, candidate(168.0, 204.0), mixed,
                    bilinear_sample, parabolic_peak, v2_config(), source_config(), diagnostic_config(),
                )
                self.assertFalse(output["authoritative"])
                self.assertFalse(output["posePromotionAllowed"])
                experimental = output["experimentalCandidate"]
                if experimental is not None:
                    endpoint = experimental["openingEndpointProfileDeg"][1]
                    self.assertLess(abs((endpoint - 180.0 + 180.0) % 360.0 - 180.0), 0.30, output)
                else:
                    self.assertIn(output["errorCode"], {
                        "LOCAL_SECOND_WALL_NOT_FOUND", "MULTIPLE_LOCAL_OPENINGS", "PARTIAL_GROOVE_OBSERVATION",
                    })

    @unittest.skipIf(jsonschema is None, "jsonschema is installed by the explicit Schema gate")
    def test_example_config_and_result_match_versioned_schemas(self) -> None:
        root = Path(__file__).resolve().parents[1]
        config = json.loads(
            (root / "config/local-second-wall-diagnostic.example.json").read_text(encoding="utf-8")
        )
        config_schema = json.loads(
            (root / "contracts/local-second-wall-diagnostic-config.schema.json").read_text(encoding="utf-8")
        )
        result_schema = json.loads(
            (root / "contracts/local-second-wall-diagnostic-result.schema.json").read_text(encoding="utf-8")
        )
        jsonschema.Draft202012Validator.check_schema(config_schema)
        jsonschema.Draft202012Validator.check_schema(result_schema)
        jsonschema.validate(config, config_schema)
        image = groove_image(170.18, 179.72, center=CENTER, radius=RADIUS)
        output = diagnose_local_second_wall(
            image, CENTER, RADIUS, candidate(168.0, 182.0), refine(image, 170.0, 180.0),
            bilinear_sample, parabolic_peak, v2_config(), source_config(),
            diagnostic_config(scan_step_deg=7.0, max_seeds_per_domain=3),
        )
        jsonschema.validate(output, result_schema)


if __name__ == "__main__":
    unittest.main()
