from __future__ import annotations

import math
import unittest

import numpy as np

from algorithms.slot_pose.physical_outer_circle import locate_physical_outer_circle


def polar_resample(gray, center, inner, outer, n_radii, n_angles):
    radii = np.linspace(inner, outer, n_radii)[:, None]
    angles = np.linspace(0.0, 2.0 * math.pi, n_angles, endpoint=False)[None, :]
    xs = np.rint(center[0] + radii * np.cos(angles)).astype(int)
    ys = np.rint(center[1] + radii * np.sin(angles)).astype(int)
    valid = (xs >= 0) & (ys >= 0) & (xs < gray.shape[1]) & (ys < gray.shape[0])
    out = np.zeros(xs.shape, dtype=float)
    out[valid] = gray[ys[valid], xs[valid]]
    return out


def robust_fit(points, fallback):
    pts = np.asarray(points, dtype=float)
    for _ in range(5):
        x, y = pts[:, 0], pts[:, 1]
        a = np.column_stack((2 * x, 2 * y, np.ones(len(pts))))
        cx, cy, c = np.linalg.lstsq(a, x * x + y * y, rcond=None)[0]
        radius = math.sqrt(max(0.0, c + cx * cx + cy * cy))
        residual = np.abs(np.hypot(x - cx, y - cy) - radius)
        keep = residual <= max(3.0, float(np.median(residual)) * 3.0)
        if keep.all() or keep.sum() < 8:
            break
        pts = pts[keep]
    return float(cx), float(cy), float(radius)


def housing_image(*, occluded=False):
    size = 800
    yy, xx = np.indices((size, size))
    cx, cy, radius = 397.0, 403.0, 160.0
    distance = np.hypot(xx - cx, yy - cy)
    image = np.where(distance <= radius, 185.0, 5.0)
    angle = np.degrees(np.arctan2(yy - cy, xx - cx)) % 360.0
    notch = (np.abs((angle - 275.0 + 180.0) % 360.0 - 180.0) < 5.0) & (distance > radius - 24.0)
    image[notch] = 5.0
    if occluded:
        fixture = (xx > cx) & (np.abs((angle + 180.0) % 360.0 - 180.0) < 35.0)
        image[fixture & (distance > radius - 3.0)] = 120.0
    return image, (cx, cy, radius)


class PhysicalOuterCircleTests(unittest.TestCase):
    def test_refines_offset_alignment_circle_with_notch_and_fixture_occlusion(self):
        image, truth = housing_image(occluded=True)
        result = locate_physical_outer_circle(
            image, (truth[0] + 7.0, truth[1] - 5.0), truth[2] - 12.0,
            polar_resample, robust_fit, {},
        )
        self.assertEqual("accepted", result["status"], result)
        circle = result["physicalCircle"]
        self.assertAlmostEqual(truth[0], circle["centerX"], delta=2.0)
        self.assertAlmostEqual(truth[1], circle["centerY"], delta=2.0)
        self.assertAlmostEqual(truth[2], circle["radiusPx"], delta=2.0)
        self.assertGreater(result["angularCoverage"], 0.65)

    def test_blank_frame_fails_without_returning_a_physical_circle(self):
        result = locate_physical_outer_circle(
            np.zeros((300, 300)), (150.0, 150.0), 100.0,
            polar_resample, robust_fit, {},
        )
        self.assertEqual("failed", result["status"])
        self.assertIsNone(result["physicalCircle"])
        self.assertIn("insufficient_edge_points", result["failedChecks"])


if __name__ == "__main__":
    unittest.main()
