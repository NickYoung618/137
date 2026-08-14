import tempfile
import unittest
from pathlib import Path

import numpy as np

from tools.diagnose_latest_truth_edges import ordered_opposite_pair, require_external_output


class LatestTruthDiagnosticTests(unittest.TestCase):
    def test_ordered_opposite_pair_returns_dark_band_center(self):
        positions = np.arange(-10.0, 10.0)
        derivative = np.zeros_like(positions)
        derivative[5] = -18.0
        derivative[12] = 11.0
        pair = ordered_opposite_pair(derivative, positions)
        self.assertIsNotNone(pair)
        self.assertEqual(-5.0, pair["negativePositionPx"])
        self.assertEqual(2.0, pair["positivePositionPx"])
        self.assertEqual(-1.5, pair["centerPositionPx"])
        self.assertEqual(7.0, pair["pairWidthPx"])

    def test_wrong_polarity_order_is_not_promoted(self):
        positions = np.arange(-10.0, 10.0)
        derivative = np.zeros_like(positions)
        derivative[5] = 18.0
        derivative[12] = -11.0
        self.assertIsNone(ordered_opposite_pair(derivative, positions))

    def test_diagnostic_output_must_remain_outside_worktree(self):
        with self.assertRaisesRegex(ValueError, "outside the Git worktree"):
            require_external_output(Path("tests/latest-truth-output"))
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(Path(tmp).resolve(), require_external_output(Path(tmp)))


if __name__ == "__main__":
    unittest.main()
