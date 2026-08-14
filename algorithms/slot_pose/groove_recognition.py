"""Explainable single-frame filtering of raw circular dark regions into grooves."""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from typing import Any, Iterable

import numpy as np

from algorithms.slot_pose.angular_profile import NotchCandidate


DEFAULT_GROOVE_RECOGNITION_CONFIG: dict[str, Any] = {
    "threshold_version": "groove-geometry-v1",
    "n_radii": 81,
    "radial_span_px": 120.0,
    "shoulder_width_deg": 4.0,
    "shoulder_gap_deg": 1.0,
    "search_margin_deg": 8.0,
    "min_local_contrast": 20.0,
    "min_edge_contrast": 15.0,
    "min_radial_depth_px": 35.0,
    "min_radial_depth_ratio": 0.25,
    "min_paired_edge_support": 0.55,
    "min_contour_continuity": 0.72,
    "max_width_coefficient_of_variation": 0.185,
    "max_center_drift_ratio": 0.35,
    "min_tangential_width_px": 8.0,
    "max_tangential_width_px": 1200.0,
    "outer_connection_tolerance_px": 12.0,
    "max_gap_rows": 2,
    "min_groove_score": 0.62,
    "ambiguity_margin": 0.05,
}


def validate_groove_config(config: dict[str, Any]) -> None:
    required = set(DEFAULT_GROOVE_RECOGNITION_CONFIG)
    missing = sorted(required - set(config))
    if missing:
        raise ValueError(f"groove_recognition missing fields: {missing}")
    version = config["threshold_version"]
    if not isinstance(version, str) or not version.strip():
        raise ValueError("groove_recognition.threshold_version must be a non-empty string")
    n_radii = int(config["n_radii"])
    max_gap_rows = int(config["max_gap_rows"])
    if n_radii < 16:
        raise ValueError("groove_recognition.n_radii must be >=16")
    if max_gap_rows < 0 or max_gap_rows >= n_radii:
        raise ValueError("groove_recognition.max_gap_rows is invalid")
    positive = (
        "radial_span_px", "shoulder_width_deg", "shoulder_gap_deg", "search_margin_deg",
        "min_local_contrast", "min_edge_contrast", "min_radial_depth_px",
        "min_tangential_width_px", "max_tangential_width_px", "outer_connection_tolerance_px",
    )
    for key in positive:
        value = float(config[key])
        if not math.isfinite(value) or value <= 0.0:
            raise ValueError(f"groove_recognition.{key} must be a positive finite number")
    if float(config["min_tangential_width_px"]) >= float(config["max_tangential_width_px"]):
        raise ValueError("groove_recognition tangential width bounds are invalid")
    for key in (
        "min_radial_depth_ratio", "min_paired_edge_support", "min_contour_continuity",
        "max_width_coefficient_of_variation", "max_center_drift_ratio",
        "min_groove_score", "ambiguity_margin",
    ):
        value = float(config[key])
        if not math.isfinite(value) or not 0.0 <= value <= 1.0:
            raise ValueError(f"groove_recognition.{key} must be in [0,1]")


def merged_groove_config(config: dict[str, Any] | None) -> dict[str, Any]:
    merged = {**DEFAULT_GROOVE_RECOGNITION_CONFIG, **(config or {})}
    validate_groove_config(merged)
    return merged


@dataclass(frozen=True)
class _RowEvidence:
    dark: bool
    paired_edges: bool
    contrast: float
    left_edge_contrast: float
    right_edge_contrast: float
    width_deg: float | None
    center_offset_deg: float | None


def _indices(center: int, offsets: range, count: int) -> np.ndarray:
    return np.asarray([(center + offset) % count for offset in offsets], dtype=np.int64)


def _best_dark_run(
    row: np.ndarray,
    center_index: int,
    candidate_half_samples: int,
    search_half_samples: int,
    threshold: float,
    step_deg: float,
) -> tuple[float, float] | None:
    values = row[_indices(center_index, range(-search_half_samples, search_half_samples + 1), row.size)]
    mask = values < threshold
    runs: list[tuple[int, int]] = []
    start = None
    for index, flag in enumerate(mask.tolist() + [False]):
        if flag and start is None:
            start = index
        elif not flag and start is not None:
            runs.append((start, index - 1))
            start = None
    candidate_low = search_half_samples - candidate_half_samples
    candidate_high = search_half_samples + candidate_half_samples
    scored = []
    for low, high in runs:
        overlap = max(0, min(high, candidate_high) - max(low, candidate_low) + 1)
        if overlap:
            scored.append((overlap, high - low + 1, low, high))
    if not scored:
        return None
    _, width, low, high = max(scored, key=lambda item: (item[0], item[1], -abs((item[2] + item[3]) / 2 - search_half_samples)))
    center_offset = ((low + high) / 2.0 - search_half_samples) * step_deg
    return width * step_deg, center_offset


def _row_evidence(
    row: np.ndarray,
    candidate: NotchCandidate,
    config: dict[str, Any],
) -> _RowEvidence:
    count = row.size
    step = 360.0 / count
    center = int(round(candidate.center_deg / step)) % count
    half = max(1, int(math.ceil(candidate.half_width_deg / step)))
    gap = max(1, int(math.ceil(float(config["shoulder_gap_deg"]) / step)))
    shoulder = max(2, int(math.ceil(float(config["shoulder_width_deg"]) / step)))
    margin = max(1, int(math.ceil(float(config["search_margin_deg"]) / step)))
    inside = _indices(center, range(-half, half + 1), count)
    left = _indices(center, range(-half - gap - shoulder, -half - gap), count)
    right = _indices(center, range(half + gap + 1, half + gap + shoulder + 1), count)
    inside_level = float(np.median(row[inside]))
    left_level = float(np.median(row[left]))
    right_level = float(np.median(row[right]))
    metal_level = min(left_level, right_level)
    contrast = metal_level - inside_level
    left_edge_contrast = left_level - inside_level
    right_edge_contrast = right_level - inside_level
    dark = contrast >= float(config["min_local_contrast"])
    paired = (
        dark
        and left_edge_contrast >= float(config["min_edge_contrast"])
        and right_edge_contrast >= float(config["min_edge_contrast"])
    )
    run = _best_dark_run(row, center, half, half + margin, metal_level - float(config["min_local_contrast"]), step)
    return _RowEvidence(
        dark=dark,
        paired_edges=paired and run is not None,
        contrast=contrast,
        left_edge_contrast=left_edge_contrast,
        right_edge_contrast=right_edge_contrast,
        width_deg=None if run is None else run[0],
        center_offset_deg=None if run is None else run[1],
    )


def _outer_connected_rows(dark: list[bool], radial_step_px: float, tolerance_px: float, max_gap: int) -> list[int]:
    tolerance_rows = max(1, int(math.ceil(tolerance_px / radial_step_px)))
    outer_zone_start = max(0, len(dark) - tolerance_rows)
    starts = [index for index in range(outer_zone_start, len(dark)) if dark[index]]
    if not starts:
        return []
    current = max(starts)
    connected = [current]
    gap = 0
    for index in range(current - 1, -1, -1):
        if dark[index]:
            connected.append(index)
            gap = 0
        else:
            gap += 1
            if gap > max_gap:
                break
    return sorted(connected)


def _bounded_score(value: float, threshold: float) -> float:
    return min(1.0, max(0.0, value / max(threshold, 1e-9)))


def assess_groove(
    polar: np.ndarray,
    candidate: NotchCandidate,
    outer_radius_px: float,
    radial_span_px: float,
    config: dict[str, Any],
    *,
    pixel_scale: float = 1.0,
) -> dict[str, Any]:
    values = np.asarray(polar, dtype=np.float64)
    if values.ndim != 2 or values.shape[0] < 2 or values.shape[1] < 36 or not np.isfinite(values).all():
        raise ValueError("groove recognition polar image must be finite 2D data")
    if not math.isfinite(outer_radius_px) or outer_radius_px <= 0.0 or radial_span_px <= 0.0 or pixel_scale <= 0.0:
        raise ValueError("groove recognition geometry is invalid")
    config = merged_groove_config(config)
    rows = [_row_evidence(row, candidate, config) for row in values]
    radial_step = radial_span_px / max(1, values.shape[0] - 1)
    connected = _outer_connected_rows(
        [row.dark for row in rows], radial_step,
        float(config["outer_connection_tolerance_px"]) * pixel_scale,
        int(config["max_gap_rows"]),
    )
    outer_connected = bool(connected)
    radial_depth = (values.shape[0] - 1 - min(connected)) * radial_step if connected else 0.0
    radial_depth_ratio = min(1.0, radial_depth / radial_span_px)
    span_rows = list(range(min(connected), max(connected) + 1)) if connected else []
    contour_continuity = (
        sum(rows[index].dark for index in span_rows) / len(span_rows) if span_rows else 0.0
    )
    edge_rows = [index for index in connected if rows[index].paired_edges]
    paired_edge_support = len(edge_rows) / len(connected) if connected else 0.0
    contrasts = [rows[index].contrast for index in connected]
    left_edges = [rows[index].left_edge_contrast for index in connected]
    right_edges = [rows[index].right_edge_contrast for index in connected]
    widths = [rows[index].width_deg for index in edge_rows if rows[index].width_deg is not None]
    centers = [rows[index].center_offset_deg for index in edge_rows if rows[index].center_offset_deg is not None]
    local_contrast = float(np.median(contrasts)) if contrasts else 0.0
    left_edge = float(np.median(left_edges)) if left_edges else 0.0
    right_edge = float(np.median(right_edges)) if right_edges else 0.0
    width_mean = statistics.fmean(widths) if widths else 2.0 * candidate.half_width_deg
    width_cv = statistics.pstdev(widths) / width_mean if len(widths) > 1 and width_mean > 0.0 else 0.0
    center_drift = statistics.pstdev(centers) if len(centers) > 1 else 0.0
    center_drift_ratio = center_drift / max(candidate.half_width_deg, 1e-9)
    angular_width = 2.0 * candidate.half_width_deg
    tangential_width = math.radians(angular_width) * outer_radius_px
    min_depth = float(config["min_radial_depth_px"]) * pixel_scale

    rejection: list[str] = []
    if not outer_connected:
        rejection.append("outer_edge_not_connected")
    if radial_depth < min_depth or radial_depth_ratio < float(config["min_radial_depth_ratio"]):
        rejection.append("radial_depth_too_small")
    if local_contrast < float(config["min_local_contrast"]):
        rejection.append("local_metal_contrast_too_low")
    if paired_edge_support < float(config["min_paired_edge_support"]):
        rejection.append("paired_edge_support_too_low")
    if contour_continuity < float(config["min_contour_continuity"]):
        rejection.append("contour_discontinuous")
    if width_cv > float(config["max_width_coefficient_of_variation"]):
        rejection.append("width_variation_too_high")
    if center_drift_ratio > float(config["max_center_drift_ratio"]):
        rejection.append("center_drift_too_high")
    if not float(config["min_tangential_width_px"]) * pixel_scale <= tangential_width <= float(config["max_tangential_width_px"]) * pixel_scale:
        rejection.append("tangential_width_out_of_range")

    scores = [
        _bounded_score(radial_depth, min_depth),
        _bounded_score(radial_depth_ratio, float(config["min_radial_depth_ratio"])),
        _bounded_score(local_contrast, float(config["min_local_contrast"])),
        _bounded_score(paired_edge_support, float(config["min_paired_edge_support"])),
        _bounded_score(contour_continuity, float(config["min_contour_continuity"])),
        max(0.0, 1.0 - width_cv / max(float(config["max_width_coefficient_of_variation"]), 1e-9)),
        max(0.0, 1.0 - center_drift_ratio / max(float(config["max_center_drift_ratio"]), 1e-9)),
    ]
    groove_score = statistics.fmean(scores)
    score_threshold = float(config["min_groove_score"])
    ambiguity_margin = float(config["ambiguity_margin"])
    hard_passed = not rejection
    accepted = hard_passed and groove_score >= score_threshold + ambiguity_margin
    uncertain = hard_passed and not accepted and groove_score >= score_threshold - ambiguity_margin
    if hard_passed and not accepted and not uncertain:
        rejection.append("groove_score_too_low")
    return {
        "candidateId": candidate.candidate_id,
        "grooveScore": groove_score,
        "accepted": accepted,
        "uncertain": uncertain,
        "rejectionReasons": rejection,
        "radialDepthPx": radial_depth,
        "radialDepthRatio": radial_depth_ratio,
        "angularWidthDeg": angular_width,
        "tangentialWidthPx": tangential_width,
        "localMetalContrast": local_contrast,
        "leftEdgeContrast": left_edge,
        "rightEdgeContrast": right_edge,
        "pairedEdgeSupport": paired_edge_support,
        "contourContinuity": contour_continuity,
        "widthMeanDeg": width_mean,
        "widthCoefficientOfVariation": width_cv,
        "centerDriftDeg": center_drift,
        "centerDriftRatio": center_drift_ratio,
        "outerConnected": outer_connected,
        "thresholdVersion": config["threshold_version"],
    }


def recognize_grooves(
    polar: np.ndarray,
    candidates: Iterable[NotchCandidate],
    outer_radius_px: float,
    radial_span_px: float,
    config: dict[str, Any] | None,
    minimum_required_count: int,
    *,
    pixel_scale: float = 1.0,
) -> dict[str, Any]:
    if minimum_required_count < 1:
        raise ValueError("minimum_required_count must be positive")
    merged = merged_groove_config(config)
    items = sorted(candidates, key=lambda item: (item.center_deg, item.candidate_id))
    assessments = [
        assess_groove(polar, item, outer_radius_px, radial_span_px, merged, pixel_scale=pixel_scale)
        for item in items
    ]
    accepted_ids = [item["candidateId"] for item in assessments if item["accepted"]]
    uncertain_ids = [item["candidateId"] for item in assessments if item["uncertain"]]
    if len(accepted_ids) >= minimum_required_count:
        status = "accepted"
    elif len(accepted_ids) + len(uncertain_ids) >= minimum_required_count and uncertain_ids:
        status = "ambiguous"
    else:
        status = "failed"
    return {
        "thresholdVersion": merged["threshold_version"],
        "minimumRequiredCount": minimum_required_count,
        "rawCandidateCount": len(items),
        "acceptedCount": len(accepted_ids),
        "acceptedCandidateIds": accepted_ids,
        "uncertainCandidateIds": uncertain_ids,
        "status": status,
        "assessments": assessments,
    }
