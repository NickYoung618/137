#!/usr/bin/env python3
"""Render per-image hole-2 previews and strictly grouped batch reports.

This offline delivery tool reads existing detector JSONL.  It does not run a
detector, read target truth, convert pixels to millimetres, or make production
OK/NG decisions.  Its drawings contain only dimension 7 and Phi12.2
predictions, not a complete part contour.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "hole2-batch-visual-report/1"
SCOPE = (
    "Only dimension 7 and Phi12.2 predictions are shown; "
    "this is not ground truth or a complete part contour."
)
CAPTURE_DISCLAIMER = (
    "captureGroupEstimate uses filename suffixes only; these are not confirmed "
    "physical product counts without an externally confirmed acquisition rule."
)
IMAGE_EXTENSIONS = {".bmp", ".png", ".jpg", ".jpeg", ".tif", ".tiff"}
INDEX_FIELDS = [
    "group", "imageName", "imagePath", "sequenceNumber",
    "executionSuccess", "executionError",
    "registrationValid", "registrationFailureReason",
    "d7Valid", "d7FailureReason", "d7LengthPx",
    "d7EvidenceComplete", "d7EvidenceAuditStatus", "d7EvidenceAuditReason",
    "phiValid", "phiFailureReason", "phiDiameterPx",
    "phiEvidenceComplete", "phiEvidenceAuditStatus", "phiEvidenceAuditReason",
    "bothMeasurementsValid", "previewJpeg", "predictionLabelmeJson",
    "captureGroupIndex", "captureGroupComplete",
]


def _require_external(path: Path, role: str) -> Path:
    resolved = path.expanduser().resolve()
    repository = PROJECT_ROOT.resolve()
    if resolved == repository or repository in resolved.parents:
        raise ValueError(f"{role} must remain outside the Git worktree")
    return resolved


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            record = json.loads(line)
            if not isinstance(record, dict):
                raise ValueError(f"JSONL record {line_number} must be an object")
            missing = {
                "group", "imagePath", "executionError", "result"
            } - record.keys()
            if missing:
                raise ValueError(
                    f"JSONL record {line_number} missing: {','.join(sorted(missing))}"
                )
            records.append(record)
    if not records:
        raise ValueError("batch JSONL contains no records")
    identities: set[tuple[str, str]] = set()
    for record in records:
        identity = _identity(record)
        if identity in identities:
            raise ValueError(
                f"duplicate group+filename record identity: {identity[0]}/{identity[1]}"
            )
        identities.add(identity)
    return records


def _identity(record: dict[str, Any]) -> tuple[str, str]:
    return str(record["group"]), Path(str(record["imagePath"])).name


def _safe_component(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._")
    return safe or "item"


def _parse_sequence(image_name: str) -> int | None:
    match = re.search(r"(\d+)$", Path(image_name).stem)
    return None if match is None else int(match.group(1))


def _result(record: dict[str, Any]) -> dict[str, Any] | None:
    result = record.get("result")
    return result if isinstance(result, dict) else None


def _registration(record: dict[str, Any]) -> dict[str, Any]:
    result = _result(record)
    value = None if result is None else result.get("registration")
    return value if isinstance(value, dict) else {}


def _feature(record: dict[str, Any], name: str) -> dict[str, Any]:
    result = _result(record)
    features = None if result is None else result.get("features")
    value = None if not isinstance(features, dict) else features.get(name)
    return value if isinstance(value, dict) else {}


def _feature_valid(record: dict[str, Any], name: str) -> bool:
    return (
        not record.get("executionError")
        and bool(_feature(record, name).get("measurementValid", False))
    )


def _usable_points(value: Any) -> bool:
    return isinstance(value, list) and len(value) >= 2


def _evidence_audit(record: dict[str, Any], name: str) -> dict[str, Any]:
    feature = _feature(record, name)
    if not _feature_valid(record, name):
        return {"complete": False, "status": "not_applicable", "reason": "measurement_invalid"}
    explicit_status = feature.get("evidenceAuditStatus")
    if explicit_status in {"complete", "partial", "unavailable"}:
        return {
            "complete": bool(feature.get("evidenceComplete", explicit_status == "complete")),
            "status": explicit_status,
            "reason": feature.get("evidenceAuditReason"),
        }
    target = feature.get("target")
    if not isinstance(target, dict):
        return {"complete": False, "status": "unavailable", "reason": "target_geometry_unavailable"}
    if name == "7":
        evidence = target.get("rawEdgeEvidence", {})
        fitted = target.get("fittedGeometry", {})
        raw_sides = {
            item.get("side") for item in evidence.get("boundaries", [])
            if isinstance(item, dict) and _usable_points(item.get("pointsPx"))
        } if isinstance(evidence, dict) else set()
        fitted_sides = {
            item.get("side") for item in fitted.get("boundaries", [])
            if isinstance(item, dict) and _usable_points(item.get("segmentPointsPx"))
        } if isinstance(fitted, dict) else set()
        sides = raw_sides & fitted_sides
        if sides == {"A", "B"}:
            return {"complete": True, "status": "complete", "reason": None}
        if sides:
            return {"complete": False, "status": "partial", "reason": "only_one_boundary_evidence_available"}
        return {"complete": False, "status": "unavailable", "reason": "boundary_evidence_unavailable"}
    evidence = target.get("rawEdgeEvidence", {})
    segments = evidence.get("arcSegments", []) if isinstance(evidence, dict) else []
    calibrated = any(
        isinstance(item, dict)
        and item.get("side") == "reference_left"
        and _usable_points(item.get("pointsPx"))
        for item in segments
    )
    return (
        {"complete": True, "status": "complete", "reason": None}
        if calibrated else
        {"complete": False, "status": "unavailable", "reason": "calibrated_arc_evidence_unavailable"}
    )


def _record_evidence_warning(record: dict[str, Any]) -> bool:
    return any(
        _feature_valid(record, name) and not _evidence_audit(record, name)["complete"]
        for name in ("7", "Phi12.2")
    )


def _record_invalid(record: dict[str, Any]) -> bool:
    return (
        bool(record.get("executionError"))
        or not bool(_registration(record).get("registrationValid", False))
        or not _feature_valid(record, "7")
        or not _feature_valid(record, "Phi12.2")
    )


def _reason(record: dict[str, Any], role: str) -> str | None:
    if record.get("executionError"):
        return "execution_error"
    if role == "registration":
        return _registration(record).get("failureReason")
    return _feature(record, role).get("failureReason")


def _measurement(record: dict[str, Any], name: str, key: str) -> float | None:
    if not _feature_valid(record, name):
        return None
    target = _feature(record, name).get("target")
    value = None if not isinstance(target, dict) else target.get(key)
    if not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        return None
    return float(value)


def _selector_matches(record: dict[str, Any], selector: str) -> bool:
    group, name = _identity(record)
    stem = Path(name).stem
    return selector in {name, stem, f"{group}/{name}", f"{group}/{stem}"}


def _select_records(
    records: list[dict[str, Any]],
    frames: list[str],
    only_invalid: bool,
) -> tuple[list[dict[str, Any]], str]:
    selectors = [value.strip() for value in frames if value.strip()]
    if selectors:
        selected: list[dict[str, Any]] = []
        selected_identities: set[tuple[str, str]] = set()
        for selector in selectors:
            matches = [record for record in records if _selector_matches(record, selector)]
            if not matches:
                raise ValueError(f"explicit frame selector did not match: {selector}")
            if len(matches) > 1:
                raise ValueError(
                    f"explicit frame selector is ambiguous; use group/name: {selector}"
                )
            record = matches[0]
            if _identity(record) not in selected_identities:
                selected.append(record)
                selected_identities.add(_identity(record))
        mode = "explicit_frames"
    else:
        selected = list(records)
        mode = "all_records"
    if only_invalid:
        selected = [record for record in selected if _record_invalid(record)]
        mode = "only_invalid" if not selectors else "explicit_frames_and_only_invalid"
    return selected, mode


def _image_catalog(image_root: Path) -> dict[str, list[Path]]:
    catalog: dict[str, list[Path]] = {}
    for path in image_root.rglob("*"):
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS:
            catalog.setdefault(path.name, []).append(path.resolve())
    return catalog


def _resolve_image(
    record: dict[str, Any],
    image_root: Path,
    catalog: dict[str, list[Path]],
) -> Path:
    group, name = _identity(record)
    recorded = Path(str(record["imagePath"])).expanduser()
    candidates: list[Path] = []
    if recorded.is_file():
        candidates.append(recorded.resolve())
    grouped = image_root / group / name
    if grouped.is_file():
        candidates.append(grouped.resolve())
    candidates.extend(catalog.get(name, []))
    unique: list[Path] = []
    for candidate in candidates:
        try:
            candidate.relative_to(image_root)
        except ValueError:
            continue
        if candidate not in unique:
            unique.append(candidate)
    if len(unique) != 1:
        raise ValueError(
            f"image must resolve uniquely below image root: {group}/{name} "
            f"matches={len(unique)}"
        )
    return unique[0]


def _font(size: int) -> ImageFont.ImageFont:
    try:
        return ImageFont.truetype("DejaVuSans.ttf", size=size)
    except OSError:
        return ImageFont.load_default()


def _format_number(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.3f}"


def _status_lines(record: dict[str, Any]) -> list[str]:
    group, name = _identity(record)
    execution_error = record.get("executionError")
    registration = _registration(record)
    d7_valid = _feature_valid(record, "7")
    phi_valid = _feature_valid(record, "Phi12.2")
    lines = [f"image={name}  group={group}"]
    if execution_error:
        lines.append(f"executionError={execution_error}")
    lines.append(
        "registration="
        f"{bool(registration.get('registrationValid', False))} "
        f"reason={_reason(record, 'registration')}"
    )
    lines.append(
        f"7 valid={d7_valid} reason={_reason(record, '7')} "
        f"lengthPx={_format_number(_measurement(record, '7', 'lengthPx'))} "
        f"evidence={_evidence_audit(record, '7')['status']}"
    )
    lines.append(
        f"Phi12.2 valid={phi_valid} reason={_reason(record, 'Phi12.2')} "
        f"diameterPx={_format_number(_measurement(record, 'Phi12.2', 'diameterPx'))} "
        f"evidence={_evidence_audit(record, 'Phi12.2')['status']}"
    )
    return lines


def _draw_preview(
    image_path: Path,
    record: dict[str, Any],
    output_path: Path,
    max_width: int,
) -> tuple[int, int]:
    image = Image.open(image_path).convert("RGB")
    scale = min(1.0, max_width / float(image.width))
    size = (
        max(1, int(round(image.width * scale))),
        max(1, int(round(image.height * scale))),
    )
    if size != image.size:
        image = image.resize(size, Image.Resampling.LANCZOS)
    draw = ImageDraw.Draw(image)
    line_width = max(2, int(round(5 * scale)))
    marker = max(3, int(round(7 * scale)))

    d7 = _feature(record, "7")
    if _feature_valid(record, "7") and isinstance(d7.get("target"), dict):
        target = d7["target"]
        fitted = target.get("fittedGeometry", {})
        boundaries = fitted.get("boundaries", []) if isinstance(fitted, dict) else []
        for index, boundary in enumerate(boundaries):
            points = boundary.get("segmentPointsPx") if isinstance(boundary, dict) else None
            if isinstance(points, list) and len(points) >= 2:
                scaled = [
                    (float(point[0]) * scale, float(point[1]) * scale)
                    for point in points
                ]
                color = (255, 190, 0) if index == 0 else (255, 110, 0)
                draw.line(scaled, fill=color, width=line_width)
        annotation = target.get("measurementAnnotation", {})
        points = annotation.get("pointsPx") if isinstance(annotation, dict) else None
        if len(boundaries) >= 2 and isinstance(points, list) and len(points) == 2:
            scaled = [(float(p[0]) * scale, float(p[1]) * scale) for p in points]
            draw.line(scaled, fill=(0, 235, 255), width=line_width)
            for x, y in scaled:
                draw.ellipse((x - marker, y - marker, x + marker, y + marker),
                             fill=(0, 235, 255))

    phi = _feature(record, "Phi12.2")
    if _feature_valid(record, "Phi12.2") and isinstance(phi.get("target"), dict):
        evidence = phi["target"].get("rawEdgeEvidence", {})
        segments = evidence.get("arcSegments", []) if isinstance(evidence, dict) else []
        for segment in segments:
            if not isinstance(segment, dict) or segment.get("side") != "reference_left":
                continue
            points = segment.get("pointsPx") if isinstance(segment, dict) else None
            if isinstance(points, list) and len(points) >= 2:
                scaled = [(float(p[0]) * scale, float(p[1]) * scale) for p in points]
                draw.line(scaled, fill=(0, 255, 80), width=line_width)

    lines = _status_lines(record)
    font_size = max(9, min(24, image.width // 75))
    font = _font(font_size)
    line_height = font_size + 3
    panel_height = min(image.height, 8 + line_height * len(lines))
    panel_color = (
        (120, 0, 0) if _record_invalid(record)
        else (145, 92, 0) if _record_evidence_warning(record)
        else (0, 0, 0)
    )
    draw.rectangle((0, 0, image.width - 1, panel_height), fill=panel_color)
    y = 4
    for line in lines:
        draw.text((6, y), line, fill=(255, 255, 255), font=font)
        y += line_height

    if not _feature_valid(record, "7") and not _feature_valid(record, "Phi12.2"):
        border_width = max(3, image.width // 300)
        for offset in range(border_width):
            draw.rectangle(
                (offset, offset, image.width - 1 - offset, image.height - 1 - offset),
                outline=(255, 0, 0),
            )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path, format="JPEG", quality=82, optimize=True)
    return image.size


def _prediction_shapes(record: dict[str, Any]) -> list[dict[str, Any]]:
    shapes: list[dict[str, Any]] = []
    d7 = _feature(record, "7")
    if _feature_valid(record, "7") and isinstance(d7.get("target"), dict):
        target = d7["target"]
        fitted = target.get("fittedGeometry", {})
        boundaries = fitted.get("boundaries", []) if isinstance(fitted, dict) else []
        for boundary in boundaries:
            points = boundary.get("segmentPointsPx") if isinstance(boundary, dict) else None
            side = boundary.get("side") if isinstance(boundary, dict) else None
            if isinstance(points, list) and len(points) >= 2 and side in {"A", "B"}:
                shapes.append({
                    "label": f"prediction:7:boundary:{side}",
                    "points": [[float(value) for value in point] for point in points],
                    "group_id": "prediction:7",
                    "description": "fitted neck outer-contour boundary; original target pixels",
                    "shape_type": "line",
                    "flags": {},
                })
        annotation = target.get("measurementAnnotation", {})
        points = annotation.get("pointsPx") if isinstance(annotation, dict) else None
        if len(boundaries) >= 2 and isinstance(points, list) and len(points) == 2:
            shapes.append({
                "label": "prediction:7:dimension",
                "points": [[float(value) for value in point] for point in points],
                "group_id": "prediction:7",
                "description": "perpendicular distance annotation; not an edge",
                "shape_type": "line",
                "flags": {},
            })
    phi = _feature(record, "Phi12.2")
    if _feature_valid(record, "Phi12.2") and isinstance(phi.get("target"), dict):
        evidence = phi["target"].get("rawEdgeEvidence", {})
        segments = evidence.get("arcSegments", []) if isinstance(evidence, dict) else []
        side_counts: dict[str, int] = {}
        for segment in segments:
            points = segment.get("pointsPx") if isinstance(segment, dict) else None
            side = str(segment.get("side", "unknown")) if isinstance(segment, dict) else "unknown"
            if side != "reference_left":
                continue
            if not isinstance(points, list) or len(points) < 2:
                continue
            index = side_counts.get(side, 0)
            side_counts[side] = index + 1
            shapes.append({
                "label": f"prediction:Phi12.2:arc:{side}:{index}",
                "points": [[float(value) for value in point] for point in points],
                "group_id": "prediction:Phi12.2",
                "description": "detected visible outer-contour arc; no unobserved circle extrapolation",
                "shape_type": "linestrip",
                "flags": {},
            })
    return shapes


def _prediction_document(
    record: dict[str, Any],
    image_path: Path,
    width: int,
    height: int,
) -> dict[str, Any]:
    result = _result(record)
    return {
        "version": "5.5.0",
        "flags": {},
        "shapes": _prediction_shapes(record),
        "imagePath": str(image_path),
        "imageData": None,
        "imageHeight": height,
        "imageWidth": width,
        "predictionMetadata": {
            "schemaVersion": SCHEMA_VERSION,
            "scope": SCOPE,
            "isGroundTruth": False,
            "isCompletePartContour": False,
            "algorithmVersion": None if result is None else result.get("algorithmVersion"),
            "authoritativeReference": None if result is None else result.get("authoritativeReference"),
            "runtimeInputProvenance": None if result is None else result.get("runtimeInputs"),
            "group": str(record["group"]),
            "executionError": record.get("executionError"),
            "registration": {
                "valid": bool(_registration(record).get("registrationValid", False)),
                "failureReason": _reason(record, "registration"),
            },
            "features": {
                "7": {
                    "valid": _feature_valid(record, "7"),
                    "failureReason": _reason(record, "7"),
                    "lengthPx": _measurement(record, "7", "lengthPx"),
                    "evidenceComplete": _evidence_audit(record, "7")["complete"],
                    "evidenceAuditStatus": _evidence_audit(record, "7")["status"],
                    "evidenceAuditReason": _evidence_audit(record, "7")["reason"],
                },
                "Phi12.2": {
                    "valid": _feature_valid(record, "Phi12.2"),
                    "failureReason": _reason(record, "Phi12.2"),
                    "diameterPx": _measurement(record, "Phi12.2", "diameterPx"),
                    "evidenceComplete": _evidence_audit(record, "Phi12.2")["complete"],
                    "evidenceAuditStatus": _evidence_audit(record, "Phi12.2")["status"],
                    "evidenceAuditReason": _evidence_audit(record, "Phi12.2")["reason"],
                },
            },
        },
    }


def _new_group_stats() -> dict[str, Any]:
    return {
        "total": 0,
        "executionSuccess": 0,
        "executionError": 0,
        "registrationValid": 0,
        "registrationInvalid": 0,
        "featureValid": {"7": 0, "Phi12.2": 0},
        "featureInvalid": {"7": 0, "Phi12.2": 0},
        "evidenceComplete": {"7": 0, "Phi12.2": 0},
        "evidenceAuditStatus": {"7": Counter(), "Phi12.2": Counter()},
        "bothMeasurementsValid": 0,
        "failureReasons": {
            "executionError": Counter(),
            "registration": Counter(),
            "7": Counter(),
            "Phi12.2": Counter(),
        },
        "generatedPreviewCount": 0,
        "generatedLabelmeCount": 0,
    }


def _execution_reason(value: Any) -> str:
    text = str(value)
    return text.split(":", 1)[0] if text else "unknown"


def _group_stats(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    groups: dict[str, dict[str, Any]] = {}
    for record in records:
        group = str(record["group"])
        stats = groups.setdefault(group, _new_group_stats())
        stats["total"] += 1
        execution_error = record.get("executionError")
        if execution_error:
            stats["executionError"] += 1
            stats["failureReasons"]["executionError"][_execution_reason(execution_error)] += 1
        else:
            stats["executionSuccess"] += 1
        registration_valid = (
            not execution_error
            and bool(_registration(record).get("registrationValid", False))
        )
        stats["registrationValid" if registration_valid else "registrationInvalid"] += 1
        if not registration_valid:
            stats["failureReasons"]["registration"][
                _reason(record, "registration") or "invalid_without_reason"
            ] += 1
        valid_features = []
        for name in ("7", "Phi12.2"):
            valid = _feature_valid(record, name)
            valid_features.append(valid)
            stats["featureValid" if valid else "featureInvalid"][name] += 1
            audit = _evidence_audit(record, name)
            stats["evidenceAuditStatus"][name][audit["status"]] += 1
            if audit["complete"]:
                stats["evidenceComplete"][name] += 1
            if not valid:
                stats["failureReasons"][name][
                    _reason(record, name) or "invalid_without_reason"
                ] += 1
        if all(valid_features):
            stats["bothMeasurementsValid"] += 1
    return groups


def _serialize_group_stats(stats: dict[str, Any]) -> dict[str, Any]:
    value = dict(stats)
    value["featureValid"] = dict(stats["featureValid"])
    value["featureInvalid"] = dict(stats["featureInvalid"])
    value["evidenceComplete"] = dict(stats["evidenceComplete"])
    value["evidenceAuditStatus"] = {
        name: dict(sorted(counter.items()))
        for name, counter in stats["evidenceAuditStatus"].items()
    }
    value["failureReasons"] = {
        role: dict(sorted(counter.items()))
        for role, counter in stats["failureReasons"].items()
    }
    return value


def _capture_group_estimate(
    records: list[dict[str, Any]],
    images_per_product: int,
) -> tuple[dict[str, Any], dict[tuple[str, str], dict[str, Any]]]:
    by_group: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        by_group.setdefault(str(record["group"]), []).append(record)
    group_reports: dict[str, Any] = {}
    membership: dict[tuple[str, str], dict[str, Any]] = {}
    for group, group_records in sorted(by_group.items()):
        parsed: list[tuple[int, dict[str, Any]]] = []
        missing_suffix: list[str] = []
        sequence_counts: Counter[int] = Counter()
        for record in group_records:
            sequence = _parse_sequence(_identity(record)[1])
            if sequence is None:
                missing_suffix.append(_identity(record)[1])
                continue
            parsed.append((sequence, record))
            sequence_counts[sequence] += 1
        estimated_groups: list[dict[str, Any]] = []
        if parsed:
            anchor = min(sequence for sequence, _ in parsed)
            buckets: dict[int, list[tuple[int, dict[str, Any]]]] = {}
            for sequence, record in parsed:
                bucket = (sequence - anchor) // images_per_product
                buckets.setdefault(bucket, []).append((sequence, record))
            for ordinal, bucket in enumerate(sorted(buckets), 1):
                items = buckets[bucket]
                expected_start = anchor + bucket * images_per_product
                expected_end = expected_start + images_per_product - 1
                unique_sequences = sorted({sequence for sequence, _ in items})
                gaps = [
                    sequence for sequence in range(expected_start, expected_end + 1)
                    if sequence not in unique_sequences
                ]
                duplicates = sorted(
                    sequence for sequence in unique_sequences
                    if sequence_counts[sequence] > 1
                )
                complete = not gaps and not duplicates and len(items) == images_per_product
                estimate = {
                    "captureGroupIndex": ordinal,
                    "expectedSequenceStart": expected_start,
                    "expectedSequenceEnd": expected_end,
                    "observedSequences": unique_sequences,
                    "observedCount": len(items),
                    "uniqueSequenceCount": len(unique_sequences),
                    "complete": complete,
                    "gaps": gaps,
                    "duplicateSequences": duplicates,
                }
                estimated_groups.append(estimate)
                for sequence, record in items:
                    membership[_identity(record)] = {
                        "captureGroupIndex": ordinal,
                        "captureGroupComplete": complete,
                        "sequenceNumber": sequence,
                    }
            anchor_sequence: int | None = anchor
        else:
            anchor_sequence = None
        group_reports[group] = {
            "anchorSequence": anchor_sequence,
            "estimatedCaptureGroupCount": len(estimated_groups),
            "completeGroupCount": sum(item["complete"] for item in estimated_groups),
            "incompleteGroupCount": sum(not item["complete"] for item in estimated_groups),
            "missingSequenceSuffix": sorted(missing_suffix),
            "estimatedGroups": estimated_groups,
        }
    return {
        "imagesPerProductParameter": images_per_product,
        "confirmedPhysicalProductCount": False,
        "disclaimer": CAPTURE_DISCLAIMER,
        "groups": group_reports,
    }, membership


def _write_index(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=INDEX_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def _summary_text(summary: dict[str, Any]) -> str:
    lines = [
        "Hole 2 batch visual report",
        SCOPE,
        f"selection={summary['selection']['mode']} generated={summary['selection']['generatedRecords']}",
    ]
    for group, stats in summary["groups"].items():
        lines.extend([
            "",
            f"group={group}",
            f"total={stats['total']}",
            f"executionSuccess={stats['executionSuccess']} executionError={stats['executionError']}",
            f"registrationValid={stats['registrationValid']} registrationInvalid={stats['registrationInvalid']}",
            f"7Valid={stats['featureValid']['7']} 7Invalid={stats['featureInvalid']['7']}",
            f"7EvidenceComplete={stats['evidenceComplete']['7']} auditStatus={json.dumps(stats['evidenceAuditStatus']['7'], sort_keys=True)}",
            f"Phi12.2Valid={stats['featureValid']['Phi12.2']} Phi12.2Invalid={stats['featureInvalid']['Phi12.2']}",
            f"Phi12.2EvidenceComplete={stats['evidenceComplete']['Phi12.2']} auditStatus={json.dumps(stats['evidenceAuditStatus']['Phi12.2'], sort_keys=True)}",
            f"bothMeasurementsValid={stats['bothMeasurementsValid']}",
            f"generatedPreviewCount={stats['generatedPreviewCount']} generatedLabelmeCount={stats['generatedLabelmeCount']}",
            "failureReasons=" + json.dumps(stats["failureReasons"], ensure_ascii=False, sort_keys=True),
        ])
    lines.extend(["", "captureGroupEstimate:", CAPTURE_DISCLAIMER])
    for group, estimate in summary["captureGroupEstimate"]["groups"].items():
        lines.append(
            f"group={group} estimatedCaptureGroupCount="
            f"{estimate['estimatedCaptureGroupCount']} "
            f"complete={estimate['completeGroupCount']} "
            f"incomplete={estimate['incompleteGroupCount']}"
        )
        if estimate["missingSequenceSuffix"]:
            lines.append(
                "missingSequenceSuffix="
                + ",".join(estimate["missingSequenceSuffix"])
            )
        for item in estimate["estimatedGroups"]:
            lines.append(
                f"  captureGroupIndex={item['captureGroupIndex']} "
                f"expected={item['expectedSequenceStart']}-"
                f"{item['expectedSequenceEnd']} "
                f"observed={item['observedCount']} "
                f"complete={item['complete']} "
                f"gaps={','.join(str(value) for value in item['gaps']) or 'none'} "
                f"duplicates="
                f"{','.join(str(value) for value in item['duplicateSequences']) or 'none'}"
            )
    return "\n".join(lines) + "\n"


def render_batch_report(
    *,
    jsonl_path: Path,
    image_root: Path,
    output_dir: Path,
    only_invalid: bool = False,
    frames: list[str] | None = None,
    max_preview_width: int = 1536,
    images_per_product: int = 20,
) -> dict[str, Any]:
    jsonl_path = _require_external(jsonl_path, "batch JSONL")
    image_root = _require_external(image_root, "image root")
    output_dir = _require_external(output_dir, "output directory")
    if not jsonl_path.is_file():
        raise ValueError(f"batch JSONL does not exist: {jsonl_path}")
    if not image_root.is_dir():
        raise ValueError(f"image root does not exist: {image_root}")
    if max_preview_width < 64:
        raise ValueError("max preview width must be at least 64")
    if images_per_product < 1:
        raise ValueError("images per product must be positive")
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError("output directory must be absent or empty")

    records = _load_jsonl(jsonl_path)
    selected, selection_mode = _select_records(
        records, frames or [], only_invalid
    )
    stats_by_group = _group_stats(records)
    capture_estimate, capture_membership = _capture_group_estimate(
        records, images_per_product
    )
    catalog = _image_catalog(image_root)
    output_dir.mkdir(parents=True, exist_ok=True)
    index_rows: list[dict[str, Any]] = []
    for record in selected:
        group, image_name = _identity(record)
        image_path = _resolve_image(record, image_root, catalog)
        item_dir = (
            output_dir / "records" / _safe_component(group)
            / _safe_component(Path(image_name).stem)
        )
        preview_path = item_dir / "preview.jpg"
        prediction_path = item_dir / "prediction.labelme.json"
        with Image.open(image_path) as source:
            original_width, original_height = source.size
        _draw_preview(image_path, record, preview_path, max_preview_width)
        prediction_path.parent.mkdir(parents=True, exist_ok=True)
        prediction_path.write_text(
            json.dumps(
                _prediction_document(
                    record, image_path, original_width, original_height
                ),
                ensure_ascii=False,
                indent=2,
                allow_nan=False,
            ) + "\n",
            encoding="utf-8",
        )
        stats_by_group[group]["generatedPreviewCount"] += 1
        stats_by_group[group]["generatedLabelmeCount"] += 1
        membership = capture_membership.get(_identity(record), {})
        d7_valid = _feature_valid(record, "7")
        phi_valid = _feature_valid(record, "Phi12.2")
        d7_audit = _evidence_audit(record, "7")
        phi_audit = _evidence_audit(record, "Phi12.2")
        index_rows.append({
            "group": group,
            "imageName": image_name,
            "imagePath": str(image_path),
            "sequenceNumber": membership.get("sequenceNumber", ""),
            "executionSuccess": not bool(record.get("executionError")),
            "executionError": record.get("executionError") or "",
            "registrationValid": bool(_registration(record).get("registrationValid", False)),
            "registrationFailureReason": _reason(record, "registration") or "",
            "d7Valid": d7_valid,
            "d7FailureReason": _reason(record, "7") or "",
            "d7LengthPx": _measurement(record, "7", "lengthPx") or "",
            "d7EvidenceComplete": d7_audit["complete"],
            "d7EvidenceAuditStatus": d7_audit["status"],
            "d7EvidenceAuditReason": d7_audit["reason"] or "",
            "phiValid": phi_valid,
            "phiFailureReason": _reason(record, "Phi12.2") or "",
            "phiDiameterPx": _measurement(record, "Phi12.2", "diameterPx") or "",
            "phiEvidenceComplete": phi_audit["complete"],
            "phiEvidenceAuditStatus": phi_audit["status"],
            "phiEvidenceAuditReason": phi_audit["reason"] or "",
            "bothMeasurementsValid": d7_valid and phi_valid,
            "previewJpeg": str(preview_path.relative_to(output_dir)),
            "predictionLabelmeJson": str(prediction_path.relative_to(output_dir)),
            "captureGroupIndex": membership.get("captureGroupIndex", ""),
            "captureGroupComplete": membership.get("captureGroupComplete", False),
        })

    summary = {
        "schemaVersion": SCHEMA_VERSION,
        "scope": SCOPE,
        "runtimeInputs": {
            "batchJsonl": str(jsonl_path),
            "imageRoot": str(image_root),
            "targetTruthRead": False,
        },
        "previewPolicy": {
            "maximumWidthPx": max_preview_width,
            "upscalingAllowed": False,
            "jpegQuality": 82,
        },
        "selection": {
            "mode": selection_mode,
            "onlyInvalid": only_invalid,
            "explicitFrames": frames or [],
            "inputRecords": len(records),
            "generatedRecords": len(index_rows),
        },
        "groups": {
            group: _serialize_group_stats(stats)
            for group, stats in sorted(stats_by_group.items())
        },
        "captureGroupEstimate": capture_estimate,
    }
    _write_index(output_dir / "index.csv", index_rows)
    (output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    (output_dir / "summary.txt").write_text(
        _summary_text(summary), encoding="utf-8"
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jsonl", required=True, type=Path)
    parser.add_argument("--image-root", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--only-invalid", action="store_true")
    parser.add_argument("--frame", action="append", default=[])
    parser.add_argument("--max-preview-width", type=int, default=1536)
    parser.add_argument("--images-per-product", type=int, default=20)
    args = parser.parse_args()
    summary = render_batch_report(
        jsonl_path=args.jsonl,
        image_root=args.image_root,
        output_dir=args.output_dir,
        only_invalid=args.only_invalid,
        frames=args.frame,
        max_preview_width=args.max_preview_width,
        images_per_product=args.images_per_product,
    )
    print(
        f"input={summary['selection']['inputRecords']} "
        f"generated={summary['selection']['generatedRecords']}"
    )
    for group, stats in summary["groups"].items():
        print(
            f"group={group} total={stats['total']} "
            f"registration={stats['registrationValid']} "
            f"7={stats['featureValid']['7']} "
            f"Phi12.2={stats['featureValid']['Phi12.2']} "
            f"previews={stats['generatedPreviewCount']}"
        )
    print(f"report -> {args.output_dir.expanduser().resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
