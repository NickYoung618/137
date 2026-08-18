from __future__ import annotations

import math
import unittest
from unittest import mock

import numpy as np

from algorithms.slot_pose import physical_outer_circle as physical_module
from algorithms.slot_pose.physical_outer_circle import locate_physical_outer_circle


def algebraic_fit(points, fallback):
    pts = np.asarray(points, dtype=float)
    x, y = pts[:, 0], pts[:, 1]
    a = np.column_stack((2 * x, 2 * y, np.ones(len(pts))))
    cx, cy, c = np.linalg.lstsq(a, x * x + y * y, rcond=None)[0]
    return float(cx), float(cy), math.sqrt(max(0.0, float(c + cx * cx + cy * cy)))


class GyjEdgeProbe:
    def __init__(self, truth, *, missing_sector=None, outlier_sector=None):
        self.truth = truth
        self.missing_sector = missing_sector
        self.outlier_sector = outlier_sector
        self.calls = []

    def __call__(self, gray, center, angle, predicted_radius):
        self.calls.append((gray, center, angle, predicted_radius))
        degrees = math.degrees(angle) % 360.0
        if self.missing_sector and self.missing_sector[0] <= degrees <= self.missing_sector[1]:
            return None
        radius = self.truth[2]
        if self.outlier_sector and self.outlier_sector[0] <= degrees <= self.outlier_sector[1]:
            radius += 35.0
        return self.truth[0] + radius * math.cos(angle), self.truth[1] + radius * math.sin(angle)


class LocalResidualProbe:
    def __init__(self, truth, sectors, offset=7.0):
        self.truth = truth
        self.sectors = sectors
        self.offset = offset

    def __call__(self, gray, center, angle, predicted_radius):
        degrees = math.degrees(angle) % 360.0
        affected = any(
            (start <= degrees <= end if start <= end else degrees >= start or degrees <= end)
            for start, end in self.sectors
        )
        radius = self.truth[2] + (self.offset if affected else 0.0)
        return self.truth[0] + radius * math.cos(angle), self.truth[1] + radius * math.sin(angle)


class FitProbe:
    def __init__(self):
        self.calls = []

    def __call__(self, points, fallback):
        self.calls.append((points, fallback))
        # The real gyj robust fitter removes the injected fixture sector. Keep
        # the test focused on delegation by fitting only the dominant radius.
        cx, cy, _ = fallback
        radii = np.asarray([math.hypot(x - cx, y - cy) for x, y in points])
        median = float(np.median(radii))
        kept = [point for point, radius in zip(points, radii) if abs(radius - median) <= 8.0]
        return algebraic_fit(kept, fallback)


class CandidateProbe:
    def __init__(self, truth, *, missing=(), wrong=()):
        self.truth = truth
        self.missing = set(missing)
        self.wrong = set(wrong)
        self.calls = []

    def __call__(self, gray, center, angle, predicted_radius, **controls):
        index = int(round((math.degrees(angle) % 360.0) / 5.0)) % 72
        self.calls.append((index, controls))
        if index in self.missing:
            return []
        cx, cy, radius = self.truth
        radii = [radius]
        if index in self.wrong:
            radii.append(radius - 45.0)
        return [{
            "x": cx + value * math.cos(angle),
            "y": cy + value * math.sin(angle),
            "radiusPx": value,
            "strength": 20.0,
            "polarity": "bright_to_dark",
            "backgroundPersistenceRatio": 1.0,
        } for value in reversed(radii)]


class PhysicalOuterCircleTests(unittest.TestCase):
    @staticmethod
    def _family_rays(
        circles: list[tuple[float, float, float]], *, n_angles: int = 72,
        active: dict[int, set[int]] | None = None,
    ) -> list[dict]:
        records = []
        for index, angle in enumerate(np.linspace(0.0, 2.0 * math.pi, n_angles, endpoint=False)):
            candidates = []
            for circle_index, (cx, cy, radius) in enumerate(circles):
                if active is not None and index not in active.get(circle_index, set()):
                    continue
                candidates.append({
                    "x": cx + radius * math.cos(angle),
                    "y": cy + radius * math.sin(angle),
                    "radiusPx": radius,
                    "strength": 20.0 + circle_index,
                    "polarity": "bright_to_dark",
                    "backgroundPersistenceRatio": 1.0,
                })
            records.append({"angleIndex": index, "angleRad": float(angle), "candidates": candidates})
        return records

    @staticmethod
    def _intersecting_family_rays(
        circles: list[tuple[float, float, float]], *, search_center=(200.0, 210.0),
        n_angles: int = 72,
    ) -> list[dict]:
        """Build physically valid observations lying on rays from search_center."""
        ox, oy = search_center
        records = []
        for index, angle in enumerate(np.linspace(0.0, 2.0 * math.pi, n_angles, endpoint=False)):
            ux, uy = math.cos(angle), math.sin(angle)
            candidates = []
            for circle_index, (cx, cy, radius) in enumerate(circles):
                dx, dy = cx - ox, cy - oy
                projection = dx * ux + dy * uy
                discriminant = radius * radius - dx * dx - dy * dy + projection * projection
                if discriminant < 0.0:
                    continue
                ray_radius = projection + math.sqrt(discriminant)
                if ray_radius <= 0.0:
                    continue
                candidates.append({
                    "x": ox + ray_radius * ux,
                    "y": oy + ray_radius * uy,
                    "radiusPx": ray_radius,
                    "strength": 20.0 + circle_index,
                    "polarity": "bright_to_dark",
                    "backgroundPersistenceRatio": 1.0,
                })
            records.append({"angleIndex": index, "angleRad": float(angle), "candidates": candidates})
        return records

    def test_global_family_selection_is_deterministic_and_deduplicates_seed_hypotheses(self):
        truth = (200.0, 210.0, 100.0)
        rays = self._family_rays([truth])
        decision, points, angle_indices = physical_module.select_circle_edge_family(
            rays, search=truth, n_angles=72,
            config={"enabled": True, "min_support_ratio": 0.75, "min_angular_coverage": 0.65},
            scale=1.0, max_center_shift_px=80.0,
            min_radius_ratio=0.94, max_radius_ratio=1.10,
        )
        self.assertEqual("selected", decision["status"], decision)
        self.assertEqual(1, decision["familyCount"])
        self.assertEqual(1, decision["qualifiedFamilyCount"])
        self.assertEqual(72, len(points))
        self.assertEqual(list(range(72)), angle_indices.tolist())
        self.assertGreater(decision["families"][0]["memberHypothesisCount"], 1)

        reordered = [
            {**record, "candidates": list(reversed(record["candidates"]))}
            for record in reversed(rays)
        ]
        again, again_points, _ = physical_module.select_circle_edge_family(
            reordered, search=truth, n_angles=72,
            config={"enabled": True, "min_support_ratio": 0.75, "min_angular_coverage": 0.65},
            scale=1.0, max_center_shift_px=80.0,
            min_radius_ratio=0.94, max_radius_ratio=1.10,
        )
        self.assertEqual("selected", again["status"])
        self.assertEqual(decision["families"], again["families"])
        self.assertTrue(np.allclose(points, again_points))

    def test_v2_consolidates_all_group_members_and_is_candidate_order_invariant(self):
        truth = (200.0, 210.0, 100.0)
        rays = self._family_rays([truth])
        config = {
            "enabled": True,
            "strategy_version": physical_module.EDGE_FAMILY_STRATEGY_V2,
            "min_support_ratio": 0.75,
            "min_angular_coverage": 0.65,
        }
        decision, points, indices = physical_module.select_circle_edge_family(
            rays, search=truth, n_angles=72, config=config, scale=1.0,
            max_center_shift_px=80.0, min_radius_ratio=0.94, max_radius_ratio=1.10,
        )
        self.assertEqual("selected", decision["status"], decision)
        family = decision["families"][0]
        consensus = family["consensus"]
        self.assertEqual("physical-circle-family-consensus/1", consensus["schemaVersion"])
        self.assertEqual("converged", consensus["status"])
        self.assertTrue(consensus["converged"])
        self.assertGreater(consensus["memberHypothesisCount"], 1)
        self.assertLessEqual(consensus["iterationCount"], consensus["maxIterations"])
        self.assertEqual(72, len(points))
        self.assertEqual(list(range(72)), indices.tolist())

        reordered = [
            {**record, "candidates": list(reversed(record["candidates"]))}
            for record in reversed(rays)
        ]
        again, again_points, again_indices = physical_module.select_circle_edge_family(
            reordered, search=truth, n_angles=72, config=config, scale=1.0,
            max_center_shift_px=80.0, min_radius_ratio=0.94, max_radius_ratio=1.10,
        )
        self.assertEqual(decision["families"], again["families"])
        self.assertTrue(np.array_equal(indices, again_indices))
        self.assertTrue(np.allclose(points, again_points))

    def test_v1_keeps_legacy_family_summary_without_consensus(self):
        truth = (200.0, 210.0, 100.0)
        decision, _, _ = physical_module.select_circle_edge_family(
            self._family_rays([truth]), search=truth, n_angles=72,
            config={"enabled": True, "strategy_version": physical_module.EDGE_FAMILY_STRATEGY_V1},
            scale=1.0, max_center_shift_px=80.0,
            min_radius_ratio=0.94, max_radius_ratio=1.10,
        )
        self.assertEqual("selected", decision["status"])
        self.assertNotIn("consensus", decision["families"][0])

    def test_v2_preserves_v1_assignments_when_existing_residual_gate_passes(self):
        truth = (200.0, 210.0, 100.0)
        rays = self._family_rays([truth])
        common = dict(
            search=truth, n_angles=72, scale=1.0, max_center_shift_px=80.0,
            min_radius_ratio=0.94, max_radius_ratio=1.10,
        )
        legacy, legacy_points, legacy_indices = physical_module.select_circle_edge_family(
            rays, config={"enabled": True}, **common,
        )
        decision, points, indices = physical_module.select_circle_edge_family(
            rays,
            config={
                "enabled": True,
                "strategy_version": physical_module.EDGE_FAMILY_STRATEGY_V2,
            },
            consensus_trigger_residual_p95_px=5.0,
            **common,
        )
        consensus = decision["families"][0]["consensus"]
        self.assertEqual("not_needed", consensus["status"])
        self.assertFalse(consensus["applied"])
        self.assertEqual(legacy["families"][0]["circle"], decision["families"][0]["circle"])
        self.assertTrue(np.array_equal(legacy_indices, indices))
        self.assertTrue(np.array_equal(legacy_points, points))

    def test_v2_corrects_a_biased_adjacent_edge_representative_from_member_consensus(self):
        truth = (200.0, 210.0, 100.0)
        angles = np.linspace(0.0, 2.0 * math.pi, 12, endpoint=False)
        candidate_x = np.column_stack([
            truth[0] + truth[2] * np.cos(angles),
            truth[0] + 96.0 * np.cos(angles),
        ])
        candidate_y = np.column_stack([
            truth[1] + truth[2] * np.sin(angles),
            truth[1] + 96.0 * np.sin(angles),
        ])
        biased_points = np.column_stack((candidate_x[:, 1], candidate_y[:, 1]))
        indices = np.arange(12, dtype=int)
        family = {
            "circle": (200.0, 210.0, 96.0),
            "points": biased_points,
            "indices": indices,
            "assignmentByRay": {
                int(ray): point for ray, point in zip(indices, biased_points)
            },
            "support": 12,
            "coverage": 1.0,
            "median": 2.0,
            "p95": 6.0,
            "failed": [],
            "memberCount": 3,
            "_members": [
                {"circle": (200.0, 210.0, 99.8)},
                {"circle": truth},
                {"circle": (200.2, 209.9, 100.1)},
            ],
        }
        result = physical_module._consolidate_family_consensus(
            family, candidate_x, candidate_y, gate=8.0,
            n_angles=12, angular_bin_count=12, minimum_support=10,
            preliminary_residual_gate=8.0, trigger_residual_gate=5.0,
            config={"min_angular_coverage": 0.8}, search=truth,
            center_limit=80.0, min_radius_ratio=0.94, max_radius_ratio=1.10,
        )
        self.assertEqual("converged", result["consensus"]["status"])
        self.assertTrue(result["consensus"]["applied"])
        self.assertEqual(6.0, result["consensus"]["originalResidualP95Px"])
        self.assertTrue(np.allclose(candidate_x[:, 0], result["points"][:, 0]))
        self.assertTrue(np.allclose(candidate_y[:, 0], result["points"][:, 1]))
        self.assertAlmostEqual(100.0, result["circle"][2], places=9)

    def test_v2_nonconvergent_assignments_are_rejected_at_fixed_bound(self):
        truth = (200.0, 210.0, 100.0)
        family = {
            "circle": truth, "points": np.empty((0, 2)), "indices": np.asarray([], dtype=int),
            "assignmentByRay": {}, "support": 0, "coverage": 0.0,
            "median": 0.0, "p95": 0.0, "failed": [], "memberCount": 1,
            "_members": [{"circle": truth}],
        }
        first_points = np.asarray([[300.0, 210.0], [200.0, 310.0], [100.0, 210.0]])
        second_points = np.asarray([[301.0, 210.0], [200.0, 311.0], [99.0, 210.0]])
        indices = np.asarray([0, 1, 2], dtype=int)
        assignments = [(first_points, indices)]
        for iteration in range(physical_module.FAMILY_CONSENSUS_MAX_ITERATIONS):
            assignments.append((second_points if iteration % 2 == 0 else first_points, indices))
        with mock.patch.object(
            physical_module, "_assign_family_candidates", side_effect=assignments,
        ), mock.patch.object(
            physical_module, "_algebraic_hypothesis_fit", return_value=truth,
        ):
            result = physical_module._consolidate_family_consensus(
                family, np.zeros((3, 1)), np.zeros((3, 1)), gate=8.0,
                n_angles=3, angular_bin_count=3, minimum_support=3,
                preliminary_residual_gate=8.0,
                trigger_residual_gate=0.0,
                config={"min_angular_coverage": 0.5}, search=truth,
                center_limit=80.0, min_radius_ratio=0.94, max_radius_ratio=1.10,
            )
        consensus = result["consensus"]
        self.assertFalse(consensus["converged"])
        self.assertEqual(
            physical_module.FAMILY_CONSENSUS_MAX_ITERATIONS,
            consensus["iterationCount"],
        )
        self.assertIn("family_consensus_not_converged", result["failed"])

    def test_global_family_selection_ignores_sparse_wrong_family_without_interpolation(self):
        truth = (200.0, 210.0, 100.0)
        wrong = (200.0, 210.0, 95.0)
        active = {0: set(range(72)) - set(range(20, 28)), 1: set(range(8))}
        decision, points, angle_indices = physical_module.select_circle_edge_family(
            self._family_rays([truth, wrong], active=active),
            search=truth, n_angles=72,
            config={"enabled": True, "min_support_ratio": 0.70, "min_angular_coverage": 0.65},
            scale=1.0, max_center_shift_px=80.0,
            min_radius_ratio=0.94, max_radius_ratio=1.10,
        )
        self.assertEqual("selected", decision["status"], decision)
        self.assertEqual(64, len(points))
        self.assertEqual(set(range(72)) - set(range(20, 28)), set(angle_indices.tolist()))

    def test_zero_and_multiple_eligible_families_fail_closed(self):
        search = (200.0, 210.0, 100.0)
        empty, points, indices = physical_module.select_circle_edge_family(
            [], search=search, n_angles=72, config={"enabled": True}, scale=1.0,
            max_center_shift_px=80.0, min_radius_ratio=0.94, max_radius_ratio=1.10,
        )
        self.assertEqual("no_family", empty["status"])
        self.assertEqual(["no_qualified_edge_family"], empty["failedChecks"])
        self.assertEqual(0, len(points))
        self.assertEqual(0, len(indices))

        concentric = [(200.0, 210.0, 95.0), (200.0, 210.0, 109.0)]
        ambiguous, points, indices = physical_module.select_circle_edge_family(
            self._intersecting_family_rays(concentric), search=search, n_angles=72,
            config={
                "enabled": True, "assignment_residual_px": 2.0,
                "min_support_ratio": 0.75, "min_angular_coverage": 0.65,
            },
            scale=1.0, max_center_shift_px=80.0,
            min_radius_ratio=0.94, max_radius_ratio=1.10,
        )
        self.assertEqual("ambiguous", ambiguous["status"], ambiguous)
        self.assertEqual(2, ambiguous["qualifiedFamilyCount"])
        self.assertEqual(["ambiguous_edge_families"], ambiguous["failedChecks"])
        self.assertEqual(0, len(points))
        self.assertEqual(0, len(indices))

    def test_nonconcentric_multiple_families_and_bounded_overflow_fail_closed(self):
        search = (200.0, 210.0, 100.0)
        circles = [(190.0, 210.0, 98.0), (215.0, 210.0, 102.0)]
        rays = self._intersecting_family_rays(circles)
        ambiguous, _, _ = physical_module.select_circle_edge_family(
            rays, search=search, n_angles=72,
            config={
                "enabled": True, "assignment_residual_px": 2.0,
                "dedup_center_px": 4.0, "dedup_radius_px": 4.0,
                "min_support_ratio": 0.75, "min_angular_coverage": 0.65,
            },
            scale=1.0, max_center_shift_px=80.0,
            min_radius_ratio=0.94, max_radius_ratio=1.10,
        )
        self.assertEqual("ambiguous", ambiguous["status"], ambiguous)

        overflow, points, _ = physical_module.select_circle_edge_family(
            rays, search=search, n_angles=72,
            config={"enabled": True, "max_seed_count": 8, "max_hypotheses": 8},
            scale=1.0, max_center_shift_px=80.0,
            min_radius_ratio=0.94, max_radius_ratio=1.10,
        )
        self.assertEqual("overflow", overflow["status"])
        self.assertEqual(["family_search_overflow"], overflow["failedChecks"])
        self.assertEqual(0, len(points))

    def test_nonfinite_candidate_evidence_is_rejected(self):
        rays = self._family_rays([(200.0, 210.0, 100.0)])
        rays[7]["candidates"][0]["x"] = math.nan
        decision, points, indices = physical_module.select_circle_edge_family(
            rays, search=(200.0, 210.0, 100.0), n_angles=72,
            config={"enabled": True}, scale=1.0, max_center_shift_px=80.0,
            min_radius_ratio=0.94, max_radius_ratio=1.10,
        )
        self.assertEqual("invalid", decision["status"])
        self.assertEqual(["invalid_edge_family_evidence"], decision["failedChecks"])
        self.assertEqual(0, len(points))
        self.assertEqual(0, len(indices))

    def test_short_support_and_low_angular_coverage_do_not_form_a_family(self):
        truth = (200.0, 210.0, 100.0)
        cases = {
            "short_support": set(range(24)),
            "low_coverage": set(range(50)),
        }
        for name, active_indices in cases.items():
            with self.subTest(name=name):
                rays = self._family_rays([truth], active={0: active_indices})
                decision, points, indices = physical_module.select_circle_edge_family(
                    rays, search=truth, n_angles=72,
                    config={
                        "enabled": True, "min_support_ratio": 0.55,
                        "min_angular_coverage": 0.75,
                    },
                    scale=1.0, max_center_shift_px=80.0,
                    min_radius_ratio=0.94, max_radius_ratio=1.10,
                )
                self.assertEqual("no_family", decision["status"], decision)
                self.assertEqual(["no_qualified_edge_family"], decision["failedChecks"])
                self.assertEqual(0, len(points))
                self.assertEqual(0, len(indices))

    def test_enabled_family_path_samples_once_and_robust_fits_only_unique_winner(self):
        truth = (200.0, 210.0, 100.0)
        candidates = CandidateProbe(truth, missing=range(20, 24), wrong=range(4, 12))
        fit = FitProbe()
        legacy_calls = []

        def forbidden_legacy(*args):
            legacy_calls.append(args)
            return None

        result = locate_physical_outer_circle(
            np.zeros((500, 500)), truth[:2], truth[2], truth[:2], truth[2],
            forbidden_legacy, fit,
            {
                "n_angles": 72, "min_edge_point_count": 45, "angular_bin_count": 12,
                "edge_family_selection": {
                    "enabled": True, "min_support_ratio": 0.70,
                    "min_angular_coverage": 0.65,
                },
            },
            source_sha256="9" * 64,
            outer_boundary_edge_candidates=candidates,
        )
        self.assertEqual("accepted", result["status"], result)
        self.assertEqual([], legacy_calls)
        self.assertEqual(72, len(candidates.calls))
        self.assertTrue(all(call[1]["max_peaks"] == 8 for call in candidates.calls))
        self.assertEqual(1, len(fit.calls))
        self.assertEqual(68, result["edgePointCount"])
        self.assertEqual("selected", result["edgeFamilySelection"]["status"])
        self.assertEqual(1, result["edgeFamilySelection"]["qualifiedFamilyCount"])

    def test_delegates_all_edge_decisions_and_fit_to_locked_gyj_functions(self):
        truth = (397.0, 403.0, 160.0)
        edge = GyjEdgeProbe(truth, missing_sector=(270.0, 280.0), outlier_sector=(0.0, 25.0))
        fit = FitProbe()
        result = locate_physical_outer_circle(
            np.zeros((800, 800)),
            alignment_center=(truth[0] + 7.0, truth[1] - 5.0),
            alignment_radius_px=truth[2] - 12.0,
            search_center=(truth[0], truth[1]),
            search_radius_px=truth[2] - 12.0,
            outer_boundary_edge_point=edge,
            robust_fit_circle=fit,
            config={},
            source_sha256="a" * 64,
        )
        self.assertEqual("accepted", result["status"], result)
        self.assertEqual(720, len(edge.calls))
        self.assertEqual(1, len(fit.calls))
        self.assertEqual("gyj.outer_boundary_edge_point+robust_fit_circle", result["sourceAlgorithm"])
        self.assertEqual("a" * 64, result["sourceSha256"])
        circle = result["physicalCircle"]
        self.assertAlmostEqual(truth[0], circle["centerX"], delta=1e-6)
        self.assertAlmostEqual(truth[1], circle["centerY"], delta=1e-6)
        self.assertAlmostEqual(truth[2], circle["radiusPx"], delta=1e-6)
        empty = [item for item in result["sectorEvidence"]["sectors"] if item["pointCount"] == 0]
        self.assertTrue(empty)
        self.assertTrue(all(item["residualP95Px"] is None for item in empty))

    def test_insufficient_gyj_edge_points_fails_without_fitting_or_fallback_circle(self):
        calls = []

        def no_edge(*args):
            return None

        def forbidden_fit(*args):
            calls.append(args)
            return 150.0, 150.0, 100.0

        result = locate_physical_outer_circle(
            np.zeros((300, 300)), (150.0, 150.0), 100.0, (150.0, 150.0), 100.0,
            no_edge, forbidden_fit, {}, source_sha256="b" * 64,
        )
        self.assertEqual("failed", result["status"])
        self.assertIsNone(result["physicalCircle"])
        self.assertEqual([], calls)
        self.assertIn("insufficient_edge_points", result["failedChecks"])

    def test_sector_evidence_is_emitted_while_recovery_is_default_off(self):
        truth = (200.0, 210.0, 100.0)
        result = locate_physical_outer_circle(
            np.zeros((500, 500)), truth[:2], truth[2], truth[:2], truth[2],
            LocalResidualProbe(truth, [(30.0, 50.0)]),
            lambda points, fallback: truth,
            {}, source_sha256="c" * 64,
        )
        self.assertEqual("failed", result["status"])
        self.assertEqual(["residual_p95"], result["failedChecks"])
        self.assertEqual(36, result["sectorEvidence"]["binCount"])
        self.assertGreater(result["sectorEvidence"]["suspectSectorCount"], 0)
        self.assertEqual("disabled", result["robustRefit"]["status"])
        self.assertAlmostEqual(5.0, result["residualThresholdPx"])
        self.assertLess(result["residualMarginPx"], 0.0)

    def test_bounded_local_sector_exclusion_can_recover_residual_only_failure(self):
        truth = (200.0, 210.0, 100.0)
        result = locate_physical_outer_circle(
            np.zeros((500, 500)), truth[:2], truth[2], truth[:2], truth[2],
            LocalResidualProbe(truth, [(30.0, 50.0)]),
            lambda points, fallback: truth,
            {"sector_robustness": {"enabled": True}}, source_sha256="d" * 64,
        )
        self.assertEqual("accepted", result["status"], result)
        self.assertEqual([], result["failedChecks"])
        self.assertEqual("accepted", result["robustRefit"]["status"])
        self.assertGreater(result["robustRefit"]["excludedPointCount"], 0)
        self.assertLessEqual(result["residualP95Px"], 5.0)

    def test_distributed_bad_sectors_remain_fail_closed(self):
        truth = (200.0, 210.0, 100.0)
        result = locate_physical_outer_circle(
            np.zeros((500, 500)), truth[:2], truth[2], truth[:2], truth[2],
            LocalResidualProbe(truth, [(0.0, 10.0), (60.0, 70.0), (120.0, 130.0),
                                       (180.0, 190.0), (240.0, 250.0)]),
            lambda points, fallback: truth,
            {"sector_robustness": {"enabled": True}}, source_sha256="e" * 64,
        )
        self.assertEqual("failed", result["status"])
        self.assertIn("residual_p95", result["failedChecks"])
        self.assertEqual("rejected", result["robustRefit"]["status"])
        self.assertIn("too_many_suspect_sectors", result["robustRefit"]["reasons"])
        self.assertAlmostEqual(5.0, result["residualThresholdPx"])
        self.assertLess(result["residualMarginPx"], 0.0)
        self.assertEqual(36, result["sectorEvidence"]["binCount"])
        self.assertGreater(
            result["sectorEvidence"]["suspectSectorCount"],
            physical_module.DEFAULT_SECTOR_ROBUSTNESS_CONFIG["max_excluded_sector_count"],
        )

    def test_sector_runs_merge_across_zero_degrees(self):
        truth = (200.0, 210.0, 100.0)
        result = locate_physical_outer_circle(
            np.zeros((500, 500)), truth[:2], truth[2], truth[:2], truth[2],
            LocalResidualProbe(truth, [(350.0, 10.0)]),
            lambda points, fallback: truth,
            {}, source_sha256="f" * 64,
        )
        runs = result["sectorEvidence"]["suspectRuns"]
        self.assertEqual(1, len(runs), runs)
        self.assertTrue(runs[0]["wrapsBoundary"])

    def test_wraparound_local_pollution_can_be_recovered_once(self):
        truth = (200.0, 210.0, 100.0)
        result = locate_physical_outer_circle(
            np.zeros((500, 500)), truth[:2], truth[2], truth[:2], truth[2],
            LocalResidualProbe(truth, [(350.0, 10.0)]),
            lambda points, fallback: truth,
            {"sector_robustness": {"enabled": True}}, source_sha256="1" * 64,
        )
        self.assertEqual("accepted", result["status"], result)
        self.assertEqual("accepted", result["robustRefit"]["status"])

    def test_recovery_rejects_insufficient_retained_coverage(self):
        truth = (200.0, 210.0, 100.0)

        def edge(gray, center, angle, predicted_radius):
            degrees = math.degrees(angle) % 360.0
            if 100.0 <= degrees <= 195.0:
                return None
            radius = truth[2] + (7.0 if 30.0 <= degrees <= 50.0 else 0.0)
            return truth[0] + radius * math.cos(angle), truth[1] + radius * math.sin(angle)

        result = locate_physical_outer_circle(
            np.zeros((500, 500)), truth[:2], truth[2], truth[:2], truth[2], edge,
            lambda points, fallback: truth,
            {"sector_robustness": {"enabled": True}}, source_sha256="2" * 64,
        )
        self.assertEqual("failed", result["status"])
        self.assertEqual("rejected", result["robustRefit"]["status"])
        self.assertIn("retained_coverage", result["robustRefit"]["reasons"])

    def test_recovery_rejects_refit_circle_drift(self):
        truth = (200.0, 210.0, 100.0)
        calls = []

        def drifting_fit(points, fallback):
            calls.append(len(points))
            return truth if len(calls) == 1 else (truth[0] + 4.0, truth[1], truth[2])

        result = locate_physical_outer_circle(
            np.zeros((500, 500)), truth[:2], truth[2], truth[:2], truth[2],
            LocalResidualProbe(truth, [(30.0, 50.0)]), drifting_fit,
            {"sector_robustness": {"enabled": True}}, source_sha256="3" * 64,
        )
        self.assertEqual("failed", result["status"])
        self.assertEqual(2, len(calls))
        self.assertIn("refit_center_delta", result["robustRefit"]["reasons"])


if __name__ == "__main__":
    unittest.main()
