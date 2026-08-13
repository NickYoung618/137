from __future__ import annotations

import hashlib
import json
import unittest
import zipfile
from pathlib import Path

from algorithms.end_face import CORE_SOURCE_SHA256, core


ROOT = Path(__file__).resolve().parents[1]
DESKTOP_ALGORITHM_ZIP = Path("/home/ubuntu/disk/zzx/算法/算法.zip")
EVIDENCE = ROOT / "specs/005-short-line-candidate/evidence/a2-v2-first-25-user-summary.json"


class EndFaceReferenceSourceTests(unittest.TestCase):
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
