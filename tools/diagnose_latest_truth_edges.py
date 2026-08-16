#!/usr/bin/env python3
"""Create external truth/prediction overlays and edge-profile diagnostics.

This is an offline evaluation tool.  It may read target LabelMe truth, while
the detector entry point deliberately cannot.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from algorithms.hole_2.main import (
    bilinear_sample,
    build_reference,
    contrast_stretch,
    load_gray,
    smooth_1d,
)
from tools.evaluate_current_capture import _fit_truth_circle, _strict_truth


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require_external_output(path: Path) -> Path:
    resolved = path.expanduser().resolve()
    if resolved == PROJECT_ROOT.resolve() or PROJECT_ROOT.resolve() in resolved.parents:
        raise ValueError("diagnostic output must remain outside the Git worktree")
    return resolved


def ordered_opposite_pair(
    derivative: np.ndarray,
    positions: np.ndarray,
    *,
    minimum_peak: float = 4.0,
    minimum_width: float = 3.0,
    maximum_width: float = 16.0,
) -> dict[str, float] | None:
    """Select a dark-band negative/positive edge pair without a length prior."""
    candidates: list[dict[str, float]] = []
    for negative in range(1, len(derivative) - 1):
        negative_peak = -float(derivative[negative])
        if (
            negative_peak < minimum_peak
            or negative_peak < -float(derivative[negative - 1])
            or negative_peak < -float(derivative[negative + 1])
        ):
            continue
        for positive in range(negative + 1, len(derivative) - 1):
            width = float(positions[positive] - positions[negative])
            if width < minimum_width:
                continue
            if width > maximum_width:
                break
            positive_peak = float(derivative[positive])
            if (
                positive_peak < minimum_peak
                or positive_peak < float(derivative[positive - 1])
                or positive_peak < float(derivative[positive + 1])
            ):
                continue
            candidates.append({
                "negativePositionPx": float(positions[negative]),
                "positivePositionPx": float(positions[positive]),
                "negativePeak": negative_peak,
                "positivePeak": positive_peak,
                "pairWidthPx": width,
                "centerPositionPx": float(
                    (positions[negative] + positions[positive]) * 0.5
                ),
                "score": float(min(negative_peak, positive_peak)),
            })
    return max(candidates, key=lambda item: item["score"], default=None)


def _d7_profiles(
    gray: np.ndarray,
    truth_line: list[list[float]],
    tangent_offsets: list[float],
) -> dict[str, Any]:
    first = np.asarray(truth_line[0], dtype=np.float64)
    second = np.asarray(truth_line[1], dtype=np.float64)
    axis = second - first
    axis /= float(np.linalg.norm(axis))
    tangent = np.asarray([-axis[1], axis[0]], dtype=np.float64)
    samples: list[dict[str, Any]] = []
    center_positions: dict[str, list[float]] = {"p1": [], "p2": []}
    offsets = np.arange(-24.0, 25.0, dtype=np.float64)
    mids = (offsets[:-1] + offsets[1:]) * 0.5
    for tangent_offset in tangent_offsets:
        for endpoint_name, endpoint in (("p1", first), ("p2", second)):
            origin = endpoint + tangent_offset * tangent
            profile = bilinear_sample(
                gray,
                origin[0] + offsets * axis[0],
                origin[1] + offsets * axis[1],
            )
            smoothed = smooth_1d(profile, 7)
            derivative = np.diff(smoothed)
            pair = ordered_opposite_pair(derivative, mids)
            if pair is not None:
                center_positions[endpoint_name].append(pair["centerPositionPx"])
            samples.append({
                "endpoint": endpoint_name,
                "tangentOffsetPx": float(tangent_offset),
                "axisOffsetsPx": offsets.tolist(),
                "intensity": [float(value) for value in smoothed],
                "gradientPositionsPx": mids.tolist(),
                "signedGradient": [float(value) for value in derivative],
                "selectedPair": pair,
            })
    return {
        "axisUnit": axis.tolist(),
        "tangentUnit": tangent.tolist(),
        "samples": samples,
        "pairedCenterOffsetMedianPx": {
            side: None if not values else float(np.median(values))
            for side, values in center_positions.items()
        },
        "pairedSupportCount": {
            side: len(values) for side, values in center_positions.items()
        },
    }


def _reference_edge_phase(reference: Any, shape: Any) -> float:
    offsets = np.arange(-12.0, 13.0, dtype=np.float64)
    values: list[float] = []
    cx, cy, radius = shape.circle
    for angle in shape.template_angles:
        profile = bilinear_sample(
            reference.gray,
            cx + (radius + offsets) * math.cos(float(angle)),
            cy + (radius + offsets) * math.sin(float(angle)),
        )
        inner = float(np.median(profile[:5]))
        outer = float(np.median(profile[-5:]))
        delta = outer - inner
        if abs(delta) < 12.0:
            continue
        values.append(float((profile[12] - inner) / delta))
    if not values:
        raise ValueError("reference Phi12.2 edge phase is unavailable")
    return float(np.clip(np.median(values), 0.05, 0.95))


def _phi_profile(
    gray: np.ndarray,
    truth_circle: tuple[float, float, float],
    truth_arc: list[list[float]],
    predicted_circle: tuple[float, float, float],
    reference_phase: float,
) -> dict[str, Any]:
    cx, cy, radius = truth_circle
    points = np.asarray(truth_arc, dtype=np.float64)
    angles = np.unwrap(np.arctan2(points[:, 1] - cy, points[:, 0] - cx))
    sampled_angles = np.linspace(float(angles.min()), float(angles.max()), 120)
    offsets = np.arange(-12.0, 13.0, dtype=np.float64)
    profiles = []
    for angle in sampled_angles:
        profiles.append(bilinear_sample(
            gray,
            cx + (radius + offsets) * math.cos(float(angle)),
            cy + (radius + offsets) * math.sin(float(angle)),
        ))
    median_profile = np.median(np.asarray(profiles), axis=0)
    smoothed = smooth_1d(median_profile, 5)
    derivative = np.diff(smoothed)
    mids = (offsets[:-1] + offsets[1:]) * 0.5
    positive_index = int(np.argmax(derivative))
    negative_index = int(np.argmin(derivative))
    return {
        "truthCircle": {"centerPx": [cx, cy], "radiusPx": radius},
        "predictedCircle": {
            "centerPx": [predicted_circle[0], predicted_circle[1]],
            "radiusPx": predicted_circle[2],
        },
        "truthArcCoverageDeg": float(math.degrees(float(np.ptp(angles)))),
        "radialOffsetsFromTruthPx": offsets.tolist(),
        "medianIntensity": [float(value) for value in smoothed],
        "gradientPositionsFromTruthPx": mids.tolist(),
        "medianSignedRadialGradient": [float(value) for value in derivative],
        "strongestPositiveGradient": {
            "offsetFromTruthRadiusPx": float(mids[positive_index]),
            "value": float(derivative[positive_index]),
        },
        "strongestNegativeGradient": {
            "offsetFromTruthRadiusPx": float(mids[negative_index]),
            "value": float(derivative[negative_index]),
        },
        "referenceEdgePhaseFraction": reference_phase,
    }


def _overlay(
    image_path: Path,
    truth_line: list[list[float]],
    truth_circle: tuple[float, float, float],
    predicted_line: list[list[float]],
    predicted_circle: tuple[float, float, float],
    output: Path,
) -> None:
    image = Image.open(image_path).convert("RGB")
    draw = ImageDraw.Draw(image)
    for circle, color in ((truth_circle, (0, 255, 0)), (predicted_circle, (255, 0, 0))):
        cx, cy, radius = circle
        draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), outline=color, width=5)
    draw.line([tuple(point) for point in truth_line], fill=(0, 255, 0), width=7)
    draw.line([tuple(point) for point in predicted_line], fill=(255, 0, 0), width=7)
    for points, color in ((truth_line, (0, 255, 0)), (predicted_line, (255, 0, 0))):
        for x, y in points:
            draw.ellipse((x - 7, y - 7, x + 7, y + 7), fill=color)
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output)


def diagnose(
    *,
    result_path: Path,
    reference_annotation: Path,
    reference_image: Path,
    target_image: Path,
    target_annotation: Path,
    expected_image_sha256: str,
    expected_annotation_sha256: str,
    output_dir: Path,
) -> dict[str, Any]:
    output_dir = require_external_output(output_dir)
    image_hash = sha256_file(target_image)
    annotation_hash = sha256_file(target_annotation)
    if image_hash != expected_image_sha256:
        raise ValueError("target image SHA-256 mismatch")
    if annotation_hash != expected_annotation_sha256:
        raise ValueError("target annotation SHA-256 mismatch")
    result = json.loads(result_path.read_text(encoding="utf-8"))
    truth_line, truth_arc = _strict_truth(target_annotation, target_image)
    truth_circle = _fit_truth_circle(truth_arc)
    predicted_line = result["features"]["7"]["target"]["pointsPx"]
    predicted_phi = result["features"]["Phi12.2"]["target"]
    predicted_circle = (
        float(predicted_phi["centerPx"][0]),
        float(predicted_phi["centerPx"][1]),
        float(predicted_phi["radiusPx"]),
    )
    reference = build_reference(reference_annotation, reference_image)
    shape = next(item for item in reference.shapes if item.sanitized == "Phi12_2")
    reference_phase = _reference_edge_phase(reference, shape)
    gray = contrast_stretch(load_gray(target_image))
    d7 = _d7_profiles(gray, truth_line, [-30.0, -20.0, -10.0, 0.0, 10.0, 20.0, 30.0])
    phi = _phi_profile(gray, truth_circle, truth_arc, predicted_circle, reference_phase)
    output_dir.mkdir(parents=True, exist_ok=True)
    _overlay(
        target_image, truth_line, truth_circle, predicted_line, predicted_circle,
        output_dir / "truth-prediction-overlay.png",
    )
    (output_dir / "d7-edge-profiles.json").write_text(
        json.dumps(d7, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    (output_dir / "phi-radial-profile.json").write_text(
        json.dumps(phi, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    predicted_length = math.dist(*predicted_line)
    truth_length = math.dist(*truth_line)
    summary = {
        "schemaVersion": "hole2-latest-truth-edge-diagnostic/1",
        "hashes": {"targetImage": image_hash, "targetAnnotation": annotation_hash},
        "d7": {
            "truthLengthPx": truth_length,
            "predictedLengthPx": predicted_length,
            "lengthAbsoluteErrorPx": abs(predicted_length - truth_length),
            "pairedCenterOffsetMedianPx": d7["pairedCenterOffsetMedianPx"],
            "pairedSupportCount": d7["pairedSupportCount"],
            "rootCause": "single_outer_gradient_peak_selected_instead_of_dark_contour_centerline",
        },
        "Phi12.2": {
            "truthDiameterPx": 2.0 * truth_circle[2],
            "predictedDiameterPx": 2.0 * predicted_circle[2],
            "diameterAbsoluteErrorPx": abs(2.0 * predicted_circle[2] - 2.0 * truth_circle[2]),
            "centerErrorPx": math.dist(truth_circle[:2], predicted_circle[:2]),
            "referencePolarityDelta": float(shape.polarity),
            "referenceEdgePhaseFraction": reference_phase,
            "rootCause": "magnitude_only_primary_circle_score_did_not_enforce_positive_outer_edge_phase",
        },
        "legend": {"truth": "green", "prediction": "red"},
    }
    (output_dir / "diagnostic-summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--result", required=True, type=Path)
    parser.add_argument("--reference-annotation", required=True, type=Path)
    parser.add_argument("--reference-image", required=True, type=Path)
    parser.add_argument("--target-image", required=True, type=Path)
    parser.add_argument("--target-annotation", required=True, type=Path)
    parser.add_argument("--expected-image-sha256", required=True)
    parser.add_argument("--expected-annotation-sha256", required=True)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    summary = diagnose(
        result_path=args.result,
        reference_annotation=args.reference_annotation,
        reference_image=args.reference_image,
        target_image=args.target_image,
        target_annotation=args.target_annotation,
        expected_image_sha256=args.expected_image_sha256,
        expected_annotation_sha256=args.expected_annotation_sha256,
        output_dir=args.output_dir,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
