from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.audit_a2_robustness_groups import audit_results, build_annotation_queue
from tools.plan_a2_robustness_folds import (
    SealedLeakageError, build_fold_plan, materialize_fold_manifests,
)


def sha(index: int) -> str:
    return f"{index:064x}"


def sample_rows(sample_id: str, start: int, count: int = 3, split: str = "unassigned") -> list[dict]:
    return [{
        "relative_path": f"A2/{sample_id.replace(':', '-')}/{index:03d}.bmp",
        "source_image_sha256": sha(start + index),
        "sample_id": sample_id,
        "condition_id": "fixed",
        "repeat_index": str(index),
        "split": split,
        "dataset_class": "normal",
        "grouping_authority": "capture-owner",
        "grouping_provenance": "confirmed-record",
    } for index in range(1, count + 1)]


def cause(sample_id: str, family: str = "circle") -> dict:
    return {
        "sample_id": sample_id,
        "failure_family": family,
        "selection_authority": "readonly-diagnosis",
        "selection_provenance": "historical-700-replay",
    }


def seal(sample_id: str = "normal:part-006", digests: list[str] | None = None) -> dict:
    return {
        "selectedSampleId": sample_id,
        "selectedImageSha256s": digests or [sha(6001)],
        "lockPayloadSha256": sha(9999),
    }


class RobustnessFoldTests(unittest.TestCase):
    def test_whole_sample_two_and_three_fold_plans_have_no_leakage(self) -> None:
        indices = (1, 2, 3, 4, 5, 7)
        rows = sum((sample_rows(f"normal:part-{index:03d}", index * 100) for index in indices), [])
        causes = [cause(f"normal:part-{index:03d}", "circle" if index < 4 else "groove") for index in indices]
        for count in (2, 3):
            with self.subTest(folds=count):
                plan = build_fold_plan(rows, causes, seal(), fold_count=count)
                self.assertEqual("READY", plan["planStatus"])
                self.assertEqual(count, len(plan["folds"]))
                for fold in plan["folds"]:
                    development = set(fold["developmentSampleIds"])
                    validation = set(fold["validationSampleIds"])
                    self.assertFalse(development & validation)
                    self.assertEqual(0, fold["sampleIntersectionCount"])
                    self.assertEqual(0, fold["sha256IntersectionCount"])
                    for sample_id in development | validation:
                        purposes = {
                            "validation" if sample_id in validation else "development"
                            for row in rows if row["sample_id"] == sample_id
                        }
                        self.assertEqual(1, len(purposes))

    def test_single_sample_is_insufficient_and_cross_purpose_is_rejected(self) -> None:
        rows = sample_rows("normal:part-001", 100)
        plan = build_fold_plan(rows, [cause("normal:part-001")], seal(), fold_count=2)
        self.assertEqual("INSUFFICIENT_PARTS", plan["planStatus"])
        rows[-1]["split"] = "validation"
        rows[0]["split"] = "development"
        with self.assertRaisesRegex(ValueError, "sample.*purpose"):
            build_fold_plan(rows, [cause("normal:part-001")], seal(), fold_count=2)

    def test_sealed_sample_or_sha_is_rejected_before_any_results_are_needed(self) -> None:
        rows = sample_rows("normal:part-006", 6000)
        with self.assertRaises(SealedLeakageError):
            build_fold_plan(rows, [cause("normal:part-006")], seal(digests=[rows[0]["source_image_sha256"]]))
        renamed = sample_rows("normal:renamed", 7000)
        lock = seal(digests=[renamed[1]["source_image_sha256"]])
        with self.assertRaises(SealedLeakageError):
            build_fold_plan(renamed, [cause("normal:renamed")], lock)
        with self.assertRaisesRegex(ValueError, "seal lock"):
            build_fold_plan(renamed, [cause("normal:renamed")], {})

    def test_materialized_run_manifests_preserve_whole_sample_folds(self) -> None:
        rows = sample_rows("normal:part-008", 800) + sample_rows("normal:part-009", 900)
        plan = build_fold_plan(rows, [cause("normal:part-008"), cause("normal:part-009")], seal(), fold_count=2)
        source = {
            "schemaVersion": "inspection-dataset-manifest/1", "datasetId": "a2", "images": [
                {
                    "imageId": row["relative_path"], "relativePath": row["relative_path"],
                    "sampleId": row["sample_id"], "sha256": row["source_image_sha256"],
                    "sourceImageSha256": row["source_image_sha256"], "split": "unassigned",
                    "bytes": 1, "format": "BMP", "width": 1, "height": 1, "mode": "L",
                } for row in rows
            ],
        }
        subsets = materialize_fold_manifests(plan, source)
        for fold_id, pair in subsets.items():
            development = {item["sampleId"] for item in pair["development"]["images"]}
            validation = {item["sampleId"] for item in pair["validation"]["images"]}
            self.assertFalse(development & validation, fold_id)
            self.assertTrue(all(item["split"] == "development" for item in pair["development"]["images"]))
            self.assertTrue(all(item["split"] == "validation" for item in pair["validation"]["images"]))


class RobustnessAuditTests(unittest.TestCase):
    def test_stream_audit_parses_only_target_nonsealed_sha_and_builds_funnel(self) -> None:
        rows = sample_rows("normal:part-008", 800) + sample_rows("normal:part-009", 900)
        causes = [cause("normal:part-008", "circle"), cause("normal:part-009", "circle")]
        plan = build_fold_plan(rows, causes, seal(), fold_count=2)
        target = rows[0]["source_image_sha256"]
        sealed_sha = sha(6001)
        unrelated = sha(7001)
        records = [
            {"image": {"sha256": target}, "result": {"valid": False},
             "error": {"code": "HOUSING_CIRCLE_NOT_FOUND", "stage": "circle_localization"},
             "diagnostics": {"circleLocalization": {"status": "not_found", "failedChecks": ["no_sparse_physical_candidate"]}}},
            {"image": {"sha256": sealed_sha}, "result": {"valid": True}, "diagnostics": {"secret": "must-not-parse"}},
            {"image": {"sha256": unrelated}, "result": {"valid": True}, "diagnostics": {}},
        ]
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "results.jsonl"
            path.write_text("\n".join(json.dumps(item) for item in records) + "\n", encoding="utf-8")
            audit = audit_results(path, plan, rows, seal())
        self.assertEqual(3, audit["linesScanned"])
        self.assertEqual(1, audit["targetRecordsParsed"])
        self.assertEqual(0, audit["sealedRecordsParsed"])
        self.assertFalse(audit["accuracyEvaluated"])
        self.assertLess(audit["elapsedMs"], 5000.0)
        group = next(item for item in audit["groups"] if item["sampleId"] == "normal:part-008")
        self.assertEqual(1, group["errorCodeCounts"]["HOUSING_CIRCLE_NOT_FOUND"])
        self.assertEqual(1, group["stageFunnel"]["circleLocalizationFailed"])

    def test_annotation_queue_is_identity_stable_and_contains_no_algorithm_truth(self) -> None:
        rows = sample_rows("normal:part-008", 800, count=5) + sample_rows("normal:part-009", 900, count=5)
        causes = [cause("normal:part-008", "circle"), cause("normal:part-009", "groove")]
        first = build_annotation_queue(rows, causes, per_sample=2)
        second = build_annotation_queue(list(reversed(rows)), list(reversed(causes)), per_sample=2)
        self.assertEqual(first, second)
        self.assertEqual(4, len(first))
        self.assertTrue(all(item["humanVerified"] is False for item in first))
        self.assertTrue(all("algorithm" not in json.dumps(item).lower() for item in first))
        required = {"outer_circle_visible_arc", "real_groove_open_boundary", "groove_sidewalls", "groove_mouth_endpoints", "occlusion_shadow_regions"}
        self.assertTrue(all(required.issubset(item["requiredShapes"]) for item in first))
        unsafe = list(rows)
        unsafe[0] = {**unsafe[0], "relative_path": "../escape.bmp"}
        with self.assertRaisesRegex(ValueError, "unsafe"):
            build_annotation_queue(unsafe, causes, per_sample=2)

    def test_new_schemas_are_valid(self) -> None:
        try:
            from jsonschema import Draft202012Validator
        except ImportError:
            self.skipTest("jsonschema unavailable")
        root = Path(__file__).resolve().parents[1]
        for name in ("a2-robustness-fold-plan.schema.json", "a2-robustness-audit.schema.json"):
            schema = json.loads((root / "contracts" / name).read_text(encoding="utf-8"))
            Draft202012Validator.check_schema(schema)

    def test_generated_plan_and_audit_validate_against_schemas(self) -> None:
        try:
            import jsonschema
        except ImportError:
            self.skipTest("jsonschema unavailable")
        rows = sample_rows("normal:part-008", 800) + sample_rows("normal:part-009", 900)
        causes = [cause("normal:part-008"), cause("normal:part-009")]
        plan = build_fold_plan(rows, causes, seal(), fold_count=2)
        with tempfile.TemporaryDirectory() as temporary:
            results = Path(temporary) / "results.jsonl"
            results.write_text("", encoding="utf-8")
            audit = audit_results(results, plan, rows, seal())
        root = Path(__file__).resolve().parents[1]
        jsonschema.validate(
            plan,
            json.loads((root / "contracts/a2-robustness-fold-plan.schema.json").read_text()),
        )
        jsonschema.validate(
            audit,
            json.loads((root / "contracts/a2-robustness-audit.schema.json").read_text()),
        )


if __name__ == "__main__":
    unittest.main()
