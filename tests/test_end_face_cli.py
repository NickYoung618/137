from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image

from algorithms.end_face import CORE_SOURCE_SHA256, core
from algorithms.end_face.main import main, run


ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "algorithms/end_face/core.py"


class EndFaceCliTests(unittest.TestCase):
    def test_desktop_core_source_is_preserved(self) -> None:
        digest = hashlib.sha256(CORE.read_bytes()).hexdigest()
        self.assertEqual(CORE_SOURCE_SHA256, digest)
        for name in ("build_reference_model", "detect_measurements", "estimate_global_transform"):
            self.assertTrue(callable(getattr(core, name, None)), name)

    def test_run_wraps_existing_core_measurements(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            image = root / "target.bmp"
            annotation = root / "annotation.json"
            reference = root / "reference.bmp"
            Image.new("L", (20, 16), 127).save(image)
            reference.write_bytes(b"reference")
            annotation.write_text(json.dumps({"imagePath": reference.name}), encoding="utf-8")
            model = SimpleNamespace(reference_path=reference, shapes=[])
            measurements = {
                "transform.target_center_x_px": 10.0,
                "transform.target_center_y_px": 8.0,
                "transform.scale": 1.0,
                "transform.rotation_deg": 0.0,
                "Phi100.radius_ref_px": 10.0,
            }
            with patch("algorithms.end_face.adapter.core.build_reference_model", return_value=model), patch(
                "algorithms.end_face.adapter.core.detect_measurements",
                return_value=(measurements, "circle-alignment rotation_score=10.0, notch_check(Δ=0deg, prom=20.0)"),
            ):
                payload = run(image, annotation, task_id="cli-test")
        self.assertEqual("succeeded", payload["technicalStatus"])
        self.assertTrue(payload["result"]["valid"])
        self.assertEqual("a-end-face-result/3", payload["schemaVersion"])
        self.assertIn("circle-alignment", payload["result"]["shiftMethod"])
        self.assertEqual(measurements, payload["result"]["measurements"])
        self.assertEqual({}, payload["result"]["shortLineCandidates"])
        self.assertEqual(
            "reference-gradient-registration-v1",
            payload["algorithm"]["shortLineCandidate"]["candidateId"],
        )

    def test_invalid_candidate_config_returns_structured_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            image = root / "target.bmp"
            annotation = root / "annotation.json"
            reference = root / "reference.bmp"
            candidate_config = root / "candidate.json"
            Image.new("L", (20, 16), 127).save(image)
            reference.write_bytes(b"reference")
            annotation.write_text(json.dumps({"imagePath": reference.name}), encoding="utf-8")
            candidate_config.write_text(json.dumps({"schemaVersion": "unsupported"}), encoding="utf-8")
            with patch(
                "algorithms.end_face.adapter.core.build_reference_model",
                return_value=SimpleNamespace(reference_path=reference, shapes=[]),
            ):
                payload = run(
                    image,
                    annotation,
                    task_id="invalid-candidate-config",
                    short_line_candidate_config=candidate_config,
                )
        self.assertEqual("failed", payload["technicalStatus"])
        self.assertIsNone(payload["result"])
        self.assertEqual("DETECTION_FAILED", payload["error"]["code"])
        self.assertIn("candidate config", payload["error"]["message"])

    def test_missing_input_returns_structured_failure(self) -> None:
        payload = run(Path("missing-target.bmp"), Path("missing-annotation.json"), task_id="missing-input")
        self.assertEqual("failed", payload["technicalStatus"])
        self.assertIsNone(payload["result"])
        self.assertEqual("DETECTION_FAILED", payload["error"]["code"])

    def test_cli_writes_json_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            image = root / "target.bmp"
            annotation = root / "annotation.json"
            output = root / "nested/result.json"
            image.write_bytes(b"target")
            annotation.write_text("{}", encoding="utf-8")
            with patch("algorithms.end_face.main.run", return_value={
                "schemaVersion": "a-end-face-result/3",
                "technicalStatus": "succeeded",
                "result": {"valid": True},
            }):
                exit_code = main([
                    "--image", str(image), "--annotation", str(annotation), "--output", str(output), "--strict"
                ])
            self.assertEqual(0, exit_code)
            self.assertEqual("a-end-face-result/3", json.loads(output.read_text(encoding="utf-8"))["schemaVersion"])

    def test_script_help_is_independent(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(ROOT / "algorithms/end_face/main.py"), "--help"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(0, completed.returncode, completed.stderr)
        self.assertIn("--annotation", completed.stdout)
        self.assertIn("--image", completed.stdout)
        self.assertIn("--quality-policy", completed.stdout)
        self.assertIn("--short-line-candidate-config", completed.stdout)


if __name__ == "__main__":
    unittest.main()
