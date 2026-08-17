import json
import math
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

import jsonschema

from algorithms.hole_2.current_capture import (
    SimilarityTransform,
    build_feature_outputs,
    sanitize_json_value,
    validate_result_contract,
)
from tools.run_current_capture import main as run_cli_main


class CurrentCaptureContractTests(unittest.TestCase):
    def test_dual_coordinate_output_preserves_reference_columns(self):
        transform = SimilarityTransform(100.0, 40.0, 0.75, 90.0)
        measurements = {
            "d7_x1": 10.0, "d7_y1": 20.0, "d7_x2": 110.0, "d7_y2": 20.0,
            "d7_length": 100.0, "d7.quality.upstream": "ok:dual_boundary_fit",
            "d7.quality.candidate_fallback_pass": "v6_original_quality",
            "Phi12_2_cx": 80.0, "Phi12_2_cy": 70.0, "Phi12_2_r": 30.0,
            "Phi12_2_diameter_px": 60.0, "Phi12_2.quality.edge_points": 77.0,
            "Phi12_2.quality.fit_residual_px": 0.4,
            "Phi12_2.quality.candidate_recovery_pass": "expanded_radius",
            "Phi12_2.quality.candidate_evidence_arc_segments_target_px": [
                {"side": "reference_left", "pointsPx": [[140.0, 92.5], [137.5, 100.0], [140.0, 107.5]]},
                {"side": "reference_right", "pointsPx": [[170.0, 92.5], [172.5, 100.0], [170.0, 107.5]]},
            ],
            "d7.quality.candidate_boundary_evidence_target_px": [
                {
                    "side": "A", "rawPointsPx": [[85.0, 47.5], [85.0, 62.5]],
                    "supportPointsPx": [[85.0, 70.0]],
                    "supportTransitionPairsPx": [[[81.0, 70.0], [89.0, 70.0]]],
                    "supportEvidenceMode": "paired_transition_midpoints_plus_contiguous_outward_paired_support",
                    "segmentPointsPx": [[85.0, 47.5], [85.0, 70.0]],
                    "lineEquation": [1.0, 0.0, -85.0],
                },
                {
                    "side": "B", "rawPointsPx": [[85.0, 122.5], [85.0, 137.5]],
                    "supportPointsPx": [[85.0, 145.0]],
                    "supportTransitionPairsPx": [[[81.0, 145.0], [89.0, 145.0]]],
                    "supportEvidenceMode": "paired_transition_midpoints_plus_contiguous_outward_paired_support",
                    "segmentPointsPx": [[85.0, 122.5], [85.0, 145.0]],
                    "lineEquation": [1.0, 0.0, -85.0],
                },
            ],
        }
        features, compatible = build_feature_outputs(measurements, transform, phi_support_angles=[0.0, math.pi / 2])
        self.assertEqual(100.0, compatible["d7_length"])
        self.assertEqual(60.0, compatible["Phi12_2_diameter_px"])
        self.assertTrue(features["7"]["measurementValid"])
        self.assertTrue(features["7"]["evidenceComplete"])
        self.assertEqual("complete", features["7"]["evidenceAuditStatus"])
        self.assertEqual("valid", features["7"]["qualityStatus"])
        self.assertEqual("v6_original_quality", features["7"]["quality"]["candidate_fallback_pass"])
        self.assertEqual("v6_original_quality", features["7"]["recoveryPass"])
        self.assertAlmostEqual(75.0, features["7"]["target"]["lengthPx"])
        self.assertTrue(features["Phi12.2"]["measurementValid"])
        self.assertTrue(features["Phi12.2"]["evidenceComplete"])
        self.assertEqual("complete", features["Phi12.2"]["evidenceAuditStatus"])
        self.assertEqual("expanded_radius", features["Phi12.2"]["quality"]["candidate_recovery_pass"])
        self.assertEqual("expanded_radius", features["Phi12.2"]["recoveryPass"])
        self.assertAlmostEqual(22.5, features["Phi12.2"]["target"]["radiusPx"])
        self.assertEqual(2, len(features["Phi12.2"]["target"]["supportPointsPx"]))
        self.assertEqual(
            "outer_contour_calibrated_visible_arc",
            features["Phi12.2"]["target"]["rawEdgeEvidence"]["semantics"],
        )
        self.assertEqual(
            ["reference_left"],
            [
                segment["side"]
                for segment in features["Phi12.2"]["target"]["rawEdgeEvidence"]["arcSegments"]
            ],
        )
        self.assertFalse(
            features["Phi12.2"]["target"]["fittedGeometry"]["isDetectedContour"]
        )
        self.assertEqual(
            "perpendicular_distance",
            features["7"]["target"]["measurementAnnotation"]["type"],
        )
        self.assertEqual(
            2, len(features["7"]["target"]["fittedGeometry"]["boundaries"])
        )
        for boundary in features["7"]["target"]["rawEdgeEvidence"]["boundaries"]:
            self.assertEqual(1, len(boundary["supportPointsPx"]))
            self.assertEqual(1, len(boundary["supportTransitionPairsPx"]))
            self.assertEqual(
                "paired_transition_midpoints_plus_contiguous_outward_paired_support",
                boundary["supportEvidenceMode"],
            )
        schema = json.loads((
            Path(__file__).resolve().parents[1]
            / "specs/016-measurement-evidence-geometry-audit/contracts/measurement-evidence-v1.schema.json"
        ).read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator(schema).validate({
            "7": features["7"]["target"],
            "Phi12.2": features["Phi12.2"]["target"],
        })
        audit_schema = json.loads((
            Path(__file__).resolve().parents[1]
            / "specs/016-measurement-evidence-geometry-audit/contracts/evidence-audit-v1.schema.json"
        ).read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator(audit_schema).validate({
            name: {
                key: feature[key]
                for key in (
                    "measurementValid", "evidenceComplete",
                    "evidenceAuditStatus", "evidenceAuditReason",
                )
            }
            for name, feature in features.items()
        })

    def test_measurement_validity_is_independent_from_evidence_completeness(self):
        transform = SimilarityTransform(0.0, 0.0, 1.0, 0.0)
        measurements = {
            "d7_x1": 10.0, "d7_y1": 20.0, "d7_x2": 50.0, "d7_y2": 20.0,
            "d7_length": 40.0,
            "Phi12_2_cx": 80.0, "Phi12_2_cy": 70.0, "Phi12_2_r": 30.0,
            "Phi12_2_diameter_px": 60.0,
            "Phi12_2.quality.candidate_evidence_arc_segments_target_px": [
                {"side": "reference_left", "pointsPx": [[50.0, 65.0], [50.0, 75.0]]},
            ],
        }
        features, _ = build_feature_outputs(
            measurements, transform, phi_support_angles=[0.0]
        )
        self.assertTrue(features["7"]["measurementValid"])
        self.assertFalse(features["7"]["evidenceComplete"])
        self.assertEqual("unavailable", features["7"]["evidenceAuditStatus"])
        self.assertEqual(
            "boundary_evidence_unavailable", features["7"]["evidenceAuditReason"]
        )
        self.assertTrue(features["Phi12.2"]["measurementValid"])
        self.assertTrue(features["Phi12.2"]["evidenceComplete"])
        self.assertEqual("complete", features["Phi12.2"]["evidenceAuditStatus"])
        self.assertIsNone(features["Phi12.2"]["evidenceAuditReason"])
        self.assertEqual(
            "outer_contour_calibrated_visible_arc",
            features["Phi12.2"]["target"]["rawEdgeEvidence"]["semantics"],
        )

    def test_v6_review_geometry_does_not_upgrade_formal_evidence(self):
        transform = SimilarityTransform(0.0, 0.0, 1.0, 0.0)
        review = [
            {
                "side": side,
                "semantics": "legacy_single_gradient_boundary",
                "rawPointsPx": [[x, 10.0], [x, 30.0]],
                "inlierPointsPx": [[x, 10.0], [x, 30.0]],
                "lineEquation": [1.0, 0.0, -x],
                "segmentPointsPx": [[x, 10.0], [x, 30.0]],
                "reviewOnly": True,
                "equivalentToFormalBoundary": False,
            }
            for side, x in (("A", 20.0), ("B", 80.0))
        ]
        measurements = {
            "d7_x1": 20.0, "d7_y1": 20.0,
            "d7_x2": 80.0, "d7_y2": 20.0, "d7_length": 60.0,
            "d7.quality.candidate_fallback_pass": "v6_original_quality",
            "d7.quality.candidate_legacy_boundary_review_target_px": review,
            "Phi12_2_cx": 100.0, "Phi12_2_cy": 100.0,
            "Phi12_2_r": 30.0, "Phi12_2_diameter_px": 60.0,
            "Phi12_2.quality.candidate_evidence_arc_segments_target_px": [
                {"side": "reference_left", "pointsPx": [[70.0, 95.0], [70.0, 105.0]]},
            ],
        }
        features, _ = build_feature_outputs(measurements, transform, [0.0])
        d7 = features["7"]
        self.assertTrue(d7["measurementValid"])
        self.assertFalse(d7["evidenceComplete"])
        self.assertEqual("unavailable", d7["evidenceAuditStatus"])
        self.assertEqual([], d7["target"]["rawEdgeEvidence"]["boundaries"])
        self.assertEqual([], d7["target"]["fittedGeometry"]["boundaries"])
        self.assertEqual(2, len(d7["target"]["rawEdgeEvidence"]["legacyReviewBoundaries"]))
        self.assertEqual(2, len(d7["target"]["fittedGeometry"]["legacyReviewBoundaries"]))

    def test_phi_valid_without_calibrated_arc_is_explicitly_unauditable(self):
        transform = SimilarityTransform(0.0, 0.0, 1.0, 0.0)
        measurements = {
            "Phi12_2_cx": 80.0, "Phi12_2_cy": 70.0, "Phi12_2_r": 30.0,
            "Phi12_2_diameter_px": 60.0,
        }
        features, _ = build_feature_outputs(
            measurements, transform, phi_support_angles=[0.0]
        )
        self.assertTrue(features["Phi12.2"]["measurementValid"])
        self.assertFalse(features["Phi12.2"]["evidenceComplete"])
        self.assertEqual("unavailable", features["Phi12.2"]["evidenceAuditStatus"])
        self.assertEqual(
            "calibrated_arc_evidence_unavailable",
            features["Phi12.2"]["evidenceAuditReason"],
        )

    def test_partial_failure_does_not_change_other_feature(self):
        transform = SimilarityTransform(0.0, 0.0, 1.0, 0.0)
        measurements = {
            "d7_x1": float("nan"), "d7_y1": float("nan"),
            "d7_x2": float("nan"), "d7_y2": float("nan"), "d7_length": float("nan"),
            "d7.quality.upstream": "failed:p1_boundary_fit",
            "Phi12_2_cx": 80.0, "Phi12_2_cy": 70.0, "Phi12_2_r": 30.0,
            "Phi12_2_diameter_px": 60.0,
        }
        features, _ = build_feature_outputs(measurements, transform, phi_support_angles=[0.0])
        self.assertFalse(features["7"]["measurementValid"])
        self.assertEqual("not_applicable", features["7"]["evidenceAuditStatus"])
        self.assertEqual("invalid", features["7"]["qualityStatus"])
        self.assertIsNone(features["7"]["target"])
        self.assertTrue(features["Phi12.2"]["measurementValid"])

    def test_nonfinite_numbers_are_serialized_as_null(self):
        value = sanitize_json_value({"nan": float("nan"), "inf": float("inf"), "ok": 1.25})
        self.assertEqual({"nan": None, "inf": None, "ok": 1.25}, value)
        json.dumps(value, allow_nan=False)

    def test_runtime_contract_has_no_target_annotation_role(self):
        fixture = {
            "schemaVersion": "hole2-current-capture-result/2",
            "algorithmVersion": "test",
            "configVersion": "test",
            "runtimeInputs": [
                {"role": "authoritative_reference_annotation", "path": "manual.json", "sha256": "018e3449c051c15f7946315bd0d7f21cd79f4d4983efca0d11c7d98f02bfffa6"},
                {"role": "authoritative_reference_image", "path": "manual.bmp", "sha256": "faf357c2e6e8e58d667f76a3d9ed4f4d51ab4d451c2661cf0efbc641405b2d8b"},
                {"role": "target_image", "path": "target.bmp", "sha256": "0" * 64},
                {"role": "configuration", "path": "config.json", "sha256": "1" * 64},
            ],
            "registration": {
                "registrationValid": False, "failureReason": "test",
                "primaryFailureReason": "test", "registrationRecoveryPass": None,
                "candidates": [{}, {}, {}, {}], "selected": None, "transform": None,
                "inverseTransform": None,
                "transformDirection": "reference_px_to_target_px",
                "inverseTransformDirection": "target_px_to_reference_px",
                "referenceImageSize": [100, 100], "targetImageSize": [100, 100],
            },
            "features": {
                "7": {"featureCode": "HOLE2-DIM-7", "measurementValid": False, "evidenceComplete": False, "evidenceAuditStatus": "not_applicable", "evidenceAuditReason": "measurement_invalid", "qualityStatus": "invalid", "failureReason": "registration_invalid", "sourceDetector": "v6", "recoveryPass": None, "reference": None, "target": None, "quality": {}},
                "Phi12.2": {"featureCode": "HOLE2-DIA-12_2", "measurementValid": False, "evidenceComplete": False, "evidenceAuditStatus": "not_applicable", "evidenceAuditReason": "measurement_invalid", "qualityStatus": "invalid", "failureReason": "registration_invalid", "sourceDetector": "v6", "recoveryPass": None, "reference": None, "target": None, "quality": {}},
            },
            "authoritativeReference": {
                "referenceVersion": "hole2-authoritative-manual-reference/1",
                "templateSelfCheck": False,
                "transformDirection": "authoritative_reference_px_to_target_px",
                "transform": None,
                "registrationEvidenceSource": "authoritative_reference_image_pixels",
                "annotationShapeSummary": {
                    "7": {"shapeType": "line", "pointCount": 2},
                    "Phi12.2": {"shapeType": "linestrip", "pointCount": 80},
                },
            },
            "qualityStatus": {
                "technicalValid": False, "state": "registration_invalid",
                "failureReasons": ["registration:test"],
                "productionDisposition": "not_evaluated",
            },
            "geometryConsistency": {
                "evaluated": False, "outlier": False, "rejected": False,
                "failureReason": "registration_invalid",
                "outlierReason": None,
                "ratioSource": "authoritative_manual_reference_geometry",
                "decision": "not_evaluated",
                "corroboratingEvidence": [],
                "hardRejectionPolicy": "ratio_outlier_requires_independent_risk_evidence",
                "outputAdjustmentApplied": False,
            },
            "referenceMeasurements": {}, "v6Measurements": {},
            "timingMs": {"total": 1.0},
            "evidenceScope": "single_image_pixel_geometry_only_not_repeatability_mm_accuracy_or_production_ok_ng",
            "errors": [],
        }
        validate_result_contract(fixture)
        fixture["runtimeInputs"][2]["role"] = "target_annotation"
        with self.assertRaisesRegex(ValueError, "runtime inputs"):
            validate_result_contract(fixture)

    def test_cli_returns_nonzero_when_any_measurement_is_invalid(self):
        invalid_result = {
            "qualityStatus": {
                "technicalValid": False,
                "state": "measurement_invalid",
                "failureReasons": ["feature:7:boundary_points_below_gate"],
            },
            "registration": {
                "registrationValid": True,
                "selected": {"orientationDeg": 270},
            },
            "features": {
                "7": {"measurementValid": False},
                "Phi12.2": {"measurementValid": True},
            },
            "timingMs": {"total": 1.0},
            "authoritativeReference": {"templateSelfCheck": False},
        }
        argv = [
            "run_current_capture.py",
            "--reference-annotation", "manual.json",
            "--reference-image", "manual.bmp",
            "--target-image", "target.bmp",
            "--config", "config.json", "--out", "/tmp/result.json",
        ]
        with patch("sys.argv", argv), \
                patch("tools.run_current_capture.run_current_capture", return_value=invalid_result), \
                patch("tools.run_current_capture.write_result"):
            self.assertEqual(2, run_cli_main())


if __name__ == "__main__":
    unittest.main()
