import importlib.util
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location('opposing_turn_native_routes', ROOT / 'opposing_turn_native_routes.py')
routes = importlib.util.module_from_spec(spec)
spec.loader.exec_module(routes)


class Waypoint:
    def __init__(self, road, lane, s, yaw, junction=False):
        self.road_id, self.lane_id, self.s = road, lane, s
        self.is_junction = junction
        self.transform = SimpleNamespace(rotation=SimpleNamespace(yaw=yaw))
        self.successors = []

    def next(self, distance):
        return self.successors

    def get_junction(self):
        return SimpleNamespace(id=7) if self.is_junction else None


class Map:
    xml = '<OpenDRIVE><road id="10"><lanes><laneSection><left><lane id="1" type="driving"/></left><right><lane id="-1" type="driving"/></right></laneSection></lanes></road><road id="20"><lanes><laneSection><left><lane id="1" type="driving"/></left><right><lane id="-1" type="driving"/></right></laneSection></lanes></road></OpenDRIVE>'

    def __init__(self, east, west):
        self.spawns = [SimpleNamespace(location=east), SimpleNamespace(location=west)]

    def to_opendrive(self):
        return self.xml

    def get_spawn_points(self):
        return self.spawns

    def get_waypoint(self, location):
        return location


def survey_map():
    east = Waypoint(10, -1, 0, 0)
    east_junction = Waypoint(10, -1, 2, 0, True)
    north = Waypoint(20, -1, 4, 90)
    west = Waypoint(10, 1, 0, 180)
    west_junction = Waypoint(10, 1, 2, 180, True)
    south = Waypoint(20, 1, 4, -90)
    east.successors = [east_junction]
    east_junction.successors = [north]
    west.successors = [west_junction]
    west_junction.successors = [south]
    return Map(east, west), east_junction, west_junction


class NativeRouteSurveyTests(unittest.TestCase):
    def test_connected_opposing_left_routes_from_both_directions(self):
        world_map, _, _ = survey_map()
        pair = routes.choose_native_pair(world_map)
        self.assertEqual({pair['subject']['approach_lane_id'], pair['opposing']['approach_lane_id']}, {-1, 1})
        self.assertEqual(len(pair['subject']['path']), 3)
        self.assertEqual(pair['junction_id'], 7)

    def test_disconnected_and_one_way_geometry_rejected(self):
        world_map, _, west_junction = survey_map()
        west_junction.successors = []
        with self.assertRaisesRegex(ValueError, 'no surveyed'):
            routes.choose_native_pair(world_map)
        world_map, _, _ = survey_map()
        world_map.xml = world_map.xml.replace('<left><lane id="1" type="driving"/></left>', '<left/>')
        with self.assertRaisesRegex(ValueError, 'no surveyed'):
            routes.choose_native_pair(world_map)

    def test_wrong_turn_and_same_direction_lane_rejected(self):
        world_map, _, west_junction = survey_map()
        west_junction.successors[0].transform.rotation.yaw = 90
        with self.assertRaisesRegex(ValueError, 'no surveyed'):
            routes.choose_native_pair(world_map)
        world_map, _, _ = survey_map()
        world_map.spawns[1].location.lane_id = -1
        with self.assertRaisesRegex(ValueError, 'no surveyed'):
            routes.choose_native_pair(world_map)


if __name__ == '__main__':
    unittest.main()
