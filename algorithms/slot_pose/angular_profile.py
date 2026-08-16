"""Circular outer-edge dark-region candidates and deterministic notch pairing."""

from __future__ import annotations

import itertools
import math
from dataclasses import asdict, dataclass
from typing import Any, Iterable

import numpy as np


DEFAULT_DARK_CANDIDATE_ROBUSTNESS_CONFIG: dict[str, Any] = {
    "schema_version": "angular-dark-candidate-robustness/1",
    "enabled": False,
    "quantile_levels": [0.05, 0.10],
    "max_hypotheses": 3,
    "dedup_center_deg": 2.0,
    "min_interval_overlap_ratio": 0.5,
}


def merged_dark_candidate_robustness_config(config: dict[str, Any] | None) -> dict[str, Any]:
    supplied = config or {}
    if not isinstance(supplied, dict):
        raise ValueError("detector.dark_candidate_robustness must be an object")
    unknown = sorted(set(supplied) - set(DEFAULT_DARK_CANDIDATE_ROBUSTNESS_CONFIG))
    if unknown:
        raise ValueError(f"detector.dark_candidate_robustness has unknown fields: {unknown}")
    merged = {**DEFAULT_DARK_CANDIDATE_ROBUSTNESS_CONFIG, **supplied}
    if merged["schema_version"] != "angular-dark-candidate-robustness/1":
        raise ValueError("detector.dark_candidate_robustness.schema_version is unsupported")
    if not isinstance(merged["enabled"], bool):
        raise ValueError("detector.dark_candidate_robustness.enabled must be boolean")
    levels = merged["quantile_levels"]
    if (
        not isinstance(levels, list)
        or len(levels) > 3
        or any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in levels)
    ):
        raise ValueError("detector.dark_candidate_robustness.quantile_levels is invalid")
    levels = [float(value) for value in levels]
    if (
        any(not math.isfinite(value) or not 0.0 < value < 0.5 for value in levels)
        or levels != sorted(set(levels))
    ):
        raise ValueError(
            "detector.dark_candidate_robustness.quantile_levels must be unique increasing values in (0,0.5)"
        )
    merged["quantile_levels"] = levels
    maximum = merged["max_hypotheses"]
    if isinstance(maximum, bool) or not isinstance(maximum, int) or not 1 <= maximum <= 4:
        raise ValueError("detector.dark_candidate_robustness.max_hypotheses must be in [1,4]")
    if maximum < 1 + len(levels):
        raise ValueError(
            "detector.dark_candidate_robustness.max_hypotheses is smaller than configured hypotheses"
        )
    for key in ("dedup_center_deg", "min_interval_overlap_ratio"):
        value = merged[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
            raise ValueError(f"detector.dark_candidate_robustness.{key} must be finite")
        merged[key] = float(value)
    if not 0.0 < merged["dedup_center_deg"] <= 30.0:
        raise ValueError("detector.dark_candidate_robustness.dedup_center_deg must be in (0,30]")
    if not 0.0 <= merged["min_interval_overlap_ratio"] <= 1.0:
        raise ValueError(
            "detector.dark_candidate_robustness.min_interval_overlap_ratio must be in [0,1]"
        )
    return merged


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


def _runs_at_threshold(
    smoothed: np.ndarray,
    *,
    threshold: float,
    median: float,
    config: dict[str, Any],
    origin: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    step = 360.0 / float(smoothed.size)
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for run in _circular_runs(smoothed < threshold):
        width = len(run) * step
        half_width = width / 2.0
        prominence = float(median - np.min(smoothed[run]))
        weights = np.maximum(0.0, threshold - smoothed[run])
        reasons: list[str] = []
        if weights.sum() <= 1e-9: reasons.append("zero_deficit")
        if prominence < float(config["min_prominence"]): reasons.append("prominence")
        if half_width < float(config["min_half_width_deg"]): reasons.append("half_width_too_small")
        if half_width > float(config["max_half_width_deg"]): reasons.append("half_width_too_large")
        base = float(run[0]) * step
        offsets = np.arange(len(run), dtype=np.float64) * step
        center = (
            wrap_360_deg(base + float(np.sum(offsets * weights) / np.sum(weights)))
            if weights.sum() > 1e-9 else wrap_360_deg(base + width / 2.0)
        )
        record = {
            "center_deg": center,
            "half_width_deg": half_width,
            "start_deg": wrap_360_deg((float(run[0]) - 0.5) * step),
            "end_deg": wrap_360_deg((float(run[-1]) + 0.5) * step),
            "wraps_boundary": run[0] > run[-1],
            "prominence": prominence,
            "deficit_area": float(np.sum(weights) * step),
            "_indices": frozenset(run),
            "_origin": origin,
        }
        if reasons:
            rejected.append({
                "origin": origin,
                "centerDeg": center,
                "halfWidthDeg": half_width,
                "startDeg": record["start_deg"],
                "endDeg": record["end_deg"],
                "wrapsBoundary": record["wraps_boundary"],
                "prominence": prominence,
                "reasons": reasons,
            })
        else:
            accepted.append(record)
    return accepted, rejected


def _same_dark_run(first: dict[str, Any], second: dict[str, Any], robustness: dict[str, Any]) -> bool:
    if circular_distance_deg(float(first["center_deg"]), float(second["center_deg"])) > float(
        robustness["dedup_center_deg"]
    ):
        return False
    overlap = len(first["_indices"] & second["_indices"])
    denominator = min(len(first["_indices"]), len(second["_indices"]))
    return denominator > 0 and overlap / denominator >= float(robustness["min_interval_overlap_ratio"])


def extract_dark_candidates(
    profile: np.ndarray,
    config: dict[str, Any],
    robustness_config: dict[str, Any] | None = None,
) -> tuple[list[NotchCandidate], dict[str, Any]]:
    """Extract qualifying dark runs; optional hypotheses share one smoothed profile."""
    validate_profile_config(config)
    robustness = merged_dark_candidate_robustness_config(robustness_config)
    values = np.asarray(profile, dtype=np.float64)
    smoothed = circular_smooth(values, int(config["smoothing_window"]))
    median = float(np.median(smoothed))
    mad = float(np.median(np.abs(smoothed - median)))
    robust_sigma = max(1e-6, 1.4826 * mad)
    threshold = median - float(config["mad_multiplier"]) * robust_sigma
    observed_min = float(np.min(smoothed))
    observed_max = float(np.max(smoothed))
    raw_usable = observed_min < threshold < observed_max
    hypotheses: list[tuple[str, float, bool]] = [("mad", threshold, raw_usable)]
    if robustness["enabled"]:
        hypotheses.extend(
            (f"quantile:{level:g}", float(np.quantile(smoothed, level)), True)
            for level in robustness["quantile_levels"]
        )
    accepted_by_hypothesis: list[dict[str, Any]] = []
    rejected_runs: list[dict[str, Any]] = []
    hypothesis_records: list[dict[str, Any]] = []
    threshold_by_origin: dict[str, float] = {}
    for hypothesis_index, (origin, candidate_threshold, usable) in enumerate(
        hypotheses[: int(robustness["max_hypotheses"])], start=1,
    ):
        evaluate = usable or not robustness["enabled"]
        accepted, rejected = (
            _runs_at_threshold(
                smoothed, threshold=candidate_threshold, median=median, config=config, origin=origin,
            ) if evaluate else ([], [])
        )
        accepted_by_hypothesis.extend(accepted)
        rejected_runs.extend(rejected)
        threshold_by_origin[origin] = candidate_threshold
        accepted_public = [{
            "origin": origin,
            "centerDeg": item["center_deg"],
            "halfWidthDeg": item["half_width_deg"],
            "startDeg": item["start_deg"],
            "endDeg": item["end_deg"],
            "wrapsBoundary": item["wraps_boundary"],
            "prominence": item["prominence"],
            "reasons": [],
        } for item in accepted]
        source_value = None if origin == "mad" else float(origin.split(":", 1)[1])
        hypothesis_records.append({
            "hypothesisId": f"hypothesis-{hypothesis_index:03d}",
            "origin": origin,
            "source": "mad" if origin == "mad" else "quantile",
            "sourceValue": source_value,
            "threshold": candidate_threshold,
            "rawThreshold": candidate_threshold,
            "boundedThreshold": min(observed_max, max(observed_min, candidate_threshold)),
            "usable": usable,
            "evaluated": evaluate,
            "status": "evaluated" if evaluate else "unusable",
            "rawRuns": accepted_public + rejected,
            "acceptedRuns": accepted_public,
            "rejectedRuns": rejected,
            "acceptedRunCount": len(accepted),
            "rejectedRunCount": len(rejected),
        })

    if robustness["enabled"]:
        clusters: list[dict[str, Any]] = []
        for item in sorted(
            accepted_by_hypothesis,
            key=lambda value: (float(value["center_deg"]), -float(value["prominence"]), value["_origin"]),
        ):
            cluster = next(
                (current for current in clusters if _same_dark_run(item, current["representative"], robustness)),
                None,
            )
            if cluster is None:
                clusters.append({"representative": item, "origins": {item["_origin"]}})
            else:
                cluster["origins"].add(item["_origin"])
                representative = cluster["representative"]
                if (
                    float(item["prominence"]), float(item["deficit_area"])
                ) > (
                    float(representative["prominence"]), float(representative["deficit_area"])
                ):
                    cluster["representative"] = item
        provisional = [cluster["representative"] for cluster in clusters]
        origins_by_center = {id(cluster["representative"]): sorted(cluster["origins"]) for cluster in clusters}
    else:
        provisional = accepted_by_hypothesis
        origins_by_center = {id(item): [item["_origin"]] for item in provisional}

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
    candidates = []
    candidate_origins: dict[str, list[str]] = {}
    for index, item in enumerate(by_center):
        identifier = f"candidate-{index + 1:03d}"
        candidate_origins[identifier] = origins_by_center[id(item)]
        payload = {key: value for key, value in item.items() if not key.startswith("_")}
        candidates.append(NotchCandidate(candidate_id=identifier, rank=rank_by_index[index], **payload))
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
        "rawDarkThreshold": threshold,
        "thresholdUsable": raw_usable,
        "thresholdMode": "multi_threshold" if robustness["enabled"] else "mad",
        "thresholdHypotheses": hypothesis_records,
        "hypothesisCandidateCount": len(accepted_by_hypothesis),
        "deduplicatedCount": len(candidates),
        "candidateHypothesisOrigins": candidate_origins,
        "candidateOrigins": candidate_origins,
        "candidateSourceThresholds": {
            identifier: [threshold_by_origin[origin] for origin in origins]
            for identifier, origins in candidate_origins.items()
        },
        "rejectedRuns": rejected_runs,
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
