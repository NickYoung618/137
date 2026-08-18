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


def _guidance_record(payload: dict[str, Any], *, nested_plc: bool = False) -> dict[str, Any]:
    plc = (payload.get("plcExecution") or {}) if nested_plc else payload
    return {
        "detectionStatus": payload.get("detectionStatus"),
        "guidanceStatus": payload.get("guidanceStatus"),
        "currentAngleDeg": payload.get("currentAngleDeg"),
        "targetAngleDeg": payload.get("targetAngleDeg"),
        "toleranceDeg": payload.get("toleranceDeg"),
        "correctionRawDeg": payload.get("correctionRawDeg"),
        "correctionDeg": payload.get("correctionDeg"),
        "imageFrameCorrectionDeg": payload.get("imageFrameCorrectionDeg"),
        "rotationDirection": payload.get("rotationDirection"),
        "withinTolerance": payload.get("withinTolerance"),
        "plcExecutionStatus": plc.get("status") if nested_plc else plc.get("plcExecutionStatus"),
        "mechanicalCorrectionDeg": plc.get("mechanicalCorrectionDeg"),
        "plcCommand": plc.get("plcCommand"),
    }


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
    groove_refinement = diagnostics.get("grooveRefinement")
    datum_measurement = (single_groove_pose or {}).get("datumMeasurement") or {}
    target_assessment = (single_groove_pose or {}).get("targetAssessment") or {}
    intermediate_guidance = (single_groove_pose or {}).get("guidance") or {}
    final_result = result.get("result") or {}
    position = datum_measurement.get("position") or {}
    y_down_target = {
        "measuredDeg": datum_measurement.get("measuredFromPositiveYClockwiseDeg"),
        "horizontalPosition": position.get("horizontal"),
        "verticalPosition": position.get("vertical"),
        "positionGatePassed": target_assessment.get("positionGatePassed"),
        "angleTolerancePassed": target_assessment.get("angleTolerancePassed"),
        "toleranceStatus": target_assessment.get("toleranceStatus"),
        "imageFrameCorrectionDeg": target_assessment.get("imageFrameCorrectionDeg"),
        "mechanicalCorrectionDeg": target_assessment.get("mechanicalCorrectionDeg"),
        "plcBlocked": "PLC_MAPPING_UNCONFIRMED" in (target_assessment.get("blockers") or []),
    }
    intermediate_guidance_record = _guidance_record(intermediate_guidance, nested_plc=True)
    is_v3_final = final_result.get("detectionStatus") in {"DETECTED", "DETECTION_FAILED"}
    guidance_record = _guidance_record(final_result) if is_v3_final else intermediate_guidance_record
    return {
        "imageId": manifest_item["imageId"],
        "relativePath": manifest_item["relativePath"],
        "imageSha256": manifest_item["sha256"],
        "datasetClass": manifest_item.get("datasetClass"),
        "result": {
            "valid": bool(final_result.get("valid", False)),
            "signedRelativeRotationDeg": final_result.get("signedRelativeRotationDeg"),
            "errorCode": (result.get("error") or {}).get("code"),
            "errorStage": (result.get("error") or {}).get("stage"),
        },
        "face": diagnostics.get("face"),
        "circleLocalization": diagnostics.get("circleLocalization"),
        "physicalOuterCircle": diagnostics.get("physicalOuterCircle"),
        "candidateSummary": diagnostics.get("candidateSummary"),
        "candidates": raw_candidates,
        "rawCandidates": raw_candidates,
        "grooveRecognition": groove_recognition,
        "grooveCandidates": diagnostics.get("grooveCandidates") or [],
        "grooveRefinement": groove_refinement,
        "grooveShadowSourceDiscrimination": diagnostics.get("grooveShadowSourceDiscrimination"),
        "singleGroovePose": single_groove_pose,
        "yDownTargetDiagnostic": y_down_target,
        "guidance": guidance_record,
        "guidanceAuthority": "final_result" if is_v3_final else "legacy_intermediate_fallback",
        "intermediateGuidance": intermediate_guidance_record,
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
        "failClosed": not bool(final_result.get("valid", False)),
    }


def _point(center: tuple[float, float], radius: float, angle_deg: float) -> tuple[float, float]:
    angle = math.radians(angle_deg)
    return center[0] + radius * math.cos(angle), center[1] + radius * math.sin(angle)


def _draw_sidewall_evidence(
    draw: ImageDraw.ImageDraw, side: dict[str, Any], *, inlier_color: str, width: int,
) -> None:
    """Draw v2 detected/support/rejected points without hiding rejected evidence."""
    detected = side.get("detectedPoints") or side.get("points") or []
    supports = side.get("points") or []
    rejected = side.get("rejectedPoints") or []
    point_radius = max(2, width)
    for point in detected:
        x, y = map(float, point)
        draw.ellipse((x - point_radius, y - point_radius, x + point_radius, y + point_radius), fill="#35c7ff")
    for point in rejected:
        x, y = map(float, point)
        draw.line((x - point_radius, y - point_radius, x + point_radius, y + point_radius), fill="#ff5d73", width=width)
        draw.line((x - point_radius, y + point_radius, x + point_radius, y - point_radius), fill="#ff5d73", width=width)
    for point in supports:
        x, y = map(float, point)
        draw.ellipse((x - point_radius, y - point_radius, x + point_radius, y + point_radius), fill=inlier_color)
    line = side.get("line") or {}
    if len(supports) >= 2 and all(isinstance(line.get(key), (int, float)) for key in ("a", "b", "c")):
        a, b = float(line["a"]), float(line["b"])
        direction = (-b, a)
        projections = [(float(point[0]) * direction[0] + float(point[1]) * direction[1], point) for point in supports]
        endpoints = [min(projections)[1], max(projections)[1]]
        draw.line((*map(float, endpoints[0]), *map(float, endpoints[1])), fill="#ffffff", width=max(width, 2))


def render_overlay(image_path: Path, record: dict[str, Any], output_path: Path) -> None:
    with Image.open(image_path) as source:
        image = source.convert("RGB")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=max(18, image.width // 180))
    localization = record.get("circleLocalization") or {}
    width = max(5, image.width // 900)
    selected_circle_candidate = localization.get("selectedCandidateId")
    for proposal in localization.get("componentProposals") or []:
        bbox = proposal.get("bboxNormalized")
        if not isinstance(bbox, list) or len(bbox) != 4:
            continue
        bounds = (
            float(bbox[0]) * image.width, float(bbox[1]) * image.height,
            float(bbox[2]) * image.width, float(bbox[3]) * image.height,
        )
        color = "#ffe14f" if proposal.get("status") == "eligible" else "#ff5d73"
        draw.rectangle(bounds, outline=color, width=width)
        draw.text(
            (bounds[0], bounds[1]),
            f" {proposal.get('proposalId')} {proposal.get('status')}",
            fill=color, font=font, stroke_width=2, stroke_fill="black",
        )
    for candidate in localization.get("circleCandidates") or []:
        circle = candidate.get("coarsePhysicalCircle")
        if not isinstance(circle, dict):
            continue
        center_x, center_y, circle_radius = map(float, (
            circle["centerX"], circle["centerY"], circle["radiusPx"],
        ))
        color = "#9b7bff" if candidate.get("candidateId") == selected_circle_candidate else "#ff5d73"
        draw.ellipse(
            (center_x - circle_radius, center_y - circle_radius, center_x + circle_radius, center_y + circle_radius),
            outline=color, width=width,
        )
        draw.text(
            (center_x - circle_radius, center_y),
            f" {candidate.get('candidateId')} rank={candidate.get('rank')} score={candidate.get('score')}",
            fill=color, font=font, stroke_width=2, stroke_fill="black",
        )
    face = record.get("face") or {}
    if all(isinstance(face.get(key), (int, float)) for key in ("centerX", "centerY", "radiusPx")):
        center = float(face["centerX"]), float(face["centerY"])
        radius = float(face["radiusPx"])
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
        source_diagnostic = record.get("grooveShadowSourceDiscrimination") or {}
        source_by_candidate = {
            str(item.get("candidateId")): item
            for item in source_diagnostic.get("candidateEvidence") or []
            if isinstance(item, dict)
        }
        for candidate in record.get("candidates") or []:
            candidate_id = str(candidate["candidateId"])
            role = role_by_candidate.get(candidate_id)
            assessment = assessments.get(candidate_id)
            source_item = source_by_candidate.get(candidate_id) or {}
            source_color = {
                "REAL_GROOVE_SURVIVOR": "#38d66b",
                "NON_GROOVE_SOURCE_REJECTED": "#ff5dce",
                "MIXED_OR_OCCLUDED_EVIDENCE": "#ff5d73",
                "INDETERMINATE": "#ffe14f",
            }.get(source_item.get("sourceDisposition"))
            color = source_color or ROLE_COLORS.get(role, "#ffe14f" if assessment is None else ("#38d66b" if assessment.get("accepted") else "#ff5d73"))
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
        refinement = record.get("grooveRefinement") or {}
        for side_name, color in (("startSide", "#38d66b"), ("endSide", "#ffe14f")):
            side = refinement.get(side_name) or {}
            if side:
                _draw_sidewall_evidence(draw, side, inlier_color=color, width=width)
        if refinement.get("status") == "accepted":
            for point in refinement.get("outerCircleIntersections") or []:
                x, y = float(point["x"]), float(point["y"])
                point_radius = max(6, width * 2)
                draw.ellipse((x - point_radius, y - point_radius, x + point_radius, y + point_radius), outline="#ffffff", width=width)
        target_diagnostic = record.get("yDownTargetDiagnostic") or {}
        guidance = record.get("guidance") or {}
        if target_diagnostic.get("measuredDeg") is not None or guidance.get("currentAngleDeg") is not None:
            datum_endpoint = _point(center, radius, 90.0)
            target_endpoint = _point(center, radius, 175.0)
            draw.line((center, datum_endpoint), fill="#ffe14f", width=width)
            draw.line((center, target_endpoint), fill="#9b7bff", width=width)
    error = record["result"].get("errorCode") or "NONE"
    count = len(record.get("candidates") or [])
    groove_count = len(record.get("grooveCandidates") or [])
    draw.rectangle((0, 0, min(image.width, 2400), max(110, image.height // 18)), fill="#111111")
    single_pose = record.get("singleGroovePose") or {}
    single_measurement = single_pose.get("imageMeasurement") or {}
    image_azimuth = single_measurement.get("azimuthDeg")
    single_text = "" if image_azimuth is None else f" image-up-cw={float(image_azimuth):.2f}deg"
    target_diagnostic = record.get("yDownTargetDiagnostic") or {}
    guidance = record.get("guidance") or {}
    measured_y = guidance.get("currentAngleDeg", target_diagnostic.get("measuredDeg"))
    if guidance.get("detectionStatus") is not None:
        correction = guidance.get("imageFrameCorrectionDeg")
        correction_text = "N/A" if correction is None else f"{float(correction):+.3f}deg"
        target_text = (
            f" detection={guidance.get('detectionStatus')} guidance={guidance.get('guidanceStatus')}"
            f" current={'N/A' if measured_y is None else f'{float(measured_y):.3f}deg'}"
            f" target={guidance.get('targetAngleDeg')}+/-{guidance.get('toleranceDeg')}deg"
            f" correction={correction_text} direction={guidance.get('rotationDirection')}"
        )
    else:
        target_text = "" if measured_y is None else (
            f" y-down={float(measured_y):.2f}deg target={target_diagnostic.get('toleranceStatus')}"
        )
    source_diagnostic = record.get("grooveShadowSourceDiscrimination") or {}
    source_text = ""
    if source_diagnostic:
        source_text = (
            f" source={source_diagnostic.get('classification')}"
            f" status={source_diagnostic.get('status')}"
            f" failed={'|'.join(source_diagnostic.get('failedChecks') or [])}"
        )
    draw.text(
        (18, 12),
        f"{record['imageId']}  raw={count} grooves={groove_count}{single_text}{target_text}  error={error}",
        fill="white", font=font,
    )
    draw.text(
        (18, 56),
        "cyan=all side points; green=survivor; magenta=non-groove; red=mixed/rejected; white=line/intersection"
        + source_text,
        fill="white", font=font,
    )
    image.thumbnail((1800, 1200), Image.Resampling.LANCZOS)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path, quality=90)


def contact_sheet_layout(
    image_count: int, *, tile_width: int = 600, tile_height: int = 430, max_dimension: int = 65_000,
) -> tuple[int, int, int, int]:
    if image_count <= 0:
        return 0, 0, 0, 0
    minimum_columns = max(1, math.ceil(image_count * tile_height / max_dimension))
    maximum_columns = max(1, max_dimension // tile_width)
    columns = min(maximum_columns, max(3 if image_count >= 3 else image_count, minimum_columns))
    rows = math.ceil(image_count / columns)
    if rows * tile_height > max_dimension:
        raise ValueError(f"contact sheet cannot fit {image_count} images within JPEG dimension limit")
    return columns, rows, columns * tile_width, rows * tile_height


def render_contact_sheet(overlays: list[tuple[str, Path]], output_path: Path) -> None:
    if not overlays:
        return
    tile_width, tile_height = 600, 430
    columns, rows, sheet_width, sheet_height = contact_sheet_layout(
        len(overlays), tile_width=tile_width, tile_height=tile_height,
    )
    sheet = Image.new("RGB", (sheet_width, sheet_height), "#191919")
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


def render_review(
    manifest: dict[str, Any], results: list[dict[str, Any]], data_root: Path,
    output_dir: Path, *, allow_missing_images: bool = False,
) -> dict[str, Any]:
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
        record = build_review_record(item, result)
        if not image_path.is_file():
            if not allow_missing_images:
                raise ValueError(f"image is unavailable for {relative.as_posix()}")
            record["sourceOverlayStatus"] = "unavailable"
            records.append(record)
            continue
        if sha256_file(image_path) != item["sha256"]:
            raise ValueError(f"image hash mismatch for {relative.as_posix()}")
        record["sourceOverlayStatus"] = "available"
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
    refinement_statuses = Counter(
        ((record.get("grooveRefinement") or {}).get("status") or "not_available") for record in records
    )
    target_statuses = Counter(
        ((record.get("yDownTargetDiagnostic") or {}).get("toleranceStatus") or "not_available")
        for record in records
    )
    plc_blocked_count = sum(
        (
            (record.get("guidance") or {}).get("plcExecutionStatus") == "BLOCKED_MAPPING_UNCONFIRMED"
            or (record.get("yDownTargetDiagnostic") or {}).get("plcBlocked") is True
        ) for record in records
    )
    detection_statuses = Counter(
        (record.get("guidance") or {}).get("detectionStatus") or "not_available"
        for record in records
    )
    guidance_statuses = Counter(
        (record.get("guidance") or {}).get("guidanceStatus") or "not_available"
        for record in records
    )
    rotation_directions = Counter(
        (record.get("guidance") or {}).get("rotationDirection") or "not_available"
        for record in records
    )
    intermediate_detection_statuses = Counter(
        (record.get("intermediateGuidance") or {}).get("detectionStatus") or "not_available"
        for record in records
    )
    intermediate_guidance_statuses = Counter(
        (record.get("intermediateGuidance") or {}).get("guidanceStatus") or "not_available"
        for record in records
    )
    physical_circle_accepted_count = sum(
        (record.get("physicalOuterCircle") or {}).get("status") == "accepted" for record in records
    )
    localization_statuses = Counter(
        (record.get("circleLocalization") or {}).get("status") or "not_available" for record in records
    )
    source_overlay_statuses = Counter(
        record.get("sourceOverlayStatus", "unavailable") for record in records
    )
    summary = {
        "schemaVersion": "slot-pose-review/2" if any(
            key != "not_available" for key in detection_statuses
        ) else "slot-pose-review/1",
        "datasetId": dataset_id,
        "imageCount": len(records),
        "candidateBearingConvention": "image +x is 0 deg; clockwise is positive because image y increases downward",
        "roleSuggestionsAreAuthoritative": False,
        "failureCounts": dict(sorted(failures.items())),
        "singleGrooveGeometryValidCount": single_valid_count,
        "imageGrooveAzimuthAvailableCount": image_azimuth_count,
        "mechanicalGuidanceBlockedByDatumCount": datum_blocked_count,
        "grooveRefinementStatusCounts": dict(sorted(refinement_statuses.items())),
        "targetToleranceStatusCounts": dict(sorted(target_statuses.items())),
        "plcGuidanceBlockedCount": plc_blocked_count,
        "detectionStatusCounts": dict(sorted(detection_statuses.items())),
        "guidanceStatusCounts": dict(sorted(guidance_statuses.items())),
        "rotationDirectionCounts": dict(sorted(rotation_directions.items())),
        "intermediateGuidanceAuthoritative": False,
        "intermediateDetectionStatusCounts": dict(sorted(intermediate_detection_statuses.items())),
        "intermediateGuidanceStatusCounts": dict(sorted(intermediate_guidance_statuses.items())),
        "physicalOuterCircleAcceptedCount": physical_circle_accepted_count,
        "circleLocalizationStatusCounts": dict(sorted(localization_statuses.items())),
        "sourceOverlayStatusCounts": dict(sorted(source_overlay_statuses.items())),
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
    with (output_dir / "guidance.csv").open("w", newline="", encoding="utf-8") as handle:
        fields = [
            "image_id", "relative_path", "detection_status", "guidance_status",
            "current_angle_deg", "target_angle_deg", "tolerance_deg", "correction_raw_deg",
            "correction_deg", "image_frame_correction_deg", "rotation_direction",
            "within_tolerance", "plc_execution_status", "mechanical_correction_deg",
        ]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for record in records:
            guidance = record.get("guidance") or {}
            writer.writerow({
                "image_id": record["imageId"], "relative_path": record["relativePath"],
                "detection_status": guidance.get("detectionStatus"),
                "guidance_status": guidance.get("guidanceStatus"),
                "current_angle_deg": guidance.get("currentAngleDeg"),
                "target_angle_deg": guidance.get("targetAngleDeg"),
                "tolerance_deg": guidance.get("toleranceDeg"),
                "correction_raw_deg": guidance.get("correctionRawDeg"),
                "correction_deg": guidance.get("correctionDeg"),
                "image_frame_correction_deg": guidance.get("imageFrameCorrectionDeg"),
                "rotation_direction": guidance.get("rotationDirection"),
                "within_tolerance": guidance.get("withinTolerance"),
                "plc_execution_status": guidance.get("plcExecutionStatus"),
                "mechanical_correction_deg": guidance.get("mechanicalCorrectionDeg"),
            })
    with (output_dir / "circle-candidates.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=[
            "image_id", "relative_path", "proposal_id", "proposal_status", "bbox_normalized",
            "proposal_center_x", "proposal_center_y", "proposal_radius_px", "proposal_failed_checks",
            "candidate_id", "candidate_status", "rank", "score", "edge_point_count", "inlier_ratio",
            "angular_coverage", "residual_p95_px", "candidate_failed_checks", "selected",
        ])
        writer.writeheader()
        for record in records:
            localization = record.get("circleLocalization") or {}
            circle_candidates = localization.get("circleCandidates") or []
            candidates_by_proposal = {
                str(candidate.get("proposalId")): candidate
                for candidate in circle_candidates
                if candidate.get("proposalId") is not None
            }
            selected_id = localization.get("selectedCandidateId")
            emitted_candidate_ids: set[str] = set()
            for proposal in localization.get("componentProposals") or []:
                candidate = candidates_by_proposal.get(str(proposal.get("proposalId"))) or {}
                if candidate.get("candidateId") is not None:
                    emitted_candidate_ids.add(str(candidate["candidateId"]))
                writer.writerow({
                    "image_id": record["imageId"], "relative_path": record["relativePath"],
                    "proposal_id": proposal.get("proposalId"), "proposal_status": proposal.get("status"),
                    "bbox_normalized": json.dumps(proposal.get("bboxNormalized"), separators=(",", ":")),
                    "proposal_center_x": proposal.get("centerX"), "proposal_center_y": proposal.get("centerY"),
                    "proposal_radius_px": proposal.get("radiusPx"),
                    "proposal_failed_checks": "|".join(proposal.get("failedChecks") or []),
                    "candidate_id": candidate.get("candidateId"), "candidate_status": candidate.get("status"),
                    "rank": candidate.get("rank"), "score": candidate.get("score"),
                    "edge_point_count": candidate.get("edgePointCount"), "inlier_ratio": candidate.get("inlierRatio"),
                    "angular_coverage": candidate.get("angularCoverage"), "residual_p95_px": candidate.get("residualP95Px"),
                    "candidate_failed_checks": "|".join(candidate.get("failedChecks") or []),
                    "selected": bool(candidate) and candidate.get("candidateId") == selected_id,
                })
            # A malformed or older diagnostic can omit proposalId while still
            # carrying useful sparse-fit evidence. Never silently lose it.
            for candidate in circle_candidates:
                if str(candidate.get("candidateId")) in emitted_candidate_ids:
                    continue
                coarse = candidate.get("coarsePhysicalCircle") or {}
                writer.writerow({
                    "image_id": record["imageId"], "relative_path": record["relativePath"],
                    "proposal_id": candidate.get("proposalId"), "proposal_status": None,
                    "bbox_normalized": None,
                    "proposal_center_x": coarse.get("centerX"), "proposal_center_y": coarse.get("centerY"),
                    "proposal_radius_px": coarse.get("radiusPx"), "proposal_failed_checks": None,
                    "candidate_id": candidate.get("candidateId"), "candidate_status": candidate.get("status"),
                    "rank": candidate.get("rank"), "score": candidate.get("score"),
                    "edge_point_count": candidate.get("edgePointCount"), "inlier_ratio": candidate.get("inlierRatio"),
                    "angular_coverage": candidate.get("angularCoverage"),
                    "residual_p95_px": candidate.get("residualP95Px"),
                    "candidate_failed_checks": "|".join(candidate.get("failedChecks") or []),
                    "selected": candidate.get("candidateId") == selected_id,
                })
    with (output_dir / "sidewall-models.csv").open("w", newline="", encoding="utf-8") as handle:
        fields = [
            "image_id", "relative_path", "refinement_status", "schema_version", "threshold_version",
            "side", "line_fit_strategy", "detected_point_count", "support_point_count",
            "rejected_point_count", "line_inlier_ratio", "line_longitudinal_coverage",
            "line_residual_median_px", "line_residual_p95_px", "line_residual_max_px",
            "raw_hypothesis_count", "refit_hypothesis_count", "final_hypothesis_count",
            "best_model_id", "second_model_id", "best_support_count", "second_support_count",
            "support_margin", "refinement_elapsed_ms", "failed_checks",
        ]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for record in records:
            refinement = record.get("grooveRefinement") or {}
            for side_name in ("startSide", "endSide"):
                side = refinement.get(side_name) or {}
                if not side:
                    continue
                residual = side.get("lineResidualPx") or {}
                writer.writerow({
                    "image_id": record["imageId"], "relative_path": record["relativePath"],
                    "refinement_status": refinement.get("status"),
                    "schema_version": refinement.get("schemaVersion"),
                    "threshold_version": refinement.get("thresholdVersion"), "side": side_name,
                    "line_fit_strategy": side.get("lineFitStrategy"),
                    "detected_point_count": side.get("detectedPointCount", len(side.get("detectedPoints") or [])),
                    "support_point_count": side.get("supportPointCount", len(side.get("points") or [])),
                    "rejected_point_count": side.get("rejectedPointCount", len(side.get("rejectedPoints") or [])),
                    "line_inlier_ratio": side.get("lineInlierRatio"),
                    "line_longitudinal_coverage": side.get("lineLongitudinalCoverage"),
                    "line_residual_median_px": residual.get("median"),
                    "line_residual_p95_px": residual.get("p95"), "line_residual_max_px": residual.get("max"),
                    "raw_hypothesis_count": side.get("rawLineHypothesisCount"),
                    "refit_hypothesis_count": side.get("refitLineHypothesisCount"),
                    "final_hypothesis_count": side.get("lineHypothesisCount"),
                    "best_model_id": side.get("bestModelId"), "second_model_id": side.get("secondModelId"),
                    "best_support_count": side.get("bestSupportCount"),
                    "second_support_count": side.get("secondSupportCount"), "support_margin": side.get("supportMargin"),
                    "refinement_elapsed_ms": refinement.get("elapsedMs"),
                    "failed_checks": "|".join(refinement.get("failedChecks") or []),
                })
    with (output_dir / "failures.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=[
            "image_id", "relative_path", "error_code", "error_stage", "candidate_count", "groove_count",
            "single_groove_status", "image_azimuth_deg", "measured_y_down_deg",
            "position_gate_passed", "angle_tolerance_passed", "tolerance_status",
            "image_frame_correction_deg", "groove_refinement_status", "groove_refinement_failures",
            "plc_blocked", "role_status",
        ])
        writer.writeheader()
        for record in records:
            guidance = record.get("guidance") or {}
            is_detection_failure = (
                guidance.get("detectionStatus") == "DETECTION_FAILED"
                if guidance.get("detectionStatus") is not None
                else not record["result"]["valid"]
            )
            if not is_detection_failure:
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
                "measured_y_down_deg": record["yDownTargetDiagnostic"].get("measuredDeg"),
                "position_gate_passed": record["yDownTargetDiagnostic"].get("positionGatePassed"),
                "angle_tolerance_passed": record["yDownTargetDiagnostic"].get("angleTolerancePassed"),
                "tolerance_status": record["yDownTargetDiagnostic"].get("toleranceStatus"),
                "image_frame_correction_deg": record["yDownTargetDiagnostic"].get("imageFrameCorrectionDeg"),
                "groove_refinement_status": (record.get("grooveRefinement") or {}).get("status"),
                "groove_refinement_failures": "|".join(
                    (record.get("grooveRefinement") or {}).get("failedChecks") or []
                ),
                "plc_blocked": record["yDownTargetDiagnostic"].get("plcBlocked"),
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
    parser.add_argument("--allow-missing-images", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        summary = render_review(
            manifest, load_results(args.results), args.data_root, args.output_dir,
            allow_missing_images=args.allow_missing_images,
        )
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(f"Wrote {args.output_dir}: images={summary['imageCount']}, failures={summary['failureCounts']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
