from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image

from tools.compare_short_line_candidates import (
    ComparisonInputError,
    main,
    preflight_comparison_inputs,
    summarize_comparisons,
    validate_single_development_group,
)
from tools.make_manifest import build_manifest


def comparison_record(task_id: str, transition_19: str, transition_30: str) -> dict:
    def feature(canonical: str, transition: str) -> dict:
        core_valid = transition in {"both_valid", "regressed"}
        candidate_valid = transition in {"both_valid", "recovered"}
        return {
            "feature": f"{canonical}��",
            "canonicalFeature": canonical,
            "candidateId": "reference-gradient-registration-v1",
            "algorithmVersion": "1.0.0",
            "configSha256": "2" * 64,
            "core": {"coreValid": core_valid, "source": "test", "reason": None, "target": None, "reference": None, "fields": {}},
            "candidate": {
                "candidateValid": candidate_valid,
                "source": "reference-gradient-registration-v1",
                "target": None,
                "reference": None,
                "deltaFromCore": None,
                "elapsedMs": 1.0,
            },
            "diagnostic": {
                "failedChecks": [] if candidate_valid else ["minimum_correlation"],
                "failureCategories": [] if candidate_valid else ["fit_instability"],
            },
            "transition": transition,
        }
    return {
        "schemaVersion": "a-end-face-short-line-comparison/1",
        "taskId": task_id,
        "technicalStatus": "compared",
        "input": {"relativePath": f"{task_id}.bmp", "sha256": "0" * 64, "width": 8, "height": 6},
        "provenance": {
            "coreSourceSha256": "1" * 64,
            "candidateConfigSha256": "2" * 64,
            "candidateReferenceMode": "desktop_core",
            "candidateReferenceAnnotationSha256": None,
            "candidateReferenceImageSha256": None,
        },
        "baselineSchemaVersion": "a-end-face-result/2",
        "coreFeatureStatus": {
            "19": {"coreValid": transition_19 in {"both_valid", "regressed"}, "source": "test", "reason": None},
            "30": {"coreValid": transition_30 in {"both_valid", "regressed"}, "source": "test", "reason": None},
            "46": {"coreValid": False, "source": "test", "reason": "d46_radial_low_score"},
            "M78": {"coreValid": True, "source": "test", "reason": None},
            "80": {"coreValid": True, "source": "test", "reason": None},
            "86": {"coreValid": True, "source": "test", "reason": None},
        },
        "features": {"19��": feature("19", transition_19), "30��": feature("30", transition_30)},
        "error": None,
    }


class ShortLineComparisonTests(unittest.TestCase):
    def test_development_scope_requires_one_explicit_complete_twenty_frame_group(self) -> None:
        manifest = {
            "images": [
                {
                    "sampleId": "sample-dev",
                    "position": "a2",
                    "split": "development",
                    "repeatIndex": index,
                }
                for index in range(1, 21)
            ]
        }
        self.assertEqual(
            {"sampleId": "sample-dev", "position": "a2", "imageCount": 20},
            validate_single_development_group(manifest),
        )
        for mutate in (
            lambda value: value["images"].pop(),
            lambda value: value["images"][0].update(split="validation"),
            lambda value: value["images"][0].update(sampleId="another-sample"),
        ):
            invalid = json.loads(json.dumps(manifest))
            mutate(invalid)
            with self.assertRaises(ComparisonInputError):
                validate_single_development_group(invalid)

    def test_preflight_requires_exact_unique_manifest_task_mapping(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            data_root = root / "data"
            image = data_root / "sample_1" / "pos_1" / "image_001.bmp"
            image.parent.mkdir(parents=True)
            Image.new("L", (8, 6), 20).save(image)
            manifest = build_manifest(data_root, "compare-test", "a_end_face", 1, "sample_1", "pos_1")
            manifest_path = root / "manifest.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            results_path = root / "results.jsonl"
            results_path.write_text(json.dumps({
                "schemaVersion": "a-end-face-result/2",
                "taskId": "wrong-task",
                "technicalStatus": "failed",
                "result": None,
                "error": {"code": "DETECTION_FAILED", "message": "test"},
            }) + "\n", encoding="utf-8")
            with self.assertRaises(ComparisonInputError):
                preflight_comparison_inputs(manifest_path, data_root, results_path)

    def test_summary_preserves_transitions_priority_features_and_is_deterministic(self) -> None:
        records = [
            comparison_record("a", "recovered", "both_invalid"),
            comparison_record("b", "both_invalid", "regressed"),
        ]
        summary = summarize_comparisons(records, {"datasetId": "synthetic"})
        self.assertEqual(1, summary["candidateFeatures"]["19"]["transitions"]["recovered"])
        self.assertEqual(1, summary["candidateFeatures"]["30"]["transitions"]["regressed"])
        self.assertEqual(2, summary["priorityCoreFeatures"]["46"]["invalid"])
        self.assertFalse(summary["acceptance"]["noRegression"])
        self.assertTrue(summary["acceptance"]["hasEvidenceBackedRecovery"])
        self.assertEqual(summary, summarize_comparisons(records, {"datasetId": "synthetic"}))

    def test_compare_cli_writes_per_image_jsonl_and_resummarizes_without_images(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            data_root = root / "data"
            image = data_root / "sample_1" / "pos_1" / "image_001.bmp"
            image.parent.mkdir(parents=True)
            Image.new("L", (8, 6), 20).save(image)
            manifest = build_manifest(data_root, "compare-e2e", "a_end_face", 1, "sample_1", "pos_1")
            task_id = manifest["images"][0]["imageId"]
            manifest_path = root / "manifest.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            baseline = comparison_record(task_id, "recovered", "both_invalid")
            results_path = root / "results.jsonl"
            results_path.write_text(json.dumps({
                "schemaVersion": "a-end-face-result/2",
                "taskId": task_id,
                "technicalStatus": "succeeded",
                "result": {
                    "featureQuality": {
                        value["feature"]: {
                            "feature": value["feature"],
                            "canonicalFeature": value["canonicalFeature"],
                            "coreValid": value["core"]["coreValid"],
                            "source": value["core"]["source"],
                            "reason": value["core"]["reason"],
                            "fields": {},
                        }
                        for value in baseline["features"].values()
                    },
                    "measurements": {},
                },
                "error": None,
            }) + "\n", encoding="utf-8")
            annotation = root / "annotation.json"
            reference = root / "reference.bmp"
            annotation.write_text("{}", encoding="utf-8")
            Image.new("L", (8, 6), 20).save(reference)
            output_dir = root / "output"

            class FakeEvaluator:
                def __init__(self, *_args, **_kwargs):
                    self.provenance = {
                        "candidateId": "reference-gradient-registration-v1",
                        "algorithmVersion": "1.0.0",
                        "configSha256": "2" * 64,
                        "referenceMode": "desktop_core",
                        "referenceSchemaVersion": None,
                        "referenceAnnotationSha256": None,
                        "referenceImageSha256": None,
                    }

                def evaluate_image(self, *_args, **_kwargs):
                    return baseline["features"]

            with patch(
                "tools.compare_short_line_candidates.core.build_reference_model",
                return_value=SimpleNamespace(reference_path=reference),
            ), patch(
                "tools.compare_short_line_candidates.ShortLineCandidateEvaluator",
                FakeEvaluator,
            ):
                exit_code = main([
                    "compare",
                    "--manifest", str(manifest_path),
                    "--data-root", str(data_root),
                    "--annotation", str(annotation),
                    "--results-jsonl", str(results_path),
                    "--output-dir", str(output_dir),
                ])
            self.assertEqual(0, exit_code)
            comparison_path = output_dir / "short-line-comparison.jsonl"
            summary_path = output_dir / "short-line-summary.json"
            self.assertTrue(comparison_path.is_file())
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            self.assertEqual(1, summary["acceptance"]["recoveredCount"])
            resummary = root / "resummary.json"
            self.assertEqual(0, main([
                "summarize",
                "--comparison-jsonl", str(comparison_path),
                "--output", str(resummary),
            ]))
            rebuilt = json.loads(resummary.read_text(encoding="utf-8"))
            self.assertEqual(summary["candidateFeatures"], rebuilt["candidateFeatures"])
            self.assertEqual(summary["priorityCoreFeatures"], rebuilt["priorityCoreFeatures"])


if __name__ == "__main__":
    unittest.main()
