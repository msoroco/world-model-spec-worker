import copy
import hashlib
import importlib.util
import json
import math
import pathlib
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("c133321_native_capture", HERE / "native_capture.py")
CAPTURE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CAPTURE)
from test_roundabout import topology_source


class Settings:
    synchronous_mode = False
    fixed_delta_seconds = None


class Actor:
    def __init__(self, actor_id, type_id):
        self.id = actor_id
        self.type_id = type_id
        self.is_alive = True

    def destroy(self):
        self.is_alive = False


class World:
    def __init__(self):
        self.settings = Settings()
        self.frame = 100

    def get_settings(self):
        return copy.copy(self.settings)

    def apply_settings(self, settings):
        self.settings = copy.copy(settings)

    def tick(self):
        self.frame += 1
        return self.frame

    def get_snapshot(self):
        class Timestamp:
            elapsed_seconds = 0
        class Snapshot:
            frame = 0
            timestamp = Timestamp()
        result = Snapshot()
        result.frame = self.frame
        result.timestamp.elapsed_seconds = self.frame * .05
        return result


class Operator:
    def __init__(self, map_bytes, wrong_identity=False):
        self.raw = map_bytes
        self.topology = topology_source()
        self.topology["map_sha256"] = hashlib.sha256(map_bytes).hexdigest()
        self.wrong_identity = wrong_identity
        self.actor = None

    def map_bytes(self, world):
        return self.raw

    def readback_map(self, world):
        return self.topology

    def spawn_vehicle(self, world, blueprint, position):
        self.actor = Actor(17, blueprint)
        return self.actor

    def actor_state(self, actor):
        return {"x": -5, "y": -2, "heading_x": 1, "heading_y": 0}

    def apply_control(self, actor, control):
        if not -1 <= control["steer"] <= 1:
            raise AssertionError("invalid Native steering")

    def observe(self, world, actor, frame):
        index = frame - 101
        section = "entry" if index < 200 else "ring" if index <= 600 else "exit"
        if section == "entry":
            x, y = -4.0 + 4.0 * index / 199.0, -2.0
        elif section == "ring":
            angle = -math.pi / 2.0 + math.pi * (index - 200) / 400.0
            x, y = 2.0 * math.cos(angle), 2.0 * math.sin(angle)
        else:
            x, y = -4.0 * (index - 601) / 298.0, 2.0
        return {"source_frame_id": frame,
                "actor_id": "wrong" if self.wrong_identity else str(actor.id),
                "section": section, "lane_id": "lane-inner", "heading_x": -1, "heading_y": 0,
                "x": x, "y": y, "z": 0.0, "speed_mps": 1.0,
                "body_vertices_m": [[x-1, y-1, 0], [x-1, y+1, 0],
                                    [x+1, y+1, 0], [x+1, y-1, 0]]}

    def cameras(self, world, actor, views, review):
        return {name: lambda frame: b"fixture-image" for name in views}, []


def survey(raw):
    assignment = CAPTURE.ASSIGNMENT
    return {"source_kind": "reviewed_original_native_roundabout",
            "assignment_id": assignment, "cell_id": "C133321",
            "jurisdiction": "Las Vegas, Nevada", "intended_departure": "opposite_direction",
            "entry_id": "south-entry", "exit_id": "north-exit",
            "vehicle_blueprint": "vehicle.fixture",
            "map_sha256": hashlib.sha256(raw).hexdigest(),
            "controller_sha256": hashlib.sha256((HERE / "runner.py").read_bytes()).hexdigest(),
            "weather_sha256": "c" * 64,
            "camera_plan_sha256": "d" * 64,
            "lane_roles": ["left", "outer"],
            "case_ids": [assignment + "__" + name for name in CAPTURE.CASES]}


class TestNativeCapture(unittest.TestCase):
    def test_source_gated_full_capture_and_restore(self):
        raw = b"fixture-OpenDRIVE-map"
        world = World()
        operator = Operator(raw)
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            path = root / "survey.json"
            path.write_text(json.dumps(survey(raw)) + "\n")
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            result = CAPTURE.capture(world, case_id=CAPTURE.ASSIGNMENT + "__left_lane_u_turn",
                                     survey_path=path, survey_sha256=digest,
                                     output=root / "attempt", operator=operator)
            self.assertEqual(result["source_frame_count"], 900)
            self.assertTrue(result["requested_lane_observed"])
            self.assertTrue((root / "attempt" / "inventory.json").is_file())
            self.assertEqual(len(list((root / "attempt" / "cameras" / "overview").iterdir())), 900)
            self.assertFalse(operator.actor.is_alive)
            self.assertFalse(world.settings.synchronous_mode)

    def test_unreviewed_map_rejected_before_world_change(self):
        raw = b"fixture-OpenDRIVE-map"
        world = World()
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            path = root / "survey.json"
            path.write_text(json.dumps(survey(raw)) + "\n")
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            with self.assertRaisesRegex(ValueError, "loaded map differs"):
                CAPTURE.capture(world, case_id=CAPTURE.ASSIGNMENT + "__left_lane_u_turn",
                                survey_path=path, survey_sha256=digest,
                                output=root / "attempt", operator=Operator(b"different"))
            self.assertFalse(world.settings.synchronous_mode)
            self.assertFalse((root / "attempt").exists())
