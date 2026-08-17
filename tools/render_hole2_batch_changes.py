#!/usr/bin/env python3
"""Render external old/new hole-2 batch prediction changes for human review.

The output contains only the two measurement targets (dimension 7 and
Phi12.2).  It is not a part-contour annotation and it never reads target
truth.  Input images, JSONL files, and rendered output must remain external to
the Git worktree.
"""
from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "hole2-batch-prediction-review/1"
COLORS = {"old": (255, 70, 70), "new": (0, 220, 255)}
SCOPE = (
    "Only dimension 7 and Phi12.2 predictions are drawn; "
    "this is not a part contour annotation."
)


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
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"JSONL record {line_number} must be an object: {path}")
            for key in ("group", "imagePath", "executionError", "result"):
                if key not in value:
                    raise ValueError(f"JSONL record {line_number} missing {key}: {path}")
            records.append(value)
    if not records:
        raise ValueError(f"JSONL contains no records: {path}")
    return records


def _record_key(record: dict[str, Any]) -> tuple[str, str]:
    return str(record["group"]), Path(str(record["imagePath"])).name


def _index(records: list[dict[str, Any]], label: str) -> dict[tuple[str, str], dict[str, Any]]:
    indexed: dict[tuple[str, str], dict[str, Any]] = {}
    for record in records:
        key = _record_key(record)
        if key in indexed:
            raise ValueError(
                f"duplicate {label} record identity {key}; group+filename must be unique"
            )
        indexed[key] = record
    return indexed


def _usable_points(value: Any) -> bool:
    return isinstance(value, list) and len(value) >= 2


def _evidence_audit(feature: dict[str, Any], name: str) -> dict[str, Any]:
    if not bool(feature.get("measurementValid", False)):
        return {"complete": False, "status": "not_applicable", "reason": "measurement_invalid"}
    status = feature.get("evidenceAuditStatus")
    if status in {"complete", "partial", "unavailable"}:
        return {
            "complete": bool(feature.get("evidenceComplete", status == "complete")),
            "status": status,
            "reason": feature.get("evidenceAuditReason"),
        }
    target = feature.get("target")
    if not isinstance(target, dict):
        return {"complete": False, "status": "unavailable", "reason": "target_geometry_unavailable"}
    if name == "7":
        evidence = target.get("rawEdgeEvidence", {})
        fitted = target.get("fittedGeometry", {})
        raw = {
            item.get("side") for item in evidence.get("boundaries", [])
            if isinstance(item, dict) and _usable_points(item.get("pointsPx"))
        } if isinstance(evidence, dict) else set()
        lines = {
            item.get("side") for item in fitted.get("boundaries", [])
            if isinstance(item, dict) and _usable_points(item.get("segmentPointsPx"))
        } if isinstance(fitted, dict) else set()
        sides = raw & lines
        if sides == {"A", "B"}:
            return {"complete": True, "status": "complete", "reason": None}
        if sides:
            return {"complete": False, "status": "partial", "reason": "only_one_boundary_evidence_available"}
        return {"complete": False, "status": "unavailable", "reason": "boundary_evidence_unavailable"}
    evidence = target.get("rawEdgeEvidence", {})
    segments = evidence.get("arcSegments", []) if isinstance(evidence, dict) else []
    complete = any(
        isinstance(item, dict) and item.get("side") == "reference_left"
        and _usable_points(item.get("pointsPx")) for item in segments
    )
    return (
        {"complete": True, "status": "complete", "reason": None}
        if complete else
        {"complete": False, "status": "unavailable", "reason": "calibrated_arc_evidence_unavailable"}
    )


def _feature_state(record: dict[str, Any], name: str) -> tuple[Any, ...]:
    result = record.get("result")
    if not isinstance(result, dict):
        return None, None, None, None
    feature = result.get("features", {}).get(name, {})
    audit = _evidence_audit(feature, name)
    return (
        bool(feature.get("measurementValid", False)), feature.get("failureReason"),
        audit["status"], audit["reason"],
    )


def _status_signature(record: dict[str, Any]) -> tuple[Any, ...]:
    result = record.get("result")
    registration = {} if not isinstance(result, dict) else result.get("registration", {})
    return (
        record.get("executionError"),
        bool(registration.get("registrationValid", False)),
        registration.get("failureReason"),
        *_feature_state(record, "7"),
        *_feature_state(record, "Phi12.2"),
    )


def _quality_summary(feature: dict[str, Any]) -> dict[str, Any]:
    quality = feature.get("quality")
    if not isinstance(quality, dict):
        return {}
    selected: dict[str, Any] = {}
    for key, value in quality.items():
        if not (
            key.startswith("candidate_")
            or ".candidate_" in key
            or key == "geometryConsistency"
        ):
            continue
        if isinstance(value, (str, int, float, bool)) or value is None:
            if not isinstance(value, float) or math.isfinite(value):
                selected[key] = value
        elif isinstance(value, list) and len(value) <= 16:
            selected[key] = value
        elif key == "geometryConsistency" and isinstance(value, dict):
            selected[key] = {
                field: value.get(field)
                for field in (
                    "evaluated", "outlier", "rejected", "decision",
                    "absoluteDeviation", "maximumAbsoluteDeviation",
                    "corroboratingEvidence",
                )
                if field in value
            }
    return selected


def _version_metadata(record: dict[str, Any]) -> dict[str, Any]:
    result = record.get("result")
    if not isinstance(result, dict):
        return {
            "algorithmVersion": None,
            "executionError": record.get("executionError"),
            "registration": {"registrationValid": False, "failureReason": None},
            "features": {},
        }
    registration = result.get("registration", {})
    features: dict[str, Any] = {}
    for name in ("7", "Phi12.2"):
        feature = result.get("features", {}).get(name, {})
        features[name] = {
            "measurementValid": bool(feature.get("measurementValid", False)),
            "failureReason": feature.get("failureReason"),
            "sourceDetector": feature.get("sourceDetector"),
            "recoveryPass": feature.get("recoveryPass"),
            "evidenceComplete": _evidence_audit(feature, name)["complete"],
            "evidenceAuditStatus": _evidence_audit(feature, name)["status"],
            "evidenceAuditReason": _evidence_audit(feature, name)["reason"],
            "quality": _quality_summary(feature),
        }
    return {
        "algorithmVersion": result.get("algorithmVersion"),
        "authoritativeReference": result.get("authoritativeReference"),
        "runtimeInputProvenance": result.get("runtimeInputs"),
        "executionError": record.get("executionError"),
        "registration": {
            "registrationValid": bool(registration.get("registrationValid", False)),
            "failureReason": registration.get("failureReason"),
        },
        "features": features,
    }


def _shapes(record: dict[str, Any], version: str) -> list[dict[str, Any]]:
    result = record.get("result")
    if not isinstance(result, dict):
        return []
    shapes: list[dict[str, Any]] = []
    for name in ("7", "Phi12.2"):
        feature = result.get("features", {}).get(name, {})
        if not feature.get("measurementValid") or not isinstance(feature.get("target"), dict):
            continue
        target = feature["target"]
        description = json.dumps({
            "version": version,
            "algorithmVersion": result.get("algorithmVersion"),
            "authoritativeReference": result.get("authoritativeReference"),
            "runtimeInputProvenance": result.get("runtimeInputs"),
            "measurementValid": True,
            "failureReason": feature.get("failureReason"),
            "sourceDetector": feature.get("sourceDetector"),
            "recoveryPass": feature.get("recoveryPass"),
            "evidenceComplete": _evidence_audit(feature, name)["complete"],
            "evidenceAuditStatus": _evidence_audit(feature, name)["status"],
            "evidenceAuditReason": _evidence_audit(feature, name)["reason"],
            "quality": _quality_summary(feature),
        }, ensure_ascii=False, separators=(",", ":"))
        if name == "7":
            fitted = target.get("fittedGeometry", {})
            boundaries = fitted.get("boundaries", []) if isinstance(fitted, dict) else []
            for boundary in boundaries:
                points = boundary.get("segmentPointsPx") if isinstance(boundary, dict) else None
                side = boundary.get("side") if isinstance(boundary, dict) else None
                if isinstance(points, list) and len(points) >= 2 and side in {"A", "B"}:
                    shapes.append({
                        "label": f"{version}:7:boundary:{side}",
                        "points": [[float(value) for value in point] for point in points],
                        "group_id": f"{version}:7", "description": description,
                        "shape_type": "line", "flags": {},
                    })
            legacy_review = (
                fitted.get("legacyReviewBoundaries", [])
                if isinstance(fitted, dict) else []
            )
            for boundary in legacy_review:
                points = boundary.get("segmentPointsPx") if isinstance(boundary, dict) else None
                side = boundary.get("side") if isinstance(boundary, dict) else None
                if isinstance(points, list) and len(points) >= 2 and side in {"A", "B"}:
                    shapes.append({
                        "label": f"{version}:review:7:legacy-boundary:{side}",
                        "points": [[float(value) for value in point] for point in points],
                        "group_id": f"{version}:review:7",
                        "description": description,
                        "shape_type": "line",
                        "flags": {
                            "reviewOnly": True,
                            "equivalentToFormalBoundary": False,
                        },
                    })
            annotation = target.get("measurementAnnotation", {})
            points = annotation.get("pointsPx") if isinstance(annotation, dict) else None
            if len(boundaries) >= 2 and isinstance(points, list) and len(points) == 2:
                shapes.append({
                    "label": f"{version}:7:dimension",
                    "points": [[float(value) for value in point] for point in points],
                    "group_id": f"{version}:7", "description": description,
                    "shape_type": "line", "flags": {},
                })
            elif len(legacy_review) >= 2 and isinstance(points, list) and len(points) == 2:
                shapes.append({
                    "label": f"{version}:review:7:dimension",
                    "points": [[float(value) for value in point] for point in points],
                    "group_id": f"{version}:review:7",
                    "description": description,
                    "shape_type": "line",
                    "flags": {
                        "reviewOnly": True,
                        "equivalentToFormalBoundary": False,
                    },
                })
        else:
            fitted = target.get("fittedGeometry", {})
            center = fitted.get("centerPx") if isinstance(fitted, dict) else None
            radius = fitted.get("radiusPx") if isinstance(fitted, dict) else None
            if (
                isinstance(center, list) and len(center) == 2
                and isinstance(radius, (int, float)) and float(radius) > 0.0
            ):
                center_point = [float(center[0]), float(center[1])]
                shapes.append({
                    "label": f"{version}:Phi12.2:fit-circle",
                    "points": [
                        center_point,
                        [center_point[0] + float(radius), center_point[1]],
                    ],
                    "group_id": f"{version}:Phi12.2",
                    "description": description,
                    "shape_type": "circle",
                    "flags": {"fittedModel": True, "isDetectedContour": False},
                })
            evidence = target.get("rawEdgeEvidence", {})
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
                    "label": f"{version}:Phi12.2:arc:{side}:{index}",
                    "points": [[float(value) for value in point] for point in points],
                    "group_id": f"{version}:Phi12.2", "description": description,
                    "shape_type": "linestrip", "flags": {},
                })
    return shapes


def _shapes_for_version(version: str, record: dict[str, Any]) -> list[dict[str, Any]]:
    """Stable test/tool adapter with version-first argument order."""
    return _shapes(record, version)


def _image_catalog(image_root: Path) -> dict[str, list[Path]]:
    catalog: dict[str, list[Path]] = {}
    for path in image_root.rglob("*"):
        if path.is_file():
            catalog.setdefault(path.name, []).append(path.resolve())
    return catalog


def _resolve_image(record: dict[str, Any], image_root: Path, catalog: dict[str, list[Path]]) -> Path:
    recorded = Path(str(record["imagePath"])).expanduser()
    if recorded.is_file():
        resolved = recorded.resolve()
        try:
            resolved.relative_to(image_root)
        except ValueError:
            pass
        else:
            return resolved
    matches = catalog.get(recorded.name, [])
    if len(matches) != 1:
        raise ValueError(
            f"image filename must resolve uniquely below image root: {recorded.name} "
            f"matches={len(matches)}"
        )
    return matches[0]


def _safe_name(group: str, image_name: str) -> str:
    raw = f"{group}__{Path(image_name).stem}"
    return re.sub(r"[^A-Za-z0-9._-]+", "_", raw).strip("._") or "frame"


def _font(size: int) -> ImageFont.ImageFont:
    try:
        return ImageFont.truetype("DejaVuSans.ttf", size=size)
    except OSError:
        return ImageFont.load_default()


def _compact_quality(metadata: dict[str, Any], name: str) -> str:
    feature = metadata.get("features", {}).get(name, {})
    quality = feature.get("quality", {})
    preferred = (
        "candidate_acceptance_score_contract",
        "candidate_phase_fit_residual_target_px",
        "candidate_phase_edge_points",
        "candidate_phase_polarity_support_fraction",
        "candidate_phase_angle_coverage_fraction",
        "d7.quality.candidate_p1_fit_residual_target_px",
        "d7.quality.candidate_p2_fit_residual_target_px",
        "d7.quality.candidate_failed_sides",
    )
    parts = []
    for key in preferred:
        if key not in quality:
            continue
        value = quality[key]
        if isinstance(value, float):
            value = round(value, 4)
        parts.append(f"{key.split('.')[-1]}={value}")
        if len(parts) == 3:
            break
    return "; ".join(parts) if parts else "quality=n/a"


def _draw_solid_fit_circle(
    draw: ImageDraw.ImageDraw,
    box: tuple[float, float, float, float],
    color: tuple[int, int, int],
    width: int,
) -> None:
    """Draw the fitted circle continuously; it remains a model, not evidence."""
    draw.ellipse(box, outline=color, width=width)


def _draw_prediction(draw: ImageDraw.ImageDraw, record: dict[str, Any], version: str, width: int) -> None:
    color = COLORS[version]
    line_width = max(3, width // 900)
    radius_marker = max(5, width // 600)
    for shape in _shapes(record, version):
        points = [tuple(point) for point in shape["points"]]
        shape_color = (
            (255, 170, 0) if version == "old" else (255, 70, 220)
        ) if shape.get("flags", {}).get("reviewOnly") else color
        if shape["shape_type"] in {"line", "linestrip"}:
            draw.line(points, fill=shape_color, width=line_width)
            marker_points = points if shape["shape_type"] == "line" else (points[0], points[-1])
            for x, y in marker_points:
                draw.ellipse(
                    (x - radius_marker, y - radius_marker, x + radius_marker, y + radius_marker),
                    fill=shape_color,
                )
        elif shape["shape_type"] == "circle" and len(points) == 2:
            center, edge = points
            radius = math.dist(center, edge)
            box = (
                center[0] - radius, center[1] - radius,
                center[0] + radius, center[1] + radius,
            )
            _draw_solid_fit_circle(
                draw, box, color, max(2, line_width - 1)
            )


def _render_overlay(image_path: Path, old: dict[str, Any], new: dict[str, Any], output: Path) -> None:
    image = Image.open(image_path).convert("RGB")
    draw = ImageDraw.Draw(image)
    _draw_prediction(draw, old, "old", image.width)
    _draw_prediction(draw, new, "new", image.width)
    old_meta = _version_metadata(old)
    new_meta = _version_metadata(new)
    lines = [SCOPE, "RED=old  CYAN=new"]
    for version, metadata in (("old", old_meta), ("new", new_meta)):
        registration = metadata["registration"]
        lines.append(
            f"{version} version={metadata['algorithmVersion']} "
            f"registrationValid={registration['registrationValid']} "
            f"reason={registration['failureReason']}"
        )
        for name in ("7", "Phi12.2"):
            feature = metadata.get("features", {}).get(name, {})
            lines.append(
                f"{version} {name} valid={feature.get('measurementValid')} "
                f"evidence={feature.get('evidenceAuditStatus')} "
                f"reason={feature.get('failureReason')} "
                f"{_compact_quality(metadata, name)}"
            )
    font_size = max(13, min(30, image.width // 180))
    font = _font(font_size)
    line_height = font_size + 5
    panel_height = line_height * len(lines) + 12
    draw.rectangle((0, 0, image.width, panel_height), fill=(0, 0, 0))
    y = 6
    for line in lines:
        draw.text((8, y), line, fill=(245, 245, 245), font=font)
        y += line_height
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output)


def _labelme_document(
    image_path: Path,
    width: int,
    height: int,
    old: dict[str, Any],
    new: dict[str, Any],
) -> dict[str, Any]:
    return {
        "version": "5.5.0",
        "flags": {},
        "shapes": _shapes(old, "old") + _shapes(new, "new"),
        "imagePath": str(image_path),
        "imageData": None,
        "imageHeight": height,
        "imageWidth": width,
        "reviewMetadata": {
            "schemaVersion": SCHEMA_VERSION,
            "scope": SCOPE,
            "colors": {"old": "red", "new": "cyan"},
            "old": _version_metadata(old),
            "new": _version_metadata(new),
        },
    }


def _matches_selector(key: tuple[str, str], selectors: set[str]) -> bool:
    group, name = key
    stem = Path(name).stem
    return bool({name, stem, f"{group}/{name}", f"{group}/{stem}"} & selectors)


def render_review(
    *,
    old_jsonl: Path,
    new_jsonl: Path,
    image_root: Path,
    output_dir: Path,
    frames: list[str] | None = None,
) -> dict[str, Any]:
    old_jsonl = _require_external(old_jsonl, "old JSONL")
    new_jsonl = _require_external(new_jsonl, "new JSONL")
    image_root = _require_external(image_root, "image root")
    output_dir = _require_external(output_dir, "output directory")
    if not image_root.is_dir():
        raise ValueError(f"image root does not exist: {image_root}")
    old_index = _index(_load_jsonl(old_jsonl), "old")
    new_index = _index(_load_jsonl(new_jsonl), "new")
    common = sorted(set(old_index) & set(new_index))
    if not common:
        raise ValueError("old and new JSONL have no matching group+filename records")
    selectors = {value.strip() for value in frames or [] if value.strip()}
    if selectors:
        selected = [key for key in common if _matches_selector(key, selectors)]
        unmatched = sorted(
            selector for selector in selectors
            if not any(_matches_selector(key, {selector}) for key in common)
        )
        if unmatched:
            raise ValueError("explicit frame selector did not match: " + ",".join(unmatched))
        selection_mode = "explicit_frames"
    else:
        selected = [
            key for key in common
            if _status_signature(old_index[key]) != _status_signature(new_index[key])
        ]
        selection_mode = "status_changes"
    catalog = _image_catalog(image_root)
    output_dir.mkdir(parents=True, exist_ok=True)
    items: list[dict[str, Any]] = []
    for key in selected:
        old = old_index[key]
        new = new_index[key]
        image_path = _resolve_image(new, image_root, catalog)
        item_dir = output_dir / _safe_name(*key)
        overlay_path = item_dir / "old-new-overlay.png"
        labelme_path = item_dir / "old-new-predictions.labelme.json"
        _render_overlay(image_path, old, new, overlay_path)
        with Image.open(image_path) as image:
            width, height = image.size
        document = _labelme_document(image_path, width, height, old, new)
        labelme_path.parent.mkdir(parents=True, exist_ok=True)
        labelme_path.write_text(
            json.dumps(document, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
            encoding="utf-8",
        )
        items.append({
            "group": key[0],
            "imageName": key[1],
            "imagePath": str(image_path),
            "statusChanged": _status_signature(old) != _status_signature(new),
            "overlayPng": str(overlay_path.relative_to(output_dir)),
            "predictionLabelmeJson": str(labelme_path.relative_to(output_dir)),
            "old": _version_metadata(old),
            "new": _version_metadata(new),
        })
    summary = {
        "schemaVersion": SCHEMA_VERSION,
        "scope": SCOPE,
        "oldJsonl": str(old_jsonl),
        "newJsonl": str(new_jsonl),
        "imageRoot": str(image_root),
        "selectionMode": selection_mode,
        "matchedFrames": len(common),
        "statusChangedFrames": sum(
            _status_signature(old_index[key]) != _status_signature(new_index[key])
            for key in common
        ),
        "renderedFrames": len(items),
        "unmatchedOldFrames": len(set(old_index) - set(new_index)),
        "unmatchedNewFrames": len(set(new_index) - set(old_index)),
        "items": items,
    }
    (output_dir / "review-summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--old-jsonl", required=True, type=Path)
    parser.add_argument("--new-jsonl", required=True, type=Path)
    parser.add_argument("--image-root", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument(
        "--frame",
        action="append",
        default=[],
        help="Render a named frame even when status is unchanged; repeatable.",
    )
    args = parser.parse_args()
    summary = render_review(
        old_jsonl=args.old_jsonl,
        new_jsonl=args.new_jsonl,
        image_root=args.image_root,
        output_dir=args.output_dir,
        frames=args.frame,
    )
    print(
        f"matched={summary['matchedFrames']} "
        f"changed={summary['statusChangedFrames']} "
        f"rendered={summary['renderedFrames']}"
    )
    print(f"review -> {args.output_dir.expanduser().resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
