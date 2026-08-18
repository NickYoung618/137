#!/usr/bin/env python3
"""Trace which radial edge family the locked outer-circle detector selects.

This is a development-only, read-only diagnostic.  It calls the repository-
contained gyj edge primitive but never changes detector output or thresholds.
"""

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

from algorithms.slot_pose import circle_edge_candidates


def _finite(value: Any, label: str) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{label} must be finite")
    return result


enumerate_radial_edges = circle_edge_candidates.enumerate_radial_edge_candidates


def cluster_selected_offsets(
    records: list[dict[str, Any]], *, merge_px: float = 8.0,
) -> list[dict[str, Any]]:
    """Cluster selected radii without assuming how many physical circles exist."""
    if merge_px <= 0.0:
        raise ValueError("merge_px must be positive")
    points: list[tuple[float, float]] = []
    for record in records:
        points.append((
            _finite(record["selectedOffsetPx"], "selectedOffsetPx"),
            _finite(record["angleDeg"], "angleDeg") % 360.0,
        ))
    groups: list[list[tuple[float, float]]] = []
    for point in sorted(points):
        if not groups or abs(point[0] - float(np.median([item[0] for item in groups[-1]]))) > merge_px:
            groups.append([point])
        else:
            groups[-1].append(point)
    ranked = sorted(groups, key=lambda group: (-len(group), abs(float(np.median([p[0] for p in group])))))
    return [{
        "familyId": f"edge-family-{index:03d}",
        "count": len(group),
        "medianOffsetPx": float(np.median([point[0] for point in group])),
        "minOffsetPx": min(point[0] for point in group),
        "maxOffsetPx": max(point[0] for point in group),
        "sampleAnglesDeg": sorted(point[1] for point in group),
    } for index, group in enumerate(ranked, start=1)]


def summarize_switch_sectors(
    records: list[dict[str, Any]], *, primary_family_id: str,
) -> list[dict[str, Any]]:
    ordered = sorted(records, key=lambda item: float(item["angleDeg"]) % 360.0)
    if not ordered:
        return []
    angles = [float(item["angleDeg"]) % 360.0 for item in ordered]
    deltas = [((angles[(i + 1) % len(angles)] - angles[i]) % 360.0) for i in range(len(angles))]
    positive = [value for value in deltas if value > 1e-9]
    expected_step = float(np.median(positive)) if positive else 360.0
    switched = [str(item.get("familyId")) != primary_family_id for item in ordered]
    if not any(switched):
        return []
    if all(switched):
        runs = [list(range(len(ordered)))]
    else:
        starts = [i for i, flag in enumerate(switched) if flag and not switched[i - 1]]
        runs = []
        for start in starts:
            run = []
            i = start
            while switched[i]:
                run.append(i)
                nxt = (i + 1) % len(ordered)
                if ((angles[nxt] - angles[i]) % 360.0) > expected_step * 1.5:
                    break
                i = nxt
            runs.append(run)
    return [{
        "startDeg": angles[run[0]],
        "endDeg": angles[run[-1]],
        "wrapsBoundary": angles[run[0]] > angles[run[-1]],
        "sampleAnglesDeg": [angles[index] for index in run],
        "sampleCount": len(run),
    } for run in runs]


def _outside_worktree(path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    resolved = path.resolve()
    if resolved == root or root in resolved.parents:
        raise ValueError("trace output must be outside the Git worktree")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load_result(path: Path, image_name: str) -> dict[str, Any]:
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    matches = [item for item in records if Path(item["image"]["path"]).name == image_name]
    if len(matches) != 1:
        raise ValueError(f"expected exactly one result for {image_name}, found {len(matches)}")
    return matches[0]


def _proposal(result: dict[str, Any]) -> tuple[float, float, float]:
    localization = result["diagnostics"]["circleLocalization"]
    selected = localization.get("selectedCandidateId") or localization.get("bestCandidateId")
    candidates = {item["candidateId"]: item for item in localization.get("circleCandidates", [])}
    selected_candidate = candidates.get(selected)
    if selected_candidate is None and candidates:
        selected_candidate = next(iter(candidates.values()))
    proposal_id = (selected_candidate or {}).get("proposalId")
    proposals = {item["proposalId"]: item for item in localization.get("componentProposals", [])}
    proposal = proposals.get(proposal_id)
    if proposal is None:
        physical = result["diagnostics"]["physicalOuterCircle"]["searchPriorCircle"]
        return float(physical["centerX"]), float(physical["centerY"]), float(physical["radiusPx"])
    return float(proposal["centerX"]), float(proposal["centerY"]), float(proposal["radiusPx"])


def build_trace(image_path: Path, result: dict[str, Any], *, n_angles: int = 180) -> dict[str, Any]:
    gray = np.asarray(Image.open(image_path).convert("L"), dtype=np.float64)
    cx, cy, radius = _proposal(result)
    records: list[dict[str, Any]] = []
    missing: list[float] = []
    for index in range(n_angles):
        angle_deg = index * 360.0 / n_angles
        angle = math.radians(angle_deg)
        radii, profile = core.sample_radial(gray, cx, cy, angle, radius, 90)
        if len(radii) < 45:
            missing.append(angle_deg)
            continue
        values = core.smooth_1d(profile, 9)
        point = core.outer_boundary_edge_point(gray, (cx, cy), angle, radius)
        selected_radius = None if point is None else math.hypot(point[0] - cx, point[1] - cy)
        if selected_radius is None:
            missing.append(angle_deg)
        peaks = enumerate_radial_edges(radii, values, min_gradient=4.0, separation_px=3.0)
        record = {"angleDeg": angle_deg, "gradientPeaks": peaks, "selectedRadiusPx": selected_radius}
        if selected_radius is not None:
            record["selectedOffsetPx"] = selected_radius - radius
            records.append(record)
    clusters = cluster_selected_offsets(records, merge_px=18.0)
    for record in records:
        record["familyId"] = min(
            clusters, key=lambda item: abs(record["selectedOffsetPx"] - item["medianOffsetPx"])
        )["familyId"]
    rebuilt = []
    for cluster in clusters:
        members = [record for record in records if record["familyId"] == cluster["familyId"]]
        if not members:
            continue
        offsets = [float(record["selectedOffsetPx"]) for record in members]
        rebuilt.append({
            "familyId": cluster["familyId"],
            "count": len(members),
            "medianOffsetPx": float(np.median(offsets)),
            "minOffsetPx": min(offsets),
            "maxOffsetPx": max(offsets),
            "sampleAnglesDeg": sorted(float(record["angleDeg"]) for record in members),
        })
    clusters = sorted(rebuilt, key=lambda item: (-item["count"], abs(item["medianOffsetPx"])))
    primary = clusters[0]["familyId"] if clusters else None
    switch_sectors = [] if primary is None else summarize_switch_sectors(records, primary_family_id=primary)
    return {
        "schemaVersion": "circle-edge-family-trace/1",
        "developmentOnly": True,
        "detectorModified": False,
        "authoritative": False,
        "image": {"sha256": _sha256(image_path), "width": gray.shape[1], "height": gray.shape[0]},
        "searchPriorCircle": {"centerX": cx, "centerY": cy, "radiusPx": radius},
        "angleCount": n_angles,
        "selectedCount": len(records),
        "missingAnglesDeg": missing,
        "families": clusters,
        "primaryFamilyId": primary,
        "switchSectors": switch_sectors,
        "edgeFamilySwitchObserved": len(clusters) > 1,
        "perRay": records,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--results", type=Path, required=True, help="JSONL containing the baseline result")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--n-angles", type=int, default=180)
    args = parser.parse_args()
    _outside_worktree(args.output)
    if args.n_angles < 36:
        raise ValueError("n-angles must be >=36")
    report = build_trace(args.image, _load_result(args.results, args.image.name), n_angles=args.n_angles)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("schemaVersion", "selectedCount", "families", "switchSectors")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
