"""Circular outer-edge dark-region candidates and deterministic notch pairing."""

from __future__ import annotations

import itertools
import math
from dataclasses import asdict, dataclass
from typing import Any, Iterable

import numpy as np


def wrap_360_deg(value: float) -> float:
    return float(value) % 360.0


def circular_delta_deg(value: float, reference: float) -> float:
    """Return the signed shortest rotation from reference to value."""
    result = (float(value) - float(reference) + 180.0) % 360.0 - 180.0
    return 0.0 if abs(result) < 1e-12 else result


def circular_distance_deg(a: float, b: float) -> float:
    return abs(circular_delta_deg(a, b))


def circular_midpoint_deg(a: float, b: float) -> float:
    return wrap_360_deg(float(a) + circular_delta_deg(b, a) / 2.0)


@dataclass(frozen=True)
class NotchCandidate:
    candidate_id: str
    center_deg: float
    half_width_deg: float
    start_deg: float
    end_deg: float
    wraps_boundary: bool
    prominence: float
    deficit_area: float
    rank: int

    def to_dict(self) -> dict[str, Any]:
        raw = asdict(self)
        return {
            "candidateId": raw["candidate_id"],
            "centerDeg": raw["center_deg"],
            "halfWidthDeg": raw["half_width_deg"],
            "startDeg": raw["start_deg"],
            "endDeg": raw["end_deg"],
            "wrapsBoundary": raw["wraps_boundary"],
            "prominence": raw["prominence"],
            "deficitArea": raw["deficit_area"],
            "rank": raw["rank"],
        }


@dataclass(frozen=True)
class PairAssessment:
    candidate_ids: tuple[str, str]
    separation_deg: float
    width_ratio: float
    prominence_ratio: float
    centerline_deg: float
    score: float
    failed_checks: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidateIds": list(self.candidate_ids),
            "separationDeg": self.separation_deg,
            "widthRatio": self.width_ratio,
            "prominenceRatio": self.prominence_ratio,
            "centerlineDeg": self.centerline_deg,
            "score": self.score,
            "failedChecks": list(self.failed_checks),
        }


def _positive_number(config: dict[str, Any], key: str) -> float:
    value = float(config[key])
    if not math.isfinite(value) or value <= 0.0:
        raise ValueError(f"{key} must be a positive finite number")
    return value


def validate_profile_config(config: dict[str, Any]) -> None:
    n_angles = int(config["n_angles"])
    n_radii = int(config["n_radii"])
    window = int(config["smoothing_window"])
    if n_angles < 36 or n_radii < 2:
        raise ValueError("profile n_angles must be >=36 and n_radii must be >=2")
    if window < 1 or window > n_angles or window % 2 == 0:
        raise ValueError("profile smoothing_window must be a positive odd value <= n_angles")
    for key in ("shell_width_px", "mad_multiplier", "min_prominence", "min_half_width_deg", "max_half_width_deg"):
        _positive_number(config, key)
    if float(config["min_half_width_deg"]) >= float(config["max_half_width_deg"]):
        raise ValueError("profile min_half_width_deg must be below max_half_width_deg")


def validate_pairing_config(config: dict[str, Any]) -> None:
    minimum = int(config["min_candidates"])
    maximum = int(config["max_candidates"])
    if minimum < 2 or maximum < minimum:
        raise ValueError("pairing candidate bounds must satisfy 2 <= min <= max")
    min_sep = _positive_number(config, "min_separation_deg")
    max_sep = _positive_number(config, "max_separation_deg")
    expected = _positive_number(config, "expected_separation_deg")
    if not min_sep < max_sep <= 180.0 or not min_sep <= expected <= max_sep:
        raise ValueError("pairing separation bounds or expected value are invalid")
    for key in ("min_width_ratio", "min_prominence_ratio", "min_pair_score", "min_score_margin"):
        value = float(config[key])
        if not math.isfinite(value) or not 0.0 <= value <= 1.0:
            raise ValueError(f"{key} must be in [0, 1]")


def circular_smooth(values: np.ndarray, window: int) -> np.ndarray:
    array = np.asarray(values, dtype=np.float64)
    if array.ndim != 1 or array.size == 0:
        raise ValueError("angular profile must be a non-empty one-dimensional array")
    if not np.isfinite(array).all():
        raise ValueError("angular profile must contain only finite values")
    if window < 1 or window > array.size or window % 2 == 0:
        raise ValueError("smoothing window must be a positive odd value <= profile length")
    half = window // 2
    return np.mean([np.roll(array, shift) for shift in range(-half, half + 1)], axis=0)


def _circular_runs(mask: np.ndarray) -> list[list[int]]:
    flags = np.asarray(mask, dtype=bool)
    if flags.ndim != 1 or not flags.any():
        return []
    if flags.all():
        return [list(range(flags.size))]
    starts = [index for index in range(flags.size) if flags[index] and not flags[index - 1]]
    runs: list[list[int]] = []
    for start in starts:
        run: list[int] = []
        index = start
        while flags[index]:
            run.append(index)
            index = (index + 1) % flags.size
        runs.append(run)
    return runs


def extract_dark_candidates(profile: np.ndarray, config: dict[str, Any]) -> tuple[list[NotchCandidate], dict[str, Any]]:
    """Extract every qualifying circular dark run from a one-dimensional profile."""
    validate_profile_config(config)
    values = np.asarray(profile, dtype=np.float64)
    smoothed = circular_smooth(values, int(config["smoothing_window"]))
    median = float(np.median(smoothed))
    mad = float(np.median(np.abs(smoothed - median)))
    robust_sigma = max(1e-6, 1.4826 * mad)
    threshold = median - float(config["mad_multiplier"]) * robust_sigma
    step = 360.0 / float(values.size)
    provisional: list[dict[str, float | bool]] = []
    for run in _circular_runs(smoothed < threshold):
        width = len(run) * step
        half_width = width / 2.0
        prominence = float(median - np.min(smoothed[run]))
        weights = np.maximum(0.0, threshold - smoothed[run])
        if (
            weights.sum() <= 1e-9
            or prominence < float(config["min_prominence"])
            or half_width < float(config["min_half_width_deg"])
            or half_width > float(config["max_half_width_deg"])
        ):
            continue
        base = float(run[0]) * step
        offsets = np.arange(len(run), dtype=np.float64) * step
        center = wrap_360_deg(base + float(np.sum(offsets * weights) / np.sum(weights)))
        start = wrap_360_deg((float(run[0]) - 0.5) * step)
        end = wrap_360_deg((float(run[-1]) + 0.5) * step)
        provisional.append({
            "center_deg": center,
            "half_width_deg": half_width,
            "start_deg": start,
            "end_deg": end,
            "wraps_boundary": start > end,
            "prominence": prominence,
            "deficit_area": float(np.sum(weights) * step),
        })

    by_center = sorted(provisional, key=lambda item: float(item["center_deg"]))
    quality_order = sorted(
        range(len(by_center)),
        key=lambda index: (
            -float(by_center[index]["prominence"]),
            -float(by_center[index]["deficit_area"]),
            float(by_center[index]["center_deg"]),
        ),
    )
    rank_by_index = {index: rank for rank, index in enumerate(quality_order, start=1)}
    candidates = [
        NotchCandidate(candidate_id=f"candidate-{index + 1:03d}", rank=rank_by_index[index], **item)
        for index, item in enumerate(by_center)
    ]
    ranked = sorted(candidates, key=lambda item: item.rank)
    summary = {
        "count": len(candidates),
        "bestCandidateId": ranked[0].candidate_id if ranked else None,
        "secondCandidateId": ranked[1].candidate_id if len(ranked) > 1 else None,
        "prominenceGap": (
            ranked[0].prominence - ranked[1].prominence if len(ranked) > 1 else None
        ),
        "sampleCount": int(values.size),
        "medianIntensity": median,
        "madIntensity": mad,
        "darkThreshold": threshold,
    }
    return candidates, summary


def _safe_ratio(a: float, b: float) -> float:
    maximum = max(float(a), float(b))
    return min(float(a), float(b)) / maximum if maximum > 0.0 else 0.0


def assess_pairs(candidates: Iterable[NotchCandidate], config: dict[str, Any]) -> dict[str, Any]:
    """Assess every pair and select only a score-separated unique best pair."""
    validate_pairing_config(config)
    items = sorted(candidates, key=lambda item: (item.center_deg, item.candidate_id))
    count_failures: list[str] = []
    if len(items) < int(config["min_candidates"]):
        count_failures.append("candidate_count_too_low")
    if len(items) > int(config["max_candidates"]):
        count_failures.append("candidate_count_too_high")

    expected = float(config["expected_separation_deg"])
    separation_span = max(
        expected - float(config["min_separation_deg"]),
        float(config["max_separation_deg"]) - expected,
        1e-9,
    )
    assessments: list[PairAssessment] = []
    for first, second in itertools.combinations(items, 2):
        separation = circular_distance_deg(first.center_deg, second.center_deg)
        width_ratio = _safe_ratio(first.half_width_deg, second.half_width_deg)
        prominence_ratio = _safe_ratio(first.prominence, second.prominence)
        failed: list[str] = []
        if not float(config["min_separation_deg"]) <= separation <= float(config["max_separation_deg"]):
            failed.append("separation")
        if width_ratio < float(config["min_width_ratio"]):
            failed.append("width_ratio")
        if prominence_ratio < float(config["min_prominence_ratio"]):
            failed.append("prominence_ratio")
        separation_score = max(0.0, 1.0 - abs(separation - expected) / separation_span)
        score = (separation_score + width_ratio + prominence_ratio) / 3.0
        assessments.append(PairAssessment(
            candidate_ids=(first.candidate_id, second.candidate_id),
            separation_deg=separation,
            width_ratio=width_ratio,
            prominence_ratio=prominence_ratio,
            centerline_deg=circular_midpoint_deg(first.center_deg, second.center_deg),
            score=score,
            failed_checks=tuple(failed),
        ))

    assessments.sort(key=lambda item: (-item.score, item.candidate_ids))
    qualified = [item for item in assessments if not item.failed_checks]
    best = qualified[0] if qualified else None
    second = qualified[1] if len(qualified) > 1 else None
    margin = (best.score - second.score) if best is not None and second is not None else (best.score if best else None)
    failure_checks = list(count_failures)
    if best is None:
        failure_checks.append("no_pair_passed_geometry")
    elif best.score < float(config["min_pair_score"]):
        failure_checks.append("pair_score")
    if best is not None and second is not None and float(margin or 0.0) < float(config["min_score_margin"]):
        failure_checks.append("pair_not_unique")
    unique = best is not None and not failure_checks
    selected = best if unique else None
    return {
        "assessments": [item.to_dict() for item in assessments],
        "selectedCandidateIds": list(selected.candidate_ids) if selected else None,
        "centerlineDeg": selected.centerline_deg if selected else None,
        "separationDeg": selected.separation_deg if selected else None,
        "widthRatio": selected.width_ratio if selected else None,
        "prominenceRatio": selected.prominence_ratio if selected else None,
        "bestScore": best.score if best else None,
        "secondBestScore": second.score if second else None,
        "scoreMargin": margin,
        "unique": unique,
        "failedChecks": failure_checks,
    }
