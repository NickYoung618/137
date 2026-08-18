#!/usr/bin/env python3
"""Build a Git-external, read-only 161 manual-circle edge-family report."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any

import numpy as np

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from algorithms.end_face import core
from algorithms.slot_pose import circle_edge_candidates
from algorithms.slot_pose.circle_edge_candidates import (
    enumerate_radial_edge_candidates, load_detection_gray_fast,
)
from tools.dataset_common import sha256_file, write_json


SCHEMA_VERSION = "manual-circle-edge-family-analysis/1"
EXPECTED_ANNOTATION_SHA256 = "5707b530594fc71ecd75616ebde3ab07c51a11938b986e69c492a0a9c8b01e9f"
EXPECTED_WIDTH = 5472
EXPECTED_HEIGHT = 3648
EXPECTED_LABEL = "HUMAN_outer_circle_visible_arc"


def validate_labelme(payload: dict[str, Any]) -> np.ndarray:
    if payload.get("imageWidth") != EXPECTED_WIDTH or payload.get("imageHeight") != EXPECTED_HEIGHT:
        raise ValueError(f"LabelMe image dimensions must be {EXPECTED_WIDTH}x{EXPECTED_HEIGHT}")
    shapes = payload.get("shapes")
    if not isinstance(shapes, list) or len(shapes) != 1:
        raise ValueError("LabelMe must contain exactly one manual outer-circle shape")
    shape = shapes[0]
    if shape.get("label") != EXPECTED_LABEL or shape.get("shape_type") != "linestrip":
        raise ValueError("LabelMe shape must be HUMAN_outer_circle_visible_arc/linestrip")
    points = np.asarray(shape.get("points"), dtype=np.float64)
    if points.shape != (88, 2) or not np.isfinite(points).all():
        raise ValueError("manual outer-circle shape must contain 88 finite points")
    if (
        np.any(points[:, 0] < 0.0) or np.any(points[:, 0] >= EXPECTED_WIDTH)
        or np.any(points[:, 1] < 0.0) or np.any(points[:, 1] >= EXPECTED_HEIGHT)
    ):
        raise ValueError("manual points must be inside the LabelMe image")
    return points


def _residual_summary(values: np.ndarray) -> dict[str, float]:
    finite = np.asarray(values, dtype=np.float64)
    if finite.size == 0 or not np.isfinite(finite).all():
        return {"median": 0.0, "p95": 0.0, "max": 0.0}
    return {
        "median": float(np.median(finite)),
        "p95": float(np.percentile(finite, 95)),
        "max": float(np.max(finite)),
    }


def fit_manual_circle(points: np.ndarray) -> tuple[dict[str, Any], dict[str, Any]]:
    fallback = core.fit_circle(points)
    circle = tuple(map(float, core.robust_fit_circle(points, fallback)))
    residuals = np.abs(np.hypot(points[:, 0] - circle[0], points[:, 1] - circle[1]) - circle[2])
    angles = np.sort(np.mod(np.arctan2(points[:, 1] - circle[1], points[:, 0] - circle[0]), 2.0 * math.pi))
    gaps = np.diff(np.r_[angles, angles[0] + 2.0 * math.pi])
    coverage = math.degrees(2.0 * math.pi - float(np.max(gaps)))
    center_shifts: list[float] = []
    radius_shifts: list[float] = []
    for index in range(len(points)):
        subset = np.delete(points, index, axis=0)
        fitted = tuple(map(float, core.robust_fit_circle(subset, core.fit_circle(subset))))
        center_shifts.append(math.hypot(fitted[0] - circle[0], fitted[1] - circle[1]))
        radius_shifts.append(abs(fitted[2] - circle[2]))
    max_center = max(center_shifts)
    max_radius = max(radius_shifts)
    return (
        {
            "centerX": circle[0], "centerY": circle[1], "radiusPx": circle[2],
            "arcCoverageDeg": coverage, "residualPx": _residual_summary(residuals),
        },
        {
            "fitCount": len(points), "maxCenterShiftPx": max_center,
            "maxCenterEquivalentAngleDeg": math.degrees(max_center / circle[2]),
            "maxRadiusShiftPx": max_radius, "maxRadiusShiftRatio": max_radius / circle[2],
        },
    )


def _ray_circle_radius(
    origin: tuple[float, float], angle: float, circle: tuple[float, float, float],
) -> float:
    ux, uy = math.cos(angle), math.sin(angle)
    dx, dy = circle[0] - origin[0], circle[1] - origin[1]
    projected = dx * ux + dy * uy
    discriminant = circle[2] ** 2 - dx * dx - dy * dy + projected * projected
    if discriminant < 0.0:
        raise ValueError("search origin does not intersect the manual circle on every ray")
    radius = projected + math.sqrt(discriminant)
    if radius <= 0.0:
        raise ValueError("manual circle intersection is behind the ray origin")
    return radius


def _circular_sectors(flags: list[bool], step_deg: float) -> list[dict[str, Any]]:
    if not any(flags):
        return []
    if all(flags):
        return [{"startDeg": 0.0, "endDeg": (len(flags) - 1) * step_deg, "wrapsBoundary": True, "sampleCount": len(flags)}]
    starts = [index for index, flag in enumerate(flags) if flag and not flags[index - 1]]
    sectors = []
    for start in starts:
        indices = []
        index = start
        while flags[index]:
            indices.append(index)
            index = (index + 1) % len(flags)
        sectors.append({
            "startDeg": float(indices[0] * step_deg % 360.0),
            "endDeg": float(indices[-1] * step_deg % 360.0),
            "wrapsBoundary": indices[-1] < indices[0] or indices[-1] >= len(flags),
            "sampleCount": len(indices),
        })
    return sectors


def project_radial_evidence(
    gray: np.ndarray, manual_circle: tuple[float, float, float],
    search_circle: tuple[float, float, float], *, ray_count: int = 720,
    truth_gate_px: float = 8.0,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    per_ray = []
    truth_present_flags: list[bool] = []
    switch_flags: list[bool] = []
    legacy_errors: list[float] = []
    for index, angle in enumerate(np.linspace(0.0, 2.0 * math.pi, ray_count, endpoint=False)):
        truth_radius = _ray_circle_radius(search_circle[:2], float(angle), manual_circle)
        radii, profile = core.sample_radial(gray, search_circle[0], search_circle[1], float(angle), search_circle[2], 90)
        values = core.smooth_1d(profile, 9)
        peaks = enumerate_radial_edge_candidates(
            radii, values, min_gradient=4.0, separation_px=3.0,
            max_peaks=8, polarity=None, min_background_persistence_ratio=0.0,
        )
        peak_records = []
        for peak in peaks:
            radius = float(peak["radiusPx"])
            x = search_circle[0] + radius * math.cos(angle)
            y = search_circle[1] + radius * math.sin(angle)
            error = abs(math.hypot(x - manual_circle[0], y - manual_circle[1]) - manual_circle[2])
            peak_records.append({**peak, "manualCircleErrorPx": error})
        truth_present = any(item["manualCircleErrorPx"] <= truth_gate_px for item in peak_records)
        selected = core.outer_boundary_edge_point(gray, search_circle[:2], float(angle), search_circle[2])
        if selected is None:
            selected_radius = None
            selected_error = None
        else:
            selected_radius = math.hypot(selected[0] - search_circle[0], selected[1] - search_circle[1])
            selected_error = abs(
                math.hypot(selected[0] - manual_circle[0], selected[1] - manual_circle[1]) - manual_circle[2]
            )
            legacy_errors.append(selected_error)
        truth_present_flags.append(truth_present)
        switch_flags.append(selected_error is not None and selected_error > truth_gate_px)
        per_ray.append({
            "angleDeg": float(index * 360.0 / ray_count), "truthRadiusPx": truth_radius,
            "gradientPeaks": peak_records, "legacySelectedRadiusPx": selected_radius,
            "legacySelectedErrorPx": selected_error,
        })
    truth_count = sum(truth_present_flags)
    legacy_truth = sum(
        item["legacySelectedErrorPx"] is not None and item["legacySelectedErrorPx"] <= truth_gate_px
        for item in per_ray
    )
    step = 360.0 / ray_count
    projection = {
        "rayCount": ray_count, "truthGatePx": truth_gate_px,
        "truthPeakPresentCount": truth_count, "truthPeakPresentRatio": truth_count / ray_count,
        "legacySelectedTruthCount": legacy_truth, "legacySelectedTruthRatio": legacy_truth / ray_count,
        "missingSectors": _circular_sectors([not flag for flag in truth_present_flags], step),
        "switchSectors": _circular_sectors(switch_flags, step),
        "legacySelectedErrorPx": _residual_summary(np.asarray(legacy_errors)),
    }
    return projection, per_ray


def build_report(
    annotation_path: Path, image_path: Path, search_circle: tuple[float, float, float],
) -> dict[str, Any]:
    annotation_sha = sha256_file(annotation_path)
    if annotation_sha != EXPECTED_ANNOTATION_SHA256:
        raise ValueError(f"unexpected 161 annotation SHA-256: {annotation_sha}")
    payload = json.loads(annotation_path.read_text(encoding="utf-8"))
    points = validate_labelme(payload)
    manual, leave_one_out = fit_manual_circle(points)
    gray = load_detection_gray_fast(image_path)
    if gray.shape != (EXPECTED_HEIGHT, EXPECTED_WIDTH):
        raise ValueError(f"image dimensions must be {EXPECTED_WIDTH}x{EXPECTED_HEIGHT}")
    circle = (manual["centerX"], manual["centerY"], manual["radiusPx"])
    projection, per_ray = project_radial_evidence(gray, circle, search_circle)
    algorithm_path = Path(circle_edge_candidates.__file__).resolve()
    return {
        "schemaVersion": SCHEMA_VERSION, "developmentOnly": True,
        "runtimeInputAllowed": False, "status": "verified",
        "inputs": {
            "annotationSha256": annotation_sha, "imageSha256": sha256_file(image_path),
            "algorithmSha256": sha256_file(algorithm_path),
            "coreSha256": sha256_file(Path(core.__file__).resolve()),
            "width": EXPECTED_WIDTH, "height": EXPECTED_HEIGHT,
        },
        "labelme": {"label": EXPECTED_LABEL, "shapeType": "linestrip", "pointCount": 88, "valid": True},
        "manualCircle": manual, "leaveOneOut": leave_one_out,
        "projection": projection, "perRay": per_ray,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--annotation", required=True, type=Path)
    parser.add_argument("--image", required=True, type=Path)
    parser.add_argument("--search-circle", required=True, nargs=3, type=float, metavar=("CX", "CY", "R"))
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        output = args.output.resolve()
        if output.is_relative_to(REPOSITORY_ROOT):
            raise ValueError("analysis output must remain outside the Git worktree")
        report = build_report(args.annotation.resolve(), args.image.resolve(), tuple(args.search_circle))
        import jsonschema
        schema = json.loads((REPOSITORY_ROOT / "contracts/manual-circle-edge-family-analysis.schema.json").read_text())
        jsonschema.validate(report, schema)
        write_json(output, report)
        print(f"Wrote {output} sha256={hashlib.sha256(output.read_bytes()).hexdigest()}")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
