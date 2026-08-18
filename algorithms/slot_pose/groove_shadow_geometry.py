"""Rotation-relative candidate geometry for fixture-shadow diagnostics.

This module intentionally has no image identity, absolute-angle or manual-truth
input. Pixel-level fixture body and U-contour evidence is added by the runtime
caller; this primitive only describes bounded angular overlap between regions
that were independently extracted from the image.
"""

from __future__ import annotations

import math
from typing import Any, Callable

import numpy as np


SCHEMA_VERSION = "groove-shadow-relative-geometry/1"
MAX_CANDIDATES = 16
FLOOR_STRATEGY_VERSION = "five-track-curved-floor-family-v1"


def _otsu(values: np.ndarray) -> int:
    array = np.clip(np.asarray(values), 0.0, 255.0).astype(np.uint8, copy=False)
    if array.size == 0:
        return 0
    histogram = np.bincount(array.reshape(-1), minlength=256).astype(float)
    total_count = float(array.size)
    total_sum = float(np.dot(np.arange(256, dtype=float), histogram))
    background_count = background_sum = 0.0
    best_score = -1.0
    best = 0
    for threshold in range(255):
        background_count += histogram[threshold]
        background_sum += threshold * histogram[threshold]
        foreground_count = total_count - background_count
        if background_count <= 0.0 or foreground_count <= 0.0:
            continue
        left_mean = background_sum / background_count
        right_mean = (total_sum - background_sum) / foreground_count
        score = background_count * foreground_count * (left_mean - right_mean) ** 2
        if score > best_score:
            best_score = score
            best = threshold
    return best


def _circular_true_runs(mask: np.ndarray) -> list[tuple[int, int]]:
    flags = np.asarray(mask, dtype=bool)
    count = len(flags)
    if count == 0 or not bool(np.any(flags)) or bool(np.all(flags)):
        return []
    starts = [index for index in range(count) if flags[index] and not flags[index - 1]]
    runs = []
    for start in starts:
        length = 0
        while length < count and flags[(start + length) % count]:
            length += 1
        runs.append((start, length))
    return runs


def detect_stationary_fixture_sectors(
    gray: np.ndarray, center: tuple[float, float], outer_radius: float, *,
    angular_sample_count: int = 720,
) -> dict[str, Any]:
    """Verify two textured exterior fixture sectors around the housing.

    The threshold is derived from the current frame. No expected angle, image
    identity or reviewed label is accepted as input.
    """
    base = {
        "schemaVersion": "stationary-two-body-fixture-evidence/1",
        "status": "not_evaluated", "fixtureBodiesVerified": False,
        "angularSampleCount": angular_sample_count,
        "radialSampleCount": 32, "frameDerivedThreshold": None,
        "sectors": [], "failedChecks": [],
        "fixedAngleApplied": False, "manualTruthAppliedAtRuntime": False,
    }
    image = np.asarray(gray)
    if (
        image.ndim != 2 or image.size == 0 or not np.isfinite(image).all()
        or len(center) != 2
        or not all(math.isfinite(float(value)) for value in center)
        or not math.isfinite(float(outer_radius)) or float(outer_radius) <= 0.0
        or isinstance(angular_sample_count, bool)
        or not isinstance(angular_sample_count, int)
        or not 180 <= angular_sample_count <= 1440
    ):
        return {**base, "failedChecks": ["fixture_geometry_input_invalid"]}
    angles = np.linspace(0.0, 360.0, angular_sample_count, endpoint=False)
    radians = np.radians(angles)
    offsets = np.linspace(0.02 * outer_radius, 0.45 * outer_radius, 32)
    radii = outer_radius + offsets[:, None]
    xs = np.rint(float(center[0]) + radii * np.cos(radians)).astype(int)
    ys = np.rint(float(center[1]) + radii * np.sin(radians)).astype(int)
    valid = (
        (xs >= 0) & (xs < image.shape[1])
        & (ys >= 0) & (ys < image.shape[0])
    )
    values = np.zeros(xs.shape, dtype=float)
    values[valid] = image[ys[valid], xs[valid]]
    minimum_valid = 10
    medians = np.full(angular_sample_count, np.nan, dtype=float)
    textures = np.full(angular_sample_count, np.nan, dtype=float)
    valid_counts = np.count_nonzero(valid, axis=0)
    for index in np.flatnonzero(valid_counts >= minimum_valid):
        samples = values[:, index][valid[:, index]]
        medians[index] = float(np.median(samples))
        textures[index] = float(np.std(samples))
    finite = medians[np.isfinite(medians)]
    if finite.size < angular_sample_count // 3 or float(np.max(finite) - np.min(finite)) <= 1.0:
        return {**base, "failedChecks": ["fixture_exterior_contrast_unavailable"]}
    threshold = _otsu(finite)
    foreground = np.isfinite(medians) & (medians > threshold)
    # Close only isolated one-sample holes caused by surface texture.
    foreground = foreground | (np.roll(foreground, 1) & np.roll(foreground, -1))
    minimum_run = max(6, angular_sample_count // 30)
    runs = [item for item in _circular_true_runs(foreground) if item[1] >= minimum_run]
    sectors = []
    step = 360.0 / angular_sample_count
    for index, (start, length) in enumerate(runs, start=1):
        indices = np.asarray([(start + offset) % angular_sample_count for offset in range(length)])
        center_angle = float((angles[start] + 0.5 * (length - 1) * step) % 360.0)
        sine = math.sin(math.radians(center_angle))
        role = "lower_fixture" if sine > 0.0 else "upper_fixture"
        sectors.append({
            "sectorId": f"fixture-sector-{index:02d}", "role": role,
            "startDeg": float(angles[start]), "spanDeg": float(length * step),
            "centerDeg": center_angle, "wrapsBoundary": start + length > angular_sample_count,
            "medianGray": float(np.nanmedian(medians[indices])),
            "textureStd": float(np.nanmedian(textures[indices])),
            "radialForegroundOccupancy": float(np.mean(
                values[:, indices][valid[:, indices]] > threshold
            )),
            "validRayRatio": float(np.mean(valid_counts[indices] >= minimum_valid)),
        })
    roles = [item["role"] for item in sectors]
    verified = len(sectors) == 2 and sorted(roles) == ["lower_fixture", "upper_fixture"]
    failed = [] if verified else ["stationary_fixture_pair_not_unique"]
    return {
        **base, "status": "verified" if verified else "not_evaluated",
        "fixtureBodiesVerified": verified,
        "frameDerivedThreshold": float(threshold),
        "sectors": sectors[:4], "failedChecks": failed,
    }


def _finite_candidate(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    identifier = value.get("candidateId")
    if not isinstance(identifier, str) or not identifier:
        return None
    numbers: dict[str, float] = {}
    for key in ("centerDeg", "halfWidthDeg"):
        item = value.get(key)
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            return None
        number = float(item)
        if not math.isfinite(number):
            return None
        numbers[key] = number
    if not 0.0 < numbers["halfWidthDeg"] < 90.0:
        return None
    return {
        "candidateId": identifier,
        "centerDeg": numbers["centerDeg"] % 360.0,
        "halfWidthDeg": numbers["halfWidthDeg"],
    }


def _distance(left: float, right: float) -> float:
    return abs((left - right + 180.0) % 360.0 - 180.0)


def assess_candidate_fixture_overlap(
    candidate: dict[str, Any], fixture_evidence: dict[str, Any],
) -> dict[str, Any]:
    """Classify overlap with fixture bodies detected in this same frame.

    The lower body is a false-source risk only.  The upper body is the only
    body allowed to carry an occlusion-risk interpretation.  Neither role is
    inferred from a learned/sample angle: roles come from the verified
    per-frame image geometry emitted by ``detect_stationary_fixture_sectors``.
    """
    base = {
        "schemaVersion": "candidate-fixture-overlap/1",
        "status": "not_evaluated", "candidateId": None,
        "overlapRole": None, "overlapSectorIds": [],
        "lowerFixtureFalseSourceRisk": False,
        "upperFixtureOcclusionRisk": False,
        "candidateSelectionUsedFixedAngle": False,
        "failedChecks": [],
    }
    normalized = _finite_candidate(candidate)
    if normalized is None:
        return {**base, "failedChecks": ["candidate_geometry_invalid"]}
    base["candidateId"] = normalized["candidateId"]
    if (
        not isinstance(fixture_evidence, dict)
        or fixture_evidence.get("schemaVersion")
        != "stationary-two-body-fixture-evidence/1"
        or fixture_evidence.get("status") != "verified"
        or fixture_evidence.get("fixtureBodiesVerified") is not True
    ):
        return {**base, "failedChecks": ["fixture_bodies_not_verified"]}
    overlaps: list[dict[str, Any]] = []
    for sector in fixture_evidence.get("sectors", []):
        if not isinstance(sector, dict) or sector.get("role") not in {
            "upper_fixture", "lower_fixture",
        }:
            return {**base, "failedChecks": ["fixture_sector_invalid"]}
        try:
            center = float(sector["centerDeg"]) % 360.0
            span = float(sector["spanDeg"])
        except (KeyError, TypeError, ValueError):
            return {**base, "failedChecks": ["fixture_sector_invalid"]}
        if not math.isfinite(center) or not math.isfinite(span) or not 0.0 < span < 180.0:
            return {**base, "failedChecks": ["fixture_sector_invalid"]}
        if _distance(normalized["centerDeg"], center) <= normalized["halfWidthDeg"] + span / 2.0:
            overlaps.append(sector)
    roles = sorted({str(item["role"]) for item in overlaps})
    overlap_role = roles[0] if len(roles) == 1 else ("multiple_fixture_bodies" if roles else "none")
    return {
        **base, "status": "evaluated", "overlapRole": overlap_role,
        "overlapSectorIds": sorted(str(item["sectorId"]) for item in overlaps),
        "lowerFixtureFalseSourceRisk": "lower_fixture" in roles,
        "upperFixtureOcclusionRisk": "upper_fixture" in roles,
    }


def build_fixture_source_exclusion(
    candidate: dict[str, Any], fixture_evidence: dict[str, Any],
    refinement: dict[str, Any], *, groove_floor_evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build fail-closed source evidence consumed by recovery gates.

    Two fitted walls are deliberately insufficient to claim a U-shaped groove:
    a fixture edge can also form two plausible lines.  Until a separate floor
    detector supplies accepted evidence, ``uContourComplete`` remains false.
    """
    overlap = assess_candidate_fixture_overlap(candidate, fixture_evidence)
    floor = groove_floor_evidence if isinstance(groove_floor_evidence, dict) else {
        "schemaVersion": "groove-floor-evidence/1", "status": "not_evaluated",
        "failedChecks": ["groove_floor_not_evaluated"],
    }
    bodies_verified = fixture_evidence.get("fixtureBodiesVerified") is True
    walls_complete = (
        isinstance(refinement, dict) and refinement.get("status") == "accepted"
        and isinstance(refinement.get("startSide"), dict)
        and isinstance(refinement.get("endSide"), dict)
        and isinstance(refinement.get("outerCircleIntersections"), list)
        and len(refinement["outerCircleIntersections"]) == 2
    )
    floor_complete = floor.get("status") == "accepted"
    u_complete = bool(walls_complete and floor_complete)
    overlap_role = overlap.get("overlapRole")
    # The lower body cannot occlude the groove in this fixture geometry.  A
    # candidate coincident with it is therefore a fixture-source candidate.
    # The upper body can overlap a real groove, so a separately proven curved
    # floor plus both walls may exclude the fixture source there.
    excluded = bool(
        bodies_verified and overlap.get("status") == "evaluated" and u_complete
        and overlap_role in {"none", "upper_fixture"}
    )
    failures: list[str] = []
    if not bodies_verified:
        failures.append("fixture_bodies_not_verified")
    if not walls_complete:
        failures.append("two_sidewalls_not_complete")
    if not floor_complete:
        failures.append("groove_floor_not_complete")
    if overlap_role == "lower_fixture":
        failures.append("lower_fixture_false_candidate")
    elif overlap_role == "upper_fixture" and not u_complete:
        failures.append("upper_fixture_shadow_overlap")
    elif overlap_role == "multiple_fixture_bodies":
        failures.append("multiple_fixture_overlap")
    return {
        "schemaVersion": "fixture-groove-source-exclusion/1",
        "status": "verified" if excluded else "rejected",
        "fixtureBodiesVerified": bodies_verified,
        "candidateFixtureOverlap": overlap,
        "twoSidewallsComplete": walls_complete,
        "grooveFloorEvidence": floor,
        "uContourComplete": u_complete,
        "fixtureSourceExcluded": excluded,
        "candidateSelectionUsedFixedAngle": False,
        "failedChecks": failures,
    }


def assess_groove_floor_evidence(
    gray: np.ndarray, center: tuple[float, float], outer_radius: float,
    candidate: dict[str, Any],
    bilinear_sample: Callable[[np.ndarray, np.ndarray, np.ndarray], np.ndarray],
    *, pixel_scale: float = 1.0, search_depth_px: float | None = None,
) -> dict[str, Any]:
    """Detect a bounded curved inner floor joining the two groove walls.

    Five radial tracks are sampled inside the candidate.  A real U-shaped
    floor must have a bounded cross-track transition family with center and
    bilateral support, the middle track must be deeper than the flanks, and
    paired tracks must be geometrically symmetric.  One ambiguous outer flank
    may be resolved only by that global family. Thresholds are locked by the strategy version;
    no reviewed label, filename, target angle or fixture angle is accepted.
    """
    base = {
        "schemaVersion": "groove-floor-evidence/1",
        "strategyVersion": FLOOR_STRATEGY_VERSION,
        "status": "not_evaluated", "candidateId": candidate.get("candidateId") if isinstance(candidate, dict) else None,
        "trackCount": 5, "acceptedTrackCount": 0, "tracks": [],
        "curvatureDepthPx": None, "flankSymmetryErrorPx": None,
        "depthSearchSource": None, "depthSearchPx": None,
        "checks": [], "failedChecks": [],
        "fixedAngleApplied": False, "manualTruthAppliedAtRuntime": False,
    }
    image = np.asarray(gray)
    normalized = _finite_candidate(candidate)
    try:
        depth = float(candidate["radialDepthPx"])
    except (KeyError, TypeError, ValueError):
        depth = math.nan
    depth_source = "recognition_radial_depth"
    if not math.isfinite(depth) or depth <= 0.0:
        if (
            isinstance(search_depth_px, (int, float)) and not isinstance(search_depth_px, bool)
            and math.isfinite(float(search_depth_px)) and float(search_depth_px) > 0.0
        ):
            depth = float(search_depth_px)
            depth_source = "bounded_independent_search"
    base["depthSearchSource"] = depth_source
    base["depthSearchPx"] = depth if math.isfinite(depth) and depth > 0.0 else None
    if (
        normalized is None or image.ndim != 2 or image.size == 0
        or not math.isfinite(depth) or depth <= 0.0
        or len(center) != 2 or not all(math.isfinite(float(value)) for value in center)
        or not math.isfinite(float(outer_radius)) or outer_radius <= 0.0
        or not math.isfinite(float(pixel_scale)) or pixel_scale <= 0.0
    ):
        return {**base, "failedChecks": ["groove_floor_input_invalid"]}
    sample_count = 96
    # Ascending radius: inner metal first, then the dark groove after its floor.
    radii = np.linspace(outer_radius - 1.35 * depth, outer_radius - 0.25 * depth, sample_count)
    offsets = np.asarray([-0.65, -0.30, 0.0, 0.30, 0.65]) * normalized["halfWidthDeg"]
    tracks: list[dict[str, Any]] = []
    for offset in offsets:
        angle = math.radians(normalized["centerDeg"] + float(offset))
        xs = float(center[0]) + radii * math.cos(angle)
        ys = float(center[1]) + radii * math.sin(angle)
        try:
            raw = np.asarray(bilinear_sample(image, xs, ys), dtype=float)
        except Exception:
            return {**base, "failedChecks": ["groove_floor_sampling_failed"]}
        if raw.shape != radii.shape or not np.isfinite(raw).all():
            return {**base, "failedChecks": ["groove_floor_samples_invalid"]}
        smooth = np.convolve(raw, np.ones(5, dtype=float) / 5.0, mode="same")
        falling = -np.gradient(smooth, radii)
        # Ignore convolution boundaries and retain local maxima in the physical
        # floor-depth band only.
        inferred_depth = outer_radius - radii
        eligible = (
            (np.arange(sample_count) >= 4) & (np.arange(sample_count) < sample_count - 4)
            & (inferred_depth >= 0.35 * depth) & (inferred_depth <= 1.25 * depth)
        )
        peaks = [
            index for index in range(2, sample_count - 2)
            if eligible[index] and falling[index] > 0.0
            and falling[index] >= falling[index - 1] and falling[index] > falling[index + 1]
        ]
        peaks.sort(key=lambda index: (-float(falling[index]), index))
        if not peaks:
            tracks.append({
                "offsetFraction": float(offset / normalized["halfWidthDeg"]),
                "status": "failed", "floorDepthPx": None,
                "peakGradientPerPx": None, "innerOuterContrast": None,
                "dominanceRatio": None, "failedChecks": ["floor_edge_not_found"],
            })
            continue
        best = peaks[0]
        second = float(falling[peaks[1]]) if len(peaks) > 1 else 0.0
        dominance = float(falling[best]) / max(second, 1e-9)
        inner = float(np.median(raw[max(0, best - 8):max(1, best - 3)]))
        outer = float(np.median(raw[min(sample_count - 1, best + 3):min(sample_count, best + 8)]))
        contrast = inner - outer
        noise = float(np.median(np.abs(falling[eligible] - np.median(falling[eligible]))))
        failed = []
        if contrast < max(8.0, 4.0 * noise):
            failed.append("floor_contrast_insufficient")
        if len(peaks) > 1 and dominance < 1.25:
            failed.append("floor_edge_not_unique")
        tracks.append({
            "offsetFraction": float(offset / normalized["halfWidthDeg"]),
            "status": "accepted" if not failed else "failed",
            "floorDepthPx": float(inferred_depth[best]),
            "peakGradientPerPx": float(falling[best]),
            "innerOuterContrast": contrast, "dominanceRatio": dominance,
            "failedChecks": failed,
        })
    accepted = [item for item in tracks if item["status"] == "accepted"]
    base["tracks"] = tracks
    base["acceptedTrackCount"] = len(accepted)
    support_complete = bool(
        len(accepted) >= 4
        and (
            tracks[2]["status"] == "accepted"
            or all(tracks[index]["status"] == "accepted" for index in (0, 1, 3, 4))
        )
        and any(tracks[index]["status"] == "accepted" for index in (0, 1))
        and any(tracks[index]["status"] == "accepted" for index in (3, 4))
        and all(item["floorDepthPx"] is not None for item in tracks)
    )
    if not support_complete:
        return {**base, "status": "rejected", "failedChecks": ["floor_track_support_incomplete"]}
    depths = [float(item["floorDepthPx"]) for item in tracks]
    curvature = depths[2] - 0.5 * (depths[0] + depths[4])
    symmetry = max(abs(depths[0] - depths[4]), abs(depths[1] - depths[3]))
    checks = [
        {
            "checkId": "curved_floor_depth", "value": curvature,
            "threshold": 0.08 * depth, "thresholdKind": "min",
            "margin": curvature - 0.08 * depth,
            "passed": curvature >= 0.08 * depth,
        },
        {
            "checkId": "paired_floor_symmetry", "value": symmetry,
            "threshold": 0.25 * depth, "thresholdKind": "max",
            "margin": 0.25 * depth - symmetry,
            "passed": symmetry <= 0.25 * depth,
        },
    ]
    failed = [item["checkId"] for item in checks if item["passed"] is False]
    return {
        **base, "status": "accepted" if not failed else "rejected",
        "curvatureDepthPx": curvature, "flankSymmetryErrorPx": symmetry,
        "checks": checks, "failedChecks": failed,
    }


def assess_relative_shadow_geometry(
    candidates: list[dict[str, Any]], target_candidate_id: str, *,
    search_margin_deg: float,
) -> dict[str, Any]:
    """Describe target/competitor overlap without fixed locations or labels."""
    base = {
        "schemaVersion": SCHEMA_VERSION,
        "status": "not_evaluated",
        "targetCandidateId": target_candidate_id,
        "candidateCount": len(candidates) if isinstance(candidates, list) else 0,
        "overlapEvidence": False,
        "overlappingCandidateCount": 0,
        "nearbyCandidateCount": 0,
        "nearestBoundaryGapDeg": None,
        "competitors": [],
        "failedChecks": [],
    }
    if (
        not isinstance(candidates, list) or len(candidates) > MAX_CANDIDATES
        or not isinstance(target_candidate_id, str) or not target_candidate_id
        or isinstance(search_margin_deg, bool)
        or not isinstance(search_margin_deg, (int, float))
        or not math.isfinite(float(search_margin_deg))
        or float(search_margin_deg) <= 0.0
    ):
        return {**base, "failedChecks": ["relative_geometry_input_invalid"]}
    normalized = [_finite_candidate(item) for item in candidates]
    if any(item is None for item in normalized):
        return {**base, "failedChecks": ["candidate_geometry_invalid"]}
    finite = [item for item in normalized if item is not None]
    targets = [item for item in finite if item["candidateId"] == target_candidate_id]
    if len(targets) != 1 or len({item["candidateId"] for item in finite}) != len(finite):
        return {**base, "failedChecks": ["target_candidate_not_unique"]}
    target = targets[0]
    competitors = []
    for item in finite:
        if item["candidateId"] == target_candidate_id:
            continue
        center_distance = _distance(target["centerDeg"], item["centerDeg"])
        signed_gap = center_distance - target["halfWidthDeg"] - item["halfWidthDeg"]
        competitors.append({
            "candidateId": item["candidateId"],
            "centerDistanceDeg": center_distance,
            "boundaryGapDeg": max(0.0, signed_gap),
            "overlapDeg": max(0.0, -signed_gap),
            "overlaps": signed_gap < 0.0,
            "nearby": signed_gap <= float(search_margin_deg),
        })
    competitors.sort(key=lambda item: (
        item["boundaryGapDeg"], -item["overlapDeg"], item["candidateId"],
    ))
    overlaps = [item for item in competitors if item["overlaps"]]
    nearby = [item for item in competitors if item["nearby"]]
    return {
        **base,
        "status": "evaluated",
        "overlapEvidence": bool(overlaps),
        "overlappingCandidateCount": len(overlaps),
        "nearbyCandidateCount": len(nearby),
        "nearestBoundaryGapDeg": (
            None if not competitors else float(competitors[0]["boundaryGapDeg"])
        ),
        "competitors": competitors[:8],
        "failedChecks": [],
    }
