#!/usr/bin/env python3
"""Compare a frozen current-capture result with external confirmed LabelMe truth."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from algorithms.hole_2.main import fit_circle_kasa, geometric_circle_fit, read_labelme
from algorithms.hole_2.current_capture import validate_result_contract


SCHEMA_VERSION = "hole2-current-capture-acceptance/1"
SCOPE = "single_image_pixel_geometry_only_no_acceptance_tolerance_not_repeatability_mm_accuracy_or_production_ok_ng"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _strict_truth(
    annotation_path: Path, target_image_path: Path
) -> tuple[list[list[float]], list[list[float]]]:
    annotation = read_labelme(annotation_path)
    image_path = annotation.get("imagePath")
    if not isinstance(image_path, str) or Path(image_path).name != target_image_path.name:
        raise ValueError("target annotation imagePath does not match target image")
    shapes = annotation.get("shapes")
    if not isinstance(shapes, list) or len(shapes) != 2:
        raise ValueError("target annotation must contain exactly 2 shapes")
    by_label: dict[str, dict[str, Any]] = {}
    for shape in shapes:
        label = shape.get("label")
        if label in by_label:
            raise ValueError(f"duplicate target truth label: {label}")
        by_label[label] = shape
    if set(by_label) != {"7", "Φ12.2"}:
        raise ValueError("target annotation labels must be exactly 7 and Φ12.2")
    line = by_label["7"]
    if line.get("shape_type") != "line" or len(line.get("points", [])) != 2:
        raise ValueError("7 must be a LabelMe line with exactly 2 points")
    arc = by_label["Φ12.2"]
    if arc.get("shape_type") != "linestrip" or len(arc.get("points", [])) != 77:
        raise ValueError("Φ12.2 must be a LabelMe linestrip with exactly 77 points")
    return line["points"], arc["points"]


def _fit_truth_circle(points: list[list[float]]) -> tuple[float, float, float]:
    array = np.asarray(points, dtype=np.float64)
    initial = fit_circle_kasa(array)
    return geometric_circle_fit(array, initial)


def _line_metrics(truth: list[list[float]], prediction: dict[str, Any]) -> dict[str, float]:
    truth_points = [tuple(float(v) for v in point) for point in truth]
    predicted_points = [tuple(float(v) for v in point) for point in prediction["pointsPx"]]
    direct = [math.dist(truth_points[0], predicted_points[0]),
              math.dist(truth_points[1], predicted_points[1])]
    swapped = [math.dist(truth_points[0], predicted_points[1]),
               math.dist(truth_points[1], predicted_points[0])]
    endpoint_errors = direct if sum(direct) <= sum(swapped) else swapped
    truth_length = math.dist(truth_points[0], truth_points[1])
    predicted_length = math.dist(predicted_points[0], predicted_points[1])
    return {
        "truthLengthPx": truth_length,
        "predictedLengthPx": predicted_length,
        "lengthAbsoluteErrorPx": abs(predicted_length - truth_length),
        "endpointMeanErrorPx": float(np.mean(endpoint_errors)),
        "endpointMaxErrorPx": float(max(endpoint_errors)),
    }


def _circle_metrics(truth: list[list[float]], prediction: dict[str, Any]) -> dict[str, Any]:
    truth_circle = _fit_truth_circle(truth)
    predicted_center = tuple(float(v) for v in prediction["centerPx"])
    predicted_radius = float(prediction["radiusPx"])
    truth_points = np.asarray(truth, dtype=np.float64)
    radial = np.abs(
        np.hypot(truth_points[:, 0] - predicted_center[0],
                 truth_points[:, 1] - predicted_center[1]) - predicted_radius
    )
    return {
        "truthCircle": {
            "centerPx": [truth_circle[0], truth_circle[1]],
            "radiusPx": truth_circle[2], "diameterPx": 2.0 * truth_circle[2],
        },
        "predictedCircle": {
            "centerPx": list(predicted_center), "radiusPx": predicted_radius,
            "diameterPx": 2.0 * predicted_radius,
        },
        "centerErrorPx": math.dist(truth_circle[:2], predicted_center),
        "radiusAbsoluteErrorPx": abs(predicted_radius - truth_circle[2]),
        "diameterAbsoluteErrorPx": abs(2.0 * predicted_radius - 2.0 * truth_circle[2]),
        "truthPointToPredictedCircleResidualPx": {
            "median": float(np.median(radial)),
            "p95": float(np.percentile(radial, 95.0)),
            "max": float(np.max(radial)),
        },
    }


def _reject_truth_leakage(result: dict[str, Any], annotation_path: Path) -> None:
    truth_resolved = annotation_path.resolve()
    for item in result.get("runtimeInputs", []):
        if item.get("role") == "target_annotation":
            raise ValueError("target annotation leaked into runtime input roles")
        raw_path = item.get("path")
        if raw_path and Path(raw_path).resolve() == truth_resolved:
            raise ValueError("target annotation leaked into runtime inputs")


def _detection_summary(result: dict[str, Any]) -> dict[str, Any]:
    registration = result["registration"]
    selected = registration.get("selected")
    candidates = []
    for candidate in registration.get("candidates", []):
        candidates.append({
            "orientationDeg": candidate.get("orientationDeg"),
            "score": candidate.get("score"),
            "valid": bool(candidate.get("valid")),
            "failureReasons": list(candidate.get("failureReasons") or []),
            "supportCount": candidate.get("supportCount"),
            "spatialCoverage": candidate.get("spatialCoverage"),
            "medianResidualPx": candidate.get("medianResidualPx"),
            "maxResidualPx": candidate.get("maxResidualPx"),
        })
    features: dict[str, Any] = {}
    for name in ("7", "Phi12.2"):
        feature = result["features"][name]
        features[name] = {
            "qualityStatus": feature["qualityStatus"],
            "measurementValid": feature["measurementValid"],
            "failureReason": feature["failureReason"],
            "sourceDetector": feature["sourceDetector"],
            "quality": feature["quality"],
        }
    return {
        "algorithmVersion": result["algorithmVersion"],
        "configVersion": result["configVersion"],
        "resultSchemaVersion": result["schemaVersion"],
        "timingMs": result["timingMs"],
        "qualityStatus": result["qualityStatus"],
        "registration": {
            "qualityStatus": "valid" if registration["registrationValid"] else "invalid",
            "registrationValid": registration["registrationValid"],
            "failureReason": registration["failureReason"],
            "selectedOrientationDeg": None if selected is None else selected.get("orientationDeg"),
            "transform": registration["transform"],
            "inverseTransform": registration["inverseTransform"],
            "transformDirection": registration["transformDirection"],
            "inverseTransformDirection": registration["inverseTransformDirection"],
            "candidateScoreMargin": registration.get("candidateScoreMargin"),
            "roundtripErrorPx": registration.get("roundtripErrorPx"),
            "candidates": candidates,
        },
        "features": features,
    }


def validate_acceptance_contract(report: dict[str, Any]) -> None:
    required = {
        "schemaVersion", "status", "hashes", "truthValidation",
        "detectionSummary", "metrics", "scope", "errors",
    }
    missing = sorted(required - report.keys())
    if missing:
        raise ValueError("acceptance report missing required fields: " + ",".join(missing))
    if report["schemaVersion"] != SCHEMA_VERSION:
        raise ValueError("unsupported acceptance schemaVersion")
    if report["status"] not in {"evaluated", "result_invalid", "input_rejected"}:
        raise ValueError("invalid acceptance status")
    if set(report["metrics"]) != {"7", "Phi12.2"}:
        raise ValueError("acceptance metrics must contain exactly 7 and Phi12.2")
    summary = report["detectionSummary"]
    if not isinstance(summary, dict) or not {
        "algorithmVersion", "configVersion", "resultSchemaVersion", "timingMs",
        "qualityStatus", "registration", "features",
    } <= summary.keys():
        raise ValueError("acceptance detectionSummary is incomplete")
    if report["scope"] != SCOPE:
        raise ValueError("invalid acceptance scope")
    json.dumps(report, ensure_ascii=False, allow_nan=False)


def evaluate_current_capture(
    result_path: Path,
    target_image_path: Path,
    target_annotation_path: Path,
    expected_image_sha256: str,
    expected_annotation_sha256: str,
) -> dict[str, Any]:
    image_sha = _sha256(target_image_path)
    annotation_sha = _sha256(target_annotation_path)
    if image_sha != expected_image_sha256:
        raise ValueError(f"image SHA-256 mismatch: expected {expected_image_sha256}, got {image_sha}")
    if annotation_sha != expected_annotation_sha256:
        raise ValueError(
            f"annotation SHA-256 mismatch: expected {expected_annotation_sha256}, got {annotation_sha}"
        )
    result = json.loads(result_path.read_text(encoding="utf-8"))
    validate_result_contract(result)
    _reject_truth_leakage(result, target_annotation_path)
    target_inputs = [
        item for item in result.get("runtimeInputs", []) if item.get("role") == "target_image"
    ]
    if len(target_inputs) != 1 or target_inputs[0].get("sha256") != image_sha:
        raise ValueError("detection result target image SHA-256 does not match acceptance image")
    truth_line, truth_arc = _strict_truth(target_annotation_path, target_image_path)
    features = result.get("features", {})
    line = features.get("7", {})
    circle = features.get("Phi12.2", {})
    metrics: dict[str, Any] = {"7": None, "Phi12.2": None}
    if line.get("measurementValid") and isinstance(line.get("target"), dict):
        metrics["7"] = _line_metrics(truth_line, line["target"])
    if circle.get("measurementValid") and isinstance(circle.get("target"), dict):
        metrics["Phi12.2"] = _circle_metrics(truth_arc, circle["target"])
    evaluated = metrics["7"] is not None and metrics["Phi12.2"] is not None
    report = {
        "schemaVersion": SCHEMA_VERSION,
        "status": "evaluated" if evaluated else "result_invalid",
        "hashes": {
            "targetImage": image_sha,
            "targetAnnotation": annotation_sha,
            "detectionResult": _sha256(result_path),
        },
        "truthValidation": {
            "valid": True, "shapeCount": 2, "labels": ["7", "Φ12.2"],
        },
        "detectionSummary": _detection_summary(result),
        "metrics": metrics,
        "scope": SCOPE,
        "errors": [] if evaluated else ["one_or_more_detection_features_invalid"],
    }
    validate_acceptance_contract(report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--result", required=True)
    parser.add_argument("--target-image", required=True)
    parser.add_argument("--target-annotation", required=True)
    parser.add_argument("--expected-image-sha256", required=True)
    parser.add_argument("--expected-annotation-sha256", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    report = evaluate_current_capture(
        Path(args.result), Path(args.target_image), Path(args.target_annotation),
        args.expected_image_sha256, args.expected_annotation_sha256,
    )
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(f"status={report['status']} report -> {output}")
    return 0 if report["status"] == "evaluated" else 2


if __name__ == "__main__":
    raise SystemExit(main())
