import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from tools.analyze_hole2_single_truth_study import (
    analyze_study,
    map_manifest,
    map_ordered_groups,
)


def _record(name, group="batch", *, d7=True, phi=True, length=100.0, diameter=170.0):
    return {
        "group": group,
        "imagePath": f"/external/{name}",
        "executionError": None,
        "result": {
            "registration": {"registrationValid": True},
            "features": {
                "7": {
                    "measurementValid": d7,
                    "failureReason": None if d7 else "tangent_boundary_fit_failed",
                    "sourceDetector": "d7-source",
                    "recoveryPass": None,
                    "target": {"lengthPx": length} if d7 else None,
                },
                "Phi12.2": {
                    "measurementValid": phi,
                    "failureReason": None if phi else "phase_failure",
                    "sourceDetector": "phi-source",
                    "recoveryPass": "center_recenter" if phi else None,
                    "target": {"diameterPx": diameter} if phi else None,
                },
            },
            "qualityStatus": {"technicalValid": d7 and phi, "state": "complete" if d7 and phi else "measurement_invalid"},
        },
    }


def _truth(status="PASS"):
    return {
        "schemaVersion": "hole2-latest-truth-key-metrics/1",
        "status": status,
        "truthHashes": {"targetImage": "image-sha", "targetAnnotation": "annotation-sha"},
        "7": {"lengthAbsoluteErrorPx": 0.7, "maximumAllowedPx": 2.0, "passed": status == "PASS"},
        "Phi12.2": {"diameterAbsoluteErrorPx": 0.1, "maximumAllowedPx": 1.0, "passed": status == "PASS"},
    }


class Hole2SingleTruthStudyTests(unittest.TestCase):
    def test_explicit_ordered_group_size_needs_population_role_map(self):
        records = [
            _record("a.bmp", group="normal"),
            _record("b.bmp", group="normal"),
            _record("c.bmp", group="normal"),
            _record("bad.bmp", group="defective"),
        ]
        mapped = map_ordered_groups(
            records,
            group_size=2,
            group_roles={
                "normal": ("normal", "evaluation"),
                "defective": ("defective", "observation"),
            },
        )
        self.assertEqual(
            ["normal-explicit-0000", "normal-explicit-0000", "normal-explicit-0001"],
            [item["captureGroupId"] for item in mapped[:3]],
        )
        self.assertEqual(("defective", "observation"), (mapped[3]["population"], mapped[3]["role"]))
        with self.assertRaisesRegex(ValueError, "group-role"):
            map_ordered_groups(records, group_size=2, group_roles={"normal": ("normal", "evaluation")})

    def test_manifest_is_strict_and_unique(self):
        records = [_record("a.bmp"), _record("b.bmp")]
        manifest = {"frames": [
            {"fileName": "a.bmp", "population": "normal", "role": "development", "captureGroupId": "part-1"},
        ]}
        with self.assertRaisesRegex(ValueError, "unmapped"):
            map_manifest(records, manifest)
        manifest["frames"].append(dict(manifest["frames"][0]))
        with self.assertRaisesRegex(ValueError, "duplicate"):
            map_manifest([records[0]], manifest)

    def test_cohorts_are_isolated_and_repeatability_is_diagnostic(self):
        records = [
            _record("a.bmp", length=100.0, diameter=170.0),
            _record("b.bmp", length=104.0, diameter=174.0),
            _record("bad.bmp", group="bad", d7=False, phi=False),
        ]
        manifest = {"frames": [
            {"fileName": "a.bmp", "population": "normal", "role": "development", "captureGroupId": "shared"},
            {"fileName": "b.bmp", "population": "normal", "role": "development", "captureGroupId": "shared"},
            {"fileName": "bad.bmp", "population": "defective", "role": "observation", "captureGroupId": "shared"},
        ]}
        mapped = map_manifest(records, manifest)
        report = analyze_study(mapped, _truth("PASS"), minimum_group_frames=2)
        self.assertEqual({"normal/development", "defective/observation"}, set(report["cohorts"]))
        self.assertEqual(2, len(report["captureGroups"]))
        normal = next(item for item in report["captureGroups"] if item["population"] == "normal")
        self.assertEqual(4.0, normal["features"]["7"]["rangePx"])
        self.assertEqual(2.0, normal["features"]["7"]["medianAbsoluteDeviationPx"])
        static = normal["features"]["7"]["staticRepeatability"]
        self.assertEqual("EVALUATED", static["evaluationStatus"])
        self.assertAlmostEqual(2.8284271247461903, static["sampleStandardDeviationPx"])
        self.assertAlmostEqual(16.970562748477143, static["sixSigmaPx"])
        self.assertNotIn("passed", static)
        self.assertEqual("diagnostic_not_accuracy", normal["evidenceScope"])
        self.assertEqual({"d7-source": 2}, normal["features"]["7"]["sourceDetectors"])

    def test_truth_failure_cannot_be_overridden(self):
        record = _record("a.bmp")
        manifest = {"frames": [
            {"fileName": "a.bmp", "population": "normal", "role": "development", "captureGroupId": "part-1"},
        ]}
        report = analyze_study(map_manifest([record], manifest), _truth("FAIL"), minimum_group_frames=2)
        self.assertEqual("FAIL", report["accuracyAnchor"]["status"])
        self.assertEqual("single_truth_only", report["accuracyAnchor"]["evidenceScope"])
        self.assertNotIn("status", report["cohorts"]["normal/development"])

        default_report = analyze_study(map_manifest([record], manifest), _truth("PASS"))
        static = default_report["captureGroups"][0]["features"]["7"]["staticRepeatability"]
        self.assertEqual("INCOMPLETE", static["evaluationStatus"])
        self.assertEqual(20, static["requiredValidFrames"])

    def test_cli_rejects_output_inside_git_worktree(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            jsonl = root / "input.jsonl"
            manifest = root / "manifest.json"
            truth = root / "truth.json"
            jsonl.write_text(json.dumps(_record("a.bmp")) + "\n", encoding="utf-8")
            manifest.write_text(json.dumps({"frames": [
                {"fileName": "a.bmp", "population": "normal", "role": "development", "captureGroupId": "part-1"},
            ]}), encoding="utf-8")
            truth.write_text(json.dumps(_truth()), encoding="utf-8")
            completed = subprocess.run([
                "uv", "run", "python", "tools/analyze_hole2_single_truth_study.py",
                "--jsonl", str(jsonl), "--manifest", str(manifest),
                "--truth-report", str(truth), "--output", "must-not-exist-study.json",
            ], capture_output=True, text=True)
        self.assertNotEqual(0, completed.returncode)
        self.assertIn("outside the Git worktree", completed.stderr)
        self.assertFalse(Path("must-not-exist-study.json").exists())


if __name__ == "__main__":
    unittest.main()
