from __future__ import annotations

import json
import tempfile
import unittest
from types import MethodType
from pathlib import Path

from algorithms.slot_pose.contract import load_config
from algorithms.slot_pose.legacy_adapter import LegacyAEndFaceAdapter
from algorithms.slot_pose.main import run
from tools.generate_synthetic_multi_notches import build_dataset


class MultiNotchRoleIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temporary.name)
        try:
            build_dataset(cls.root, 137)
        except FileNotFoundError as exc:
            cls.temporary.cleanup()
            raise unittest.SkipTest(f"historical source unavailable: {exc}") from exc
        cls.config = cls.root / "config.json"
        cls.images = cls.root / "images"

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temporary.cleanup()

    def test_multi_role_geometry_with_extra_candidate_and_rotation(self) -> None:
        for case_id in ("normal_base", "normal_translate", "normal_wrap"):
            with self.subTest(case_id=case_id):
                payload = run(self.images / f"{case_id}.png", self.config, f"roles:{case_id}")
                self.assertFalse(payload["result"]["valid"])
                self.assertIsNone(payload["result"]["signedRelativeRotationDeg"])
                self.assertEqual("DATUM_DEFINITION_UNCONFIRMED", payload["error"]["code"])
                assignment = payload["diagnostics"]["roleAssignment"]
                self.assertTrue(assignment["unique"], payload)
                groove_ids = {item["candidateId"] for item in payload["diagnostics"]["grooveCandidates"]}
                self.assertTrue(set(assignment["selectedRoleCandidateIds"].values()).issubset(groove_ids))
                self.assertGreaterEqual(payload["diagnostics"]["candidateSummary"]["count"], 4)
                self.assertAlmostEqual(85.0, assignment["drawingAngle"]["includedAngleDeg"], delta=1.0)
                self.assertEqual("NOT_EVALUATED", assignment["drawingAngle"]["toleranceStatus"])

    def test_missing_and_ambiguous_roles_fail_closed(self) -> None:
        expected = {
            "bad_missing_target": "ROLE_ASSIGNMENT_FAILED",
            "bad_ambiguous_target": "ROLE_ASSIGNMENT_AMBIGUOUS",
        }
        for case_id, code in expected.items():
            with self.subTest(case_id=case_id):
                payload = run(self.images / f"{case_id}.png", self.config, f"roles:{case_id}")
                self.assertFalse(payload["result"]["valid"])
                self.assertEqual(code, payload["error"]["code"], payload)
                self.assertIsNone(payload["result"]["signedRelativeRotationDeg"])

    def test_rejected_shadow_fixture_and_weak_dark_region_cannot_fill_target_role(self) -> None:
        for case_id in ("bad_shadow_target", "bad_fixture_target", "bad_weak_target"):
            with self.subTest(case_id=case_id):
                payload = run(self.images / f"{case_id}.png", self.config, f"roles:{case_id}")
                self.assertFalse(payload["result"]["valid"])
                self.assertIn(payload["error"]["code"], {"GROOVE_RECOGNITION_FAILED", "GROOVE_RECOGNITION_AMBIGUOUS"})
                self.assertIsNone(payload["result"]["signedRelativeRotationDeg"])
                recognition = payload["diagnostics"]["grooveRecognition"]
                rejected = {item["candidateId"] for item in recognition["assessments"] if not item["accepted"]}
                self.assertTrue(rejected)
                assignment = payload["diagnostics"].get("roleAssignment")
                if assignment is not None:
                    used = set((assignment.get("selectedRoleCandidateIds") or {}).values())
                    self.assertTrue(used.isdisjoint(rejected))

    def test_borderline_groove_evidence_returns_ambiguous_before_role_assignment(self) -> None:
        config = json.loads(self.config.read_text(encoding="utf-8"))
        config["detector"]["groove_recognition"].update({"min_groove_score": 0.99, "ambiguity_margin": 0.1})
        path = self.root / "ambiguous-groove.json"
        path.write_text(json.dumps(config), encoding="utf-8")
        payload = run(self.images / "normal_base.png", path, "roles:ambiguous-groove")
        self.assertEqual("GROOVE_RECOGNITION_AMBIGUOUS", payload["error"]["code"])
        self.assertEqual("ambiguous", payload["diagnostics"]["grooveRecognition"]["status"])
        self.assertNotIn("roleAssignment", payload["diagnostics"])
        self.assertIsNone(payload["result"]["signedRelativeRotationDeg"])

    def test_multi_role_profile_does_not_require_legacy_single_notch(self) -> None:
        adapter = LegacyAEndFaceAdapter(load_config(self.config))
        adapter.module.find_outer_notch_angle = MethodType(lambda _self, *_args: None, adapter.module)
        estimate = adapter.estimate(self.images / "normal_base.png")
        self.assertTrue(estimate["diagnostics"]["roleAssignment"]["unique"])
        self.assertGreaterEqual(estimate["diagnostics"]["candidateSummary"]["count"], 4)

    def test_drawing_inspection_does_not_become_mechanical_correction(self) -> None:
        config = json.loads(self.config.read_text(encoding="utf-8"))
        config["pose"].update({
            "drawing_datum_definition_confirmed": True,
            "a2_drawing_feature_mapping_confirmed": True,
            "output_purpose": "drawing_tolerance_inspection",
        })
        path = self.root / "inspection-only.json"
        path.write_text(json.dumps(config), encoding="utf-8")
        payload = run(self.images / "normal_base.png", path, "roles:inspection-only")
        self.assertFalse(payload["result"]["valid"])
        self.assertEqual("OUTPUT_PURPOSE_UNCONFIRMED", payload["error"]["code"])
        self.assertEqual("PASS", payload["diagnostics"]["roleAssignment"]["drawingAngle"]["toleranceStatus"])


if __name__ == "__main__":
    unittest.main()
