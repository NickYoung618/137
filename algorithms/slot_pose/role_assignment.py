"""Deterministic assignment of generic notch candidates to configured drawing roles."""

from __future__ import annotations

import itertools
import math
from typing import Any, Iterable

from algorithms.slot_pose.angular_profile import NotchCandidate, circular_delta_deg, circular_distance_deg, wrap_360_deg


REQUIRED_ROLES = ("datum_primary", "target_left")
DATUM_DEFINITIONS = {"single_candidate_ray", "opposed_candidates_axis"}


def validate_role_config(config: dict[str, Any]) -> None:
    assignments = config.get("assignments")
    if not isinstance(assignments, dict):
        raise ValueError("role_assignment.assignments must be an object")
    for role in REQUIRED_ROLES:
        if role not in assignments:
            raise ValueError(f"role_assignment.assignments.{role} is required")
    definition = config.get("datum_definition")
    if definition not in DATUM_DEFINITIONS:
        raise ValueError(f"unsupported datum_definition: {definition!r}")
    if definition == "opposed_candidates_axis" and "datum_secondary" not in assignments:
        raise ValueError("opposed_candidates_axis requires datum_secondary")
    for role, rule in assignments.items():
        if not isinstance(role, str) or not role or not isinstance(rule, dict):
            raise ValueError("role assignment names and rules must be non-empty objects")
        expected = rule.get("expected_reference_azimuth_deg")
        deviation = rule.get("max_deviation_deg")
        if not isinstance(expected, (int, float)) or not math.isfinite(float(expected)):
            raise ValueError(f"{role}.expected_reference_azimuth_deg must be finite")
        if not isinstance(deviation, (int, float)) or not 0.0 < float(deviation) <= 180.0:
            raise ValueError(f"{role}.max_deviation_deg must be in (0, 180]")
    margin = config.get("min_score_margin")
    if not isinstance(margin, (int, float)) or not 0.0 <= float(margin) <= 1.0:
        raise ValueError("role_assignment.min_score_margin must be in [0, 1]")
    opposition = config.get("max_opposition_error_deg")
    if not isinstance(opposition, (int, float)) or not 0.0 < float(opposition) <= 180.0:
        raise ValueError("role_assignment.max_opposition_error_deg must be in (0, 180]")
    nominal = config.get("drawing_nominal_angle_deg")
    tolerance = config.get("drawing_tolerance_deg")
    if nominal is not None and (not isinstance(nominal, (int, float)) or not 0.0 <= float(nominal) <= 180.0):
        raise ValueError("drawing_nominal_angle_deg must be null or in [0, 180]")
    if tolerance is not None and (not isinstance(tolerance, (int, float)) or float(tolerance) < 0.0):
        raise ValueError("drawing_tolerance_deg must be null or non-negative")


def assign_roles(
    candidates: Iterable[NotchCandidate],
    config: dict[str, Any],
    *,
    expected_offset_deg: float = 0.0,
) -> dict[str, Any]:
    """Enumerate distinct candidate assignments and accept only a score-separated best."""
    validate_role_config(config)
    items = sorted(candidates, key=lambda item: (item.center_deg, item.candidate_id))
    roles = list(config["assignments"])
    assessments: list[dict[str, Any]] = []
    for chosen in itertools.permutations(items, len(roles)):
        deviations: dict[str, float] = {}
        failed: list[str] = []
        for role, candidate in zip(roles, chosen, strict=True):
            rule = config["assignments"][role]
            expected = wrap_360_deg(float(rule["expected_reference_azimuth_deg"]) + expected_offset_deg)
            deviation = circular_distance_deg(candidate.center_deg, expected)
            deviations[role] = deviation
            if deviation > float(rule["max_deviation_deg"]):
                failed.append(f"{role}_window")
        normalized = [
            deviations[role] / float(config["assignments"][role]["max_deviation_deg"])
            for role in roles
        ]
        azimuths = {role: candidate.center_deg for role, candidate in zip(roles, chosen, strict=True)}
        opposition_error: float | None = None
        if config["datum_definition"] == "opposed_candidates_axis":
            separation = circular_distance_deg(float(azimuths["datum_primary"]), float(azimuths["datum_secondary"]))
            opposition_error = abs(180.0 - separation)
            if opposition_error > float(config["max_opposition_error_deg"]):
                failed.append("datum_opposition")
        score = max(0.0, 1.0 - sum(normalized) / len(normalized))
        assessments.append({
            "roleCandidateIds": {role: candidate.candidate_id for role, candidate in zip(roles, chosen, strict=True)},
            "roleAzimuthsDeg": azimuths,
            "deviationsDeg": deviations,
            "datumOppositionErrorDeg": opposition_error,
            "score": score,
            "failedChecks": failed,
        })
    assessments.sort(key=lambda item: (-float(item["score"]), tuple(item["roleCandidateIds"].values())))
    qualified = [item for item in assessments if not item["failedChecks"]]
    best = qualified[0] if qualified else None
    second = qualified[1] if len(qualified) > 1 else None
    margin = float(best["score"] - second["score"]) if best and second else (float(best["score"]) if best else None)
    failures: list[str] = []
    if len(items) < len(roles):
        failures.append("candidate_count_below_role_count")
    if best is None:
        failures.append("no_assignment_passed_role_geometry")
        if any("datum_opposition" in item["failedChecks"] for item in assessments):
            failures.append("datum_opposition")
    elif second is not None and float(margin or 0.0) < float(config["min_score_margin"]):
        failures.append("role_assignment_not_unique")

    selected = best if best is not None and not failures else None
    geometry: dict[str, Any] | None = None
    if selected is not None:
        azimuths = selected["roleAzimuthsDeg"]
        datum = float(azimuths["datum_primary"])
        if config["datum_definition"] == "opposed_candidates_axis":
            geometry = _drawing_geometry(
                datum, float(azimuths["target_left"]), config, selected["datumOppositionErrorDeg"],
            )
        else:
            geometry = _drawing_geometry(datum, float(azimuths["target_left"]), config, None)
    if failures:
        selected = None
        geometry = None
    return {
        "assessments": assessments,
        "selectedRoleCandidateIds": selected["roleCandidateIds"] if selected else None,
        "selectedRoleAzimuthsDeg": selected["roleAzimuthsDeg"] if selected else None,
        "bestScore": float(best["score"]) if best else None,
        "secondBestScore": float(second["score"]) if second else None,
        "scoreMargin": margin,
        "unique": selected is not None,
        "datumDefinition": config["datum_definition"],
        "drawingAngle": geometry,
        "failedChecks": failures,
    }


def _drawing_geometry(
    datum_deg: float,
    target_deg: float,
    config: dict[str, Any],
    opposition_error_deg: float | None,
) -> dict[str, Any]:
    clockwise = wrap_360_deg(target_deg - datum_deg)
    shortest_signed = circular_delta_deg(target_deg, datum_deg)
    included = abs(shortest_signed)
    return {
        "datumAzimuthImageDeg": datum_deg,
        "targetAzimuthImageDeg": target_deg,
        "clockwiseAngleDeg": clockwise,
        "shortestSignedAngleDeg": shortest_signed,
        "includedAngleDeg": included,
        "datumOppositionErrorDeg": opposition_error_deg,
        "drawingNominalDeg": config.get("drawing_nominal_angle_deg"),
        "drawingToleranceDeg": config.get("drawing_tolerance_deg"),
        "toleranceStatus": "NOT_EVALUATED",
    }
