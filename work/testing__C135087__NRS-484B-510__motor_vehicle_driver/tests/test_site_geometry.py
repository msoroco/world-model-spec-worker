"""Reviewed Native geometry tests use source-labelled CPU fixtures only."""

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from restricted_zone import ZonePlan
from reviewed_site import ROLES
from site_geometry import load, point_at_station, station_of
from native_adapter import NativePlacement


class SiteGeometryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=".runtime-work")
        self.root = Path(self.tmp.name)
        self.plan = ZonePlan("site-test", "reviewed-map", 10, 30, 16, -5, 23,
                             6, 24, 8, 15)
        sources = {}
        for role in ROLES:
            path = self.root / (role + ".txt")
            path.write_text("CPU fixture: " + role + "\n")
            sources[role] = {"path": path.name,
                             "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        geometry = self.root / "geometry.txt"
        geometry.write_text("CPU fixture geometry; no site authority claimed\n")
        binding = {
            "geometry_source": {"path": geometry.name,
                                "sha256": hashlib.sha256(geometry.read_bytes()).hexdigest()},
            "map_name": self.plan.map_id,
            "approach_route": [{"station_m": -5, "location_m": [-5, 0, 0]},
                               {"station_m": 35, "location_m": [35, 0, 0]}],
            "blueprints": {"subject": "vehicle.test.subject",
                           "entrant": "vehicle.test.entrant", "passenger": "walker.test"},
            "fixed_actors": {"zone_sign": {"actor_id": 11, "type_id": "static.sign"},
                             "zone_curb": {"actor_id": 12, "type_id": "static.curb"}},
            "camera_poses": {view: {"location_m": [0, 0, 2],
                                    "rotation_deg": [0, 0, 0]} for view in
                             ("overview", "approach", "reference_corner", "driver_reference")},
            "passenger_spawn_m": [16, 2, 0], "passenger_door_m": [16, 1, 0],
            "entrant_access_polygon_m": [[10, -2], [30, -2], [30, 2], [10, 2]],
            "observation_tolerances_m": {"station": 2, "door": 1, "access": 1}}
        self.packet = {"case_id": self.plan.case_id, "cell_id": "C135087",
                       "map_id": self.plan.map_id, "restricted_purpose": self.plan.restricted_purpose,
                       "zone_start_m": 10, "zone_end_m": 30,
                       "reviewer": "fixture reviewer", "reviewed_at": "fixture date",
                       "sources": sources, "native_binding": binding}
        self.path = self.root / "site.json"
        self.write()

    def tearDown(self):
        self.tmp.cleanup()

    def write(self):
        self.path.write_text(json.dumps(self.packet) + "\n")

    def test_reviewed_route_projection(self):
        binding = load(self.path, self.plan)
        self.assertEqual(point_at_station(binding, 16), (16, 0, 0))
        self.assertEqual(station_of(binding, (23, 1, 0)), 23)
        with self.assertRaisesRegex(ValueError, "outside reviewed route"):
            station_of(binding, (23, 3, 0))

    def test_missing_or_stale_geometry_rejected(self):
        self.packet["native_binding"].pop("geometry_source")
        self.write()
        with self.assertRaisesRegex(ValueError, "geometry source reference missing"):
            load(self.path, self.plan)
        self.packet["native_binding"]["geometry_source"] = {
            "path": "geometry.txt", "sha256": "0" * 64}
        self.write()
        with self.assertRaisesRegex(ValueError, "geometry source stale"):
            load(self.path, self.plan)

    def test_unreviewed_route_and_actor_rejected(self):
        self.packet["native_binding"]["approach_route"][1]["location_m"] = [100, 0, 0]
        self.write()
        with self.assertRaisesRegex(ValueError, "station distances disagree"):
            load(self.path, self.plan)
        self.packet["native_binding"]["approach_route"][1]["location_m"] = [35, 0, 0]
        self.packet["native_binding"]["fixed_actors"].pop("zone_sign")
        self.write()
        with self.assertRaisesRegex(ValueError, "fixed actor missing"):
            load(self.path, self.plan)

    def test_native_placement_and_restoration(self):
        class Location:
            def __init__(self, x, y, z):
                self.x, self.y, self.z = x, y, z

        class Rotation:
            def __init__(self, yaw):
                self.yaw = yaw

        class Transform:
            def __init__(self, location, rotation):
                self.location, self.rotation = location, rotation

        class Actor:
            def __init__(self, actor_id, type_id, transform=None):
                self.id, self.type_id, self.transform = actor_id, type_id, transform
                self.destroyed = False

            def get_transform(self):
                return self.transform

            def destroy(self):
                self.destroyed = True

        class Settings:
            synchronous_mode = False
            fixed_delta_seconds = None

        class Actors:
            def find(self, actor_id):
                return {11: Actor(11, "static.sign"),
                        12: Actor(12, "static.curb")}.get(actor_id)

        class Map:
            name = "reviewed-map"

            def get_waypoint(self, location, project_to_road):
                return type("Waypoint", (), {"transform": Transform(location, Rotation(0))})()

        class World:
            def __init__(self):
                self.settings, self.actors, self.mutations = Settings(), [], 0

            def get_map(self): return Map()
            def get_actors(self): return Actors()
            def get_settings(self): return self.settings
            def apply_settings(self, settings):
                self.settings = settings
                self.mutations += 1

            def get_blueprint_library(self):
                return type("Library", (), {"find": lambda _, name: name})()

            def try_spawn_actor(self, blueprint, transform):
                actor = Actor(20 + len(self.actors), blueprint, transform)
                self.actors.append(actor)
                return actor

        class Client:
            def __init__(self): self.world = World()
            def get_world(self): return self.world

        carla = type("Carla", (), {"Location": Location, "Rotation": Rotation,
                                   "Transform": Transform})
        client = Client()
        placement = NativePlacement(client, carla, self.plan, self.path)
        self.assertEqual(client.world.mutations, 0)
        placement.load_map("reviewed-map")
        placement.mark_zone(10, 30, self.plan.restricted_purpose, self.plan.restricted_source)
        subject = placement.spawn_vehicle("subject", 16, "passenger-vehicle-candidate")
        entrant = placement.spawn_vehicle("restricted-purpose-entrant", -5,
                                           "reserved-purpose-vehicle-candidate")
        passenger = placement.spawn_pedestrian("passenger", 16)
        placement.set_route(entrant, 23)
        placement.set_route(passenger, 16)
        placement.schedule(entrant, "start_approach", 6)
        self.assertEqual(len(placement.owned), 3)
        self.assertEqual(placement.routes[entrant.id], (23, 0, 0))
        self.assertTrue(placement.restore())
        self.assertTrue(all(actor.destroyed for actor in (subject, entrant, passenger)))
        self.assertFalse(client.world.get_settings().synchronous_mode)

    def test_native_mismatch_fails_before_world_mutation(self):
        class World:
            def get_map(self): return type("Map", (), {"name": "wrong-map"})()

        class Client:
            def get_world(self): return World()

        with self.assertRaisesRegex(ValueError, "live Native map differs"):
            NativePlacement(Client(), object(), self.plan, self.path)


if __name__ == "__main__":
    unittest.main()
