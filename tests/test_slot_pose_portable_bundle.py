from __future__ import annotations

import json
import math
import os
import shutil
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from algorithms.slot_pose.contract import (
    effective_config_sha256,
    load_config,
    sha256_file,
)
from algorithms.slot_pose.legacy_adapter import (
    LegacyAdapterError,
    LegacyAEndFaceAdapter,
)
from tools.build_slot_pose_portable_bundle import ROOT, build_bundle
from tools.verify_slot_pose_portable_bundle import verify_bundle

CONFIG = ROOT / "config/inspection.example.json"
COMMIT = "a" * 40


class PortableBundleTests(unittest.TestCase):
    def _source(self, root: Path) -> Path:
        reference = root / "reference.bmp"
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
            json.dumps({"imagePath": reference.name, "shapes": shapes}), encoding="utf-8"
        )
        raw = json.loads(CONFIG.read_text(encoding="utf-8"))
        bundled_source = ROOT / "algorithms/end_face/core.py"
        raw["legacy_asset"] = {
            "source_mode": "bundled_module",
            "bundled_module": "algorithms.end_face.core",
            "source_sha256": sha256_file(bundled_source),
            "upstream_source_sha256": "36a53cea8efd172cba0a06a4935b078ac77fd4551a509ed2c3519833fd206c35",
            "annotation_path": str(annotation),
            "annotation_sha256": sha256_file(annotation),
            "reference_path": str(reference),
            "reference_sha256": sha256_file(reference),
        }
        source = root / "source-config.json"
        source.write_text(json.dumps(raw), encoding="utf-8")
        return source

    def _build(self, root: Path, suffix: str = "one") -> tuple[Path, Path, Path]:
        source_root = root / "source"
        source_root.mkdir(exist_ok=True)
        source = self._source(source_root)
        output = root / f"bundle-{suffix}"
        archive = root / f"bundle-{suffix}.tar.gz"
        build_bundle(
            source,
            output,
            archive,
            bundle_id="portable-test",
            branch="030-self-contained-assets",
            commit=COMMIT,
        )
        return source, output, archive

    def test_bundle_relocates_and_initializes_after_source_removal(self) -> None:
        with tempfile.TemporaryDirectory() as temporary, tempfile.TemporaryDirectory() as unrelated:
            root = Path(temporary)
            source, output, _ = self._build(root)
            source_effective = effective_config_sha256(load_config(source))
            moved = root / "已移动 bundle"
            output.rename(moved)
            shutil.rmtree(source.parent)
            prior = Path.cwd()
            try:
                os.chdir(unrelated)
                portable = load_config(moved / "config.json")
                adapter = LegacyAEndFaceAdapter(portable)
            finally:
                os.chdir(prior)
            self.assertEqual(source_effective, effective_config_sha256(portable))
            self.assertEqual(moved / "assets/annotation.json", adapter.paths.annotation)
            self.assertEqual(moved / "assets/reference.bmp", adapter.paths.reference)

    def test_adapter_reverification_fails_closed_after_tamper(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            _, output, _ = self._build(Path(temporary))
            adapter = LegacyAEndFaceAdapter(load_config(output / "config.json"))
            with (output / "assets/reference.bmp").open("ab") as handle:
                handle.write(b"x")
            with self.assertRaises(LegacyAdapterError) as caught:
                adapter.verify_assets()
            self.assertEqual("ASSET_MISMATCH", caught.exception.code)

    def test_manifest_checksums_inventory_and_no_external_path_leak(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            _, output, _ = self._build(Path(temporary))
            report = verify_bundle(output)
            self.assertTrue(report["valid"])
            self.assertEqual(6, report["verifiedFileCount"])
            text = "\n".join(
                (output / name).read_text(encoding="utf-8")
                for name in ("config.json", "manifest.json", "README.md")
            )
            self.assertNotIn("/home/", text)
            manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(
                {"config.json", "assets/annotation.json", "assets/reference.bmp", "README.md"},
                {entry["path"] for entry in manifest["files"]},
            )

    def test_missing_or_tampered_payload_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _, output, _ = self._build(root)
            (output / "assets/annotation.json").unlink()
            with self.assertRaisesRegex(ValueError, "inventory"):
                verify_bundle(output)

            shutil.rmtree(output)
            _, output, _ = self._build(root, "two")
            with (output / "README.md").open("a", encoding="utf-8") as handle:
                handle.write("tamper")
            with self.assertRaisesRegex(ValueError, "integrity"):
                verify_bundle(output)

    def test_identical_builds_have_identical_archive_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source_root = root / "source"
            source_root.mkdir()
            source = self._source(source_root)
            archives = []
            for suffix in ("a", "b"):
                output = root / f"out-{suffix}"
                archive = root / f"archive-{suffix}.tar.gz"
                build_bundle(
                    source, output, archive, bundle_id="same-bundle",
                    branch="030-self-contained-assets", commit=COMMIT,
                )
                archives.append(archive)
            self.assertEqual(sha256_file(archives[0]), sha256_file(archives[1]))
            self.assertEqual(archives[0].read_bytes(), archives[1].read_bytes())

    def test_builder_refuses_overwrite_and_git_worktree_output(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self._source(root)
            existing = root / "existing"
            existing.mkdir()
            with self.assertRaises(FileExistsError):
                build_bundle(
                    source, existing, root / "new.tar.gz", bundle_id="portable-test",
                    branch="030-self-contained-assets", commit=COMMIT,
                )
            with self.assertRaisesRegex(ValueError, "Git working tree"):
                build_bundle(
                    source, ROOT / "outputs/forbidden", root / "new.tar.gz",
                    bundle_id="portable-test", branch="030-self-contained-assets", commit=COMMIT,
                )

    def test_builder_rejects_annotation_that_requires_rewriting(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self._source(root)
            raw = json.loads(source.read_text(encoding="utf-8"))
            annotation = Path(raw["legacy_asset"]["annotation_path"])
            payload = json.loads(annotation.read_text(encoding="utf-8"))
            payload["imagePath"] = "/external/reference.bmp"
            annotation.write_text(json.dumps(payload), encoding="utf-8")
            raw["legacy_asset"]["annotation_sha256"] = sha256_file(annotation)
            source.write_text(json.dumps(raw), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "will not rewrite"):
                build_bundle(
                    source, root / "out", root / "out.tar.gz", bundle_id="portable-test",
                    branch="030-self-contained-assets", commit=COMMIT,
                )


if __name__ == "__main__":
    unittest.main()
