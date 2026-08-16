from __future__ import annotations

import unittest
import json
import tempfile

from tools.evaluation_governance import build_static_repeatability, circular_statistics
from tests.test_a2_evaluation_governance import records
from tools.evaluation_governance import prepare_dataset
from pathlib import Path
from tools.evaluate_static_repeatability import main as evaluate_main


def result(sha: str, angle: float | None, *, elapsed: float = 10.0, cx: float = 100.0, valid: bool = True) -> dict:
    correction = None if angle is None else (85.0 - angle + 180.0) % 360.0 - 180.0
    direction = "NONE" if angle is not None and 80 <= angle <= 90 else ("CLOCKWISE" if correction is not None and correction > 0 else "COUNTERCLOCKWISE")
    return {
        "image": {"sha256": sha},
        "result": {
            "valid": valid,
            "detectionStatus": "DETECTED" if valid else "DETECTION_FAILED",
            "guidanceStatus": ("DETECTED_IN_POSITION" if direction == "NONE" else "DETECTED_NEEDS_ADJUSTMENT") if valid else "NOT_AVAILABLE",
            "currentAngleDeg": angle if valid else None,
            "rotationDirection": direction if valid else None,
        },
        "error": None if valid else {"code": "GROOVE_RECOGNITION_FAILED"},
        "diagnostics": {
            "elapsedMs": elapsed,
            "physicalOuterCircle": {"status": "accepted", "physicalCircle": {"centerX": cx, "centerY": 200.0, "radiusPx": 50.0}} if valid else None,
            "singleGroovePose": {"datumMeasurement": {"grooveOpeningPoint": {"x": cx + 5.0, "y": 220.0}}} if valid else None,
        },
    }


class StaticRepeatabilityTests(unittest.TestCase):
    def test_circular_statistics_cross_wrap(self) -> None:
        stats = circular_statistics([179.9, -179.9, 180.0 - 1e-9])
        self.assertAlmostEqual(0.2, stats["range"], places=6)
        self.assertLess(stats["standardDeviation"], 0.2)
        self.assertLess(stats["p95AbsoluteResidual"], 0.11)

    def test_group_reports_detection_geometry_timing_and_null_failures(self) -> None:
        inventory, grouping = records("normal:p1", "target", 20)
        manifest, eligibility, _ = prepare_dataset(Path("/unused"), inventory, grouping, verify_images=False)
        payloads = [result(item["sha256"], 82.0 + i * 0.001, elapsed=5 + i, cx=100 + i * 0.01) for i, item in enumerate(manifest["images"])]
        payloads[-1] = result(manifest["images"][-1]["sha256"], None, valid=False)
        report = build_static_repeatability(manifest, payloads, eligibility)
        group = report["groups"][0]
        self.assertEqual(19, group["detection"]["validCount"])
        self.assertEqual(1, group["detection"]["failedCount"])
        self.assertAlmostEqual(0.95, group["detection"]["validRate"])
        self.assertEqual(19, group["angle"]["n"])
        self.assertIsNotNone(group["geometry"]["circleCenterX"]["range"])
        self.assertEqual(20, group["timing"]["n"])
        self.assertEqual(23.0, group["timing"]["max"])
        self.assertEqual("TARGET_NEAR", group["guidanceClass"])

    def test_cross_group_summary_centers_residuals_and_covers_three_guidance_classes(self) -> None:
        all_i, all_g, payloads = [], [], []
        for offset, (sample, condition, angle) in enumerate((("p1", "near", 85.0), ("p2", "cw", 20.0), ("p3", "ccw", -150.0))):
            inv, grp = records(sample, condition, 20, start=offset * 100 + 1)
            all_i += inv; all_g += grp
        manifest, eligibility, _ = prepare_dataset(Path("/unused"), all_i, all_g, verify_images=False)
        centers = {"near": 85.0, "cw": 20.0, "ccw": -150.0}
        for item in manifest["images"]:
            payloads.append(result(item["sha256"], centers[item["conditionId"]] + (item["repeatIndex"] - 10) * 0.001))
        report = build_static_repeatability(manifest, payloads, eligibility)
        pooled = report["summary"]["pooledWithinGroupAngleResidual"]
        self.assertLess(pooled["range"], 0.03)
        self.assertEqual("COMPLETE", report["summary"]["guidanceCoverage"]["status"])
        self.assertEqual(1, report["summary"]["guidanceCoverage"]["groupCounts"]["TARGET_NEAR"])
        self.assertEqual(1, report["summary"]["guidanceCoverage"]["groupCounts"]["NEEDS_CLOCKWISE"])
        self.assertEqual(1, report["summary"]["guidanceCoverage"]["groupCounts"]["NEEDS_COUNTERCLOCKWISE"])

    def test_excluded_group_is_not_in_authoritative_summary(self) -> None:
        inventory, grouping = records("p1", "short", 18)
        manifest, eligibility, _ = prepare_dataset(Path("/unused"), inventory, grouping, verify_images=False)
        payloads = [result(item["sha256"], 85.0) for item in manifest["images"]]
        report = build_static_repeatability(manifest, payloads, eligibility)
        self.assertEqual(0, report["summary"]["eligibleGroupCount"])
        self.assertEqual(1, report["summary"]["excludedGroupCount"])
        self.assertEqual(0, report["summary"]["authoritativeFrameCount"])

    def test_evaluate_cli_writes_json_and_flat_group_csv(self) -> None:
        inventory, grouping = records("p1", "fixed", 20)
        manifest, eligibility, _ = prepare_dataset(Path("/unused"), inventory, grouping, verify_images=False)
        payloads = [result(item["sha256"], 85.0 + (item["repeatIndex"] - 10) * 0.001) for item in manifest["images"]]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest_path, eligibility_path, results_path = root / "manifest.json", root / "eligibility.json", root / "results.jsonl"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            eligibility_path.write_text(json.dumps(eligibility), encoding="utf-8")
            results_path.write_text("\n".join(json.dumps(item) for item in payloads) + "\n", encoding="utf-8")
            output = root / "report"
            self.assertEqual(0, evaluate_main(["--manifest", str(manifest_path), "--results", str(results_path), "--eligibility", str(eligibility_path), "--output-dir", str(output)]))
            self.assertTrue((output / "static-repeatability.json").is_file())
            self.assertIn("angle_range_deg", (output / "static-groups.csv").read_text())


if __name__ == "__main__":
    unittest.main()
