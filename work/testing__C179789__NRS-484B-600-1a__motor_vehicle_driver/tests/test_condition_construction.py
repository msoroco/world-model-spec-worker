import copy
import importlib.util
import unittest
from pathlib import Path
from types import SimpleNamespace as NS

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("condition_construction", ROOT / "condition_construction.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class Location:
    def __init__(self, *, x, y, z):
        self.x, self.y, self.z = x, y, z


class World:
    def __init__(self):
        self.original = NS(**dict(zip(MODULE.WEATHER_FIELDS, (10, 0, 0, 0, 100, 30))))
        self.weather = self.original
        self.calls = []
        self.corrupt_readback = False

    def get_weather(self):
        if self.corrupt_readback and self.weather is not self.original:
            value = copy.copy(self.weather)
            value.precipitation = 0
            return value
        return self.weather

    def set_weather(self, weather):
        self.calls.append(weather)
        self.weather = weather

    def cast_ray(self, eye, target):
        self.ray = (eye, target)
        return [NS(location=Location(x=18, y=0, z=1.5))]


class ConditionConstructionTests(unittest.TestCase):
    def profile(self):
        return dict(zip(MODULE.WEATHER_FIELDS, (80, 75, 85, 20, 40, 5)))

    def test_weather_readback_and_restore(self):
        world = World()
        with MODULE.apply_sourced_weather(world, self.profile(), profile_source="reviewed profile reference") as receipt:
            self.assertEqual(receipt["readback"]["precipitation"], 75)
            self.assertFalse(receipt["surface_state_verified"])
            self.assertIsNot(world.weather, world.original)
        self.assertIs(world.weather, world.original)
        self.assertEqual(len(world.calls), 2)

    def test_readback_failure_also_restores(self):
        world = World()
        world.corrupt_readback = True
        with self.assertRaisesRegex(ValueError, "readback differs"):
            with MODULE.apply_sourced_weather(world, self.profile(), profile_source="reviewed profile reference"):
                pass
        self.assertIs(world.weather, world.original)

    def test_original_ray_and_lane_probe(self):
        world = World()
        waypoint = NS(road_id=7, lane_id=-1, lane_width=3.25)
        result = MODULE.sample_lane_and_sight(world, waypoint, Location(x=0, y=0, z=1.5),
                                               (1, 0, 0), 30, map_source="map packet",
                                               ray_source="Native cast_ray frame")
        self.assertEqual(result["sight_distance_m"], 18)
        self.assertEqual(result["lane_width_m"], 3.25)
        self.assertFalse(result["original_camera_visibility_verified"])
        self.assertEqual(world.ray[1].x, 30)
        with self.assertRaisesRegex(ValueError, "map and ray source"):
            MODULE.sample_lane_and_sight(world, waypoint, Location(x=0, y=0, z=1.5),
                                         (1, 0, 0), 30, map_source="", ray_source="ray")

    def test_narrow_route_surveys_native_width_and_continuity(self):
        class Waypoint:
            def __init__(self, distance, width=2.8, lane=-1, junction=False, branch=False):
                self.distance = distance
                self.lane_width = width
                self.road_id = 7
                self.lane_id = lane
                self.is_junction = junction
                self.branch = branch

            def next(self, step):
                if self.branch:
                    return [Waypoint(self.distance + step), Waypoint(self.distance + step)]
                return [Waypoint(self.distance + step)]

        receipt = MODULE.survey_narrow_route(Waypoint(0), target_width_m=[2.5, 3.0])
        self.assertEqual(receipt['surveyed_length_m'], 110)
        self.assertEqual(len(receipt['samples']), 23)
        self.assertFalse(receipt['physical_motion_verified'])
        with self.assertRaisesRegex(ValueError, 'width or continuity'):
            MODULE.survey_narrow_route(Waypoint(0, width=3.5), target_width_m=[2.5, 3.0])
        with self.assertRaisesRegex(ValueError, 'width or continuity'):
            MODULE.survey_narrow_route(Waypoint(0, lane=1, junction=True), target_width_m=[2.5, 3.0])
        with self.assertRaisesRegex(ValueError, 'missing or branching'):
            MODULE.survey_narrow_route(Waypoint(0, branch=True), target_width_m=[2.5, 3.0])


if __name__ == "__main__":
    unittest.main()
