import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest


PACKAGE = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("construction", PACKAGE / "construction.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class Waypoint:
    def __init__(self, x, y, yaw, junction=False, road=1, lane=-1, station=0):
        self.transform = SimpleNamespace(location=SimpleNamespace(x=x, y=y),
                                         rotation=SimpleNamespace(yaw=yaw))
        self.is_junction = junction
        self.road_id, self.lane_id, self.s = road, lane, station
        self.lane_type = "Driving"
        self.forward = []
    def next(self, distance):
        return self.forward
    def previous(self, distance):
        return []
    def get_junction(self):
        return SimpleNamespace(id=42)


class Map:
    def __init__(self, waypoints):
        self.waypoints = waypoints
    def generate_waypoints(self, distance):
        return self.waypoints


class ConstructionTest(unittest.TestCase):
    def test_selects_opposing_routes_and_connected_left_exit(self):
        west = Waypoint(-40, 0, 0, station=10)
        west_near = Waypoint(-4, 0, 0, station=11)
        west_entry = Waypoint(-4, 0, 0, True, road=10, station=14)
        west_exit = Waypoint(0, -8, -90, False, road=11, station=18)
        east = Waypoint(40, 0, 180, road=2, station=10)
        east_near = Waypoint(4, 0, 180, road=2, station=11)
        east_entry = Waypoint(4, 0, 180, True, road=20, station=14)
        west.forward = [west_near]
        west_near.forward = [west_entry]
        west_entry.forward = [west_exit]
        east.forward = [east_near]
        east_near.forward = [east_entry]
        result = MODULE.select_intersection(Map([west, east]))
        self.assertIs(result["ego"]["outside"], west)
        self.assertIs(result["oncoming"]["outside"], east)
        self.assertIs(result["left_route"][-1], west_exit)

    def test_rejects_same_direction_or_disconnected_exit(self):
        west = Waypoint(-20, 0, 0, station=10)
        west_entry = Waypoint(-4, 0, 0, True, road=10, station=14)
        east = Waypoint(20, 0, 0, road=2, station=10)
        east_entry = Waypoint(4, 0, 0, True, road=20, station=14)
        west.forward = [west_entry]
        east.forward = [east_entry]
        with self.assertRaisesRegex(ValueError, "No connected opposing"):
            MODULE.select_intersection(Map([west, east]))

    def test_spawn_failure_destroys_owned_actor(self):
        destroyed = []
        class Blueprint:
            def set_attribute(self, key, value):
                pass
        class Library:
            def find(self, name):
                return Blueprint()
        class Actor:
            def destroy(self):
                destroyed.append(True)
        class World:
            calls = 0
            def get_blueprint_library(self):
                return Library()
            def try_spawn_actor(self, blueprint, transform):
                self.calls += 1
                return Actor() if self.calls == 1 else None
        waypoint = Waypoint(0, 0, 0)
        chosen = {"ego": {"outside": waypoint}, "oncoming": {"outside": waypoint}}
        with self.assertRaisesRegex(ValueError, "Native spawn failed"):
            MODULE.spawn_pair(World(), chosen)
        self.assertEqual(destroyed, [True])


if __name__ == "__main__":
    unittest.main()
