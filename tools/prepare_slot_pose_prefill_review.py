#!/usr/bin/env python3
"""Create Git-external AUTO_ LabelMe and raw/019/020 visual review bundles."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.dataset_common import inspect_image, safe_relative_path, sha256_file
from tools.render_slot_pose_review import build_review_record, load_results, render_overlay


COLORS = {
    "circle": "#35c7ff", "raw": "#ffe14f", "fixture_a": "#ff9f43",
    "fixture_b": "#9b7bff", "wall_left": "#38d66b", "wall_right": "#ff5dce",
    "endpoint_left": "#ffffff", "endpoint_right": "#ff5d73",
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


def _shape(label: str, points: list[list[float]], shape_type: str, color: str, source: str) -> dict[str, Any]:
    return {
        "label": label, "points": points, "group_id": None,
        "description": "AUTO suggestion; verify/correct before creating human truth",
        "shape_type": shape_type,
        "flags": {
            "auto_generated": True, "human_verified": False,
            "runtime_input_allowed": False, "display_color": color,
            "source_algorithm": source,
        },
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


def _radial_point(circle: tuple[float, float, float], angle_deg: float) -> list[float]:
    import math
    angle = math.radians(float(angle_deg))
    return [circle[0] + circle[2] * math.cos(angle), circle[1] + circle[2] * math.sin(angle)]


def _fixture_labels(diagnostics: dict[str, Any]) -> dict[str, str]:
    matches = (diagnostics.get("fixtureShadowEvidence") or {}).get("matches") or []
    output: dict[str, str] = {}
    for suffix in ("a", "b"):
        choices = [
            item for item in matches
            if isinstance(item, dict) and str(item.get("templateId") or "").endswith(f"-{suffix}")
        ]
        if not choices:
            continue
        matched = [item for item in choices if item.get("status") == "matched"]
        pool = matched or choices
        selected = min(
            pool,
            key=lambda item: (float(item.get("centerDistanceDeg", 999.0)), str(item.get("candidateId"))),
        )
        output[str(selected.get("candidateId"))] = suffix
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


def _auto_labelme(
    item: dict[str, Any], image_name: str, payload_019: dict[str, Any], payload_020: dict[str, Any],
) -> dict[str, Any]:
    diagnostic_019 = payload_019.get("diagnostics") or {}
    diagnostic_020 = payload_020.get("diagnostics") or {}
    circle = _circle(diagnostic_020) or _circle(diagnostic_019)
    shapes: list[dict[str, Any]] = []
    if circle is not None:
        shapes.append(_shape(
            "AUTO_fitted_outer_circle",
            [[circle[0], circle[1]], [circle[0] + circle[2], circle[1]]],
            "circle", COLORS["circle"], "020" if _circle(diagnostic_020) else "019",
        ))
        fixtures = _fixture_labels(diagnostic_020) or _fixture_labels(diagnostic_019)
        for candidate in diagnostic_019.get("rawCandidates") or diagnostic_019.get("candidates") or []:
            candidate_id = str(candidate.get("candidateId") or "unknown")
            endpoint = _radial_point(circle, float(candidate["centerDeg"]))
            shapes.append(_shape(
                f"AUTO_raw_dark_candidate_{candidate_id}",
                [[circle[0], circle[1]], endpoint], "line", COLORS["raw"], "019",
            ))
            fixture_name = fixtures.get(candidate_id)
            if fixture_name is not None:
                shapes.append(_shape(
                    f"AUTO_fixture_shadow_candidate_{fixture_name}",
                    [[circle[0], circle[1]], endpoint], "line",
                    COLORS[f"fixture_{fixture_name}"], "020",
                ))
    wall_source = "019" if diagnostic_019.get("grooveRefinement") else "020"
    wall_diagnostics = diagnostic_019 if wall_source == "019" else diagnostic_020
    shapes.extend(_wall_shapes(wall_diagnostics, wall_source))
    return {
        "version": "5.0.1",
        "flags": {
            "human_verified": False, "formal_truth": False,
            "independent_from_algorithm": False, "runtime_input_allowed": False,
            "annotation_version": "AUTO-prefill-review-v1",
            "review_real_groove_required": True,
            "review_fixture_shadow_a_required": True,
            "review_fixture_shadow_b_required": True,
            "review_sidewalls_same_source_required": True,
        },
        "shapes": shapes,
        "imagePath": f"../raw/{image_name}", "imageData": None,
        "imageHeight": int(item["height"]), "imageWidth": int(item["width"]),
    }


def _contact_sheet(rows: list[tuple[str, Path, Path, Path]], output: Path) -> None:
    tile_w, tile_h, header = 560, 380, 32
    sheet = Image.new("RGB", (tile_w * 3, (tile_h + header) * len(rows)), "#181818")
    draw = ImageDraw.Draw(sheet); font = ImageFont.load_default(size=20)
    for row_index, (image_id, raw, overlay_019, overlay_020) in enumerate(rows):
        y = row_index * (tile_h + header)
        for column, (title, path) in enumerate((("RAW", raw), ("019", overlay_019), ("020", overlay_020))):
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
        overlay_019 = output_dir / "overlay-019" / f"{safe_id}.jpg"
        overlay_020 = output_dir / "overlay-020" / f"{safe_id}.jpg"
        for payload, path in ((by_019[actual_sha], overlay_019), (by_020[actual_sha], overlay_020)):
            if (payload.get("image") or {}).get("sha256") != actual_sha:
                raise ValueError(f"result SHA mismatch: {relative.as_posix()}")
            render_overlay(image_path, build_review_record(item, payload), path)
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
        _write_json(labelme_path, _auto_labelme(item, raw_name, by_019[actual_sha], by_020[actual_sha]))
        contact_rows.append((image_id, raw_path, overlay_019, overlay_020))
        entries.append({
            "imageId": image_id, "relativeImagePath": relative.as_posix(),
            "imageSha256": actual_sha,
            "rawRelativePath": raw_path.relative_to(output_dir).as_posix(),
            "overlay019RelativePath": overlay_019.relative_to(output_dir).as_posix(),
            "overlay020RelativePath": overlay_020.relative_to(output_dir).as_posix(),
            "autoLabelmeRelativePath": labelme_path.relative_to(output_dir).as_posix(),
            "autoLabelmeSha256": sha256_file(labelme_path),
            "humanVerified": False,
            "reviewQuestions": [
                "mark_or_confirm_real_groove", "mark_or_confirm_fixture_shadow_a",
                "mark_or_confirm_fixture_shadow_b", "confirm_detected_sidewalls_same_physical_source",
            ],
        })
    _contact_sheet(contact_rows, output_dir / "contact-sheet.jpg")
    index = {
        "schemaVersion": "slot-pose-prefill-review/1",
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
