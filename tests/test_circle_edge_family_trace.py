import math
import json
from pathlib import Path
import unittest

import jsonschema
import numpy as np

from algorithms.slot_pose import circle_edge_candidates
from tools.trace_circle_edge_families import (
    cluster_selected_offsets,
    enumerate_radial_edges,
    summarize_switch_sectors,
)


class CircleEdgeFamilyTraceTests(unittest.TestCase):
    def test_production_and_diagnostic_peak_enumeration_share_one_implementation(self):
        self.assertIs(enumerate_radial_edges, circle_edge_candidates.enumerate_radial_edge_candidates)

    def test_enumerates_multiple_concentric_bright_to_dark_edges(self):
        radii = np.arange(90.0, 131.0)
        values = np.full(radii.shape, 220.0)
        values[radii >= 102.0] = 140.0
        values[radii >= 120.0] = 10.0
        peaks = enumerate_radial_edges(radii, values, min_gradient=20.0, separation_px=4.0)
        falling = [item for item in peaks if item["polarity"] == "bright_to_dark"]
        self.assertEqual(len(falling), 2)
        self.assertAlmostEqual(falling[0]["radiusPx"], 119.5)
        self.assertAlmostEqual(falling[1]["radiusPx"], 101.5)

    def test_single_edge_is_not_invented_as_two_families(self):
        radii = np.arange(20.0, 51.0)
        values = np.where(radii < 37.0, 180.0, 15.0)
        peaks = enumerate_radial_edges(radii, values, min_gradient=30.0)
        self.assertEqual([item["radiusPx"] for item in peaks], [36.5])

    def test_bright_to_dark_candidates_are_bounded_subpixel_and_require_dark_tail(self):
        radii = np.arange(80.0, 141.0)
        values = np.full(radii.shape, 210.0)
        values[radii >= 95.0] = 20.0
        values[radii >= 105.0] = 200.0
        values[radii >= 122.0] = 10.0
        peaks = circle_edge_candidates.enumerate_radial_edge_candidates(
            radii, values, min_gradient=10.0, separation_px=3.0, max_peaks=1,
            polarity="bright_to_dark", min_background_persistence_ratio=0.95,
        )
        self.assertEqual(1, len(peaks))
        self.assertAlmostEqual(121.5, peaks[0]["radiusPx"])
        self.assertEqual("bright_to_dark", peaks[0]["polarity"])
        self.assertGreaterEqual(peaks[0]["backgroundPersistenceRatio"], 0.95)

    def test_candidate_controls_and_nonfinite_values_fail_before_sampling(self):
        radii = np.arange(3.0)
        values = np.arange(3.0)
        invalid = (
            {"min_gradient": 0.0}, {"separation_px": 0.0}, {"max_peaks": 0},
            {"polarity": "sideways"}, {"min_background_persistence_ratio": 1.1},
        )
        for options in invalid:
            with self.subTest(options=options), self.assertRaises(ValueError):
                circle_edge_candidates.enumerate_radial_edge_candidates(radii, values, **options)

    def test_selected_offsets_cluster_cross_edge_switches(self):
        records = [
            {"angleDeg": angle, "selectedOffsetPx": offset}
            for angle, offset in enumerate([5.0, 5.5, 4.8, -43.0, -42.4, 5.2])
        ]
        clusters = cluster_selected_offsets(records, merge_px=4.0)
        self.assertEqual([item["count"] for item in clusters], [4, 2])
        self.assertAlmostEqual(clusters[0]["medianOffsetPx"], 5.1)
        self.assertAlmostEqual(clusters[1]["medianOffsetPx"], -42.7)

    def test_offset_chain_does_not_bridge_distinct_edge_families(self):
        records = [
            {"angleDeg": float(index), "selectedOffsetPx": offset}
            for index, offset in enumerate([-60.0, -52.5, -45.0, -37.5, -5.0, 2.0, 8.0])
        ]
        clusters = cluster_selected_offsets(records, merge_px=8.0)
        self.assertGreaterEqual(len(clusters), 3)
        self.assertTrue(all(item["maxOffsetPx"] - item["minOffsetPx"] <= 16.0 for item in clusters))

    def test_switch_sector_wraps_zero_degree(self):
        records = [
            {"angleDeg": angle, "familyId": "edge-family-002" if angle in {350.0, 0.0, 10.0} else "edge-family-001"}
            for angle in (0.0, 10.0, 20.0, 340.0, 350.0)
        ]
        sectors = summarize_switch_sectors(records, primary_family_id="edge-family-001")
        self.assertEqual(len(sectors), 1)
        self.assertTrue(sectors[0]["wrapsBoundary"])
        self.assertEqual(sectors[0]["sampleAnglesDeg"], [350.0, 0.0, 10.0])

    def test_31_and_328_degree_rotations_have_no_special_mask_or_order_rule(self):
        source = (
            Path(__file__).resolve().parents[1]
            / "algorithms/slot_pose/physical_outer_circle.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("31.0", source)
        self.assertNotIn("328.0", source)
        for rotation in (31.0, 328.0):
            records = [
                {
                    "angleDeg": (angle + rotation) % 360.0,
                    "familyId": "edge-family-002" if angle in {350.0, 0.0, 10.0} else "edge-family-001",
                }
                for angle in (0.0, 10.0, 20.0, 340.0, 350.0)
            ]
            reordered = list(reversed(records))
            first = summarize_switch_sectors(records, primary_family_id="edge-family-001")
            second = summarize_switch_sectors(reordered, primary_family_id="edge-family-001")
            self.assertEqual(first, second)
            self.assertEqual(1, len(first))
            self.assertEqual(3, first[0]["sampleCount"])

    def test_nonfinite_input_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "finite"):
            enumerate_radial_edges(np.array([1.0, 2.0]), np.array([1.0, math.nan]))
        with self.assertRaisesRegex(ValueError, "finite"):
            cluster_selected_offsets([{"angleDeg": 0.0, "selectedOffsetPx": math.inf}])

    def test_trace_contract_rejects_private_path_fields(self):
        report = {
            "schemaVersion": "circle-edge-family-trace/1", "developmentOnly": True,
            "detectorModified": False, "authoritative": False,
            "image": {"sha256": "a" * 64, "width": 100, "height": 80},
            "searchPriorCircle": {}, "angleCount": 180, "selectedCount": 0,
            "missingAnglesDeg": [], "families": [], "primaryFamilyId": None,
            "switchSectors": [], "edgeFamilySwitchObserved": False, "perRay": [],
        }
        schema = json.loads((Path(__file__).resolve().parents[1] / "contracts/circle-edge-family-trace.schema.json").read_text())
        jsonschema.validate(report, schema)
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate({**report, "imagePath": "forbidden-input-field"}, schema)


if __name__ == "__main__":
    unittest.main()
