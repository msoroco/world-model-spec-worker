import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from saved_measurement import REQUIRED, comparison_projection, measure_saved
from comparison_audit import audit_saved_attempts


class SavedMeasurementTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.case_id = "testing__C104081__NRS-484B-297-6__pedestrian__blocked_intervening"
        self.direction = 1
        self.area_blocked = True
        self._write_fixture()

    def _write_fixture(self):
        survey = {
            "source_kind": "synthetic_fixture", "cell_id": "C104081", "layout": "hill_crest",
            "map_id": "diagnostic-only", "local_to_world": {"x": 100.0, "y": 200.0, "yaw_degrees": 90.0},
            "surface_bounds_local_m": {
                "sidewalk": [0, 60, 4, 6], "intervening_area": [0, 60, 2, 4],
                "designated_bicycle_lane": [0, 60, 0, 2],
                "immediately_adjacent_highway": [0, 60, -3, 4],
            }, "original_sidewalk_direction": self.direction,
            "observed_missing_sidewalk_intervals_local_m": [[20, 34]],
        }
        (self.root / "site-survey.json").write_text(json.dumps(survey) + "\n")
        points = [(10, 5), (17, 5), (18, 1 if self.area_blocked else 3),
                  (25, 1 if self.area_blocked else 3), (36, 1 if self.area_blocked else 3),
                  (37, 5), (50, 5)]
        if self.direction == -1: points.reverse()
        frames, walkers, obstacles, traffic = [], [], [], []
        def world_rect(x0, x1, y0, y1):
            return [[100 - y, 200 + x] for x, y in ((x0, y0), (x0, y1), (x1, y1), (x1, y0))]
        for i, (x, y) in enumerate(points):
            frame = 500 + i
            time = 1.0 + i * .05
            frames.append({"carla_frame": frame, "video_frame": i, "time_s": time})
            vertices = [[100 - (y + dy), 200 + (x + dx)] for dx, dy in
                        ((-.1, -.1), (-.1, .1), (.1, .1), (.1, -.1))]
            walkers.append({"frame": frame, "time_s": time, "body_vertices_world_m": vertices})
            obstacles.append({"frame": frame, "time_s": time,
                "intervening_barrier_present": self.area_blocked,
                "sidewalk_obstruction_end_local_m": 34,
                "sidewalk_obstruction_kind": "impassable_section",
                "sidewalk_obstruction_vertices_world_m": world_rect(20, 34, 4, 6),
                "intervening_barrier_vertices_world_m": world_rect(20, 34, 2, 4) if self.area_blocked else None})
            traffic.append({"frame": frame, "time_s": time, "nearest_traffic_distance_m": 20.0})
        for name, rows in (("video_frames.jsonl", frames), ("pedestrian_history.jsonl", walkers),
                           ("obstruction_history.jsonl", obstacles), ("traffic_history.jsonl", traffic)):
            (self.root / name).write_text("".join(json.dumps(row) + "\n" for row in rows))
        self._seal()

    def _seal(self):
        packet = {"case_id": self.case_id, "source_kind": "synthetic_fixture",
            "capture_context": {"pedestrian_blueprint": "walker.pedestrian.0001",
                                "camera_profile_sha256": "a" * 64,
                                "traffic_plan_sha256": "b" * 64}, "files": {
            name: {"path": name, "sha256": hashlib.sha256((self.root / name).read_bytes()).hexdigest()}
            for name in REQUIRED}}
        (self.root / "source-packet.json").write_text(json.dumps(packet) + "\n")

    def _mutate_json(self, name, callback):
        path = self.root / name
        obj = json.loads(path.read_text())
        callback(obj)
        path.write_text(json.dumps(obj) + "\n")
        self._seal()

    def _mutate_jsonl(self, name, callback):
        path = self.root / name
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        callback(rows)
        path.write_text("".join(json.dumps(row) + "\n" for row in rows))
        self._seal()

    def test_blocked_intervening_lane_use_and_return(self):
        receipt = measure_saved(self.root, self.case_id)
        self.assertTrue(receipt["diagnostic_fixture"])
        self.assertEqual(receipt["observables"]["designated_lane_frames"], [502, 503, 504])
        self.assertEqual(receipt["observables"]["first_sidewalk_return_frame"], 505)
        self.assertEqual(receipt["observables"]["pedestrian_direction"], 1)
        self.assertEqual(receipt["legal_judgment"], "unresolved")

    def test_clear_intervening_avoids_lane(self):
        self.area_blocked = False
        self._write_fixture()
        receipt = measure_saved(self.root, self.case_id)
        self.assertFalse(receipt["observables"]["designated_lane_used"])
        self.assertFalse(receipt["observables"]["intervening_barrier_present"])

    def test_opposite_direction_preserves_sidewalk_direction(self):
        self.direction = -1
        self._write_fixture()
        receipt = measure_saved(self.root, self.case_id)
        self.assertEqual(receipt["observables"]["pedestrian_direction"], -1)
        self.assertEqual(receipt["observables"]["first_sidewalk_return_frame"], 505)

    def test_missing_source_rejected(self):
        (self.root / "traffic_history.jsonl").unlink()
        with self.assertRaisesRegex(ValueError, "missing required saved source"):
            measure_saved(self.root, self.case_id)

    def test_mutated_source_rejected(self):
        with (self.root / "pedestrian_history.jsonl").open("a") as stream:
            stream.write("{}\n")
        with self.assertRaisesRegex(ValueError, "digest mismatch"):
            measure_saved(self.root, self.case_id)

    def test_frame_join_rejected(self):
        self._mutate_jsonl("pedestrian_history.jsonl", lambda rows: rows[3].update(frame=999))
        with self.assertRaisesRegex(ValueError, "join original frame/time"):
            measure_saved(self.root, self.case_id)

    def test_wrong_cadence_rejected(self):
        self._mutate_jsonl("video_frames.jsonl", lambda rows: rows[3].update(time_s=1.165))
        with self.assertRaisesRegex(ValueError, "20 Hz"):
            measure_saved(self.root, self.case_id)

    def test_missing_return_rejected(self):
        def no_return(rows):
            for row in rows[-2:]:
                for vertex in row["body_vertices_world_m"]:
                    vertex[0] = 99.0
        self._mutate_jsonl("pedestrian_history.jsonl", no_return)
        with self.assertRaisesRegex(ValueError, "origin or return"):
            measure_saved(self.root, self.case_id)

    def test_original_label_requires_original_survey(self):
        packet_path = self.root / "source-packet.json"
        packet = json.loads(packet_path.read_text())
        packet["source_kind"] = "original_saved_acquisition"
        packet_path.write_text(json.dumps(packet) + "\n")
        with self.assertRaisesRegex(ValueError, "original Native survey"):
            measure_saved(self.root, self.case_id)

    def test_boolean_barrier_without_geometry_rejected(self):
        self._mutate_jsonl("obstruction_history.jsonl", lambda rows: rows[2].update(intervening_barrier_vertices_world_m=None))
        with self.assertRaisesRegex(ValueError, "observed intervening barrier geometry"):
            measure_saved(self.root, self.case_id)

    def test_obstruction_geometry_extent_mismatch_rejected(self):
        def short_obstruction(rows):
            for row in rows:
                row["sidewalk_obstruction_vertices_world_m"] = [[100 - y, 200 + x] for x, y in
                    ((20, 4), (20, 6), (30, 6), (30, 4))]
        self._mutate_jsonl("obstruction_history.jsonl", short_obstruction)
        with self.assertRaisesRegex(ValueError, "geometry disagrees"):
            measure_saved(self.root, self.case_id)

    def test_comparison_packet_derived_from_saved_sources(self):
        packet = comparison_projection(self.root, self.case_id)
        self.assertEqual(packet["source_kind"], "synthetic_fixture")
        self.assertTrue(packet["designated_lane_used"])
        self.assertEqual(packet["duration_frames"], 7)
        self.assertEqual(packet["traffic_plan_sha256"], "b" * 64)
        self.assertEqual(packet["measurement_sources_sha256"]["traffic_history.jsonl"],
                         hashlib.sha256((self.root / "traffic_history.jsonl").read_bytes()).hexdigest())
        self.assertEqual(packet["legal_judgment"], "unresolved")

    def test_comparison_packet_missing_camera_binding_rejected(self):
        path = self.root / "source-packet.json"
        packet = json.loads(path.read_text())
        packet["capture_context"].pop("camera_profile_sha256")
        path.write_text(json.dumps(packet) + "\n")
        with self.assertRaisesRegex(ValueError, "camera profile"):
            comparison_projection(self.root, self.case_id)

    def test_comparison_audit_rejects_diagnostic_attempts(self):
        plan = {"cases": [{"case_id": self.case_id}], "comparisons": []}
        attempts = {self.case_id: str(self.root)}
        with self.assertRaisesRegex(ValueError, "original saved acquisition"):
            audit_saved_attempts(plan, attempts)

    def test_original_label_requires_surveyed_surfaces(self):
        self._mutate_json("site-survey.json", lambda survey: survey.update(source_kind="original_native_map_survey"))
        path = self.root / "source-packet.json"
        packet = json.loads(path.read_text())
        packet["source_kind"] = "original_saved_acquisition"
        path.write_text(json.dumps(packet) + "\n")
        with self.assertRaisesRegex(ValueError, "observed surface"):
            measure_saved(self.root, self.case_id)

    def test_wrong_direction_rejected(self):
        self._mutate_json("site-survey.json", lambda survey: survey.update(original_sidewalk_direction=-1))
        with self.assertRaisesRegex(ValueError, "original sidewalk direction"):
            measure_saved(self.root, self.case_id)


if __name__ == "__main__":
    unittest.main()
