#!/usr/bin/env python3
"""Audit existing slot-pose JSONL and Manifest without reading or rerunning images."""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from algorithms.slot_pose.contract import validate_result
from tools.dataset_common import sha256_file, write_json


def _counts(values: list[Any]) -> dict[str, int]:
    return dict(sorted(Counter("not_available" if value is None else str(value) for value in values).items()))


def _circular_range(values: list[float]) -> float:
    radians = [math.radians(value) for value in values]
    center = math.degrees(math.atan2(sum(math.sin(value) for value in radians), sum(math.cos(value) for value in radians)))
    unwrapped = [center + (value - center + 180.0) % 360.0 - 180.0 for value in values]
    return max(unwrapped) - min(unwrapped)


def _percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    low, high = math.floor(position), math.ceil(position)
    return ordered[low] if low == high else ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def audit_replay(manifest: dict[str, Any], results: list[dict[str, Any]]) -> dict[str, Any]:
    started = time.perf_counter()
    images = list(manifest.get("images") or [])
    by_hash = {str(item.get("sha256")): item for item in images}
    consistency_errors: list[dict[str, str]] = []
    if len(by_hash) != len(images):
        consistency_errors.append({"code": "MANIFEST_DUPLICATE_HASH", "message": "image hashes are not unique"})
    matched: list[tuple[dict[str, Any], dict[str, Any]]] = []
    seen: set[str] = set()
    for payload in results:
        digest = str((payload.get("image") or {}).get("sha256", ""))
        item = by_hash.get(digest)
        if item is None:
            consistency_errors.append({"code": "RESULT_UNKNOWN_IMAGE", "message": digest})
            continue
        if digest in seen:
            consistency_errors.append({"code": "RESULT_DUPLICATE_IMAGE", "message": digest})
            continue
        seen.add(digest)
        try:
            validate_result(payload)
        except (ValueError, KeyError, TypeError) as exc:
            consistency_errors.append({"code": "FINAL_RESULT_INCONSISTENT", "message": f"{item.get('imageId')}: {exc}"})
        matched.append((item, payload))
    missing = sorted(set(by_hash) - seen)
    if missing:
        consistency_errors.append({"code": "RESULTS_MISSING", "message": f"missing={len(missing)}"})
    if len(results) != len(images):
        consistency_errors.append({"code": "COUNT_MISMATCH", "message": f"manifest={len(images)} results={len(results)}"})

    finals = [payload.get("result") or {} for _, payload in matched]
    errors = [(payload.get("error") or {}).get("code") or "NONE" for _, payload in matched]
    dataset_classes = [item.get("datasetClass", "normal") for item, _ in matched]
    purposes = [item.get("split", "unassigned") for item, _ in matched]
    intermediate = [((payload.get("diagnostics") or {}).get("singleGroovePose") or {}).get("guidance") or {} for _, payload in matched]
    diagnostics = [payload.get("diagnostics") or {} for _, payload in matched]
    elapsed = [
        float(value) for _, payload in matched
        if isinstance((value := (payload.get("diagnostics") or {}).get("elapsedMs")), (int, float))
    ]

    pose_labeled = [(item, payload) for item, payload in matched if item.get("poseUsable") in {True, False}]
    pose_unusable = [(item, payload) for item, payload in pose_labeled if item.get("poseUsable") is False]
    pose_false_positive = sum(payload.get("result", {}).get("valid") is True for _, payload in pose_unusable)
    pose_unknown = len(matched) - len(pose_labeled)
    if not pose_labeled:
        pose_metric_status = "BLOCKED"
    elif pose_unknown:
        pose_metric_status = "PARTIAL"
    else:
        pose_metric_status = "AUTHORITATIVE"

    explicit_grouping = manifest.get("policy", {}).get("groupingExplicit") is True
    repeatability_groups: list[dict[str, Any]] = []
    if explicit_grouping:
        grouped: dict[tuple[str, str], list[float]] = defaultdict(list)
        for item, payload in matched:
            angle = payload.get("result", {}).get("currentAngleDeg")
            if payload.get("result", {}).get("valid") is True and isinstance(angle, (int, float)):
                grouped[(str(item.get("sampleId")), str(item.get("conditionId") or item.get("position")))].append(float(angle))
        for (sample, condition), angles in sorted(grouped.items()):
            if len(angles) >= 2:
                repeatability_groups.append({
                    "sampleId": sample, "conditionId": condition, "count": len(angles),
                    "circularRangeDeg": _circular_range(angles),
                })
    repeatability = {
        "status": "EVALUATED" if repeatability_groups else "NOT_EVALUATED",
        "reason": None if repeatability_groups else "EXPLICIT_PHYSICAL_SAMPLE_AND_CONDITION_GROUPS_REQUIRED",
        "groups": repeatability_groups,
    }

    queue_counts = Counter()
    for code in errors:
        if code in {"HOUSING_CIRCLE_NOT_FOUND", "PHYSICAL_OUTER_CIRCLE_FAILED"}:
            queue_counts["circle_truth"] += 1
        elif code in {"GROOVE_RECOGNITION_FAILED", "GROOVE_RECOGNITION_AMBIGUOUS"}:
            queue_counts["groove_shadow_role_truth"] += 1
        elif code == "GROOVE_REFINEMENT_FAILED":
            queue_counts["sidewall_endpoint_truth"] += 1
    if pose_unknown:
        queue_counts["bad_reason_and_pose_usability"] = pose_unknown

    purpose_counts = _counts(purposes)
    stage_funnel = {
        "circleLocalizationDiagnosticAvailable": sum(bool(item.get("circleLocalization")) for item in diagnostics),
        "circleLocalizationAccepted": sum((item.get("circleLocalization") or {}).get("status") == "accepted" for item in diagnostics),
        "physicalOuterCircleAccepted": sum((item.get("physicalOuterCircle") or {}).get("status") == "accepted" for item in diagnostics),
        "rawCandidateExtractionAvailable": sum(item.get("rawCandidates") is not None for item in diagnostics),
        "grooveRecognitionAccepted": sum((item.get("grooveRecognition") or {}).get("status") == "accepted" for item in diagnostics),
        "grooveRecognitionAmbiguous": sum((item.get("grooveRecognition") or {}).get("status") == "ambiguous" for item in diagnostics),
        "grooveRecognitionFailed": sum((item.get("grooveRecognition") or {}).get("status") == "failed" for item in diagnostics),
        "grooveRefinementAccepted": sum((item.get("grooveRefinement") or {}).get("status") == "accepted" for item in diagnostics),
        "grooveRefinementFailed": sum((item.get("grooveRefinement") or {}).get("status") == "failed" for item in diagnostics),
        "topLevelQualityRejected": errors.count("QUALITY_REJECTED"),
        "finalDetected": sum(item.get("valid") is True for item in finals),
    }
    by_dataset_class: dict[str, Any] = {}
    for dataset_class in sorted(set(map(str, dataset_classes))):
        indices = [index for index, value in enumerate(dataset_classes) if str(value) == dataset_class]
        by_dataset_class[dataset_class] = {
            "imageCount": len(indices),
            "validCount": sum(finals[index].get("valid") is True for index in indices),
            "errorCodeCounts": _counts([errors[index] for index in indices]),
        }
    manifest_findings = []
    if purpose_counts.get("unassigned", 0):
        manifest_findings.append({
            "code": "EVALUATION_PURPOSE_UNASSIGNED", "count": purpose_counts["unassigned"],
            "impact": "records cannot be claimed as independent development/validation/test/acceptance metrics",
        })
    if manifest.get("policy", {}).get("semanticsExplicit") is not True:
        manifest_findings.append({
            "code": "DATASET_SEMANTICS_NOT_EXPLICIT", "count": len(images),
            "impact": "directory class is not authoritative pose usability",
        })
    independent_truth = {
        purpose: {
            "imageCount": purpose_counts.get(purpose, 0),
            "reviewedTruthCount": 0,
            "independentTruthStatus": "NOT_AVAILABLE",
        }
        for purpose in ("development", "validation", "test", "acceptance")
    }
    return {
        "schemaVersion": "slot-pose-replay-audit/1",
        "status": "FAILED" if consistency_errors else "PASSED",
        "datasetId": manifest.get("datasetId"),
        "manifestImageCount": len(images),
        "resultCount": len(results),
        "matchedCount": len(matched),
        "finalOutcome": {
            "validCounts": _counts([str(bool(item.get("valid"))).lower() for item in finals]),
            "detectionStatusCounts": _counts([item.get("detectionStatus") for item in finals]),
            "guidanceStatusCounts": _counts([item.get("guidanceStatus") for item in finals]),
            "rotationDirectionCounts": _counts([item.get("rotationDirection") for item in finals]),
            "errorCodeCounts": _counts(errors),
        },
        "intermediateOutcome": {
            "authoritative": False,
            "detectionStatusCounts": _counts([item.get("detectionStatus") for item in intermediate]),
            "guidanceStatusCounts": _counts([item.get("guidanceStatus") for item in intermediate]),
        },
        "datasetClassCounts": _counts(dataset_classes),
        "byDatasetClass": by_dataset_class,
        "stageFunnel": stage_funnel,
        "manifestFindings": manifest_findings,
        "evaluationPurposeCounts": purpose_counts,
        "independentTruthByPurpose": independent_truth,
        "poseUsabilityMetric": {
            "status": pose_metric_status, "labeledCount": len(pose_labeled), "unknownCount": pose_unknown,
            "poseUnusableCount": len(pose_unusable), "falsePositiveCount": pose_false_positive,
            "falsePositiveRate": pose_false_positive / len(pose_unusable) if pose_unusable else None,
            "blocker": None if pose_metric_status == "AUTHORITATIVE" else "POSE_USABILITY_LABELS_INCOMPLETE",
        },
        "repeatability": repeatability,
        "annotationQueue": [
            {"annotationType": key, "sampleCount": value} for key, value in sorted(queue_counts.items())
        ],
        "algorithmElapsedMs": {
            "n": len(elapsed), "p50": statistics.median(elapsed) if elapsed else None,
            "p95": _percentile(elapsed, 0.95), "max": max(elapsed) if elapsed else None,
        },
        "thresholdAnalysis": {
            "status": "OBSERVED_ONLY", "replacementThreshold": None,
            "reason": "locked acceptance replay cannot be used to select production thresholds",
        },
        "consistencyErrors": consistency_errors,
        "auditWallMs": (time.perf_counter() - started) * 1000.0,
        "thresholdChangesApplied": False,
        "imagesRead": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        results = [json.loads(line) for line in args.results.read_text(encoding="utf-8").splitlines() if line.strip()]
        report = audit_replay(manifest, results)
        report["inputs"] = {
            "manifestSha256": sha256_file(args.manifest), "resultsSha256": sha256_file(args.results),
        }
        write_json(args.output, report)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(f"{report['status']}: matched={report['matchedCount']} output={args.output}")
    return 0 if report["status"] == "PASSED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
