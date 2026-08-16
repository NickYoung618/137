from __future__ import annotations

import json
import csv
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from tools.dataset_common import inspect_image
from tools.evaluation_governance import (
    build_development_manifest,
    build_group_eligibility,
    freeze_transitional_blind,
    expand_confirmed_segments,
    prepare_dataset,
)
from tools.prepare_a2_evaluation import main as prepare_main
from tools.freeze_transition_blind import main as freeze_main
from tools.run_transitional_blind_once import run_once


def digest(index: int) -> str:
    return f"{index:064x}"


def records(sample: str, condition: str, count: int, *, dataset_class: str = "normal", start: int = 1, split: str = "unassigned"):
    inventory, grouping = [], []
    for repeat in range(1, count + 1):
        index = start + repeat - 1
        relative = f"A2/{dataset_class}/{sample}-{condition}-{repeat:03d}.bmp"
        common = {"relative_path": relative, "dataset_class": dataset_class, "source_image_sha256": digest(index)}
        inventory.append(common | {"sample_id": "", "condition_id": "", "repeat_index": "", "capture_sequence": str(index), "capture_timestamp": "", "split": "unassigned"})
        grouping.append(common | {"sample_id": sample, "condition_id": condition, "repeat_index": str(repeat), "split": split, "grouping_authority": "capture-owner", "grouping_provenance": "record-1"})
    return inventory, grouping


class EvaluationGovernanceTests(unittest.TestCase):
    def test_blank_inventory_cannot_be_used_as_confirmed_grouping(self) -> None:
        inventory, _ = records("p1", "c1", 20)
        with self.assertRaisesRegex(ValueError, "confirmed grouping"):
            prepare_dataset(Path("/unused"), inventory, inventory, verify_images=False)

    def test_confirmed_segments_expand_tail_conditions_without_algorithm_results(self) -> None:
        inventory, _ = records("unused", "unused", 20, start=481)
        segments = [
            {"dataset_class": "normal", "start_capture_sequence": "481", "end_capture_sequence": "498", "sample_id": "normal:part-025", "condition_id": "pre-rotation", "split": "unassigned", "grouping_authority": "owner", "grouping_provenance": "capture-record"},
            {"dataset_class": "normal", "start_capture_sequence": "499", "end_capture_sequence": "500", "sample_id": "normal:part-025", "condition_id": "post-rotation", "split": "unassigned", "grouping_authority": "owner", "grouping_provenance": "capture-record"},
        ]
        expanded = expand_confirmed_segments(inventory, segments)
        by_condition = {}
        for item in expanded:
            by_condition.setdefault(item["condition_id"], []).append(item)
        self.assertEqual(18, len(by_condition["pre-rotation"]))
        self.assertEqual(2, len(by_condition["post-rotation"]))
        self.assertEqual({"normal:part-025"}, {item["sample_id"] for item in expanded})
        self.assertEqual(["1", "2"], [item["repeat_index"] for item in by_condition["post-rotation"]])

    def test_confirmed_segments_reject_overlap_and_incomplete_coverage(self) -> None:
        inventory, _ = records("unused", "unused", 3)
        base = {"dataset_class": "normal", "sample_id": "p", "condition_id": "c", "split": "unassigned", "grouping_authority": "owner", "grouping_provenance": "record"}
        with self.assertRaisesRegex(ValueError, "do not cover"):
            expand_confirmed_segments(inventory, [base | {"start_capture_sequence": "1", "end_capture_sequence": "2"}])
        with self.assertRaisesRegex(ValueError, "overlap"):
            expand_confirmed_segments(inventory, [base | {"start_capture_sequence": "1", "end_capture_sequence": "2"}, base | {"start_capture_sequence": "2", "end_capture_sequence": "3"}])

    def test_listed_unified_root_is_processed_once_without_class_recursion(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            inventory, grouping = [], []
            for index, relative, klass in ((1, "A2/frame.bmp", "normal"), (2, "A2/坏/frame.bmp", "bad")):
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                Image.new("L", (8, 6), index).save(path)
                info = inspect_image(path)
                inventory.append({"relative_path": relative, "dataset_class": klass, "source_image_sha256": info["sha256"], "capture_sequence": str(index), "split": "unassigned"})
                grouping.append({"relative_path": relative, "dataset_class": klass, "source_image_sha256": info["sha256"], "sample_id": f"{klass}:p1", "condition_id": "c1", "repeat_index": "1", "split": "unassigned", "grouping_authority": "owner", "grouping_provenance": "record"})
            manifest, _, report = prepare_dataset(root, inventory, grouping, verify_images=True, minimum_frames=1)
            self.assertEqual(2, len(manifest["images"]))
            self.assertEqual({"A2/frame.bmp", "A2/坏/frame.bmp"}, {item["relativePath"] for item in manifest["images"]})
            self.assertEqual(2, report["verifiedImageCount"])

    def test_twenty_is_eligible_and_eighteen_plus_two_are_retained_but_excluded(self) -> None:
        i1, g1 = records("normal:p24", "fixed", 20, start=1)
        i2, g2 = records("normal:p25", "before-rotation", 18, start=21)
        i3, g3 = records("normal:p25", "after-rotation", 2, start=39)
        _, eligibility, _ = prepare_dataset(Path("/unused"), i1 + i2 + i3, g1 + g2 + g3, verify_images=False)
        by_condition = {item["conditionId"]: item for item in eligibility["groups"]}
        self.assertEqual("ELIGIBLE", by_condition["fixed"]["status"])
        self.assertEqual(["FRAME_COUNT_LT_20"], by_condition["before-rotation"]["exclusionReasons"])
        self.assertEqual(["FRAME_COUNT_LT_20"], by_condition["after-rotation"]["exclusionReasons"])
        self.assertEqual(40, sum(item["frameCount"] for item in eligibility["groups"]))

    def test_static_group_requires_contiguous_capture_sequence_in_repeat_order(self) -> None:
        inventory, grouping = records("normal:p1", "fixed", 20)
        inventory[10]["capture_sequence"] = "99"
        _, eligibility, _ = prepare_dataset(Path("/unused"), inventory, grouping, verify_images=False)
        self.assertIn("CAPTURE_SEQUENCE_NOT_CONTIGUOUS", eligibility["groups"][0]["exclusionReasons"])

    def test_bad_groups_require_authoritative_pose_semantics(self) -> None:
        inventory, grouping = records("bad:p1", "fixed", 20, dataset_class="bad")
        _, blocked, _ = prepare_dataset(Path("/unused"), inventory, grouping, verify_images=False)
        self.assertIn("BAD_SEMANTICS_UNCONFIRMED", blocked["groups"][0]["exclusionReasons"])
        semantics = {
            row["relative_path"]: {"bad_reason": "blur", "pose_usable": "true", "authority": "quality", "provenance": "review"}
            for row in inventory
        }
        _, eligible, _ = prepare_dataset(Path("/unused"), inventory, grouping, semantics_records=semantics, verify_images=False)
        self.assertEqual("ELIGIBLE", eligible["groups"][0]["status"])

    def test_sample_and_source_lineage_cannot_cross_purposes(self) -> None:
        inventory, grouping = records("p1", "c1", 20, split="development")
        grouping[-1]["split"] = "validation"
        with self.assertRaisesRegex(ValueError, "sample.*purposes"):
            prepare_dataset(Path("/unused"), inventory, grouping, verify_images=False)

    def test_blind_selection_is_order_independent_and_freezes_whole_sample(self) -> None:
        ia, ga = records("normal:a", "c1", 20, start=1)
        ib1, gb1 = records("normal:b", "c1", 20, start=101)
        ib2, gb2 = records("normal:b", "c2", 20, start=121)
        manifest, eligibility, _ = prepare_dataset(Path("/unused"), ia + ib1 + ib2, ga + gb1 + gb2, verify_images=False)
        blind1, lock1 = freeze_transitional_blind(manifest, eligibility)
        reversed_manifest = dict(manifest, images=list(reversed(manifest["images"])))
        blind2, lock2 = freeze_transitional_blind(reversed_manifest, eligibility)
        self.assertEqual(lock1["selectedSampleId"], lock2["selectedSampleId"])
        self.assertEqual(lock1["selectedImageSha256s"], lock2["selectedImageSha256s"])
        self.assertEqual("NON_STRICT_TRANSITIONAL", lock1["blindStatus"])
        self.assertFalse(lock1["strictUnseenClaimed"])
        self.assertTrue(all(item["sampleId"] == lock1["selectedSampleId"] for item in blind1["images"]))
        self.assertEqual({item["sha256"] for item in blind1["images"]}, set(lock1["selectedImageSha256s"]))
        development = build_development_manifest(manifest, lock1)
        self.assertFalse(any(item["sampleId"] == lock1["selectedSampleId"] for item in development["images"]))
        self.assertEqual({"development"}, {item["split"] for item in development["images"]})

    def test_blind_requires_candidate_and_never_accepts_results(self) -> None:
        inventory, grouping = records("p1", "short", 2)
        manifest, eligibility, _ = prepare_dataset(Path("/unused"), inventory, grouping, verify_images=False)
        with self.assertRaisesRegex(ValueError, "eligible physical sample"):
            freeze_transitional_blind(manifest, eligibility)

    def test_new_schemas_are_valid(self) -> None:
        try:
            from jsonschema import Draft202012Validator
        except ImportError:
            self.skipTest("jsonschema unavailable")
        for name in ("a2-static-group-eligibility", "a2-static-repeatability", "a2-transitional-blind-lock", "a2-transitional-blind-execution"):
            schema = json.loads((Path(__file__).parents[1] / "contracts" / f"{name}.schema.json").read_text())
            Draft202012Validator.check_schema(schema)

    def test_prepare_and_freeze_clis_write_path_safe_versioned_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            image = root / "A2" / "frame.bmp"
            image.parent.mkdir()
            Image.new("L", (8, 6), 10).save(image)
            info = inspect_image(image)
            inventory = root / "inventory.csv"
            grouping = root / "grouping.csv"
            inventory_rows = [{"relative_path": "A2/frame.bmp", "sample_id": "", "condition_id": "", "repeat_index": "", "capture_sequence": "1", "capture_timestamp": "", "split": "unassigned", "dataset_class": "normal", "source_image_sha256": info["sha256"]}]
            grouping_rows = [{"relative_path": "A2/frame.bmp", "source_image_sha256": info["sha256"], "sample_id": "normal:p1", "condition_id": "fixed", "repeat_index": "1", "split": "unassigned", "dataset_class": "normal", "grouping_authority": "owner", "grouping_provenance": "record"}]
            for path, rows in ((inventory, inventory_rows), (grouping, grouping_rows)):
                with path.open("w", newline="", encoding="utf-8") as handle:
                    writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
                    writer.writeheader(); writer.writerows(rows)
            prepared = root / "prepared"
            self.assertEqual(0, prepare_main(["--data-root", str(root), "--inventory", str(inventory), "--grouping", str(grouping), "--output-dir", str(prepared), "--verify-images", "--minimum-frames", "1"]))
            blind = root / "blind"
            self.assertEqual(0, freeze_main(["--manifest", str(prepared / "manifest.json"), "--eligibility", str(prepared / "static-group-eligibility.json"), "--output-dir", str(blind)]))
            lock = json.loads((blind / "transitional-blind-lock.json").read_text())
            self.assertEqual("NON_STRICT_TRANSITIONAL", lock["blindStatus"])
            self.assertTrue((blind / "SHA256SUMS").is_file())
            self.assertTrue((blind / "development-manifest.json").is_file())
            self.assertEqual(2, freeze_main(["--manifest", str(prepared / "manifest.json"), "--eligibility", str(prepared / "static-group-eligibility.json"), "--output-dir", str(blind)]))

    def test_locked_blind_execution_writes_once_and_refuses_repeat(self) -> None:
        inventory, grouping = records("normal:p1", "fixed", 20)
        manifest, eligibility, _ = prepare_dataset(Path("/unused"), inventory, grouping, verify_images=False)
        blind_manifest, lock = freeze_transitional_blind(manifest, eligibility, created_at="2026-08-16T00:00:00Z")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = root / "config.json"
            config.write_text("{}", encoding="utf-8")
            fake = lambda _manifest, _root, _config: [
                {"image": {"sha256": item["sha256"]}, "result": {"valid": True}} for item in _manifest["images"]
            ]
            record = run_once(blind_manifest, lock, root, config, root / "once", runner=fake)
            self.assertEqual(1, record["executionCount"])
            self.assertEqual(20, record["resultCount"])
            with self.assertRaisesRegex(ValueError, "second run"):
                run_once(blind_manifest, lock, root, config, root / "once", runner=fake)

    def test_locked_blind_failed_attempt_is_claimed_and_cannot_be_retried(self) -> None:
        inventory, grouping = records("normal:p1", "fixed", 20)
        manifest, eligibility, _ = prepare_dataset(Path("/unused"), inventory, grouping, verify_images=False)
        blind_manifest, lock = freeze_transitional_blind(manifest, eligibility, created_at="2026-08-16T00:00:00Z")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = root / "config.json"
            config.write_text("{}", encoding="utf-8")

            def fail(*_args):
                raise RuntimeError("simulated detector interruption")

            with self.assertRaisesRegex(RuntimeError, "interruption"):
                run_once(blind_manifest, lock, root, config, root / "once", runner=fail)
            self.assertTrue((root / "once" / "execution-claim.json").is_file())
            with self.assertRaisesRegex(ValueError, "second run"):
                run_once(blind_manifest, lock, root, config, root / "once", runner=lambda *_args: [])


if __name__ == "__main__":
    unittest.main()
