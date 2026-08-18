#!/usr/bin/env python3
"""Materialize the explicit, Git-external single-shot initial profile."""

from __future__ import annotations

import argparse
import copy
import json
import math
import sys
from pathlib import Path
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from algorithms.slot_pose.sidewall_consistency import DEFAULT_SIDEWALL_CONSISTENCY_CONFIG
from algorithms.slot_pose.physical_outer_circle import (
    DEFAULT_EDGE_FAMILY_SELECTION_CONFIG,
    EDGE_FAMILY_STRATEGY_V2,
    merged_physical_outer_circle_config,
)
from algorithms.slot_pose.groove_resolution import DEFAULT_AMBIGUITY_RESOLUTION_CONFIG
from algorithms.slot_pose.source_consistency_adjudication import (
    DEFAULT_SOURCE_CONSISTENCY_ADJUDICATION_CONFIG,
)
from tools.dataset_common import sha256_file, write_json
from tools.prepare_source_consistency_adjudication_config import build_experimental_config


PROFILE_VERSION = "single-shot-initial-profile/2"
PROFILE_ID = "single-real-groove-85deg-fail-closed-v2"
PROFILE_VERSION_V3 = "single-shot-initial-profile/3"
PROFILE_ID_V3 = "single-real-groove-85deg-global-circle-family-v3"
PROFILE_VERSION_V4 = "single-shot-initial-profile/4"
PROFILE_ID_V4 = "single-real-groove-85deg-circle-family-consensus-v4"


def _same_number(actual: Any, expected: float) -> bool:
    return (
        not isinstance(actual, bool)
        and isinstance(actual, (int, float))
        and math.isfinite(float(actual))
        and math.isclose(float(actual), float(expected), rel_tol=0.0, abs_tol=0.0)
    )


def build_initial_config(base: dict[str, Any]) -> dict[str, Any]:
    """Enable only the already-audited single-shot image-guidance chain."""
    if not isinstance(base, dict):
        raise ValueError("base config must be an object")
    source = copy.deepcopy(base)
    detector = source.get("detector")
    if not isinstance(detector, dict) or detector.get("diagnostic_mode") != "single_real_groove":
        raise ValueError("single-shot initial profile requires single_real_groove")

    legacy = source.get("legacy_asset")
    if not isinstance(legacy, dict) or legacy.get("source_mode") != "bundled_module":
        raise ValueError("single-shot initial profile requires the bundled repository core")
    if legacy.get("bundled_module") != "algorithms.end_face.core":
        raise ValueError("single-shot initial profile bundled module is not the audited core")

    pose = source.get("pose")
    if not isinstance(pose, dict) or pose.get("production_plc_mapping_confirmed") is not False:
        raise ValueError("single-shot initial profile requires PLC mapping to remain unconfirmed")

    single = detector.get("single_groove_pose")
    target = single.get("target") if isinstance(single, dict) else None
    if not isinstance(single, dict) or single.get("schema_version") != "single-real-groove-pose-config/3":
        raise ValueError("single-shot initial profile requires single-groove pose v3")
    required_target = {
        "nominal_deg": 85.0,
        "tolerance_deg": 5.0,
        "accepted_min_deg": 80.0,
        "accepted_max_deg": 90.0,
    }
    if not isinstance(target, dict) or any(
        not _same_number(target.get(key), value) for key, value in required_target.items()
    ):
        raise ValueError("single-shot initial target must remain 85deg +/-5deg with [80,90] deadband")
    if (
        target.get("required_horizontal_position") != "left"
        or target.get("required_vertical_position") != "lower_or_axis"
        or target.get("angle_convention_id") != "image-y-down-clockwise-signed/1"
    ):
        raise ValueError("single-shot initial target quadrant or angle convention is invalid")

    source_gate = detector.get("sidewall_source_consistency")
    if not isinstance(source_gate, dict) or source_gate.get("enabled") is not True:
        raise ValueError("single-shot initial profile requires sidewall source consistency")
    for key, expected in DEFAULT_SIDEWALL_CONSISTENCY_CONFIG.items():
        if key == "enabled":
            continue
        actual = source_gate.get(key)
        if isinstance(expected, float):
            matches = _same_number(actual, expected)
        else:
            matches = actual == expected
        if not matches:
            name = "contrast" if key == "max_contrast_normalized_difference" else key
            raise ValueError(f"single-shot initial profile refuses changed source-consistency {name}")

    configured = build_experimental_config(source)
    configured["detector"]["ambiguity_resolution"] = {
        **DEFAULT_AMBIGUITY_RESOLUTION_CONFIG,
        "enabled": True,
        "max_candidates": 3,
    }
    adjudication = configured["detector"]["source_consistency_adjudication"]
    for key, expected in DEFAULT_SOURCE_CONSISTENCY_ADJUDICATION_CONFIG.items():
        actual = adjudication.get(key)
        expected_value = True if key == "enabled" else expected
        if isinstance(expected_value, float):
            matches = _same_number(actual, expected_value)
        else:
            matches = actual == expected_value
        if not matches:
            raise ValueError(f"single-shot initial profile refuses changed adjudication {key}")
    return configured


def build_initial_config_v3(base: dict[str, Any]) -> dict[str, Any]:
    """Materialize the reviewed single-image circle-family selector explicitly."""
    configured = build_initial_config(base)
    detector = configured["detector"]
    physical = merged_physical_outer_circle_config(detector.get("physical_outer_circle"))
    physical["edge_family_selection"] = {
        **DEFAULT_EDGE_FAMILY_SELECTION_CONFIG,
        "enabled": True,
    }
    detector["physical_outer_circle"] = physical
    configured["config_id"] = PROFILE_ID_V3
    return configured


def build_initial_config_v4(base: dict[str, Any]) -> dict[str, Any]:
    """Materialize the reviewed bounded family-consensus strategy explicitly."""
    selection = (
        base.get("detector", {}).get("physical_outer_circle", {})
        .get("edge_family_selection")
        if isinstance(base, dict) else None
    )
    if isinstance(selection, dict) and selection.get("enabled") is True:
        physical = merged_physical_outer_circle_config(
            base["detector"]["physical_outer_circle"]
        )
        if physical["edge_family_selection"]["strategy_version"] != (
            DEFAULT_EDGE_FAMILY_SELECTION_CONFIG["strategy_version"]
        ):
            raise ValueError("v4 upgrade requires the reviewed version-1 circle-family strategy")
        configured = copy.deepcopy(base)
    else:
        configured = build_initial_config_v3(base)
    selection = configured["detector"]["physical_outer_circle"]["edge_family_selection"]
    selection["strategy_version"] = EDGE_FAMILY_STRATEGY_V2
    configured["config_id"] = PROFILE_ID_V4
    return configured


def build_profile_report(*, source_config_sha256: str, output_config_sha256: str) -> dict[str, Any]:
    return {
        "schemaVersion": PROFILE_VERSION,
        "profileId": PROFILE_ID,
        "sourceConfigSha256": source_config_sha256,
        "materializedConfigSha256": output_config_sha256,
        "detectorMode": "single_real_groove",
        "target": {
            "angleConventionId": "image-y-down-clockwise-signed/1",
            "targetAngleDeg": 85.0,
            "toleranceDeg": 5.0,
            "acceptedMinDeg": 80.0,
            "acceptedMaxDeg": 90.0,
        },
        "sourceConsistency": {
            "originalThresholdVersion": DEFAULT_SIDEWALL_CONSISTENCY_CONFIG["threshold_version"],
            "originalContrastThreshold": DEFAULT_SIDEWALL_CONSISTENCY_CONFIG[
                "max_contrast_normalized_difference"
            ],
            "originalEvidencePreserved": True,
            "adjudicationVersion": DEFAULT_SOURCE_CONSISTENCY_ADJUDICATION_CONFIG["threshold_version"],
        },
        "ambiguityResolution": {
            "schemaVersion": DEFAULT_AMBIGUITY_RESOLUTION_CONFIG["schema_version"],
            "enabled": True,
            "maxCandidates": 3,
            "selectionEvidence": "existing_subpixel_sidewall_and_outer_circle_gates",
        },
        "policies": {
            "singleCaptureRequired": True,
            "pairedCaptureRequired": False,
            "occlusionFailsClosed": True,
            "mixedFixtureEdgeFailsClosed": True,
            "imageGuidanceAllowed": True,
            "plcAllowed": False,
            "manualTruthAppliedAtRuntime": False,
            "developmentOnly": True,
        },
    }


def build_profile_report_v3(*, source_config_sha256: str, output_config_sha256: str) -> dict[str, Any]:
    report = build_profile_report(
        source_config_sha256=source_config_sha256,
        output_config_sha256=output_config_sha256,
    )
    report.update({"schemaVersion": PROFILE_VERSION_V3, "profileId": PROFILE_ID_V3})
    report["circleEdgeFamilySelection"] = {
        "schemaVersion": DEFAULT_EDGE_FAMILY_SELECTION_CONFIG["schema_version"],
        "strategyVersion": DEFAULT_EDGE_FAMILY_SELECTION_CONFIG["strategy_version"],
        "enabled": True,
        "boundedCandidateCount": True,
        "uniqueFamilyRequired": True,
        "originalQualityGatesPreserved": True,
        "fixedAngleMaskApplied": False,
    }
    return report


def build_profile_report_v4(*, source_config_sha256: str, output_config_sha256: str) -> dict[str, Any]:
    report = build_profile_report_v3(
        source_config_sha256=source_config_sha256,
        output_config_sha256=output_config_sha256,
    )
    report.update({"schemaVersion": PROFILE_VERSION_V4, "profileId": PROFILE_ID_V4})
    report["circleEdgeFamilySelection"]["strategyVersion"] = EDGE_FAMILY_STRATEGY_V2
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-config", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--profile-version", choices=("2", "3", "4"), default="4")
    return parser.parse_args()


def _external(path: Path, label: str) -> Path:
    resolved = path.resolve()
    if resolved.is_relative_to(REPOSITORY_ROOT):
        raise ValueError(f"{label} must remain outside the Git worktree")
    return resolved


def main() -> int:
    args = parse_args()
    try:
        output = _external(args.output, "materialized config output")
        report_path = _external(args.report, "profile report output")
        if output == report_path:
            raise ValueError("config output and profile report must be different paths")
        base = json.loads(args.base_config.read_text(encoding="utf-8"))
        builders = {
            "2": build_initial_config,
            "3": build_initial_config_v3,
            "4": build_initial_config_v4,
        }
        configured = builders[args.profile_version](base)
        write_json(output, configured)
        report_builders = {
            "2": build_profile_report,
            "3": build_profile_report_v3,
            "4": build_profile_report_v4,
        }
        report_builder = report_builders[args.profile_version]
        report = report_builder(
            source_config_sha256=sha256_file(args.base_config), output_config_sha256=sha256_file(output),
        )
        write_json(report_path, report)
        print(
            f"Wrote config sha256={report['materializedConfigSha256']} "
            f"profile={report_path}"
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
