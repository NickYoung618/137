from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.build_complete_groove_review_queue import (
    build_complete_groove_review_queue,
    write_review_queue_bundle,
)

try:
    import jsonschema
except ImportError:
    jsonschema = None


def digest(number: int) -> str:
    return f"{number:064x}"


def image(sample: str, index: int, number: int) -> dict:
    return {
        "imageId": f"{sample}:fixed-pose:{index:04d}",
        "relativePath": f"A2/normal/frame-{number:04d}.bmp",
        "sampleId": sample,
        "conditionId": "fixed-pose",
        "repeatIndex": index,
        "sourceImageSha256": digest(number),
        "sha256": digest(number),
        "bytes": 1024,
        "format": "BMP",
        "width": 5472,
        "height": 3648,
        "mode": "L",
    }


def result(number: int, *, two_walls: bool, error: str = "GROOVE_SOURCE_INCONSISTENT") -> dict:
    diagnostics = {}
    if two_walls:
        diagnostics["grooveRefinement"] = {
            "status": "failed",
            "startSide": {"points": [[1.0, 2.0], [2.0, 3.0]]},
            "endSide": {"points": [[8.0, 2.0], [7.0, 3.0]]},
        }
        diagnostics["localSecondWallDiagnostic"] = {
            "schemaVersion": "local-second-wall-diagnostic/4",
            "status": "PARTIALLY_OBSERVED",
            "sideSearchMergeClusters": [
                {"clusterId": "falling-wall-cluster-001"},
                {"clusterId": "rising-wall-cluster-001"},
            ],
        }
    return {
        "image": {"sha256": digest(number)},
        "result": {"valid": False},
        "error": {"code": error, "stage": "groove_source_consistency"},
        "diagnostics": diagnostics,
    }


class CompleteGrooveReviewQueueTests(unittest.TestCase):
    def manifests_and_results(self) -> tuple[list[dict], list[dict]]:
        part008 = [image("normal:part-008", i, 800 + i) for i in range(1, 5)]
        part019 = [image("normal:part-019", i, 1900 + i) for i in range(1, 5)]
        part009 = [image("normal:part-009", i, 900 + i) for i in range(1, 3)]
        manifest = {"schemaVersion": "inspection-dataset-manifest/1", "datasetId": "fold", "images": part008 + part019 + part009}
        results = [result(800 + i, two_walls=True) for i in range(1, 5)]
        results += [result(1900 + i, two_walls=True) for i in range(1, 5)]
        results += [result(900 + i, two_walls=False, error="HOUSING_CIRCLE_NOT_FOUND") for i in range(1, 3)]
        return [manifest], results

    def test_sample_first_sha_stable_queue_excludes_known_partial_and_contains_no_truth(self) -> None:
        manifests, results = self.manifests_and_results()
        kwargs = dict(
            exclusions={
                "normal:part-006": "sealed_transition_sample",
                "normal:part-019": "human_confirmed_partial_mixed_opening",
            },
            max_samples=1,
            frames_per_sample=2,
            source_manifest_sha256s=[digest(61)],
            source_result_sha256s=[digest(62)],
        )
        first = build_complete_groove_review_queue(manifests, results, **kwargs)
        second = build_complete_groove_review_queue(
            [{**manifests[0], "images": list(reversed(manifests[0]["images"]))}],
            list(reversed(results)), **kwargs,
        )
        self.assertEqual(first, second)
        self.assertEqual("complete-groove-review-queue/1", first["schemaVersion"])
        self.assertEqual(2, len(first["entries"]))
        self.assertEqual({"normal:part-008"}, {item["sampleId"] for item in first["entries"]})
        self.assertTrue(all(item["humanVerified"] is False for item in first["entries"]))
        self.assertFalse(first["truthPolicy"]["accuracyEvaluated"])
        self.assertFalse(first["truthPolicy"]["algorithmOutputIsTruth"])
        serialized = json.dumps(first).lower()
        self.assertNotIn("currentangle", serialized)
        self.assertNotIn("correctiondeg", serialized)
        excluded = {item["sampleId"]: item["reason"] for item in first["excludedSamples"]}
        self.assertEqual("human_confirmed_partial_mixed_opening", excluded["normal:part-019"])
        audit = {item["sampleId"]: item for item in first["sampleAudit"]}
        self.assertEqual(4, audit["normal:part-008"]["twoWallEvidenceCount"])
        self.assertEqual("EXCLUDED", audit["normal:part-019"]["selectionStatus"])

    def test_manifest_result_mismatch_and_unsafe_path_fail_closed(self) -> None:
        manifests, results = self.manifests_and_results()
        with self.assertRaisesRegex(ValueError, "result missing"):
            build_complete_groove_review_queue(
                manifests, results[:-1], exclusions={}, max_samples=1, frames_per_sample=2,
            )
        unsafe = json.loads(json.dumps(manifests))
        unsafe[0]["images"][0]["relativePath"] = "../escape.bmp"
        with self.assertRaisesRegex(ValueError, "unsafe"):
            build_complete_groove_review_queue(
                unsafe, results, exclusions={}, max_samples=1, frames_per_sample=2,
            )

    def test_bundle_is_external_and_schema_valid(self) -> None:
        manifests, results = self.manifests_and_results()
        queue = build_complete_groove_review_queue(
            manifests, results,
            exclusions={"normal:part-019": "human_confirmed_partial_mixed_opening"},
            max_samples=1, frames_per_sample=2,
        )
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "queue"
            write_review_queue_bundle(output, queue)
            self.assertTrue((output / "review-queue.json").is_file())
            self.assertTrue((output / "review-queue.csv").is_file())
            manifest = json.loads((output / "review-manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(2, len(manifest["images"]))
            self.assertTrue(all("relativePath" in item and "sha256" in item for item in manifest["images"]))
            if jsonschema is not None:
                root = Path(__file__).resolve().parents[1]
                schema = json.loads(
                    (root / "contracts/complete-groove-review-queue.schema.json").read_text(encoding="utf-8")
                )
                jsonschema.Draft202012Validator.check_schema(schema)
                jsonschema.validate(queue, schema)

        project = Path(__file__).resolve().parents[1]
        with self.assertRaisesRegex(ValueError, "outside"):
            write_review_queue_bundle(project / "forbidden-review-output", queue)


if __name__ == "__main__":
    unittest.main()
