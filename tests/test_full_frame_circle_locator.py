from __future__ import annotations

import math
import unittest

import numpy as np
from PIL import Image, ImageDraw

from algorithms.slot_pose.full_frame_circle_locator import (
    DEFAULT_FULL_FRAME_CIRCLE_LOCATOR_CONFIG,
    extract_component_proposals,
    locate_full_frame_circle,
    merged_full_frame_circle_locator_config,
)


def _disk_image(circles: list[tuple[float, float, float]], size: tuple[int, int] = (512, 384)) -> np.ndarray:
    image = Image.new("L", size, 18)
    draw = ImageDraw.Draw(image)
    for center_x, center_y, radius in circles:
        draw.ellipse(
            (center_x - radius, center_y - radius, center_x + radius, center_y + radius),
            fill=185,
        )
    return np.asarray(image, dtype=float)


def _radial_edge(_gray, center, angle, radius):
    return (
        float(center[0]) + float(radius) * math.cos(float(angle)),
        float(center[1]) + float(radius) * math.sin(float(angle)),
    )


def _fit_circle(points, _prior):
    xy = np.asarray(points, dtype=float)
    center = xy.mean(axis=0)
    radius = float(np.mean(np.hypot(xy[:, 0] - center[0], xy[:, 1] - center[1])))
    return float(center[0]), float(center[1]), radius


class FullFrameCircleConfigTests(unittest.TestCase):
    def test_default_is_disabled_and_strict(self) -> None:
        config = merged_full_frame_circle_locator_config(None)
        self.assertFalse(config["enabled"])
        self.assertEqual("full-frame-circle-locator/1", config["schema_version"])
        for key, value in (
            ("downsample_factor", 1),
            ("max_coarse_candidates", 0),
            ("selection_min_score_margin", math.nan),
            ("allowed_center_normalized", [0.8, 0.1, 0.2, 0.9]),
            ("unexpected", True),
        ):
            candidate = {**DEFAULT_FULL_FRAME_CIRCLE_LOCATOR_CONFIG, key: value}
            with self.subTest(key=key), self.assertRaises(ValueError):
                merged_full_frame_circle_locator_config(candidate)


class ComponentProposalTests(unittest.TestCase):
    def _config(self, **updates):
        return merged_full_frame_circle_locator_config({
            **DEFAULT_FULL_FRAME_CIRCLE_LOCATOR_CONFIG,
            "enabled": True,
            "downsample_factor": 4,
            "allowed_center_normalized": [0.0, 0.0, 1.0, 1.0],
            "min_radius_to_min_image_dim": 0.12,
            "max_radius_to_min_image_dim": 0.48,
            "min_component_area_ratio": 0.02,
            **updates,
        })

    def test_brightness_translation_scale_and_noise_keep_explainable_proposal(self) -> None:
        base = _disk_image([(180, 190, 70)])
        rng = np.random.default_rng(7)
        variants = [
            base,
            np.clip(base * 0.55 + 31.0, 0, 255),
            np.clip(base + rng.normal(0.0, 4.0, base.shape), 0, 255),
            _disk_image([(300, 165, 85)]),
        ]
        expected = [(180, 190, 70), (180, 190, 70), (180, 190, 70), (300, 165, 85)]
        for image, truth in zip(variants, expected):
            with self.subTest(truth=truth):
                proposals = extract_component_proposals(image, self._config())
                eligible = [item for item in proposals if item["status"] == "eligible"]
                self.assertEqual(1, len(eligible), proposals)
                self.assertAlmostEqual(truth[0], eligible[0]["centerX"], delta=6)
                self.assertAlmostEqual(truth[1], eligible[0]["centerY"], delta=6)
                self.assertAlmostEqual(truth[2], eligible[0]["radiusPx"], delta=7)
                self.assertIn("threshold", eligible[0])
                self.assertIn("failedChecks", eligible[0])

    def test_crop_border_and_nonfinite_fail_explainably(self) -> None:
        cropped = _disk_image([(35, 190, 80)])
        proposals = extract_component_proposals(
            cropped, self._config(allow_border_contact=False, min_border_clearance_ratio=0.05),
        )
        self.assertTrue(proposals)
        self.assertTrue(all(item["status"] == "rejected" for item in proposals))
        self.assertTrue(any("border_clearance" in item["failedChecks"] for item in proposals))
        bad = cropped.copy()
        bad[0, 0] = math.nan
        with self.assertRaisesRegex(ValueError, "finite"):
            extract_component_proposals(bad, self._config())


class FullFrameSelectionTests(unittest.TestCase):
    def _config(self, **updates):
        return merged_full_frame_circle_locator_config({
            **DEFAULT_FULL_FRAME_CIRCLE_LOCATOR_CONFIG,
            "enabled": True,
            "downsample_factor": 4,
            "allowed_center_normalized": [0.0, 0.0, 1.0, 1.0],
            "min_radius_to_min_image_dim": 0.10,
            "max_radius_to_min_image_dim": 0.48,
            "min_component_area_ratio": 0.01,
            "selection_min_score_margin": 0.05,
            **updates,
        })

    def test_unique_candidate_delegates_sparse_then_final_and_has_rank(self) -> None:
        calls: list[int] = []

        def edge(gray, center, angle, radius):
            calls.append(1)
            return _radial_edge(gray, center, angle, radius)

        result = locate_full_frame_circle(
            _disk_image([(190, 190, 72)]),
            (200.0, 190.0, 70.0),
            edge,
            _fit_circle,
            self._config(sparse_n_angles=72),
            final_physical_config={
                "n_angles": 144, "min_edge_point_count": 36, "angular_bin_count": 18,
            },
            source_sha256="1" * 64,
        )
        self.assertEqual("accepted", result["status"], result)
        self.assertIsNotNone(result["finalPhysicalCircle"])
        self.assertEqual(1, result["circleCandidates"][0]["rank"])
        self.assertEqual(72 + 144, len(calls))
        self.assertEqual("circle-candidate-001", result["selectedCandidateId"])

    def test_none_overflow_and_equal_double_fail_closed(self) -> None:
        no_circle = locate_full_frame_circle(
            np.full((384, 512), 20.0), (200.0, 190.0, 70.0), _radial_edge, _fit_circle,
            self._config(), final_physical_config=None, source_sha256="2" * 64,
        )
        self.assertEqual("not_found", no_circle["status"])

        two = _disk_image([(130, 190, 55), (365, 190, 55)])
        overflow = locate_full_frame_circle(
            two, (200.0, 190.0, 55.0), _radial_edge, _fit_circle,
            self._config(max_coarse_candidates=1), final_physical_config=None,
            source_sha256="2" * 64,
        )
        self.assertEqual("overflow", overflow["status"])

        ambiguous = locate_full_frame_circle(
            two, (200.0, 190.0, 55.0), _radial_edge, _fit_circle,
            self._config(max_coarse_candidates=4), final_physical_config=None,
            source_sha256="2" * 64,
        )
        self.assertEqual("ambiguous", ambiguous["status"], ambiguous)
        self.assertIsNone(ambiguous["selectedCandidateId"])
        self.assertIsNotNone(ambiguous["secondCandidateId"])


if __name__ == "__main__":
    unittest.main()
