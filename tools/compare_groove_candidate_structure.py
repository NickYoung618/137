#!/usr/bin/env python3
"""Compare per-candidate square-opening evidence without assigning truth."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
from typing import Any

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from algorithms.end_face import core
from algorithms.slot_pose.groove_refinement import refine_groove_opening


def _line_angle(line: dict[str, Any]) -> float:
    return math.degrees(math.atan2(float(line["b"]), float(line["a"]))) % 180.0


def _parallel_difference(left: dict[str, Any], right: dict[str, Any]) -> float:
    delta = abs(_line_angle(left) - _line_angle(right)) % 180.0
    return min(delta, 180.0 - delta)


def summarize_candidate_structure(
    candidate_id: str,
    assessment: dict[str, Any],
    refinement: dict[str, Any] | None,
) -> dict[str, Any]:
    base = {
        "candidateId": candidate_id,
        "authoritative": False,
        "humanTruthAppliedAtRuntime": False,
        "runtimeDecisionChanged": False,
        "recognitionEvidence": assessment,
    }
    if not isinstance(refinement, dict):
        return {**base, "status": "PIXEL_STRUCTURE_NOT_EVALUATED", "failedChecks": ["refinement_not_available"],
                "parallelDifferenceDeg": None, "endpointStructurePresent": False}
    left = refinement.get("startSide")
    right = refinement.get("endSide")
    complete = bool(
        refinement.get("status") == "accepted"
        and isinstance(left, dict) and isinstance(left.get("line"), dict)
        and isinstance(right, dict) and isinstance(right.get("line"), dict)
        and refinement.get("outerCircleIntersections") is not None
    )
    failed = list(refinement.get("failedChecks") or [])
    if not complete and not failed:
        failed.append("complete_two_wall_geometry_not_available")
    def side_summary(side: Any) -> dict[str, Any] | None:
        if not isinstance(side, dict):
            return None
        profile = side.get("profileEvidence") or {}
        return {
            "lineResidualP95Px": (side.get("lineResidualPx") or {}).get("p95"),
            "lineInlierRatio": side.get("lineInlierRatio"),
            "lineLongitudinalCoverage": side.get("lineLongitudinalCoverage"),
            "radialCoverage": profile.get("radialCoverage"),
            "edgeContrastMedian": side.get("edgeContrastMedian"),
            "edgeGradientMedianPerPx": side.get("edgeGradientMedianPerPx"),
            "intersectionPresent": side.get("intersection") is not None,
        }
    return {
        **base,
        "status": "COMPLETE_TWO_WALL_GEOMETRY" if complete else "PIXEL_STRUCTURE_INCOMPLETE",
        "failedChecks": failed,
        "parallelDifferenceDeg": _parallel_difference(left["line"], right["line"]) if complete else None,
        "endpointStructurePresent": bool(refinement.get("outerCircleIntersections") is not None),
        "openingWidthDeg": refinement.get("openingWidthDeg"),
        "leftWall": side_summary(left),
        "rightWall": side_summary(right),
    }


def _outside_worktree(path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    resolved = path.resolve()
    if resolved == root or root in resolved.parents:
        raise ValueError("candidate comparison output must be outside the Git worktree")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return digest


def _records(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def compare_result(result: dict[str, Any]) -> dict[str, Any]:
    image_path = Path(result["image"]["path"])
    gray = np.asarray(Image.open(image_path).convert("L"), dtype=np.float64)
    diagnostics = result["diagnostics"]
    physical = diagnostics["physicalOuterCircle"].get("physicalCircle")
    if not isinstance(physical, dict):
        return {"imageSha256": result["image"]["sha256"], "status": "CIRCLE_NOT_AVAILABLE", "candidates": []}
    center = (float(physical["centerX"]), float(physical["centerY"]))
    radius = float(physical["radiusPx"])
    scale = float(diagnostics["face"]["scale"])
    raw = {item["candidateId"]: item for item in diagnostics.get("rawCandidates", [])}
    assessments = {item["candidateId"]: item for item in (diagnostics.get("grooveRecognition") or {}).get("assessments", [])}
    config = diagnostics["quality"]["thresholds"]["groove_refinement"]
    summaries = []
    for candidate_id in sorted(raw):
        assessment = assessments.get(candidate_id, {})
        depth = assessment.get("radialDepthPx")
        refinement = None
        if isinstance(depth, (int, float)) and math.isfinite(float(depth)) and float(depth) > 0.0:
            candidate = {**raw[candidate_id], "radialDepthPx": float(depth)}
            refinement = refine_groove_opening(
                gray, center, radius, candidate, core.bilinear_sample, core.parabolic_peak,
                config, pixel_scale=scale,
            )
        summaries.append(summarize_candidate_structure(candidate_id, assessment, refinement))
    return {
        "imageSha256": _sha256(image_path),
        "status": "DIAGNOSTIC_ONLY",
        "baselineErrorCode": (result.get("error") or {}).get("code"),
        "candidates": summaries,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--image-name", action="append", default=[])
    args = parser.parse_args()
    _outside_worktree(args.output)
    selected = set(args.image_name)
    records = [item for item in _records(args.results) if not selected or Path(item["image"]["path"]).name in selected]
    report = {
        "schemaVersion": "groove-candidate-structure-comparison/1",
        "developmentOnly": True,
        "authoritative": False,
        "detectorModified": False,
        "humanTruthAppliedAtRuntime": False,
        "images": [compare_result(item) for item in records],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"schemaVersion": report["schemaVersion"], "imageCount": len(report["images"])}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
