from __future__ import annotations

import hashlib
import json
import math
import unittest
import zipfile
from pathlib import Path

from algorithms.end_face import CORE_SOURCE_SHA256, core
from algorithms.end_face.quality import canonical_feature_label


ROOT = Path(__file__).resolve().parents[1]
DESKTOP_ALGORITHM_ZIP = Path("/home/ubuntu/disk/zzx/算法/算法.zip")
EVIDENCE = ROOT / "specs/005-short-line-candidate/evidence/a2-v2-first-25-user-summary.json"


class EndFaceReferenceSourceTests(unittest.TestCase):
    def test_desktop_labelme_maps_expected_dimensions_to_geometry(self) -> None:
        if not DESKTOP_ALGORITHM_ZIP.is_file():
            self.skipTest(f"desktop algorithm zip unavailable: {DESKTOP_ALGORITHM_ZIP}")
        with zipfile.ZipFile(DESKTOP_ALGORITHM_ZIP) as archive:
            members = [info for info in archive.infolist() if info.filename.endswith("sample_1_label.json")]
            self.assertEqual(1, len(members))
            annotation = json.loads(archive.read(members[0]).decode("utf-8"))
        shapes = {canonical_feature_label(str(shape["label"])): shape for shape in annotation["shapes"]}
        expected = {
            "46": ("line", 2),
            "100": ("linestrip", 30),
            "20": ("line", 2),
            "71": ("linestrip", 26),
            "19": ("line", 2),
            "30": ("line", 2),
            "86": ("linestrip", 85),
            "80": ("linestrip", 88),
            "M78": ("linestrip", 85),
        }
        for canonical, (shape_type, point_count) in expected.items():
            self.assertIn(canonical, shapes)
            self.assertEqual(shape_type, shapes[canonical]["shape_type"])
            self.assertEqual(point_count, len(shapes[canonical]["points"]))
        for canonical, expected_length in (("19", 44.7955193565), ("30", 26.1956057001)):
            p1, p2 = shapes[canonical]["points"]
            self.assertAlmostEqual(expected_length, math.hypot(p2[0] - p1[0], p2[1] - p1[1]), places=6)

    def test_repository_core_matches_the_desktop_archive_byte_for_byte(self) -> None:
        if not DESKTOP_ALGORITHM_ZIP.is_file():
            self.skipTest(f"desktop algorithm zip unavailable: {DESKTOP_ALGORITHM_ZIP}")
        with zipfile.ZipFile(DESKTOP_ALGORITHM_ZIP) as archive:
            members = [info for info in archive.infolist() if info.filename.endswith("repeatability_evaluation.py")]
            self.assertEqual(1, len(members))
            desktop_bytes = archive.read(members[0])
        repository_bytes = Path(core.__file__).read_bytes()
        self.assertEqual(desktop_bytes, repository_bytes)
        self.assertEqual(CORE_SOURCE_SHA256, hashlib.sha256(repository_bytes).hexdigest())

    def test_user_reported_v2_valid_and_invalid_counts_are_consistent(self) -> None:
        evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))
        self.assertEqual(25, evidence["imageCount"])
        for feature in ("19", "30", "46", "M78", "80", "86"):
            self.assertEqual(
                evidence["imageCount"],
                evidence["coreValidCounts"][feature] + evidence["coreInvalidCounts"][feature],
            )
        self.assertEqual(25, evidence["coreFailureReasons"]["19"]["short_line_lateral_edge_not_found"])
        self.assertEqual(25, evidence["coreFailureReasons"]["30"]["short_line_lateral_edge_not_found"])


if __name__ == "__main__":
    unittest.main()
