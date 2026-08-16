#!/usr/bin/env python3
"""Build a truth-free, sample-first queue for complete-groove human review."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.dataset_common import safe_relative_path, sha256_file
from tools.render_slot_pose_review import load_results


SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
REQUIRED_HUMAN_SHAPES = (
    "HUMAN_true_groove_open_boundary",
    "HUMAN_groove_mouth_endpoint_1",
    "HUMAN_groove_mouth_endpoint_2",
)
REVIEW_QUESTIONS = (
    "are_both_detected_walls_from_the_same_real_square_groove",
    "are_both_mouth_endpoints_on_the_visible_outer_circle_shoulders",
    "is_the_complete_real_groove_unoccluded_and_visible",
    "does_any_selected_wall_belong_to_fixture_shadow_or_occlusion",
)


def _require_external(path: Path) -> None:
    try:
        path.resolve().relative_to(PROJECT_ROOT.resolve())
    except ValueError:
        return
    raise ValueError("review queue output must be outside the Git worktree")


def _image_sha(item: dict[str, Any]) -> str:
    source = str(item.get("sourceImageSha256") or "").strip().lower()
    generic = str(item.get("sha256") or "").strip().lower()
    if source and generic and source != generic:
        raise ValueError("manifest sourceImageSha256 and sha256 disagree")
    digest = source or generic
    if not SHA256_RE.fullmatch(digest):
        raise ValueError("manifest image SHA-256 is invalid")
    return digest


def _wall_points_available(side: Any) -> bool:
    if not isinstance(side, dict):
        return False
    points = side.get("points")
    if not isinstance(points, list) or len(points) < 2:
        return False
    return all(
        isinstance(point, (list, tuple)) and len(point) >= 2
        and all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in point[:2])
        for point in points
    )


def _evidence_stage(payload: dict[str, Any]) -> tuple[str, bool]:
    result = payload.get("result") if isinstance(payload.get("result"), dict) else {}
    if result.get("valid") is True:
        return "VALID_COMPLETE_POSE_CANDIDATE", True
    diagnostics = payload.get("diagnostics") if isinstance(payload.get("diagnostics"), dict) else {}
    refinement = diagnostics.get("grooveRefinement")
    if isinstance(refinement, dict) and all(
        _wall_points_available(refinement.get(key)) for key in ("startSide", "endSide")
    ):
        return "TWO_WALL_REFINEMENT_CANDIDATE", True
    local = diagnostics.get("localSecondWallDiagnostic")
    clusters = local.get("sideSearchMergeClusters") if isinstance(local, dict) else None
    if isinstance(clusters, list) and len(clusters) >= 2:
        return "TWO_WALL_CLUSTER_CANDIDATE", True
    error = payload.get("error") if isinstance(payload.get("error"), dict) else {}
    return str(error.get("code") or "NO_COMPLETE_WALL_EVIDENCE"), False


def _validate_limits(max_samples: int, frames_per_sample: int) -> None:
    for name, value, maximum in (
        ("max_samples", max_samples, 20), ("frames_per_sample", frames_per_sample, 5),
    ):
        if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= maximum:
            raise ValueError(f"{name} must be an integer in [1,{maximum}]")


def build_complete_groove_review_queue(
    manifests: list[dict[str, Any]],
    results: list[dict[str, Any]],
    *,
    exclusions: dict[str, str],
    max_samples: int,
    frames_per_sample: int,
    source_manifest_sha256s: list[str] | None = None,
    source_result_sha256s: list[str] | None = None,
) -> dict[str, Any]:
    _validate_limits(max_samples, frames_per_sample)
    if not manifests:
        raise ValueError("at least one manifest is required")
    for sample, reason in exclusions.items():
        if not str(sample).strip() or not str(reason).strip():
            raise ValueError("excluded sample and reason must be non-empty")
    manifest_hashes = list(source_manifest_sha256s or [])
    result_hashes = list(source_result_sha256s or [])
    if any(not SHA256_RE.fullmatch(str(value)) for value in manifest_hashes + result_hashes):
        raise ValueError("source manifest/result SHA-256 is invalid")

    dataset_ids: list[str] = []
    images_by_sha: dict[str, dict[str, Any]] = {}
    images_by_sample: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for manifest in manifests:
        dataset_id = str(manifest.get("datasetId") or "").strip()
        if not dataset_id:
            raise ValueError("manifest datasetId is required")
        dataset_ids.append(dataset_id)
        images = manifest.get("images")
        if not isinstance(images, list):
            raise ValueError("manifest images must be an array")
        for source in images:
            if not isinstance(source, dict):
                raise ValueError("manifest image must be an object")
            relative = safe_relative_path(str(source.get("relativePath") or ""))
            if not relative.parts or relative.parts[0] != "A2":
                raise ValueError(f"unsafe/non-canonical A2 relative path: {relative.as_posix()!r}")
            sample = str(source.get("sampleId") or "").strip()
            image_id = str(source.get("imageId") or "").strip()
            if not sample or not image_id:
                raise ValueError("manifest image sampleId/imageId is required")
            digest = _image_sha(source)
            if digest in images_by_sha:
                raise ValueError(f"duplicate manifest image SHA-256: {digest}")
            normalized = {
                "imageId": image_id,
                "relativePath": relative.as_posix(),
                "sampleId": sample,
                "conditionId": str(source.get("conditionId") or ""),
                "repeatIndex": source.get("repeatIndex"),
                "sourceImageSha256": digest,
                "bytes": source.get("bytes"),
                "format": source.get("format"),
                "width": source.get("width"),
                "height": source.get("height"),
                "mode": source.get("mode"),
            }
            if (
                isinstance(normalized["bytes"], bool)
                or not isinstance(normalized["bytes"], int)
                or normalized["bytes"] < 1
                or isinstance(normalized["width"], bool)
                or not isinstance(normalized["width"], int)
                or normalized["width"] < 1
                or isinstance(normalized["height"], bool)
                or not isinstance(normalized["height"], int)
                or normalized["height"] < 1
                or not isinstance(normalized["format"], str)
                or not normalized["format"]
                or not isinstance(normalized["mode"], str)
                or not normalized["mode"]
            ):
                raise ValueError("manifest image metadata is incomplete")
            images_by_sha[digest] = normalized
            images_by_sample[sample].append(normalized)

    results_by_sha: dict[str, dict[str, Any]] = {}
    for payload in results:
        if not isinstance(payload, dict):
            raise ValueError("result record must be an object")
        digest = str((payload.get("image") or {}).get("sha256") or "").strip().lower()
        if not SHA256_RE.fullmatch(digest):
            raise ValueError("result image SHA-256 is invalid")
        if digest in results_by_sha:
            raise ValueError(f"duplicate result image SHA-256: {digest}")
        results_by_sha[digest] = payload
    missing_results = sorted(set(images_by_sha) - set(results_by_sha))
    if missing_results:
        raise ValueError(f"result missing for {len(missing_results)} manifest images")

    sample_audit: list[dict[str, Any]] = []
    eligible: list[tuple[str, int]] = []
    evidence_by_sha: dict[str, tuple[str, bool]] = {}
    for sample in sorted(images_by_sample):
        stage_counts: Counter[str] = Counter()
        two_wall_count = 0
        for item in images_by_sample[sample]:
            stage, two_wall = _evidence_stage(results_by_sha[item["sourceImageSha256"]])
            evidence_by_sha[item["sourceImageSha256"]] = (stage, two_wall)
            stage_counts[stage] += 1
            two_wall_count += int(two_wall)
        if sample in exclusions:
            selection_status = "EXCLUDED"
        elif two_wall_count >= frames_per_sample:
            selection_status = "ELIGIBLE"
            eligible.append((sample, two_wall_count))
        else:
            selection_status = "INSUFFICIENT_TWO_WALL_EVIDENCE"
        sample_audit.append({
            "sampleId": sample,
            "manifestFrameCount": len(images_by_sample[sample]),
            "resultFrameCount": len(images_by_sample[sample]),
            "twoWallEvidenceCount": two_wall_count,
            "stageCounts": {key: stage_counts[key] for key in sorted(stage_counts)},
            "selectionStatus": selection_status,
        })

    selected_samples = [
        sample for sample, _ in sorted(eligible, key=lambda item: (-item[1], item[0]))[:max_samples]
    ]
    selected_set = set(selected_samples)
    for audit in sample_audit:
        if audit["sampleId"] in selected_set:
            audit["selectionStatus"] = "SELECTED"

    entries: list[dict[str, Any]] = []
    for sample in selected_samples:
        candidates = [
            item for item in images_by_sample[sample]
            if evidence_by_sha[item["sourceImageSha256"]][1]
        ]
        ranked = sorted(candidates, key=lambda item: (
            hashlib.sha256(
                f"{sample}|{item['sourceImageSha256']}".encode("utf-8")
            ).hexdigest(),
            item["relativePath"],
        ))
        for rank, item in enumerate(ranked[:frames_per_sample], start=1):
            payload = results_by_sha[item["sourceImageSha256"]]
            error = payload.get("error") if isinstance(payload.get("error"), dict) else {}
            stage = evidence_by_sha[item["sourceImageSha256"]][0]
            entries.append({
                **item,
                "selectionRank": rank,
                "selectionRule": "sha256(sampleId|sourceImageSha256)/1",
                "evidenceStage": stage,
                "topLevelErrorCode": str(error.get("code") or "NONE"),
                "requiredHumanShapes": list(REQUIRED_HUMAN_SHAPES),
                "reviewQuestions": list(REVIEW_QUESTIONS),
                "humanVerified": False,
            })

    return {
        "schemaVersion": "complete-groove-review-queue/1",
        "datasetIds": sorted(dataset_ids),
        "sourceManifestSha256s": sorted(manifest_hashes),
        "sourceResultSha256s": sorted(result_hashes),
        "selectionPolicy": {
            "sampleEvidenceRule": "at_least_frames_per_sample_with_two_wall_pixel_evidence",
            "withinSampleRule": "sha256(sampleId|sourceImageSha256)/1",
            "maxSamples": max_samples,
            "framesPerSample": frames_per_sample,
            "predictionAngleUsed": False,
            "thresholdDistanceUsed": False,
        },
        "excludedSamples": [
            {"sampleId": sample, "reason": exclusions[sample], "authority": "explicit_review_governance"}
            for sample in sorted(exclusions)
        ],
        "sampleAudit": sample_audit,
        "entries": entries,
        "truthPolicy": {
            "accuracyEvaluated": False,
            "algorithmOutputIsTruth": False,
            "humanVerified": False,
            "runtimeInputAllowed": False,
        },
    }


def write_review_queue_bundle(output_dir: Path, queue: dict[str, Any]) -> None:
    output_dir = output_dir.resolve()
    _require_external(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "review-queue.json").write_text(
        json.dumps(queue, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    entries = queue.get("entries") or []
    fieldnames = [
        "sampleId", "imageId", "conditionId", "repeatIndex", "relativePath",
        "sourceImageSha256", "selectionRank", "selectionRule", "evidenceStage",
        "topLevelErrorCode", "requiredHumanShapes", "reviewQuestions", "humanVerified",
    ]
    with (output_dir / "review-queue.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for item in entries:
            writer.writerow({
                **{key: item.get(key) for key in fieldnames},
                "requiredHumanShapes": ";".join(item["requiredHumanShapes"]),
                "reviewQuestions": ";".join(item["reviewQuestions"]),
            })
    review_manifest = {
        "schemaVersion": "inspection-dataset-manifest/1",
        "datasetId": "complete-groove-human-review-queue",
        "images": [{
            "imageId": item["imageId"],
            "relativePath": item["relativePath"],
            "sampleId": item["sampleId"],
            "conditionId": item["conditionId"],
            "repeatIndex": item["repeatIndex"],
            "sourceImageSha256": item["sourceImageSha256"],
            "sha256": item["sourceImageSha256"],
            "bytes": item["bytes"],
            "format": item["format"],
            "width": item["width"],
            "height": item["height"],
            "mode": item["mode"],
        } for item in entries],
    }
    (output_dir / "review-manifest.json").write_text(
        json.dumps(review_manifest, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _parse_exclusions(values: list[str]) -> dict[str, str]:
    output: dict[str, str] = {}
    for value in values:
        if "=" not in value:
            raise ValueError("--exclude-sample must use SAMPLE_ID=REASON")
        sample, reason = (part.strip() for part in value.split("=", 1))
        if not sample or not reason or sample in output:
            raise ValueError("excluded sample ids/reasons must be unique and non-empty")
        output[sample] = reason
    return output


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, action="append", required=True)
    parser.add_argument("--results", type=Path, action="append", required=True)
    parser.add_argument("--exclude-sample", action="append", default=[])
    parser.add_argument("--max-samples", type=int, default=1)
    parser.add_argument("--frames-per-sample", type=int, default=2)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        manifests = [json.loads(path.read_text(encoding="utf-8")) for path in args.manifest]
        results = [payload for path in args.results for payload in load_results(path)]
        queue = build_complete_groove_review_queue(
            manifests,
            results,
            exclusions=_parse_exclusions(args.exclude_sample),
            max_samples=args.max_samples,
            frames_per_sample=args.frames_per_sample,
            source_manifest_sha256s=[sha256_file(path) for path in args.manifest],
            source_result_sha256s=[sha256_file(path) for path in args.results],
        )
        write_review_queue_bundle(args.output_dir, queue)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(
        f"audited_samples={len(queue['sampleAudit'])} selected_samples="
        f"{sum(item['selectionStatus'] == 'SELECTED' for item in queue['sampleAudit'])} "
        f"queue_entries={len(queue['entries'])} accuracyEvaluated=false"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
