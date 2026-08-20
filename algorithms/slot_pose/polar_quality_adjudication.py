"""Default-off adjudication for a sole legacy polar-quality failure.

The decision consumes only bounded diagnostics already produced by the physical
single-groove chain.  It never samples an image, changes a threshold, mutates
original quality evidence, supplies pose geometry, or authorizes PLC output.
"""

from __future__ import annotations

import copy
import math
from typing import Any, Callable


DEFAULT_POLAR_QUALITY_ADJUDICATION_CONFIG: dict[str, Any] = {
    "schema_version": "polar-quality-adjudication/1",
    "enabled": False,
    "strategy_version": "locked-physical-groove-proof-v1",
    "development_only": True,
}

_SCHEMA_VERSION = "polar-quality-adjudication/1"
_STRATEGY_VERSION = "locked-physical-groove-proof-v1"
_NOT_EVALUATED_FAILURE = "polar_quality_adjudication_not_evaluated"


def validate_polar_quality_adjudication_config(config: dict[str, Any]) -> None:
    if not isinstance(config, dict):
        raise ValueError("detector.polar_quality_adjudication must be an object")
    required = set(DEFAULT_POLAR_QUALITY_ADJUDICATION_CONFIG)
    missing = sorted(required - set(config))
    unknown = sorted(set(config) - required)
    if missing:
        raise ValueError(f"polar_quality_adjudication missing fields: {missing}")
    if unknown:
        raise ValueError(f"polar_quality_adjudication has unknown fields: {unknown}")
    if config["schema_version"] != _SCHEMA_VERSION:
        raise ValueError("polar_quality_adjudication.schema_version is unsupported")
    if not isinstance(config["enabled"], bool):
        raise ValueError("polar_quality_adjudication.enabled must be boolean")
    if config["strategy_version"] != _STRATEGY_VERSION:
        raise ValueError("polar_quality_adjudication.strategy_version is unsupported")
    if config["development_only"] is not True:
        raise ValueError("polar_quality_adjudication.development_only must be true")


def merged_polar_quality_adjudication_config(
    config: dict[str, Any] | None,
) -> dict[str, Any]:
    if config is not None and not isinstance(config, dict):
        raise ValueError("detector.polar_quality_adjudication must be an object")
    merged = copy.deepcopy(DEFAULT_POLAR_QUALITY_ADJUDICATION_CONFIG)
    if config:
        merged.update(copy.deepcopy(config))
    validate_polar_quality_adjudication_config(merged)
    return merged


def _finite_number(value: Any) -> bool:
    return (
        not isinstance(value, bool)
        and isinstance(value, (int, float))
        and math.isfinite(float(value))
    )


def _finite_point(value: Any) -> bool:
    if isinstance(value, dict):
        return _finite_number(value.get("x")) and _finite_number(value.get("y"))
    return (
        isinstance(value, (list, tuple))
        and len(value) == 2
        and all(_finite_number(item) for item in value)
    )


def _valid_observed_side(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    points = value.get("points")
    support = value.get("supportPointCount")
    return bool(
        isinstance(points, list)
        and len(points) >= 2
        and all(_finite_point(point) for point in points)
        and isinstance(support, int)
        and not isinstance(support, bool)
        and support >= 2
    )


def _effective_source_accepted(refinement: dict[str, Any]) -> bool:
    source = refinement.get("sourceConsistency")
    if (
        isinstance(source, dict)
        and source.get("status") == "accepted"
        and source.get("failedChecks") == []
    ):
        return True
    adjudication = refinement.get("sourceConsistencyAdjudication")
    return bool(
        isinstance(adjudication, dict)
        and adjudication.get("decision") == "ACCEPTED_OVERRIDE"
        and adjudication.get("effectiveStatus") == "accepted"
        and adjudication.get("imagePoseReleaseAllowed") is True
        and adjudication.get("manualTruthAppliedAtRuntime") is False
        and adjudication.get("plcAllowed") is False
    )


def _base(config: dict[str, Any], *, original_failed: list[str]) -> dict[str, Any]:
    return {
        "schemaVersion": config["schema_version"],
        "strategyVersion": config["strategy_version"],
        "enabled": True,
        "developmentOnly": True,
        "authoritative": False,
        "productionDefaultAllowed": False,
        "plcAllowed": False,
        "manualTruthAppliedAtRuntime": False,
        "fixedAngleApplied": False,
        "originalFailedChecks": list(original_failed),
    }


def _not_evaluated(
    config: dict[str, Any], *, original_failed: list[str], reason: str,
    score: float | None = None, threshold: float | None = None,
) -> dict[str, Any]:
    effective_failed = (
        list(original_failed) if original_failed else [_NOT_EVALUATED_FAILURE]
    )
    return {
        **_base(config, original_failed=original_failed),
        "decision": "NOT_EVALUATED",
        "originalPolarScore": score,
        "originalPolarThreshold": threshold,
        "effectiveFailedChecks": effective_failed,
        "checks": [],
        "failedChecks": [reason],
        "imagePoseReleaseAllowed": False,
    }


def adjudicate_polar_quality(
    evidence: dict[str, Any] | None,
    config: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Return a separate effective-quality decision without mutating evidence."""
    if config is None:
        return None
    merged = merged_polar_quality_adjudication_config(config)
    if not merged["enabled"]:
        return None
    if not isinstance(evidence, dict):
        return _not_evaluated(
            merged, original_failed=[], reason="evidence_bundle_missing",
        )
    quality = evidence.get("quality")
    if not isinstance(quality, dict):
        return _not_evaluated(
            merged, original_failed=[], reason="original_quality_missing",
        )
    failed = quality.get("failedChecks")
    safe_failed = (
        list(failed)
        if isinstance(failed, list)
        and all(isinstance(item, str) for item in failed)
        and len(set(failed)) == len(failed)
        else []
    )
    thresholds = quality.get("thresholds")
    score_value = quality.get("polarScore")
    threshold_value = (
        thresholds.get("min_polar_score") if isinstance(thresholds, dict) else None
    )
    if (
        not isinstance(failed, list)
        or not all(isinstance(item, str) for item in failed)
        or len(set(failed)) != len(failed)
        or not _finite_number(score_value)
        or not _finite_number(threshold_value)
    ):
        return _not_evaluated(
            merged, original_failed=safe_failed, reason="original_quality_malformed",
            score=float(score_value) if _finite_number(score_value) else None,
            threshold=float(threshold_value) if _finite_number(threshold_value) else None,
        )
    score = float(score_value)
    threshold = float(threshold_value)
    polar_failed_by_value = score < threshold
    if ("polar_score" in safe_failed) != polar_failed_by_value:
        return _not_evaluated(
            merged, original_failed=safe_failed,
            reason="polar_score_failure_relationship_inconsistent",
            score=score, threshold=threshold,
        )
    base = {
        **_base(merged, original_failed=safe_failed),
        "originalPolarScore": score,
        "originalPolarThreshold": threshold,
    }
    if not safe_failed:
        return {
            **base,
            "decision": "NOT_NEEDED",
            "effectiveFailedChecks": [],
            "checks": [],
            "failedChecks": [],
            "imagePoseReleaseAllowed": False,
        }

    circle = evidence.get("physicalOuterCircle")
    recognition = evidence.get("grooveRecognition")
    refinement = evidence.get("grooveRefinement")
    pose = evidence.get("singleGroovePose")
    family = circle.get("edgeFamilySelection") if isinstance(circle, dict) else None
    accepted_ids = (
        recognition.get("acceptedCandidateIds") if isinstance(recognition, dict) else None
    )
    recognized_id = accepted_ids[0] if isinstance(accepted_ids, list) and len(accepted_ids) == 1 else None
    fixture = refinement.get("fixtureSourceExclusion") if isinstance(refinement, dict) else None
    floor = fixture.get("grooveFloorEvidence") if isinstance(fixture, dict) else None
    intersections = refinement.get("outerCircleIntersections") if isinstance(refinement, dict) else None
    pose_role = pose.get("role") if isinstance(pose, dict) else None

    def sole_polar() -> bool:
        return safe_failed == ["polar_score"]

    def unique_circle() -> bool:
        return bool(
            isinstance(circle, dict)
            and circle.get("status") == "accepted"
            and circle.get("failedChecks") == []
            and isinstance(family, dict)
            and family.get("status") == "selected"
            and family.get("qualifiedFamilyCount") == 1
            and isinstance(family.get("selectedFamilyId"), str)
            and bool(family["selectedFamilyId"])
            and family.get("failedChecks") == []
        )

    def unique_groove() -> bool:
        return bool(
            isinstance(recognition, dict)
            and recognition.get("status") == "accepted"
            and recognition.get("acceptedCount") == 1
            and isinstance(accepted_ids, list)
            and len(accepted_ids) == 1
            and isinstance(recognized_id, str)
            and bool(recognized_id)
        )

    def accepted_pose() -> bool:
        return bool(
            isinstance(pose, dict)
            and pose.get("status") == "accepted"
            and pose.get("acceptedGrooveCount") == 1
            and pose.get("geometryValid") is True
            and isinstance(pose_role, dict)
            and pose_role.get("status") == "unique_detected"
            and pose_role.get("candidateId") == recognized_id
            and isinstance(pose.get("imageMeasurement"), dict)
            and _finite_number(pose["imageMeasurement"].get("azimuthDeg"))
            and pose["imageMeasurement"].get("midpointSource")
            == "subpixel_sidewall_outer_circle_intersections"
        )

    def accepted_refinement() -> bool:
        return bool(
            isinstance(refinement, dict)
            and refinement.get("status") == "accepted"
            and refinement.get("failedChecks") == []
            and refinement.get("coarseCandidateId") == recognized_id
        )

    def observed_walls() -> bool:
        return bool(
            isinstance(refinement, dict)
            and _valid_observed_side(refinement.get("startSide"))
            and _valid_observed_side(refinement.get("endSide"))
            and refinement.get("startSide") is not refinement.get("endSide")
        )

    def finite_endpoints() -> bool:
        if not isinstance(intersections, list) or len(intersections) != 2:
            return False
        if not all(_finite_point(point) for point in intersections):
            return False
        first, second = intersections
        return not (
            math.isclose(float(first["x"]), float(second["x"]), abs_tol=1e-12)
            and math.isclose(float(first["y"]), float(second["y"]), abs_tol=1e-12)
        )

    def complete_floor() -> bool:
        return bool(
            isinstance(floor, dict)
            and floor.get("schemaVersion") == "groove-floor-evidence/1"
            and floor.get("status") == "accepted"
            and floor.get("trackCount") == 5
            and floor.get("acceptedTrackCount") == 5
            and floor.get("failedChecks") == []
        )

    def fixture_excluded() -> bool:
        return bool(
            isinstance(fixture, dict)
            and fixture.get("schemaVersion") in {
                "fixture-groove-source-exclusion/1",
                "fixture-groove-source-exclusion/2",
                "fixture-groove-source-exclusion/4",
            }
            and fixture.get("status") == "verified"
            and fixture.get("fixtureBodiesVerified") is True
            and fixture.get("twoSidewallsComplete") is True
            and fixture.get("uContourComplete") is True
            and fixture.get("fixtureSourceExcluded") is True
            and fixture.get("candidateSelectionUsedFixedAngle") is False
            and fixture.get("failedChecks") == []
            and (
                fixture.get("schemaVersion") != "fixture-groove-source-exclusion/4"
                or (
                    fixture.get("radialUContourOwnershipVerified") is True
                    and fixture.get("manualTruthAppliedAtRuntime") is False
                )
            )
        )

    def runtime_only() -> bool:
        return bool(
            isinstance(floor, dict)
            and floor.get("manualTruthAppliedAtRuntime") is False
            and floor.get("fixedAngleApplied") is False
        )

    definitions: tuple[tuple[str, Callable[[], bool]], ...] = (
        ("sole_polar_failure", sole_polar),
        ("unique_physical_outer_circle_edge_family", unique_circle),
        ("unique_accepted_real_groove", unique_groove),
        ("accepted_single_groove_pose", accepted_pose),
        ("accepted_physical_refinement", accepted_refinement),
        ("two_distinct_observed_sidewalls", observed_walls),
        ("finite_outer_circle_endpoints", finite_endpoints),
        ("complete_five_track_curved_floor", complete_floor),
        ("effective_source_consistency_accepted", lambda: bool(
            isinstance(refinement, dict) and _effective_source_accepted(refinement)
        )),
        ("fixture_source_exclusion_verified", fixture_excluded),
        ("runtime_image_geometry_only", runtime_only),
    )
    checks = [{"checkId": check_id, "passed": bool(check())} for check_id, check in definitions]
    failed_checks = [item["checkId"] for item in checks if not item["passed"]]
    accepted = not failed_checks
    return {
        **base,
        "decision": "ACCEPTED_OVERRIDE" if accepted else "REJECTED",
        "effectiveFailedChecks": [] if accepted else list(safe_failed),
        "checks": checks,
        "failedChecks": failed_checks,
        "imagePoseReleaseAllowed": accepted,
    }
