import hashlib
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace as Box
import unittest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from comparison_audit import DIRECTION
from native_scene import create, validate


MAP_TEXT = ("<OpenDRIVE>" + "".join(
    f'<road id="{road}"><lanes><laneSection s="0"><left><lane id="1" type="driving">'
    f'<width sOffset="0" a="{width}"/></lane></left><right><lane id="-1" type="driving">'
    f'<width sOffset="0" a="{width}"/></lane></right></laneSection></lanes></road>'
    for road, width in ((42, 4.0), (43, 3.5))) + "</OpenDRIVE>")
PLAN = json.loads((HERE / "case-plan.json").read_text())


def packet():
    base = {"ego_speed_request_mps": 10.0, "leader_initial_gap_m": 30.0,
            "surface_wetness_request": .2, "highway_width_m": 8.0,
            "native_precipitation_request": 20.0, "native_fog_request": 10.0}
    items = {}
    for case in PLAN["cases"]:
        case_id = case["case_id"]
        variables = dict(base)
        comparison = next((item for item in PLAN["comparisons"]
                           if item["case_ids"][1] == case_id), None)
        if comparison:
            field = comparison["deliberate_differences"][0]
            step = .1 if field == "surface_wetness_request" else 1.0
            variables[field] += DIRECTION[comparison["comparison_id"]] * step
        road_id = 43 if comparison and comparison["comparison_id"] == "width" else 42
        items[case_id] = {"case_id": case_id, "source_citation": "reviewed source packet",
                          "reviewer": "fixture reviewer", "road_id": road_id, "lane_id": -1,
                          "ego_station_m": 50.0, "variables": variables}
    return {"assignment_id": PLAN["assignment_id"],
            "source_citation": "fixture source", "reviewer": "fixture reviewer",
            "map_sha256": hashlib.sha256(MAP_TEXT.encode()).hexdigest(),
            "ego_blueprint_id": "vehicle.ego", "leader_blueprint_id": "vehicle.leader",
            "leader_speed_request_mps": 8.0,
            "paved_road": True, "travel_direction": "forward",
            "duration_frames": 900, "camera_profile": "four-view", "cases": items}


class FakeWaypoint:
    lane_id, is_junction = -1, False
    lane_type = Box(name="Driving")
    transform = Box(get_forward_vector=lambda: Box(x=1.0, y=0.0, z=0.0))

    def __init__(self, road_id=42):
        self.road_id = road_id

    def next(self, distance):
        if distance <= 5:
            raise AssertionError("leader not ahead")
        return [FakeWaypoint(self.road_id)]


class FakeActor:
    def __init__(self, actor_id):
        self.id = actor_id
        self.destroyed = False
        self.velocity = None
        self.physics = Box(wheels=[Box(tire_friction=1.0)])

    def set_target_velocity(self, velocity):
        self.velocity = velocity

    def get_physics_control(self):
        return self.physics

    def apply_physics_control(self, physics):
        self.physics = physics

    def destroy(self):
        self.destroyed = True


class FakeWorld:
    def __init__(self, map_text=MAP_TEXT, fail_second=False):
        self.map_text = map_text
        self.fail_second = fail_second
        self.weather = Box(wetness=0.0, precipitation=0.0, fog_density=0.0)
        self.spawned = []

    def get_map(self):
        return Box(to_opendrive=lambda: self.map_text,
                   get_waypoint_xodr=lambda road, lane, station: FakeWaypoint(road))

    def get_blueprint_library(self):
        return Box(find=lambda identity: identity)

    def try_spawn_actor(self, blueprint, transform):
        if self.fail_second and len(self.spawned) == 1:
            return None
        actor = FakeActor(len(self.spawned) + 1)
        self.spawned.append(actor)
        return actor

    def get_weather(self):
        return self.weather

    def set_weather(self, weather):
        self.weather = weather


class NativeSceneTests(unittest.TestCase):
    def with_packet(self, callback, document=None):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "packet.json"
            path.write_text(json.dumps(document if document is not None else packet()))
            return callback(path)

    def test_seven_exact_case_spawns_weather_and_cleanup(self):
        for case in PLAN["cases"]:
            case_id = case["case_id"]
            with self.subTest(case_id=case_id):
                def check(path):
                    world = FakeWorld()
                    scene = create(world, path, HERE / "case-plan.json", case_id,
                                   lambda x, y, z: (x, y, z))
                    self.assertEqual(len(world.spawned), 2)
                    self.assertEqual(scene.ego.velocity[0],
                                     packet()["cases"][case_id]["variables"]["ego_speed_request_mps"])
                    self.assertEqual(world.weather.wetness,
                                     100 * packet()["cases"][case_id]["variables"]["surface_wetness_request"])
                    self.assertEqual(scene.source["opendrive_sha256"], packet()["map_sha256"])
                    scene.close()
                    self.assertTrue(all(actor.destroyed for actor in world.spawned))
                    self.assertEqual(world.weather.wetness, 0)
                self.with_packet(check)

    def test_unreviewed_extra_change_rejected(self):
        document = packet()
        alternative = PLAN["comparisons"][0]["case_ids"][1]
        document["cases"][alternative]["variables"]["leader_initial_gap_m"] += 1
        with self.assertRaisesRegex(ValueError, "undeclared comparison"):
            self.with_packet(lambda path: validate(path, HERE / "case-plan.json", alternative), document)

    def test_map_mismatch_rejected_before_spawning(self):
        def check(path):
            world = FakeWorld(map_text="different")
            with self.assertRaisesRegex(ValueError, "OpenDRIVE source differs"):
                create(world, path, HERE / "case-plan.json", PLAN["cases"][0]["case_id"],
                       lambda x, y, z: (x, y, z))
            self.assertEqual(world.spawned, [])
        self.with_packet(check)

    def test_requested_width_must_match_original_opendrive(self):
        document = packet()
        for item in document["cases"].values():
            item["variables"]["highway_width_m"] += 1
        def check(path):
            world = FakeWorld()
            with self.assertRaisesRegex(ValueError, "driving width differs"):
                create(world, path, HERE / "case-plan.json", PLAN["cases"][0]["case_id"],
                       lambda x, y, z: (x, y, z))
            self.assertEqual(world.spawned, [])
        self.with_packet(check, document)

    def test_failed_second_spawn_destroys_ego_and_restores_weather(self):
        def check(path):
            world = FakeWorld(fail_second=True)
            with self.assertRaisesRegex(ValueError, "vehicle spawn failed"):
                create(world, path, HERE / "case-plan.json", PLAN["cases"][0]["case_id"],
                       lambda x, y, z: (x, y, z))
            self.assertTrue(world.spawned[0].destroyed)
            self.assertEqual(world.weather.wetness, 0)
        self.with_packet(check)


if __name__ == "__main__":
    unittest.main()
