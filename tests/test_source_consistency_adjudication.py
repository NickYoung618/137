from __future__ import annotations

import copy
import json
import math
import statistics
import time
import unittest
from pathlib import Path

try:
    import jsonschema
except ImportError:
    jsonschema = None

from algorithms.slot_pose.source_consistency_adjudication import (
    DEFAULT_SOURCE_CONSISTENCY_ADJUDICATION_CONFIG,
    adjudicate_source_consistency,
    merged_source_consistency_adjudication_config,
)
from tools.summarize_source_consistency_adjudication import summarize
from tools.prepare_source_consistency_adjudication_config import build_experimental_config


CHECKS = (
    ("edge_contrast_asymmetry", "contrastNormalizedDifference", 0.18, 0.12, "max"),
    ("edge_gradient_asymmetry", "gradientNormalizedDifference", 0.30, 0.35, "max"),
    ("normalized_profile_dissimilar", "normalizedProfileMae", 0.03, 0.22, "max"),
    ("normalized_profile_uncorrelated", "normalizedProfileCorrelation", 0.99, 0.75, "min"),
    ("radial_coverage_inconsistent", "radialCoverageDifference", 0.03, 0.20, "max"),
    ("endpoint_structure_inconsistent", "endpointStructureDifference", 0.02, 0.15, "max"),
)


def source_evidence(
    *,
    endpoint: float = 0.02,
    failed: list[str] | None = None,
    status: str = "rejected",
) -> dict:
    failed = ["edge_contrast_asymmetry"] if failed is None else list(failed)
    metrics = {metric: value for _, metric, value, _, _ in CHECKS}
    metrics["endpointStructureDifference"] = endpoint
    checks = []
    for check_id, metric, value, threshold, kind in CHECKS:
        value = endpoint if metric == "endpointStructureDifference" else value
        passed = check_id not in failed
        margin = threshold - value if kind == "max" else value - threshold
        checks.append({
            "checkId": check_id,
            "metric": metric,
            "value": value,
            "threshold": threshold,
            "thresholdKind": kind,
            "margin": margin,
            "passed": passed,
        })
    return {
        "schemaVersion": "groove-sidewall-source-consistency/1",
        "thresholdVersion": "sidewall-source-consistency-v1",
        "enabled": True,
        "status": status,
        "metrics": metrics,
        "checks": checks,
        "failedChecks": failed,
    }


class SourceConsistencyAdjudicationTests(unittest.TestCase):
    def enabled_config(self) -> dict:
        return {**DEFAULT_SOURCE_CONSISTENCY_ADJUDICATION_CONFIG, "enabled": True}

    def test_exact_contrast_only_clean_structure_is_accepted_override_without_mutation(self) -> None:
        source = source_evidence(endpoint=0.02029454542025491)
        before = copy.deepcopy(source)
        result = adjudicate_source_consistency(source, self.enabled_config())
        self.assertEqual(before, source)
        self.assertEqual("ACCEPTED_OVERRIDE", result["decision"])
        self.assertEqual("rejected", result["originalStatus"])
        self.assertEqual("accepted", result["effectiveStatus"])
        self.assertEqual(["edge_contrast_asymmetry"], result["originalFailedChecks"])
        self.assertTrue(result["imagePoseReleaseAllowed"])
        self.assertFalse(result["authoritative"])
        self.assertFalse(result["plcAllowed"])
        self.assertFalse(result["manualTruthAppliedAtRuntime"])
        self.assertEqual([], result["failedChecks"])

    def test_known_mixed_endpoint_structure_and_multiple_failures_remain_rejected(self) -> None:
        mixed = adjudicate_source_consistency(
            source_evidence(endpoint=0.07641190021573054), self.enabled_config(),
        )
        self.assertEqual("REJECTED", mixed["decision"])
        self.assertEqual("rejected", mixed["effectiveStatus"])
        self.assertFalse(mixed["imagePoseReleaseAllowed"])
        self.assertIn("strict_endpoint_structure", mixed["failedChecks"])

        multiple = adjudicate_source_consistency(
            source_evidence(
                endpoint=0.02,
                failed=["edge_contrast_asymmetry", "edge_gradient_asymmetry"],
            ),
            self.enabled_config(),
        )
        self.assertEqual("REJECTED", multiple["decision"])
        self.assertIn("exact_contrast_only_failure", multiple["failedChecks"])
        self.assertIn("all_required_noncontrast_checks_pass", multiple["failedChecks"])

    def test_missing_unknown_duplicate_or_nonfinite_evidence_is_not_evaluated(self) -> None:
        cases = []
        missing = source_evidence()
        missing["metrics"].pop("normalizedProfileMae")
        cases.append(missing)
        unknown = source_evidence()
        unknown["checks"].append({**unknown["checks"][0], "checkId": "unknown_check"})
        cases.append(unknown)
        duplicate = source_evidence()
        duplicate["checks"].append(copy.deepcopy(duplicate["checks"][0]))
        cases.append(duplicate)
        nonfinite = source_evidence()
        nonfinite["metrics"]["endpointStructureDifference"] = math.nan
        cases.append(nonfinite)
        for source in cases:
            with self.subTest(source=source):
                result = adjudicate_source_consistency(source, self.enabled_config())
                self.assertEqual("NOT_EVALUATED", result["decision"])
                self.assertEqual("not_evaluated", result["effectiveStatus"])
                self.assertFalse(result["imagePoseReleaseAllowed"])
                self.assertTrue(result["failedChecks"])

    def test_original_accepted_is_not_needed_and_disabled_is_legacy_no_field(self) -> None:
        accepted = source_evidence(failed=[], status="accepted")
        for check in accepted["checks"]:
            check["passed"] = True
        self.assertEqual(
            "NOT_NEEDED",
            adjudicate_source_consistency(accepted, self.enabled_config())["decision"],
        )
        self.assertIsNone(adjudicate_source_consistency(accepted, None))
        self.assertIsNone(adjudicate_source_consistency(
            accepted, DEFAULT_SOURCE_CONSISTENCY_ADJUDICATION_CONFIG,
        ))

    def test_configuration_is_strict_default_off_and_development_only(self) -> None:
        merged = merged_source_consistency_adjudication_config(None)
        self.assertFalse(merged["enabled"])
        self.assertTrue(merged["development_only"])
        for key, value in (
            ("max_endpoint_structure_difference", 1.1),
            ("max_endpoint_structure_difference", math.nan),
            ("development_only", False),
            ("unexpected", True),
        ):
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                merged_source_consistency_adjudication_config({key: value})

    @unittest.skipIf(jsonschema is None, "jsonschema is installed by the explicit Schema gate")
    def test_output_matches_dedicated_schema(self) -> None:
        root = Path(__file__).resolve().parents[1]
        schema = json.loads(
            (root / "contracts" / "source-consistency-adjudication.schema.json")
            .read_text(encoding="utf-8")
        )
        jsonschema.Draft202012Validator.check_schema(schema)
        jsonschema.validate(
            adjudicate_source_consistency(source_evidence(), self.enabled_config()),
            schema,
        )
        upstream_not_evaluated = source_evidence(status="not_evaluated")
        upstream_not_evaluated["metrics"] = {}
        upstream_not_evaluated["checks"] = []
        upstream_not_evaluated["failedChecks"] = ["refinement_not_accepted"]
        jsonschema.validate(
            adjudicate_source_consistency(upstream_not_evaluated, self.enabled_config()),
            schema,
        )
        malformed_status = source_evidence(status="unexpected")
        malformed_result = adjudicate_source_consistency(malformed_status, self.enabled_config())
        self.assertIsNone(malformed_result["originalStatus"])
        jsonschema.validate(malformed_result, schema)

    def test_scalar_adjudication_p95_is_below_five_milliseconds(self) -> None:
        source = source_evidence()
        config = self.enabled_config()
        samples = []
        for _ in range(500):
            started = time.perf_counter_ns()
            adjudicate_source_consistency(source, config)
            samples.append((time.perf_counter_ns() - started) / 1_000_000.0)
        p95 = statistics.quantiles(samples, n=100, method="inclusive")[94]
        self.assertLessEqual(p95, 5.0)

    def test_summary_separates_original_effective_guidance_and_plc(self) -> None:
        adjudication = adjudicate_source_consistency(source_evidence(), self.enabled_config())
        payload = summarize([
            {
                "result": {
                    "valid": True,
                    "guidanceStatus": "DETECTED_NEEDS_ADJUSTMENT",
                    "rotationDirection": "CLOCKWISE",
                    "plcCommand": None,
                },
                "diagnostics": {"sidewallSourceConsistencyAdjudication": adjudication},
                "error": None,
            },
            {
                "result": {
                    "valid": False,
                    "guidanceStatus": "NOT_AVAILABLE",
                    "rotationDirection": None,
                    "plcCommand": None,
                },
                "diagnostics": {},
                "error": {"code": "GROOVE_RECOGNITION_FAILED"},
            },
        ])
        self.assertEqual(2, payload["resultCount"])
        self.assertEqual(1, payload["adjudicationCount"])
        self.assertEqual(1, payload["validCount"])
        self.assertEqual({"ACCEPTED_OVERRIDE": 1}, payload["decisionCounts"])
        self.assertEqual(0, payload["plcCommandNonNullCount"])
        self.assertFalse(payload["manualTruthAppliedAtRuntime"])

    def test_experimental_materializer_preserves_original_contrast_and_rejects_relaxation(self) -> None:
        base = {
            "detector": {
                "diagnostic_mode": "single_real_groove",
                "groove_refinement": {"threshold_version": "groove-sidewall-subpixel-v2"},
                "sidewall_source_consistency": {"enabled": True},
            }
        }
        configured = build_experimental_config(base)
        self.assertNotIn("source_consistency_adjudication", base["detector"])
        self.assertEqual(
            0.12,
            configured["detector"]["sidewall_source_consistency"][
                "max_contrast_normalized_difference"
            ],
        )
        self.assertTrue(configured["detector"]["source_consistency_adjudication"]["enabled"])
        self.assertTrue(configured["detector"]["source_consistency_adjudication"]["development_only"])
        relaxed = copy.deepcopy(base)
        relaxed["detector"]["sidewall_source_consistency"][
            "max_contrast_normalized_difference"
        ] = 0.20
        with self.assertRaisesRegex(ValueError, "changed original contrast threshold"):
            build_experimental_config(relaxed)

    def enabled_v2_config(self) -> dict:
        return {
            "schema_version": "source-consistency-adjudication/2",
            "enabled": True,
            "strategy_version": "locked-noncontrast-gates-v2",
            "development_only": True,
        }

    def fixture_source_excluded(self) -> dict:
        return {
            "schemaVersion": "fixture-groove-source-exclusion/1",
            "status": "verified",
            "fixtureBodiesVerified": True,
            "uContourComplete": True,
            "fixtureSourceExcluded": True,
            "candidateSelectionUsedFixedAngle": False,
        }

    def enabled_v3_config(self) -> dict:
        return {
            "schema_version": "source-consistency-adjudication/3",
            "enabled": True,
            "strategy_version": "locked-shape-profile-fixture-gates-v3",
            "development_only": True,
        }

    def enabled_v4_config(self) -> dict:
        return {
            "schema_version": "source-consistency-adjudication/4",
            "enabled": True,
            "strategy_version": "locked-visible-boundary-ownership-v4",
            "development_only": True,
        }

    def radial_fixture_source_excluded(self) -> dict:
        return {
            "schemaVersion": "fixture-groove-source-exclusion/2",
            "status": "verified", "fixtureBodiesVerified": True,
            "uContourComplete": True, "fixtureSourceExcluded": True,
            "candidateSelectionUsedFixedAngle": False,
            "radialSidewallsVerified": True, "radialRecoveryApplied": True,
        }

    def test_v2_uses_locked_noncontrast_checks_without_own_numeric_threshold(self) -> None:
        source = source_evidence(endpoint=0.149)
        before = copy.deepcopy(source)
        result = adjudicate_source_consistency(
            source, self.enabled_v2_config(),
            fixture_source_evidence=self.fixture_source_excluded(),
        )
        self.assertEqual(before, source)
        self.assertEqual("source-consistency-adjudication/2", result["schemaVersion"])
        self.assertEqual("ACCEPTED_OVERRIDE", result["decision"])
        self.assertEqual("accepted", result["effectiveStatus"])
        self.assertNotIn("strict_endpoint_structure", {
            item["checkId"] for item in result["checks"]
        })
        self.assertFalse(result["authoritative"])
        self.assertFalse(result["plcAllowed"])

    def test_v2_contrast_only_is_diagnostic_without_fixture_source_exclusion(self) -> None:
        result = adjudicate_source_consistency(
            source_evidence(endpoint=0.02), self.enabled_v2_config(),
        )
        self.assertEqual("REJECTED", result["decision"])
        self.assertEqual("rejected", result["effectiveStatus"])
        self.assertFalse(result["imagePoseReleaseAllowed"])
        self.assertIn("fixture_source_exclusion_verified", result["failedChecks"])

    def test_v2_rejects_any_structural_failure_and_malformed_evidence(self) -> None:
        multiple = source_evidence(
            endpoint=0.20,
            failed=["edge_contrast_asymmetry", "endpoint_structure_inconsistent"],
        )
        result = adjudicate_source_consistency(multiple, self.enabled_v2_config())
        self.assertEqual("REJECTED", result["decision"])
        self.assertIn("exact_contrast_only_failure", result["failedChecks"])
        self.assertIn("all_locked_noncontrast_checks_pass", result["failedChecks"])
        malformed = source_evidence()
        malformed["metrics"]["radialCoverageDifference"] = math.nan
        result = adjudicate_source_consistency(malformed, self.enabled_v2_config())
        self.assertEqual("NOT_EVALUATED", result["decision"])

    def test_v3_allows_only_photometric_asymmetry_with_radial_u_contour_proof(self) -> None:
        source = source_evidence(
            endpoint=0.139,
            failed=["edge_contrast_asymmetry", "edge_gradient_asymmetry"],
        )
        accepted = adjudicate_source_consistency(
            source, self.enabled_v3_config(),
            fixture_source_evidence=self.radial_fixture_source_excluded(),
        )
        self.assertEqual("ACCEPTED_OVERRIDE", accepted["decision"], accepted)
        self.assertTrue(accepted["imagePoseReleaseAllowed"])
        without_geometry = adjudicate_source_consistency(
            source, self.enabled_v3_config(), fixture_source_evidence=None,
        )
        self.assertEqual("REJECTED", without_geometry["decision"])
        structural = source_evidence(
            endpoint=0.2,
            failed=["edge_contrast_asymmetry", "endpoint_structure_inconsistent"],
        )
        rejected = adjudicate_source_consistency(
            structural, self.enabled_v3_config(),
            fixture_source_evidence=self.radial_fixture_source_excluded(),
        )
        self.assertEqual("REJECTED", rejected["decision"])
        self.assertIn("photometric_only_failure", rejected["failedChecks"])

        legacy_contrast_only = adjudicate_source_consistency(
            source_evidence(endpoint=0.02), self.enabled_v3_config(),
            fixture_source_evidence=self.fixture_source_excluded(),
        )
        self.assertEqual("ACCEPTED_OVERRIDE", legacy_contrast_only["decision"])

    def test_v3_fixture_proof_follows_actual_recovery_path(self) -> None:
        source = source_evidence(
            endpoint=0.07,
            failed=["edge_contrast_asymmetry", "edge_gradient_asymmetry"],
        )
        result = adjudicate_source_consistency(
            source, self.enabled_v3_config(),
            fixture_source_evidence=self.fixture_source_excluded(),
        )
        self.assertEqual("ACCEPTED_OVERRIDE", result["decision"], result)

    def test_v4_allows_endpoint_scalar_only_with_recovery_or_boundary_ownership(self) -> None:
        source = source_evidence(
            endpoint=0.178,
            failed=[
                "edge_contrast_asymmetry", "edge_gradient_asymmetry",
                "endpoint_structure_inconsistent",
            ],
        )
        recovered = adjudicate_source_consistency(
            source, self.enabled_v4_config(),
            fixture_source_evidence=self.radial_fixture_source_excluded(),
        )
        self.assertEqual("ACCEPTED_OVERRIDE", recovered["decision"], recovered)
        self.assertEqual("recovery_verified", recovered["sourceSeparationBasis"])

        complete_u = adjudicate_source_consistency(
            source, self.enabled_v4_config(),
            fixture_source_evidence=self.fixture_source_excluded(),
        )
        self.assertEqual("ACCEPTED_OVERRIDE", complete_u["decision"], complete_u)
        self.assertEqual("complete_u_contour", complete_u["sourceSeparationBasis"])

        boundary = {
            "schemaVersion": "fixture-groove-source-exclusion/3",
            "status": "verified", "fixtureBodiesVerified": True,
            "twoSidewallsComplete": True, "uContourComplete": False,
            "fixtureSourceExcluded": True,
            "visibleBoundaryOwnershipVerified": True,
            "centralFloorTrackPresent": True,
            "candidateSelectionUsedFixedAngle": False,
            "manualTruthAppliedAtRuntime": False,
        }
        contrast_only = adjudicate_source_consistency(
            source_evidence(endpoint=0.04), self.enabled_v4_config(),
            fixture_source_evidence=boundary,
        )
        self.assertEqual("ACCEPTED_OVERRIDE", contrast_only["decision"], contrast_only)
        self.assertEqual("visible_boundary_ownership", contrast_only["sourceSeparationBasis"])


if __name__ == "__main__":
    unittest.main()
