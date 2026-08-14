import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from tools.analyze_hole2_batch import analyze_records, build_explicit_groups


def _record(index: int, *, registration=True, d7=True, phi=True, d7_length=100.0, phi_diameter=170.0):
    return {
        "group": "normal",
        "imagePath": f"/external/frame-{index}.bmp",
        "executionError": None,
        "result": {
            "registration": {"registrationValid": registration, "failureReason": None if registration else "no_valid_candidate"},
            "features": {
                "7": {"measurementValid": d7, "failureReason": None if d7 else "failed", "target": None if not d7 else {"lengthPx": d7_length}},
                "Phi12.2": {"measurementValid": phi, "failureReason": None if phi else "failed", "target": None if not phi else {"diameterPx": phi_diameter}},
            },
            "qualityStatus": {"technicalValid": registration and d7 and phi, "state": "complete" if registration and d7 and phi else "measurement_invalid"},
            "timingMs": {"total": 10.0 + index},
        },
    }


class Hole2BatchDiagnosticTests(unittest.TestCase):
    def test_explicit_group_size_drives_runs_repeatability_and_ratio_outliers(self):
        records = [
            _record(0), _record(1, registration=False, d7=False, phi=False),
            _record(2, registration=False, d7=False, phi=False), _record(3),
        ]
        groups = build_explicit_groups(records, group_size=2, manifest=None)
        report = analyze_records(records, groups, ratio_baseline=0.585984, ratio_thresholds=[0.02, 0.05])
        self.assertEqual([2, 2], [group["count"] for group in report["repeatabilityGroups"]])
        self.assertEqual(1, len(report["consecutiveFailureRuns"]["registration"]))
        self.assertEqual(2, report["consecutiveFailureRuns"]["registration"][0]["count"])
        self.assertEqual(2, report["geometryConsistency"]["bothValidCount"])
        self.assertIn("0.02", report["geometryConsistency"]["absoluteDeviationCounts"])

    def test_grouping_is_never_inferred_from_filename(self):
        records = [_record(0)]
        with self.assertRaisesRegex(ValueError, "explicit"):
            build_explicit_groups(records, group_size=None, manifest=None)

    def test_manifest_grouping_maps_relative_paths(self):
        records = [_record(0), _record(1)]
        manifest = {
            "images": [
                {"relativePath": "frame-0.bmp", "sampleId": "s1", "position": "p1"},
                {"relativePath": "frame-1.bmp", "sampleId": "s1", "position": "p1"},
            ]
        }
        groups = build_explicit_groups(records, group_size=None, manifest=manifest)
        self.assertEqual("s1/p1", groups[0])
        self.assertEqual("s1/p1", groups[1])

    def test_cli_rejects_output_inside_git_worktree(self):
        with tempfile.TemporaryDirectory() as directory:
            input_path = Path(directory) / "results.jsonl"
            input_path.write_text(json.dumps(_record(0)) + "\n", encoding="utf-8")
            completed = subprocess.run(
                [
                    "uv", "run", "python", "tools/analyze_hole2_batch.py",
                    "--results-jsonl", str(input_path), "--group-size", "1",
                    "--output", "diagnostic-output-must-not-exist.json",
                ],
                capture_output=True,
                text=True,
            )
        self.assertNotEqual(0, completed.returncode)
        self.assertIn("outside the Git worktree", completed.stderr)
        self.assertFalse(Path("diagnostic-output-must-not-exist.json").exists())


if __name__ == "__main__":
    unittest.main()
