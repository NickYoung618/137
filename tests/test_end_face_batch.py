from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from tools.evaluate_end_face_batch import BatchInputError, load_validated_manifest, main, summarize_results
from tools.make_manifest import build_manifest


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_PATH = ROOT / "specs/004-quality-policy-batch/evidence/a2-local-user-summary.json"


def a2_evidence_results() -> list[dict]:
    evidence = json.loads(EVIDENCE_PATH.read_text(encoding="utf-8"))
    counts = evidence["invalidFeatureCounts"]
    results: list[dict] = []
    for index in range(evidence["imageCount"]):
        features = {}
        for feature, invalid_count in counts.items():
            valid = index >= invalid_count
            features[feature] = {
                "feature": feature,
                "canonicalFeature": feature,
                "classification": "feature_measurement",
                "coreValid": valid,
                "source": "evidence",
                "reason": None if valid else "user_reported_invalid",
                "fields": {"measurement_valid": 1.0 if valid else 0.0},
                "diagnostic": {"detectorPath": "evidence_only", "fixedConditions": {}, "observed": {}},
            }
        results.append({
            "schemaVersion": "a-end-face-result/2",
            "taskId": f"a2-evidence-{index + 1:02d}",
            "technicalStatus": "succeeded",
            "execution": {"elapsedMs": evidence["meanElapsedMs"]},
            "result": {
                "valid": True,
                "localization": {"valid": True},
                "measurementCompleteness": {
                    "allValid": all(item["coreValid"] for item in features.values()),
                },
                "featureQuality": features,
            },
            "error": None,
        })
    return results


class EndFaceBatchTests(unittest.TestCase):
    def test_a2_user_evidence_counts_are_reproducible_without_images(self) -> None:
        evidence = json.loads(EVIDENCE_PATH.read_text(encoding="utf-8"))
        results = a2_evidence_results()
        dataset = {"datasetId": "a2-local-user-evidence", "datasetFingerprint": None, "manifestSha256": None}
        summary = summarize_results(results, dataset)
        self.assertEqual(25, summary["technical"]["valid"])
        self.assertEqual(25, summary["localization"]["valid"])
        self.assertEqual(0, summary["measurementCompleteness"]["valid"])
        self.assertEqual(evidence["meanElapsedMs"], summary["timing"]["meanMs"])
        for feature, expected in evidence["invalidFeatureCounts"].items():
            self.assertEqual(expected, summary["features"][feature]["invalid"])
        self.assertEqual(summary, summarize_results(results, dataset))

    def test_manifest_hash_change_is_rejected_before_detection(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            image_path = root / "sample_1" / "pos_1" / "image_001.bmp"
            image_path.parent.mkdir(parents=True)
            Image.new("L", (8, 6), 20).save(image_path)
            manifest = build_manifest(root, "tamper-test", "a_end_face", 1, "sample_1", "pos_1")
            manifest_path = root / "manifest.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            Image.new("L", (8, 6), 21).save(image_path)
            with self.assertRaises(BatchInputError):
                load_validated_manifest(manifest_path, root)

    def test_manifest_task_must_be_a_end_face(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            image_path = root / "image.bmp"
            Image.new("L", (4, 4), 20).save(image_path)
            manifest = build_manifest(root, "wrong-task", "other", 1, "sample_1", "pos_1")
            manifest_path = root / "manifest.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaises(BatchInputError):
                load_validated_manifest(manifest_path, root)

    def test_batch_detect_writes_jsonl_and_recomputable_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            data_root = root / "data"
            image_path = data_root / "sample_1" / "pos_1" / "image_001.bmp"
            image_path.parent.mkdir(parents=True)
            Image.new("L", (8, 6), 20).save(image_path)
            manifest = build_manifest(data_root, "batch-test", "a_end_face", 1, "sample_1", "pos_1")
            manifest_path = root / "manifest.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            annotation = root / "annotation.json"
            annotation.write_text("{}", encoding="utf-8")
            output_dir = root / "output"

            payload = a2_evidence_results()[0]
            payload["taskId"] = manifest["images"][0]["imageId"]

            class FakeInspector:
                def __init__(self, *_args, **_kwargs):
                    pass

                def inspect(self, _image, task_id=None):
                    result = json.loads(json.dumps(payload))
                    result["taskId"] = task_id
                    return result

            with patch("tools.evaluate_end_face_batch.EndFaceInspector", FakeInspector):
                exit_code = main([
                    "detect",
                    "--manifest", str(manifest_path),
                    "--data-root", str(data_root),
                    "--annotation", str(annotation),
                    "--output-dir", str(output_dir),
                ])
            self.assertEqual(0, exit_code)
            results_path = output_dir / "results.jsonl"
            summary_path = output_dir / "quality-summary.json"
            self.assertTrue(results_path.is_file())
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            self.assertEqual(1, summary["technical"]["valid"])
            recomputed = root / "recomputed.json"
            self.assertEqual(0, main([
                "summarize", "--results-jsonl", str(results_path), "--output", str(recomputed)
            ]))
            recomputed_payload = json.loads(recomputed.read_text(encoding="utf-8"))
            self.assertEqual(summary["features"], recomputed_payload["features"])


if __name__ == "__main__":
    unittest.main()
