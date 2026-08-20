from __future__ import annotations

import copy
import json
import math
import tempfile
import time
from types import SimpleNamespace
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from algorithms.slot_pose.contract import load_config, sha256_file
from algorithms.slot_pose.legacy_adapter import (
    LegacyAEndFaceAdapter,
    LegacyAdapterError,
    REQUIRED_FUNCTIONS,
    apply_polar_quality_adjudication,
    apply_normalized_face_search_roi,
    recovery_fixture_exclusion_verified,
    wall_family_recovery_used,
)
from tests.test_polar_quality_adjudication import complete_evidence


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/inspection.example.json"


class LegacyAdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = load_config(CONFIG)
        missing = [
            cls.config["legacy_asset"][key]
            for key in ("annotation_path", "reference_path")
            if not Path(cls.config["legacy_asset"][key]).is_file()
        ]
        cls.missing_external_reference_assets = missing

    def test_asset_hash_mismatch_fails_before_import(self) -> None:
        config = copy.deepcopy(self.config)
        config["legacy_asset"]["source_sha256"] = "0" * 64
        with self.assertRaises(LegacyAdapterError) as caught:
            LegacyAEndFaceAdapter(config)
        self.assertEqual("ASSET_MISMATCH", caught.exception.code)

    def test_all_wall_recovery_versions_require_complete_fixture_exclusion(self) -> None:
        for side in (
            {"lineFitStrategy": "bounded-cross-radius-wall-family-v1"},
            {"lineFitStrategy": "shared-longitudinal-wall-family-v2"},
            {"wallFamilyRecoveryUsed": True},
        ):
            with self.subTest(side=side):
                self.assertTrue(wall_family_recovery_used({"startSide": side, "endSide": {}}))
        self.assertFalse(wall_family_recovery_used({"startSide": {}, "endSide": {}}))

        base = {
            "status": "verified", "fixtureBodiesVerified": True,
            "uContourComplete": True, "fixtureSourceExcluded": True,
            "candidateSelectionUsedFixedAngle": False,
        }
        for schema in (
            "fixture-groove-source-exclusion/1",
            "fixture-groove-source-exclusion/2",
        ):
            self.assertTrue(recovery_fixture_exclusion_verified({**base, "schemaVersion": schema}))
        for mutation in (
            {"status": "rejected"}, {"uContourComplete": False},
            {"fixtureSourceExcluded": False}, {"candidateSelectionUsedFixedAngle": True},
        ):
            self.assertFalse(recovery_fixture_exclusion_verified({
                **base, "schemaVersion": "fixture-groove-source-exclusion/2", **mutation,
            }))

    def test_polar_quality_effective_failures_do_not_mutate_original_quality(self) -> None:
        diagnostics = complete_evidence()
        original_quality = copy.deepcopy(diagnostics["quality"])
        original_failures = diagnostics["quality"]["failedChecks"]
        config = {
            "schema_version": "polar-quality-adjudication/1",
            "enabled": True,
            "strategy_version": "locked-physical-groove-proof-v1",
            "development_only": True,
        }
        effective = apply_polar_quality_adjudication(
            diagnostics, original_failures, config,
        )
        self.assertEqual([], effective)
        self.assertEqual(original_quality, diagnostics["quality"])
        self.assertIs(original_failures, diagnostics["quality"]["failedChecks"])
        self.assertEqual(
            "ACCEPTED_OVERRIDE", diagnostics["polarQualityAdjudication"]["decision"],
        )

        denied = complete_evidence()
        denied["grooveRefinement"]["fixtureSourceExclusion"]["fixtureSourceExcluded"] = False
        denied_original = denied["quality"]["failedChecks"]
        denied_effective = apply_polar_quality_adjudication(
            denied, denied_original, config,
        )
        self.assertEqual(["polar_score"], denied_effective)
        self.assertEqual(["polar_score"], denied_original)
        self.assertEqual("REJECTED", denied["polarQualityAdjudication"]["decision"])

    def test_bundled_core_loads_without_gyj_source_tree(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            reference = root / "reference.png"
            Image.new("L", (96, 96), 128).save(reference)
            angles = np.linspace(0.0, 2.0 * math.pi, 16, endpoint=False)
            shapes = []
            for label, radius in (("inner", 16.0), ("outer", 36.0)):
                shapes.append({
                    "label": label,
                    "shape_type": "linestrip",
                    "points": [
                        [48.0 + radius * math.cos(angle), 48.0 + radius * math.sin(angle)]
                        for angle in angles
                    ],
                })
            annotation = root / "annotation.json"
            annotation.write_text(
                json.dumps({"imagePath": reference.name, "shapes": shapes}),
                encoding="utf-8",
            )
            bundled_source = ROOT / "algorithms" / "end_face" / "core.py"
            config = copy.deepcopy(self.config)
            config["legacy_asset"] = {
                "source_mode": "bundled_module",
                "bundled_module": "algorithms.end_face.core",
                "source_sha256": sha256_file(bundled_source),
                "upstream_source_sha256": "36a53cea8efd172cba0a06a4935b078ac77fd4551a509ed2c3519833fd206c35",
                "annotation_path": str(annotation),
                "annotation_sha256": sha256_file(annotation),
                "reference_path": str(reference),
                "reference_sha256": sha256_file(reference),
            }
            adapter = LegacyAEndFaceAdapter(config)
            self.assertEqual(bundled_source.resolve(), adapter.paths.source)
            self.assertEqual("bundled_module", adapter.source_mode)
            self.assertEqual(list(REQUIRED_FUNCTIONS), list(adapter.function_inventory))

            bad = copy.deepcopy(config)
            bad["legacy_asset"]["source_sha256"] = "0" * 64
            with self.assertRaises(LegacyAdapterError) as caught:
                LegacyAEndFaceAdapter(bad)
            self.assertEqual("ASSET_MISMATCH", caught.exception.code)

    def test_edge_family_strategy_preserves_locked_core_and_requires_bundled_source(self) -> None:
        adapter = object.__new__(LegacyAEndFaceAdapter)
        adapter.module = SimpleNamespace(**{name: (lambda *args, **kwargs: None) for name in REQUIRED_FUNCTIONS})
        adapter.source_mode = "external_file"
        adapter.config = {"detector": {"physical_outer_circle": {"edge_family_selection": {"enabled": False}}}}
        adapter._verify_inventory()

        adapter.config["detector"]["physical_outer_circle"]["edge_family_selection"]["enabled"] = True
        with self.assertRaisesRegex(LegacyAdapterError, "bundled_module_required"):
            adapter._verify_inventory()
        adapter.source_mode = "bundled_module"
        adapter._verify_inventory()

    def test_normalized_face_search_roi_masks_only_alignment_input(self) -> None:
        image = np.arange(80, dtype=np.uint8).reshape(8, 10)
        masked = apply_normalized_face_search_roi(image, [0.2, 0.25, 0.8, 0.75])
        np.testing.assert_array_equal(masked[2:6, 2:8], image[2:6, 2:8])
        self.assertEqual(0, int(masked[:2].sum()))
        self.assertEqual(0, int(masked[:, :2].sum()))
        self.assertEqual(0, int(masked[6:].sum()))
        self.assertEqual(0, int(masked[:, 8:].sum()))
        self.assertGreater(int(image.sum()), int(masked.sum()))

    def test_reference_baseline_and_source_remains_unchanged(self) -> None:
        if self.missing_external_reference_assets:
            self.skipTest(
                "external reference assets are unavailable: "
                f"{self.missing_external_reference_assets}"
            )
        adapter = LegacyAEndFaceAdapter(self.config)
        source = adapter.paths.source
        before = sha256_file(source)
        started = time.perf_counter()
        output = adapter.estimate(Path(self.config["legacy_asset"]["reference_path"]))
        elapsed = time.perf_counter() - started
        after = sha256_file(source)
        self.assertEqual(before, after)
        self.assertEqual(list(REQUIRED_FUNCTIONS), output["diagnostics"]["functionInventory"])
        self.assertEqual("bundled_module", output["diagnostics"]["legacyCoreSource"]["mode"])
        self.assertTrue(output["diagnostics"]["legacyCoreSource"]["repositoryContained"])
        slot = output["diagnostics"]["slot"]
        self.assertAlmostEqual(247.2167307, output["diagnostics"]["referenceNotch"]["azimuthImageDeg"], places=3)
        self.assertAlmostEqual(247.0943426, output["candidate_image_deg"], places=3)
        self.assertAlmostEqual(0.0, slot["polarRotationDeg"], delta=0.2)
        self.assertAlmostEqual(0.0, slot["notchRotationDeg"], delta=0.2)
        self.assertGreater(slot["prominence"], 100.0)
        self.assertLess(elapsed, 8.0)

    def test_existing_quality_outputs_drive_fail_closed_gate(self) -> None:
        if self.missing_external_reference_assets:
            self.skipTest(
                "external reference assets are unavailable: "
                f"{self.missing_external_reference_assets}"
            )
        config = copy.deepcopy(self.config)
        config["detector"]["min_notch_prominence"] = 1000.0
        adapter = LegacyAEndFaceAdapter(config)
        with self.assertRaises(LegacyAdapterError) as caught:
            adapter.estimate(Path(config["legacy_asset"]["reference_path"]))
        self.assertEqual("QUALITY_REJECTED", caught.exception.code)
        self.assertIn("notch_prominence", caught.exception.diagnostics["quality"]["failedChecks"])


if __name__ == "__main__":
    unittest.main()
