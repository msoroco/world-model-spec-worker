import unittest
import json
import tempfile
from pathlib import Path

from lane_use import measure_frame, measure_joined_frames
from finalize_lane_use import finalize


LANE = [(0, 0), (20, 0), (20, 4), (0, 4)]
MOTORCYCLE = [(4, 1.5), (6, 1.5), (6, 2.5), (4, 2.5)]


class LaneUseMeasurements(unittest.TestCase):
    def test_adjacent_vehicle_has_measured_gap_and_no_lane_occupancy(self):
        ego = [(4, 4.5), (6, 4.5), (6, 6.5), (4, 6.5)]
        value = measure_frame(LANE, MOTORCYCLE, ego)
        self.assertAlmostEqual(value["motorcycle_lane_overlap_fraction"], 1)
        self.assertAlmostEqual(value["ego_lane_overlap_fraction"], 0)
        self.assertAlmostEqual(value["footprint_surface_gap_m"], 2)

    def test_adjacent_vehicle_partly_enters_occupied_lane(self):
        ego = [(4, 3), (6, 3), (6, 5), (4, 5)]
        value = measure_frame(LANE, MOTORCYCLE, ego)
        self.assertAlmostEqual(value["ego_lane_overlap_fraction"], 0.5)
        self.assertAlmostEqual(value["footprint_surface_gap_m"], 0.5)

    def test_spatial_overlap_is_measured_without_legal_label(self):
        ego = [(5, 2), (7, 2), (7, 4), (5, 4)]
        value = measure_frame(LANE, MOTORCYCLE, ego)
        self.assertAlmostEqual(value["footprint_overlap_area_m2"], 0.5)
        self.assertEqual(value["footprint_surface_gap_m"], 0)
        self.assertNotIn("deprived_of_full_use", value)

    def test_reversed_winding_keeps_results(self):
        ego = [(4, 3), (6, 3), (6, 5), (4, 5)]
        normal = measure_frame(LANE, MOTORCYCLE, ego)
        reversed_winding = measure_frame(LANE[::-1], MOTORCYCLE[::-1], ego[::-1])
        self.assertEqual(normal, reversed_winding)

    def test_invalid_geometry_rejected(self):
        with self.assertRaisesRegex(ValueError, "polygon area is zero"):
            measure_frame(LANE, [(1, 1), (2, 2), (3, 3)], MOTORCYCLE)
        with self.assertRaisesRegex(ValueError, "convex"):
            measure_frame([(0, 0), (4, 0), (2, 1), (4, 4), (0, 4)], MOTORCYCLE, MOTORCYCLE)

    def test_joined_frames_preserve_sources_and_reject_gaps(self):
        row = {
            "frame": 10, "time_s": 0.5, "lane_polygon": LANE,
            "motorcycle_footprint": MOTORCYCLE,
            "ego_footprint": [(4, 3), (6, 3), (6, 5), (4, 5)],
            "source_refs": {"actor_trace": "trace.jsonl#10", "actor_bounds": "bounds.json#10", "lane_map": "lane.json#A"},
        }
        second = dict(row, frame=11, time_s=0.55)
        values = measure_joined_frames([row, second])
        self.assertEqual([value["frame"] for value in values], [10, 11])
        self.assertEqual(values[0]["source_refs"], row["source_refs"])
        with self.assertRaisesRegex(ValueError, "contiguous"):
            measure_joined_frames([row, dict(second, frame=12)])
        with self.assertRaisesRegex(ValueError, "not increasing"):
            measure_joined_frames([row, dict(second, time_s=0.5)])
        with self.assertRaisesRegex(ValueError, "references"):
            measure_joined_frames([dict(row, source_refs={})])

    def test_saved_only_finalizer_reads_and_writes_bound_frames(self):
        row = {
            "frame": 0, "time_s": 0, "lane_polygon": LANE,
            "motorcycle_footprint": MOTORCYCLE,
            "ego_footprint": [(4, 3), (6, 3), (6, 5), (4, 5)],
            "source_refs": {"actor_trace": "trace.jsonl#0", "actor_bounds": "bounds.json#0", "lane_map": "lane.json#A"},
        }
        with tempfile.TemporaryDirectory() as name:
            source = Path(name) / "source.jsonl"
            output = Path(name) / "measured.jsonl"
            source.write_text(json.dumps(row) + "\n")
            self.assertEqual(finalize(source, output), 1)
            measured = json.loads(output.read_text())
            self.assertEqual(measured["source_refs"], row["source_refs"])
            self.assertAlmostEqual(measured["footprint_surface_gap_m"], 0.5)
            with self.assertRaisesRegex(ValueError, "missing"):
                finalize(Path(name) / "absent.jsonl", output)


if __name__ == "__main__":
    unittest.main()
