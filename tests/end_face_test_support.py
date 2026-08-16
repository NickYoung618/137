from __future__ import annotations

import copy
import json
import math
from pathlib import Path
from types import SimpleNamespace

import numpy as np
from PIL import Image, ImageDraw

from algorithms.end_face import core


DEFAULT_CANDIDATE_CONFIG = {
    "schemaVersion": "a-end-face-short-line-candidate-config/1",
    "candidateId": "reference-gradient-registration-v1",
    "algorithmVersion": "1.0.0",
    "features": ["19", "30"],
    "template": {
        "alongExtensionPx": 6.0,
        "halfWidthPx": 12.0,
        "sampleStepPx": 1.0,
    },
    "search": {
        "coarse": {
            "angleRadiusDeg": 8.0,
            "angleStepDeg": 1.0,
            "longitudinalRadiusPx": 8.0,
            "longitudinalStepPx": 2.0,
            "lateralRadiusPx": 24.0,
            "lateralStepPx": 2.0,
        },
        "fine": {
            "angleRadiusDeg": 1.0,
            "angleStepDeg": 0.25,
            "longitudinalRadiusPx": 2.0,
            "longitudinalStepPx": 0.5,
            "lateralRadiusPx": 2.0,
            "lateralStepPx": 0.5,
        },
    },
    "gates": {
        "minimumPredictionLengthPx": 4.0,
        "maximumPredictionLengthPx": 80.0,
        "minimumCoverageRatio": 0.98,
        "minimumTemplateStd": 2.0,
        "minimumRoiContrast": 8.0,
        "minimumGradientP90": 2.0,
        "minimumCorrelation": 0.45,
        "minimumRobustZ": 2.0,
        "minimumSeparatedPeakGap": 0.015,
        "separationAngleDeg": 4.0,
        "separationLongitudinalPx": 6.0,
        "separationLateralPx": 6.0,
        "maximumAngleCorrectionDeg": 7.75,
    },
}


def write_candidate_config(path: Path, mutate=None) -> dict:
    payload = copy.deepcopy(DEFAULT_CANDIDATE_CONFIG)
    if mutate is not None:
        mutate(payload)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return payload


def _endpoints(midpoint: tuple[float, float], angle_deg: float, length: float) -> tuple[tuple[float, float], tuple[float, float]]:
    angle = math.radians(angle_deg)
    half = np.array([math.cos(angle), math.sin(angle)], dtype=np.float64) * (length * 0.5)
    middle = np.asarray(midpoint, dtype=np.float64)
    p1 = middle - half
    p2 = middle + half
    return (float(p1[0]), float(p1[1])), (float(p2[0]), float(p2[1]))


def draw_short_line(
    midpoint: tuple[float, float],
    angle_deg: float,
    length: float = 48.0,
    foreground: int = 220,
    background: int = 30,
    extra_midpoints: tuple[tuple[float, float], ...] = (),
) -> np.ndarray:
    image = Image.new("L", (128, 128), background)
    draw = ImageDraw.Draw(image)
    for current in (midpoint, *extra_midpoints):
        p1, p2 = _endpoints(current, angle_deg, length)
        draw.line((p1, p2), fill=foreground, width=3)
        # An asymmetric local marker makes longitudinal registration observable.
        draw.ellipse((p1[0] - 2, p1[1] - 2, p1[0] + 2, p1[1] + 2), fill=foreground)
    return core.gaussian_blur(np.asarray(image))


def synthetic_candidate_case(
    *,
    canonical: str = "19",
    target_midpoint: tuple[float, float] = (64.0, 69.0),
    target_angle_deg: float = 3.0,
    foreground: int = 220,
    extra_midpoints: tuple[tuple[float, float], ...] = (),
    core_valid: bool = True,
):
    raw_label = f"{canonical}��"
    reference_midpoint = (64.0, 64.0)
    length = 48.0 if canonical == "19" else 30.0
    reference_points = _endpoints(reference_midpoint, 0.0, length)
    reference_gray = draw_short_line(reference_midpoint, 0.0, length)
    target_gray = draw_short_line(
        target_midpoint,
        target_angle_deg,
        length,
        foreground=foreground,
        extra_midpoints=extra_midpoints,
    )
    shape = SimpleNamespace(label=raw_label, shape_type="line", points=[list(reference_points[0]), list(reference_points[1])])
    reference_model = SimpleNamespace(
        shapes=[shape],
        reference_gray=reference_gray,
        reference_grad=core.gradient_magnitude(reference_gray),
        alignment_center=reference_midpoint,
        reference_path=Path("synthetic-reference.bmp"),
    )
    predicted_p1, predicted_p2 = reference_points
    measurements = {
        "transform.target_center_x_px": 64.0,
        "transform.target_center_y_px": 64.0,
        "transform.scale": 1.0,
        "transform.rotation_deg": 0.0,
        f"{raw_label}.detect.source": "short_line_lateral_edge" if core_valid else "short_line_transform_fallback",
        f"{raw_label}.quality.measurement_valid": 1.0 if core_valid else 0.0,
        f"{raw_label}.quality.anomaly_flag": 0.0 if core_valid else 1.0,
        f"{raw_label}.quality.anomaly_reason": "" if core_valid else "short_line_lateral_edge_not_found",
        f"{raw_label}.x1_px": predicted_p1[0],
        f"{raw_label}.y1_px": predicted_p1[1],
        f"{raw_label}.x2_px": predicted_p2[0],
        f"{raw_label}.y2_px": predicted_p2[1],
        f"{raw_label}.length_px": length,
        f"{raw_label}.angle_deg": 0.0,
        f"{raw_label}.x1_ref_px": predicted_p1[0],
        f"{raw_label}.y1_ref_px": predicted_p1[1],
        f"{raw_label}.x2_ref_px": predicted_p2[0],
        f"{raw_label}.y2_ref_px": predicted_p2[1],
        f"{raw_label}.length_ref_px": length,
        f"{raw_label}.angle_ref_deg": 0.0,
    }
    feature_quality = {
        raw_label: {
            "feature": raw_label,
            "canonicalFeature": canonical,
            "classification": "feature_measurement",
            "coreValid": core_valid,
            "source": "short_line_lateral_edge" if core_valid else "short_line_transform_fallback",
            "reason": None if core_valid else "short_line_lateral_edge_not_found",
            "fields": {
                "measurement_valid": 1.0 if core_valid else 0.0,
                "anomaly_flag": 0.0 if core_valid else 1.0,
                "anomaly_reason": "" if core_valid else "short_line_lateral_edge_not_found",
            },
            "diagnostic": {},
        }
    }
    return reference_model, target_gray, measurements, feature_quality
