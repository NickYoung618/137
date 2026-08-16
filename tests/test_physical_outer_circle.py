from __future__ import annotations

import math
import unittest

import numpy as np

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


class PhysicalOuterCircleTests(unittest.TestCase):
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
