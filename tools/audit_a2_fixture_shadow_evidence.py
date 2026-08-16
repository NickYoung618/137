#!/usr/bin/env python3
"""Audit fixed-shadow evidence without images, sealed samples, or accuracy claims."""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.audit_a2_robustness_groups import build_annotation_queue


SHA_RE = re.compile(r'"sha256"\s*:\s*"([0-9a-f]{64})"')
SHA_RE_FULL = re.compile(r"^[0-9a-f]{64}$")
QUEUE_SAMPLES = ("normal:part-015", "normal:part-019", "normal:part-021")


def _summary(values: list[float]) -> dict[str, Any]:
    if not values:
        return {"count": 0, "min": None, "median": None, "max": None}
    ordered = sorted(values)
    return {
        "count": len(ordered),
        "min": ordered[0],
        "median": statistics.median(ordered),
        "max": ordered[-1],
    }


def _finite(candidate: dict[str, Any], key: str) -> float:
    value = candidate.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise ValueError(f"candidate {key} is not finite")
    return float(value)


def _grouping_index(
    grouping_rows: list[dict[str, Any]], seal_lock: dict[str, Any],
) -> tuple[dict[str, dict[str, str]], dict[str, list[dict[str, str]]]]:
    sealed_sample = str(seal_lock.get("selectedSampleId", "")).strip()
    sealed_sha = {str(value).strip().lower() for value in seal_lock.get("selectedImageSha256s", [])}
    if not sealed_sample or not sealed_sha:
        raise ValueError("seal lock must contain selected sample and SHA-256 values")
    by_sha: dict[str, dict[str, str]] = {}
    by_sample: dict[str, list[dict[str, str]]] = defaultdict(list)
    for source in grouping_rows:
        sample = str(source.get("sample_id", "")).strip()
        dataset_class = str(source.get("dataset_class", "")).strip()
        digest = str(source.get("source_image_sha256", "")).strip().lower()
        if dataset_class != "normal" or sample == sealed_sample:
            continue
        if not SHA_RE_FULL.fullmatch(digest):
            raise ValueError("normal grouping contains invalid source SHA-256")
        if digest in sealed_sha:
            raise ValueError("sealed SHA is present in audit population; rejected before results read")
        if digest in by_sha:
            raise ValueError("duplicate normal source SHA-256 in grouping")
        row = {key: str(value) for key, value in source.items()}
        by_sha[digest] = row
        by_sample[sample].append(row)
    if not by_sha:
        raise ValueError("fixture shadow audit population is empty")
    return by_sha, dict(by_sample)


def _strict_record(candidates: list[dict[str, Any]]) -> dict[str, dict[str, Any]] | None:
    if len(candidates) != 3:
        return None
    a = [item for item in candidates if 25.0 <= _finite(item, "centerDeg") <= 40.0]
    b = [item for item in candidates if 315.0 <= _finite(item, "centerDeg") <= 340.0]
    third = [
        item for item in candidates
        if not 25.0 <= _finite(item, "centerDeg") <= 40.0
        and not 315.0 <= _finite(item, "centerDeg") <= 340.0
    ]
    if len(a) != 1 or len(b) != 1 or len(third) != 1:
        return None
    return {"fixtureA": a[0], "fixtureB": b[0], "third": third[0]}


def audit_fixture_shadow_history(
    results_path: Path,
    grouping_rows: list[dict[str, Any]],
    seal_lock: dict[str, Any],
) -> dict[str, Any]:
    by_sha, by_sample = _grouping_index(grouping_rows, seal_lock)
    target_sha = set(by_sha)
    sealed_sha = {str(value).lower() for value in seal_lock["selectedImageSha256s"]}
    counts: Counter[int] = Counter()
    strict: list[dict[str, dict[str, Any]]] = []
    sample_third_centers: dict[str, list[float]] = defaultdict(list)
    lines_scanned = parsed = sealed_parsed = 0
    seen: set[str] = set()
    with results_path.open(encoding="utf-8") as handle:
        for line in handle:
            lines_scanned += 1
            hashes = set(SHA_RE.findall(line))
            matches = hashes & target_sha
            if not matches:
                continue
            if len(matches) != 1:
                raise ValueError("historical line matches multiple target SHA-256 values")
            digest = next(iter(matches))
            if digest in sealed_sha:
                sealed_parsed += 1
                raise ValueError("sealed result would be parsed")
            if digest in seen:
                continue
            record = json.loads(line)
            parsed += 1
            actual = str((record.get("image") or {}).get("sha256", "")).lower()
            if actual != digest:
                raise ValueError("matched SHA is not record.image.sha256")
            seen.add(digest)
            diagnostics = record.get("diagnostics") if isinstance(record.get("diagnostics"), dict) else {}
            candidates = diagnostics.get("rawCandidates")
            candidates = candidates if isinstance(candidates, list) else []
            counts[len(candidates)] += 1
            evidence = _strict_record(candidates)
            if evidence is not None:
                strict.append(evidence)
                sample = by_sha[digest]["sample_id"]
                sample_third_centers[sample].append(_finite(evidence["third"], "centerDeg"))
    def feature(role: str, key: str) -> dict[str, Any]:
        return _summary([_finite(item[role], key) for item in strict])
    return {
        "schemaVersion": "a2-fixture-shadow-history-audit/1",
        "coordinateFrameId": "image-x-right-y-down-clockwise/1",
        "accuracyEvaluated": False,
        "linesScanned": lines_scanned,
        "targetImageCount": len(target_sha),
        "targetRecordsParsed": parsed,
        "sealedRecordsParsed": sealed_parsed,
        "matchedUniqueImageCount": len(seen),
        "rawCandidateCountDistribution": {
            str(key): counts[key] for key in sorted(counts)
        },
        "strictThreeCandidateEvidence": {
            "definition": {
                "candidateCount": 3,
                "fixtureAWindowDeg": [25.0, 40.0],
                "fixtureBWindowDeg": [315.0, 340.0],
                "remainingCandidateCount": 1,
            },
            "frameCount": len(strict),
            "fixtureA": {
                "centerDeg": feature("fixtureA", "centerDeg"),
                "halfWidthDeg": feature("fixtureA", "halfWidthDeg"),
                "prominence": feature("fixtureA", "prominence"),
                "deficitArea": feature("fixtureA", "deficitArea"),
            },
            "fixtureB": {
                "centerDeg": feature("fixtureB", "centerDeg"),
                "halfWidthDeg": feature("fixtureB", "halfWidthDeg"),
                "prominence": feature("fixtureB", "prominence"),
                "deficitArea": feature("fixtureB", "deficitArea"),
            },
            "thirdCandidate": {
                "centerDeg": feature("third", "centerDeg"),
                "prominence": feature("third", "prominence"),
                "deficitArea": feature("third", "deficitArea"),
            },
        },
        "sampleThirdCandidateCenterDeg": {
            sample: _summary(values) for sample, values in sorted(sample_third_centers.items())
        },
        "relaxedPairEvidence": {
            "status": "definition_missing",
            "reportedFrameCount": 365,
            "reportedPopulationWithCandidates": 413,
            "reportedRate": 365 / 413,
            "normative": False,
            "reason": "relaxed angle windows or matching definition were not supplied",
        },
        "limitations": [
            "Historical algorithm candidates are diagnostic evidence, not physical truth.",
            "No fixed angle is used as an ignore mask or production classifier.",
            "No percentage accuracy is computed.",
        ],
    }


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def _write_queue(path: Path, rows: list[dict[str, Any]]) -> None:
    flattened = [{
        **{key: value for key, value in row.items() if key != "requiredShapes"},
        "requiredShapes": ";".join(row["requiredShapes"]),
    } for row in rows]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(flattened[0]))
        writer.writeheader()
        writer.writerows(flattened)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--grouping", type=Path, required=True)
    parser.add_argument("--seal-lock", type=Path, required=True)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    grouping_rows = _read_csv(args.grouping)
    lock = json.loads(args.seal_lock.read_text(encoding="utf-8"))
    audit = audit_fixture_shadow_history(args.results, grouping_rows, lock)
    causes = [
        {"sample_id": sample, "failure_family": "fixture-shadow-overlap-review"}
        for sample in QUEUE_SAMPLES
    ]
    queue = build_annotation_queue(grouping_rows, causes, per_sample=2)
    if len(queue) != 6:
        raise ValueError("fixture shadow annotation queue requires two frames for each target sample")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "audit.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    _write_queue(args.output_dir / "annotation-queue.csv", queue)
    print(
        f"audited={audit['targetRecordsParsed']} strict={audit['strictThreeCandidateEvidence']['frameCount']} "
        f"queue={len(queue)} accuracyEvaluated=false"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
