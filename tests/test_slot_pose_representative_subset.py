import unittest

from tools.build_slot_pose_representative_subset import build_subset


class RepresentativeSubsetTests(unittest.TestCase):
    def test_explicit_selection_preserves_lineage_and_rewrites_only_task_identity(self):
        manifest = {
            "schemaVersion": "inspection-dataset-manifest/1",
            "datasetId": "fold-1",
            "images": [
                {"imageId": "part:1", "relativePath": "A2/1.bmp", "sha256": "a" * 64}
            ],
        }
        result = {
            "taskId": "fold-1:part:1",
            "result": {"valid": False},
            "error": {"code": "X"},
        }
        subset, outputs, report = build_subset(
            [manifest], [[result]], ["part:1"], "review-024"
        )
        self.assertEqual("review-024:part:1", outputs[0]["taskId"])
        self.assertEqual(result["error"], outputs[0]["error"])
        self.assertEqual("fold-1:part:1", report["lineage"][0]["sourceTaskId"])
        self.assertFalse(report["algorithmResultsUsedForSelection"])
        self.assertEqual(manifest["images"], subset["images"])

    def test_duplicate_or_missing_identity_fails_closed(self):
        manifest = {
            "schemaVersion": "inspection-dataset-manifest/1",
            "datasetId": "fold-1",
            "images": [],
        }
        with self.assertRaisesRegex(ValueError, "unique"):
            build_subset([manifest], [[]], ["x", "x"], "r")
        with self.assertRaisesRegex(ValueError, "missing imageId"):
            build_subset([manifest], [[]], ["x"], "r")
