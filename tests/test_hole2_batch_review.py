import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from PIL import Image


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TOOL = PROJECT_ROOT / "tools" / "render_hole2_batch_changes.py"


def _feature(name, *, valid, failure=None, shift=0.0):
    if name == "7":
        target = {
            "coordinateSystem": "target_px",
            "pointsPx": [[20.0 + shift, 30.0], [80.0 + shift, 30.0]],
            "lengthPx": 60.0,
            "rawEdgeEvidence": {
                "semantics": "neck_outer_contour_edges",
                "boundaries": [
                    {"side": "A", "pointsPx": [[20.0 + shift, 15.0], [20.0 + shift, 45.0]]},
                    {"side": "B", "pointsPx": [[80.0 + shift, 15.0], [80.0 + shift, 45.0]]},
                ],
            },
            "fittedGeometry": {
                "type": "parallel_lines",
                "boundaries": [
                    {"side": "A", "segmentPointsPx": [[20.0 + shift, 15.0], [20.0 + shift, 45.0]]},
                    {"side": "B", "segmentPointsPx": [[80.0 + shift, 15.0], [80.0 + shift, 45.0]]},
                ],
            },
            "measurementAnnotation": {
                "type": "perpendicular_distance",
                "pointsPx": [[20.0 + shift, 30.0], [80.0 + shift, 30.0]],
                "valuePx": 60.0,
            },
        }
        quality = {
            "d7.quality.candidate_p1_edge_points": 31.0,
            "d7.quality.candidate_p2_edge_points": 30.0,
            "d7.quality.candidate_p1_fit_residual_target_px": 0.25,
            "d7.quality.candidate_p2_fit_residual_target_px": 0.30,
            "d7.quality.candidate_failed_sides": [],
        }
    else:
        target = {
            "coordinateSystem": "target_px",
            "centerPx": [120.0 + shift, 80.0],
            "radiusPx": 30.0,
            "diameterPx": 60.0,
            "rawEdgeEvidence": {
                "semantics": "outer_contour_two_visible_arcs",
                "arcSegments": [
                    {"side": "reference_left", "pointsPx": [[92.0 + shift, 70.0], [90.0 + shift, 80.0], [92.0 + shift, 90.0]]},
                    {"side": "reference_right", "pointsPx": [[148.0 + shift, 70.0], [150.0 + shift, 80.0], [148.0 + shift, 90.0]]},
                ],
            },
            "fittedGeometry": {
                "type": "circle_model", "centerPx": [120.0 + shift, 80.0],
                "radiusPx": 30.0, "isDetectedContour": False,
            },
            "measurementAnnotation": {"type": "diameter", "valuePx": 60.0},
        }
        quality = {
            "candidate_edge_semantics": "reference_phase_outer_polarity_edge",
            "candidate_phase_fit_residual_target_px": 0.6,
            "candidate_phase_edge_points": 196,
            "candidate_phase_polarity_support_fraction": 1.0,
            "candidate_phase_angle_coverage_fraction": 0.98,
        }
    return {
        "measurementValid": valid,
        "qualityStatus": "valid" if valid else "invalid",
        "failureReason": failure,
        "sourceDetector": "synthetic-detector",
        "recoveryPass": None,
        "target": target if valid else None,
        "quality": quality,
    }


def _record(image, *, version, d7=True, phi=True, d7_failure=None, phi_failure=None):
    return {
        "group": "normal",
        "imagePath": str(image),
        "executionError": None,
        "result": {
            "algorithmVersion": version,
            "registration": {"registrationValid": True, "failureReason": None},
            "features": {
                "7": _feature("7", valid=d7, failure=d7_failure),
                "Phi12.2": _feature("Phi12.2", valid=phi, failure=phi_failure),
            },
        },
    }


class Hole2BatchReviewTests(unittest.TestCase):
    def _fixture(self, root):
        image_root = root / "images"
        image_root.mkdir()
        changed = image_root / "changed.bmp"
        unchanged = image_root / "unchanged.bmp"
        Image.new("RGB", (180, 140), (35, 35, 35)).save(changed)
        Image.new("RGB", (180, 140), (45, 45, 45)).save(unchanged)
        old_path = root / "old.jsonl"
        new_path = root / "new.jsonl"
        old_records = [
            _record(changed, version="old/1"),
            _record(unchanged, version="old/1"),
        ]
        new_records = [
            _record(
                changed,
                version="new/2",
                d7=False,
                d7_failure="upstream_phi12_2_candidate_invalid",
            ),
            _record(unchanged, version="new/2"),
        ]
        old_path.write_text(
            "".join(json.dumps(item) + "\n" for item in old_records),
            encoding="utf-8",
        )
        new_path.write_text(
            "".join(json.dumps(item) + "\n" for item in new_records),
            encoding="utf-8",
        )
        return image_root, old_path, new_path

    def _run(self, old_path, new_path, image_root, output_dir, *extra):
        return subprocess.run(
            [
                "uv", "run", "python", str(TOOL),
                "--old-jsonl", str(old_path),
                "--new-jsonl", str(new_path),
                "--image-root", str(image_root),
                "--output-dir", str(output_dir),
                *extra,
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
        )

    def test_default_renders_only_status_changes_with_labelme_predictions(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            image_root, old_path, new_path = self._fixture(root)
            output_dir = root / "review"
            completed = self._run(old_path, new_path, image_root, output_dir)
            self.assertEqual(0, completed.returncode, completed.stderr)
            summary = json.loads((output_dir / "review-summary.json").read_text())
            self.assertEqual(2, summary["matchedFrames"])
            self.assertEqual(1, summary["renderedFrames"])
            self.assertEqual("status_changes", summary["selectionMode"])
            item = summary["items"][0]
            self.assertTrue((output_dir / item["overlayPng"]).is_file())
            labelme = json.loads(
                (output_dir / item["predictionLabelmeJson"]).read_text()
            )
            labels = {shape["label"] for shape in labelme["shapes"]}
            self.assertIn("old:7:boundary:A", labels)
            self.assertIn("old:7:boundary:B", labels)
            self.assertIn("old:7:dimension", labels)
            self.assertIn("old:Phi12.2:arc:reference_left:0", labels)
            self.assertNotIn("new:Phi12.2:arc:reference_right:0", labels)
            self.assertNotIn("circle", {
                shape["shape_type"] for shape in labelme["shapes"]
            })
            metadata = labelme["reviewMetadata"]
            self.assertEqual("old/1", metadata["old"]["algorithmVersion"])
            self.assertFalse(metadata["new"]["features"]["7"]["measurementValid"])
            self.assertIn(
                "candidate_phase_fit_residual_target_px",
                metadata["new"]["features"]["Phi12.2"]["quality"],
            )
            self.assertEqual(
                "complete",
                metadata["new"]["features"]["Phi12.2"]["evidenceAuditStatus"],
            )
            self.assertEqual(
                "Only dimension 7 and Phi12.2 predictions are drawn; this is not a part contour annotation.",
                metadata["scope"],
            )

    def test_evidence_only_change_is_reviewable_without_fabricated_arc(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            image_root, old_path, new_path = self._fixture(root)
            records = [json.loads(line) for line in new_path.read_text().splitlines()]
            records[1]["result"]["features"]["Phi12.2"]["target"]["rawEdgeEvidence"]["arcSegments"] = []
            new_path.write_text(
                "".join(json.dumps(record) + "\n" for record in records),
                encoding="utf-8",
            )
            output_dir = root / "review"
            completed = self._run(old_path, new_path, image_root, output_dir)
            self.assertEqual(0, completed.returncode, completed.stderr)
            summary = json.loads((output_dir / "review-summary.json").read_text())
            self.assertEqual(2, summary["renderedFrames"])
            item = next(item for item in summary["items"] if item["imageName"] == "unchanged.bmp")
            labelme = json.loads((output_dir / item["predictionLabelmeJson"]).read_text())
            self.assertEqual(
                "unavailable",
                labelme["reviewMetadata"]["new"]["features"]["Phi12.2"]["evidenceAuditStatus"],
            )
            self.assertFalse(any(
                shape["label"].startswith("new:Phi12.2")
                for shape in labelme["shapes"]
            ))

    def test_explicit_frame_can_render_unchanged_status(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            image_root, old_path, new_path = self._fixture(root)
            output_dir = root / "review"
            completed = self._run(
                old_path, new_path, image_root, output_dir,
                "--frame", "unchanged",
            )
            self.assertEqual(0, completed.returncode, completed.stderr)
            summary = json.loads((output_dir / "review-summary.json").read_text())
            self.assertEqual("explicit_frames", summary["selectionMode"])
            self.assertEqual(["unchanged.bmp"], [item["imageName"] for item in summary["items"]])

    def test_output_inside_worktree_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            image_root, old_path, new_path = self._fixture(root)
            output_dir = PROJECT_ROOT / "review-output-must-not-exist"
            completed = self._run(old_path, new_path, image_root, output_dir)
            self.assertNotEqual(0, completed.returncode)
            self.assertIn("outside the Git worktree", completed.stderr)
            self.assertFalse(output_dir.exists())


if __name__ == "__main__":
    unittest.main()
