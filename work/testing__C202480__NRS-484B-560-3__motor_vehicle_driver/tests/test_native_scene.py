"""Exercise real builder calls with fake Native world and both approaches."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
from native_scene import create, inspect
from native_camera import VIEWS
from runner import retain_site_sources


class Actor:
    def __init__(self):
        self.destroyed = False

    def destroy(self):
        self.destroyed = True


class Map:
    def __init__(self, text):
        self.text = text

    def to_opendrive(self):
        return self.text

    def get_all_landmarks(self):
        return [type("Landmark", (), {"id": "stop-rail-1"})()]


class Library:
    def find(self, name):
        if not name.startswith("vehicle."):
            raise ValueError("non-vehicle blueprint")
        return name


class World:
    def __init__(self, text):
        self.map = Map(text)
        self.calls = []
        self.actors = []
        self.fail_second = False

    def get_map(self):
        return self.map

    def get_blueprint_library(self):
        return Library()

    def try_spawn_actor(self, blueprint, transform):
        self.calls.append((blueprint, transform))
        if self.fail_second and len(self.calls) == 2:
            return None
        actor = Actor()
        self.actors.append(actor)
        return actor


class NativeSceneTests(unittest.TestCase):
    def setUp(self):
        private = ROOT / ".runtime-work"
        private.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=private)
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.plan = HERE / "case-plan.json"
        self.cases = json.loads(self.plan.read_text())["cases"]
        self.opendrive = "<OpenDRIVE><road id='fixture'/></OpenDRIVE>"

    def packet(self, case, direction=1):
        sources = {}
        for name in ("opendrive", "crossing_authority", "lane_markings",
                     "highway_boundary", "right_side_constraints", "camera_poses"):
            path = self.folder / (name + ".txt")
            path.write_text(self.opendrive if name == "opendrive" else
                            "synthetic diagnostic " + name + "\n", encoding="utf-8")
            sources[name] = {"path": path.name,
                             "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        count = case["marked_highway_lane_count"]
        right_y, left_y = (-4., -1.) if direction == 1 else (4., 1.)
        stop_x, rail_x = (0., 10.) if direction == 1 else (0., -10.)
        slots = {"right": {"x_m": -10. * direction, "y_m": right_y},
                 "left": {"x_m": -10. * direction, "y_m": left_y}}
        ego = "right" if case["subject_lateral_plan"] == "rightmost_feasible" else "left"
        companion = ("left" if ego == "right" else "right") if (
            case["traffic_arrangement"] == "two_queues") else None
        packet = {"format": "c202480-reviewed-crossing-site-v1",
                  "case_id": case["case_id"], "sources": sources,
                  "stopping_required_context": "reviewed_crossing_instruction",
                  "sign_landmark_id": "stop-rail-1", "rail_crossing_map_ref": "rail-1",
                  "marked_lanes": [{"lane_id": i, "direction": (direction if i < count//2 else -direction),
                                    "marking_source_ref": "lane_markings.txt"}
                                   for i in range(count)],
                  "approach_direction": direction,
                  "stop_line_x_m": stop_x, "rail_line_x_m": rail_x,
                  "highway_right_y_m": -6. * direction,
                  "highway_left_y_m": 6. * direction,
                  "slots": slots, "ego_slot": ego,
                  "rightmost_feasible_slot": "right", "companion_slot": companion,
                  "vehicle_blueprints": {"ego": "vehicle.test.ego",
                                         "companion": "vehicle.test.companion"}}
        packet["cameras"] = [
            {"name": name, "width": width, "height": height,
             "attachment": "ego" if name == "driver_reference" else "world",
             "pose_source_citation": "synthetic fixture camera pose",
             "reviewer": "CPU fixture", "location_xyz_m": [0., 0., 2.],
             "rotation_rpy_deg": [0., 0., 0.], "fov_deg": 90.}
            for name, width, height in VIEWS]
        documents = {
            "crossing_authority": {"governs_crossing": True,
                                   "sign_landmark_id": packet["sign_landmark_id"],
                                   "rail_crossing_map_ref": packet["rail_crossing_map_ref"],
                                   "stop_line_x_m": stop_x, "rail_line_x_m": rail_x},
            "lane_markings": {"marked_lanes": packet["marked_lanes"]},
            "highway_boundary": {"highway_right_y_m": packet["highway_right_y_m"],
                                 "highway_left_y_m": packet["highway_left_y_m"]},
            "right_side_constraints": {"slots": slots,
                                       "rightmost_feasible_slot": "right"},
            "camera_poses": {"cameras": packet["cameras"]},
        }
        for name, document in documents.items():
            source = self.folder / (name + ".txt")
            source.write_text(json.dumps(document, sort_keys=True) + "\n", encoding="utf-8")
            sources[name]["sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
        path = self.folder / "site-packet.json"
        path.write_text(json.dumps(packet, indent=2) + "\n", encoding="utf-8")
        return path, packet

    def test_all_six_cases_spawn_and_close_in_both_directions(self):
        for case in self.cases:
            for direction in (1, -1):
                with self.subTest(case=case["case_id"], direction=direction):
                    path, packet = self.packet(case, direction)
                    world = World(self.opendrive)
                    scene = create(world, path, self.plan, case["case_id"],
                                   lambda x, y, z, yaw: (x, y, z, yaw))
                    expected = 2 if case["traffic_arrangement"] == "two_queues" else 1
                    self.assertEqual(len(world.calls), expected)
                    self.assertEqual(world.calls[0][1][3], 0 if direction == 1 else 180)
                    self.assertEqual(world.calls[0][1][1], packet["slots"][packet["ego_slot"]]["y_m"])
                    scene.close()
                    self.assertTrue(all(actor.destroyed for actor in world.actors))

    def test_changed_site_source_or_map_rejected(self):
        case = self.cases[0]
        path, _ = self.packet(case)
        (self.folder / "lane_markings.txt").write_text("changed\n")
        with self.assertRaisesRegex(ValueError, "site source hash differs"):
            inspect(path, self.plan, case["case_id"])
        path, _ = self.packet(case)
        with self.assertRaisesRegex(ValueError, "OpenDRIVE differs"):
            create(World("<OpenDRIVE>other</OpenDRIVE>"), path, self.plan,
                   case["case_id"], lambda *args: args)

    def test_spawn_failure_destroys_first_actor(self):
        case = next(item for item in self.cases if item["traffic_arrangement"] == "two_queues")
        path, _ = self.packet(case)
        world = World(self.opendrive)
        world.fail_second = True
        with self.assertRaisesRegex(ValueError, "spawn failed"):
            create(world, path, self.plan, case["case_id"], lambda *args: args)
        self.assertTrue(world.actors[0].destroyed)

    def test_resealed_marking_source_still_must_match_case(self):
        case = self.cases[0]
        path, packet = self.packet(case)
        marking = self.folder / "lane_markings.txt"
        marking.write_text(json.dumps({"marked_lanes": []}) + "\n")
        packet["sources"]["lane_markings"]["sha256"] = hashlib.sha256(marking.read_bytes()).hexdigest()
        path.write_text(json.dumps(packet) + "\n")
        with self.assertRaisesRegex(ValueError, "marked highway lanes differ"):
            inspect(path, self.plan, case["case_id"])

    def test_site_packet_and_source_bytes_retained_for_saved_processing(self):
        case = self.cases[0]
        path, _ = self.packet(case)
        attempt = self.folder / "attempt"
        attempt.mkdir()
        retained = retain_site_sources(attempt, path, self.plan, case["case_id"])
        self.assertEqual(retained, attempt / "site/packet.json")
        (self.folder / "lane_markings.txt").write_text("changed after Native\n")
        inspect(retained, self.plan, case["case_id"])


if __name__ == "__main__":
    unittest.main()
