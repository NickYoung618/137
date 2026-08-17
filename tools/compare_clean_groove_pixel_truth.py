#!/usr/bin/env python3
"""Compare independent clean-groove pixels with a SHA-bound runtime result."""

from __future__ import annotations

import argparse
import copy
import json
import math
import statistics
import sys
from pathlib import Path
from typing import Any, Iterable

import numpy as np

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.dataset_common import sha256_file


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = PROJECT_ROOT / "contracts" / "clean-groove-residual-diagnostic.schema.json"
LABELS = {
    "left_wall": "HUMAN_clean_groove_wall_left_support",
    "right_wall": "HUMAN_clean_groove_wall_right_support",
    "left_endpoint": "HUMAN_clean_groove_mouth_endpoint_left",
    "right_endpoint": "HUMAN_clean_groove_mouth_endpoint_right",
}


def percentile(values: Iterable[float], quantile: float) -> float:
    ordered = sorted(float(value) for value in values)
    if not ordered:
        raise ValueError("percentile requires at least one value")
    position = (len(ordered) - 1) * float(quantile) / 100.0
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def circular_difference_deg(first: float, second: float) -> float:
    return (float(first) - float(second) + 180.0) % 360.0 - 180.0


def _outside_worktree(path: Path) -> None:
    resolved = path.resolve()
    if resolved == PROJECT_ROOT or PROJECT_ROOT in resolved.parents:
        raise ValueError("output must be outside the Git worktree")


def _finite_point(value: Any, name: str) -> np.ndarray:
    array = np.asarray(value, dtype=float)
    if array.shape != (2,) or not np.isfinite(array).all():
        raise ValueError(f"{name} must be one finite 2D point")
    return array


def _finite_points(value: Any, name: str, minimum: int = 2) -> np.ndarray:
    array = np.asarray(value, dtype=float)
    if array.ndim != 2 or array.shape[1:] != (2,) or len(array) < minimum or not np.isfinite(array).all():
        raise ValueError(f"{name} must contain at least {minimum} finite 2D points")
    return array


def _line_normalized(value: Any, name: str) -> np.ndarray:
    if not isinstance(value, dict):
        raise ValueError(f"{name} line is missing")
    line = np.asarray([value.get("a"), value.get("b"), value.get("c")], dtype=float)
    if line.shape != (3,) or not np.isfinite(line).all():
        raise ValueError(f"{name} line must be finite")
    norm = float(np.linalg.norm(line[:2]))
    if norm <= 1e-12:
        raise ValueError(f"{name} line is degenerate")
    return line / norm


def _fit_tls(points: np.ndarray, name: str) -> np.ndarray:
    center = np.mean(points, axis=0)
    centered = points - center
    _, singular, vectors = np.linalg.svd(centered, full_matrices=False)
    if len(singular) < 2 or singular[0] <= 1e-12:
        raise ValueError(f"{name} points are degenerate")
    direction = vectors[0]
    normal = np.asarray([-direction[1], direction[0]], dtype=float)
    normal /= np.linalg.norm(normal)
    return np.asarray([normal[0], normal[1], -float(np.dot(normal, center))])


def _distances(points: np.ndarray, line: np.ndarray) -> list[float]:
    return [float(abs(line[0] * point[0] + line[1] * point[1] + line[2])) for point in points]


def _stats(values: Iterable[float], *, include_values: bool = False) -> dict[str, Any]:
    numbers = [float(value) for value in values]
    result: dict[str, Any] = {
        "median": float(statistics.median(numbers)),
        "p95": percentile(numbers, 95.0),
        "max": max(numbers),
    }
    if include_values:
        result["values"] = numbers
    return result


def _line_angle(line: np.ndarray) -> float:
    return math.degrees(math.atan2(float(line[0]), float(-line[1]))) % 180.0


def _unoriented_angle_difference(first: np.ndarray, second: np.ndarray) -> float:
    difference = abs((_line_angle(first) - _line_angle(second) + 90.0) % 180.0 - 90.0)
    return float(difference)


def _direction(center: np.ndarray, point: np.ndarray) -> float:
    delta = point - center
    if float(np.linalg.norm(delta)) <= 1e-12:
        raise ValueError("mouth midpoint equals runtime circle center")
    return math.degrees(math.atan2(float(delta[1]), float(delta[0]))) % 360.0


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read JSON: {path.name}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"JSON root must be an object: {path.name}")
    return payload


def _load_results(path: Path) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise ValueError(f"cannot read runtime JSONL: {path.name}") from exc
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
            image_sha = record["image"]["sha256"]
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            raise ValueError(f"invalid runtime record at line {line_number}") from exc
        if not isinstance(image_sha, str) or len(image_sha) != 64:
            raise ValueError(f"invalid runtime image SHA at line {line_number}")
        if image_sha in records:
            raise ValueError(f"duplicate runtime image SHA: {image_sha}")
        records[image_sha] = record
    return records


def _label_points(labelme: dict[str, Any], label: str, *, minimum: int, exact: int | None = None) -> np.ndarray:
    points: list[Any] = []
    for shape in labelme.get("shapes", []):
        if isinstance(shape, dict) and shape.get("label") == label:
            if shape.get("shape_type") != "point" or not isinstance(shape.get("points"), list) or len(shape["points"]) != 1:
                raise ValueError(f"{label} must use one-point point shapes")
            points.append(shape["points"][0])
    if len(points) < minimum or (exact is not None and len(points) != exact):
        raise ValueError(f"{label} point count is invalid")
    return _finite_points(points, label, minimum=minimum)


def _map_auto_walls(refinement: dict[str, Any]) -> dict[str, dict[str, Any]]:
    intersections = refinement.get("outerCircleIntersections")
    if not isinstance(intersections, list) or len(intersections) != 2:
        raise ValueError("groove refinement must contain two outer-circle intersections")
    sides = [refinement.get("startSide"), refinement.get("endSide")]
    mapped = []
    for index, (intersection, side) in enumerate(zip(intersections, sides, strict=True)):
        point = _finite_point([intersection.get("x"), intersection.get("y")], f"AUTO endpoint {index}")
        if not isinstance(side, dict):
            raise ValueError("groove refinement sidewall is missing")
        mapped.append({"endpoint": point, "line": _line_normalized(side.get("line"), f"AUTO side {index}"),
                       "points": _finite_points(side.get("points"), f"AUTO side {index} support")})
    mapped.sort(key=lambda item: float(item["endpoint"][0]))
    return {"left": mapped[0], "right": mapped[1]}


def _entry_diagnostic(entry: dict[str, Any], labelme: dict[str, Any], record: dict[str, Any]) -> dict[str, Any]:
    if record.get("image", {}).get("width") != entry.get("imageWidth") or record.get("image", {}).get("height") != entry.get("imageHeight"):
        raise ValueError("runtime image dimensions do not match validation")
    diagnostics = record.get("diagnostics")
    if not isinstance(diagnostics, dict):
        raise ValueError("runtime diagnostics are missing")
    circle_payload = diagnostics.get("physicalOuterCircle")
    if not isinstance(circle_payload, dict) or circle_payload.get("status") != "accepted":
        raise ValueError("physical outer circle is not accepted")
    circle = circle_payload.get("physicalCircle")
    if not isinstance(circle, dict):
        raise ValueError("physical outer circle is missing")
    center = _finite_point([circle.get("centerX"), circle.get("centerY")], "runtime circle center")
    refinement = diagnostics.get("grooveRefinement")
    if not isinstance(refinement, dict) or refinement.get("physicalRefinementStatus") != "accepted":
        raise ValueError("groove physical refinement is not accepted")
    auto = _map_auto_walls(refinement)
    human_walls = {
        "left": _label_points(labelme, LABELS["left_wall"], minimum=3),
        "right": _label_points(labelme, LABELS["right_wall"], minimum=3),
    }
    human_endpoints = {
        "left": _label_points(labelme, LABELS["left_endpoint"], minimum=1, exact=1)[0],
        "right": _label_points(labelme, LABELS["right_endpoint"], minimum=1, exact=1)[0],
    }
    walls: dict[str, Any] = {}
    for name in ("left", "right"):
        human_line = _fit_tls(human_walls[name], f"HUMAN {name} wall")
        walls[name] = {
            "humanSupportPointCount": len(human_walls[name]),
            "autoSupportPointCount": len(auto[name]["points"]),
            "humanToAutoLinePx": _stats(_distances(human_walls[name], auto[name]["line"]), include_values=True),
            "autoSupportToHumanLinePx": _stats(_distances(auto[name]["points"], human_line)),
            "unorientedLineAngleDifferenceDeg": _unoriented_angle_difference(human_line, auto[name]["line"]),
        }
    human_midpoint = (human_endpoints["left"] + human_endpoints["right"]) / 2.0
    auto_midpoint = (auto["left"]["endpoint"] + auto["right"]["endpoint"]) / 2.0
    human_direction = _direction(center, human_midpoint)
    auto_direction = _direction(center, auto_midpoint)
    source = refinement.get("sourceConsistency") or diagnostics.get("grooveSourceConsistency")
    if not isinstance(source, dict):
        raise ValueError("groove source consistency is missing")
    failed = source.get("failedChecks")
    if not isinstance(failed, list):
        raise ValueError("groove source-consistency failedChecks are missing")
    contrast_only = source.get("status") == "rejected" and failed == ["edge_contrast_asymmetry"]
    mouth = {
        "leftEndpointErrorPx": float(np.linalg.norm(human_endpoints["left"] - auto["left"]["endpoint"])),
        "rightEndpointErrorPx": float(np.linalg.norm(human_endpoints["right"] - auto["right"]["endpoint"])),
        "midpointErrorPx": float(np.linalg.norm(human_midpoint - auto_midpoint)),
        "humanWidthPx": float(np.linalg.norm(human_endpoints["right"] - human_endpoints["left"])),
        "autoWidthPx": float(np.linalg.norm(auto["right"]["endpoint"] - auto["left"]["endpoint"])),
    }
    mouth["widthDifferencePx"] = mouth["autoWidthPx"] - mouth["humanWidthPx"]
    return {
        "imageId": entry["imageId"], "sourceImageSha256": entry["sourceImageSha256"],
        "humanLabelmeSha256": entry["labelmeSha256"], "walls": walls, "mouth": mouth,
        "conditionalDirection": {"conditionalOnRuntimeCircleCenter": True,
            "runtimeCircleCenter": {"x": float(center[0]), "y": float(center[1])},
            "humanDirectionFromPositiveXClockwiseDeg": human_direction,
            "autoDirectionFromPositiveXClockwiseDeg": auto_direction,
            "circularDifferenceDeg": circular_difference_deg(human_direction, auto_direction)},
        "sourceConsistency": {"status": source.get("status"), "metrics": copy.deepcopy(source.get("metrics", {})),
            "checks": copy.deepcopy(source.get("checks", [])), "failedChecks": list(failed),
            "contrastOnlyFalseRejectionObserved": contrast_only},
    }


def build_clean_groove_residual_diagnostic(validation_path: Path, results_path: Path, output_path: Path) -> dict[str, Any]:
    validation_path, results_path, output_path = map(Path, (validation_path, results_path, output_path))
    _outside_worktree(output_path)
    if output_path.exists():
        raise ValueError("output must not already exist")
    validation = _load_json(validation_path)
    if validation.get("schemaVersion") != "clean-groove-pixel-review/1" or validation.get("artifactType") != "VALIDATION":
        raise ValueError("validation must be clean-groove-pixel-review/1 VALIDATION")
    if validation.get("lifecycleStatus") not in ("WALL_ENDPOINT_COMPLETE", "WALL_ENDPOINT_AND_OUTER_REFERENCE_COMPLETE"):
        raise ValueError("validation lifecycle must be WALL_ENDPOINT_COMPLETE or higher")
    entries = validation.get("entries")
    if not isinstance(entries, list) or not entries:
        raise ValueError("validation entries are missing")
    counts = validation.get("counts")
    if not isinstance(counts, dict) or counts.get("pending") != 0:
        raise ValueError("validation must have pending=0")
    results = _load_results(results_path)
    report_entries = []
    seen: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("validation entry must be an object")
        image_id = entry.get("imageId")
        if not isinstance(image_id, str) or "part-006" in image_id:
            raise ValueError("sealed sample part-006 is forbidden")
        image_sha = entry.get("sourceImageSha256")
        if not isinstance(image_sha, str) or image_sha in seen:
            raise ValueError("duplicate or invalid validation image SHA")
        seen.add(image_sha)
        if not entry.get("wallEndpointPixelReviewComplete") or entry.get("reviewStatus") not in (
                "WALL_ENDPOINT_COMPLETE", "WALL_ENDPOINT_AND_OUTER_REFERENCE_COMPLETE"):
            raise ValueError("entry is not WALL_ENDPOINT_COMPLETE")
        relative = entry.get("labelmeRelativePath")
        if not isinstance(relative, str) or Path(relative).is_absolute() or ".." in Path(relative).parts:
            raise ValueError("unsafe LabelMe relative path")
        labelme_path = validation_path.parent / relative
        if sha256_file(labelme_path) != entry.get("labelmeSha256"):
            raise ValueError("LabelMe SHA-256 mismatch")
        labelme = _load_json(labelme_path)
        if labelme.get("imageWidth") != entry.get("imageWidth") or labelme.get("imageHeight") != entry.get("imageHeight"):
            raise ValueError("LabelMe dimensions do not match validation")
        flags = labelme.get("flags")
        if not isinstance(flags, dict) or not flags.get("human_verified") or flags.get("annotation_pending") \
                or flags.get("copied_from_auto"):
            raise ValueError("LabelMe independent human flags are invalid")
        record = results.get(image_sha)
        if record is None:
            raise ValueError(f"missing runtime image SHA: {image_sha}")
        report_entries.append(_entry_diagnostic(entry, labelme, record))
    report = {
        "schemaVersion": "clean-groove-residual-diagnostic/1", "artifactType": "DIAGNOSTIC",
        "sourceValidationSha256": sha256_file(validation_path), "sourceResultsSha256": sha256_file(results_path),
        "entries": report_entries, "summary": {"imageCount": len(report_entries),
            "wallEndpointCompleteCount": len(report_entries),
            "contrastOnlyFalseRejectionCount": sum(int(entry["sourceConsistency"]["contrastOnlyFalseRejectionObserved"])
                                                      for entry in report_entries)},
        "policy": {"outerCircleErrorEvaluated": False, "poseAngleAccuracyEvaluated": False,
            "accuracyClaimAllowed": False, "thresholdTuningAllowed": False, "runtimeInputAllowed": False,
            "plcInputAllowed": False, "humanCoordinatesAppliedAtRuntime": False},
    }
    try:
        import jsonschema
        jsonschema.Draft202012Validator(_load_json(SCHEMA_PATH)).validate(report)
    except ImportError:
        pass
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--validation", required=True, type=Path)
    parser.add_argument("--results", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        report = build_clean_groove_residual_diagnostic(args.validation, args.results, args.output)
    except ValueError as exc:
        parser.error(str(exc))
    print(json.dumps({"status": "ok", "images": report["summary"]["imageCount"],
                      "output": args.output.name}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
