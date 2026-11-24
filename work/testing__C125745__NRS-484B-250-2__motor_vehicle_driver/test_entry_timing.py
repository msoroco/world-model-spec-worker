import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from entry_timing import measure


class TimingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "trace.json"
        self.case = "testing__C125745__NRS-484B-250-2__motor_vehicle_driver__entry_inside"
        def body(x):
            return [[x, 4], [x+1, 4], [x+1, 5], [x, 5]]
        self.packet = {"case_id": self.case,
                       "map_source_sha256": "map", "intersection_source_sha256": "junction",
                       "highway_source_sha256": "highway", "device_source_sha256": "device",
                       "ego_actor_id": 11, "other_actor_id": 12,
                       "ego_road_id": 3, "other_road_id": 4,
                       "intersection_polygon_xy_m": [[0, 0], [10, 0], [10, 10], [0, 10]],
                       "frames": []}
        for i in range(5):
            self.packet["frames"].append({"frame": 100+i, "time_s": i*.05,
                "ego": {"id": 11, "road_id": 3, "body_corners_xy_m": body(-2+i)},
                "other": {"id": 12, "road_id": 4,
                          "body_corners_xy_m": body(-3+i)}})

    def run_packet(self, packet=None):
        self.path.write_text(json.dumps(packet or self.packet)+"\n")
        return measure(self.path, hashlib.sha256(self.path.read_bytes()).hexdigest(),
                       case_id=self.case, expected_frames=5)

    def test_first_footprint_entry_brackets_and_difference(self):
        result = self.run_packet()
        self.assertEqual(result["entry_brackets"]["ego"]["entry_frame"], 101)
        self.assertEqual(result["entry_brackets"]["other"]["entry_frame"], 102)
        self.assertAlmostEqual(result["intersection_entry_time_difference_s"], -.05)
        self.assertEqual(result["approximately_same_time"], "undetermined")

    def test_rejects_stale_source_and_wrong_case(self):
        self.path.write_text(json.dumps(self.packet)+"\n")
        with self.assertRaisesRegex(ValueError, "source hash"):
            measure(self.path, "0"*64, case_id=self.case, expected_frames=5)
        with self.assertRaisesRegex(ValueError, "case identity"):
            measure(self.path, hashlib.sha256(self.path.read_bytes()).hexdigest(),
                    case_id="other-case", expected_frames=5)

    def test_rejects_frame_gap_and_same_highway(self):
        packet = copy.deepcopy(self.packet)
        packet["frames"][2]["frame"] += 1
        with self.assertRaisesRegex(ValueError, "frame discontinuity"):
            self.run_packet(packet)
        packet = copy.deepcopy(self.packet)
        packet["other_road_id"] = 3
        with self.assertRaisesRegex(ValueError, "different source highways"):
            self.run_packet(packet)

    def test_rejects_missing_entry_and_unbracketed_start(self):
        packet = copy.deepcopy(self.packet)
        for row in packet["frames"]:
            row["other"]["body_corners_xy_m"] = [[-5, 4],[-4, 4],[-4, 5],[-5, 5]]
        with self.assertRaisesRegex(ValueError, "both original intersection entries"):
            self.run_packet(packet)
        packet = copy.deepcopy(self.packet)
        packet["frames"][0]["ego"]["body_corners_xy_m"] = [[1,4],[2,4],[2,5],[1,5]]
        with self.assertRaisesRegex(ValueError, "unbracketed"):
            self.run_packet(packet)


if __name__ == "__main__":
    unittest.main()
