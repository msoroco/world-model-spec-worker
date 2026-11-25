import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from physical_parking import assess


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value) + "\n")


class PhysicalParkingTests(unittest.TestCase):
    def fixture(self, root):
        source = root / "original-attempt"
        source.mkdir()
        write(source / "inventory.json", {"diagnostic_fixture": True})
        frames = [{"frame": 100 + i, "time_s": i / 20} for i in range(9)]
        write(source / "frame_map.json", {"frames": frames})
        states = ["approaching", "stopping", "parked", "parked", "parked",
                  "parked", "departing", "departing", "departing"]
        write(source / "activity.json", {"samples": [dict(row, state=states[i],
                                                        speed_mps=0 if states[i] == "parked" else 1)
                                                    for i, row in enumerate(frames)]})
        write(source / "vehicle_footprint.json", {"samples": [dict(row,
            polygon_m=[[i, 0], [i + 1, 0], [i + 1, 1], [i, 1]])
            for i, row in enumerate(frames)]})
        (root / "trace.jsonl").write_text("".join(json.dumps(row) + "\n" for row in frames))
        (root / "video_frames.jsonl").write_text("".join(json.dumps(dict(row,
            carla_frame=row["frame"], video_frame=i)) + "\n" for i, row in enumerate(frames)))
        return {"parking_position": "overlap"}, {"max_access_intrusion_area_m2": 2.0}

    def test_met_not_met_and_unverified_are_distinct(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config, measurement = self.fixture(root)
            complete = assess(root, config, measurement)
            self.assertEqual(complete["physical_checks"]["maneuver"]["status"], "met")
            self.assertTrue(complete["maneuver_completed"])
            activity_path = root / "original-attempt/activity.json"
            activity = json.loads(activity_path.read_text())
            activity["samples"][-1]["state"] = "parked"
            activity["samples"][-2]["state"] = "parked"
            activity["samples"][-3]["state"] = "parked"
            write(activity_path, activity)
            incomplete = assess(root, config, measurement)
            self.assertEqual(incomplete["physical_checks"]["maneuver"]["status"], "not_met")
            self.assertFalse(incomplete["maneuver_completed"])
            (root / "trace.jsonl").unlink()
            missing = assess(root, config, measurement)
            self.assertEqual(missing["physical_checks"]["maneuver"]["status"], "unverified")
            self.assertFalse(missing["maneuver_completed"])


if __name__ == "__main__":
    unittest.main()
