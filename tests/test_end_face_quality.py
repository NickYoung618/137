from __future__ import annotations

import copy
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from algorithms.end_face import CORE_SOURCE_SHA256
from algorithms.end_face.adapter import EndFaceInspector
from algorithms.end_face.quality import diagnose_core_quality, evaluate_quality, load_quality_policy


ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "config/end_face_quality.example.json"
DESKTOP_ALGORITHM_ZIP = Path("/home/ubuntu/disk/zzx/算法/算法.zip")


def localized_measurements() -> dict[str, object]:
    return {
        "transform.target_center_x_px": 50.0,
        "transform.target_center_y_px": 40.0,
        "transform.scale": 1.0,
        "transform.rotation_deg": 0.5,
        "19��.detect.source": "short_line_transform_fallback",
        "19��.quality.measurement_valid": 0.0,
        "19��.quality.anomaly_flag": 1.0,
        "19��.quality.anomaly_reason": "short_line_lateral_edge_not_found",
    }


LOCALIZATION_METHOD = "circle-alignment rotation_score=10.0, notch_check(Δ=0.0deg, prom=20.0)"


class EndFaceQualityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.policy = load_quality_policy(POLICY_PATH)

    def test_feature_failure_does_not_veto_localization(self) -> None:
        quality = evaluate_quality(
            localized_measurements(), LOCALIZATION_METHOD, (100, 80), self.policy, POLICY_PATH
        )
        self.assertTrue(quality["localization"]["valid"])
        self.assertFalse(quality["measurementCompleteness"]["allValid"])
        feature = quality["featureQuality"]["19��"]
        self.assertFalse(feature["coreValid"])
        self.assertEqual("19", feature["canonicalFeature"])
        self.assertEqual("feature_measurement", feature["classification"])
        self.assertEqual("short_line_lateral_edge_not_found", feature["reason"])

    def test_localization_policy_rejects_out_of_range_scale_without_promoting_feature(self) -> None:
        measurements = localized_measurements()
        measurements["transform.scale"] = 1.5
        quality = evaluate_quality(measurements, LOCALIZATION_METHOD, (100, 80), self.policy, POLICY_PATH)
        self.assertFalse(quality["localization"]["valid"])
        self.assertIn("scale_range", quality["localization"]["failedChecks"])
        self.assertFalse(quality["featureQuality"]["19��"]["coreValid"])

    def test_explicit_required_feature_can_veto_localization_but_not_change_core_status(self) -> None:
        policy = copy.deepcopy(self.policy)
        policy["localization"]["requiredFeatureLabels"] = ["19"]
        quality = evaluate_quality(localized_measurements(), LOCALIZATION_METHOD, (100, 80), policy, POLICY_PATH)
        self.assertFalse(quality["localization"]["valid"])
        self.assertIn("required_feature:19", quality["localization"]["failedChecks"])
        self.assertFalse(quality["featureQuality"]["19��"]["coreValid"])
        self.assertEqual("localization_required", quality["featureQuality"]["19��"]["classification"])

    def test_orientation_requires_polar_or_notch_evidence(self) -> None:
        quality = evaluate_quality(
            localized_measurements(), "circle-alignment rotation_score=2.0", (100, 80), self.policy, POLICY_PATH
        )
        self.assertFalse(quality["localization"]["valid"])
        self.assertIn("orientation_evidence", quality["localization"]["failedChecks"])
        recovered = evaluate_quality(
            localized_measurements(),
            "circle-alignment rotation_score=2.0, notch_override(Δ=1.0deg, prom=20.0)",
            (100, 80), self.policy, POLICY_PATH,
        )
        self.assertTrue(recovered["localization"]["valid"])

    def test_diagnostic_catalog_traces_reported_core_paths(self) -> None:
        cases = {
            "short_line_lateral_edge_not_found": ("short_line_lateral_edge", "shortLinePeakRule"),
            "d46_radial_low_score": ("d46_radial_ncc", "minimumNccScore"),
            "template_anchor_fallback": ("middle_ring_template", "minimumTemplateScore"),
        }
        for reason, (path, threshold) in cases.items():
            with self.subTest(reason=reason):
                diagnostic = diagnose_core_quality({
                    "reason": reason,
                    "source": "test",
                    "fields": {
                        "d46_ncc_score": 0.2,
                        "template_score": 0.1,
                    },
                })
                self.assertEqual(path, diagnostic["detectorPath"])
                self.assertIn(threshold, diagnostic["fixedConditions"])

    def test_accessible_reference_keeps_19_and_30_invalid_but_localization_valid(self) -> None:
        if not DESKTOP_ALGORITHM_ZIP.is_file():
            self.skipTest(f"desktop algorithm zip unavailable: {DESKTOP_ALGORITHM_ZIP}")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with zipfile.ZipFile(DESKTOP_ALGORITHM_ZIP) as archive:
                selected = [
                    info for info in archive.infolist()
                    if info.filename.endswith(("sample_1_label.json", "sample_1_reference.bmp"))
                ]
                self.assertEqual(2, len(selected))
                for info in selected:
                    target = root / Path(info.filename).name
                    target.write_bytes(archive.read(info))
            inspector = EndFaceInspector(root / "sample_1_label.json", POLICY_PATH)
            payload = inspector.inspect(root / "sample_1_reference.bmp", task_id="reference-quality-test")

        self.assertEqual("succeeded", payload["technicalStatus"])
        self.assertEqual("a-end-face-result/2", payload["schemaVersion"])
        self.assertTrue(payload["result"]["localization"]["valid"])
        self.assertFalse(payload["result"]["measurementCompleteness"]["allValid"])
        invalid = payload["result"]["measurementCompleteness"]["invalidFeatures"]
        self.assertTrue(any(name.startswith("19") for name in invalid), invalid)
        self.assertTrue(any(name.startswith("30") for name in invalid), invalid)
        canonical_invalid = {
            item["canonicalFeature"]
            for item in payload["result"]["featureQuality"].values()
            if not item["coreValid"]
        }
        self.assertTrue({"19", "30"}.issubset(canonical_invalid), canonical_invalid)
        self.assertEqual(CORE_SOURCE_SHA256, payload["algorithm"]["coreSourceSha256"])


if __name__ == "__main__":
    unittest.main()
