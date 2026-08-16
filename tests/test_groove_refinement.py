from __future__ import annotations

import math
import unittest

import numpy as np

from algorithms.slot_pose.groove_refinement import (
    DEFAULT_GROOVE_REFINEMENT_CONFIG,
    _circle_intersection,
    _robust_fit_line,
    _select_consensus_line,
    refine_groove_opening,
)


def bilinear_sample(gray: np.ndarray, xs: np.ndarray, ys: np.ndarray) -> np.ndarray:
    height, width = gray.shape
    x0 = np.floor(xs).astype(int)
    y0 = np.floor(ys).astype(int)
    x1, y1 = x0 + 1, y0 + 1
    valid = (x0 >= 0) & (y0 >= 0) & (x1 < width) & (y1 < height)
    output = np.full(xs.shape, np.nan, dtype=float)
    dx, dy = xs[valid] - x0[valid], ys[valid] - y0[valid]
    output[valid] = (
        gray[y0[valid], x0[valid]] * (1.0 - dx) * (1.0 - dy)
        + gray[y0[valid], x1[valid]] * dx * (1.0 - dy)
        + gray[y1[valid], x0[valid]] * (1.0 - dx) * dy
        + gray[y1[valid], x1[valid]] * dx * dy
    )
    return output


def parabolic_peak(values: list[float], index: int) -> float:
    if index <= 0 or index >= len(values) - 1:
        return 0.0
    left, center, right = values[index - 1:index + 2]
    denominator = left - 2.0 * center + right
    if abs(denominator) < 1e-12:
        return 0.0
    return max(-1.0, min(1.0, 0.5 * (left - right) / denominator))


def circular_delta(value: float, reference: float) -> float:
    return (value - reference + 180.0) % 360.0 - 180.0


def groove_image(
    start_deg: float,
    end_deg: float,
    *,
    center: tuple[float, float] = (260.35, 251.65),
    radius: float = 185.4,
    depth: float = 110.0,
    contrast: float = 170.0,
) -> np.ndarray:
    yy, xx = np.mgrid[:520, :520].astype(float)
    radial = np.hypot(xx - center[0], yy - center[1])
    angle = np.degrees(np.arctan2(yy - center[1], xx - center[0])) % 360.0
    span = (end_deg - start_deg) % 360.0
    inside_angle = ((angle - start_deg) % 360.0) <= span
    inside_circle = radial <= radius
    inside_groove_depth = radial >= radius - depth
    image = np.full(radial.shape, 25.0, dtype=float)
    image[inside_circle] = 210.0
    image[inside_circle & inside_angle & inside_groove_depth] = 210.0 - contrast
    # A compact separable blur makes the edge continuous and subpixel-sampleable.
    for _ in range(2):
        image = (
            np.roll(image, 1, 0) + 2 * image + np.roll(image, -1, 0)
            + np.roll(image, 1, 1) + np.roll(image, -1, 1)
        ) / 6.0
    return image


def candidate(start: float, end: float) -> dict:
    return {
        "candidateId": "candidate-001",
        "startDeg": start % 360.0,
        "endDeg": end % 360.0,
        "centerDeg": (start + ((end - start) % 360.0) / 2.0) % 360.0,
        "radialDepthPx": 100.0,
    }


def v2_config(**overrides: object) -> dict:
    return {
        **DEFAULT_GROOVE_REFINEMENT_CONFIG,
        "threshold_version": "groove-sidewall-subpixel-v2",
        **overrides,
    }


class GrooveRefinementTests(unittest.TestCase):
    def test_refined_sides_preserve_canonical_local_gray_and_gradient_profiles(self) -> None:
        center, radius = (260.35, 251.65), 185.4
        result = refine_groove_opening(
            groove_image(170.18, 179.72, center=center, radius=radius), center, radius,
            candidate(170.0, 180.0), bilinear_sample, parabolic_peak, v2_config(),
        )
        self.assertEqual("accepted", result["status"], result)
        for side_name in ("startSide", "endSide"):
            evidence = result[side_name]["profileEvidence"]
            self.assertEqual("metal_to_dark", evidence["canonicalDirection"])
            self.assertEqual(
                len(evidence["rawCanonicalGrayProfile"]),
                len(evidence["normalizedCanonicalGrayProfile"]),
            )
            self.assertGreaterEqual(len(evidence["rawCanonicalGrayProfile"]), 9)
            self.assertEqual(
                len(evidence["radialPositionsNormalized"]),
                len(evidence["edgeContrastProfile"]),
            )
            self.assertTrue(all(0.0 <= value <= 1.0 for value in evidence["normalizedCanonicalGrayProfile"]))

    def test_subpixel_sidewalls_intersect_circle_and_recover_midpoint(self) -> None:
        center, radius = (260.35, 251.65), 185.4
        result = refine_groove_opening(
            groove_image(170.18, 179.72, center=center, radius=radius), center, radius,
            candidate(170.0, 180.0), bilinear_sample, parabolic_peak,
            DEFAULT_GROOVE_REFINEMENT_CONFIG,
        )
        self.assertEqual("accepted", result["status"], result)
        self.assertAlmostEqual(174.95, result["openingMidpointProfileDeg"], delta=0.10)
        self.assertEqual(2, len(result["outerCircleIntersections"]))
        self.assertTrue(all(value < 1e-6 for value in result["intersectionCircleResidualPx"]))
        for side in ("startSide", "endSide"):
            self.assertGreaterEqual(result[side]["supportPointCount"], 12)
            self.assertLess(result[side]["lineResidualPx"]["p95"], 2.0)

    def test_wraparound_and_endpoint_order_are_circular(self) -> None:
        center, radius = (260.35, 251.65), 185.4
        image = groove_image(354.75, 5.35, center=center, radius=radius)
        normal = refine_groove_opening(
            image, center, radius, candidate(355.0, 5.0), bilinear_sample, parabolic_peak,
            DEFAULT_GROOVE_REFINEMENT_CONFIG,
        )
        reversed_coarse = refine_groove_opening(
            image, center, radius, candidate(5.0, 355.0), bilinear_sample, parabolic_peak,
            {**DEFAULT_GROOVE_REFINEMENT_CONFIG, "allow_endpoint_reversal": True},
        )
        self.assertEqual("accepted", normal["status"], normal)
        self.assertAlmostEqual(0.05, normal["openingMidpointProfileDeg"], delta=0.10)
        self.assertEqual("accepted", reversed_coarse["status"], reversed_coarse)
        self.assertLess(abs(circular_delta(
            reversed_coarse["openingMidpointProfileDeg"], normal["openingMidpointProfileDeg"]
        )), 0.10)

    def test_weak_or_missing_side_fails_closed(self) -> None:
        center, radius = (260.35, 251.65), 185.4
        cases = {
            "weak": groove_image(170.0, 180.0, center=center, radius=radius, contrast=5.0),
            "missing": np.full((520, 520), 210.0, dtype=float),
        }
        for name, image in cases.items():
            with self.subTest(name=name):
                result = refine_groove_opening(
                    image, center, radius, candidate(170.0, 180.0),
                    bilinear_sample, parabolic_peak, DEFAULT_GROOVE_REFINEMENT_CONFIG,
                )
                self.assertEqual("failed", result["status"])
                self.assertTrue(result["failedChecks"])
                self.assertIsNone(result["openingMidpointProfileDeg"])

    def test_invalid_geometry_and_nonfinite_sampling_fail_closed(self) -> None:
        result = refine_groove_opening(
            np.full((50, 50), np.nan), (25.0, 25.0), 20.0, candidate(10.0, 20.0),
            bilinear_sample, parabolic_peak, DEFAULT_GROOVE_REFINEMENT_CONFIG,
        )
        self.assertEqual("failed", result["status"])
        self.assertIn("invalid_image", result["failedChecks"])

    def test_robust_sidewall_fit_rejects_outliers_and_bad_intersections(self) -> None:
        inliers = [(100.0 + 0.08 * math.sin(index), 20.0 + 4.0 * index) for index in range(24)]
        line, kept, residuals = _robust_fit_line(
            inliers + [(125.0, 40.0), (72.0, 68.0), (138.0, 92.0)],
            minimum=16,
        )
        self.assertLess(len(kept), len(inliers) + 3)
        self.assertLess(float(np.percentile(residuals, 95.0)), 0.15)
        self.assertAlmostEqual(1.0, abs(line[0]), delta=0.01)

        with self.assertRaisesRegex(ValueError, "does not intersect"):
            _circle_intersection((1.0, 0.0, -500.0), (260.0, 250.0), 185.0, 0.0, 2.0)
        with self.assertRaisesRegex(ValueError, "not near coarse boundary"):
            _circle_intersection((1.0, 0.0, -100.0), (260.0, 250.0), 185.0, 0.0, 2.0)

    def test_v2_consensus_keeps_long_straight_core_and_rejects_fillet_points(self) -> None:
        ys = np.linspace(-70.0, 40.0, 20)
        core = [(-50.0 + 0.12 * math.sin(index), float(y)) for index, y in enumerate(ys)]
        fillet_and_texture = [
            (-42.0, -86.0), (-44.0, -81.0), (-45.0, -76.0),
            (-41.0, 44.0), (-43.0, 48.0), (-45.0, 52.0),
        ]
        decision = _select_consensus_line(
            core + fillet_and_texture, minimum=16, center=(0.0, 0.0), outer_radius=100.0,
            coarse_angle_deg=240.0, maximum_delta_deg=3.0, config=v2_config(), pixel_scale=1.0,
        )
        self.assertEqual("accepted", decision["status"], decision)
        self.assertGreaterEqual(decision["inlierCount"], 18)
        self.assertGreaterEqual(decision["longitudinalCoverage"], 0.70)
        self.assertLessEqual(decision["residualP95Px"], 2.0)
        self.assertGreaterEqual(decision["rejectedPointCount"], 5)
        self.assertAlmostEqual(240.0, decision["intersectionAngleDeg"], delta=0.2)

    def test_v2_consensus_rejects_short_support_and_equal_two_line_ambiguity(self) -> None:
        short = [(-50.0 + 0.05 * math.sin(index), float(y)) for index, y in enumerate(np.linspace(-10.0, 10.0, 16))]
        spread = [(-25.0 + 3.0 * index, y) for index, y in enumerate((-80.0, -65.0, -50.0, 35.0, 50.0, 65.0))]
        short_result = _select_consensus_line(
            short + spread, minimum=12, center=(0.0, 0.0), outer_radius=100.0,
            coarse_angle_deg=240.0, maximum_delta_deg=15.0, config=v2_config(), pixel_scale=1.0,
        )
        self.assertEqual("not_found", short_result["status"])

        first = [(-50.0, float(y)) for y in np.linspace(-70.0, 40.0, 16)]
        second = [(-58.0, float(y)) for y in np.linspace(-70.0, 40.0, 16)]
        ambiguous = _select_consensus_line(
            first + second, minimum=12, center=(0.0, 0.0), outer_radius=100.0,
            coarse_angle_deg=240.0, maximum_delta_deg=10.0, config=v2_config(), pixel_scale=1.0,
        )
        self.assertEqual("ambiguous", ambiguous["status"], ambiguous)
        self.assertEqual(0, ambiguous["supportMargin"])

    def test_v2_is_deterministic_wrap_safe_and_emits_explainable_diagnostics(self) -> None:
        center, radius = (260.35, 251.65), 185.4
        image = groove_image(354.75, 5.35, center=center, radius=radius)
        outputs = [
            refine_groove_opening(
                image, center, radius, candidate(355.0, 5.0),
                bilinear_sample, parabolic_peak, v2_config(),
            )
            for _ in range(3)
        ]
        deterministic = [{key: value for key, value in item.items() if key != "elapsedMs"} for item in outputs]
        self.assertTrue(all(item == deterministic[0] for item in deterministic[1:]))
        result = outputs[0]
        self.assertGreaterEqual(result["elapsedMs"], 0.0)
        self.assertEqual("accepted", result["status"], result)
        self.assertEqual("slot-groove-subpixel-opening/2", result["schemaVersion"])
        self.assertAlmostEqual(0.05, result["openingMidpointProfileDeg"], delta=0.10)
        for side_name in ("startSide", "endSide"):
            side = result[side_name]
            self.assertEqual("deterministic-consensus-tls-v2", side["lineFitStrategy"])
            self.assertEqual(side["detectedPointCount"], side["supportPointCount"] + side["rejectedPointCount"])
            self.assertGreaterEqual(side["lineInlierRatio"], 0.5)
            self.assertGreaterEqual(side["lineLongitudinalCoverage"], 0.7)
            self.assertIsNotNone(side["bestModelId"])


if __name__ == "__main__":
    unittest.main()
