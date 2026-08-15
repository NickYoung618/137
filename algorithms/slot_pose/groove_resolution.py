"""Bounded physical refinement for ambiguous coarse groove candidates."""

from __future__ import annotations

from typing import Any, Callable


DEFAULT_AMBIGUITY_RESOLUTION_CONFIG: dict[str, Any] = {
    "schema_version": "groove-ambiguity-resolution/1",
    "enabled": False,
    "max_candidates": 3,
}


def merged_ambiguity_resolution_config(config: dict[str, Any] | None) -> dict[str, Any]:
    if config is not None and not isinstance(config, dict):
        raise ValueError("ambiguity_resolution must be an object")
    merged = {**DEFAULT_AMBIGUITY_RESOLUTION_CONFIG, **(config or {})}
    unexpected = sorted(set(merged) - set(DEFAULT_AMBIGUITY_RESOLUTION_CONFIG))
    if unexpected:
        raise ValueError(f"ambiguity_resolution has unsupported fields: {unexpected}")
    if merged["schema_version"] != "groove-ambiguity-resolution/1":
        raise ValueError("ambiguity_resolution.schema_version is unsupported")
    if not isinstance(merged["enabled"], bool):
        raise ValueError("ambiguity_resolution.enabled must be boolean")
    maximum = merged["max_candidates"]
    if isinstance(maximum, bool) or not isinstance(maximum, int) or not 2 <= maximum <= 3:
        raise ValueError("ambiguity_resolution.max_candidates must be an integer in [2,3]")
    return merged


def resolve_groove_candidates(
    candidates: list[dict[str, Any]],
    refiner: Callable[[dict[str, Any]], dict[str, Any]],
    config: dict[str, Any] | None,
) -> dict[str, Any]:
    merged = merged_ambiguity_resolution_config(config)
    base = {
        "schemaVersion": "groove-ambiguity-resolution/1",
        "enabled": merged["enabled"],
        "candidateCount": len(candidates),
        "maxCandidates": merged["max_candidates"],
        "selectedCandidateId": None,
        "survivors": [],
        "attempts": [],
        "authoritativeSelectionEvidence": "existing_subpixel_sidewall_and_outer_circle_gates",
    }
    if not merged["enabled"]:
        return {**base, "status": "disabled"}
    if len(candidates) > merged["max_candidates"]:
        return {**base, "status": "candidate_limit_exceeded"}
    attempts = []
    survivors = []
    for candidate in candidates:
        refinement = refiner(candidate)
        attempt = {
            "candidateId": str(candidate["candidateId"]),
            "accepted": refinement.get("status") == "accepted",
            "refinement": refinement,
        }
        attempts.append(attempt)
        if attempt["accepted"]:
            survivors.append({**candidate, "grooveRefinement": refinement})
    output = {**base, "attempts": attempts, "survivors": survivors}
    if len(survivors) == 1:
        return {**output, "status": "resolved", "selectedCandidateId": survivors[0]["candidateId"]}
    return {**output, "status": "none_survived" if not survivors else "multiple_survived"}
