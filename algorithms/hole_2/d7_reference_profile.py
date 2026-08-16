"""Independent D7 reference-profile phase candidate.

This module is deliberately outside the formal current-capture measurement
decision.  It transfers the *photometric context* of the two authoritative
manual D7 boundaries to a target image and emits an auditable candidate.  It
never changes the formal D7 value or validity.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from .main import (
    D7_BOUNDARY_MIN_AXIS_COSINE,
    bilinear_sample,
    boundary_parallelism_deg,
    line_axis_intersection,
    parabolic_peak,
    robust_fit_line,
)


AUDIT_CONTRACT_VERSION = "d7-reference-profile-audit/1"


@dataclass(frozen=True)
class ReferenceBoundaryProfile:
    side: str
    axis: tuple[float, float]
    tangent: tuple[float, float]
    offsets_ref_px: np.ndarray
    intensity_template: np.ndarray
    gradient_template: np.ndarray
    context_step: float
    transition_offsets_ref_px: tuple[float, float]
    transition_signs: tuple[float, float]
    manual_phase_fraction: float
    contrast: float
    source_profile_count: int


def _context_step(values: np.ndarray, offsets: np.ndarray) -> float:
    """Measure the material-level change across, but away from, the edge band."""
    extent = float(np.max(np.abs(offsets)))
    negative = (offsets >= -0.70 * extent) & (offsets <= -0.35 * extent)
    positive = (offsets >= 0.35 * extent) & (offsets <= 0.70 * extent)
    if int(negative.sum()) < 2 or int(positive.sum()) < 2:
        return 0.0
    return float(np.median(values[positive]) - np.median(values[negative]))


def _unit(vector: tuple[float, float]) -> tuple[float, float]:
    length = math.hypot(*vector)
    if not math.isfinite(length) or length < 1e-9:
        raise ValueError("D7 axis is degenerate")
    return float(vector[0] / length), float(vector[1] / length)


def _sample_profile(
    image: np.ndarray,
    center: tuple[float, float],
    axis: tuple[float, float],
    offsets: np.ndarray,
) -> np.ndarray | None:
    xs = center[0] + offsets * axis[0]
    ys = center[1] + offsets * axis[1]
    values = np.asarray(bilinear_sample(image, xs, ys), dtype=np.float64)
    if values.ndim != 1 or len(values) < 7 or not bool(np.isfinite(values).all()):
        return None
    return values


def _normalize(values: np.ndarray, *, minimum_contrast: float = 4.0) -> tuple[np.ndarray, float] | None:
    values = np.asarray(values, dtype=np.float64)
    if values.ndim != 1 or len(values) < 3 or not bool(np.isfinite(values).all()):
        return None
    contrast = float(np.percentile(values, 90.0) - np.percentile(values, 10.0))
    centered = values - float(np.mean(values))
    norm = float(np.linalg.norm(centered))
    if contrast < minimum_contrast or norm < 1e-9:
        return None
    return centered / norm, contrast


def _profile_templates(profiles: list[np.ndarray]) -> tuple[np.ndarray, np.ndarray, float]:
    normalized_profiles: list[np.ndarray] = []
    contrasts: list[float] = []
    for profile in profiles:
        normalized = _normalize(profile)
        if normalized is None:
            continue
        values, contrast = normalized
        normalized_profiles.append(values)
        contrasts.append(contrast)
    if len(normalized_profiles) < 3:
        raise ValueError("reference D7 profile support is insufficient")
    intensity = np.median(np.asarray(normalized_profiles), axis=0)
    intensity_normalized = _normalize(intensity, minimum_contrast=0.01)
    if intensity_normalized is None:
        raise ValueError("reference D7 intensity template is degenerate")
    intensity = intensity_normalized[0]
    gradient_raw = np.diff(intensity)
    gradient_normalized = _normalize(gradient_raw, minimum_contrast=0.001)
    if gradient_normalized is None:
        raise ValueError("reference D7 gradient template is degenerate")
    return intensity, gradient_normalized[0], float(np.median(contrasts))


def _transition_pair(
    normalized_profile: np.ndarray,
    offsets: np.ndarray,
    *,
    expected_offsets: tuple[float, float] | None = None,
    expected_signs: tuple[float, float] | None = None,
) -> tuple[float, float, float, float] | None:
    """Find an ordered opposite-polarity transition pair around one layer."""
    gradient = np.diff(np.asarray(normalized_profile, dtype=np.float64))
    mids = 0.5 * (offsets[:-1] + offsets[1:])
    if len(gradient) < 5:
        return None
    reference_width = None
    if expected_offsets is not None:
        reference_width = abs(expected_offsets[1] - expected_offsets[0])
    best: tuple[float, float, float, float, float] | None = None
    for first in range(1, len(gradient) - 1):
        first_value = float(gradient[first])
        if abs(first_value) < abs(float(gradient[first - 1])) or abs(first_value) < abs(float(gradient[first + 1])):
            continue
        for second in range(first + 1, len(gradient) - 1):
            second_value = float(gradient[second])
            if first_value * second_value >= 0.0:
                continue
            if abs(second_value) < abs(float(gradient[second - 1])) or abs(second_value) < abs(float(gradient[second + 1])):
                continue
            first_position = float(mids[first])
            second_position = float(mids[second])
            width = second_position - first_position
            if not 3.0 <= width <= 18.0:
                continue
            signs = (1.0 if first_value > 0.0 else -1.0,
                     1.0 if second_value > 0.0 else -1.0)
            if expected_signs is not None and signs != expected_signs:
                continue
            if reference_width is not None and not 0.55 * reference_width <= width <= 1.65 * reference_width:
                continue
            strength = min(abs(first_value), abs(second_value))
            if expected_offsets is None:
                phase_prior = math.exp(-((0.5 * (first_position + second_position)) ** 2) / (2.0 * 6.0 ** 2))
            else:
                mismatch = (
                    (first_position - expected_offsets[0]) ** 2
                    + (second_position - expected_offsets[1]) ** 2
                )
                phase_prior = math.exp(-mismatch / (2.0 * 5.0 ** 2))
            score = float(strength * phase_prior)
            candidate = (
                score, first_position, second_position,
                float(first_value), float(second_value),
            )
            if best is None or candidate[0] > best[0]:
                best = candidate
    if best is None:
        return None
    return best[1], best[2], best[3], best[4]


def build_reference_profile_models(
    reference_image: np.ndarray,
    p1_ref: tuple[float, float],
    p2_ref: tuple[float, float],
    *,
    profile_half_width_ref_px: float = 24.0,
    tangent_half_width_ref_px: float = 30.0,
    tangent_samples: int = 21,
) -> dict[str, ReferenceBoundaryProfile]:
    """Build A/B profile models from the authoritative manual D7 line."""
    if tangent_samples < 3:
        raise ValueError("reference tangent_samples must be at least 3")
    axis = _unit((p2_ref[0] - p1_ref[0], p2_ref[1] - p1_ref[1]))
    tangent = (-axis[1], axis[0])
    offsets = np.arange(
        -float(profile_half_width_ref_px),
        float(profile_half_width_ref_px) + 0.5,
        1.0,
        dtype=np.float64,
    )
    tangent_offsets = np.linspace(
        -float(tangent_half_width_ref_px),
        float(tangent_half_width_ref_px),
        int(tangent_samples),
    )
    models: dict[str, ReferenceBoundaryProfile] = {}
    for side, origin in (("A", p1_ref), ("B", p2_ref)):
        profiles = []
        for tangent_offset in tangent_offsets:
            center = (
                origin[0] + float(tangent_offset) * tangent[0],
                origin[1] + float(tangent_offset) * tangent[1],
            )
            profile = _sample_profile(reference_image, center, axis, offsets)
            if profile is not None:
                profiles.append(profile)
        intensity, gradient, contrast = _profile_templates(profiles)
        reference_pair = _transition_pair(intensity, offsets)
        if reference_pair is None:
            raise ValueError(f"reference D7-{side} transition pair is unavailable")
        transition_first, transition_second, first_value, second_value = reference_pair
        phase_fraction = (
            (0.0 - transition_first) / (transition_second - transition_first)
        )
        if not 0.0 <= phase_fraction <= 1.0:
            raise ValueError(f"reference D7-{side} manual phase is outside transition pair")
        models[side] = ReferenceBoundaryProfile(
            side=side,
            axis=axis,
            tangent=tangent,
            offsets_ref_px=offsets,
            intensity_template=intensity,
            gradient_template=gradient,
            context_step=_context_step(intensity, offsets),
            transition_offsets_ref_px=(transition_first, transition_second),
            transition_signs=(
                1.0 if first_value > 0.0 else -1.0,
                1.0 if second_value > 0.0 else -1.0,
            ),
            manual_phase_fraction=float(phase_fraction),
            contrast=contrast,
            source_profile_count=len(profiles),
        )
    return models


def _correlation(
    template: np.ndarray,
    values: np.ndarray,
    *,
    minimum_contrast: float = 4.0,
) -> float | None:
    normalized = _normalize(values, minimum_contrast=minimum_contrast)
    if normalized is None:
        return None
    candidate = normalized[0]
    if len(candidate) != len(template):
        return None
    return float(np.dot(template, candidate))


def _match_scan(
    target: np.ndarray,
    model: ReferenceBoundaryProfile,
    center: tuple[float, float],
    axis: tuple[float, float],
    target_scale: float,
    search_window_target_px: float,
    *,
    minimum_score: float,
    minimum_margin: float,
) -> dict[str, float] | None:
    shifts = np.arange(
        -float(search_window_target_px),
        float(search_window_target_px) + 0.5,
        1.0,
        dtype=np.float64,
    )
    sample_offsets = model.offsets_ref_px * float(target_scale)
    scores = np.full(len(shifts), -np.inf, dtype=np.float64)
    intensity_scores = np.full(len(shifts), -np.inf, dtype=np.float64)
    gradient_scores = np.full(len(shifts), -np.inf, dtype=np.float64)
    for index, shift in enumerate(shifts):
        shifted = (
            center[0] + float(shift) * axis[0],
            center[1] + float(shift) * axis[1],
        )
        profile = _sample_profile(target, shifted, axis, sample_offsets)
        if profile is None:
            continue
        intensity_score = _correlation(model.intensity_template, profile)
        normalized_profile = _normalize(profile)
        if intensity_score is None or normalized_profile is None:
            continue
        gradient_score = _correlation(
            model.gradient_template,
            np.diff(normalized_profile[0]),
            minimum_contrast=0.001,
        )
        if gradient_score is None:
            continue
        candidate_context = _context_step(
            normalized_profile[0], model.offsets_ref_px
        )
        reference_context = float(model.context_step)
        if abs(reference_context) >= 0.02:
            if candidate_context * reference_context <= 0.0:
                continue
            context_score = min(
                abs(candidate_context) / abs(reference_context),
                abs(reference_context) / max(abs(candidate_context), 1e-12),
            )
            if context_score < 0.35:
                continue
        else:
            context_score = 1.0
        # Both terms are signed: reversed photometric polarity cannot pass by
        # having a high absolute gradient magnitude.
        score = (
            0.45 * intensity_score
            + 0.35 * gradient_score
            + 0.20 * context_score
        )
        scores[index] = score
        intensity_scores[index] = intensity_score
        gradient_scores[index] = gradient_score
    finite = np.flatnonzero(np.isfinite(scores))
    if len(finite) < 3:
        return None
    best_index = int(finite[int(np.argmax(scores[finite]))])
    best_score = float(scores[best_index])
    if best_score < minimum_score:
        return None
    competitor_mask = np.isfinite(scores)
    competitor_mask[max(0, best_index - 3):min(len(scores), best_index + 4)] = False
    competitors = scores[competitor_mask]
    second_score = float(np.max(competitors)) if len(competitors) else -1.0
    margin = best_score - second_score
    if margin < minimum_margin:
        return None
    delta = 0.0
    if 0 < best_index < len(scores) - 1 and bool(np.isfinite(scores[best_index - 1:best_index + 2]).all()):
        delta = float(parabolic_peak(scores.tolist(), best_index))
    shift = float(shifts[best_index] + delta)
    matched_center = (
        center[0] + shift * axis[0],
        center[1] + shift * axis[1],
    )
    matched_profile = _sample_profile(
        target, matched_center, axis, sample_offsets
    )
    if matched_profile is None:
        return None
    normalized_matched = _normalize(matched_profile)
    if normalized_matched is None:
        return None
    expected_offsets = (
        model.transition_offsets_ref_px[0] * float(target_scale),
        model.transition_offsets_ref_px[1] * float(target_scale),
    )
    pair = _transition_pair(
        normalized_matched[0], sample_offsets,
        expected_offsets=expected_offsets,
        expected_signs=model.transition_signs,
    )
    if pair is None:
        return None
    first_transition, second_transition, _, _ = pair
    phase_correction = float(
        first_transition
        + model.manual_phase_fraction * (second_transition - first_transition)
    )
    # The context match chooses the layer; the paired transitions localize the
    # same dimensionless manual phase inside that layer. A large disagreement
    # means the two independent evidence sources did not identify one object.
    if abs(phase_correction) > 9.0:
        return None
    shift += phase_correction
    return {
        "shift": shift,
        "contextShift": float(shift - phase_correction),
        "phaseCorrection": phase_correction,
        "transitionFirst": float(first_transition),
        "transitionSecond": float(second_transition),
        "score": best_score,
        "margin": float(margin),
        "intensityScore": float(intensity_scores[best_index]),
        "gradientScore": float(gradient_scores[best_index]),
    }


def _invalid_boundary(side: str, reason: str, **values: Any) -> dict[str, Any]:
    return {
        "side": side,
        "valid": False,
        "failureReason": reason,
        "supportCount": int(values.get("supportCount", 0)),
        "scoreMedian": values.get("scoreMedian"),
        "scoreMarginMedian": values.get("scoreMarginMedian"),
        "shiftMedianTargetPx": values.get("shiftMedianTargetPx"),
        "shiftMadTargetPx": values.get("shiftMadTargetPx"),
        "fitResidualTargetPx": values.get("fitResidualTargetPx"),
        "axisCosine": values.get("axisCosine"),
        "featurePointTargetPx": None,
        "lineEquation": None,
        "segmentPointsTargetPx": [],
        "matchedPointsTargetPx": values.get("matchedPointsTargetPx", []),
    }


def _match_boundary(
    target: np.ndarray,
    model: ReferenceBoundaryProfile,
    origin: tuple[float, float],
    axis: tuple[float, float],
    tangent: tuple[float, float],
    *,
    target_scale: float,
    search_window_target_px: float,
    tangent_half_width_target_px: float,
    tangent_samples: int,
    min_support: int,
    minimum_score: float,
    minimum_margin: float,
    maximum_shift_mad_px: float,
    maximum_fit_residual_px: float,
) -> dict[str, Any]:
    points: list[tuple[float, float]] = []
    shifts: list[float] = []
    scores: list[float] = []
    margins: list[float] = []
    per_scan: list[dict[str, float]] = []
    for tangent_offset in np.linspace(
        -float(tangent_half_width_target_px),
        float(tangent_half_width_target_px),
        int(tangent_samples),
    ):
        center = (
            origin[0] + float(tangent_offset) * tangent[0],
            origin[1] + float(tangent_offset) * tangent[1],
        )
        matched = _match_scan(
            target, model, center, axis, target_scale,
            search_window_target_px,
            minimum_score=minimum_score,
            minimum_margin=minimum_margin,
        )
        if matched is None:
            continue
        shift = float(matched["shift"])
        points.append((
            float(center[0] + shift * axis[0]),
            float(center[1] + shift * axis[1]),
        ))
        shifts.append(shift)
        scores.append(float(matched["score"]))
        margins.append(float(matched["margin"]))
        per_scan.append({"tangentOffsetTargetPx": float(tangent_offset), **matched})
    common = {
        "supportCount": len(points),
        "scoreMedian": None if not scores else float(np.median(scores)),
        "scoreMarginMedian": None if not margins else float(np.median(margins)),
        "shiftMedianTargetPx": None if not shifts else float(np.median(shifts)),
        "shiftMadTargetPx": None if not shifts else float(np.median(np.abs(
            np.asarray(shifts) - float(np.median(shifts))
        ))),
        "matchedPointsTargetPx": [list(point) for point in points],
        "scanDiagnostics": per_scan,
    }
    if len(points) < int(min_support):
        return _invalid_boundary(model.side, "profile_support_below_gate", **common)
    if float(common["shiftMadTargetPx"]) > float(maximum_shift_mad_px):
        return _invalid_boundary(model.side, "profile_shift_mad_above_gate", **common)
    fitted = robust_fit_line(points, min_points=int(min_support))
    if fitted is None:
        return _invalid_boundary(model.side, "profile_line_fit_failed", **common)
    line, inliers = fitted
    residuals = np.abs(line[0] * inliers[:, 0] + line[1] * inliers[:, 1] + line[2])
    residual = float(np.median(residuals))
    axis_cosine = abs(float(line[0]) * axis[0] + float(line[1]) * axis[1])
    common.update({"fitResidualTargetPx": residual, "axisCosine": axis_cosine})
    if residual > float(maximum_fit_residual_px):
        return _invalid_boundary(model.side, "profile_fit_residual_above_gate", **common)
    if axis_cosine < D7_BOUNDARY_MIN_AXIS_COSINE:
        return _invalid_boundary(model.side, "profile_axis_alignment_below_gate", **common)
    intersection = line_axis_intersection(
        tuple(float(value) for value in line), origin, axis
    )
    if intersection is None:
        return _invalid_boundary(model.side, "profile_axis_intersection_failed", **common)
    feature_point, _ = intersection
    direction = np.asarray([-float(line[1]), float(line[0])], dtype=np.float64)
    projections = inliers @ direction
    segment = [
        inliers[int(np.argmin(projections))].tolist(),
        inliers[int(np.argmax(projections))].tolist(),
    ]
    return {
        "side": model.side,
        "valid": True,
        "failureReason": None,
        **common,
        "inlierCount": int(len(inliers)),
        "featurePointTargetPx": [float(feature_point[0]), float(feature_point[1])],
        "lineEquation": [float(value) for value in line],
        "segmentPointsTargetPx": segment,
    }


def evaluate_reference_profile_candidate(
    target: np.ndarray,
    models: dict[str, ReferenceBoundaryProfile],
    p1_target: tuple[float, float],
    p2_target: tuple[float, float],
    *,
    target_scale: float,
    search_window_target_px: float = 42.0,
    tangent_half_width_target_px: float = 30.0,
    tangent_samples: int = 21,
    min_support: int = 12,
    minimum_score: float = 0.58,
    minimum_margin: float = 0.025,
    maximum_shift_mad_px: float = 2.5,
    maximum_fit_residual_px: float = 3.0,
    maximum_parallelism_deg: float = 12.0,
) -> dict[str, Any]:
    """Evaluate an independent D7 candidate without updating formal output."""
    if set(models) != {"A", "B"}:
        raise ValueError("reference profile models must contain A and B")
    if not math.isfinite(target_scale) or target_scale <= 0.0:
        raise ValueError("target_scale must be finite and positive")
    axis = _unit((p2_target[0] - p1_target[0], p2_target[1] - p1_target[1]))
    tangent = (-axis[1], axis[0])
    boundaries = {
        side: _match_boundary(
            target, models[side], origin, axis, tangent,
            target_scale=target_scale,
            search_window_target_px=search_window_target_px,
            tangent_half_width_target_px=tangent_half_width_target_px,
            tangent_samples=tangent_samples,
            min_support=min_support,
            minimum_score=minimum_score,
            minimum_margin=minimum_margin,
            maximum_shift_mad_px=maximum_shift_mad_px,
            maximum_fit_residual_px=maximum_fit_residual_px,
        )
        for side, origin in (("A", p1_target), ("B", p2_target))
    }
    failure_reasons = [
        f"{side}:{boundary['failureReason']}"
        for side, boundary in boundaries.items() if not boundary["valid"]
    ]
    parallelism = None
    measurement = None
    if not failure_reasons:
        parallelism = boundary_parallelism_deg(
            tuple(boundaries["A"]["lineEquation"]),
            tuple(boundaries["B"]["lineEquation"]),
        )
        if parallelism > float(maximum_parallelism_deg):
            failure_reasons.append("both:profile_parallelism_above_gate")
        else:
            measurement = float(math.dist(
                boundaries["A"]["featurePointTargetPx"],
                boundaries["B"]["featurePointTargetPx"],
            ))
    return {
        "contractVersion": AUDIT_CONTRACT_VERSION,
        "candidateValid": not failure_reasons,
        "failureReason": None if not failure_reasons else ",".join(failure_reasons),
        "formalMeasurementUpdated": False,
        "measurementTargetPx": measurement,
        "boundaryA": boundaries["A"],
        "boundaryB": boundaries["B"],
        "parallelismDeg": None if parallelism is None else float(parallelism),
    }


def _line_from_points(points: list[list[float]]) -> tuple[float, float, float]:
    if len(points) != 2:
        raise ValueError("manual D7 boundary must contain exactly two points")
    fitted = robust_fit_line(
        [(float(point[0]), float(point[1])) for point in points], min_points=2
    )
    if fitted is None:
        raise ValueError("manual D7 boundary line is degenerate")
    return tuple(float(value) for value in fitted[0])


def _manual_width(lines: dict[str, tuple[float, float, float]], points: dict[str, list[list[float]]]) -> float:
    directions = []
    for side in ("A", "B"):
        a, b, _ = lines[side]
        direction = np.asarray([-b, a], dtype=np.float64)
        if directions and float(np.dot(directions[0], direction)) < 0.0:
            direction = -direction
        directions.append(direction)
    tangent = directions[0] + directions[1]
    tangent /= float(np.linalg.norm(tangent))
    normal = np.asarray([-tangent[1], tangent[0]], dtype=np.float64)
    offsets = []
    for side in ("A", "B"):
        midpoint = np.mean(np.asarray(points[side], dtype=np.float64), axis=0)
        offsets.append(float(np.dot(midpoint, normal)))
    return abs(offsets[1] - offsets[0])


def _labelme_d7_truth(
    labelme_path: Path,
) -> tuple[dict[str, list[list[float]]], list[list[float]] | None]:
    data = json.loads(Path(labelme_path).read_text(encoding="utf-8"))
    manual_points: dict[str, list[list[float]]] = {}
    measurement_line: list[list[float]] | None = None
    accepted = {
        "d7-a": "A", "7-a": "A", "d7_a": "A",
        "d7-b": "B", "7-b": "B", "d7_b": "B",
    }
    for shape in data.get("shapes", []):
        label = str(shape.get("label", "")).strip().lower()
        if label == "7" and shape.get("shape_type") == "line":
            points = shape.get("points") or []
            if len(points) == 2:
                measurement_line = points
        side = accepted.get(label)
        if side is None:
            continue
        if shape.get("shape_type") != "line":
            raise ValueError(f"D7-{side} must be a LabelMe line")
        manual_points[side] = shape.get("points") or []
    if set(manual_points) != {"A", "B"} and measurement_line is None:
        missing = "A" if "A" not in manual_points else "B"
        raise ValueError(f"target LabelMe is missing D7-{missing}")
    return manual_points, measurement_line


def _distribution(values: list[float]) -> dict[str, float | int | None]:
    finite = np.asarray([value for value in values if math.isfinite(value)], dtype=np.float64)
    if len(finite) == 0:
        return {
            "count": 0, "median": None, "mad": None,
            "p10": None, "p90": None,
        }
    median = float(np.median(finite))
    return {
        "count": int(len(finite)),
        "median": median,
        "mad": float(np.median(np.abs(finite - median))),
        "p10": float(np.percentile(finite, 10.0)),
        "p90": float(np.percentile(finite, 90.0)),
    }


def compare_formal_evidence_to_labelme(
    formal_feature: dict[str, Any], labelme_path: Path,
) -> dict[str, Any]:
    """Compare frozen formal D7 edge layers with offline A/B truth lines.

    The target annotation is read only by this evaluation helper.  Selection
    uses the already-emitted formal fit and its unchanged residual gate; it
    never feeds a phase, offset, or validity decision back into detection.
    """
    manual_points, _ = _labelme_d7_truth(labelme_path)
    if set(manual_points) != {"A", "B"}:
        raise ValueError("formal edge-layer comparison requires D7-A and D7-B")
    manual_lines = {
        side: _line_from_points(manual_points[side]) for side in ("A", "B")
    }
    manual_width = _manual_width(manual_lines, manual_points)
    target = formal_feature.get("target") or {}
    raw = target.get("rawEdgeEvidence") or {}
    raw_boundaries = {
        str(item.get("side")): item
        for item in raw.get("boundaries", []) if isinstance(item, dict)
    }
    fitted_geometry = target.get("fittedGeometry") or {}
    fitted_boundaries = {
        str(item.get("side")): item
        for item in fitted_geometry.get("boundaries", [])
        if isinstance(item, dict)
    }
    quality = formal_feature.get("quality") or {}
    sides: dict[str, Any] = {}
    for side, strip_key in (
        ("A", "d7.quality.candidate_p1_strip"),
        ("B", "d7.quality.candidate_p2_strip"),
    ):
        truth_line = np.asarray(manual_lines[side], dtype=np.float64)
        pairs = np.asarray(
            raw_boundaries.get(side, {}).get("transitionPairsPx", []),
            dtype=np.float64,
        )
        if pairs.ndim != 3 or pairs.shape[1:] != (2, 2):
            pairs = np.empty((0, 2, 2), dtype=np.float64)
        strip = quality.get(strip_key) or {}
        selection_line = strip.get("fittedLine")
        selection_gate = strip.get("layerStabilizationResidualGatePx")
        selection_source = "formal_side_fit_with_existing_residual_gate"
        if not isinstance(selection_line, list) or len(selection_line) != 3:
            selection_line = fitted_boundaries.get(side, {}).get("lineEquation")
            selection_gate = None
            selection_source = "formal_shared_fit_without_pair_filter"
        if (
            len(pairs) and isinstance(selection_line, list)
            and len(selection_line) == 3 and selection_gate is not None
        ):
            line = np.asarray(selection_line, dtype=np.float64)
            mids = np.mean(pairs, axis=1)
            keep = np.abs(mids @ line[:2] + line[2]) <= float(selection_gate)
            selected = pairs[keep]
        else:
            selected = pairs
        layers = {
            "outer": selected[:, 0, :] if len(selected) else np.empty((0, 2)),
            "midpoint": np.mean(selected, axis=1) if len(selected) else np.empty((0, 2)),
            "inner": selected[:, 1, :] if len(selected) else np.empty((0, 2)),
        }
        layer_report: dict[str, Any] = {}
        for name, points in layers.items():
            signed = [
                float(truth_line[0] * point[0] + truth_line[1] * point[1] + truth_line[2])
                for point in points
            ]
            layer_report[name] = {
                "signedDistancePx": _distribution(signed),
                "absoluteDistanceMedianPx": (
                    None if not signed else float(np.median(np.abs(signed)))
                ),
            }
        phases: list[float] = []
        for outer, inner in selected:
            outer_distance = float(
                truth_line[0] * outer[0] + truth_line[1] * outer[1] + truth_line[2]
            )
            inner_distance = float(
                truth_line[0] * inner[0] + truth_line[1] * inner[1] + truth_line[2]
            )
            denominator = inner_distance - outer_distance
            if abs(denominator) > 1e-12:
                phases.append(float(-outer_distance / denominator))
        formal_line = fitted_boundaries.get(side, {}).get("lineEquation")
        formal_line_distance = None
        if isinstance(formal_line, list) and len(formal_line) == 3:
            a, b, c = [float(value) for value in formal_line]
            formal_line_distance = float(np.mean([
                abs(a * float(point[0]) + b * float(point[1]) + c)
                for point in manual_points[side]
            ]))
        sides[side] = {
            "rawPairCount": int(len(pairs)),
            "selectedPairCount": int(len(selected)),
            "selectionSource": selection_source,
            "selectionResidualGatePx": (
                None if selection_gate is None else float(selection_gate)
            ),
            "formalLineDistancePx": formal_line_distance,
            "manualPhaseDefinition": "outer=0_midpoint=0.5_inner=1",
            "manualPhaseFraction": _distribution(phases),
            "manualPhaseWithinPairCount": int(sum(
                0.0 <= phase <= 1.0 for phase in phases
            )),
            "layers": layer_report,
            "manualLinePointsPx": manual_points[side],
        }
    formal_width = target.get("lengthPx")
    return {
        "truthRole": "offline_evaluation_only_not_runtime_input",
        "truthPath": str(labelme_path),
        "truthSha256": hashlib.sha256(Path(labelme_path).read_bytes()).hexdigest(),
        "manualMeasurementTargetPx": float(manual_width),
        "formalMeasurementTargetPx": formal_width,
        "measurementLengthErrorPx": (
            None if formal_width is None
            else abs(float(formal_width) - float(manual_width))
        ),
        "formalMeasurementUpdated": False,
        "sides": sides,
    }


def compare_audit_to_labelme(audit: dict[str, Any], labelme_path: Path) -> dict[str, Any]:
    """Offline-only coordinate comparison against explicit D7-A/D7-B lines."""
    manual_points, measurement_line = _labelme_d7_truth(labelme_path)
    boundary_line_truth = set(manual_points) == {"A", "B"}
    if not boundary_line_truth and measurement_line is None:
        missing = "A" if "A" not in manual_points else "B"
        raise ValueError(f"target LabelMe is missing D7-{missing}")
    if boundary_line_truth:
        manual_lines = {
            side: _line_from_points(manual_points[side]) for side in ("A", "B")
        }
        manual_width = _manual_width(manual_lines, manual_points)
    else:
        assert measurement_line is not None
        manual_width = math.dist(measurement_line[0], measurement_line[1])
    sides: dict[str, Any] = {}
    for side in ("A", "B"):
        candidate = audit.get(f"boundary{side}") or {}
        candidate_line = candidate.get("lineEquation")
        if not candidate.get("valid") or not isinstance(candidate_line, list):
            sides[side] = {
                "candidateAvailable": False,
                "lineDistancePx": None,
                "featurePointDistancePx": None,
            }
            continue
        if boundary_line_truth:
            a, b, c = [float(value) for value in candidate_line]
            distances = [
                abs(a * float(point[0]) + b * float(point[1]) + c)
                for point in manual_points[side]
            ]
            sides[side] = {
                "candidateAvailable": True,
                "lineDistancePx": float(np.mean(distances)),
                "featurePointDistancePx": None,
                "manualLinePointsPx": manual_points[side],
                "candidateLineEquation": candidate_line,
            }
        else:
            assert measurement_line is not None
            truth_point = measurement_line[0 if side == "A" else 1]
            candidate_point = candidate["featurePointTargetPx"]
            sides[side] = {
                "candidateAvailable": True,
                "lineDistancePx": None,
                "featurePointDistancePx": float(math.dist(
                    truth_point, candidate_point
                )),
                "manualMeasurementPointPx": truth_point,
                "candidateFeaturePointPx": candidate_point,
            }
    candidate_width = audit.get("measurementTargetPx")
    return {
        "truthRole": "offline_evaluation_only_not_runtime_input",
        "truthGeometry": (
            "two_boundary_lines" if boundary_line_truth
            else "two_measurement_endpoints"
        ),
        "truthPath": str(labelme_path),
        "truthSha256": hashlib.sha256(Path(labelme_path).read_bytes()).hexdigest(),
        "manualMeasurementTargetPx": float(manual_width),
        "candidateMeasurementTargetPx": candidate_width,
        "measurementLengthErrorPx": (
            None if candidate_width is None
            else abs(float(candidate_width) - float(manual_width))
        ),
        "sides": sides,
    }
