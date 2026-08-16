#!/usr/bin/env python3
"""Stream a selected historical replay without parsing sealed or unrelated records."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import statistics
import time
from collections import Counter, defaultdict
from pathlib import Path, PurePosixPath
from typing import Any, Sequence


SHA_RE = re.compile(r'"sha256"\s*:\s*"([0-9a-f]{64})"')
SHA256_VALUE_RE = re.compile(r"^[0-9a-f]{64}$")
REQUIRED_SHAPES = [
    "outer_circle_visible_arc",
    "real_groove_boundary",
    "groove_sidewalls",
    "groove_mouth_endpoints",
    "fixture_shadow_a_region",
    "fixture_shadow_b_region",
]


def _target_samples(plan: dict[str, Any]) -> set[str]:
    return {
        str(sample)
        for family in plan.get("families", [])
        for sample in family.get("sampleIds", [])
    }


def _root_causes(plan: dict[str, Any]) -> dict[str, str]:
    return {
        str(sample): str(family.get("failureFamily", ""))
        for family in plan.get("families", [])
        for sample in family.get("sampleIds", [])
    }


def _grouping_index(
    grouping_rows: list[dict[str, Any]], plan: dict[str, Any], seal_lock: dict[str, Any],
) -> tuple[dict[str, dict[str, str]], dict[str, list[dict[str, str]]]]:
    targets = _target_samples(plan)
    sealed_sample = str(seal_lock.get("selectedSampleId", ""))
    sealed_sha = {str(value).lower() for value in seal_lock.get("selectedImageSha256s", [])}
    if sealed_sample in targets:
        raise ValueError("sealed sample is present in audit plan; rejected before results read")
    by_sha: dict[str, dict[str, str]] = {}
    by_sample: dict[str, list[dict[str, str]]] = defaultdict(list)
    for source in grouping_rows:
        sample = str(source.get("sample_id", "")).strip()
        if sample not in targets:
            continue
        relative = str(source.get("relative_path", "")).strip()
        path = PurePosixPath(relative)
        if not relative or path.is_absolute() or ".." in path.parts:
            raise ValueError(f"unsafe relative path in grouping: {relative!r}")
        digest = str(source.get("source_image_sha256", "")).strip().lower()
        if digest in sealed_sha:
            raise ValueError("sealed SHA is present in audit population; rejected before results read")
        if digest in by_sha:
            raise ValueError(f"duplicate target SHA in grouping: {digest}")
        row = {key: str(value) for key, value in source.items()}
        by_sha[digest] = row
        by_sample[sample].append(row)
    missing = sorted(targets - set(by_sample))
    if missing:
        raise ValueError(f"audit plan samples missing from grouping: {missing}")
    return by_sha, dict(by_sample)


def _finite(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    converted = float(value)
    return converted if math.isfinite(converted) else None


def _numeric_summary(values: list[float]) -> dict[str, Any]:
    if not values:
        return {"count": 0, "min": None, "median": None, "p95": None, "max": None}
    ordered = sorted(values)
    rank = max(0, math.ceil(0.95 * len(ordered)) - 1)
    return {
        "count": len(ordered),
        "min": ordered[0],
        "median": statistics.median(ordered),
        "p95": ordered[rank],
        "max": ordered[-1],
    }


def _update_group(state: dict[str, Any], record: dict[str, Any]) -> None:
    state["recordCount"] += 1
    result = record.get("result") if isinstance(record.get("result"), dict) else {}
    error = record.get("error") if isinstance(record.get("error"), dict) else {}
    diagnostics = record.get("diagnostics") if isinstance(record.get("diagnostics"), dict) else {}
    code = str(error.get("code") or "NONE")
    state["errorCodeCounts"][code] += 1
    state["stageFunnel"]["records"] += 1
    if result.get("valid") is True:
        state["stageFunnel"]["detected"] += 1
    if code in {"HOUSING_CIRCLE_NOT_FOUND", "HOUSING_CIRCLE_AMBIGUOUS"}:
        state["stageFunnel"]["circleLocalizationFailed"] += 1
    if code == "PHYSICAL_OUTER_CIRCLE_FAILED":
        state["stageFunnel"]["physicalCircleFailed"] += 1
    if code == "GROOVE_RECOGNITION_FAILED":
        state["stageFunnel"]["grooveRecognitionFailed"] += 1
    if code == "GROOVE_RECOGNITION_AMBIGUOUS":
        state["stageFunnel"]["grooveRecognitionAmbiguous"] += 1
    if code == "GROOVE_REFINEMENT_FAILED":
        state["stageFunnel"]["grooveRefinementFailed"] += 1

    summary = diagnostics.get("candidateSummary") if isinstance(diagnostics.get("candidateSummary"), dict) else {}
    raw_count = summary.get("count")
    if isinstance(raw_count, int) and not isinstance(raw_count, bool):
        state["rawCandidateCounts"].append(float(raw_count))
        if raw_count == 0:
            state["stageFunnel"]["rawCandidateZero"] += 1
    recognition = diagnostics.get("grooveRecognition") if isinstance(diagnostics.get("grooveRecognition"), dict) else {}
    accepted_count = recognition.get("acceptedCount")
    if isinstance(accepted_count, int) and not isinstance(accepted_count, bool):
        state["acceptedGrooveCounts"].append(float(accepted_count))
    for assessment in recognition.get("assessments", []):
        if isinstance(assessment, dict) and not assessment.get("accepted", False):
            state["grooveRejectionReasons"].update(
                str(value) for value in assessment.get("rejectionReasons", [])
            )

    physical = diagnostics.get("physicalOuterCircle")
    if not isinstance(physical, dict):
        localization = diagnostics.get("circleLocalization")
        if isinstance(localization, dict):
            physical = localization.get("finalPhysicalCircleDiagnostics")
    if isinstance(physical, dict):
        for key, bucket in (("residualP95Px", "circleResidualP95Px"), ("residualMarginPx", "circleResidualMarginPx")):
            value = _finite(physical.get(key))
            if value is not None:
                state[bucket].append(value)


def audit_results(
    results_path: Path,
    plan: dict[str, Any],
    grouping_rows: list[dict[str, Any]],
    seal_lock: dict[str, Any],
) -> dict[str, Any]:
    """Scan every line, but JSON-decode only target and nonsealed image SHA lines."""
    started = time.perf_counter_ns()
    by_sha, by_sample = _grouping_index(grouping_rows, plan, seal_lock)
    target_sha = set(by_sha)
    sealed_sha = {str(value).lower() for value in seal_lock.get("selectedImageSha256s", [])}
    causes = _root_causes(plan)
    states: dict[str, dict[str, Any]] = {}
    for sample, rows in by_sample.items():
        states[sample] = {
            "sampleId": sample,
            "failureFamily": causes[sample],
            "expectedImageCount": len(rows),
            "recordCount": 0,
            "errorCodeCounts": Counter(),
            "stageFunnel": Counter(),
            "rawCandidateCounts": [],
            "acceptedGrooveCounts": [],
            "circleResidualP95Px": [],
            "circleResidualMarginPx": [],
            "grooveRejectionReasons": Counter(),
        }
    lines_scanned = 0
    parsed = 0
    sealed_parsed = 0
    duplicate_target_records = 0
    seen: set[str] = set()
    with results_path.open(encoding="utf-8") as handle:
        for line in handle:
            lines_scanned += 1
            hashes = set(SHA_RE.findall(line))
            matches = hashes & target_sha
            if not matches:
                continue
            if len(matches) != 1:
                raise ValueError("historical JSONL line matches more than one target SHA")
            digest = next(iter(matches))
            if digest in sealed_sha:
                sealed_parsed += 1
                raise ValueError("sealed result would be parsed")
            record = json.loads(line)
            parsed += 1
            actual = str((record.get("image") or {}).get("sha256", "")).lower()
            if actual != digest:
                raise ValueError("target SHA match did not belong to record.image.sha256")
            if digest in seen:
                duplicate_target_records += 1
                continue
            seen.add(digest)
            _update_group(states[by_sha[digest]["sample_id"]], record)
    groups = []
    for sample in sorted(states):
        state = states[sample]
        groups.append({
            "sampleId": sample,
            "failureFamily": state["failureFamily"],
            "expectedImageCount": state["expectedImageCount"],
            "recordCount": state["recordCount"],
            "missingRecordCount": state["expectedImageCount"] - state["recordCount"],
            "errorCodeCounts": dict(sorted(state["errorCodeCounts"].items())),
            "stageFunnel": dict(sorted(state["stageFunnel"].items())),
            "rawCandidateCount": _numeric_summary(state["rawCandidateCounts"]),
            "acceptedGrooveCount": _numeric_summary(state["acceptedGrooveCounts"]),
            "circleResidualP95Px": _numeric_summary(state["circleResidualP95Px"]),
            "circleResidualMarginPx": _numeric_summary(state["circleResidualMarginPx"]),
            "grooveRejectionReasonCounts": dict(sorted(state["grooveRejectionReasons"].items())),
        })
    return {
        "schemaVersion": "a2-robustness-audit/1",
        "methodVersion": "target-sha-stream-audit/1",
        "accuracyEvaluated": False,
        "linesScanned": lines_scanned,
        "targetRecordsParsed": parsed,
        "sealedRecordsParsed": sealed_parsed,
        "duplicateTargetRecordCount": duplicate_target_records,
        "targetImageCount": len(target_sha),
        "matchedUniqueImageCount": len(seen),
        "elapsedMs": (time.perf_counter_ns() - started) / 1e6,
        "groups": groups,
        "limitations": [
            "Historical outputs are diagnostic evidence and are not geometric truth.",
            "No percentage accuracy is computed.",
        ],
    }


def build_annotation_queue(
    grouping_rows: list[dict[str, Any]],
    root_cause_rows: list[dict[str, Any]],
    *,
    per_sample: int = 2,
) -> list[dict[str, Any]]:
    if isinstance(per_sample, bool) or not isinstance(per_sample, int) or not 1 <= per_sample <= 5:
        raise ValueError("per_sample must be in [1,5]")
    causes: dict[str, str] = {}
    for row in root_cause_rows:
        sample = str(row.get("sample_id", "")).strip()
        family = str(row.get("failure_family", "")).strip()
        if not sample or not family or sample in causes:
            raise ValueError("annotation queue root-cause samples must be unique and non-empty")
        causes[sample] = family
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in grouping_rows:
        sample = str(row.get("sample_id", ""))
        if sample in causes:
            relative = str(row.get("relative_path", "")).strip()
            path = PurePosixPath(relative)
            digest = str(row.get("source_image_sha256", "")).strip().lower()
            if not relative or path.is_absolute() or ".." in path.parts:
                raise ValueError(f"unsafe annotation queue relative path: {relative!r}")
            if not SHA256_VALUE_RE.fullmatch(digest):
                raise ValueError(f"invalid annotation queue source SHA-256: {relative}")
            grouped[sample].append(row)
    output: list[dict[str, Any]] = []
    for sample in sorted(causes):
        ranked = sorted(
            grouped.get(sample, []),
            key=lambda row: (
                hashlib.sha256(
                    f"{sample}|{row.get('source_image_sha256', '')}".encode("utf-8")
                ).hexdigest(),
                str(row.get("relative_path", "")),
            ),
        )
        for rank, row in enumerate(ranked[:per_sample], start=1):
            output.append({
                "relativePath": str(row.get("relative_path", "")),
                "sourceImageSha256": str(row.get("source_image_sha256", "")),
                "sampleId": sample,
                "conditionId": str(row.get("condition_id", "")),
                "failureFamily": causes[sample],
                "selectionRule": "sha256(sample_id|source_image_sha256)/1",
                "selectionRank": rank,
                "requiredShapes": list(REQUIRED_SHAPES),
                "humanVerified": False,
            })
    return output


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--grouping", type=Path, required=True)
    parser.add_argument("--root-causes", type=Path, required=True)
    parser.add_argument("--seal-lock", type=Path, required=True)
    parser.add_argument("--fold-plan", type=Path, required=True)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--annotation-per-sample", type=int, default=2)
    args = parser.parse_args(argv)
    grouping = _read_csv(args.grouping)
    causes = _read_csv(args.root_causes)
    plan = json.loads(args.fold_plan.read_text(encoding="utf-8"))
    lock = json.loads(args.seal_lock.read_text(encoding="utf-8"))
    audit = audit_results(args.results, plan, grouping, lock)
    queue = build_annotation_queue(grouping, causes, per_sample=args.annotation_per_sample)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "audit.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
    )
    flat_groups = [{
        "sample_id": item["sampleId"],
        "failure_family": item["failureFamily"],
        "expected_image_count": item["expectedImageCount"],
        "record_count": item["recordCount"],
        "missing_record_count": item["missingRecordCount"],
        "error_code_counts_json": json.dumps(item["errorCodeCounts"], sort_keys=True),
        "stage_funnel_json": json.dumps(item["stageFunnel"], sort_keys=True),
    } for item in audit["groups"]]
    _write_csv(args.output_dir / "groups.csv", flat_groups)
    _write_csv(args.output_dir / "annotation-queue.csv", [{
        **{key: value for key, value in item.items() if key != "requiredShapes"},
        "requiredShapes": ";".join(item["requiredShapes"]),
    } for item in queue])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
