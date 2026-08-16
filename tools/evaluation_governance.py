#!/usr/bin/env python3
"""Pure offline governance helpers for A2 grouping, repeatability, and blind locks."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from PIL import Image

from tools.dataset_common import MANIFEST_SCHEMA_VERSION, inspect_image, natural_key, safe_relative_path


SHA256_PATTERN = "0123456789abcdef"
PURPOSES = {"unassigned", "development", "tuning", "validation", "test", "acceptance"}
BLIND_SALT = "a2-transitional-blind-v1"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def stable_json_sha256(payload: Any) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError(f"CSV is empty: {path.name}")
    return rows


def _sha(value: object, field: str) -> str:
    text = str(value or "").strip().lower()
    if len(text) != 64 or any(character not in SHA256_PATTERN for character in text):
        raise ValueError(f"{field} must be a lowercase SHA-256")
    return text


def _positive_int(value: object, field: str) -> int:
    try:
        number = int(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be a positive integer") from exc
    if number <= 0:
        raise ValueError(f"{field} must be a positive integer")
    return number


def _finite(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def percentile(values: Iterable[float], fraction: float) -> float | None:
    ordered = sorted(float(value) for value in values)
    if not ordered:
        return None
    position = (len(ordered) - 1) * fraction
    low, high = math.floor(position), math.ceil(position)
    if low == high:
        return ordered[low]
    weight = position - low
    return ordered[low] * (1.0 - weight) + ordered[high] * weight


def wrap_to_180(value: float) -> float:
    wrapped = (float(value) + 180.0) % 360.0 - 180.0
    return -180.0 if wrapped == 180.0 else wrapped


def circular_statistics(values: Iterable[float]) -> dict[str, Any]:
    data = [float(value) for value in values if _finite(value) is not None]
    if not data:
        return {"n": 0, "mean": None, "range": None, "standardDeviation": None, "p95AbsoluteResidual": None, "residuals": []}
    radians = [math.radians(value) for value in data]
    sine, cosine = sum(math.sin(value) for value in radians), sum(math.cos(value) for value in radians)
    mean = math.degrees(math.atan2(sine, cosine))
    mean = wrap_to_180(mean)
    residuals = [wrap_to_180(value - mean) for value in data]
    unwrapped = [mean + residual for residual in residuals]
    deviation = statistics.stdev(residuals) if len(residuals) >= 2 else None
    return {
        "n": len(data),
        "mean": mean,
        "range": max(unwrapped) - min(unwrapped) if len(unwrapped) >= 2 else 0.0,
        "standardDeviation": deviation,
        "p95AbsoluteResidual": percentile((abs(value) for value in residuals), 0.95),
        "residuals": residuals,
    }


def scalar_statistics(values: Iterable[float]) -> dict[str, Any]:
    data = [float(value) for value in values if _finite(value) is not None]
    if not data:
        return {"n": 0, "median": None, "range": None, "standardDeviation": None, "p95AbsoluteResidual": None}
    median = statistics.median(data)
    return {
        "n": len(data),
        "median": median,
        "range": max(data) - min(data) if len(data) >= 2 else 0.0,
        "standardDeviation": statistics.stdev(data) if len(data) >= 2 else None,
        "p95AbsoluteResidual": percentile((abs(value - median) for value in data), 0.95),
    }


def _normalize_rows(rows: list[dict[str, Any]], *, confirmed: bool) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    seen_hashes: set[str] = set()
    for row_number, raw in enumerate(rows, start=2):
        row = dict(raw)
        relative = str(row.get("relative_path", "")).strip()
        safe_relative_path(relative)
        if relative in indexed:
            raise ValueError(f"duplicate relative_path in {'confirmed grouping' if confirmed else 'inventory'}: {relative}")
        digest = _sha(row.get("source_image_sha256"), f"row {row_number} source_image_sha256")
        if digest in seen_hashes:
            raise ValueError(f"duplicate source_image_sha256 in {'confirmed grouping' if confirmed else 'inventory'}: {digest}")
        seen_hashes.add(digest)
        dataset_class = str(row.get("dataset_class", "")).strip().lower()
        if dataset_class not in {"normal", "bad"}:
            raise ValueError(f"invalid dataset_class for {relative}: {dataset_class!r}")
        row.update(relative_path=relative, source_image_sha256=digest, dataset_class=dataset_class)
        if confirmed:
            missing = [field for field in ("sample_id", "condition_id", "repeat_index", "grouping_authority", "grouping_provenance") if not str(row.get(field, "")).strip()]
            if missing:
                raise ValueError(f"confirmed grouping fields are missing for {relative}: {', '.join(missing)}")
            row["sample_id"] = str(row["sample_id"]).strip()
            row["condition_id"] = str(row["condition_id"]).strip()
            row["repeat_index"] = _positive_int(row["repeat_index"], f"{relative} repeat_index")
            row["grouping_authority"] = str(row["grouping_authority"]).strip()
            row["grouping_provenance"] = str(row["grouping_provenance"]).strip()
            split = str(row.get("split") or "unassigned").strip()
            if split not in PURPOSES:
                raise ValueError(f"invalid split for {relative}: {split!r}")
            row["split"] = split
        indexed[relative] = row
    if not indexed:
        raise ValueError("inventory/grouping cannot be empty")
    return indexed


def _normalize_semantics(records: dict[str, dict[str, Any]] | list[dict[str, Any]] | None) -> dict[str, dict[str, Any]]:
    if records is None:
        return {}
    if isinstance(records, dict):
        normalized = {str(key): dict(value) for key, value in records.items()}
    else:
        normalized = {str(row.get("relative_path", "")).strip(): dict(row) for row in records}
        if len(normalized) != len(records):
            raise ValueError("duplicate semantics relative_path")
    for relative in normalized:
        safe_relative_path(relative)
    return normalized


def expand_confirmed_segments(inventory_rows: list[dict[str, Any]], segment_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Expand compact human-confirmed capture ranges into per-image grouping rows."""
    inventory = _normalize_rows(inventory_rows, confirmed=False)
    by_identity: dict[tuple[str, int], dict[str, Any]] = {}
    for item in inventory.values():
        sequence = _positive_int(item.get("capture_sequence"), f"{item['relative_path']} capture_sequence")
        key = (item["dataset_class"], sequence)
        if key in by_identity:
            raise ValueError(f"duplicate capture_sequence within dataset_class: {key}")
        by_identity[key] = item
    output: list[dict[str, Any]] = []
    covered: set[str] = set()
    for row_number, row in enumerate(segment_rows, start=2):
        dataset_class = str(row.get("dataset_class", "")).strip().lower()
        if dataset_class not in {"normal", "bad"}:
            raise ValueError(f"invalid segment dataset_class at row {row_number}")
        start = _positive_int(row.get("start_capture_sequence"), f"segment row {row_number} start_capture_sequence")
        end = _positive_int(row.get("end_capture_sequence"), f"segment row {row_number} end_capture_sequence")
        if end < start:
            raise ValueError(f"segment end precedes start at row {row_number}")
        required = ("sample_id", "condition_id", "grouping_authority", "grouping_provenance")
        if any(not str(row.get(field, "")).strip() for field in required):
            raise ValueError(f"confirmed segment fields are missing at row {row_number}")
        split = str(row.get("split") or "unassigned").strip()
        if split not in PURPOSES:
            raise ValueError(f"invalid segment split at row {row_number}: {split!r}")
        selected = []
        for sequence in range(start, end + 1):
            item = by_identity.get((dataset_class, sequence))
            if item is None:
                raise ValueError(f"confirmed segment references missing capture: {dataset_class}/{sequence}")
            if item["relative_path"] in covered:
                raise ValueError(f"confirmed segments overlap at: {item['relative_path']}")
            covered.add(item["relative_path"])
            selected.append(item)
        for repeat, item in enumerate(selected, start=1):
            output.append({
                "relative_path": item["relative_path"],
                "source_image_sha256": item["source_image_sha256"],
                "sample_id": str(row["sample_id"]).strip(),
                "condition_id": str(row["condition_id"]).strip(),
                "repeat_index": str(repeat),
                "split": split,
                "dataset_class": dataset_class,
                "grouping_authority": str(row["grouping_authority"]).strip(),
                "grouping_provenance": str(row["grouping_provenance"]).strip(),
            })
    if covered != set(inventory):
        missing = sorted(set(inventory) - covered)
        raise ValueError(f"confirmed segments do not cover canonical inventory: {missing[:1]}")
    return sorted(output, key=lambda item: natural_key(item["relative_path"]))


def _metadata_by_path(metadata_manifest: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if metadata_manifest is None:
        return {}
    return {str(item.get("relativePath")): item for item in metadata_manifest.get("images", [])}


def _light_image_metadata(path: Path, expected_sha: str, verify_images: bool) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"inventory image does not exist: {path.name}")
    if verify_images:
        info = inspect_image(path)
        if info["sha256"] != expected_sha:
            raise ValueError(f"source image SHA-256 mismatch: {path.name}")
        return info
    with Image.open(path) as image:
        width, height = image.size
        image_format = image.format or path.suffix.removeprefix(".").upper()
        mode = image.mode
    return {"bytes": path.stat().st_size, "sha256": expected_sha, "format": image_format, "width": width, "height": height, "mode": mode}


def build_group_eligibility(manifest: dict[str, Any], minimum_frames: int = 20) -> dict[str, Any]:
    if manifest.get("policy", {}).get("groupingExplicit") is not True:
        raise ValueError("static eligibility requires confirmed explicit grouping")
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for item in manifest.get("images", []):
        grouped[(str(item.get("sampleId", "")), str(item.get("conditionId", "")))].append(item)
    groups: list[dict[str, Any]] = []
    for (sample, condition), items in sorted(grouped.items()):
        reasons: list[str] = []
        classes = {str(item.get("datasetClass")) for item in items}
        dataset_class = next(iter(classes)) if len(classes) == 1 else "mixed"
        ordered = sorted(items, key=lambda item: int(item["repeatIndex"]))
        if not sample or not condition or any(not item.get("groupingAuthority") or not item.get("groupingProvenance") for item in items):
            reasons.append("GROUPING_NOT_CONFIRMED")
        if len(items) < minimum_frames:
            reasons.append("FRAME_COUNT_LT_20")
        repeats = sorted(item.get("repeatIndex") for item in items)
        if repeats != list(range(1, len(items) + 1)):
            reasons.append("REPEAT_NOT_CONTIGUOUS")
        capture_sequences = [item.get("captureSequence") for item in ordered]
        if any(not isinstance(value, int) or isinstance(value, bool) for value in capture_sequences):
            reasons.append("CAPTURE_SEQUENCE_MISSING")
        elif capture_sequences != list(range(capture_sequences[0], capture_sequences[0] + len(capture_sequences))):
            reasons.append("CAPTURE_SEQUENCE_NOT_CONTIGUOUS")
        if len(classes) != 1:
            reasons.append("DATASET_CLASS_MIXED")
        if dataset_class == "bad":
            confirmed = all(
                item.get("badReason") and item.get("poseUsable") in {True, False}
                and item.get("semanticsAuthority") and item.get("semanticsProvenance")
                for item in items
            )
            if not confirmed:
                reasons.append("BAD_SEMANTICS_UNCONFIRMED")
            elif not all(item.get("poseUsable") is True for item in items):
                reasons.append("POSE_NOT_USABLE")
        reasons = sorted(set(reasons))
        groups.append({
            "sampleId": sample,
            "conditionId": condition,
            "datasetClass": dataset_class,
            "purpose": str(ordered[0].get("split", "unassigned")),
            "frameCount": len(items),
            "status": "ELIGIBLE" if not reasons else "EXCLUDED",
            "authoritative": not reasons,
            "exclusionReasons": reasons,
            "relativePaths": [str(item["relativePath"]) for item in ordered],
            "sourceImageSha256s": [str(item.get("sourceImageSha256") or item["sha256"]) for item in ordered],
        })
    return {
        "schemaVersion": "a2-static-group-eligibility/1",
        "minimumFrames": minimum_frames,
        "groupingExplicit": True,
        "groups": groups,
        "summary": {
            "groupCount": len(groups),
            "eligibleGroupCount": sum(item["status"] == "ELIGIBLE" for item in groups),
            "excludedGroupCount": sum(item["status"] == "EXCLUDED" for item in groups),
            "frameCount": sum(item["frameCount"] for item in groups),
            "exclusionReasonCounts": dict(sorted(Counter(reason for item in groups for reason in item["exclusionReasons"]).items())),
        },
    }


def prepare_dataset(
    data_root: Path,
    inventory_rows: list[dict[str, Any]],
    grouping_rows: list[dict[str, Any]],
    *,
    semantics_records: dict[str, dict[str, Any]] | list[dict[str, Any]] | None = None,
    metadata_manifest: dict[str, Any] | None = None,
    verify_images: bool = False,
    minimum_frames: int = 20,
    dataset_id: str = "a2-canonical-grouped",
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    inventory = _normalize_rows(inventory_rows, confirmed=False)
    grouping = _normalize_rows(grouping_rows, confirmed=True)
    if set(inventory) != set(grouping):
        missing = sorted(set(inventory) - set(grouping))
        extras = sorted(set(grouping) - set(inventory))
        raise ValueError(f"confirmed grouping coverage mismatch: missing={missing[:1]} extra={extras[:1]}")
    for relative, item in inventory.items():
        group = grouping[relative]
        if item["source_image_sha256"] != group["source_image_sha256"] or item["dataset_class"] != group["dataset_class"]:
            raise ValueError(f"confirmed grouping identity mismatch: {relative}")
    semantics = _normalize_semantics(semantics_records)
    if semantics and set(semantics) != set(inventory):
        raise ValueError("dataset semantics must exactly cover canonical inventory")
    sample_purposes: dict[str, set[str]] = defaultdict(set)
    lineage_purposes: dict[str, set[str]] = defaultdict(set)
    for item in grouping.values():
        if item["split"] != "unassigned":
            sample_purposes[item["sample_id"]].add(item["split"])
            lineage_purposes[item["source_image_sha256"]].add(item["split"])
    if any(len(values) > 1 for values in sample_purposes.values()):
        raise ValueError("one or more physical samples cross evaluation purposes")
    if any(len(values) > 1 for values in lineage_purposes.values()):
        raise ValueError("one or more source-image lineages cross evaluation purposes")

    metadata = _metadata_by_path(metadata_manifest)
    images: list[dict[str, Any]] = []
    verified = 0
    for relative in sorted(inventory, key=natural_key):
        source, group = inventory[relative], grouping[relative]
        semantic = semantics.get(relative, {})
        expected_sha = source["source_image_sha256"]
        if verify_images:
            info = _light_image_metadata(data_root.resolve() / safe_relative_path(relative), expected_sha, True)
            verified += 1
        elif relative in metadata:
            prior = metadata[relative]
            prior_sha = str(prior.get("sha256") or prior.get("sourceImageSha256") or "")
            if prior_sha != expected_sha:
                raise ValueError(f"metadata Manifest SHA mismatch: {relative}")
            info = {key: prior.get(key) for key in ("bytes", "format", "width", "height", "mode")} | {"sha256": expected_sha}
        elif (data_root / safe_relative_path(relative)).is_file():
            info = _light_image_metadata(data_root.resolve() / safe_relative_path(relative), expected_sha, False)
        else:
            info = {"bytes": 0, "sha256": expected_sha, "format": Path(relative).suffix.removeprefix(".").upper(), "width": 0, "height": 0, "mode": "UNKNOWN"}
        pose_text = str(semantic.get("pose_usable", "")).strip().lower()
        if pose_text not in {"", "true", "false"}:
            raise ValueError(f"invalid pose_usable for {relative}")
        pose_usable = None if not pose_text else pose_text == "true"
        authority = str(semantic.get("authority", "")).strip() or None
        provenance = str(semantic.get("provenance", "")).strip() or None
        if pose_usable is not None and (not authority or not provenance):
            raise ValueError(f"pose_usable requires semantics authority/provenance: {relative}")
        images.append({
            "imageId": f"{group['sample_id']}:{group['condition_id']}:{group['repeat_index']:04d}",
            "relativePath": relative,
            "sampleId": group["sample_id"],
            "position": group["condition_id"],
            "conditionId": group["condition_id"],
            "repeatIndex": group["repeat_index"],
            "captureSequence": _positive_int(source.get("capture_sequence"), f"{relative} capture_sequence") if str(source.get("capture_sequence", "")).strip() else None,
            "captureTimestamp": str(source.get("capture_timestamp", "")).strip() or None,
            "split": group["split"],
            "datasetClass": source["dataset_class"],
            "sourceImageSha256": expected_sha,
            "groupingAuthority": group["grouping_authority"],
            "groupingProvenance": group["grouping_provenance"],
            "badReason": str(semantic.get("bad_reason", "")).strip() or None,
            "productDisposition": str(semantic.get("product_disposition", "UNKNOWN")).strip().upper() or "UNKNOWN",
            "imageDisposition": str(semantic.get("image_disposition", "UNKNOWN")).strip().upper() or "UNKNOWN",
            "poseUsable": pose_usable,
            "semanticsAuthority": authority,
            "semanticsProvenance": provenance,
            **info,
        })
    manifest = {
        "schemaVersion": MANIFEST_SCHEMA_VERSION,
        "datasetId": dataset_id,
        "task": "slot_pose",
        "createdAt": utc_now(),
        "sourceRootHint": data_root.name,
        "datasetFingerprint": stable_json_sha256([(item["relativePath"], item["sha256"]) for item in images]),
        "policy": {
            "expectedRepeatsPerGroup": minimum_frames,
            "rawImagesAreExternal": True,
            "pathBase": "single_explicit_data_root",
            "listedPathsOnly": True,
            "groupingExplicit": True,
            "semanticsExplicit": bool(semantics),
            "evaluationPurposes": sorted({item["split"] for item in images}),
            "lockedAcceptance": any(item["split"] == "acceptance" for item in images),
            "crossClassSampleIdentityAssumption": "class_qualified_until_owner_mapping",
        },
        "reference": None,
        "images": images,
    }
    eligibility = build_group_eligibility(manifest, minimum_frames)
    report = {
        "schemaVersion": "a2-evaluation-preparation/1",
        "status": "PASSED",
        "inventoryStatus": "CONFIRMED_GROUPING_MATERIALIZED",
        "imageCount": len(images),
        "verifiedImageCount": verified,
        "manifestCanonicalSha256": stable_json_sha256(manifest),
        "eligibilityCanonicalSha256": stable_json_sha256(eligibility),
        "dataRootHint": data_root.name,
        "absolutePathsStored": False,
        "groupSummary": eligibility["summary"],
        "blockers": ["CROSS_CLASS_PHYSICAL_SAMPLE_MAPPING_UNCONFIRMED"],
    }
    return manifest, eligibility, report


def _geometry(payload: dict[str, Any]) -> dict[str, float | None]:
    diagnostics = payload.get("diagnostics") or {}
    physical = (diagnostics.get("physicalOuterCircle") or {}).get("physicalCircle") or {}
    datum = ((diagnostics.get("singleGroovePose") or {}).get("datumMeasurement") or {})
    opening = datum.get("grooveOpeningPoint") or {}
    return {
        "circleCenterX": _finite(physical.get("centerX")),
        "circleCenterY": _finite(physical.get("centerY")),
        "circleRadius": _finite(physical.get("radiusPx")),
        "grooveOpeningX": _finite(opening.get("x")),
        "grooveOpeningY": _finite(opening.get("y")),
    }


def _guidance_class(payloads: list[dict[str, Any]]) -> str:
    directions = {
        (payload.get("result") or {}).get("rotationDirection")
        for payload in payloads if (payload.get("result") or {}).get("valid") is True
    }
    directions.discard(None)
    if directions == {"NONE"}:
        return "TARGET_NEAR"
    if directions == {"CLOCKWISE"}:
        return "NEEDS_CLOCKWISE"
    if directions == {"COUNTERCLOCKWISE"}:
        return "NEEDS_COUNTERCLOCKWISE"
    return "MIXED_OR_UNAVAILABLE"


def build_static_repeatability(manifest: dict[str, Any], results: list[dict[str, Any]], eligibility: dict[str, Any]) -> dict[str, Any]:
    manifest_by_sha = {str(item["sha256"]): item for item in manifest.get("images", [])}
    results_by_sha: dict[str, dict[str, Any]] = {}
    for payload in results:
        digest = str((payload.get("image") or {}).get("sha256") or "")
        if not digest or digest in results_by_sha:
            raise ValueError(f"result image SHA is missing or duplicated: {digest!r}")
        results_by_sha[digest] = payload
    if set(manifest_by_sha) != set(results_by_sha):
        raise ValueError("results must exactly match Manifest images by SHA-256")
    eligibility_by_group = {(item["sampleId"], item["conditionId"]): item for item in eligibility.get("groups", [])}
    grouped: dict[tuple[str, str], list[tuple[dict[str, Any], dict[str, Any]]]] = defaultdict(list)
    for digest, item in manifest_by_sha.items():
        grouped[(str(item["sampleId"]), str(item["conditionId"]))].append((item, results_by_sha[digest]))

    output_groups: list[dict[str, Any]] = []
    pooled_residuals: list[float] = []
    for key, pairs in sorted(grouped.items()):
        sample, condition = key
        eligible = eligibility_by_group.get(key)
        if eligible is None:
            raise ValueError(f"eligibility group missing: {sample}/{condition}")
        pairs.sort(key=lambda pair: int(pair[0]["repeatIndex"]))
        payloads = [payload for _, payload in pairs]
        finals = [payload.get("result") or {} for payload in payloads]
        valid_payloads = [payload for payload in payloads if (payload.get("result") or {}).get("valid") is True]
        angles = [float(value) for payload in valid_payloads if (value := _finite((payload.get("result") or {}).get("currentAngleDeg"))) is not None]
        angle = circular_statistics(angles)
        residuals = angle.pop("residuals")
        if eligible["status"] == "ELIGIBLE":
            pooled_residuals.extend(residuals)
        geometries = [_geometry(payload) for payload in valid_payloads]
        timings = [value for payload in payloads if (value := _finite((payload.get("diagnostics") or {}).get("elapsedMs"))) is not None]
        errors = Counter(str((payload.get("error") or {}).get("code") or "NONE") for payload in payloads)
        output_groups.append({
            "sampleId": sample,
            "conditionId": condition,
            "datasetClass": eligible["datasetClass"],
            "purpose": eligible.get("purpose", "unassigned"),
            "frameCount": len(payloads),
            "eligibilityStatus": eligible["status"],
            "exclusionReasons": eligible["exclusionReasons"],
            "detection": {
                "validCount": len(valid_payloads),
                "failedCount": len(payloads) - len(valid_payloads),
                "validRate": len(valid_payloads) / len(payloads),
                "guidanceStatusCounts": dict(sorted(Counter(str(item.get("guidanceStatus")) for item in finals).items())),
                "rotationDirectionCounts": dict(sorted(Counter("NOT_AVAILABLE" if item.get("rotationDirection") is None else str(item.get("rotationDirection")) for item in finals).items())),
                "errorCodeCounts": dict(sorted(errors.items())),
            },
            "angle": angle | {"status": "AVAILABLE" if len(angles) >= 2 else "INSUFFICIENT_VALID_ANGLES"},
            "geometry": {field: scalar_statistics(item[field] for item in geometries if item[field] is not None) for field in ("circleCenterX", "circleCenterY", "circleRadius", "grooveOpeningX", "grooveOpeningY")},
            "timing": {
                "n": len(timings),
                "p50": percentile(timings, 0.50),
                "p95": percentile(timings, 0.95),
                "max": max(timings) if timings else None,
            },
            "guidanceClass": _guidance_class(payloads),
        })
    authoritative = [item for item in output_groups if item["eligibilityStatus"] == "ELIGIBLE"]
    coverage_counts = Counter(item["guidanceClass"] for item in authoritative)
    required = ("TARGET_NEAR", "NEEDS_CLOCKWISE", "NEEDS_COUNTERCLOCKWISE")
    pooled = scalar_statistics(pooled_residuals)
    pooled["range"] = (max(pooled_residuals) - min(pooled_residuals)) if len(pooled_residuals) >= 2 else (0.0 if pooled_residuals else None)
    summary = {
        "eligibleGroupCount": len(authoritative),
        "excludedGroupCount": len(output_groups) - len(authoritative),
        "authoritativeFrameCount": sum(item["frameCount"] for item in authoritative),
        "authoritativeValidCount": sum(item["detection"]["validCount"] for item in authoritative),
        "authoritativeValidRate": (
            sum(item["detection"]["validCount"] for item in authoritative) / sum(item["frameCount"] for item in authoritative)
            if authoritative else None
        ),
        "pooledWithinGroupAngleResidual": pooled,
        "worstGroups": {
            "angleRange": max(authoritative, key=lambda item: item["angle"]["range"] if item["angle"]["range"] is not None else -1)["sampleId"] + "/" + max(authoritative, key=lambda item: item["angle"]["range"] if item["angle"]["range"] is not None else -1)["conditionId"] if authoritative else None,
            "lowestValidRate": min(authoritative, key=lambda item: item["detection"]["validRate"])["sampleId"] + "/" + min(authoritative, key=lambda item: item["detection"]["validRate"])["conditionId"] if authoritative else None,
        },
        "guidanceCoverage": {
            "status": "COMPLETE" if all(coverage_counts[name] >= 1 for name in required) else "BLOCKED",
            "requiredClasses": list(required),
            "groupCounts": {name: coverage_counts[name] for name in (*required, "MIXED_OR_UNAVAILABLE")},
            "missingClasses": [name for name in required if coverage_counts[name] == 0],
        },
    }
    return {
        "schemaVersion": "a2-static-repeatability/1",
        "source": {
            "manifestImageCount": len(manifest_by_sha),
            "resultCount": len(results),
            "matchedCount": len(results),
            "manifestSha256": stable_json_sha256(manifest),
            "resultsSha256": stable_json_sha256(results),
        },
        "groupEligibility": eligibility.get("groups", []),
        "groups": output_groups,
        "summary": summary,
    }


def freeze_transitional_blind(manifest: dict[str, Any], eligibility: dict[str, Any], *, created_at: str | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    groups_by_sample: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for group in eligibility.get("groups", []):
        groups_by_sample[str(group["sampleId"])].append(group)
    images_by_sample: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in manifest.get("images", []):
        images_by_sample[str(item.get("sampleId"))].append(item)
    candidates: list[tuple[str, str, list[dict[str, Any]]]] = []
    for sample, groups in groups_by_sample.items():
        if not groups or any(group.get("status") != "ELIGIBLE" for group in groups):
            continue
        images = images_by_sample.get(sample, [])
        hashes = sorted(str(item.get("sourceImageSha256") or item["sha256"]) for item in images)
        if not images or len(hashes) != len(set(hashes)):
            continue
        rank = hashlib.sha256((BLIND_SALT + "\0" + "\n".join(hashes)).encode("ascii")).hexdigest()
        candidates.append((rank, sample, images))
    if not candidates:
        raise ValueError("no eligible physical sample is available for transitional blind selection")
    candidates.sort(key=lambda item: (item[0], item[1]))
    rank, selected_sample, selected_images = candidates[0]
    selected_images = sorted(selected_images, key=lambda item: natural_key(str(item["relativePath"])))
    blind_images = [dict(item, split="acceptance") for item in selected_images]
    blind_manifest = {
        **{key: value for key, value in manifest.items() if key != "images"},
        "datasetId": f"{manifest.get('datasetId', 'a2')}-transitional-blind",
        "createdAt": manifest.get("createdAt"),
        "datasetFingerprint": stable_json_sha256([(item["relativePath"], item["sha256"]) for item in blind_images]),
        "policy": {
            **manifest.get("policy", {}),
            "evaluationPurposes": ["acceptance"],
            "lockedAcceptance": True,
            "transitionalBlind": True,
            "blindStatus": "NON_STRICT_TRANSITIONAL",
            "maxExecutionCount": 1,
        },
        "images": blind_images,
    }
    development_images = [dict(item, split="development") for item in manifest.get("images", []) if str(item.get("sampleId")) != selected_sample]
    development_manifest = {
        **{key: value for key, value in manifest.items() if key != "images"},
        "datasetId": f"{manifest.get('datasetId', 'a2')}-development-with-blind-sample-excluded",
        "createdAt": manifest.get("createdAt"),
        "datasetFingerprint": stable_json_sha256([(item["relativePath"], item["sha256"]) for item in development_images]),
        "policy": {
            **manifest.get("policy", {}),
            "evaluationPurposes": ["development"],
            "lockedAcceptance": False,
            "excludedTransitionalBlindSampleId": selected_sample,
        },
        "images": development_images,
    }
    conditions = sorted({str(item["conditionId"]) for item in blind_images})
    hashes = sorted(str(item.get("sourceImageSha256") or item["sha256"]) for item in blind_images)
    base_lock = {
        "schemaVersion": "a2-transitional-blind-lock/1",
        "blindStatus": "NON_STRICT_TRANSITIONAL",
        "priorExposure": True,
        "selection": {
            "algorithm": "minimum_sha256_of_sorted_sample_source_hashes",
            "version": "1",
            "salt": BLIND_SALT,
            "candidateSampleCount": len(candidates),
            "selectedRankKey": rank,
        },
        "selectedSampleId": selected_sample,
        "selectedConditionIds": conditions,
        "selectedImageCount": len(blind_images),
        "selectedImageSha256s": hashes,
        "sourceManifestSha256": stable_json_sha256(manifest),
        "blindManifestSha256": stable_json_sha256(blind_manifest),
        "developmentManifestSha256": stable_json_sha256(development_manifest),
        "createdAtUtc": created_at or utc_now(),
        "maxExecutionCount": 1,
        "executionCount": 0,
        "strictUnseenClaimed": False,
        "limitations": [
            "The 700-image A2 replay was inspected before this lock was created.",
            "This lock reduces future selection leakage but is not an independent unseen test.",
            "A newly captured physically isolated sample is required for strict final testing.",
        ],
    }
    lock = base_lock | {"lockPayloadSha256": stable_json_sha256(base_lock)}
    return blind_manifest, lock


def build_development_manifest(manifest: dict[str, Any], lock: dict[str, Any]) -> dict[str, Any]:
    """Return the future-development partition with the locked sample fully removed."""
    selected_sample = str(lock.get("selectedSampleId") or "")
    if not selected_sample:
        raise ValueError("blind lock selectedSampleId is missing")
    images = [dict(item, split="development") for item in manifest.get("images", []) if str(item.get("sampleId")) != selected_sample]
    if len(images) == len(manifest.get("images", [])):
        raise ValueError("blind sample does not exist in source Manifest")
    development = {
        **{key: value for key, value in manifest.items() if key != "images"},
        "datasetId": f"{manifest.get('datasetId', 'a2')}-development-with-blind-sample-excluded",
        "createdAt": manifest.get("createdAt"),
        "datasetFingerprint": stable_json_sha256([(item["relativePath"], item["sha256"]) for item in images]),
        "policy": {
            **manifest.get("policy", {}),
            "evaluationPurposes": ["development"],
            "lockedAcceptance": False,
            "excludedTransitionalBlindSampleId": selected_sample,
        },
        "images": images,
    }
    if stable_json_sha256(development) != lock.get("developmentManifestSha256"):
        raise ValueError("development Manifest identity does not match blind lock")
    return development
