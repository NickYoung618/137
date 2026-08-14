#!/usr/bin/env python3
"""Summarize path-safe multi-frame slot-pose review diagnostics."""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from collections import Counter
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.dataset_common import write_json


def circular_delta_deg(value: float, reference: float) -> float:
    return (float(value) - float(reference) + 180.0) % 360.0 - 180.0


def circular_mean_deg(values: list[float]) -> float:
    if not values:
        raise ValueError("circular mean requires at least one value")
    radians = [math.radians(value) for value in values]
    return math.degrees(math.atan2(sum(math.sin(value) for value in radians), sum(math.cos(value) for value in radians))) % 360.0


def percentile(values: list[float], quantile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(float(value) for value in values)
    position = (len(ordered) - 1) * quantile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def _cluster_observations(observations: list[dict[str, Any]], threshold_deg: float) -> list[list[dict[str, Any]]]:
    if not observations:
        return []
    ordered = sorted(observations, key=lambda item: (float(item["angleDeg"]), item["imageId"], item["candidateId"]))
    gaps = [
        (float(ordered[(index + 1) % len(ordered)]["angleDeg"]) - float(ordered[index]["angleDeg"])) % 360.0
        for index in range(len(ordered))
    ]
    start = (max(range(len(gaps)), key=lambda index: gaps[index]) + 1) % len(ordered)
    rotated = ordered[start:] + ordered[:start]
    clusters: list[list[dict[str, Any]]] = [[rotated[0]]]
    for item in rotated[1:]:
        previous = clusters[-1][-1]
        if abs(circular_delta_deg(float(item["angleDeg"]), float(previous["angleDeg"]))) > threshold_deg:
            clusters.append([])
        clusters[-1].append(item)
    return clusters


def candidate_clusters(records: list[dict[str, Any]], threshold_deg: float) -> list[dict[str, Any]]:
    observations = [
        {
            "imageId": record["imageId"],
            "candidateId": candidate["candidateId"],
            "angleDeg": float(candidate["centerDeg"]),
            "halfWidthDeg": float(candidate["halfWidthDeg"]),
            "prominence": float(candidate["prominence"]),
            "rank": int(candidate["rank"]),
        }
        for record in records
        for candidate in record.get("candidates") or []
    ]
    output: list[dict[str, Any]] = []
    frame_count = len(records)
    raw_clusters = _cluster_observations(observations, threshold_deg)
    summaries: list[tuple[float, dict[str, Any]]] = []
    for cluster in raw_clusters:
        angles = [float(item["angleDeg"]) for item in cluster]
        mean = circular_mean_deg(angles)
        deltas = [circular_delta_deg(angle, mean) for angle in angles]
        prominence = [float(item["prominence"]) for item in cluster]
        half_width = [float(item["halfWidthDeg"]) for item in cluster]
        frame_support = len({str(item["imageId"]) for item in cluster})
        radians = [math.radians(angle) for angle in angles]
        resultant = math.hypot(sum(math.cos(value) for value in radians), sum(math.sin(value) for value in radians)) / len(radians)
        circular_std = math.degrees(math.sqrt(max(0.0, -2.0 * math.log(max(resultant, 1e-12)))))
        prominence_mean = statistics.fmean(prominence)
        summary = {
            "clusterId": None,
            "frameSupport": frame_support,
            "frameSupportRate": frame_support / frame_count if frame_count else 0.0,
            "observationCount": len(cluster),
            "circularMeanDeg": mean,
            "circularStdDeg": circular_std,
            "circularRangeDeg": max(deltas) - min(deltas),
            "absoluteDeviationP95Deg": percentile([abs(value) for value in deltas], 0.95),
            "halfWidthMeanDeg": statistics.fmean(half_width),
            "halfWidthStdDeg": statistics.pstdev(half_width) if len(half_width) > 1 else 0.0,
            "prominenceMean": prominence_mean,
            "prominenceP50": percentile(prominence, 0.5),
            "prominenceStd": statistics.pstdev(prominence) if len(prominence) > 1 else 0.0,
            "prominenceCoefficientOfVariation": (
                statistics.pstdev(prominence) / prominence_mean if len(prominence) > 1 and prominence_mean else 0.0
            ),
            "rankCounts": dict(sorted(Counter(str(item["rank"]) for item in cluster).items())),
            "stableDiagnosticFeature": frame_support / frame_count >= 0.8 if frame_count else False,
            "authoritativeRole": False,
        }
        summaries.append((mean, summary))
    for index, (_, summary) in enumerate(sorted(summaries, key=lambda item: item[0]), start=1):
        summary["clusterId"] = f"angle-cluster-{index:03d}"
        output.append(summary)
    return output


def candidate_id_tracks(records: list[dict[str, Any]], threshold_deg: float) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        for candidate in record.get("candidates") or []:
            grouped.setdefault(str(candidate["candidateId"]), []).append({
                "imageId": record["imageId"],
                "candidateId": candidate["candidateId"],
                "angleDeg": float(candidate["centerDeg"]),
                "halfWidthDeg": float(candidate["halfWidthDeg"]),
                "prominence": float(candidate["prominence"]),
                "rank": int(candidate["rank"]),
            })
    frame_count = len(records)
    tracks: list[dict[str, Any]] = []
    for candidate_id, observations in sorted(grouped.items()):
        modes = []
        for mode in _cluster_observations(observations, threshold_deg):
            angles = [float(item["angleDeg"]) for item in mode]
            mean = circular_mean_deg(angles)
            deltas = [circular_delta_deg(angle, mean) for angle in angles]
            modes.append({
                "observationCount": len(mode),
                "circularMeanDeg": mean,
                "circularRangeDeg": max(deltas) - min(deltas),
            })
        modes.sort(key=lambda item: (-int(item["observationCount"]), float(item["circularMeanDeg"])))
        prominence = [float(item["prominence"]) for item in observations]
        half_width = [float(item["halfWidthDeg"]) for item in observations]
        frame_support = len({str(item["imageId"]) for item in observations})
        tracks.append({
            "candidateId": candidate_id,
            "frameSupport": frame_support,
            "frameSupportRate": frame_support / frame_count if frame_count else 0.0,
            "angleModeCount": len(modes),
            "angleModes": modes,
            "imageFrameStable": frame_support / frame_count >= 0.8 and len(modes) == 1 if frame_count else False,
            "halfWidthMeanDeg": statistics.fmean(half_width),
            "halfWidthStdDeg": statistics.pstdev(half_width) if len(half_width) > 1 else 0.0,
            "prominenceMean": statistics.fmean(prominence),
            "prominenceStd": statistics.pstdev(prominence) if len(prominence) > 1 else 0.0,
            "rankCounts": dict(sorted(Counter(str(item["rank"]) for item in observations).items())),
            "authoritativeRole": False,
        })
    return tracks


def summarize_run(label: str, review: dict[str, Any], threshold_deg: float) -> dict[str, Any]:
    records = list(review.get("records") or [])
    total = len(records)
    error_counts = Counter(record.get("result", {}).get("errorCode") or "NONE" for record in records)
    candidate_counts = Counter(len(record.get("candidates") or []) for record in records)
    groove_candidate_counts = Counter(len(record.get("grooveCandidates") or []) for record in records)
    groove_status_counts = Counter(
        (record.get("grooveRecognition") or {}).get("status") or "not_available" for record in records
    )
    groove_rejections = Counter(
        reason
        for record in records
        for assessment in (record.get("grooveRecognition") or {}).get("assessments") or []
        for reason in assessment.get("rejectionReasons") or []
    )
    role_status_counts = Counter(record.get("roleSuggestion", {}).get("status") or "not_available" for record in records)
    role_signatures = Counter(
        json.dumps(record.get("roleSuggestion", {}).get("selectedRoleCandidateIds"), sort_keys=True)
        for record in records
        if record.get("roleSuggestion", {}).get("selectedRoleCandidateIds")
    )
    elapsed = [float(record["elapsedMs"]) for record in records if isinstance(record.get("elapsedMs"), (int, float))]
    circle_count = sum(
        1 for record in records
        if all(isinstance((record.get("face") or {}).get(key), (int, float)) for key in ("centerX", "centerY", "radiusPx"))
    )
    complete_ring_count = sum(1 for record in records if (record.get("angularProfile") or {}).get("completeRing") is True)
    candidate_extraction_count = sum(1 for record in records if record.get("candidateSummary") is not None)
    role_unique_count = sum(1 for record in records if record.get("roleSuggestion", {}).get("status") == "unique_diagnostic_hypothesis")
    formal_valid_count = sum(1 for record in records if record.get("result", {}).get("valid") is True)
    return {
        "label": label,
        "imageCount": total,
        "circleEstimateAvailable": {"count": circle_count, "rate": circle_count / total if total else 0.0},
        "completeRingAccepted": {"count": complete_ring_count, "rate": complete_ring_count / total if total else 0.0},
        "candidateExtractionCompleted": {"count": candidate_extraction_count, "rate": candidate_extraction_count / total if total else 0.0},
        "candidateCountDistribution": {str(key): value for key, value in sorted(candidate_counts.items())},
        "candidateClusters": candidate_clusters(records, threshold_deg),
        "candidateIdTracks": candidate_id_tracks(records, threshold_deg),
        "grooveCandidateCountDistribution": {str(key): value for key, value in sorted(groove_candidate_counts.items())},
        "grooveCandidateClusters": candidate_clusters(
            [{**record, "candidates": record.get("grooveCandidates") or []} for record in records], threshold_deg,
        ),
        "grooveRecognitionStatusCounts": dict(sorted(groove_status_counts.items())),
        "grooveRejectionReasonCounts": dict(sorted(groove_rejections.items())),
        "roleAssignmentUnique": {"count": role_unique_count, "rate": role_unique_count / total if total else 0.0},
        "roleStatusCounts": dict(sorted(role_status_counts.items())),
        "selectedRoleSignatureCounts": dict(sorted(role_signatures.items())),
        "formalValid": {"count": formal_valid_count, "rate": formal_valid_count / total if total else 0.0},
        "errorCodeCounts": dict(sorted(error_counts.items())),
        "elapsedMs": {
            "n": len(elapsed),
            "p50": percentile(elapsed, 0.5),
            "p95": percentile(elapsed, 0.95),
            "max": max(elapsed) if elapsed else None,
        },
    }


def parse_run(value: str) -> tuple[str, Path]:
    label, separator, raw_path = value.partition("=")
    if not separator or not label or not raw_path:
        raise argparse.ArgumentTypeError("run must be LABEL=REVIEW_JSON")
    return label, Path(raw_path)


def build_summary(runs: list[tuple[str, dict[str, Any]]], threshold_deg: float) -> dict[str, Any]:
    if not 0.0 < threshold_deg <= 180.0:
        raise ValueError("cluster threshold must be in (0,180]")
    return {
        "schemaVersion": "slot-pose-diagnostic-comparison/1",
        "candidateClusterThresholdDeg": threshold_deg,
        "roleSuggestionsAreAuthoritative": False,
        "runs": [summarize_run(label, review, threshold_deg) for label, review in runs],
        "interpretationLimits": [
            "Cross-frame stability can identify repeatable image features but cannot prove a drawing datum/target role.",
            "A stable image-frame cluster can still be a fixture, occlusion or lighting boundary.",
            "JPEG diagnostics cannot replace original-BMP angle accuracy truth.",
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="append", required=True, type=parse_run, help="LABEL=REVIEW_JSON")
    parser.add_argument("--cluster-threshold-deg", type=float, default=8.0)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        runs = [(label, json.loads(path.read_text(encoding="utf-8"))) for label, path in args.run]
        summary = build_summary(runs, args.cluster_threshold_deg)
        write_json(args.output, summary)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(f"Wrote {args.output}: runs={len(summary['runs'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
