#!/usr/bin/env python3
"""Plan deterministic whole-part robustness folds without reading images/results."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import copy
from collections import defaultdict
from pathlib import Path, PurePosixPath
from typing import Any, Sequence


SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
KNOWN_PURPOSES = {"development", "validation", "test"}


class SealedLeakageError(ValueError):
    """Raised before any image/result read when a sealed identity is targeted."""


def _canonical_sha256(value: Any) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _validate_relative_path(value: str) -> str:
    path = PurePosixPath(value)
    if not value or path.is_absolute() or ".." in path.parts:
        raise ValueError(f"grouping relative_path is unsafe: {value!r}")
    return value


def _validated_inputs(
    grouping_rows: list[dict[str, Any]],
    root_cause_rows: list[dict[str, Any]],
    seal_lock: dict[str, Any],
) -> tuple[dict[str, list[dict[str, str]]], dict[str, str]]:
    sealed_sample = str(seal_lock.get("selectedSampleId", "")).strip()
    sealed_sha_values = seal_lock.get("selectedImageSha256s")
    lock_digest = str(seal_lock.get("lockPayloadSha256", "")).strip().lower()
    if (
        not sealed_sample
        or not isinstance(sealed_sha_values, list)
        or not sealed_sha_values
        or any(not SHA256_RE.fullmatch(str(value).lower()) for value in sealed_sha_values)
        or not SHA256_RE.fullmatch(lock_digest)
    ):
        raise ValueError("seal lock is missing a valid sample, image SHA set or lock payload SHA")
    causes: dict[str, str] = {}
    for row in root_cause_rows:
        sample = str(row.get("sample_id", "")).strip()
        family = str(row.get("failure_family", "")).strip()
        if not sample or not family or not str(row.get("selection_authority", "")).strip() or not str(
            row.get("selection_provenance", "")
        ).strip():
            raise ValueError("root-cause rows require sample, family, authority and provenance")
        if sample in causes:
            raise ValueError(f"root-cause sample appears more than once: {sample}")
        causes[sample] = family
    if not causes:
        raise ValueError("root-cause table is empty")

    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    sha_owner: dict[str, str] = {}
    purposes: dict[str, set[str]] = defaultdict(set)
    for row in grouping_rows:
        sample = str(row.get("sample_id", "")).strip()
        if sample not in causes:
            continue
        digest = str(row.get("source_image_sha256", "")).strip().lower()
        relative = _validate_relative_path(str(row.get("relative_path", "")).strip())
        if not SHA256_RE.fullmatch(digest):
            raise ValueError(f"invalid source SHA-256 for {relative}")
        if not str(row.get("condition_id", "")).strip():
            raise ValueError(f"confirmed condition_id is missing for {relative}")
        prior = sha_owner.setdefault(digest, sample)
        if prior != sample:
            raise ValueError(f"source SHA-256 crosses physical samples: {digest}")
        split = str(row.get("split", "unassigned")).strip().lower() or "unassigned"
        if split in KNOWN_PURPOSES:
            purposes[sample].add(split)
        grouped[sample].append({key: str(value) for key, value in row.items()})
    missing = sorted(set(causes) - set(grouped))
    if missing:
        raise ValueError(f"root-cause samples are absent from confirmed grouping: {missing}")
    crossed = sorted(sample for sample, values in purposes.items() if len(values) > 1)
    if crossed:
        raise ValueError(f"sample crosses purposes: {crossed}")

    sealed_sha = {str(value).lower() for value in sealed_sha_values}
    targeted_sha = {row["source_image_sha256"].lower() for rows in grouped.values() for row in rows}
    if sealed_sample in grouped or sealed_sha & targeted_sha:
        raise SealedLeakageError(
            "sealed sample/SHA intersects the requested robustness population; rejected before result/image read"
        )
    return dict(grouped), causes


def build_fold_plan(
    grouping_rows: list[dict[str, Any]],
    root_cause_rows: list[dict[str, Any]],
    seal_lock: dict[str, Any],
    *,
    fold_count: int = 3,
) -> dict[str, Any]:
    if isinstance(fold_count, bool) or not isinstance(fold_count, int) or not 2 <= fold_count <= 7:
        raise ValueError("fold_count must be an integer in [2,7]")
    grouped, causes = _validated_inputs(grouping_rows, root_cause_rows, seal_lock)
    sample_ids = sorted(grouped, key=lambda sample: (hashlib.sha256(sample.encode()).hexdigest(), sample))
    status = "READY" if len(sample_ids) >= fold_count else "INSUFFICIENT_PARTS"
    folds: list[dict[str, Any]] = []
    if status == "READY":
        buckets = [sample_ids[index::fold_count] for index in range(fold_count)]
        all_samples = set(sample_ids)
        for index, validation_samples in enumerate(buckets, start=1):
            validation = sorted(validation_samples)
            development = sorted(all_samples - set(validation))
            validation_sha = {
                row["source_image_sha256"].lower()
                for sample in validation for row in grouped[sample]
            }
            development_sha = {
                row["source_image_sha256"].lower()
                for sample in development for row in grouped[sample]
            }
            folds.append({
                "foldId": f"fold-{index:02d}",
                "developmentSampleIds": development,
                "validationSampleIds": validation,
                "developmentImageCount": sum(len(grouped[sample]) for sample in development),
                "validationImageCount": sum(len(grouped[sample]) for sample in validation),
                "developmentSha256SetHash": _canonical_sha256(sorted(development_sha)),
                "validationSha256SetHash": _canonical_sha256(sorted(validation_sha)),
                "sampleIntersectionCount": len(set(development) & set(validation)),
                "sha256IntersectionCount": len(development_sha & validation_sha),
            })
    families: dict[str, list[str]] = defaultdict(list)
    for sample, family in causes.items():
        families[family].append(sample)
    return {
        "schemaVersion": "a2-robustness-fold-plan/1",
        "planStatus": status,
        "priorExposure": True,
        "strictBlind": False,
        "selectionStrategy": "sha256(sample_id)-ordered-round-robin/1",
        "foldCount": fold_count,
        "sampleCount": len(sample_ids),
        "imageCount": sum(len(rows) for rows in grouped.values()),
        "groupingRowsSha256": _canonical_sha256(grouping_rows),
        "rootCauseRowsSha256": _canonical_sha256(root_cause_rows),
        "sealLockPayloadSha256": str(seal_lock.get("lockPayloadSha256", "")),
        "sealedSampleId": str(seal_lock.get("selectedSampleId", "")),
        "sealedImageCount": len(seal_lock.get("selectedImageSha256s", [])),
        "families": [
            {"failureFamily": family, "sampleIds": sorted(samples)}
            for family, samples in sorted(families.items())
        ],
        "folds": folds,
        "limitations": [
            "All source images and historical results were previously exposed; folds are not strict blind test sets.",
            "Algorithm outputs are diagnostic measurements, not geometric truth.",
        ],
    }


def materialize_fold_manifests(
    plan: dict[str, Any], source_manifest: dict[str, Any],
) -> dict[str, dict[str, dict[str, Any]]]:
    """Create run_batch-compatible subsets after the identity-only plan is frozen."""
    if plan.get("planStatus") != "READY":
        raise ValueError("fold manifests require a READY plan")
    output: dict[str, dict[str, dict[str, Any]]] = {}
    source_images = source_manifest.get("images")
    if not isinstance(source_images, list):
        raise ValueError("source manifest images must be a list")
    for fold in plan["folds"]:
        fold_id = str(fold["foldId"])
        output[fold_id] = {}
        for purpose, field in (
            ("development", "developmentSampleIds"),
            ("validation", "validationSampleIds"),
        ):
            samples = set(fold[field])
            images = [copy.deepcopy(item) for item in source_images if item.get("sampleId") in samples]
            if {str(item.get("sampleId")) for item in images} != samples:
                raise ValueError(f"source manifest does not cover {fold_id} {purpose} samples")
            for item in images:
                item["split"] = purpose
            manifest = copy.deepcopy(source_manifest)
            manifest["datasetId"] = f"{source_manifest.get('datasetId', 'a2')}-robustness-{fold_id}-{purpose}"
            manifest["datasetFingerprint"] = _canonical_sha256(
                sorted(str(item.get("sha256") or item.get("sourceImageSha256")) for item in images)
            )
            manifest["images"] = images
            output[fold_id][purpose] = manifest
    return output


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--grouping", type=Path, required=True)
    parser.add_argument("--root-causes", type=Path, required=True)
    parser.add_argument("--seal-lock", type=Path, required=True)
    parser.add_argument("--fold-count", type=int, default=3)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-manifest", type=Path)
    parser.add_argument("--manifest-dir", type=Path)
    args = parser.parse_args(argv)
    plan = build_fold_plan(
        _read_csv(args.grouping), _read_csv(args.root_causes),
        json.loads(args.seal_lock.read_text(encoding="utf-8")), fold_count=args.fold_count,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if (args.source_manifest is None) != (args.manifest_dir is None):
        raise ValueError("--source-manifest and --manifest-dir must be provided together")
    if args.source_manifest is not None:
        subsets = materialize_fold_manifests(
            plan, json.loads(args.source_manifest.read_text(encoding="utf-8")),
        )
        assert args.manifest_dir is not None
        for fold_id, purposes in subsets.items():
            directory = args.manifest_dir / fold_id
            directory.mkdir(parents=True, exist_ok=True)
            for purpose, manifest in purposes.items():
                (directory / f"{purpose}-manifest.json").write_text(
                    json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
                )
    return 0 if plan["planStatus"] == "READY" else 2


if __name__ == "__main__":
    raise SystemExit(main())
