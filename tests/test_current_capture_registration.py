import json
import math
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
from PIL import Image, ImageDraw

from algorithms.hole_2.main import (
    BoundaryDetection,
    ReferenceModel,
    ShapeModel,
    build_reference,
    extract_image,
    gaussian_blur,
)
from algorithms.hole_2.current_capture import (
    SimilarityTransform,
    _detect_d7_tangent,
    _d7_multiband_recovery,
    _detect_phi12_2,
    _paired_contour_boundary,
    _ransac_circle,
    _v6_d7_fallback,
    evaluate_geometry_consistency,
    fit_similarity_transform,
    load_registration_config,
    register_current_capture,
)


def _circle_points(cx: float, cy: float, radius: float, count: int = 72):
    return [
        [cx + radius * math.cos(a), cy + radius * math.sin(a)]
        for a in np.linspace(0.0, 2.0 * math.pi, count, endpoint=False)
    ]


def _synthetic_reference(root: Path):
    size = (360, 300)
    groups = [
        ("main-a", 160.0, 130.0, 18.0),
        ("main-b", 160.0, 130.0, 34.0),
        ("main-c", 160.0, 130.0, 52.0),
        ("ear", 160.0, 45.0, 12.0),
        ("left", 70.0, 215.0, 15.0),
        ("right", 255.0, 225.0, 16.0),
    ]
    image = Image.new("L", size, 20)
    draw = ImageDraw.Draw(image)
    shapes = []
    for label, cx, cy, radius in groups:
        draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), outline=235, width=3)
        shapes.append({
            "label": label,
            "shape_type": "linestrip",
            "points": _circle_points(cx, cy, radius),
        })
    image_path = root / "reference.bmp"
    label_path = root / "annotation.json"
    image.save(image_path)
    label_path.write_text(json.dumps({"imagePath": image_path.name, "shapes": shapes}), encoding="utf-8")
    return build_reference(label_path, image_path), groups


def _render_transformed(groups, transform: SimilarityTransform, path: Path, include_outer=True):
    image = Image.new("L", (420, 420), 20)
    draw = ImageDraw.Draw(image)
    selected = groups if include_outer else groups[:3]
    for _, cx, cy, radius in selected:
        tx, ty = transform.forward(cx, cy)
        tr = transform.scale * radius
        draw.ellipse((tx - tr, ty - tr, tx + tr, ty + tr), outline=235, width=3)
    image.save(path)
    return np.asarray(image, dtype=np.float64)


def _render_inconsistent_anchors(groups, transform: SimilarityTransform, path: Path):
    """Keep the primary ring but place every outer support at a wrong pose."""
    image = Image.new("L", (420, 420), 20)
    draw = ImageDraw.Draw(image)
    for _, cx, cy, radius in groups[:3]:
        tx, ty = transform.forward(cx, cy)
        tr = transform.scale * radius
        draw.ellipse((tx - tr, ty - tr, tx + tr, ty + tr), outline=235, width=3)
    wrong_offsets = [(-72.0, 64.0), (78.0, -70.0), (68.0, 76.0)]
    for (_, cx, cy, radius), (ox, oy) in zip(groups[3:], wrong_offsets):
        tx, ty = transform.forward(cx, cy)
        tr = transform.scale * radius
        draw.ellipse((tx + ox - tr, ty + oy - tr, tx + ox + tr, ty + oy + tr), outline=235, width=3)
    image.save(path)
    return np.asarray(image, dtype=np.float64)


def _centered_transform(orientation: float) -> SimilarityTransform:
    theta = math.radians(orientation)
    cx, cy = 160.0, 130.0
    rx = math.cos(theta) * cx - math.sin(theta) * cy
    ry = math.sin(theta) * cx + math.cos(theta) * cy
    return SimilarityTransform(210.0 - rx, 210.0 - ry, 1.0, orientation)


def _test_config():
    return {
        "schema_version": "hole2-current-capture-registration-config/1",
        "config_version": "synthetic-v1",
        "orientations_deg": [0, 90, 180, 270],
        "coarse": {
            "downsample": 2, "scale_min": 0.85, "scale_max": 1.15,
            "scale_step": 0.05, "max_peaks_per_scale": 2,
            "max_global_hypotheses": 2, "nonmaximum_distance_px": 30.0,
        },
        "supports": {
            "reference_cluster_distance_px": 24.0, "downsample": 1,
            "search_radius_target_px": 16.0, "search_step_target_px": 2.0,
            "refine_search_radius_target_px": 6.0, "min_visible_fraction": 0.60,
            "min_edge_peak_normalized": 0.20,
            "min_edge_prominence_normalized": 0.08,
            "offset_saturation_fraction": 0.95,
        },
        "quality": {
            "min_support_groups": 3, "min_spatial_coverage": 0.10,
            "max_fine_angle_deg": 8.0, "min_scale": 0.75, "max_scale": 1.25,
            "max_scale_change_from_coarse_fraction": 0.20,
            "max_median_residual_px": 6.0, "max_residual_px": 12.0,
            "min_candidate_score_margin": 0.25,
            "max_roundtrip_error_px": 0.001,
        },
        "registration_recovery": {
            "enabled": True,
            "refine_search_radius_target_px": 32.0,
        },
        "d7": {
            "max_reference_tangent_error_px": 4.0,
            "max_axis_shift_target_px": 20.0,
            "min_boundary_points": 12,
            "max_fit_residual_target_px": 3.0,
            "min_edge_score": 4.0,
            "max_boundary_parallelism_deg": 12.0,
            "band_offsets_target_px": [-12.0, 0.0, 12.0],
            "band_strip_half_width_px": 6,
            "band_strip_samples": 13,
            "min_consistent_bands": 3,
            "max_cross_band_length_deviation_px": 3.0,
            "paired_edge_min_width_target_px": 3.0,
            "paired_edge_max_width_target_px": 16.0,
            "paired_edge_min_peak": 4.0,
            "paired_edge_prior_sigma_px": 14.0,
            "paired_edge_strip_half_width_px": 6,
            "paired_edge_strip_samples": 13,
            "paired_edge_min_support": 12,
        },
        "phi12_2": {
            "search_radius_px": 20, "min_radius_scale_ratio": 0.88,
            "recovery_min_radius_scale_ratio": 0.84,
            "max_radius_scale_ratio": 1.08, "min_edge_points": 20,
            "max_fit_residual_target_px": 3.0,
            "center_recovery_search_radius_px": 16.0,
            "multicircle_radial_search_width_px": 12,
            "multicircle_ransac_trials": 48,
            "multicircle_ransac_inlier_residual_px": 3.0,
            "min_angle_coverage_fraction": 0.65,
            "phase_profile_half_width_px": 12,
            "phase_profile_smooth_window": 5,
            "phase_angle_extension_deg": 5.0,
            "phase_min_contrast": 12.0,
            "phase_min_edge_score": 4.0,
            "phase_min_points": 20,
            "phase_ransac_trials": 48,
            "phase_ransac_inlier_residual_px": 3.0,
        },
        "geometry_consistency": {
            "max_reference_ratio_absolute_deviation": 0.08,
        },
    }


class CurrentCaptureRegistrationTests(unittest.TestCase):
    def test_phi_reference_phase_refines_same_positive_physical_edge(self):
        angles = np.linspace(0.0, 2.0 * math.pi, 160, endpoint=False)
        reference_gray = np.full((220, 220), 220.0)
        yy, xx = np.indices(reference_gray.shape)
        reference_gray[np.hypot(xx - 100.0, yy - 100.0) <= 40.0] = 20.0
        reference_gray = gaussian_blur(reference_gray, 1.0)
        phi = ShapeModel(
            index=0, label="Φ12.2", sanitized="Phi12_2", kind="circle",
            points=[(100.0 + 40.0 * math.cos(a), 100.0 + 40.0 * math.sin(a)) for a in angles],
            circle=(100.0, 100.0, 40.0), angle_start=0.0,
            angle_end=2.0 * math.pi, polarity=100.0, template_angles=angles,
        )
        reference = ReferenceModel(
            {}, Path("synthetic.bmp"), reference_gray, [phi], []
        )
        target = np.full((220, 220), 220.0)
        target[np.hypot(xx - 105.0, yy - 107.0) <= 36.0] = 20.0
        target = gaussian_blur(target, 1.0)
        config = _test_config()
        config["phi12_2"].update({
            "search_radius_px": 16, "center_search_step_px": 2,
            "radius_search_step_px": 1, "refine_step_px": 0.5,
            "min_edge_peak_normalized": 0.15,
            "min_edge_prominence_normalized": 0.05,
            "boundary_saturation_fraction": 0.95,
            "phase_angle_extension_deg": 0.0,
        })
        values, quality = _detect_phi12_2(
            target, reference, SimilarityTransform(0.0, 0.0, 1.0, 0.0), config
        )
        self.assertIsNotNone(values, quality)
        self.assertAlmostEqual(105.0, values["Phi12_2_cx"], delta=0.8)
        self.assertAlmostEqual(107.0, values["Phi12_2_cy"], delta=0.8)
        self.assertAlmostEqual(36.0, values["Phi12_2_r"], delta=0.8)
        self.assertTrue(quality["candidate_polarity_enforced"])
        self.assertEqual(
            "reference_phase_outer_polarity_edge", quality["candidate_edge_semantics"]
        )
        self.assertGreaterEqual(quality["candidate_phase_edge_points"], 20)

    def test_phi_reference_phase_rejects_opposite_target_polarity(self):
        angles = np.linspace(0.0, 2.0 * math.pi, 160, endpoint=False)
        yy, xx = np.indices((220, 220))
        reference_gray = np.full((220, 220), 220.0)
        reference_gray[np.hypot(xx - 100.0, yy - 100.0) <= 40.0] = 20.0
        reference_gray = gaussian_blur(reference_gray, 1.0)
        phi = ShapeModel(
            index=0, label="Φ12.2", sanitized="Phi12_2", kind="circle",
            points=[], circle=(100.0, 100.0, 40.0), angle_start=0.0,
            angle_end=2.0 * math.pi, polarity=100.0, template_angles=angles,
        )
        reference = ReferenceModel({}, Path("synthetic.bmp"), reference_gray, [phi], [])
        target = np.full((220, 220), 20.0)
        target[np.hypot(xx - 100.0, yy - 100.0) <= 40.0] = 220.0
        target = gaussian_blur(target, 1.0)
        config = _test_config()
        config["phi12_2"].update({
            "search_radius_px": 12, "center_search_step_px": 2,
            "radius_search_step_px": 1, "refine_step_px": 0.5,
            "min_edge_peak_normalized": 0.15,
            "min_edge_prominence_normalized": 0.05,
            "boundary_saturation_fraction": 0.95,
            "phase_angle_extension_deg": 0.0,
        })
        values, quality = _detect_phi12_2(
            target, reference, SimilarityTransform(0.0, 0.0, 1.0, 0.0), config
        )
        self.assertIsNone(values)
        self.assertIn("phase", quality["candidate_failure"])
        self.assertTrue(quality["candidate_polarity_enforced"])

    def test_phi_phase_evidence_does_not_reuse_legacy_normalized_peak_gate(self):
        angles = np.linspace(0.0, 2.0 * math.pi, 160, endpoint=False)
        yy, xx = np.indices((220, 220))
        reference_gray = np.full((220, 220), 220.0)
        reference_gray[np.hypot(xx - 100.0, yy - 100.0) <= 40.0] = 20.0
        reference_gray = gaussian_blur(reference_gray, 1.0)
        phi = ShapeModel(
            index=0, label="Φ12.2", sanitized="Phi12_2", kind="circle",
            points=[], circle=(100.0, 100.0, 40.0), angle_start=0.0,
            angle_end=2.0 * math.pi, polarity=100.0, template_angles=angles,
        )
        reference = ReferenceModel({}, Path("synthetic.bmp"), reference_gray, [phi], [])
        config = _test_config()
        config["phi12_2"].update({
            "search_radius_px": 12, "center_search_step_px": 2,
            "radius_search_step_px": 1, "refine_step_px": 0.5,
            "min_edge_peak_normalized": 0.35,
            "min_edge_prominence_normalized": 0.05,
            "boundary_saturation_fraction": 0.95,
            "phase_angle_extension_deg": 0.0,
        })

        def weak_but_consistent_phase(*args):
            seed = dict(args[6])
            seed.update({"edge_peak": 0.342, "phase_refined": True})
            return seed, {
                "candidate_edge_semantics": "reference_phase_outer_polarity_edge",
                "candidate_reference_edge_phase_fraction": 0.6,
                "candidate_polarity_enforced": True,
                "candidate_phase_failure": None,
                "candidate_phase_edge_points": 196,
                "candidate_phase_fit_residual_target_px": 0.68,
                "candidate_phase_polarity_support_fraction": 1.0,
                "candidate_phase_angle_coverage_fraction": 0.98,
                "candidate_phase_edge_peak_normalized": 0.342,
                "candidate_phase_fallback": None,
            }

        with patch(
            "algorithms.hole_2.current_capture._refine_phi_reference_phase",
            side_effect=weak_but_consistent_phase,
        ):
            values, quality = _detect_phi12_2(
                reference_gray, reference,
                SimilarityTransform(0.0, 0.0, 1.0, 0.0), config,
            )

        self.assertIsNotNone(values, quality)
        self.assertLess(quality["candidate_phase_edge_peak_normalized"], 0.35)
        self.assertGreaterEqual(
            quality["candidate_legacy_magnitude_edge_peak_normalized"], 0.35
        )
        self.assertTrue(quality["candidate_legacy_magnitude_edge_peak_gate_passed"])
        self.assertEqual(
            "reference_phase_multi_evidence",
            quality["candidate_acceptance_score_contract"],
        )

    def test_phi_unbounded_phase_quality_failures_do_not_fallback(self):
        angles = np.linspace(0.0, 2.0 * math.pi, 160, endpoint=False)
        yy, xx = np.indices((220, 220))
        reference_gray = np.full((220, 220), 220.0)
        reference_gray[np.hypot(xx - 100.0, yy - 100.0) <= 40.0] = 20.0
        reference_gray = gaussian_blur(reference_gray, 1.0)
        phi = ShapeModel(
            index=0, label="Φ12.2", sanitized="Phi12_2", kind="circle",
            points=[], circle=(100.0, 100.0, 40.0), angle_start=0.0,
            angle_end=2.0 * math.pi, polarity=100.0, template_angles=angles,
        )
        reference = ReferenceModel({}, Path("synthetic.bmp"), reference_gray, [phi], [])
        config = _test_config()
        config["phi12_2"].update({
            "search_radius_px": 12, "center_search_step_px": 2,
            "radius_search_step_px": 1, "refine_step_px": 0.5,
            "min_edge_peak_normalized": 0.15,
            "min_edge_prominence_normalized": 0.05,
            "boundary_saturation_fraction": 0.95,
        })
        for failure in (
            "phase_fit_residual_above_gate",
            "phase_edge_points_below_gate",
        ):
            phase_quality = {
                "candidate_edge_semantics": "reference_phase_outer_polarity_edge",
                "candidate_reference_edge_phase_fraction": 0.6,
                "candidate_polarity_enforced": True,
                "candidate_phase_failure": failure,
                "candidate_phase_edge_points": 20,
                "candidate_phase_fit_residual_target_px": 0.5,
            }
            with self.subTest(failure=failure), patch(
                "algorithms.hole_2.current_capture._refine_phi_reference_phase",
                return_value=(None, phase_quality),
            ):
                values, quality = _detect_phi12_2(
                    reference_gray, reference,
                    SimilarityTransform(0.0, 0.0, 1.0, 0.0), config,
                )
                self.assertIsNone(values, quality)
                self.assertEqual(failure, quality["candidate_failure"])

    def test_phi_phase_fallback_still_requires_legacy_magnitude_gate(self):
        angles = np.linspace(0.0, 2.0 * math.pi, 160, endpoint=False)
        yy, xx = np.indices((220, 220))
        reference_gray = np.full((220, 220), 220.0)
        reference_gray[np.hypot(xx - 100.0, yy - 100.0) <= 40.0] = 20.0
        reference_gray = gaussian_blur(reference_gray, 1.0)
        phi = ShapeModel(
            index=0, label="Φ12.2", sanitized="Phi12_2", kind="circle",
            points=[], circle=(100.0, 100.0, 40.0), angle_start=0.0,
            angle_end=2.0 * math.pi, polarity=100.0, template_angles=angles,
        )
        reference = ReferenceModel({}, Path("synthetic.bmp"), reference_gray, [phi], [])
        config = _test_config()
        config["phi12_2"].update({
            "search_radius_px": 12, "center_search_step_px": 2,
            "radius_search_step_px": 1, "refine_step_px": 0.5,
            "min_edge_peak_normalized": 2.0,
            "min_edge_prominence_normalized": 0.05,
            "boundary_saturation_fraction": 0.95,
        })
        phase_quality = {
            "candidate_edge_semantics": "reference_phase_outer_polarity_edge",
            "candidate_reference_edge_phase_fraction": 0.6,
            "candidate_polarity_enforced": True,
            "candidate_phase_failure": "phase_polarity_support_below_gate",
            "candidate_phase_edge_points": 120,
            "candidate_phase_raw_points": 125,
            "candidate_phase_inlier_fraction": 0.96,
            "candidate_phase_angle_coverage_fraction": 0.96,
            "candidate_phase_fit_residual_target_px": 0.5,
        }

        with patch(
            "algorithms.hole_2.current_capture._refine_phi_reference_phase",
            return_value=(None, phase_quality),
        ), patch(
            "algorithms.hole_2.current_capture._phi_multicircle_recovery",
            return_value=(None, {}),
        ):
            values, quality = _detect_phi12_2(
                reference_gray, reference,
                SimilarityTransform(0.0, 0.0, 1.0, 0.0), config,
            )

        self.assertIsNone(values, quality)
        self.assertIn("edge_peak_below_gate", quality["candidate_failure"])
        self.assertEqual(
            "legacy_magnitude_quality_fallback", quality["candidate_phase_fallback"]
        )

    def test_phi_polarity_fallback_rejects_low_phase_inlier_fraction(self):
        angles = np.linspace(0.0, 2.0 * math.pi, 160, endpoint=False)
        yy, xx = np.indices((220, 220))
        reference_gray = np.full((220, 220), 220.0)
        reference_gray[np.hypot(xx - 100.0, yy - 100.0) <= 40.0] = 20.0
        reference_gray = gaussian_blur(reference_gray, 1.0)
        phi = ShapeModel(
            index=0, label="Φ12.2", sanitized="Phi12_2", kind="circle",
            points=[], circle=(100.0, 100.0, 40.0), angle_start=0.0,
            angle_end=2.0 * math.pi, polarity=100.0, template_angles=angles,
        )
        reference = ReferenceModel({}, Path("synthetic.bmp"), reference_gray, [phi], [])
        config = _test_config()
        config["phi12_2"].update({
            "center_search_step_px": 2,
            "radius_search_step_px": 1,
            "refine_step_px": 0.5,
            "min_edge_peak_normalized": 0.15,
            "min_edge_prominence_normalized": 0.05,
            "boundary_saturation_fraction": 0.95,
        })
        phase_quality = {
            "candidate_edge_semantics": "reference_phase_outer_polarity_edge",
            "candidate_reference_edge_phase_fraction": 0.6,
            "candidate_polarity_enforced": True,
            "candidate_phase_failure": "phase_polarity_support_below_gate",
            "candidate_phase_edge_points": 76,
            "candidate_phase_raw_points": 155,
            "candidate_phase_inlier_fraction": 76.0 / 155.0,
            "candidate_phase_angle_coverage_fraction": 0.76,
            "candidate_phase_fit_residual_target_px": 0.5,
        }
        with patch(
            "algorithms.hole_2.current_capture._refine_phi_reference_phase",
            return_value=(None, phase_quality),
        ):
            values, quality = _detect_phi12_2(
                reference_gray, reference,
                SimilarityTransform(0.0, 0.0, 1.0, 0.0), config,
            )
        self.assertIsNone(values, quality)
        self.assertIn("phase_inlier_fraction_below_gate", quality["candidate_failure"])
        self.assertEqual(
            "phase_inlier_fraction_below_gate",
            quality["candidate_phase_fallback_rejection"],
        )

    def test_phi_polarity_fallback_preserves_high_phase_inlier_fraction(self):
        angles = np.linspace(0.0, 2.0 * math.pi, 160, endpoint=False)
        yy, xx = np.indices((220, 220))
        reference_gray = np.full((220, 220), 220.0)
        reference_gray[np.hypot(xx - 100.0, yy - 100.0) <= 40.0] = 20.0
        reference_gray = gaussian_blur(reference_gray, 1.0)
        phi = ShapeModel(
            index=0, label="Φ12.2", sanitized="Phi12_2", kind="circle",
            points=[], circle=(100.0, 100.0, 40.0), angle_start=0.0,
            angle_end=2.0 * math.pi, polarity=100.0, template_angles=angles,
        )
        reference = ReferenceModel({}, Path("synthetic.bmp"), reference_gray, [phi], [])
        config = _test_config()
        config["phi12_2"].update({
            "center_search_step_px": 2,
            "radius_search_step_px": 1,
            "refine_step_px": 0.5,
            "min_edge_peak_normalized": 0.15,
            "min_edge_prominence_normalized": 0.05,
            "boundary_saturation_fraction": 0.95,
        })
        phase_quality = {
            "candidate_edge_semantics": "reference_phase_outer_polarity_edge",
            "candidate_reference_edge_phase_fraction": 0.6,
            "candidate_polarity_enforced": True,
            "candidate_phase_failure": "phase_polarity_support_below_gate",
            "candidate_phase_edge_points": 133,
            "candidate_phase_raw_points": 139,
            "candidate_phase_inlier_fraction": 133.0 / 139.0,
            "candidate_phase_angle_coverage_fraction": 0.96,
            "candidate_phase_fit_residual_target_px": 0.5,
        }
        with patch(
            "algorithms.hole_2.current_capture._refine_phi_reference_phase",
            return_value=(None, phase_quality),
        ):
            values, quality = _detect_phi12_2(
                reference_gray, reference,
                SimilarityTransform(0.0, 0.0, 1.0, 0.0), config,
            )
        self.assertIsNotNone(values, quality)
        self.assertIsNone(quality["candidate_failure"])
        self.assertIsNone(quality["candidate_phase_fallback_rejection"])
        self.assertEqual(
            "legacy_magnitude_quality_fallback",
            quality["candidate_phase_fallback"],
        )

    def test_phi_bounded_phase_failure_can_preserve_old_quality_candidate(self):
        angles = np.linspace(0.0, 2.0 * math.pi, 160, endpoint=False)
        yy, xx = np.indices((220, 220))
        reference_gray = np.full((220, 220), 220.0)
        reference_gray[np.hypot(xx - 100.0, yy - 100.0) <= 40.0] = 20.0
        reference_gray = gaussian_blur(reference_gray, 1.0)
        phi = ShapeModel(
            index=0, label="Φ12.2", sanitized="Phi12_2", kind="circle",
            points=[], circle=(100.0, 100.0, 40.0), angle_start=0.0,
            angle_end=2.0 * math.pi, polarity=100.0, template_angles=angles,
        )
        reference = ReferenceModel({}, Path("synthetic.bmp"), reference_gray, [phi], [])
        target = reference_gray.copy()
        config = _test_config()
        config["phi12_2"].update({
            "search_radius_px": 12, "center_search_step_px": 2,
            "radius_search_step_px": 1, "refine_step_px": 0.5,
            "min_edge_peak_normalized": 0.15,
            "min_edge_prominence_normalized": 0.05,
            "boundary_saturation_fraction": 0.95,
        })
        phase_quality = {
            "candidate_edge_semantics": "reference_phase_outer_polarity_edge",
            "candidate_reference_edge_phase_fraction": 0.6,
            "candidate_polarity_enforced": True,
            "candidate_phase_failure": "phase_center_boundary_saturated",
            "candidate_phase_edge_points": 120,
            "candidate_phase_fit_residual_target_px": 0.5,
        }
        with patch(
            "algorithms.hole_2.current_capture._refine_phi_reference_phase",
            return_value=(None, phase_quality),
        ):
            values, quality = _detect_phi12_2(
                target, reference, SimilarityTransform(0.0, 0.0, 1.0, 0.0), config
            )
        self.assertIsNotNone(values, quality)
        self.assertEqual(
            "legacy_magnitude_quality_fallback", quality["candidate_phase_fallback"]
        )
        self.assertFalse(quality["candidate_polarity_enforced"])
        self.assertEqual(
            "legacy_gradient_magnitude_quality_fallback",
            quality["candidate_edge_semantics"],
        )

    def test_d7_paired_contour_uses_dark_band_center_not_outer_peak(self):
        image = np.full((200, 220), 220.0)
        image[:, 56:64] = 20.0
        image[:, 136:144] = 20.0
        image = gaussian_blur(image, 1.0)
        config = _test_config()["d7"] | {
            "paired_edge_strip_half_width_px": 24,
            "paired_edge_strip_samples": 25,
        }
        first_diagnostic = {}
        second_diagnostic = {}
        first = _paired_contour_boundary(
            image, (60.0, 100.0), (140.0, 100.0), "p1", -100.0,
            config, first_diagnostic,
        )
        second = _paired_contour_boundary(
            image, (60.0, 100.0), (140.0, 100.0), "p2", 100.0,
            config, second_diagnostic,
        )
        self.assertIsNotNone(first, first_diagnostic)
        self.assertIsNotNone(second, second_diagnostic)
        self.assertAlmostEqual(60.0, first.feature_point[0], delta=0.6)
        self.assertAlmostEqual(140.0, second.feature_point[0], delta=0.6)
        self.assertAlmostEqual(80.0, math.dist(first.feature_point, second.feature_point), delta=0.8)
        self.assertEqual("paired_edge_centerline", first_diagnostic["boundarySemantics"])
        self.assertGreaterEqual(first_diagnostic["pairSupport"], 12)
        self.assertAlmostEqual(8.0, first_diagnostic["pairWidthMedianPx"], delta=1.0)

    def test_geometry_ratio_alone_is_diagnostic_without_pulling_output(self):
        d7 = ShapeModel(
            index=0, label="7", sanitized="d7", kind="line",
            points=[(0.0, 0.0), (50.0, 0.0)], line_p1=(0.0, 0.0),
            line_p2=(50.0, 0.0),
        )
        phi = ShapeModel(
            index=1, label="Φ12.2", sanitized="Phi12_2", kind="arc",
            points=[], circle=(0.0, 0.0, 50.0),
        )
        reference = ReferenceModel({}, Path("reference.bmp"), np.zeros((10, 10)), [d7, phi], [])
        features = {
            "7": {
                "measurementValid": True, "qualityStatus": "valid", "failureReason": None,
                "sourceDetector": "test", "recoveryPass": None,
                "reference": {"lengthPx": 90.0},
                "target": {"lengthPx": 90.0}, "quality": {},
            },
            "Phi12.2": {
                "measurementValid": True, "qualityStatus": "valid", "failureReason": None,
                "sourceDetector": "test", "recoveryPass": None,
                "reference": {"diameterPx": 100.0},
                "target": {"diameterPx": 100.0}, "quality": {},
            },
        }

        report = evaluate_geometry_consistency(features, reference, _test_config())

        self.assertTrue(report["outlier"])
        self.assertFalse(report["rejected"])
        self.assertEqual("diagnostic_only_unconfirmed", report["decision"])
        self.assertIsNone(report["failureReason"])
        self.assertEqual("geometry_ratio_outlier_unconfirmed", report["outlierReason"])
        self.assertEqual(0.5, report["referenceRatio"])
        self.assertEqual(0.9, report["targetRatio"])
        self.assertFalse(report["outputAdjustmentApplied"])
        self.assertTrue(features["7"]["measurementValid"])
        self.assertEqual(90.0, features["7"]["target"]["lengthPx"])

    def test_geometry_outlier_with_registration_recovery_is_rejected(self):
        d7 = ShapeModel(
            index=0, label="7", sanitized="d7", kind="line",
            points=[(0.0, 0.0), (50.0, 0.0)], line_p1=(0.0, 0.0),
            line_p2=(50.0, 0.0),
        )
        phi = ShapeModel(
            index=1, label="Φ12.2", sanitized="Phi12_2", kind="arc",
            points=[], circle=(0.0, 0.0, 50.0),
        )
        reference = ReferenceModel({}, Path("reference.bmp"), np.zeros((10, 10)), [d7, phi], [])
        features = {
            "7": {
                "measurementValid": True, "qualityStatus": "valid", "failureReason": None,
                "sourceDetector": "test", "recoveryPass": None,
                "reference": {"lengthPx": 90.0},
                "target": {"lengthPx": 90.0}, "quality": {},
            },
            "Phi12.2": {
                "measurementValid": True, "qualityStatus": "valid", "failureReason": None,
                "sourceDetector": "test", "recoveryPass": None,
                "reference": {"diameterPx": 100.0},
                "target": {"diameterPx": 100.0}, "quality": {},
            },
        }

        report = evaluate_geometry_consistency(
            features, reference, _test_config(),
            registration={"registrationRecoveryPass": "stable_multi_support"},
        )

        self.assertTrue(report["outlier"])
        self.assertTrue(report["rejected"])
        self.assertEqual(
            ["registration_recovery:stable_multi_support"],
            report["corroboratingEvidence"],
        )
        self.assertFalse(features["7"]["measurementValid"])
        self.assertIsNone(features["7"]["target"])

    def test_d7_multiband_ignores_one_bad_parallel_strip(self):
        config = _test_config()["d7"] | {
            "band_offsets_target_px": [-24.0, -12.0, 0.0, 12.0, 24.0],
            "min_consistent_bands": 3,
        }

        def boundary(_image, p1, _p2, endpoint, **kwargs):
            bad = abs(p1[1] - 100.0) < 0.1
            x = (45.0 if bad else 60.0) if endpoint == "p1" else (155.0 if bad else 140.0)
            kwargs["diagnostics"].update({"failureStage": None, "acceptedEdgePoints": 13})
            return BoundaryDetection((x, p1[1]), (1.0, 0.0, -x), 13, 0.5, 12.0, 0.0)

        with patch("algorithms.hole_2.current_capture.detect_dimension_boundary", side_effect=boundary):
            recovered, quality = _d7_multiband_recovery(
                np.zeros((220, 220)), (60.0, 100.0), (140.0, 100.0),
                (1.0, -1.0), config,
            )

        self.assertIsNotNone(recovered, quality)
        self.assertEqual("multi_parallel_bands", quality["candidate_recovery_pass"])
        self.assertEqual(4, quality["candidate_multiband_inlier_count"])
        self.assertAlmostEqual(80.0, math.dist(*recovered), delta=0.1)

    def test_d7_multiband_does_not_recover_inconsistent_lengths(self):
        config = _test_config()["d7"] | {
            "band_offsets_target_px": [-24.0, -12.0, 0.0, 12.0, 24.0],
            "min_consistent_bands": 4,
            "max_cross_band_length_deviation_px": 1.0,
        }

        def boundary(_image, p1, _p2, endpoint, **kwargs):
            offset = p1[1] - 100.0
            x = 60.0 if endpoint == "p1" else 140.0 + offset / 2.0
            return BoundaryDetection((x, p1[1]), (1.0, 0.0, -x), 13, 0.5, 12.0, 0.0)

        with patch("algorithms.hole_2.current_capture.detect_dimension_boundary", side_effect=boundary):
            recovered, quality = _d7_multiband_recovery(
                np.zeros((220, 220)), (60.0, 100.0), (140.0, 100.0),
                (1.0, -1.0), config,
            )

        self.assertIsNone(recovered)
        self.assertEqual("p2_consistency_below_gate", quality["candidate_multiband_failure"])

    def test_phi_multicircle_ransac_rejects_outliers_without_nominal_pull(self):
        angles = np.linspace(0.1, 2.8, 80)
        circle_points = np.column_stack([
            25.0 + 42.0 * np.cos(angles),
            31.0 + 42.0 * np.sin(angles),
        ])
        outliers = np.asarray([[180.0, 20.0], [-80.0, 90.0], [150.0, 170.0]])
        fitted = _ransac_circle(
            np.vstack([circle_points, outliers]),
            trials=96, inlier_residual_px=1.0, minimum_inliers=40,
        )
        self.assertIsNotNone(fitted)
        circle, inliers, residual = fitted
        self.assertAlmostEqual(25.0, circle[0], delta=0.1)
        self.assertAlmostEqual(31.0, circle[1], delta=0.1)
        self.assertAlmostEqual(42.0, circle[2], delta=0.1)
        self.assertGreaterEqual(int(inliers.sum()), 80)
        self.assertLess(residual, 0.1)

    def test_registration_recovery_runs_only_after_no_valid_candidate(self):
        with tempfile.TemporaryDirectory() as tmp:
            reference, _ = _synthetic_reference(Path(tmp))
            hypothesis = {"score": 1.0, "scale": 1.0, "centerX": 210.0, "centerY": 210.0}

            def candidate(_hypothesis, orientation, _groups, _primary, _gradient, config):
                recovered = (
                    config["supports"]["refine_search_radius_target_px"] == 32.0
                    and orientation == 270
                )
                return {
                    "orientationDeg": orientation,
                    "coarse": hypothesis,
                    "transform": SimilarityTransform(0.0, 0.0, 1.0, 0.0).as_dict() if recovered else None,
                    "score": 10.0 if recovered else 1.0,
                    "supportCount": 4 if recovered else 2,
                    "spatialCoverage": 0.5 if recovered else 0.0,
                    "medianResidualPx": 0.0 if recovered else None,
                    "maxResidualPx": 0.0 if recovered else None,
                    "supports": [], "gateDiagnostics": {},
                    "valid": recovered,
                    "failureReasons": [] if recovered else ["support_count_below_gate"],
                }

            with patch("algorithms.hole_2.current_capture._coarse_hypotheses", return_value=[hypothesis]), patch(
                "algorithms.hole_2.current_capture._candidate", side_effect=candidate
            ) as candidate_mock:
                result = register_current_capture(reference, np.zeros((420, 420)), _test_config())

        self.assertTrue(result["registrationValid"], result)
        self.assertEqual("stable_multi_support", result["registrationRecoveryPass"])
        self.assertEqual("no_valid_candidate", result["primaryFailureReason"])
        self.assertEqual(8, candidate_mock.call_count)
        self.assertEqual("recovery", result["selected"]["registrationPass"])

    def test_ambiguous_primary_candidates_never_trigger_recovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            reference, _ = _synthetic_reference(Path(tmp))
            hypothesis = {"score": 1.0, "scale": 1.0, "centerX": 210.0, "centerY": 210.0}

            def candidate(_hypothesis, orientation, *_args):
                return {
                    "orientationDeg": orientation, "coarse": hypothesis,
                    "transform": SimilarityTransform(0.0, 0.0, 1.0, float(orientation)).as_dict(),
                    "score": 10.0 - 0.001 * orientation,
                    "supportCount": 4, "spatialCoverage": 0.5,
                    "medianResidualPx": 0.0, "maxResidualPx": 0.0,
                    "supports": [], "gateDiagnostics": {}, "valid": True,
                    "failureReasons": [],
                }

            with patch("algorithms.hole_2.current_capture._coarse_hypotheses", return_value=[hypothesis]), patch(
                "algorithms.hole_2.current_capture._candidate", side_effect=candidate
            ) as candidate_mock:
                result = register_current_capture(reference, np.zeros((420, 420)), _test_config())

        self.assertFalse(result["registrationValid"])
        self.assertEqual("ambiguous_candidates", result["failureReason"])
        self.assertIsNone(result["registrationRecoveryPass"])
        self.assertEqual(4, candidate_mock.call_count)

    def test_similarity_roundtrip_and_exact_fit(self):
        expected = SimilarityTransform(320.0, 75.0, 0.72, -88.5)
        reference = [(10.0, 20.0), (200.0, 30.0), (80.0, 190.0), (260.0, 220.0)]
        target = [expected.forward(*point) for point in reference]
        actual, residuals = fit_similarity_transform(reference, target)
        self.assertAlmostEqual(expected.dx, actual.dx, places=8)
        self.assertAlmostEqual(expected.dy, actual.dy, places=8)
        self.assertAlmostEqual(expected.scale, actual.scale, places=8)
        self.assertAlmostEqual(expected.theta_deg, actual.theta_deg, places=8)
        self.assertLess(max(residuals), 1e-8)
        for point in reference:
            self.assertLess(math.dist(point, actual.inverse(*actual.forward(*point))), 1e-8)

        inverse = actual.inverse_as_dict()
        inverse_transform = SimilarityTransform(
            inverse["dx"], inverse["dy"], inverse["scale"], inverse["thetaDeg"]
        )
        for point in reference:
            self.assertLess(
                math.dist(point, inverse_transform.forward(*actual.forward(*point))),
                1e-8,
            )

    def test_config_requires_all_four_orientations(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            config = _test_config()
            config["orientations_deg"] = [0, 90, 180]
            path.write_text(json.dumps(config), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "0, 90, 180, 270"):
                load_registration_config(path)

    def test_config_freezes_main_and_recovery_radius_bounds(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            for key, value in (
                ("min_radius_scale_ratio", 0.87),
                ("recovery_min_radius_scale_ratio", 0.83),
            ):
                with self.subTest(key=key):
                    config = _test_config()
                    config["phi12_2"][key] = value
                    path.write_text(json.dumps(config), encoding="utf-8")
                    with self.assertRaisesRegex(ValueError, "must remain"):
                        load_registration_config(path)

    def test_repository_config_keeps_legacy_and_geometry_thresholds(self):
        config_path = (
            Path(__file__).resolve().parents[1]
            / "config"
            / "current_capture_registration.v1.json"
        )
        config = load_registration_config(config_path)
        self.assertEqual(0.35, config["phi12_2"]["min_edge_peak_normalized"])
        self.assertEqual(
            0.08,
            config["geometry_consistency"][
                "max_reference_ratio_absolute_deviation"
            ],
        )

    def test_four_discrete_orientations_are_recovered(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            reference, groups = _synthetic_reference(root)
            for orientation in (0, 90, 180, 270):
                with self.subTest(orientation=orientation):
                    expected = _centered_transform(float(orientation))
                    target_path = root / f"target-{orientation}.bmp"
                    target = _render_transformed(groups, expected, target_path)
                    result = register_current_capture(reference, target, _test_config())
                    self.assertTrue(result["registrationValid"], result)
                    self.assertEqual(orientation, result["selected"]["orientationDeg"])
                    self.assertGreaterEqual(result["selected"]["supportCount"], 3)
                    self.assertIn("gateDiagnostics", result["selected"])
                    self.assertTrue(all(
                        "searchBoundary" in support and "gateDiagnostics" in support
                        for support in result["selected"]["supports"]
                    ))
                    # Raster edge localization includes a one-pixel drawing bias;
                    # the exact landmark fit above covers the stricter numeric gate.
                    self.assertLessEqual(abs(result["transform"]["scale"] - 1.0), 0.02)
                    angular = (result["transform"]["thetaDeg"] - orientation + 180.0) % 360.0 - 180.0
                    self.assertLessEqual(abs(angular), 1.0)

    def test_central_peak_without_spatial_support_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            reference, groups = _synthetic_reference(root)
            target_path = root / "central-only.bmp"
            target = _render_transformed(
                groups, _centered_transform(270.0),
                target_path, include_outer=False,
            )
            result = register_current_capture(reference, target, _test_config())
            self.assertFalse(result["registrationValid"])
            self.assertIn(result["failureReason"], {"no_valid_candidate", "ambiguous_candidates"})
            self.assertTrue(all(c["supportCount"] < 3 or not c["valid"] for c in result["candidates"]))

    def test_inconsistent_wrong_anchors_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            reference, groups = _synthetic_reference(root)
            target = _render_inconsistent_anchors(
                groups, _centered_transform(270.0), root / "wrong-anchors.bmp"
            )
            result = register_current_capture(reference, target, _test_config())
            self.assertFalse(result["registrationValid"], result)
            self.assertEqual("no_valid_candidate", result["failureReason"])
            self.assertTrue(result["candidates"])
            self.assertTrue(all(not candidate["valid"] for candidate in result["candidates"]))
            self.assertTrue(any(
                "support_count_below_gate" in candidate["failureReasons"]
                for candidate in result["candidates"]
            ))

    def test_v6_external_seed_bypasses_phase_correlation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            reference, _ = _synthetic_reference(root)
            target_path = root / "reference-copy.bmp"
            Image.open(reference.image_path).save(target_path)
            with patch("algorithms.hole_2.main.phase_correlation_shift", side_effect=AssertionError("phase used")):
                extraction = extract_image(
                    target_path,
                    reference,
                    initial_transform=(0.0, 0.0, 1.0, 0.0),
                    expand_anchors=False,
                )
            self.assertTrue(extraction.align_method.startswith("external-pose-seed"))

    def test_phi_candidate_and_d7_tangent_are_image_driven(self):
        angles = np.linspace(0.0, 2.0 * math.pi, 77, endpoint=False)
        phi = ShapeModel(
            index=0, label="Φ12.2", sanitized="Phi12_2", kind="arc",
            points=[(100.0 + 40.0 * math.cos(a), 100.0 + 40.0 * math.sin(a)) for a in angles],
            circle=(100.0, 100.0, 40.0), angle_start=0.0,
            angle_end=2.0 * math.pi, template_angles=angles,
        )
        d7 = ShapeModel(
            index=1, label="7", sanitized="d7", kind="line",
            points=[(60.0, 145.0), (140.0, 145.0)],
            line_p1=(60.0, 145.0), line_p2=(140.0, 145.0),
            endpoint_polarities=(100.0, -100.0),
        )
        reference = ReferenceModel({}, Path("synthetic.bmp"), np.zeros((220, 220)), [phi, d7], [])
        target = np.full((220, 220), 20.0)
        yy, xx = np.indices(target.shape)
        target[np.hypot(xx - 105.0, yy - 107.0) <= 36.0] = 220.0
        target = gaussian_blur(target, 1.0)
        config = _test_config()
        config["phi12_2"].update({
            "search_radius_px": 16, "center_search_step_px": 2,
            "radius_search_step_px": 1, "refine_step_px": 0.5,
            "min_edge_peak_normalized": 0.15,
            "min_edge_prominence_normalized": 0.05,
            "boundary_saturation_fraction": 0.95,
        })
        config["d7"]["max_reference_tangent_error_px"] = 6.0
        phi_values, phi_quality = _detect_phi12_2(
            target, reference, SimilarityTransform(0.0, 0.0, 1.0, 0.0), config
        )
        self.assertIsNotNone(phi_values, phi_quality)
        self.assertAlmostEqual(105.0, phi_values["Phi12_2_cx"], delta=1.0)
        self.assertAlmostEqual(107.0, phi_values["Phi12_2_cy"], delta=1.0)
        self.assertAlmostEqual(36.0, phi_values["Phi12_2_r"], delta=1.0)
        self.assertIn("candidate_center_x_boundary", phi_quality)
        self.assertIn("candidate_center_y_boundary", phi_quality)
        self.assertIn("candidate_radius_lower_bound_target_px", phi_quality)
        self.assertIn("candidate_radius_upper_bound_target_px", phi_quality)
        self.assertIn("candidate_edge_polarity", phi_quality)
        self.assertGreater(phi_quality["candidate_angle_coverage_deg"], 350.0)

        # Use a separate straight-band target so the two endpoint boundaries
        # are unambiguous; the axis must move from y=145 to the detected
        # Phi12.2 tangent at y=140.
        band = np.full((220, 220), 20.0)
        band[:, 60:141] = 220.0
        band = gaussian_blur(band, 1.0)
        tangent_values, tangent_quality = _detect_d7_tangent(
            band, reference, SimilarityTransform(0.0, 0.0, 1.0, 0.0),
            {"Phi12_2_cx": 100.0, "Phi12_2_cy": 100.0, "Phi12_2_r": 40.0},
            config,
        )
        self.assertIsNotNone(tangent_values, tangent_quality)
        self.assertAlmostEqual(-5.0, tangent_quality["candidate_axis_shift_target_px"], delta=0.1)
        self.assertAlmostEqual(80.0, tangent_values["d7_length"], delta=1.5)
        self.assertEqual([], tangent_quality["candidate_failed_sides"])
        self.assertIn("candidate_p1_strip", tangent_quality)
        self.assertIn("candidate_p2_strip", tangent_quality)

    def test_d7_failed_side_keeps_strip_diagnostics(self):
        angles = np.linspace(0.0, 2.0 * math.pi, 77, endpoint=False)
        phi = ShapeModel(
            index=0, label="Φ12.2", sanitized="Phi12_2", kind="arc",
            points=[(100.0 + 40.0 * math.cos(a), 100.0 + 40.0 * math.sin(a)) for a in angles],
            circle=(100.0, 100.0, 40.0), angle_start=0.0,
            angle_end=2.0 * math.pi, template_angles=angles,
        )
        d7 = ShapeModel(
            index=1, label="7", sanitized="d7", kind="line",
            points=[(60.0, 140.0), (140.0, 140.0)],
            line_p1=(60.0, 140.0), line_p2=(140.0, 140.0),
            endpoint_polarities=(100.0, -100.0),
        )
        reference = ReferenceModel({}, Path("synthetic.bmp"), np.zeros((220, 220)), [phi, d7], [])
        values, quality = _detect_d7_tangent(
            np.full((220, 220), 20.0), reference,
            SimilarityTransform(0.0, 0.0, 1.0, 0.0),
            {"Phi12_2_cx": 100.0, "Phi12_2_cy": 100.0, "Phi12_2_r": 40.0},
            _test_config(),
        )
        self.assertIsNone(values)
        self.assertEqual(["p1", "p2"], quality["candidate_failed_sides"])
        for side in ("p1", "p2"):
            strip = quality[f"candidate_{side}_strip"]
            self.assertEqual("paired_centerline_fit_failed", strip["failureStage"])
            self.assertEqual(0, strip["pairSupport"])

    def test_phi_radius_expands_only_after_main_lower_bound_saturation(self):
        angles = np.linspace(0.0, 2.0 * math.pi, 77, endpoint=False)
        phi = ShapeModel(
            index=0, label="Φ12.2", sanitized="Phi12_2", kind="arc",
            points=[(100.0 + 40.0 * math.cos(a), 100.0 + 40.0 * math.sin(a)) for a in angles],
            circle=(100.0, 100.0, 40.0), angle_start=0.0,
            angle_end=2.0 * math.pi, template_angles=angles,
        )
        reference = ReferenceModel({}, Path("synthetic.bmp"), np.zeros((220, 220)), [phi], [])
        target = np.full((220, 220), 20.0)
        yy, xx = np.indices(target.shape)
        target[np.hypot(xx - 100.0, yy - 100.0) <= 34.0] = 220.0
        target = gaussian_blur(target, 1.0)
        config = _test_config()
        config["phi12_2"].update({
            "search_radius_px": 8, "center_search_step_px": 2,
            "radius_search_step_px": 1, "refine_step_px": 0.5,
            "min_edge_peak_normalized": 0.15,
            "min_edge_prominence_normalized": 0.05,
            "boundary_saturation_fraction": 0.95,
        })

        values, quality = _detect_phi12_2(
            target, reference, SimilarityTransform(0.0, 0.0, 1.0, 0.0), config
        )

        self.assertIsNotNone(values, quality)
        self.assertEqual("expanded_radius", quality["candidate_recovery_pass"])
        self.assertTrue(quality["candidate_main_lower_bound_saturated"])
        self.assertGreaterEqual(quality["candidate_radius_scale_ratio"], 0.84)
        self.assertLess(quality["candidate_radius_scale_ratio"], 0.88)

    def test_phi_center_boundary_uses_bounded_recenter_pass(self):
        angles = np.linspace(0.0, 2.0 * math.pi, 77, endpoint=False)
        yy, xx = np.indices((240, 240))
        reference_gray = np.full((240, 240), 220.0)
        reference_gray[np.hypot(xx - 100.0, yy - 100.0) <= 40.0] = 20.0
        reference_gray = gaussian_blur(reference_gray, 1.0)
        phi = ShapeModel(
            index=0, label="Φ12.2", sanitized="Phi12_2", kind="arc",
            points=[(100.0 + 40.0 * math.cos(a), 100.0 + 40.0 * math.sin(a)) for a in angles],
            circle=(100.0, 100.0, 40.0), angle_start=0.0, polarity=100.0,
            angle_end=2.0 * math.pi, template_angles=angles,
        )
        reference = ReferenceModel({}, Path("synthetic.bmp"), reference_gray, [phi], [])
        target = np.full((240, 240), 220.0)
        target[np.hypot(xx - 130.0, yy - 100.0) <= 42.0] = 20.0
        target = gaussian_blur(target, 1.0)
        config = _test_config()
        config["phi12_2"].update({
            "search_radius_px": 20, "center_search_step_px": 2,
            "radius_search_step_px": 1, "refine_step_px": 0.5,
            "min_edge_peak_normalized": 0.15,
            "min_edge_prominence_normalized": 0.05,
            "boundary_saturation_fraction": 0.95,
            "center_recovery_search_radius_px": 16.0,
        })

        values, quality = _detect_phi12_2(
            target, reference, SimilarityTransform(0.0, 0.0, 1.0, 0.0), config
        )

        self.assertIsNotNone(values, quality)
        self.assertEqual("center_recenter", quality["candidate_recovery_pass"])
        self.assertAlmostEqual(130.0, values["Phi12_2_cx"], delta=1.0)
        self.assertFalse(quality["candidate_search_boundary_saturated"])
        self.assertTrue(quality["candidate_global_center_boundary_saturated"])
        self.assertTrue(quality["candidate_phase_evidence_gate_passed"])

    def test_phi_recenter_beyond_primary_window_requires_successful_phase(self):
        angles = np.linspace(0.0, 2.0 * math.pi, 77, endpoint=False)
        yy, xx = np.indices((240, 240))
        reference_gray = np.full((240, 240), 220.0)
        reference_gray[np.hypot(xx - 100.0, yy - 100.0) <= 40.0] = 20.0
        reference_gray = gaussian_blur(reference_gray, 1.0)
        phi = ShapeModel(
            index=0, label="Φ12.2", sanitized="Phi12_2", kind="arc",
            points=[], circle=(100.0, 100.0, 40.0), angle_start=0.0,
            angle_end=2.0 * math.pi, polarity=100.0, template_angles=angles,
        )
        reference = ReferenceModel({}, Path("synthetic.bmp"), reference_gray, [phi], [])
        target = np.full((240, 240), 220.0)
        target[np.hypot(xx - 130.0, yy - 100.0) <= 42.0] = 20.0
        target = gaussian_blur(target, 1.0)
        config = _test_config()
        config["phi12_2"].update({
            "search_radius_px": 20, "center_search_step_px": 2,
            "radius_search_step_px": 1, "refine_step_px": 0.5,
            "min_edge_peak_normalized": 0.15,
            "min_edge_prominence_normalized": 0.05,
            "boundary_saturation_fraction": 0.95,
            "center_recovery_search_radius_px": 16.0,
        })
        phase_quality = {
            "candidate_edge_semantics": "reference_phase_outer_polarity_edge",
            "candidate_reference_edge_phase_fraction": 0.6,
            "candidate_polarity_enforced": True,
            "candidate_phase_failure": "phase_center_boundary_saturated",
            "candidate_phase_edge_points": 150,
            "candidate_phase_raw_points": 160,
            "candidate_phase_inlier_fraction": 0.9375,
            "candidate_phase_angle_coverage_fraction": 0.98,
            "candidate_phase_fit_residual_target_px": 0.5,
        }
        with patch(
            "algorithms.hole_2.current_capture._refine_phi_reference_phase",
            return_value=(None, phase_quality),
        ):
            values, quality = _detect_phi12_2(
                target, reference, SimilarityTransform(0.0, 0.0, 1.0, 0.0), config
            )
        self.assertIsNone(values, quality)
        self.assertTrue(quality["candidate_global_center_boundary_saturated"])
        self.assertEqual(
            "global_center_displacement_requires_phase_evidence",
            quality["candidate_phase_fallback_rejection"],
        )

    def test_phi_does_not_expand_for_non_lower_bound_failure(self):
        angles = np.linspace(0.0, 2.0 * math.pi, 77, endpoint=False)
        phi = ShapeModel(
            index=0, label="Φ12.2", sanitized="Phi12_2", kind="arc",
            points=[(100.0 + 40.0 * math.cos(a), 100.0 + 40.0 * math.sin(a)) for a in angles],
            circle=(100.0, 100.0, 40.0), angle_start=0.0,
            angle_end=2.0 * math.pi, template_angles=angles,
        )
        reference = ReferenceModel({}, Path("synthetic.bmp"), np.zeros((220, 220)), [phi], [])
        target = np.full((220, 220), 20.0)
        yy, xx = np.indices(target.shape)
        target[np.hypot(xx - 100.0, yy - 100.0) <= 44.0] = 220.0
        target = gaussian_blur(target, 1.0)
        config = _test_config()
        config["phi12_2"].update({
            "search_radius_px": 8, "center_search_step_px": 2,
            "radius_search_step_px": 1, "refine_step_px": 0.5,
            "min_edge_peak_normalized": 0.35,
            "min_edge_prominence_normalized": 0.15,
            "boundary_saturation_fraction": 0.95,
        })

        values, quality = _detect_phi12_2(
            target, reference, SimilarityTransform(0.0, 0.0, 1.0, 0.0), config
        )

        self.assertIsNone(values)
        self.assertEqual("robust_multicircle", quality["candidate_recovery_pass"])
        self.assertFalse(quality["candidate_main_lower_bound_saturated"])
        self.assertNotEqual("expanded_radius", quality["candidate_recovery_pass"])

    def test_phi_expanded_pass_does_not_promote_another_saturated_boundary(self):
        angles = np.linspace(0.0, 2.0 * math.pi, 77, endpoint=False)
        phi = ShapeModel(
            index=0, label="Φ12.2", sanitized="Phi12_2", kind="arc",
            points=[(100.0 + 40.0 * math.cos(a), 100.0 + 40.0 * math.sin(a)) for a in angles],
            circle=(100.0, 100.0, 40.0), angle_start=0.0,
            angle_end=2.0 * math.pi, template_angles=angles,
        )
        reference = ReferenceModel({}, Path("synthetic.bmp"), np.zeros((220, 220)), [phi], [])
        target = np.full((220, 220), 20.0)
        yy, xx = np.indices(target.shape)
        target[np.hypot(xx - 100.0, yy - 100.0) <= 30.0] = 220.0
        target = gaussian_blur(target, 1.0)
        config = _test_config()
        config["phi12_2"].update({
            "search_radius_px": 8, "center_search_step_px": 2,
            "radius_search_step_px": 1, "refine_step_px": 0.5,
            "min_edge_peak_normalized": 0.15,
            "min_edge_prominence_normalized": 0.05,
            "boundary_saturation_fraction": 0.95,
        })

        values, quality = _detect_phi12_2(
            target, reference, SimilarityTransform(0.0, 0.0, 1.0, 0.0), config
        )

        self.assertIsNone(values)
        self.assertEqual("expanded_radius", quality["candidate_recovery_pass"])
        self.assertTrue(quality["candidate_lower_radius_boundary_saturated"])
        self.assertIn("search_boundary_saturated", quality["candidate_failure"])

    def test_d7_fallback_requires_original_v6_quality_gate(self):
        valid_v6 = {
            "d7_x1": 1.0, "d7_y1": 2.0, "d7_x2": 9.0, "d7_y2": 2.0,
            "d7_length": 8.0,
            "d7.quality.upstream": "ok:dual_boundary_fit",
        }
        values, quality = _v6_d7_fallback(
            valid_v6, {"candidate_failure": "tangent_boundary_fit_failed"}
        )
        self.assertEqual(8.0, values["d7_length"])
        self.assertEqual("v6_original_quality", quality["candidate_fallback_pass"])
        self.assertEqual("tangent_boundary_fit_failed", quality["candidate_failure"])

        for rejected in (
            {**valid_v6, "d7.quality.upstream": "failed:p1_boundary_fit"},
            {**valid_v6, "d7_length": float("nan")},
        ):
            with self.subTest(rejected=rejected):
                values, quality = _v6_d7_fallback(
                    rejected, {"candidate_failure": "tangent_boundary_fit_failed"}
                )
                self.assertIsNone(values)
                self.assertIsNone(quality["candidate_fallback_pass"])
                self.assertEqual("v6_original_quality_rejected", quality["candidate_fallback_failure"])


if __name__ == "__main__":
    unittest.main()
