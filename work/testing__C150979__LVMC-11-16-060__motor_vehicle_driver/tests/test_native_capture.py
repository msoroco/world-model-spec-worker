import copy
import hashlib
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import native_capture as capture
import speed_delivery as speed


class Settings:
    synchronous_mode = False
    fixed_delta_seconds = None


class Actor:
    id = 17
    is_alive = True
    type_id = "vehicle.tesla.model3"

    def __init__(self):
        self.velocity = types.SimpleNamespace(x=10.0, y=0.0, z=0.0)

    def get_velocity(self):
        return self.velocity

    def apply_control(self, control):
        self.control = control

    def destroy(self):
        self.is_alive = False


class Map:
    name = "ReviewedTown"

    def get_waypoint(self, location, project_to_road=False):
        return types.SimpleNamespace(road_id=3, lane_id=1, transform="start")


class World:
    def __init__(self):
        self.settings = Settings()
        self.frame = 100
        self.actor = None

    def get_settings(self):
        return copy.copy(self.settings)

    def apply_settings(self, settings):
        self.settings = copy.copy(settings)

    def get_map(self):
        return Map()

    def get_blueprint_library(self):
        return types.SimpleNamespace(find=lambda name: name)

    def try_spawn_actor(self, blueprint, transform):
        self.actor = Actor()
        return self.actor

    def tick(self):
        self.frame += 1
        return self.frame

    def get_snapshot(self):
        return types.SimpleNamespace(frame=self.frame,
            timestamp=types.SimpleNamespace(elapsed_seconds=self.frame * .05))


class Operator:
    def __init__(self, map_bytes):
        self.raw = map_bytes

    def map_bytes(self, world):
        return self.raw

    def sign_readback(self, world):
        return site(self.raw)["signs"]

    def cameras(self, world, actor, views):
        return {view: lambda frame: b"fixture-image" for view in views}, []

    def observe(self, world, actor, frame, packet):
        index = frame - 101
        station = index * .4
        row = {"source_frame_id": frame, "actor_id": actor.id, "ego_alive": True,
               "road_id": 3, "lane_id": 1, "route_station_m": station,
               "speed_mps": 10.0, "x": station, "y": 0.0, "z": 0.0,
               "heading_x": 1.0, "heading_y": 0.0,
               "body_vertices_m": [[station-1, -1, 0], [station-1, 1, 0],
                                   [station+1, 1, 0], [station+1, -1, 0]]}
        if station >= 40:
            row.update(sign_id="S1", sign_value_mph=25)
        return row


def site(raw):
    sign = {"sign_id": "S1", "value_mph": 25, "source": "review/sign",
            "direction": "route", "governed_start_station_m": 40.0,
            "governed_end_station_m": 500.0, "time_conditions_source": "review/time"}
    return {"source_kind": "reviewed_original_native_speed_site",
            "assignment_id": speed.ASSIGNMENT, "law_id": speed.LAW,
            "cell_id": "C150979", "map_sha256": hashlib.sha256(raw).hexdigest(),
            "map_name": "ReviewedTown", "municipal_jurisdiction_source": "review/municipal",
            "covered_street_source": "review/street", "road_kind": "street",
            "route": {"road_id": 3, "lane_id": 1, "one_way_source": "map/lane-inventory",
                      "spawn_station_m": 0.0, "end_station_m": 500.0},
            "start_xyz": [0.0, 0.0, 0.0],
            "sign_inventory_complete_source": "review/route",
            "sign_inventory_extent_m": [0.0, 500.0],
            "title_posting_review_source": "review/title-pending",
            "signs": [sign],
            "controller_sha256": speed.sha256(HERE / "speed_delivery.py"),
            "case_ids": [speed.ASSIGNMENT + "__" + key for key in
                         ("same25_below", "same25_at", "same25_above", "different35")]}


class NativeCaptureTest(unittest.TestCase):
    def setUp(self):
        self.prior_carla = sys.modules.get("carla")
        sys.modules["carla"] = types.SimpleNamespace(
            Location=lambda *xyz: types.SimpleNamespace(xyz=xyz),
            VehicleControl=lambda **values: values)

    def tearDown(self):
        if self.prior_carla is None:
            sys.modules.pop("carla", None)
        else:
            sys.modules["carla"] = self.prior_carla

    def test_reviewed_full_capture_and_restore(self):
        raw = b"reviewed-map"
        world = World()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            packet = root / "site.json"
            packet.write_text(json.dumps(site(raw)) + "\n")
            result = capture.capture(world, case_id=speed.ASSIGNMENT + "__same25_at",
                site_path=packet, site_sha256=speed.sha256(packet), output=root / "attempt",
                operator=Operator(raw))
            self.assertEqual(result["original_frame_count"], 900)
            self.assertEqual(len(list((root / "attempt/cameras/overview").iterdir())), 900)
            self.assertFalse(world.settings.synchronous_mode)
            self.assertFalse(world.actor.is_alive)

    def test_map_mismatch_rejected_before_world_change(self):
        raw = b"reviewed-map"
        world = World()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            packet = root / "site.json"
            packet.write_text(json.dumps(site(raw)) + "\n")
            with self.assertRaisesRegex(ValueError, "loaded map differs"):
                capture.capture(world, case_id=speed.ASSIGNMENT + "__same25_at",
                    site_path=packet, site_sha256=speed.sha256(packet), output=root / "attempt",
                    operator=Operator(b"other-map"))
            self.assertFalse(world.settings.synchronous_mode)
            self.assertIsNone(world.actor)
