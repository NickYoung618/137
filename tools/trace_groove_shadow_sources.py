#!/usr/bin/env python3
"""Create a read-only, SHA-joined failure ledger for groove/shadow diagnosis."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPORT_SCHEMA_VERSION = "groove-shadow-source-report/1"
NULL_SAFETY_FIELDS = (
    "currentAngleDeg", "correctionRawDeg", "correctionDeg",
    "imageFrameCorrectionDeg", "rotationDirection",
    "mechanicalCorrectionDeg", "plcCommand",
)
HUMAN_CLASSES = {
    "REAL_GROOVE_COMPLETE_NEAR_FIXTURE_SHADOW",
    "REAL_GROOVE_SHADOW_MIXED_OR_OCCLUDED",
    "INDETERMINATE",
}


def fixture_screening_counts(diagnostics: dict[str, Any]) -> dict[str, int]:
    """Return bounded candidate-source dispositions without exposing per-ray evidence."""
    screening = diagnostics.get("fixtureCandidateSourceScreening") or {}
    counts: Counter[str] = Counter()
    for item in screening.get("candidates") or []:
        if isinstance(item, dict) and isinstance(item.get("disposition"), str):
            counts[item["disposition"]] += 1
    return dict(sorted(counts.items()))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_jsonl_index(paths: list[Path]) -> dict[str, dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}
    for path in paths:
        with path.open(encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, 1):
                if not line.strip():
                    continue
                payload = json.loads(line)
                image_sha = payload.get("image", {}).get("sha256")
                if not isinstance(image_sha, str) or len(image_sha) != 64:
                    raise ValueError(f"invalid image SHA in {path}:{line_number}")
                if image_sha in output:
                    raise ValueError(f"duplicate result image SHA: {image_sha}")
                output[image_sha] = payload
    return output


def load_csv_index(path: Path, key: str) -> dict[str, dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    output: dict[str, dict[str, str]] = {}
    for row in rows:
        value = row.get(key)
        if not value or value in output:
            raise ValueError(f"missing or duplicate {key} in {path}: {value!r}")
        output[value] = row
    return output


def validate_acceptance_manifest(
    manifest: dict[str, Any], *, observed_physical_ids: set[str],
    expected_code_commit: str, expected_config_sha256: str,
) -> dict[str, Any]:
    """Validate metadata only; this function never opens a manifest image."""
    if not observed_physical_ids:
        raise ValueError("observed physical grouping is unavailable")
    if manifest.get("datasetUse") != "independent-acceptance":
        raise ValueError("acceptance manifest datasetUse must be independent-acceptance")
    if manifest.get("frozenCodeCommit") != expected_code_commit:
        raise ValueError("acceptance manifest code commit does not match frozen runtime")
    if manifest.get("frozenConfigSha256") != expected_config_sha256:
        raise ValueError("acceptance manifest config SHA does not match frozen runtime")
    for field in ("physicalGroupingAuthority", "physicalGroupingProvenance"):
        if not isinstance(manifest.get(field), str) or not manifest[field].strip():
            raise ValueError(f"acceptance manifest {field} is required")
    images = manifest.get("images")
    if not isinstance(images, list) or not images:
        raise ValueError("acceptance manifest images must be a non-empty array")
    sample_ids: set[str] = set()
    image_ids: set[str] = set()
    image_shas: set[str] = set()
    class_counts: Counter[str] = Counter()
    for index, item in enumerate(images):
        if not isinstance(item, dict):
            raise ValueError(f"acceptance image {index} must be an object")
        sample_id = item.get("sampleId")
        relative_path = item.get("relativePath")
        joined_identity = f"{sample_id}/{relative_path}".lower()
        if "part-006" in joined_identity:
            raise ValueError("acceptance manifest must not contain sealed part-006")
        if not isinstance(sample_id, str) or not sample_id:
            raise ValueError(f"acceptance image {index} sampleId is required")
        image_id = item.get("imageId")
        if not isinstance(image_id, str) or not image_id or image_id in image_ids:
            raise ValueError(f"acceptance image {index} imageId is missing or duplicate")
        if not isinstance(relative_path, str) or not relative_path:
            raise ValueError(f"acceptance image {index} relativePath is required")
        if sample_id in observed_physical_ids:
            raise ValueError(f"acceptance physical sample overlap: {sample_id}")
        image_sha = item.get("sha256")
        if (
            not isinstance(image_sha, str) or len(image_sha) != 64
            or any(character not in "0123456789abcdef" for character in image_sha)
        ):
            raise ValueError(f"acceptance image {index} sha256 is invalid")
        semantic = item.get("humanSemanticClass")
        if semantic not in HUMAN_CLASSES:
            raise ValueError(f"acceptance image {index} humanSemanticClass is required")
        if image_sha in image_shas:
            raise ValueError(f"duplicate acceptance image SHA: {image_sha}")
        sample_ids.add(sample_id)
        image_ids.add(image_id)
        image_shas.add(image_sha)
        class_counts[semantic] += 1
    return {
        "schemaVersion": "groove-shadow-independent-acceptance-preflight/1",
        "imageCount": len(images),
        "physicalSampleCount": len(sample_ids),
        "physicallySeparated": True,
        "sealedPart006Absent": True,
        "classCounts": dict(sorted(class_counts.items())),
        "frozenCodeCommit": expected_code_commit,
        "frozenConfigSha256": expected_config_sha256,
    }


def aggregate_acceptance_results(
    manifest: dict[str, Any], results: dict[str, dict[str, Any]],
    preflight: dict[str, Any],
) -> dict[str, Any]:
    dataset_id = str(manifest.get("datasetId", "independent-acceptance"))
    class_outcomes: dict[str, Counter[str]] = {
        semantic: Counter() for semantic in HUMAN_CLASSES
    }
    terminal_counts: Counter[str] = Counter()
    runtime_class_counts: Counter[str] = Counter()
    fixture_disposition_counts: Counter[str] = Counter()
    elapsed: list[float] = []
    all_invalid_safe = True
    traces = []
    for item in manifest["images"]:
        image_sha = item["sha256"]
        payload = results.get(image_sha)
        if payload is None:
            raise ValueError(f"acceptance result missing for image SHA: {image_sha}")
        if payload.get("taskId") != f"{dataset_id}:{item.get('imageId')}":
            raise ValueError(f"acceptance taskId mismatch for image SHA: {image_sha}")
        valid = payload.get("result", {}).get("valid") is True
        semantic = item["humanSemanticClass"]
        class_outcomes[semantic]["released" if valid else "rejected"] += 1
        terminal = normalize_terminal_stage(payload)
        terminal_counts[terminal] += 1
        diagnostic = (payload.get("diagnostics") or {}).get("grooveShadowSourceDiscrimination") or {}
        per_image_fixture_counts = fixture_screening_counts(payload.get("diagnostics") or {})
        fixture_disposition_counts.update(per_image_fixture_counts)
        runtime_class_counts[str(diagnostic.get("classification") or "not_evaluated")] += 1
        elapsed_value = (payload.get("diagnostics") or {}).get("elapsedMs")
        if isinstance(elapsed_value, (int, float)):
            elapsed.append(float(elapsed_value))
        result = payload.get("result") or {}
        safety_null = valid or (
            all(result.get(field) is None for field in NULL_SAFETY_FIELDS)
            and result.get("plcExecutionAuthoritative") is False
        )
        all_invalid_safe = all_invalid_safe and safety_null
        traces.append({
            "imageSha256": image_sha,
            "humanSemanticClass": semantic,
            "runtimeClassification": diagnostic.get("classification"),
            "valid": valid,
            "terminalStage": terminal,
            "errorCode": (payload.get("error") or {}).get("code"),
            "safetyOutputsNullWhenInvalid": safety_null,
            "fixtureScreeningDispositionCounts": per_image_fixture_counts,
        })
    elapsed.sort()
    p95 = None if not elapsed else elapsed[max(0, math.ceil(0.95 * len(elapsed)) - 1)]
    mixed = class_outcomes["REAL_GROOVE_SHADOW_MIXED_OR_OCCLUDED"]
    return {
        "schemaVersion": "groove-shadow-independent-acceptance-report/1",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "preflight": preflight,
        "summary": {
            "imageCount": len(traces),
            "classOutcomes": {
                key: dict(sorted(value.items())) for key, value in sorted(class_outcomes.items())
            },
            "terminalStageCounts": dict(sorted(terminal_counts.items())),
            "runtimeClassificationCounts": dict(sorted(runtime_class_counts.items())),
            "fixtureScreeningDispositionCounts": dict(sorted(fixture_disposition_counts.items())),
            "mixedOrOccludedAllFailClosed": mixed["released"] == 0,
            "allInvalidSafetyOutputsNull": all_invalid_safe,
            "elapsedMsP95": p95,
            "performanceGatePassed": p95 is not None and p95 <= 2500.0,
            "productionAccuracyClaimAllowed": False,
            "productionDefaultEnableAllowed": False,
            "plcAuthorizationAllowed": False,
        },
        "traces": traces,
    }


def normalize_terminal_stage(payload: dict[str, Any]) -> str:
    error = payload.get("error") or {}
    code = error.get("code")
    diagnostics = payload.get("diagnostics") or {}
    recognition = diagnostics.get("grooveRecognition")
    if code in {"PHYSICAL_OUTER_CIRCLE_FAILED", "HOUSING_CIRCLE_NOT_FOUND", "HOUSING_CIRCLE_AMBIGUOUS"}:
        return "upstream_outer_circle"
    if code == "GROOVE_RECOGNITION_FAILED":
        raw_count = recognition.get("rawCandidateCount") if isinstance(recognition, dict) else None
        return "candidate_generation" if raw_count == 0 else "groove_recognition"
    if code == "GROOVE_RECOGNITION_AMBIGUOUS":
        return "groove_ambiguity"
    if code == "QUALITY_REJECTED":
        return "polar_quality"
    if code == "GROOVE_REFINEMENT_FAILED":
        return "groove_refinement"
    if code == "GROOVE_SOURCE_INCONSISTENT":
        return "source_consistency"
    if payload.get("result", {}).get("valid") is True:
        return "valid"
    return "upstream_outer_circle"


def _status(value: Any) -> str:
    if not isinstance(value, dict):
        return "not_evaluated"
    status = value.get("status")
    if status == "accepted":
        return "accepted"
    if status == "failed":
        return "failed"
    return "not_evaluated"


def _candidate_evidence(diagnostics: dict[str, Any]) -> list[dict[str, Any]]:
    recognition = diagnostics.get("grooveRecognition")
    if not isinstance(recognition, dict):
        return []
    refinement = diagnostics.get("grooveRefinement")
    source = diagnostics.get("grooveSourceConsistency")
    output = []
    metric_names = (
        "grooveScore", "radialDepthPx", "radialDepthRatio", "angularWidthDeg",
        "tangentialWidthPx", "localMetalContrast", "leftEdgeContrast",
        "rightEdgeContrast", "pairedEdgeSupport", "contourContinuity",
        "widthMeanDeg", "widthCoefficientOfVariation", "centerDriftDeg",
        "centerDriftRatio", "outerConnected",
    )
    for assessment in recognition.get("assessments", [])[:16]:
        if not isinstance(assessment, dict):
            continue
        candidate_id = str(assessment.get("candidateId", "invalid"))
        matches_refinement = (
            isinstance(refinement, dict)
            and refinement.get("coarseCandidateId") == candidate_id
        )
        refinement_status = _status(refinement) if matches_refinement else "not_evaluated"
        source_value = source if matches_refinement else None
        if matches_refinement and isinstance(refinement, dict) and isinstance(refinement.get("sourceConsistency"), dict):
            source_value = refinement["sourceConsistency"]
        output.append({
            "candidateId": candidate_id,
            "source": "angular_profile+groove_recognition",
            "coarseAccepted": assessment.get("accepted") is True,
            "coarseRejectionReasons": list(assessment.get("rejectionReasons") or [])[:16],
            "coarseMetrics": {name: assessment.get(name) for name in metric_names if name in assessment},
            "physicalRefinementStatus": refinement_status,
            "physicalRefinementFailedChecks": (
                list(refinement.get("failedChecks") or [])[:32]
                if matches_refinement and isinstance(refinement, dict) else []
            ),
            "sourceConsistencyStatus": _status(source_value),
            "sourceConsistencyFailedChecks": (
                list(source_value.get("failedChecks") or [])[:32]
                if isinstance(source_value, dict) else []
            ),
        })
    return output


def _availability(candidates: list[dict[str, Any]]) -> str:
    accepted = [item for item in candidates if item["coarseAccepted"]]
    if not candidates:
        return "not_evaluated"
    if accepted and all(
        item["physicalRefinementStatus"] != "not_evaluated"
        and item["sourceConsistencyStatus"] != "not_evaluated"
        for item in accepted
    ):
        return "complete"
    return "partial"


def trace_failure(
    payload: dict[str, Any], failure_row: dict[str, str],
    overlay_row: dict[str, str] | None,
) -> dict[str, Any]:
    image_sha = payload.get("image", {}).get("sha256")
    if image_sha != failure_row.get("image_sha256"):
        raise ValueError(f"failure/result SHA mismatch: {failure_row.get('image_sha256')}")
    error = payload.get("error") or {}
    if error.get("code") != failure_row.get("failure_code"):
        raise ValueError(f"failure/result error mismatch for {image_sha}")
    if error.get("stage") != failure_row.get("failure_stage"):
        raise ValueError(f"failure/result stage mismatch for {image_sha}")
    diagnostics = payload.get("diagnostics") or {}
    candidates = _candidate_evidence(diagnostics)
    result = payload.get("result") or {}
    safety_null = (
        result.get("valid") is False
        and all(result.get(field) is None for field in NULL_SAFETY_FIELDS)
        and result.get("plcExecutionAuthoritative") is False
    )
    quality = diagnostics.get("quality") or {}
    thresholds = quality.get("thresholds") or {}
    return {
        "imageSha256": image_sha,
        "taskId": payload.get("taskId"),
        "sourceCohort": "observed-diagnostic",
        "sourceClass": failure_row.get("source_class"),
        "sourceRelativePath": failure_row.get("source_relative_path"),
        "originalErrorCode": error.get("code"),
        "originalStage": error.get("stage"),
        "terminalStage": normalize_terminal_stage(payload),
        "candidateCounts": {
            "generated": (diagnostics.get("grooveRecognition") or {}).get("rawCandidateCount"),
            "recognized": (diagnostics.get("grooveRecognition") or {}).get("acceptedCount"),
            "refined": sum(item["physicalRefinementStatus"] == "accepted" for item in candidates),
            "sourceAccepted": sum(item["sourceConsistencyStatus"] == "accepted" for item in candidates),
        },
        "candidateEvidenceAvailability": _availability(candidates),
        "candidateEvidence": candidates,
        "polarQuality": {
            "score": quality.get("polarScore"),
            "lockedMinimum": thresholds.get("min_polar_score"),
            "failedChecks": list(quality.get("failedChecks") or []),
        },
        "physicalOuterCircleStatus": (diagnostics.get("physicalOuterCircle") or {}).get("status", "not_evaluated"),
        "humanSemanticClass": None,
        "humanSemanticStatus": "not_labeled",
        "runtimeDisposition": diagnostics.get("grooveShadowSourceDiscrimination"),
        "fixtureScreeningDispositionCounts": fixture_screening_counts(diagnostics),
        "safetyOutputsNull": safety_null,
        "overlayStatus": "indexed_existing" if overlay_row else "unavailable",
        "overlayRelativePath": overlay_row.get("overlay") if overlay_row else None,
    }


def build_report(evidence_dir: Path, results_dir: Path) -> dict[str, Any]:
    failure_path = evidence_dir / "failure-index.csv"
    overlay_path = evidence_dir / "overlay-index.csv"
    result_paths = [results_dir / "normal-results.jsonl", results_dir / "bad-results.jsonl"]
    failures = load_csv_index(failure_path, "image_sha256")
    overlays = load_csv_index(overlay_path, "source_sha256")
    results = load_jsonl_index(result_paths)
    missing = sorted(set(failures) - set(results))
    if missing:
        raise ValueError(f"failure rows missing from result JSONL: {len(missing)}")
    traces = [trace_failure(results[sha], failures[sha], overlays.get(sha)) for sha in sorted(failures)]
    if len(traces) != 207:
        raise ValueError(f"expected 207 frozen failure rows, found {len(traces)}")
    terminal_counts = Counter(item["terminalStage"] for item in traces)
    error_counts = Counter(item["originalErrorCode"] for item in traces)
    availability_counts = Counter(item["candidateEvidenceAvailability"] for item in traces)
    fixture_disposition_counts: Counter[str] = Counter()
    for item in traces:
        fixture_disposition_counts.update(item["fixtureScreeningDispositionCounts"])
    if not all(item["safetyOutputsNull"] for item in traces):
        raise ValueError("one or more frozen invalid results violate fail-closed null outputs")
    branch = subprocess.run(
        ["git", "branch", "--show-current"], check=True, text=True, capture_output=True,
    ).stdout.strip()
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], check=True, text=True, capture_output=True,
    ).stdout.strip()
    return {
        "schemaVersion": REPORT_SCHEMA_VERSION,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "code": {"branch": branch, "commit": commit},
        "inputs": {
            "failureIndexSha256": sha256_file(failure_path),
            "overlayIndexSha256": sha256_file(overlay_path),
            "resultJsonlSha256": {path.name: sha256_file(path) for path in result_paths},
        },
        "dataUse": "observed-diagnostic-not-unseen-acceptance",
        "summary": {
            "traceCount": len(traces),
            "uniqueImageShaCount": len({item["imageSha256"] for item in traces}),
            "terminalStageCounts": dict(sorted(terminal_counts.items())),
            "originalErrorCounts": dict(sorted(error_counts.items())),
            "candidateEvidenceAvailabilityCounts": dict(sorted(availability_counts.items())),
            "fixtureScreeningDispositionCounts": dict(sorted(fixture_disposition_counts.items())),
            "allInvalidSafetyOutputsNull": True,
            "humanSemanticLabeledCount": 0,
            "completeNearShadowSafeReleaseCount": None,
            "completeNearShadowContinuedRejectionCount": None,
            "mixedOrOccludedRejectedCount": None,
        },
        "traces": traces,
        "independentAcceptance": {
            "status": "INDEPENDENT_ACCEPTANCE_BLOCKED",
            "reason": "new physically separate part manifest and frozen human labels not supplied",
            "productionAccuracyClaimAllowed": False,
            "productionDefaultEnableAllowed": False,
            "plcAuthorizationAllowed": False,
        },
    }


def write_report(report: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=False)
    report_path = output_dir / "groove-shadow-source-report.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    fields = (
        "imageSha256", "taskId", "sourceClass", "originalErrorCode",
        "originalStage", "terminalStage", "candidateEvidenceAvailability",
        "humanSemanticStatus", "safetyOutputsNull", "overlayStatus",
    )
    with (output_dir / "failure-traces.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows({field: item.get(field) for field in fields} for item in report["traces"])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", type=Path)
    parser.add_argument("--results-dir", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--acceptance-manifest", type=Path)
    parser.add_argument("--acceptance-results", type=Path)
    parser.add_argument("--observed-physical-ids", type=Path)
    parser.add_argument("--expected-code-commit")
    parser.add_argument("--expected-config-sha256")
    args = parser.parse_args()
    if args.acceptance_manifest is not None:
        required = {
            "--acceptance-results": args.acceptance_results,
            "--observed-physical-ids": args.observed_physical_ids,
            "--expected-code-commit": args.expected_code_commit,
            "--expected-config-sha256": args.expected_config_sha256,
        }
        missing = [name for name, value in required.items() if value is None]
        if missing:
            parser.error(f"acceptance mode requires: {', '.join(missing)}")
        manifest = json.loads(args.acceptance_manifest.read_text(encoding="utf-8"))
        observed_ids = {
            line.strip() for line in args.observed_physical_ids.read_text(encoding="utf-8").splitlines()
            if line.strip()
        }
        preflight = validate_acceptance_manifest(
            manifest, observed_physical_ids=observed_ids,
            expected_code_commit=str(args.expected_code_commit),
            expected_config_sha256=str(args.expected_config_sha256),
        )
        results = load_jsonl_index([args.acceptance_results.resolve()])
        report = aggregate_acceptance_results(manifest, results, preflight)
        args.output_dir.mkdir(parents=True, exist_ok=False)
        (args.output_dir / "independent-acceptance-report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
        return 0
    if args.evidence_dir is None or args.results_dir is None:
        parser.error("observed mode requires --evidence-dir and --results-dir")
    report = build_report(args.evidence_dir.resolve(), args.results_dir.resolve())
    write_report(report, args.output_dir.resolve())
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
