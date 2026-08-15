import csv
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from PIL import Image


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TOOL = PROJECT_ROOT / "tools" / "render_hole2_batch_report.py"


def _feature(name, valid, failure=None):
    if name == "7":
        target = {
            "coordinateSystem": "target_px",
            "pointsPx": [[40.0, 50.0], [140.0, 50.0]],
            "lengthPx": 100.0,
            "rawEdgeEvidence": {
                "semantics": "neck_outer_contour_edges",
                "boundaries": [
                    {"side": "A", "pointsPx": [[40.0, 35.0], [40.0, 65.0]]},
                    {"side": "B", "pointsPx": [[140.0, 35.0], [140.0, 65.0]]},
                ],
            },
            "fittedGeometry": {
                "type": "parallel_lines",
                "boundaries": [
                    {"side": "A", "segmentPointsPx": [[40.0, 35.0], [40.0, 65.0]]},
                    {"side": "B", "segmentPointsPx": [[140.0, 35.0], [140.0, 65.0]]},
                ],
            },
            "measurementAnnotation": {
                "type": "perpendicular_distance",
                "pointsPx": [[40.0, 50.0], [140.0, 50.0]],
                "valuePx": 100.0,
            },
        }
    else:
        target = {
            "coordinateSystem": "target_px",
            "centerPx": [220.0, 100.0],
            "radiusPx": 35.0,
            "diameterPx": 70.0,
            "rawEdgeEvidence": {
                "semantics": "outer_contour_two_visible_arcs",
                "arcSegments": [
                    {"side": "reference_left", "pointsPx": [[190.0, 82.0], [185.0, 100.0], [190.0, 118.0]]},
                    {"side": "reference_right", "pointsPx": [[250.0, 82.0], [255.0, 100.0], [250.0, 118.0]]},
                ],
            },
            "fittedGeometry": {
                "type": "circle_model",
                "centerPx": [220.0, 100.0],
                "radiusPx": 35.0,
                "isDetectedContour": False,
            },
            "measurementAnnotation": {"type": "diameter", "valuePx": 70.0},
        }
    return {
        "measurementValid": valid,
        "failureReason": failure,
        "sourceDetector": "test-detector",
        "recoveryPass": None,
        "target": target if valid else None,
    }


def _record(image, group, *, registration=True, d7=True, phi=True):
    return {
        "group": group,
        "imagePath": str(image),
        "executionError": None,
        "result": {
            "algorithmVersion": "hole2-test/1",
            "registration": {
                "registrationValid": registration,
                "failureReason": None if registration else "no_valid_candidate",
            },
            "features": {
                "7": _feature(
                    "7", d7,
                    None if d7 else (
                        "tangent_boundary_fit_failed" if registration
                        else "registration_invalid:no_valid_candidate"
                    ),
                ),
                "Phi12.2": _feature(
                    "Phi12.2", phi,
                    None if phi else (
                        "edge_peak_below_gate" if registration
                        else "registration_invalid:no_valid_candidate"
                    ),
                ),
            },
        },
    }


class Hole2BatchReportTests(unittest.TestCase):
    def _fixture(self, root):
        image_root = root / "images"
        records = []
        normal = image_root / "normal"
        defective = image_root / "defective"
        normal.mkdir(parents=True)
        defective.mkdir(parents=True)
        normal_names = [
            "Pic_2026_08_12_220000_1.bmp",
            "Pic_2026_08_12_220000_2.bmp",
            "Pic_2026_08_12_220000_3.bmp",
            "Pic_2026_08_12_220000_5.bmp",
        ]
        defective_names = [
            "Pic_2026_08_12_230000_101.bmp",
            "Pic_2026_08_12_230000_102.bmp",
            "Pic_2026_08_12_230000_103.bmp",
        ]
        for index, name in enumerate(normal_names + defective_names):
            directory = normal if index < len(normal_names) else defective
            Image.new("RGB", (300, 200), (40 + index, 45, 50)).save(directory / name)
        records.extend([
            _record(normal / normal_names[0], "normal"),
            _record(normal / normal_names[1], "normal", d7=False),
            _record(normal / normal_names[2], "normal", registration=False, d7=False, phi=False),
            {
                "group": "normal",
                "imagePath": str(normal / normal_names[3]),
                "executionError": "RuntimeError:synthetic failure",
                "result": None,
            },
        ])
        records.extend(_record(defective / name, "defective") for name in defective_names)
        jsonl = root / "current-capture-results.jsonl"
        jsonl.write_text(
            "".join(json.dumps(record) + "\n" for record in records),
            encoding="utf-8",
        )
        return jsonl, image_root

    def _run(self, jsonl, image_root, output_dir, *extra):
        return subprocess.run(
            [
                "uv", "run", "python", str(TOOL),
                "--jsonl", str(jsonl),
                "--image-root", str(image_root),
                "--output-dir", str(output_dir),
                "--images-per-product", "3",
                "--max-preview-width", "150",
                *extra,
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
        )

    def test_default_generates_every_record_with_scaled_preview_and_original_labelme(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            jsonl, image_root = self._fixture(root)
            output = root / "report"
            completed = self._run(jsonl, image_root, output)
            self.assertEqual(0, completed.returncode, completed.stderr)
            summary = json.loads((output / "summary.json").read_text())
            self.assertEqual(7, summary["selection"]["generatedRecords"])
            with (output / "index.csv").open(encoding="utf-8-sig") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(7, len(rows))
            valid = next(row for row in rows if row["imageName"].endswith("_1.bmp"))
            preview_path = output / valid["previewJpeg"]
            labelme_path = output / valid["predictionLabelmeJson"]
            with Image.open(preview_path) as preview:
                self.assertEqual((150, 100), preview.size)
                self.assertEqual("JPEG", preview.format)
            labelme = json.loads(labelme_path.read_text())
            self.assertEqual(300, labelme["imageWidth"])
            self.assertEqual(200, labelme["imageHeight"])
            shapes = {shape["label"]: shape for shape in labelme["shapes"]}
            self.assertEqual({
                "prediction:7:boundary:A", "prediction:7:boundary:B",
                "prediction:7:dimension",
                "prediction:Phi12.2:arc:reference_left:0",
                "prediction:Phi12.2:arc:reference_right:0",
            }, set(shapes))
            self.assertEqual(
                [[40.0, 50.0], [140.0, 50.0]],
                shapes["prediction:7:dimension"]["points"],
            )
            self.assertEqual("linestrip", shapes["prediction:Phi12.2:arc:reference_left:0"]["shape_type"])
            self.assertNotIn("circle", {shape["shape_type"] for shape in shapes.values()})
            self.assertFalse(labelme["predictionMetadata"]["isGroundTruth"])
            self.assertFalse(labelme["predictionMetadata"]["isCompletePartContour"])

            failed = next(row for row in rows if row["imageName"].endswith("_5.bmp"))
            with Image.open(output / failed["previewJpeg"]).convert("RGB") as preview:
                red, green, blue = preview.getpixel((1, preview.height - 2))
            self.assertGreater(red, 140)
            self.assertLess(green, 120)
            self.assertLess(blue, 120)

    def test_only_invalid_and_explicit_frames_control_generated_assets(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            jsonl, image_root = self._fixture(root)
            invalid_output = root / "invalid"
            completed = self._run(jsonl, image_root, invalid_output, "--only-invalid")
            self.assertEqual(0, completed.returncode, completed.stderr)
            invalid_summary = json.loads((invalid_output / "summary.json").read_text())
            self.assertEqual(3, invalid_summary["selection"]["generatedRecords"])
            self.assertEqual("only_invalid", invalid_summary["selection"]["mode"])

            frame_output = root / "frames"
            completed = self._run(
                jsonl, image_root, frame_output,
                "--frame", "Pic_2026_08_12_220000_1",
                "--frame", "defective/Pic_2026_08_12_230000_102.bmp",
            )
            self.assertEqual(0, completed.returncode, completed.stderr)
            frame_summary = json.loads((frame_output / "summary.json").read_text())
            self.assertEqual(2, frame_summary["selection"]["generatedRecords"])
            self.assertEqual("explicit_frames", frame_summary["selection"]["mode"])

    def test_group_counts_failure_reasons_and_capture_estimates_are_separate(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            jsonl, image_root = self._fixture(root)
            output = root / "report"
            completed = self._run(jsonl, image_root, output)
            self.assertEqual(0, completed.returncode, completed.stderr)
            summary = json.loads((output / "summary.json").read_text())
            self.assertNotIn("overall", summary)
            normal = summary["groups"]["normal"]
            defective = summary["groups"]["defective"]
            self.assertEqual({"normal", "defective"}, set(summary["groups"]))
            self.assertEqual(4, normal["total"])
            self.assertEqual(3, normal["executionSuccess"])
            self.assertEqual(1, normal["executionError"])
            self.assertEqual(2, normal["registrationValid"])
            self.assertEqual(2, normal["registrationInvalid"])
            self.assertEqual(1, normal["featureValid"]["7"])
            self.assertEqual(3, normal["featureInvalid"]["7"])
            self.assertEqual(2, normal["featureValid"]["Phi12.2"])
            self.assertEqual(1, normal["bothMeasurementsValid"])
            self.assertEqual(1, normal["failureReasons"]["executionError"]["RuntimeError"])
            self.assertEqual(3, defective["total"])
            self.assertEqual(3, defective["bothMeasurementsValid"])
            self.assertEqual(4, normal["generatedPreviewCount"])
            self.assertEqual(3, defective["generatedPreviewCount"])

            estimate = summary["captureGroupEstimate"]
            self.assertFalse(estimate["confirmedPhysicalProductCount"])
            self.assertIn("not confirmed physical product counts", estimate["disclaimer"])
            normal_groups = estimate["groups"]["normal"]["estimatedGroups"]
            self.assertTrue(normal_groups[0]["complete"])
            self.assertFalse(normal_groups[1]["complete"])
            self.assertEqual([4, 6], normal_groups[1]["gaps"])
            defective_groups = estimate["groups"]["defective"]["estimatedGroups"]
            self.assertTrue(defective_groups[0]["complete"])
            summary_text = (output / "summary.txt").read_text(encoding="utf-8")
            self.assertIn("group=normal estimatedCaptureGroupCount=2", summary_text)
            self.assertIn("complete=1 incomplete=1", summary_text)
            self.assertIn("gaps=4,6", summary_text)

    def test_output_inside_worktree_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            jsonl, image_root = self._fixture(root)
            output = PROJECT_ROOT / "batch-report-must-not-exist"
            completed = self._run(jsonl, image_root, output)
            self.assertNotEqual(0, completed.returncode)
            self.assertIn("outside the Git worktree", completed.stderr)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
