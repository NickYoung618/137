#!/usr/bin/env python3
"""Render path-safe candidate review artifacts from slot-pose batch results."""

from __future__ import annotations

import argparse
import csv
import itertools
import json
import math
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.dataset_common import safe_relative_path, sha256_file, write_json


ROLE_COLORS = {
    "datum_primary": "#38d66b",
    "datum_secondary": "#35c7ff",
    "target_left": "#ff5d73",
}


def load_results(path: Path) -> list[dict[str, Any]]:
    content = path.read_text(encoding="utf-8").strip()
    if not content:
        return []
    if content.startswith("["):
        payload = json.loads(content)
        if not isinstance(payload, list):
            raise ValueError("result JSON array is required")
        return payload
    if content.startswith("{") and "\n" not in content:
        return [json.loads(content)]
    return [json.loads(line) for line in content.splitlines() if line.strip()]


def _diagnostic_confidence(diagnostics: dict[str, Any]) -> float | None:
    components = diagnostics.get("quality", {}).get("confidenceComponents")
    if not isinstance(components, list) or not components:
        return None
    values = [float(value) for value in components]
    return min(values) if all(math.isfinite(value) for value in values) else None


def _signed_delta(value: float, reference: float) -> float:
    return (float(value) - float(reference) + 180.0) % 360.0 - 180.0


def _role_hypotheses(diagnostics: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    candidates = diagnostics.get("grooveCandidates")
    if candidates is None:
        candidates = diagnostics.get("candidates") or []
    role_config = diagnostics.get("quality", {}).get("thresholds", {}).get("role_assignment", {})
    nominal = role_config.get("drawing_nominal_angle_deg")
    ray_hypotheses: list[dict[str, Any]] = []
    for datum, target in itertools.permutations(candidates, 2):
        signed = _signed_delta(float(target["centerDeg"]), float(datum["centerDeg"]))
        included = abs(signed)
        ray_hypotheses.append({
            "datumCandidateId": datum["candidateId"],
            "targetCandidateId": target["candidateId"],
            "clockwiseAngleDeg": (float(target["centerDeg"]) - float(datum["centerDeg"])) % 360.0,
            "shortestSignedAngleDeg": signed,
            "includedAngleDeg": included,
            "drawingNominalDeviationDeg": abs(included - float(nominal)) if nominal is not None else None,
            "authoritative": False,
        })
    ray_hypotheses.sort(key=lambda item: (
        float(item["drawingNominalDeviationDeg"]) if item["drawingNominalDeviationDeg"] is not None else 999.0,
        item["datumCandidateId"], item["targetCandidateId"],
    ))

    axis_hypotheses: list[dict[str, Any]] = []
    for first, second in itertools.combinations(candidates, 2):
        separation = abs(_signed_delta(float(second["centerDeg"]), float(first["centerDeg"])))
        opposition_error = abs(180.0 - separation)
        midpoint = (float(first["centerDeg"]) + _signed_delta(float(second["centerDeg"]), float(first["centerDeg"])) / 2.0) % 360.0
        for target in candidates:
            if target["candidateId"] in {first["candidateId"], second["candidateId"]}:
                continue
            included = min(
                abs(_signed_delta(float(target["centerDeg"]), midpoint)),
                abs(_signed_delta(float(target["centerDeg"]), (midpoint + 180.0) % 360.0)),
            )
            axis_hypotheses.append({
                "datumCandidateIds": [first["candidateId"], second["candidateId"]],
                "targetCandidateId": target["candidateId"],
                "datumAxisAzimuthDegModulo180": midpoint % 180.0,
                "datumOppositionErrorDeg": opposition_error,
                "includedAngleDeg": included,
                "drawingNominalDeviationDeg": abs(included - float(nominal)) if nominal is not None else None,
                "authoritative": False,
            })
    axis_hypotheses.sort(key=lambda item: (
        float(item["datumOppositionErrorDeg"]),
        float(item["drawingNominalDeviationDeg"]) if item["drawingNominalDeviationDeg"] is not None else 999.0,
    ))
    return ray_hypotheses, axis_hypotheses


def build_review_record(manifest_item: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    diagnostics = result.get("diagnostics") or {}
    assignment = diagnostics.get("roleAssignment") or {}
    selected = assignment.get("selectedRoleCandidateIds")
    role_status = "unique_diagnostic_hypothesis" if assignment.get("unique") and selected else (
        "ambiguous_or_rejected" if assignment else "not_available"
    )
    ray_hypotheses, axis_hypotheses = _role_hypotheses(diagnostics)
    raw_candidates = diagnostics.get("rawCandidates") or diagnostics.get("candidates") or []
    groove_recognition = diagnostics.get("grooveRecognition") or {}
    single_groove_pose = diagnostics.get("singleGroovePose")
    return {
        "imageId": manifest_item["imageId"],
        "relativePath": manifest_item["relativePath"],
        "imageSha256": manifest_item["sha256"],
        "datasetClass": manifest_item.get("datasetClass"),
        "result": {
            "valid": bool(result.get("result", {}).get("valid", False)),
            "signedRelativeRotationDeg": result.get("result", {}).get("signedRelativeRotationDeg"),
            "errorCode": (result.get("error") or {}).get("code"),
            "errorStage": (result.get("error") or {}).get("stage"),
        },
        "face": diagnostics.get("face"),
        "physicalOuterCircle": diagnostics.get("physicalOuterCircle"),
        "candidateSummary": diagnostics.get("candidateSummary"),
        "candidates": raw_candidates,
        "rawCandidates": raw_candidates,
        "grooveRecognition": groove_recognition,
        "grooveCandidates": diagnostics.get("grooveCandidates") or [],
        "singleGroovePose": single_groove_pose,
        "roleSuggestion": {
            "status": role_status,
            "selectedRoleCandidateIds": selected,
            "selectedRoleAzimuthsDeg": assignment.get("selectedRoleAzimuthsDeg"),
            "bestScore": assignment.get("bestScore"),
            "secondBestScore": assignment.get("secondBestScore"),
            "scoreMargin": assignment.get("scoreMargin"),
            "failedChecks": assignment.get("failedChecks") or [],
            "authoritative": False,
            "requiresFieldConfirmation": True,
        },
        "singleRayRoleHypotheses": ray_hypotheses,
        "opposedDatumAxisHypotheses": axis_hypotheses,
        "diagnosticConfidence": _diagnostic_confidence(diagnostics),
        "drawingAngle": assignment.get("drawingAngle"),
        "angularProfile": diagnostics.get("angularProfile"),
        "polarRotationDeg": (diagnostics.get("slot") or {}).get("polarRotationDeg"),
        "elapsedMs": diagnostics.get("elapsedMs"),
        "failClosed": not bool(result.get("result", {}).get("valid", False)),
    }


def _point(center: tuple[float, float], radius: float, angle_deg: float) -> tuple[float, float]:
    angle = math.radians(angle_deg)
    return center[0] + radius * math.cos(angle), center[1] + radius * math.sin(angle)


def render_overlay(image_path: Path, record: dict[str, Any], output_path: Path) -> None:
    with Image.open(image_path) as source:
        image = source.convert("RGB")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=max(18, image.width // 180))
    face = record.get("face") or {}
    if all(isinstance(face.get(key), (int, float)) for key in ("centerX", "centerY", "radiusPx")):
        center = float(face["centerX"]), float(face["centerY"])
        radius = float(face["radiusPx"])
        width = max(5, image.width // 900)
        bounds = (center[0] - radius, center[1] - radius, center[0] + radius, center[1] + radius)
        for start in range(0, 360, 12):
            draw.arc(bounds, start=start, end=start + 6, fill="#ff9f43", width=width)
        physical_diagnostics = record.get("physicalOuterCircle") or {}
        physical = physical_diagnostics.get("physicalCircle") if physical_diagnostics.get("status") == "accepted" else None
        if physical and all(isinstance(physical.get(key), (int, float)) for key in ("centerX", "centerY", "radiusPx")):
            center = float(physical["centerX"]), float(physical["centerY"])
            radius = float(physical["radiusPx"])
            draw.ellipse(
                (center[0] - radius, center[1] - radius, center[0] + radius, center[1] + radius),
                outline="#35c7ff", width=width,
            )
        selected = (record.get("roleSuggestion") or {}).get("selectedRoleCandidateIds") or {}
        role_by_candidate = {candidate_id: role for role, candidate_id in selected.items()}
        assessments = {
            item["candidateId"]: item
            for item in (record.get("grooveRecognition") or {}).get("assessments") or []
        }
        for candidate in record.get("candidates") or []:
            candidate_id = str(candidate["candidateId"])
            role = role_by_candidate.get(candidate_id)
            assessment = assessments.get(candidate_id)
            color = ROLE_COLORS.get(role, "#ffe14f" if assessment is None else ("#38d66b" if assessment.get("accepted") else "#ff5d73"))
            angle = float(candidate["centerDeg"])
            endpoint = _point(center, radius, angle)
            draw.line((center, endpoint), fill=color, width=width)
            groove_label = "" if assessment is None else f" G={float(assessment['grooveScore']):.2f} {'ACCEPT' if assessment.get('accepted') else 'REJECT'}"
            label = candidate_id if role is None else f"{candidate_id} / {role}"
            draw.text(endpoint, f" {label} {angle:.2f}deg{groove_label}", fill=color, font=font, stroke_width=2, stroke_fill="black")
        single_pose = record.get("singleGroovePose") or {}
        measurement = single_pose.get("imageMeasurement") or {}
        radial_axis = measurement.get("radialAxis") or {}
        axis_from, axis_to = radial_axis.get("from"), radial_axis.get("to")
        if single_pose.get("geometryValid") and isinstance(axis_from, dict) and isinstance(axis_to, dict):
            draw.line(
                (axis_from["x"], axis_from["y"], axis_to["x"], axis_to["y"]),
                fill="#ff5dce", width=width * 2,
            )
    error = record["result"].get("errorCode") or "NONE"
    count = len(record.get("candidates") or [])
    groove_count = len(record.get("grooveCandidates") or [])
    draw.rectangle((0, 0, min(image.width, 2400), max(110, image.height // 18)), fill="#111111")
    single_pose = record.get("singleGroovePose") or {}
    single_measurement = single_pose.get("imageMeasurement") or {}
    image_azimuth = single_measurement.get("azimuthDeg")
    single_text = "" if image_azimuth is None else f" image-up-cw={float(image_azimuth):.2f}deg"
    draw.text(
        (18, 12),
        f"{record['imageId']}  raw={count} grooves={groove_count}{single_text}  error={error}",
        fill="white", font=font,
    )
    draw.text(
        (18, 56), "orange dashed=alignment prior; cyan solid=gyj physical-circle result",
        fill="white", font=font,
    )
    image.thumbnail((1800, 1200), Image.Resampling.LANCZOS)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path, quality=90)


def render_contact_sheet(overlays: list[tuple[str, Path]], output_path: Path) -> None:
    if not overlays:
        return
    tile_width, tile_height = 600, 430
    columns = min(3, len(overlays))
    rows = math.ceil(len(overlays) / columns)
    sheet = Image.new("RGB", (columns * tile_width, rows * tile_height), "#191919")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default(size=18)
    for index, (image_id, path) in enumerate(overlays):
        with Image.open(path) as source:
            tile = source.convert("RGB")
        tile.thumbnail((tile_width, tile_height - 34), Image.Resampling.LANCZOS)
        x = (index % columns) * tile_width
        y = (index // columns) * tile_height
        sheet.paste(tile, (x, y + 34))
        draw.text((x + 8, y + 7), image_id, fill="white", font=font)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output_path, quality=88)


def render_review(manifest: dict[str, Any], results: list[dict[str, Any]], data_root: Path, output_dir: Path) -> dict[str, Any]:
    result_by_task = {str(item.get("taskId")): item for item in results}
    dataset_id = str(manifest.get("datasetId", "dataset"))
    records: list[dict[str, Any]] = []
    overlays: list[tuple[str, Path]] = []
    output_dir.mkdir(parents=True, exist_ok=True)
    for item in manifest.get("images", []):
        task_id = f"{dataset_id}:{item['imageId']}"
        result = result_by_task.get(task_id)
        if result is None and len(results) == 1 and len(manifest.get("images", [])) == 1:
            result = results[0]
        if result is None:
            raise ValueError(f"missing batch result for {task_id}")
        relative = safe_relative_path(str(item["relativePath"]))
        image_path = data_root.resolve() / relative
        if sha256_file(image_path) != item["sha256"]:
            raise ValueError(f"image hash mismatch for {relative.as_posix()}")
        record = build_review_record(item, result)
        records.append(record)
        overlay_path = output_dir / "overlays" / f"{len(records):04d}.jpg"
        render_overlay(image_path, record, overlay_path)
        overlays.append((str(item["imageId"]), overlay_path))

    failures = Counter(record["result"]["errorCode"] or "NONE" for record in records)
    single_valid_count = sum(
        1 for record in records if (record.get("singleGroovePose") or {}).get("geometryValid") is True
    )
    image_azimuth_count = sum(
        1 for record in records
        if isinstance(((record.get("singleGroovePose") or {}).get("imageMeasurement") or {}).get("azimuthDeg"), (int, float))
    )
    datum_blocked_count = sum(
        1 for record in records if record["result"]["errorCode"] == "DATUM_DEFINITION_UNCONFIRMED"
    )
    summary = {
        "schemaVersion": "slot-pose-review/1",
        "datasetId": dataset_id,
        "imageCount": len(records),
        "candidateBearingConvention": "image +x is 0 deg; clockwise is positive because image y increases downward",
        "roleSuggestionsAreAuthoritative": False,
        "failureCounts": dict(sorted(failures.items())),
        "singleGrooveGeometryValidCount": single_valid_count,
        "imageGrooveAzimuthAvailableCount": image_azimuth_count,
        "mechanicalGuidanceBlockedByDatumCount": datum_blocked_count,
        "records": records,
    }
    write_json(output_dir / "review.json", summary)
    with (output_dir / "candidates.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=[
            "image_id", "relative_path", "candidate_id", "rank", "center_deg", "half_width_deg",
            "prominence", "start_deg", "end_deg", "wraps_boundary", "groove_score", "accepted",
            "rejection_reasons", "radial_depth_px", "tangential_width_px", "paired_edge_support",
            "contour_continuity", "threshold_version", "suggested_role", "authoritative",
        ])
        writer.writeheader()
        for record in records:
            selected = record["roleSuggestion"].get("selectedRoleCandidateIds") or {}
            role_by_candidate = {candidate_id: role for role, candidate_id in selected.items()}
            assessments = {
                item["candidateId"]: item
                for item in (record.get("grooveRecognition") or {}).get("assessments") or []
            }
            for candidate in record["candidates"]:
                assessment = assessments.get(candidate["candidateId"]) or {}
                writer.writerow({
                    "image_id": record["imageId"], "relative_path": record["relativePath"],
                    "candidate_id": candidate["candidateId"], "rank": candidate["rank"],
                    "center_deg": candidate["centerDeg"], "half_width_deg": candidate["halfWidthDeg"],
                    "prominence": candidate["prominence"], "start_deg": candidate["startDeg"],
                    "end_deg": candidate["endDeg"], "wraps_boundary": candidate["wrapsBoundary"],
                    "groove_score": assessment.get("grooveScore"), "accepted": assessment.get("accepted"),
                    "rejection_reasons": "|".join(assessment.get("rejectionReasons") or []),
                    "radial_depth_px": assessment.get("radialDepthPx"),
                    "tangential_width_px": assessment.get("tangentialWidthPx"),
                    "paired_edge_support": assessment.get("pairedEdgeSupport"),
                    "contour_continuity": assessment.get("contourContinuity"),
                    "threshold_version": assessment.get("thresholdVersion"),
                    "suggested_role": role_by_candidate.get(candidate["candidateId"]), "authoritative": False,
                })
    with (output_dir / "failures.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=[
            "image_id", "relative_path", "error_code", "error_stage", "candidate_count", "groove_count",
            "single_groove_status", "image_azimuth_deg", "role_status",
        ])
        writer.writeheader()
        for record in records:
            if record["result"]["valid"]:
                continue
            writer.writerow({
                "image_id": record["imageId"],
                "relative_path": record["relativePath"],
                "error_code": record["result"]["errorCode"],
                "error_stage": record["result"]["errorStage"],
                "candidate_count": len(record["candidates"]),
                "groove_count": len(record["grooveCandidates"]),
                "single_groove_status": (record.get("singleGroovePose") or {}).get("status"),
                "image_azimuth_deg": (
                    ((record.get("singleGroovePose") or {}).get("imageMeasurement") or {}).get("azimuthDeg")
                ),
                "role_status": record["roleSuggestion"]["status"],
            })
    render_contact_sheet(overlays, output_dir / "contact-sheet.jpg")
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--results", required=True, type=Path)
    parser.add_argument("--data-root", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        summary = render_review(manifest, load_results(args.results), args.data_root, args.output_dir)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(f"Wrote {args.output_dir}: images={summary['imageCount']}, failures={summary['failureCounts']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
