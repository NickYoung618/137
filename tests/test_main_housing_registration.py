from __future__ import annotations

import math
import copy
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import numpy as np
from PIL import Image, ImageDraw

from algorithms.end_face.main_housing_registration import MainHousingRegistrar
from algorithms.end_face.short_line_candidate import (
    ShortLineCandidateEvaluator,
    load_candidate_config,
)


REGISTRATION_CONFIG = {
    "downsampleFactor": 8,
    "foregroundThreshold": 50.0,
    "minimumComponentPixels": 24,
    "minimumDiameterPx": 100.0,
    "maximumAspectError": 0.22,
    "minimumComponentFillRatio": 0.03,
    "maximumComponentFillRatio": 0.82,
    "radialRayCount": 180,
    "minimumEdgeCoverageRatio": 0.48,
    "maximumCircularResidualRatio": 0.035,
    "minimumScale": 0.75,
    "maximumScale": 1.25,
    "minimumReferenceRadiusMarginRatio": 0.15,
    "angularSamples": 360,
    "radialSamples": 72,
    "minimumRotationScore": 0.20,
    "minimumRotationMargin": 0.01,
    "rotationSeparationDeg": 12.0,
    "minimumInstanceScore": 0.35,
    "minimumInstanceMargin": 0.04,
}


def housing_image(
    center: tuple[float, float],
    radius: float,
    *,
    size: tuple[int, int] = (640, 420),
    rotation_deg: float = 0.0,
    neighbors: tuple[tuple[float, float, float], ...] = (),
) -> np.ndarray:
    image = Image.new("L", size, 4)
    draw = ImageDraw.Draw(image)

    def draw_housing(cx: float, cy: float, value_radius: float, angle_deg: float, *, main: bool) -> None:
        for offset, value in ((0, 175), (-10, 65), (-24, 205), (-48, 42)):
            rr = value_radius + offset
            draw.ellipse((cx - rr, cy - rr, cx + rr, cy + rr), outline=value, width=7)
        if main:
            angle = math.radians(angle_deg)
            marker_radius = value_radius * 0.84
            mx = cx + marker_radius * math.cos(angle)
            my = cy + marker_radius * math.sin(angle)
            draw.rectangle((mx - 11, my - 4, mx + 11, my + 4), fill=245)
            angle2 = angle + math.radians(63.0)
            mx2 = cx + value_radius * 0.72 * math.cos(angle2)
            my2 = cy + value_radius * 0.72 * math.sin(angle2)
            draw.ellipse((mx2 - 6, my2 - 6, mx2 + 6, my2 + 6), fill=225)

    draw_housing(center[0], center[1], radius, rotation_deg, main=True)
    for nx, ny, nr in neighbors:
        draw_housing(nx, ny, nr, 0.0, main=False)
    return np.asarray(image, dtype=np.float64)


class MainHousingRegistrationTests(unittest.TestCase):
    def test_selects_main_instance_instead_of_smaller_neighbor(self) -> None:
        reference = housing_image((190.0, 210.0), 140.0)
        registrar = MainHousingRegistrar(reference, REGISTRATION_CONFIG)
        target = housing_image(
            (245.0, 205.0),
            140.0,
            neighbors=((505.0, 105.0, 82.0), (510.0, 335.0, 70.0)),
        )
        result = registrar.register(target)

        self.assertTrue(result.valid, result.to_dict())
        self.assertAlmostEqual(245.0, result.target_center[0], delta=5.0)
        self.assertAlmostEqual(205.0, result.target_center[1], delta=5.0)
        self.assertGreaterEqual(len(result.hypotheses), 2)
        self.assertAlmostEqual(1.0, result.scale, delta=0.06)

    def test_recovers_nonzero_scale_and_rotation(self) -> None:
        reference = housing_image((190.0, 210.0), 140.0)
        registrar = MainHousingRegistrar(reference, REGISTRATION_CONFIG)
        target = housing_image(
            (270.0, 205.0),
            154.0,
            rotation_deg=17.0,
            neighbors=((520.0, 100.0, 75.0),),
        )
        result = registrar.register(target)

        self.assertTrue(result.valid, result.to_dict())
        self.assertAlmostEqual(270.0, result.target_center[0], delta=5.0)
        self.assertAlmostEqual(205.0, result.target_center[1], delta=5.0)
        self.assertAlmostEqual(1.1, result.scale, delta=0.04)
        self.assertAlmostEqual(17.0, result.rotation_deg, delta=1.5)

    def test_blank_and_ambiguous_targets_fail_closed(self) -> None:
        reference = housing_image((190.0, 210.0), 140.0)
        registrar = MainHousingRegistrar(reference, REGISTRATION_CONFIG)
        blank = registrar.register(np.zeros_like(reference))
        self.assertFalse(blank.valid)
        self.assertIsNotNone(blank.failure_reason)
        json.dumps(blank.to_dict(), allow_nan=False)

        ambiguous = Image.new("L", (760, 420), 4)
        left = Image.fromarray(housing_image((190.0, 210.0), 140.0, size=(380, 420)).astype(np.uint8))
        right = Image.fromarray(housing_image((190.0, 210.0), 140.0, size=(380, 420)).astype(np.uint8))
        ambiguous.paste(left, (0, 0))
        ambiguous.paste(right, (380, 0))
        result = registrar.register(np.asarray(ambiguous, dtype=np.float64))
        self.assertFalse(result.valid, result.to_dict())
        self.assertEqual("instance_ambiguous", result.failure_reason)

    def test_ambiguous_reference_instances_are_rejected_without_annotations(self) -> None:
        reference = housing_image(
            (190.0, 210.0),
            140.0,
            size=(760, 420),
            neighbors=((570.0, 210.0, 140.0),),
        )
        with self.assertRaisesRegex(ValueError, "reference instance ambiguous"):
            MainHousingRegistrar(reference, REGISTRATION_CONFIG)

    def test_v2_projection_ignores_wrong_legacy_short_line_geometry(self) -> None:
        reference_pixels = housing_image((190.0, 210.0), 140.0)
        target_pixels = housing_image(
            (245.0, 205.0),
            140.0,
            neighbors=((505.0, 105.0, 82.0),),
        )
        lines = {
            "19": ((68.0, 205.0), (102.0, 205.0)),
            "30": ((84.0, 244.0), (110.0, 244.0)),
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            image_path = root / "reference.bmp"
            Image.fromarray(reference_pixels.astype(np.uint8)).save(image_path)
            annotation = root / "a2-short-lines.json"
            annotation.write_text(json.dumps({
                "version": "5.5.0",
                "flags": {},
                "shapes": [
                    {"label": label, "shape_type": "line", "points": [list(point) for point in points]}
                    for label, points in lines.items()
                ],
                "imagePath": image_path.name,
                "imageData": None,
                "imageWidth": reference_pixels.shape[1],
                "imageHeight": reference_pixels.shape[0],
            }), encoding="utf-8")
            config = load_candidate_config(Path("config/end_face_short_line_candidate.v2.json"))
            config = copy.deepcopy(config)
            config["registration"]["minimumDiameterPx"] = 100.0
            desktop_shapes = [
                SimpleNamespace(label=f"{label}��", shape_type="line", points=[list(point) for point in points])
                for label, points in lines.items()
            ]
            desktop_model = SimpleNamespace(
                shapes=desktop_shapes,
                reference_grad=np.zeros_like(reference_pixels),
                alignment_center=(500.0, 100.0),
            )
            measurements: dict[str, float | str] = {
                "transform.target_center_x_px": 500.0,
                "transform.target_center_y_px": 100.0,
                "transform.scale": 1.0,
                "transform.rotation_deg": 0.0,
            }
            quality = {}
            for label, points in lines.items():
                raw = f"{label}��"
                length = math.dist(*points)
                measurements.update({
                    f"{raw}.x1_px": 480.0,
                    f"{raw}.y1_px": 100.0,
                    f"{raw}.x2_px": 480.0 + length,
                    f"{raw}.y2_px": 100.0,
                    f"{raw}.length_px": length,
                    f"{raw}.angle_deg": 0.0,
                    f"{raw}.x1_ref_px": points[0][0],
                    f"{raw}.y1_ref_px": points[0][1],
                    f"{raw}.x2_ref_px": points[1][0],
                    f"{raw}.y2_ref_px": points[1][1],
                    f"{raw}.length_ref_px": length,
                    f"{raw}.angle_ref_deg": 0.0,
                })
                quality[raw] = {
                    "canonicalFeature": label,
                    "coreValid": False,
                    "source": "short_line_transform_fallback",
                    "reason": "short_line_lateral_edge_not_found",
                    "fields": {},
                }
            measurements_before = copy.deepcopy(measurements)
            quality_before = copy.deepcopy(quality)
            evaluator = ShortLineCandidateEvaluator(
                desktop_model,
                config,
                labelme_reference_path=annotation,
            )
            records = evaluator.evaluate_gray(target_pixels, measurements, quality)

        projected = records["19��"]["diagnostic"]["candidateSearch"]["projectedGeometry"]
        self.assertIsNotNone(projected)
        projected_midpoint = ((projected["x1"] + projected["x2"]) * 0.5, (projected["y1"] + projected["y2"]) * 0.5)
        self.assertAlmostEqual(140.0, projected_midpoint[0], delta=6.0)
        self.assertAlmostEqual(200.0, projected_midpoint[1], delta=6.0)
        self.assertGreater(math.dist(projected_midpoint, (497.0, 100.0)), 250.0)
        self.assertTrue(records["19��"]["diagnostic"]["candidateSearch"]["registration"]["valid"])
        self.assertEqual(measurements_before, measurements)
        self.assertEqual(quality_before, quality)

    def test_v2_without_external_labelme_is_blocked(self) -> None:
        config = load_candidate_config(Path("config/end_face_short_line_candidate.v2.json"))
        model = SimpleNamespace(shapes=[], reference_grad=np.zeros((16, 16)), alignment_center=(8.0, 8.0))
        with self.assertRaisesRegex(ValueError, "blocked without an external"):
            ShortLineCandidateEvaluator(model, config)

if __name__ == "__main__":
    unittest.main()
