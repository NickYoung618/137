#!/usr/bin/env python3
"""Export path-free local second-wall generation traces from slot-pose JSONL."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.render_slot_pose_review import load_results


TRACE_FIELDS = (
    "schemaVersion", "thresholdVersion", "enabled", "status", "failureStage",
    "errorCode", "authoritative", "posePromotionAllowed", "coarseCandidateId",
    "localInterval", "anchorSides", "anchorEvidence", "searchDomains", "searchLimits",
    "initialPairEvidence", "sideSearchCandidates",
    "sideSearchMergeClusters", "searchOutcomeSummary", "rawHypotheses",
    "hypothesisMergeClusters", "hypotheses", "canonicalWallPairs", "experimentalCandidate",
    "partialObservation", "passedHypothesisCount", "failedChecks",
)


def _require_external(path: Path) -> None:
    try:
        path.resolve().relative_to(PROJECT_ROOT.resolve())
    except ValueError:
        return
    raise ValueError("trace output must be outside the Git worktree")


def _basename(payload: dict[str, Any]) -> str:
    image = payload.get("image")
    path = image.get("path") if isinstance(image, dict) else None
    if not isinstance(path, str) or not path:
        raise ValueError("slot-pose result has no image.path")
    return Path(path).name


def _validate_v3_trace(diagnostic: dict[str, Any], image_name: str) -> None:
    if diagnostic.get("schemaVersion") not in {
        "local-second-wall-diagnostic/3", "local-second-wall-diagnostic/4",
    }:
        return
    searches = diagnostic.get("sideSearchCandidates") or []
    side_clusters = diagnostic.get("sideSearchMergeClusters") or []
    accepted_ids = {
        str(item["searchCandidateId"])
        for item in searches
        if isinstance(item, dict) and item.get("searchStatus") == "accepted"
    }
    clustered_ids = {
        str(candidate_id)
        for cluster in side_clusters if isinstance(cluster, dict)
        for candidate_id in (cluster.get("memberSearchCandidateIds") or [])
    }
    if accepted_ids != clustered_ids:
        raise ValueError(f"side wall cluster membership mismatch for {image_name}")
    raw = diagnostic.get("rawHypotheses") or []
    hypothesis_clusters = diagnostic.get("hypothesisMergeClusters") or []
    raw_ids = {
        str(item["rawHypothesisId"])
        for item in raw if isinstance(item, dict) and item.get("rawHypothesisId")
    }
    hypothesis_member_ids = {
        str(hypothesis_id)
        for cluster in hypothesis_clusters if isinstance(cluster, dict)
        for hypothesis_id in (cluster.get("memberRawHypothesisIds") or [])
    }
    if raw_ids != hypothesis_member_ids:
        raise ValueError(f"canonical pair cluster membership mismatch for {image_name}")
    pair_ids = [
        str(item["canonicalPairId"])
        for item in (diagnostic.get("canonicalWallPairs") or [])
        if isinstance(item, dict) and item.get("canonicalPairId")
    ]
    if len(pair_ids) != len(set(pair_ids)):
        raise ValueError(f"duplicate canonical wall pair for {image_name}")


def _trace_case(payload: dict[str, Any], image_name: str) -> dict[str, Any]:
    diagnostic = (payload.get("diagnostics") or {}).get("localSecondWallDiagnostic")
    if not isinstance(diagnostic, dict):
        raise ValueError(f"localSecondWallDiagnostic missing for {image_name}")
    _validate_v3_trace(diagnostic, image_name)
    algorithm = payload.get("algorithm") if isinstance(payload.get("algorithm"), dict) else {}
    error = payload.get("error") if isinstance(payload.get("error"), dict) else None
    return {
        "imageName": image_name,
        "topLevelValid": bool((payload.get("result") or {}).get("valid", False)),
        "topLevelErrorCode": None if error is None else error.get("code"),
        "algorithmVersion": algorithm.get("version"),
        "configSha256": algorithm.get("configSha256"),
        "effectiveConfigSha256": algorithm.get("effectiveConfigSha256"),
        "localSecondWallDiagnostic": {
            key: diagnostic[key] for key in TRACE_FIELDS if key in diagnostic
        },
    }


def build_trace_export(
    results: list[dict[str, Any]], image_names: list[str],
) -> dict[str, Any]:
    if not image_names:
        raise ValueError("at least one image name is required")
    if len(set(image_names)) != len(image_names):
        raise ValueError("image names must be unique")
    requested = set(image_names)
    selected: dict[str, dict[str, Any]] = {}
    for payload in results:
        name = _basename(payload)
        if name not in requested:
            continue
        if name in selected:
            raise ValueError(f"duplicate result basename: {name}")
        selected[name] = payload
    missing = [name for name in image_names if name not in selected]
    if missing:
        raise ValueError(f"requested result missing: {missing}")
    cases = [_trace_case(selected[name], name) for name in image_names]
    return {
        "schemaVersion": "local-second-wall-trace-export/1",
        "caseCount": len(cases),
        "cases": cases,
        "privacy": {
            "containsImagePixels": False,
            "containsAbsolutePaths": False,
            "containsHumanTruth": False,
        },
        "interpretation": {
            "uniqueDiagnosticIsAuthoritative": False,
            "thresholdTuningAllowed": False,
            "purpose": "candidate_generation_and_merge_root_cause_only",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, action="append", required=True)
    parser.add_argument("--image-name", action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        _require_external(args.output)
        results = [payload for path in args.results for payload in load_results(path)]
        output = build_trace_export(results, args.image_name)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(output, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
            encoding="utf-8",
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(f"Wrote {args.output}: cases={output['caseCount']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
