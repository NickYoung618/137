#!/usr/bin/env python3
"""Create Git-external minimal AUTO_ LabelMe and RAW/SIMPLIFIED review bundles."""

from __future__ import annotations

import argparse
import json
import math
import shutil
import sys
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.dataset_common import inspect_image, safe_relative_path, sha256_file
from tools.render_slot_pose_review import load_results


COLORS = {
    "wall_left": "#00E676",
    "wall_right": "#FF2DAA",
    "endpoint_left": "#FFFFFF",
    "endpoint_right": "#FF3B30",
    "fixture": "#FF9800",
    "experimental_wall_a": "#00E5FF",
    "experimental_wall_b": "#FFD600",
}


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _require_external(path: Path) -> None:
    try:
        path.resolve().relative_to(PROJECT_ROOT.resolve())
    except ValueError:
        return
    raise ValueError("prefill review output must be outside the Git worktree")


def _by_sha(results: list[dict[str, Any]], name: str) -> dict[str, dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}
    for payload in results:
        sha = (payload.get("image") or {}).get("sha256")
        if not isinstance(sha, str) or len(sha) != 64:
            raise ValueError(f"{name} result has no image SHA-256")
        if sha in output:
            raise ValueError(f"{name} duplicate result SHA: {sha}")
        output[sha] = payload
    return output


def manifest_from_image_names(data_root: Path, image_names: list[str]) -> dict[str, Any]:
    """Resolve explicitly named files uniquely without guessing groups or roles."""
    if not image_names:
        raise ValueError("at least one --image-name is required when --manifest is omitted")
    data_root = data_root.resolve()
    images = []
    for index, name in enumerate(image_names, start=1):
        if not name or Path(name).name != name:
            raise ValueError("--image-name must be a basename, not a path")
        matches = [path for path in data_root.rglob(name) if path.is_file()]
        if len(matches) != 1:
            raise ValueError(f"--image-name {name!r} matched {len(matches)} files; expected exactly one")
        path = matches[0]
        images.append({
            "imageId": f"review-{index:02d}-{path.stem}",
            "relativePath": path.relative_to(data_root).as_posix(),
            **inspect_image(path),
        })
    return {"datasetId": "explicit-prefill-review", "images": images}


def _shape(
    label: str, points: list[list[float]], shape_type: str, color: str, source: str,
    *, extra_flags: dict[str, Any] | None = None,
) -> dict[str, Any]:
    flags = {
        "auto_generated": True, "human_verified": False,
        "runtime_input_allowed": False, "display_color": color,
        "source_algorithm": source,
    }
    flags.update(extra_flags or {})
    return {
        "label": label, "points": points, "group_id": None,
        "description": "AUTO suggestion; verify/correct before creating human truth",
        "shape_type": shape_type,
        "flags": flags,
        "mask": None,
    }


def _circle(diagnostics: dict[str, Any]) -> tuple[float, float, float] | None:
    physical = (diagnostics.get("physicalOuterCircle") or {}).get("physicalCircle")
    if not isinstance(physical, dict):
        physical = diagnostics.get("face")
    if not isinstance(physical, dict):
        return None
    keys = ("centerX", "centerY", "radiusPx")
    if not all(isinstance(physical.get(key), (int, float)) for key in keys):
        return None
    return tuple(float(physical[key]) for key in keys)  # type: ignore[return-value]


def _finite_number(value: Any) -> bool:
    return (
        not isinstance(value, bool)
        and isinstance(value, (int, float))
        and math.isfinite(float(value))
    )


def _fixture_selections(diagnostics: dict[str, Any]) -> list[dict[str, Any]]:
    """Return observed angular intervals without inventing fixture identities.

    A complete pair may select candidate ids, but even then the AUTO review only
    exposes one-dimensional profile evidence.  An incomplete pair exposes raw
    observations as unassigned intervals; it never chooses the nearest failed
    template match.
    """
    evidence = diagnostics.get("fixtureShadowEvidence") or {}
    matches = evidence.get("candidateMatches")
    if not isinstance(matches, list):
        matches = evidence.get("matches") if isinstance(evidence.get("matches"), list) else []
    raw = diagnostics.get("rawCandidates")
    if not isinstance(raw, list):
        raw = diagnostics.get("candidates") if isinstance(diagnostics.get("candidates"), list) else []
    by_id = {
        str(item.get("candidateId")): item
        for item in raw if isinstance(item, dict) and item.get("candidateId") is not None
    }
    pair = evidence.get("pairEvidence") if isinstance(evidence.get("pairEvidence"), dict) else {}
    selected_ids = pair.get("selectedCandidateIds")
    pair_complete = (
        pair.get("status") == "complete"
        and isinstance(selected_ids, list) and len(selected_ids) == 2
        and len({str(value) for value in selected_ids}) == 2
    )
    match_by_candidate: dict[str, list[dict[str, Any]]] = {}
    for match in matches:
        if isinstance(match, dict) and match.get("candidateId") is not None:
            match_by_candidate.setdefault(str(match["candidateId"]), []).append(match)
    if pair_complete:
        requested = [(str(candidate_id), suffix) for candidate_id, suffix in zip(selected_ids, ("a", "b"))]
    else:
        requested = [(candidate_id, candidate_id) for candidate_id in sorted(by_id)]
    pair_failures = [str(value) for value in (pair.get("failedChecks") or [])]
    output: list[dict[str, Any]] = []
    for candidate_id, suffix in requested:
        candidate = by_id.get(candidate_id)
        if candidate is None or not _finite_number(candidate.get("centerDeg")):
            continue
        candidate_matches = match_by_candidate.get(candidate_id, [])
        if pair_complete:
            match_status = "MATCHED_PAIR_MEMBER"
            selection_source = "PAIR_EVIDENCE"
            relevant = [
                item for item in candidate_matches
                if str(item.get("templateId") or "").endswith(f"-{suffix}")
            ] or candidate_matches
        else:
            matched = [item for item in candidate_matches if item.get("status") == "matched"]
            relevant = candidate_matches
            if matched:
                match_status = "PAIR_INCOMPLETE_MATCHED"
            elif candidate_matches:
                match_status = "NOT_MATCHED"
            else:
                match_status = "NOT_EVALUATED"
            selection_source = "UNASSIGNED_OBSERVATION"
        failed_checks = list(dict.fromkeys(
            pair_failures
            + [
                str(value)
                for item in relevant
                for value in (item.get("failedChecks") or [])
            ]
        ))
        start, end = candidate.get("startDeg"), candidate.get("endDeg")
        if not (_finite_number(start) and _finite_number(end)):
            half = candidate.get("halfWidthDeg")
            if _finite_number(half):
                start = (float(candidate["centerDeg"]) - float(half)) % 360.0
                end = (float(candidate["centerDeg"]) + float(half)) % 360.0
        interval_supported = _finite_number(start) and _finite_number(end)
        output.append({
            "suffix": suffix,
            "candidateId": candidate_id,
            "matchStatus": match_status,
            "selectionSource": selection_source,
            "centerDeg": float(candidate["centerDeg"]),
            "startDeg": float(start) if _finite_number(start) else None,
            "endDeg": float(end) if _finite_number(end) else None,
            "intervalSupported": interval_supported,
            "fixtureIdentityConfirmed": False,
            "pixelBoundaryKnown": False,
            "failedChecks": failed_checks,
        })
    return output


def _wall_shapes(diagnostics: dict[str, Any], source: str) -> list[dict[str, Any]]:
    refinement = diagnostics.get("grooveRefinement") or {}
    sides = []
    for key in ("startSide", "endSide"):
        points = (refinement.get(key) or {}).get("points") or []
        if len(points) >= 2:
            normalized = [[float(point[0]), float(point[1])] for point in points]
            sides.append((sum(point[0] for point in normalized) / len(normalized), normalized))
    sides.sort(key=lambda item: item[0])
    shapes: list[dict[str, Any]] = []
    for side_name, (_, points) in zip(("left", "right"), sides):
        shapes.append(_shape(
            f"AUTO_detected_groove_wall_{side_name}", points, "linestrip",
            COLORS[f"wall_{side_name}"], source,
        ))
    endpoints = refinement.get("outerCircleIntersections") or []
    endpoint_points = sorted(
        [[float(item["x"]), float(item["y"])] for item in endpoints if isinstance(item, dict) and "x" in item and "y" in item],
        key=lambda point: point[0],
    )
    for side_name, point in zip(("left", "right"), endpoint_points):
        shapes.append(_shape(
            f"AUTO_detected_mouth_endpoint_{side_name}", [point], "point",
            COLORS[f"endpoint_{side_name}"], source,
        ))
    return shapes


def _experimental_bidirectional_wall_shapes(
    diagnostics: dict[str, Any],
) -> list[dict[str, Any]]:
    """Render only the final canonical wall pair, never seed-level search rays."""
    diagnostic = diagnostics.get("localSecondWallDiagnostic") or {}
    pair = diagnostic.get("experimentalCandidate")
    if not isinstance(pair, dict):
        pairs = diagnostic.get("canonicalWallPairs")
        pair = pairs[0] if isinstance(pairs, list) and pairs and isinstance(pairs[0], dict) else None
    if not isinstance(pair, dict):
        return []
    walls = pair.get("wallCandidates")
    if not isinstance(walls, list) or len(walls) != 2:
        return []
    normalized: list[tuple[float, dict[str, Any], list[list[float]]]] = []
    for wall in walls:
        if not isinstance(wall, dict):
            return []
        segment = wall.get("lineSegment")
        if not isinstance(segment, dict):
            return []
        endpoints = [segment.get("start"), segment.get("end")]
        if not all(
            isinstance(point, dict) and _finite_number(point.get("x")) and _finite_number(point.get("y"))
            for point in endpoints
        ):
            return []
        points = [[float(point["x"]), float(point["y"])] for point in endpoints]
        normalized.append((sum(point[0] for point in points) / 2.0, wall, points))
    normalized.sort(key=lambda item: item[0])
    shapes: list[dict[str, Any]] = []
    failed_checks = [str(value) for value in (pair.get("failedChecks") or [])]
    for suffix, (_, wall, points) in zip(("a", "b"), normalized):
        shapes.append(_shape(
            f"AUTO_experimental_bidirectional_wall_candidate_{suffix}",
            points, "line", COLORS[f"experimental_wall_{suffix}"], "021",
            extra_flags={
                "candidate_only": True,
                "authoritative": False,
                "pose_promotion_allowed": False,
                "canonical_pair_id": pair.get("canonicalPairId"),
                "wall_cluster_id": wall.get("clusterId"),
                "search_domain_id": wall.get("searchDomainId"),
                "search_direction": wall.get("searchDirection"),
                "pair_passed": bool(pair.get("passed", diagnostic.get("experimentalCandidate") is pair)),
                "failed_checks": failed_checks,
            },
        ))
    return shapes


def _angular_interval_points(
    circle: tuple[float, float, float], start_deg: float, end_deg: float,
) -> list[list[float]]:
    span = (float(end_deg) - float(start_deg)) % 360.0
    if not 0.0 < span <= 90.0:
        return []
    count = max(4, int(math.ceil(span / 3.0)) + 1)
    angles = [float(start_deg) + span * index / (count - 1) for index in range(count)]
    return [
        [
            circle[0] + circle[2] * 1.035 * math.cos(math.radians(angle)),
            circle[1] + circle[2] * 1.035 * math.sin(math.radians(angle)),
        ]
        for angle in angles
    ]


def _fixture_shapes(diagnostics: dict[str, Any]) -> list[dict[str, Any]]:
    circle = _circle(diagnostics)
    if circle is None:
        return []
    shapes: list[dict[str, Any]] = []
    for selection in _fixture_selections(diagnostics):
        points = (
            _angular_interval_points(circle, selection["startDeg"], selection["endDeg"])
            if selection["intervalSupported"] else []
        )
        shape_type = "linestrip"
        boundary_semantics = "angular_profile_interval"
        if not points:
            shape_type = "line"
            boundary_semantics = "direction_only"
            angle = math.radians(selection["centerDeg"])
            points = [
                [
                    circle[0] + circle[2] * ratio * math.cos(angle),
                    circle[1] + circle[2] * ratio * math.sin(angle),
                ]
                for ratio in (0.86, 1.02)
            ]
        shapes.append(_shape(
            f"AUTO_observed_dark_angular_interval_{selection['suffix']}",
            points, shape_type, COLORS["fixture"], "020",
            extra_flags={
                "candidate_only": True,
                "fixture_identity_confirmed": False,
                "boundary_semantics": boundary_semantics,
                "pixel_boundary_known": False,
                "match_status": selection["matchStatus"],
                "candidate_id": selection["candidateId"],
                "failed_checks": selection["failedChecks"],
                "selection_source": selection["selectionSource"],
                "start_deg": selection["startDeg"],
                "center_deg": selection["centerDeg"],
                "end_deg": selection["endDeg"],
            },
        ))
    return shapes


def _review_shapes(
    payload_019: dict[str, Any], payload_020: dict[str, Any],
) -> list[dict[str, Any]]:
    diagnostics_019 = payload_019.get("diagnostics") or {}
    diagnostics_020 = payload_020.get("diagnostics") or {}
    return (
        _wall_shapes(diagnostics_019, "019")
        + _fixture_shapes(diagnostics_020)
        + _experimental_bidirectional_wall_shapes(diagnostics_020)
    )


def _error_code(payload: dict[str, Any]) -> str:
    error = payload.get("error")
    if isinstance(error, dict) and isinstance(error.get("code"), str):
        return error["code"]
    return "NONE"


def _review_text_lines(
    payload_019: dict[str, Any], payload_020: dict[str, Any],
) -> list[str]:
    valid_019 = bool((payload_019.get("result") or {}).get("valid", False))
    return [
        f"019 valid={valid_019} | 020 error={_error_code(payload_020)}",
        "GREEN=019 wall-left | PINK=019 wall-right | DOTS=mouth endpoints",
        "020 fixture candidate != valid",
        "Observed dark angular interval",
        "Fixture identity unconfirmed | Pixel boundary unknown",
        "CYAN/YELLOW=021 final canonical wall-pair candidate (NOT AUTHORITATIVE)",
        "HUMAN CONFIRMATION REQUIRED: real groove",
    ]


def _font(size: int) -> ImageFont.ImageFont:
    for name in ("DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def _draw_arrow(
    draw: ImageDraw.ImageDraw, points: list[tuple[float, float]], color: str, width: int,
) -> None:
    draw.line(points, fill=color, width=width)
    if len(points) < 2:
        return
    start, end = points[-2], points[-1]
    angle = math.atan2(end[1] - start[1], end[0] - start[0])
    size = width * 2.4
    head = [
        end,
        (
            end[0] - size * math.cos(angle - math.pi / 6.0),
            end[1] - size * math.sin(angle - math.pi / 6.0),
        ),
        (
            end[0] - size * math.cos(angle + math.pi / 6.0),
            end[1] - size * math.sin(angle + math.pi / 6.0),
        ),
    ]
    draw.polygon(head, fill=color)


def render_simplified(
    image_path: Path, payload_019: dict[str, Any], payload_020: dict[str, Any],
    output_path: Path,
) -> None:
    with Image.open(image_path) as source:
        image = source.convert("RGB")
    width, height = image.size
    annotation = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(annotation)
    font_size = max(16, min(42, round(min(width, height) / 50)))
    font = _font(font_size)
    line_height = font_size + max(4, font_size // 5)
    lines = _review_text_lines(payload_019, payload_020)
    banner_height = min(height, line_height * len(lines) + 14)
    draw.rectangle((0, 0, width, banner_height), fill=(0, 0, 0, 172))
    for index, line in enumerate(lines):
        color = (
            "white" if index < 2
            else (COLORS["fixture"] if index == 2 else "#FFF176")
        )
        draw.text((12, 7 + index * line_height), line, fill=color, font=font)

    stroke = max(6, round(min(width, height) / 250))
    endpoint_radius = max(8, round(stroke * 1.6))
    for shape in _review_shapes(payload_019, payload_020):
        points = [tuple(float(value) for value in point) for point in shape["points"]]
        label, color = str(shape["label"]), str(shape["flags"]["display_color"])
        if label.startswith("AUTO_detected_groove_wall_"):
            draw.line(points, fill=color, width=stroke, joint="curve")
        elif label.startswith("AUTO_detected_mouth_endpoint_") and points:
            x, y = points[0]
            draw.ellipse(
                (x - endpoint_radius, y - endpoint_radius, x + endpoint_radius, y + endpoint_radius),
                fill=color, outline="black", width=max(2, stroke // 3),
            )
        elif label.startswith("AUTO_observed_dark_angular_interval_"):
            flags = shape["flags"]
            if shape["shape_type"] == "linestrip":
                draw.line(points, fill=color, width=stroke)
                circle = _circle(payload_020.get("diagnostics") or {})
                if circle is not None:
                    for key in ("start_deg", "center_deg", "end_deg"):
                        angle_value = flags.get(key)
                        if _finite_number(angle_value):
                            angle = math.radians(float(angle_value))
                            tick = [
                                (circle[0] + circle[2] * ratio * math.cos(angle),
                                 circle[1] + circle[2] * ratio * math.sin(angle))
                                for ratio in (1.00, 1.07)
                            ]
                            draw.line(tick, fill=color, width=stroke)
            else:
                _draw_arrow(draw, points, color, stroke)
            if points:
                anchor = points[len(points) // 2]
                values = (
                    f"{float(flags['start_deg']):.3f}/{float(flags['center_deg']):.3f}/"
                    f"{float(flags['end_deg']):.3f} deg"
                    if all(_finite_number(flags.get(key)) for key in ("start_deg", "center_deg", "end_deg"))
                    else f"center={float(flags['center_deg']):.3f} deg"
                )
                draw.text(
                    (anchor[0] + stroke, anchor[1] + stroke),
                    f"{flags['candidate_id']} | {values} | {flags['match_status']}",
                    fill=color, font=font,
                    stroke_width=2, stroke_fill="black",
                )
        elif label.startswith("AUTO_experimental_bidirectional_wall_candidate_"):
            draw.line(points, fill=color, width=stroke, joint="curve")
    image = Image.alpha_composite(image.convert("RGBA"), annotation).convert("RGB")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path, format="PNG")


def _auto_labelme(
    item: dict[str, Any], image_name: str, payload_019: dict[str, Any], payload_020: dict[str, Any],
) -> dict[str, Any]:
    return {
        "version": "5.0.1",
        "flags": {
            "human_verified": False, "formal_truth": False,
            "independent_from_algorithm": False, "runtime_input_allowed": False,
            "annotation_version": "AUTO-prefill-review-v3-angular-interval",
            "review_real_groove_required": True,
            "review_fixture_shadow_a_required": True,
            "review_fixture_shadow_b_required": True,
            "review_sidewalls_same_source_required": True,
        },
        "shapes": _review_shapes(payload_019, payload_020),
        "imagePath": f"../raw/{image_name}", "imageData": None,
        "imageHeight": int(item["height"]), "imageWidth": int(item["width"]),
    }


def _contact_sheet(rows: list[tuple[str, Path, Path]], output: Path) -> None:
    tile_w, tile_h, header = 560, 380, 32
    sheet = Image.new("RGB", (tile_w * 2, (tile_h + header) * len(rows)), "#181818")
    draw = ImageDraw.Draw(sheet); font = ImageFont.load_default(size=20)
    for row_index, (image_id, raw, simplified) in enumerate(rows):
        y = row_index * (tile_h + header)
        for column, (title, path) in enumerate((("RAW", raw), ("SIMPLIFIED", simplified))):
            with Image.open(path) as source:
                tile = source.convert("RGB")
            tile.thumbnail((tile_w, tile_h), Image.Resampling.LANCZOS)
            x = column * tile_w
            sheet.paste(tile, (x, y + header))
            draw.text((x + 8, y + 5), f"{image_id} | {title}", fill="white", font=font)
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output, quality=90)


def prepare_prefill_review(
    manifest: dict[str, Any], data_root: Path, results_019: list[dict[str, Any]],
    results_020: list[dict[str, Any]], output_dir: Path,
) -> dict[str, Any]:
    output_dir = output_dir.resolve(); _require_external(output_dir)
    data_root = data_root.resolve()
    by_019, by_020 = _by_sha(results_019, "019"), _by_sha(results_020, "020")
    entries, contact_rows = [], []
    for item in manifest.get("images") or []:
        relative = safe_relative_path(str(item["relativePath"]))
        image_path = data_root / relative
        if not image_path.is_file():
            raise ValueError(f"missing image: {relative.as_posix()}")
        actual_sha = sha256_file(image_path)
        if actual_sha != item.get("sha256"):
            raise ValueError(f"manifest image SHA mismatch: {relative.as_posix()}")
        if actual_sha not in by_019 or actual_sha not in by_020:
            raise ValueError(f"019/020 result SHA missing for {relative.as_posix()}")
        image_id = str(item["imageId"])
        safe_id = "".join(char if char.isalnum() or char in "._-" else "-" for char in image_id)
        raw_name = f"{safe_id}{image_path.suffix.lower()}"
        raw_path = output_dir / "raw" / raw_name
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        if raw_path.exists() and sha256_file(raw_path) != actual_sha:
            raise ValueError(f"existing raw review image SHA mismatch: {raw_name}")
        if not raw_path.exists():
            shutil.copy2(image_path, raw_path)
        payload_019, payload_020 = by_019[actual_sha], by_020[actual_sha]
        for payload in (payload_019, payload_020):
            if (payload.get("image") or {}).get("sha256") != actual_sha:
                raise ValueError(f"result SHA mismatch: {relative.as_posix()}")
        simplified_path = output_dir / "simplified" / f"{safe_id}.png"
        render_simplified(image_path, payload_019, payload_020, simplified_path)
        labelme_path = output_dir / "labelme-auto" / f"{safe_id}.json"
        if labelme_path.exists():
            prior = json.loads(labelme_path.read_text(encoding="utf-8"))
            if not isinstance(prior, dict):
                raise ValueError(f"existing LabelMe review is not an object: {labelme_path.name}")
            prior_shapes = prior.get("shapes")
            has_human_content = bool((prior.get("flags") or {}).get("human_verified")) or any(
                not str(shape.get("label") or "").startswith("AUTO_")
                for shape in (prior_shapes or []) if isinstance(shape, dict)
            )
            if has_human_content:
                raise ValueError(f"refusing to overwrite human review: {labelme_path.name}")
        _write_json(labelme_path, _auto_labelme(item, raw_name, payload_019, payload_020))
        contact_rows.append((image_id, raw_path, simplified_path))
        entries.append({
            "imageId": image_id, "relativeImagePath": relative.as_posix(),
            "imageSha256": actual_sha,
            "rawRelativePath": raw_path.relative_to(output_dir).as_posix(),
            "simplifiedRelativePath": simplified_path.relative_to(output_dir).as_posix(),
            "simplifiedSha256": sha256_file(simplified_path),
            "autoLabelmeRelativePath": labelme_path.relative_to(output_dir).as_posix(),
            "autoLabelmeSha256": sha256_file(labelme_path),
            "humanVerified": False,
            "displaySummary": {
                "019Valid": bool((payload_019.get("result") or {}).get("valid", False)),
                "020ErrorCode": _error_code(payload_020),
            },
            "reviewQuestions": [
                "mark_or_confirm_real_groove", "mark_or_confirm_fixture_shadow_a",
                "mark_or_confirm_fixture_shadow_b", "confirm_detected_sidewalls_same_physical_source",
            ],
        })
    _contact_sheet(contact_rows, output_dir / "contact-sheet.jpg")
    index = {
        "schemaVersion": "slot-pose-prefill-review/2",
        "datasetId": manifest.get("datasetId"),
        "counts": {"images": len(entries), "humanVerified": 0, "pending": len(entries)},
        "entries": entries,
        "truthPolicy": {
            "autoShapesAreTruth": False, "runtimeInputAllowed": False,
            "humanMustReview": True,
        },
    }
    _write_json(output_dir / "review-index.json", index)
    return index


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--manifest", type=Path)
    source.add_argument("--image-name", action="append", default=[])
    parser.add_argument("--data-root", required=True, type=Path)
    parser.add_argument("--results-019", required=True, type=Path)
    parser.add_argument("--results-020", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    try:
        manifest = (
            json.loads(args.manifest.read_text(encoding="utf-8"))
            if args.manifest is not None
            else manifest_from_image_names(args.data_root, args.image_name)
        )
        index = prepare_prefill_review(
            manifest, args.data_root, load_results(args.results_019),
            load_results(args.results_020), args.output_dir,
        )
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr); return 2
    print(f"Prepared {index['counts']['images']} AUTO_ review cases in {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
