"""Independent numeric checks for raw parking geometry and source custody."""
import hashlib
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from parking_measurement import load_original, measure_frame, measure_sequence


CONTEXT = {"road_edge_xy_m": [[-20, 0], [20, 0]],
           "roadway_polygon_xy_m": [[-20, -5], [20, -5], [20, 5], [-20, 5]],
           "lawful_travel_xy": [1, 0],
           "lawful_direction_source": "reviewed one-way regulation pending",
           "road_edge_source": "source-reviewed roadway edge pending",
           "roadway_source": "source-reviewed roadway polygon pending"}


def frame(number, forward=(1, 0), center=(0, 1)):
    x, y = center
    return {"frame": number, "time_s": number / 20,
            "vehicle_forward_xy": list(forward),
            "body_vertices_xy_m": [[x - 1, y - .4], [x + 1, y - .4],
                                    [x + 1, y + .4], [x - 1, y + .4]]}


class ParkingGeometryTests(unittest.TestCase):
    def test_parallel_and_lawful_heading_are_separate_measurements(self):
        lawful = measure_frame(frame(0), CONTEXT)
        reverse = measure_frame(frame(0, forward=(-1, 0)), CONTEXT)
        angled = measure_frame(frame(0, forward=(.8660254038, .5)), CONTEXT)
        self.assertAlmostEqual(lawful["parallel_deviation_deg"], 0)
        self.assertAlmostEqual(reverse["parallel_deviation_deg"], 0)
        self.assertAlmostEqual(reverse["lawful_heading_deviation_deg"], 180)
        self.assertAlmostEqual(angled["parallel_deviation_deg"], 30, places=5)
        self.assertEqual(lawful["body_corners_inside_roadway"], 4)
        self.assertEqual(measure_frame(frame(0, center=(0, 4.9)), CONTEXT)
                         ["body_corners_inside_roadway"], 2)

    def test_nearest_edge_and_source_context_are_required(self):
        context = {**CONTEXT, "road_edge_xy_m": [[-20, 0], [0, 0], [0, 20]],
                   "lawful_travel_xy": [0, 1]}
        observed = measure_frame(frame(0, forward=(0, 1), center=(1, 10)), context)
        self.assertAlmostEqual(observed["center_edge_distance_m"], 1)
        self.assertAlmostEqual(observed["parallel_deviation_deg"], 0)
        bad = {**context, "lawful_travel_xy": [1, 0]}
        with self.assertRaisesRegex(ValueError, "inconsistent"):
            measure_frame(frame(0, forward=(0, 1), center=(1, 10)), bad)

    def test_original_hash_and_frame_order(self):
        rows = [frame(10), frame(11), frame(12)]
        with TemporaryDirectory() as directory:
            path = Path(directory) / "parking-body-history.jsonl"
            path.write_text("".join(json.dumps(row) + "\n" for row in rows))
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            observed = load_original(path, digest, CONTEXT)
            self.assertEqual(len(observed["frames"]), 3)
            self.assertEqual(observed["legal_judgment"], "unresolved")
            path.write_bytes(path.read_bytes() + b"changed\n")
            with self.assertRaisesRegex(ValueError, "hash changed"):
                load_original(path, digest, CONTEXT)
        with self.assertRaisesRegex(ValueError, "frame/time order"):
            measure_sequence([frame(1), frame(1)], CONTEXT)


if __name__ == "__main__":
    unittest.main()
