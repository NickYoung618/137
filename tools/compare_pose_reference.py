#!/usr/bin/env python3
"""Compare an offline manual fitted reference with a same-image runtime v2 result."""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from algorithms.slot_pose.angular_profile import circular_delta_deg
from tools.dataset_common import sha256_file, write_json


SCHEMA_VERSION = "slot-pose-reference-comparison/1"
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def _object(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be an object")
    return value


def _sha(value: Any, name: str) -> str:
    if not isinstance(value, str) or SHA256_PATTERN.fullmatch(value) is None:
        raise ValueError(f"{name} must be a lowercase SHA-256")
    return value


def _number(value: Any, name: str, *, positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise ValueError(f"{name} must be finite")
    result = float(value)
    if positive and result <= 0.0:
        raise ValueError(f"{name} must be positive")
    return result


def _circle(value: Any, name: str) -> tuple[float, float, float]:
    payload = _object(value, name)
    return (
        _number(payload.get("centerX"), f"{name}.centerX"),
        _number(payload.get("centerY"), f"{name}.centerY"),
        _number(payload.get("radiusPx"), f"{name}.radiusPx", positive=True),
    )


def compare_pose_reference(manual: dict[str, Any], runtime: dict[str, Any]) -> dict[str, Any]:
    """Return an offline development comparison; reject every non-comparable pair."""
    manual_algorithm = _object(manual.get("algorithm"), "manual.algorithm")
    if manual_algorithm.get("runtimeInputAllowed") is not False:
        raise ValueError("manual reference must be explicitly forbidden as runtime input")
    delegated = manual_algorithm.get("delegatedCircleFitFunctions")
    if delegated != ["fit_circle", "robust_fit_circle", "geometric_circle_fit"]:
        raise ValueError("manual reference must use the locked algebraic/robust/geometric fit chain")
    manual_source_hash = _sha(
        manual_algorithm.get("circleFitSourceSha256"), "manual.algorithm.circleFitSourceSha256",
    )
    manual_source = _object(manual.get("source"), "manual.source")
    manual_image_hash = _sha(manual_source.get("imageSha256"), "manual.source.imageSha256")
    annotation_hash = _sha(manual_source.get("annotationSha256"), "manual.source.annotationSha256")

    runtime_image = _object(runtime.get("image"), "runtime.image")
    runtime_image_hash = _sha(runtime_image.get("sha256"), "runtime.image.sha256")
    if runtime_image_hash != manual_image_hash:
        raise ValueError("manual and runtime image SHA-256 differ")
    runtime_algorithm = _object(runtime.get("algorithm"), "runtime.algorithm")
    runtime_assets = _object(runtime_algorithm.get("assets"), "runtime.algorithm.assets")
    runtime_source_hash = _sha(runtime_assets.get("sourceSha256"), "runtime source SHA-256")
    if runtime_source_hash != manual_source_hash:
        raise ValueError("manual and runtime circle-fit source SHA-256 differ")

    manual_circle_record = _object(manual.get("circle"), "manual.circle")
    if manual_circle_record.get("status") != "accepted":
        raise ValueError("manual fitted circle is not accepted")
    reference_circle = _circle(
        manual_circle_record.get("refinedRobustGeometricCircle"),
        "manual.circle.refinedRobustGeometricCircle",
    )
    point_count = manual_circle_record.get("pointCount")
    if isinstance(point_count, bool) or not isinstance(point_count, int) or point_count < 8:
        raise ValueError("manual circle pointCount must be >=8")
    coverage = _number(manual_circle_record.get("angularCoverageDeg"), "manual circle coverage", positive=True)
    residual = _object(manual_circle_record.get("refinedResidualPx"), "manual refined residual")
    residual_summary = {
        key: _number(residual.get(key), f"manual residual {key}") for key in ("median", "p95", "max")
    }

    diagnostics = _object(runtime.get("diagnostics"), "runtime.diagnostics")
    physical = _object(diagnostics.get("physicalOuterCircle"), "runtime physical outer circle")
    if physical.get("status") != "accepted":
        raise ValueError("runtime physical outer circle is not accepted")
    automatic_circle = _circle(physical.get("physicalCircle"), "runtime physical circle")
    recognition = _object(diagnostics.get("grooveRecognition"), "runtime groove recognition")
    if recognition.get("acceptedCount") != 1:
        raise ValueError("runtime result must contain exactly one accepted real groove")
    refinement = _object(diagnostics.get("grooveRefinement"), "runtime groove refinement")
    if refinement.get("status") != "accepted":
        raise ValueError("runtime groove refinement is not accepted")
    endpoints = refinement.get("openingEndpointProfileDeg")
    if not isinstance(endpoints, list) or len(endpoints) != 2:
        raise ValueError("runtime refinement must contain two endpoint angles")
    endpoint_profile = [_number(value, "runtime refinement endpoint") % 360.0 for value in endpoints]
    refinement_midpoint = _number(
        refinement.get("openingMidpointProfileDeg"), "runtime refinement midpoint",
    ) % 360.0
    pose = _object(diagnostics.get("singleGroovePose"), "runtime single groove pose")
    if pose.get("schemaVersion") != "slot-single-real-groove-pose/2" or pose.get("status") != "accepted":
        raise ValueError("runtime single-groove v2 pose is not accepted")
    image_measurement = _object(pose.get("imageMeasurement"), "runtime image measurement")
    automatic_image_up = _number(image_measurement.get("azimuthDeg"), "runtime image azimuth") % 360.0
    if abs(circular_delta_deg(automatic_image_up, (refinement_midpoint + 90.0) % 360.0)) > 1e-8:
        raise ValueError("runtime refined midpoint and pose measurement are inconsistent")

    manual_recognition = _object(manual.get("grooveRecognition"), "manual groove recognition")
    if manual_recognition.get("status") != "accepted":
        raise ValueError("manual groove geometry is not accepted")
    manual_measurement = _object(manual.get("measurement"), "manual measurement")
    manual_image_up = _number(
        manual_measurement.get("openingCenterAzimuthImageDeg"), "manual opening midpoint",
    ) % 360.0

    dx = automatic_circle[0] - reference_circle[0]
    dy = automatic_circle[1] - reference_circle[1]
    center_distance = math.hypot(dx, dy)
    radius_signed = automatic_circle[2] - reference_circle[2]
    center_ratio = center_distance / reference_circle[2]
    radius_ratio = radius_signed / reference_circle[2]
    angular_bound = math.degrees(math.asin(min(1.0, center_ratio)))
    theoretical_one_pixel = math.degrees(1.0 / reference_circle[2])
    opening_delta = circular_delta_deg(automatic_image_up, manual_image_up)
    return {
        "schemaVersion": SCHEMA_VERSION,
        "status": "COMPARED",
        "referenceStatus": "DEVELOPMENT_REFERENCE",
        "source": {
            "imageSha256": manual_image_hash,
            "annotationSha256": annotation_hash,
            "circleFitSourceSha256": manual_source_hash,
            "manualRecordSha256": None,
            "runtimeRecordSha256": None,
        },
        "manualReference": {
            "pointCount": point_count,
            "angularCoverageDeg": coverage,
            "circle": {"centerX": reference_circle[0], "centerY": reference_circle[1], "radiusPx": reference_circle[2]},
            "radialResidualPx": residual_summary,
        },
        "automatic": {
            "circle": {"centerX": automatic_circle[0], "centerY": automatic_circle[1], "radiusPx": automatic_circle[2]},
            "grooveEndpointProfileDeg": endpoint_profile,
        },
        "circleDelta": {
            "centerDxPx": dx,
            "centerDyPx": dy,
            "centerDistancePx": center_distance,
            "centerDistanceRatio": center_ratio,
            "radiusSignedPx": radius_signed,
            "radiusAbsolutePx": abs(radius_signed),
            "radiusSignedRatio": radius_ratio,
            "centerErrorAngularUpperBoundDeg": angular_bound,
        },
        "grooveOpeningDelta": {
            "manualImageUpClockwiseDeg": manual_image_up,
            "automaticImageUpClockwiseDeg": automatic_image_up,
            "automaticMinusManualCircularDeg": opening_delta,
            "absoluteCircularDeg": abs(opening_delta),
        },
        "resolutionBudget": {
            "referenceRadiusPx": reference_circle[2],
            "theoreticalOnePixelArcDeg": theoretical_one_pixel,
            "isProductionAccuracyEvidence": False,
        },
        "productionAccuracyClaimed": False,
        "runtimeInputAllowed": False,
        "limitations": [
            "One manually traced image is development evidence, not production metrology truth.",
            "The theoretical one-pixel arc angle excludes center, sidewall, distortion and repeatability errors.",
            "Formal accuracy requires original-BMP held-out data, a frozen annotation protocol and independent review.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manual-review", required=True, type=Path)
    parser.add_argument("--runtime-result", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    try:
        output.relative_to(PROJECT_ROOT.resolve())
    except ValueError:
        pass
    else:
        print("ERROR: comparison output must remain outside the Git worktree", file=sys.stderr)
        return 2
    try:
        manual = json.loads(args.manual_review.read_text(encoding="utf-8"))
        runtime = json.loads(args.runtime_result.read_text(encoding="utf-8"))
        comparison = compare_pose_reference(manual, runtime)
        comparison["source"]["manualRecordSha256"] = sha256_file(args.manual_review.resolve())
        comparison["source"]["runtimeRecordSha256"] = sha256_file(args.runtime_result.resolve())
        write_json(output, comparison)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(f"Wrote {output.name}: status={comparison['status']}, productionAccuracyClaimed=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
