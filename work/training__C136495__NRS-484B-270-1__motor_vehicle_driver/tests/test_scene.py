"""CPU construction checks; no CARLA server or physical outcome is claimed."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace as NS

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "native"))
import geometry
import runner
import scene


class FakeBlueprint:
    def __init__(self, name):
        self.id = name
        self.attributes = {}

    def set_attribute(self, key, value):
        self.attributes[key] = value


class FakeActor:
    def __init__(self, blueprint, transform):
        self.blueprint = blueprint
        self.transform = transform
        self.destroyed = False

    def get_physics_control(self):
        wheels = [NS(position=NS(x=x), max_steer_angle=35) for x in (0, 240)]
        return NS(wheels=wheels)

    def get_transform(self):
        return self.transform

    def get_velocity(self):
        return NS(x=0, y=0, z=0)

    def destroy(self):
        self.destroyed = True


class FakeWorld:
    def __init__(self, fail_role=None, bad_lane=False):
        self.fail_role = fail_role
        self.bad_lane = bad_lane
        self.actors = []
        self.blueprints = {}

    def get_map(self):
        return self

    def get_waypoint(self, location, **kwargs):
        if not kwargs.get("project_to_road") is False:
            raise AssertionError("Lane survey must not project to another road")
        return NS(road_id=136495, lane_id=1 if self.bad_lane else -1)

    def get_blueprint_library(self):
        return self

    def find(self, name):
        blueprint = FakeBlueprint(name)
        self.blueprints[name] = blueprint
        return blueprint

    def spawn_actor(self, blueprint, transform):
        if blueprint.attributes["role_name"].endswith(str(self.fail_role)):
            return None
        actor = FakeActor(blueprint, transform)
        self.actors.append(actor)
        return actor


class FakeClient:
    def __init__(self, world):
        self.world = world
        self.xml = None

    def generate_opendrive_world(self, xml, parameters):
        self.xml = xml
        self.parameters = parameters
        return self.world


class ConstructionTests(unittest.TestCase):
    def setUp(self):
        self.carla = NS(
            OpendriveGenerationParameters=lambda **kwargs: kwargs,
            LaneType=NS(Driving="driving"),
            Location=lambda **kwargs: NS(**kwargs),
            Rotation=lambda **kwargs: NS(**kwargs),
            Transform=lambda location, rotation: NS(location=location, rotation=rotation),
        )

    def test_road_and_distinct_routes(self):
        self.assertEqual(geometry.validate_xml(geometry.open_drive())["driving_lane_ids"], [-1, 1])
        clear = geometry.route("ego", "clear")
        intrusion = geometry.route("ego", "intrusion")
        self.assertEqual(clear[0], intrusion[0])
        self.assertEqual(clear[-1], intrusion[-1])
        self.assertEqual(geometry.route("rider", "clear"), geometry.route("rider", "intrusion"))
        self.assertLess(min(y for _, y in intrusion), min(y for _, y in clear))
        self.assertTrue(all(-2.75 < y < 0 for _, y in intrusion))

    def test_both_conditions_construct_real_actor_calls(self):
        for condition in ("clear", "intrusion"):
            world = FakeWorld()
            built = scene.build(FakeClient(world), self.carla, condition)
            self.assertEqual(len(world.actors), 2)
            self.assertEqual([a.blueprint.id for a in world.actors],
                             [geometry.EGO_BLUEPRINT, geometry.RIDER_BLUEPRINT])
            self.assertEqual([a.blueprint.attributes["role_name"] for a in world.actors],
                             ["c136495_ego", "c136495_rider"])
            self.assertEqual(len(built["camera_plan"]), 4)
            self.assertFalse(built["physical_native_verified"])
            for role in ("ego", "rider"):
                command = scene.command_from_native(built["controllers"][role],
                                                    built["actors"][role], .05)
                self.assertGreaterEqual(command["throttle"], 0)
                self.assertEqual(command["route_station_m"], 0)

    def test_fallback_preserves_route_and_changes_only_steering_lookahead(self):
        primary = scene.build(FakeClient(FakeWorld()), self.carla, "intrusion", "primary")
        fallback = scene.build(FakeClient(FakeWorld()), self.carla, "intrusion", "fallback1")
        for role in ("ego", "rider"):
            self.assertEqual(primary["controllers"][role].route,
                             fallback["controllers"][role].route)
            self.assertEqual(primary["controllers"][role].knobs.target_speed_mps,
                             fallback["controllers"][role].knobs.target_speed_mps)
            self.assertLess(fallback["controllers"][role].knobs.lookahead_base_m,
                            primary["controllers"][role].knobs.lookahead_base_m)
        self.assertEqual(primary["source_plan"], fallback["source_plan"])
        self.assertEqual(primary["camera_plan"], fallback["camera_plan"])
        with self.assertRaisesRegex(ValueError, "candidate"):
            scene.build(FakeClient(FakeWorld()), self.carla, "clear", "fallback3")

    def test_lane_survey_rejects_wrong_road_side(self):
        world = FakeWorld(bad_lane=True)
        with self.assertRaisesRegex(RuntimeError, "lane survey"):
            scene.build(FakeClient(world), self.carla, "clear")
        self.assertEqual(world.actors, [])

    def test_failed_rider_spawn_destroys_ego(self):
        world = FakeWorld(fail_role="rider")
        with self.assertRaisesRegex(RuntimeError, "rider"):
            scene.build(FakeClient(world), self.carla, "intrusion")
        self.assertEqual(len(world.actors), 1)
        self.assertTrue(world.actors[0].destroyed)

    def test_unknown_condition_and_camera_tampering_rejected(self):
        with self.assertRaisesRegex(ValueError, "condition"):
            geometry.route("ego", "intentional")
        cameras = scene.camera_plan()
        cameras[2]["width"] = 640
        with self.assertRaisesRegex(ValueError, "camera"):
            scene.validate_camera_plan(cameras)

    def test_exact_capture_preflight_rejects_case_or_duration_drift(self):
        base = runner.ASSIGNMENT
        for condition, suffix in (("clear", "probe_a"), ("intrusion", "probe_b")):
            checked = runner.check(base + "__" + suffix, condition)
            self.assertEqual(checked["duration_s"], 30)
            self.assertEqual(len(checked["camera_plan"]), 4)
            self.assertFalse(checked["physical_native_verified"])
        with self.assertRaisesRegex(ValueError, "exact rider case"):
            runner.check(base + "__probe_a", "intrusion")
        with self.assertRaisesRegex(ValueError, "duration plan"):
            runner.check(base + "__probe_a", "clear", duration_s=10)


if __name__ == "__main__":
    unittest.main()
