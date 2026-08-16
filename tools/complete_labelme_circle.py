#!/usr/bin/env python3
"""Complete a reviewed partial LabelMe circular arc with deterministic geometry."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageFont

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from algorithms.hole_2.main import (
    CIRCLE_RESIDUAL_PX,
    circular_residual,
    fit_circle_kasa,
    robust_fit_circle,
)


SCHEMA_VERSION = "labelme-circle-completion-report/1"
CONFIG_SCHEMA_VERSION = "labelme-circle-completion-config/1"
DEFAULT_CONFIG: dict[str, Any] = {
    "schemaVersion": CONFIG_SCHEMA_VERSION,
    "inputLabel": "outer_circle_visible_arc",
    "outputLabel": "outer_circle_contour",
    "minimumSourcePoints": 8,
    "maximumMedianResidualPx": CIRCLE_RESIDUAL_PX,
    "minimumArcCoverageDeg": 120.0,
    "maximumCompletedUniquePoints": 4096,
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_config(config_path: Path | None) -> dict[str, Any]:
    supplied: dict[str, Any] = {}
    if config_path is not None:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("completion config must be a JSON object")
        supplied = payload
        unknown = sorted(set(supplied) - set(DEFAULT_CONFIG))
        if unknown:
            raise ValueError("unknown completion config fields: " + ",".join(unknown))
    config = {**DEFAULT_CONFIG, **supplied}
    if config.get("schemaVersion") != CONFIG_SCHEMA_VERSION:
        raise ValueError(f"config schemaVersion must be {CONFIG_SCHEMA_VERSION}")
    for key in ("inputLabel", "outputLabel"):
        if not isinstance(config.get(key), str) or not config[key].strip():
            raise ValueError(f"config {key} must be a non-empty string")
    if config["inputLabel"] == config["outputLabel"]:
        raise ValueError("inputLabel and outputLabel must differ")
    if not isinstance(config.get("minimumSourcePoints"), int) or config["minimumSourcePoints"] < 8:
        raise ValueError("minimumSourcePoints must be an integer >= 8")
    maximum_residual = config.get("maximumMedianResidualPx")
    if (
        isinstance(maximum_residual, bool)
        or not isinstance(maximum_residual, (int, float))
        or not 0.0 < float(maximum_residual) <= CIRCLE_RESIDUAL_PX
    ):
        raise ValueError(
            f"maximumMedianResidualPx must be in (0, CIRCLE_RESIDUAL_PX={CIRCLE_RESIDUAL_PX}]"
        )
    coverage = config.get("minimumArcCoverageDeg")
    if (
        isinstance(coverage, bool)
        or not isinstance(coverage, (int, float))
        or not 0.0 < float(coverage) <= 360.0
    ):
        raise ValueError("minimumArcCoverageDeg must be in (0, 360]")
    maximum_points = config.get("maximumCompletedUniquePoints")
    if not isinstance(maximum_points, int) or maximum_points < 8:
        raise ValueError("maximumCompletedUniquePoints must be an integer >= 8")
    return config


def _finite_points(raw_points: Any, minimum_count: int) -> np.ndarray:
    if not isinstance(raw_points, list) or len(raw_points) < minimum_count:
        raise ValueError(f"source linestrip must contain at least {minimum_count} finite points")
    values: list[tuple[float, float]] = []
    for point in raw_points:
        if (
            not isinstance(point, (list, tuple))
            or len(point) != 2
            or any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in point)
        ):
            raise ValueError(f"source linestrip must contain at least {minimum_count} finite points")
        x, y = map(float, point)
        if not math.isfinite(x) or not math.isfinite(y):
            raise ValueError(f"source linestrip must contain at least {minimum_count} finite points")
        values.append((x, y))
    points = np.asarray(values, dtype=np.float64)
    steps = np.hypot(np.diff(points[:, 0]), np.diff(points[:, 1]))
    if len(steps) < minimum_count - 1 or not np.isfinite(steps).all() or np.any(steps <= 1e-6):
        raise ValueError("source linestrip adjacent points must be distinct and finite")
    return points


def _radial_residuals(points: np.ndarray, circle: tuple[float, float, float]) -> np.ndarray:
    cx, cy, radius = circle
    return np.abs(np.hypot(points[:, 0] - cx, points[:, 1] - cy) - radius)


def _residual_summary(residuals: np.ndarray) -> dict[str, float]:
    return {
        "median": float(np.median(residuals)),
        "p95": float(np.percentile(residuals, 95.0)),
        "max": float(np.max(residuals)),
    }


def _angular_coverage_deg(points: np.ndarray, center: tuple[float, float]) -> float:
    angles = np.sort(np.mod(
        np.arctan2(points[:, 1] - center[1], points[:, 0] - center[0]),
        2.0 * math.pi,
    ))
    gaps = np.diff(np.concatenate((angles, [angles[0] + 2.0 * math.pi])))
    return math.degrees(2.0 * math.pi - float(np.max(gaps)))


def _median_spacing(points: np.ndarray) -> float:
    spacing = np.hypot(np.diff(points[:, 0]), np.diff(points[:, 1]))
    median = float(np.median(spacing))
    if not math.isfinite(median) or median <= 0.0:
        raise ValueError("source linestrip median adjacent spacing must be positive")
    return median


def _complete_points(
    source: np.ndarray,
    circle: tuple[float, float, float],
    source_spacing: float,
    maximum_unique_points: int,
) -> np.ndarray:
    circumference = 2.0 * math.pi * circle[2]
    unique_count = max(8, int(round(circumference / source_spacing)))
    if unique_count > maximum_unique_points:
        raise ValueError(
            f"derived completed point count {unique_count} exceeds safety maximum {maximum_unique_points}"
        )
    source_angles = np.unwrap(np.arctan2(source[:, 1] - circle[1], source[:, 0] - circle[0]))
    direction = -1.0 if float(np.median(np.diff(source_angles))) < 0.0 else 1.0
    start = float(source_angles[0])
    angles = start + direction * 2.0 * math.pi * np.arange(unique_count, dtype=np.float64) / unique_count
    unique = np.column_stack((
        circle[0] + circle[2] * np.cos(angles),
        circle[1] + circle[2] * np.sin(angles),
    ))
    return np.vstack((unique, unique[0]))


def _draw_preview(
    image_path: Path,
    source_points: np.ndarray,
    completed_points: np.ndarray,
    shapes: list[dict[str, Any]],
    output_path: Path,
) -> None:
    with Image.open(image_path) as source:
        image = source.convert("RGB")
    draw = ImageDraw.Draw(image)
    width = max(4, image.width // 1000)
    point_radius = max(5, image.width // 900)
    font = ImageFont.load_default(size=max(20, image.width // 180))

    draw.line([tuple(point) for point in completed_points], fill="#35c7ff", width=width, joint="curve")
    for point in completed_points[:-1]:
        x, y = map(float, point)
        draw.ellipse(
            (x - point_radius, y - point_radius, x + point_radius, y + point_radius),
            outline="#35c7ff", width=max(2, width // 2),
        )
    draw.line([tuple(point) for point in source_points], fill="#ffe14f", width=width)
    for point in source_points:
        x, y = map(float, point)
        draw.ellipse(
            (x - point_radius, y - point_radius, x + point_radius, y + point_radius),
            fill="#ffe14f",
        )

    axis_colors = {"groove_axis": "#38d66b", "datum_axis": "#ff5dce"}
    for shape in shapes:
        color = axis_colors.get(shape.get("label"))
        points = shape.get("points") or []
        if color and len(points) >= 2:
            draw.line([tuple(map(float, point)) for point in points], fill=color, width=width * 2)
            draw.text(tuple(map(float, points[-1])), f" {shape['label']}", fill=color, font=font,
                      stroke_width=2, stroke_fill="black")

    header_height = max(115, image.height // 22)
    draw.rectangle((0, 0, min(image.width, 2600), header_height), fill="#111111")
    draw.text((18, 12), "AUTO COMPLETED CIRCLE - human_verified=false", fill="white", font=font)
    draw.text(
        (18, 58), "cyan=completed fitted circle; yellow=source visible arc; green=groove; pink=datum",
        fill="white", font=font,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path, format="JPEG", quality=92)


def complete_labelme_circle(
    annotation_path: Path,
    image_path: Path,
    completed_path: Path,
    report_path: Path,
    preview_path: Path,
    config_path: Path | None = None,
) -> dict[str, Any]:
    paths = [annotation_path.resolve(), image_path.resolve(), completed_path.resolve(),
             report_path.resolve(), preview_path.resolve()]
    if len(set(paths)) != len(paths):
        raise ValueError("input and output paths must be distinct")
    project_root = PROJECT_ROOT.resolve()
    for output_path in paths[2:]:
        try:
            output_path.relative_to(project_root)
        except ValueError:
            continue
        raise ValueError("completion outputs must be outside the Git worktree")
    if not annotation_path.is_file() or not image_path.is_file():
        raise ValueError("source annotation and image must exist")
    config = _load_config(config_path)
    annotation = json.loads(annotation_path.read_text(encoding="utf-8"))
    if not isinstance(annotation, dict) or not isinstance(annotation.get("shapes"), list):
        raise ValueError("source annotation must be a LabelMe object with shapes")
    image_name = annotation.get("imagePath")
    if not isinstance(image_name, str) or Path(image_name).name != image_path.name:
        raise ValueError("LabelMe imagePath must match the supplied image filename")
    with Image.open(image_path) as image:
        image_width, image_height = image.size
        image_format = image.format
    if annotation.get("imageWidth") != image_width or annotation.get("imageHeight") != image_height:
        raise ValueError("LabelMe image dimensions do not match the supplied image")

    matches = [shape for shape in annotation["shapes"] if shape.get("label") == config["inputLabel"]]
    if len(matches) != 1:
        raise ValueError(f"exactly one source shape labeled {config['inputLabel']!r} is required")
    source_shape = matches[0]
    if source_shape.get("shape_type") != "linestrip":
        raise ValueError("source circle arc must use LabelMe shape_type=linestrip")
    source_points = _finite_points(source_shape.get("points"), int(config["minimumSourcePoints"]))
    initial = tuple(map(float, fit_circle_kasa(source_points)))
    initial_residual = circular_residual(source_points, initial)
    maximum_residual = float(config["maximumMedianResidualPx"])
    if not math.isfinite(initial_residual) or initial_residual >= maximum_residual:
        raise ValueError(
            f"circle residual {initial_residual:.6f}px must be below {maximum_residual:.6f}px"
        )
    circle = tuple(map(float, robust_fit_circle(source_points, initial)))
    if not all(math.isfinite(value) for value in circle) or circle[2] <= 0.0:
        raise ValueError("circle fit is invalid")
    source_residuals = _radial_residuals(source_points, circle)
    median_residual = circular_residual(source_points, circle)
    if not math.isfinite(median_residual) or median_residual >= maximum_residual:
        raise ValueError(
            f"circle residual {median_residual:.6f}px must be below {maximum_residual:.6f}px"
        )
    coverage = _angular_coverage_deg(source_points, (circle[0], circle[1]))
    minimum_coverage = float(config["minimumArcCoverageDeg"])
    if coverage < minimum_coverage:
        raise ValueError(
            f"source angular coverage {coverage:.6f}deg is below {minimum_coverage:.6f}deg"
        )
    source_spacing = _median_spacing(source_points)
    completed_points = _complete_points(
        source_points, circle, source_spacing, int(config["maximumCompletedUniquePoints"]),
    )
    completed_residuals = _radial_residuals(completed_points, circle)
    completed_spacing = _median_spacing(completed_points)

    completed_shape = copy.deepcopy(source_shape)
    completed_shape.update({
        "label": config["outputLabel"],
        "shape_type": "linestrip",
        "points": [[float(x), float(y)] for x, y in completed_points],
        "flags": {
            **(source_shape.get("flags") or {}),
            "auto_completed": True,
            "human_verified": False,
        },
        "description": (
            "Auto-completed from the visible arc by robust geometric circle fitting; "
            "auto_completed=true; human_verified=false; requires LabelMe review."
        ),
    })
    output = copy.deepcopy(annotation)
    output["flags"] = {
        **(annotation.get("flags") or {}),
        "auto_completed": True,
        "human_verified": False,
    }
    output_shapes: list[dict[str, Any]] = []
    removed_labels: list[str] = []
    for shape in annotation["shapes"]:
        label = shape.get("label")
        if label == config["inputLabel"]:
            output_shapes.append(completed_shape)
        elif label == "ignore_occlusion":
            removed_labels.append("ignore_occlusion")
            continue
        else:
            output_shapes.append(copy.deepcopy(shape))
    output["shapes"] = output_shapes

    completed_path.parent.mkdir(parents=True, exist_ok=True)
    completed_path.write_text(
        json.dumps(output, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    _draw_preview(image_path, source_points, completed_points, output_shapes, preview_path)

    report = {
        "schemaVersion": SCHEMA_VERSION,
        "status": "AUTO_COMPLETED_REQUIRES_HUMAN_REVIEW",
        "source": {
            "annotationFile": annotation_path.name,
            "annotationSha256": _sha256(annotation_path),
            "imageFile": image_path.name,
            "imageSha256": _sha256(image_path),
            "imageFormat": image_format,
            "imageWidth": image_width,
            "imageHeight": image_height,
            "label": config["inputLabel"],
            "pointCount": int(len(source_points)),
            "medianAdjacentSpacingPx": source_spacing,
            "angularCoverageDeg": coverage,
            "radialResidualPx": _residual_summary(source_residuals),
        },
        "fit": {
            "method": "fit_circle_kasa+robust_fit_circle+geometric_circle_fit",
            "circleResidualGate": "circular_residual(fit_circle_kasa)",
            "initialKasaCircleResidualPx": initial_residual,
            "refinedCircleResidualPx": median_residual,
            "maximumMedianResidualPx": maximum_residual,
            "minimumArcCoverageDeg": minimum_coverage,
            "centerX": circle[0],
            "centerY": circle[1],
            "radiusPx": circle[2],
        },
        "completed": {
            "annotationFile": completed_path.name,
            "annotationSha256": _sha256(completed_path),
            "previewFile": preview_path.name,
            "previewSha256": _sha256(preview_path),
            "label": config["outputLabel"],
            "pointCount": int(len(completed_points)),
            "uniquePointCount": int(len(completed_points) - 1),
            "closedByRepeatedFirstPoint": True,
            "medianAdjacentSpacingPx": completed_spacing,
            "angularCoverageDeg": 360.0,
            "radialResidualPx": _residual_summary(completed_residuals),
            "autoCompleted": True,
            "humanVerified": False,
        },
        "preservedLabels": [
            shape.get("label")
            for shape in output_shapes
            if shape.get("label") != config["outputLabel"]
        ],
        "removedLabels": removed_labels,
        "limitations": [
            "The completed contour is deterministic fitted geometry, not generated image content.",
            "The completed contour is not manual truth and requires review in LabelMe.",
        ],
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--annotation", required=True, type=Path)
    parser.add_argument("--image", required=True, type=Path)
    parser.add_argument("--completed", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--preview", required=True, type=Path)
    parser.add_argument("--config", type=Path)
    args = parser.parse_args()
    try:
        report = complete_labelme_circle(
            args.annotation, args.image, args.completed, args.report, args.preview, args.config,
        )
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(
        f"status={report['status']} source_points={report['source']['pointCount']} "
        f"completed_points={report['completed']['pointCount']} report={args.report}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
