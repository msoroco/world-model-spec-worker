import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from native_source_packet import NativeSourcePacket, STREAMS, capture_constructed_sources
from test_native_walking import CARLA, ROUTE, Walker, World


class PacketTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.survey = self.root / "survey.json"
        self.survey.write_text(json.dumps(self.survey_data("source-map")) + "\n")
        self.case = "testing__C104081__NRS-484B-297-6__pedestrian__clear_intervening"
        self.packet = NativeSourcePacket(self.case, self.survey,
                                         hashlib.sha256(self.survey.read_bytes()).hexdigest(),
                                         "a" * 64, "b" * 64, "walker.pedestrian.0001")

    @staticmethod
    def survey_data(map_id):
        surfaces = {name: {"surveyed": True} for name in (
            "sidewalk", "intervening_area", "designated_bicycle_lane",
            "immediately_adjacent_highway")}
        return {"source_kind": "original_native_map_survey", "cell_id": "C104081",
                "layout": "hill_crest", "map_id": map_id, "surfaces": surfaces,
                "local_to_world": {"x": 0, "y": 0, "yaw_degrees": 0}}

    def readbacks(self, frame, time_s, index):
        return {
            "video_frames.jsonl": {"carla_frame": frame, "video_frame": index, "time_s": time_s},
            "pedestrian_history.jsonl": {"frame": frame, "time_s": time_s,
                                           "body_vertices_world_m": [[0, 0], [0, 1], [1, 1], [1, 0]]},
            "obstruction_history.jsonl": {"frame": frame, "time_s": time_s, "obstacle_id": 7},
            "traffic_history.jsonl": {"frame": frame, "time_s": time_s, "nearest_traffic_distance_m": 20.0},
        }

    def test_seals_900_original_source_ticks_with_hashes(self):
        first = self.readbacks(100, 5.0, 0)
        self.packet.observe({"frame": 100, "time_s": 5.0}, first)
        first["pedestrian_history.jsonl"]["body_vertices_world_m"][0][0] = 99
        for i in range(1, 900):
            self.packet.observe({"frame": 100 + i, "time_s": 5 + i / 20},
                                self.readbacks(100 + i, 5 + i / 20, i))
        packet = self.packet.seal(self.root / "attempt")
        self.assertEqual(packet["source_kind"], "original_saved_acquisition")
        self.assertEqual(set(packet["files"]), {"site-survey.json", *STREAMS})
        for name, binding in packet["files"].items():
            self.assertEqual(binding["sha256"], hashlib.sha256((self.root / "attempt" / name).read_bytes()).hexdigest())
        first_saved = json.loads((self.root / "attempt" / "pedestrian_history.jsonl").read_text().splitlines()[0])
        self.assertEqual(first_saved["body_vertices_world_m"][0][0], 0)

    def test_rejects_wrong_join_and_incomplete_capture(self):
        rows = self.readbacks(100, 5.0, 0)
        rows["traffic_history.jsonl"]["frame"] = 101
        with self.assertRaisesRegex(ValueError, "join measured"):
            self.packet.observe({"frame": 100, "time_s": 5.0}, rows)
        self.packet.observe({"frame": 100, "time_s": 5.0}, self.readbacks(100, 5.0, 0))
        with self.assertRaisesRegex(ValueError, "continuity"):
            self.packet.observe({"frame": 102, "time_s": 5.1}, self.readbacks(102, 5.1, 1))
        with self.assertRaisesRegex(ValueError, "900"):
            self.packet.seal(self.root / "attempt")

    def test_rejects_changed_survey_and_foreign_case(self):
        with self.assertRaisesRegex(ValueError, "digest"):
            NativeSourcePacket(self.case, self.survey, "0" * 64,
                               "a" * 64, "b" * 64, "walker.pedestrian.0001")
        with self.assertRaisesRegex(ValueError, "wrong exact"):
            NativeSourcePacket("foreign", self.survey, hashlib.sha256(self.survey.read_bytes()).hexdigest(),
                               "a" * 64, "b" * 64, "walker.pedestrian.0001")
        incomplete = self.survey_data("source-map")
        del incomplete["surfaces"]["designated_bicycle_lane"]
        self.survey.write_text(json.dumps(incomplete) + "\n")
        with self.assertRaisesRegex(ValueError, "required observed surface"):
            NativeSourcePacket(self.case, self.survey, hashlib.sha256(self.survey.read_bytes()).hexdigest(),
                               "a" * 64, "b" * 64, "walker.pedestrian.0001")

    def test_constructed_route_collects_exact_tick_readbacks(self):
        self.survey.write_text(json.dumps(self.survey_data("reviewed-map")) + "\n")
        constructed = {"case_id": self.case, "site_map_id": "reviewed-map",
                       "survey_sha256": hashlib.sha256(self.survey.read_bytes()).hexdigest(),
                       "route_local_xy_m": [list(point) for point in ROUTE]}
        walker = Walker()
        seen = []
        def reader(sample):
            seen.append(sample["frame"])
            return self.readbacks(sample["frame"], sample["time_s"], len(seen) - 1)
        packet = capture_constructed_sources(
            World(walker), walker, CARLA, constructed, self.survey, self.case,
            reader, self.root / "captured", camera_profile_sha256="a" * 64,
            traffic_plan_sha256="b" * 64,
            pedestrian_blueprint="walker.pedestrian.0001", speed_m_s=2)
        self.assertEqual(len(seen), 900)
        self.assertEqual(seen, list(range(101, 1001)))
        self.assertEqual(packet["case_id"], self.case)
        self.assertEqual(walker.controls[-1]["speed"], 0)


if __name__ == "__main__":
    unittest.main()
