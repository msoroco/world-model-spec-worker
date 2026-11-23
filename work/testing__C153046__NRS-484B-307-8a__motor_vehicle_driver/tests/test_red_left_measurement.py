import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from red_left_measurement import measure, validate_site


class RedLeftMeasurementTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        sources = {}
        for name in ("opendrive", "official_signal", "one_way_routes", "stop_reference"):
            path = self.root / (name + ".txt")
            path.write_text(name)
            sources[name] = {"path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                             "citation": "reviewed-" + name, "reviewer": "fixture"}
        self.packet = {"format": "c153046-red-left-site-v1", "reviewer": "fixture", "sources": sources,
                       "approach_one_way": True, "receiving_one_way_to_left": True,
                       "approach_direction_xy": [1, 0], "receiving_direction_xy": [0, 1],
                       "approach_reference_xy": [0, 0],
                       "approach_lane_centers_xy": {"inner": [0, 0], "left": [0, 3.5]},
                       "extreme_left_lane_id": "left",
                       "signal": {"official": True, "head_configuration": "steady_red_alone", "native_actor_id": "7"},
                       "stop_reference": {"kind": "marked_crosswalk", "hierarchy_reviewed": True, "point_xy": [10, 0]}}
        self.packet_path = self.root / "site.json"
        self.write_packet()

    def write_packet(self):
        self.packet_path.write_text(json.dumps(self.packet))

    def trace(self, frames=None):
        if frames is None:
            frames = [(0, 0.00, 7.0, 0.0, False), (1, 0.05, 8.0, 0.0, False),
                      (2, 0.10, 10.0, 2.0, True)]
        packet_sha = hashlib.sha256(self.packet_path.read_bytes()).hexdigest()
        rows = []
        for index, time_s, x, speed, conflict in frames:
            rows.append({"case_id": "case-a", "source_packet_sha256": packet_sha,
                         "native_frame": {"origin": "native_world_snapshot", "frame": index,
                                          "time_s": time_s, "signal_actor_id": "7",
                                          "signal_state": "steady_red_alone",
                                          "ego": {"lane_id": "left", "speed_m_s": speed,
                                                  "body_vertices_xy": [[x-1, 2], [x+1, 2], [x+1, 4], [x-1, 4]]},
                                          "directed_participants": [{"native_actor_id": "8", "source_citation": "fixture-route",
                                                                     "conflict_zone_occupied": conflict}]}})
        path = self.root / "trace.jsonl"
        path.write_text("\n".join(json.dumps(row) for row in rows) + "\n")
        return path

    def test_source_bound_entry_and_conflict(self):
        result = measure(self.packet_path, self.trace(), "case-a")
        self.assertEqual(result["first_pre_entry_stop_frame"], 0)
        self.assertEqual(result["first_entry_frame"], 2)
        self.assertEqual(result["red_conflict_entry_frames"], [2])
        self.assertEqual(result["legal_judgment"], "unresolved")

    def test_reject_wrong_receiving_direction(self):
        self.packet["receiving_direction_xy"] = [0, -1]
        self.write_packet()
        with self.assertRaisesRegex(ValueError, "does not turn left"):
            validate_site(self.packet_path)

    def test_reject_wrong_left_lane(self):
        self.packet["extreme_left_lane_id"] = "inner"
        self.write_packet()
        with self.assertRaisesRegex(ValueError, "extreme-left"):
            validate_site(self.packet_path)

    def test_reject_source_mutation(self):
        (self.root / "official_signal.txt").write_text("altered")
        with self.assertRaisesRegex(ValueError, "changed"):
            validate_site(self.packet_path)

    def test_reject_missing_participant_inventory(self):
        path = self.trace()
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        del rows[1]["native_frame"]["directed_participants"]
        path.write_text("\n".join(json.dumps(row) for row in rows) + "\n")
        with self.assertRaisesRegex(ValueError, "inventory missing"):
            measure(self.packet_path, path, "case-a")

    def test_reject_missing_or_irregular_frame(self):
        with self.assertRaisesRegex(ValueError, "20 Hz"):
            measure(self.packet_path, self.trace([(0, 0, 7, 0, False), (2, .1, 10, 2, True)]), "case-a")
        with self.assertRaisesRegex(ValueError, "20 Hz"):
            measure(self.packet_path, self.trace([(0, 0, 7, 0, False), (1, .1, 10, 2, True)]), "case-a")

    def test_reject_missing_body_or_case_join(self):
        path = self.trace()
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        rows[0]["native_frame"]["ego"]["body_vertices_xy"] = []
        path.write_text("\n".join(json.dumps(row) for row in rows) + "\n")
        with self.assertRaisesRegex(ValueError, "full original ego body"):
            measure(self.packet_path, path, "case-a")
        with self.assertRaisesRegex(ValueError, "case or source"):
            measure(self.packet_path, self.trace(), "case-b")
