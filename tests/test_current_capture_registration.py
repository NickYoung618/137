import json
import math
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
from PIL import Image, ImageDraw

from algorithms.hole_2.main import ReferenceModel, ShapeModel, build_reference, extract_image, gaussian_blur
from algorithms.hole_2.current_capture import (
    SimilarityTransform,
    _detect_d7_tangent,
    _detect_phi12_2,
    _v6_d7_fallback,
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
        "d7": {
            "max_reference_tangent_error_px": 4.0,
            "max_axis_shift_target_px": 20.0,
            "min_boundary_points": 12,
            "max_fit_residual_target_px": 3.0,
            "min_edge_score": 4.0,
            "max_boundary_parallelism_deg": 12.0,
        },
        "phi12_2": {
            "search_radius_px": 20, "min_radius_scale_ratio": 0.88,
            "recovery_min_radius_scale_ratio": 0.84,
            "max_radius_scale_ratio": 1.08, "min_edge_points": 20,
            "max_fit_residual_target_px": 3.0,
        },
    }


class CurrentCaptureRegistrationTests(unittest.TestCase):
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
        self.assertIsNone(quality["candidate_recovery_pass"])
        self.assertFalse(quality["candidate_main_lower_bound_saturated"])

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
