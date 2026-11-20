import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest


MODULE = Path(__file__).resolve().parents[1] / "alley_measurement.py"
spec = importlib.util.spec_from_file_location("alley_measurement", MODULE)
measure = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = measure
spec.loader.exec_module(measure)


def box(x, y, half=0.2):
    return [[x-half, y-half], [x+half, y-half], [x+half, y+half], [x-half, y+half]]


def write_rows(root, name, rows):
    (root / name).write_text("".join(json.dumps(row) + "\n" for row in rows))


class OriginalSourceTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.footprints = [{"frame": i+10, "time_s": i*0.05,
                            "ego_id": 1, "pedestrian_id": 2, "property_id": 3,
                            "ego_corners": box(i*0.25, 0),
                            "pedestrian_corners": box(1, 1),
                            "property_corners": box(1, -1)} for i in range(3)]
        self.write()

    def write(self):
        write_rows(self.root, "participant_footprints.jsonl", self.footprints)
        write_rows(self.root, "ego_motion.jsonl", [{"frame": x["frame"], "time_s": x["time_s"],
                   "ego_id": 1, "velocity_xy": [5, 0], "acceleration_xy": [-2, 0],
                   "forward_xy": [1, 0]} for x in self.footprints])
        write_rows(self.root, "trace.jsonl", [{"frame": x["frame"], "time_s": x["time_s"]} for x in self.footprints])
        write_rows(self.root, "video_frames.jsonl", [{"video_frame": i, "carla_frame": x["frame"], "time_s": x["time_s"]} for i, x in enumerate(self.footprints)])

    def test_measures_original_synchronized_footprints(self):
        result = measure.measure(self.root)
        self.assertEqual(result["frame_count"], 3)
        self.assertAlmostEqual(result["maximum_observed_speed_mps"], 5)
        self.assertAlmostEqual(result["observations"][0]["braking_distance_proxy_m"], 6.25)
        self.assertAlmostEqual(result["observations"][0]["pedestrian_time_to_station_proxy_s"], .2)
        self.assertGreater(result["minimum_pedestrian_gap_m"], 0)
        self.assertEqual(len(result["source_sha256"]), 4)

    def test_rejects_missing_and_unjoined_sources(self):
        (self.root / "participant_footprints.jsonl").unlink()
        with self.assertRaisesRegex(ValueError, "Missing required original source"):
            measure.measure(self.root)
        self.write()
        self.footprints[1]["time_s"] = 0.06
        write_rows(self.root, "participant_footprints.jsonl", self.footprints)
        with self.assertRaisesRegex(ValueError, "join failed"):
            measure.measure(self.root)

    def test_rejects_changed_participant_identity(self):
        self.footprints[2]["pedestrian_id"] = 4
        self.write()
        with self.assertRaisesRegex(ValueError, "identity missing or changed"):
            measure.measure(self.root)

    def test_motion_source_is_required_and_no_braking_stays_unknown(self):
        (self.root / "ego_motion.jsonl").unlink()
        with self.assertRaisesRegex(ValueError, "Missing required original source"):
            measure.measure(self.root)
        self.write()
        rows = [json.loads(line) for line in (self.root / "ego_motion.jsonl").read_text().splitlines()]
        for row in rows:
            row["acceleration_xy"] = [0, 0]
        write_rows(self.root, "ego_motion.jsonl", rows)
        result = measure.measure(self.root)
        self.assertIsNone(result["observations"][0]["braking_distance_proxy_m"])


if __name__ == "__main__":
    unittest.main()
