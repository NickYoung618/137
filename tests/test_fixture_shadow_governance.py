from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.audit_a2_fixture_shadow_evidence import audit_fixture_shadow_history
from tools.audit_a2_robustness_groups import build_annotation_queue


def digest(index: int) -> str:
    return f"{index:064x}"


def grouping(sample: str, start: int, count: int = 2) -> list[dict[str, str]]:
    return [{
        "relative_path": f"A2/{sample}/{index}.bmp",
        "dataset_class": "normal",
        "source_image_sha256": digest(start + index),
        "sample_id": sample,
        "condition_id": "fixed",
        "repeat_index": str(index),
        "split": "unassigned",
    } for index in range(count)]


def record(sha: str, candidates: list[dict]) -> dict:
    return {
        "image": {"sha256": sha},
        "diagnostics": {"rawCandidates": candidates},
        "result": {"valid": False},
        "error": {"code": "GROOVE_RECOGNITION_FAILED"},
    }


def candidate(center: float, half: float, prominence: float, area: float) -> dict:
    return {
        "candidateId": "x", "centerDeg": center, "halfWidthDeg": half,
        "prominence": prominence, "deficitArea": area,
    }


class FixtureShadowGovernanceTests(unittest.TestCase):
    def test_historical_audit_reproduces_counts_and_marks_relaxed_definition_unavailable(self) -> None:
        rows = grouping("normal:part-001", 100, 3) + grouping("normal:part-006", 600, 2)
        clean = [
            candidate(31.4, 10.8, 103.0, 310.0),
            candidate(200.0, 8.0, 150.0, 1400.0),
            candidate(327.7, 11.1, 99.0, 278.0),
        ]
        records = [
            record(rows[0]["source_image_sha256"], clean),
            record(rows[1]["source_image_sha256"], clean[:2]),
            record(rows[2]["source_image_sha256"], []),
            record(rows[3]["source_image_sha256"], clean),
            record(rows[4]["source_image_sha256"], clean),
        ]
        lock = {
            "selectedSampleId": "normal:part-006",
            "selectedImageSha256s": [rows[3]["source_image_sha256"], rows[4]["source_image_sha256"]],
        }
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "results.jsonl"
            path.write_text("\n".join(json.dumps(item) for item in records) + "\n", encoding="utf-8")
            audit = audit_fixture_shadow_history(path, rows, lock)
        self.assertEqual(5, audit["linesScanned"])
        self.assertEqual(3, audit["targetRecordsParsed"])
        self.assertEqual(0, audit["sealedRecordsParsed"])
        self.assertEqual({"0": 1, "2": 1, "3": 1}, audit["rawCandidateCountDistribution"])
        self.assertEqual(1, audit["strictThreeCandidateEvidence"]["frameCount"])
        self.assertEqual("definition_missing", audit["relaxedPairEvidence"]["status"])
        self.assertFalse(audit["accuracyEvaluated"])

    def test_sealed_sha_alias_is_rejected_before_results_open(self) -> None:
        rows = grouping("normal:renamed", 700, 2)
        lock = {
            "selectedSampleId": "normal:part-006",
            "selectedImageSha256s": [rows[0]["source_image_sha256"]],
        }
        with self.assertRaisesRegex(ValueError, "sealed SHA"):
            audit_fixture_shadow_history(Path("/must/not/be/opened.jsonl"), rows, lock)

    def test_required_queue_has_explicit_real_groove_and_two_fixture_regions(self) -> None:
        rows = (
            grouping("normal:part-015", 1500)
            + grouping("normal:part-019", 1900)
            + grouping("normal:part-021", 2100)
        )
        causes = [
            {"sample_id": sample, "failure_family": "fixture-overlap"}
            for sample in ("normal:part-015", "normal:part-019", "normal:part-021")
        ]
        queue = build_annotation_queue(rows, causes, per_sample=2)
        self.assertEqual(6, len(queue))
        required = {
            "real_groove_boundary",
            "fixture_shadow_a_region",
            "fixture_shadow_b_region",
        }
        self.assertTrue(all(required.issubset(item["requiredShapes"]) for item in queue))
        self.assertTrue(all(item["humanVerified"] is False for item in queue))


if __name__ == "__main__":
    unittest.main()
