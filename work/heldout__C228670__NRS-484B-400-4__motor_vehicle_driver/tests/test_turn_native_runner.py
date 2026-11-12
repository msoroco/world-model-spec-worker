"""CPU geometry and controller tests; no CARLA connection."""
import importlib.util
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('turn_native_runner', ROOT / 'turn_native_runner.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class Point:
    def __init__(self, x=0, y=0, z=0):
        self.x, self.y, self.z = x, y, z

    def distance(self, other):
        return ((self.x-other.x)**2 + (self.y-other.y)**2)**0.5


class Waypoint:
    def __init__(self, road, lane, s, yaw, junction=False):
        self.road_id, self.lane_id, self.s = road, lane, s
        self.is_junction = junction
        self.lane_width = 3.5
        self.transform = types.SimpleNamespace(location=Point(s, road, 0),
            rotation=types.SimpleNamespace(yaw=yaw), get_right_vector=lambda: Point(0, 1, 0))
        self.following = []

    def next(self, distance):
        return self.following

    def get_junction(self):
        return types.SimpleNamespace(id=17)


XODR = '''<OpenDRIVE>
<road id="1"><lanes><laneSection><right><lane id="-1" type="driving"/></right></laneSection></lanes></road>
<road id="2"><lanes><laneSection><left><lane id="1" type="driving"/></left><right><lane id="-1" type="driving"/></right></laneSection></lanes></road>
<road id="3"><lanes><laneSection><right><lane id="-1" type="driving"/></right></laneSection></lanes></road>
</OpenDRIVE>'''


class TurnNativeTests(unittest.TestCase):
    def test_exact_case_controls_and_source_directions(self):
        for suffix, offsets in runner.CASES.items():
            config = {'law_id': 'NRS-484B-400-4', 'cell_id': 'C228670',
                      'actor': 'motor_vehicle_driver', 'selected_case_id': runner.PREFIX+suffix,
                      'case': {'case_id': runner.PREFIX+suffix}, 'rate_hz': 20,
                      'frames': 160, 'cameras': [{}]*4}
            self.assertEqual(runner.check_config(config), offsets)
        self.assertEqual(runner.road_directions(XODR)[1], {-1})
        self.assertEqual(runner.road_directions(XODR)[2], {-1, 1})

    def test_connected_left_turn_requires_one_way_source_and_two_way_destination(self):
        source = Waypoint(1, -1, 0, 0)
        before = Waypoint(1, -1, 2, 0)
        inside = Waypoint(3, -1, 4, 45, True)
        departure = Waypoint(2, -1, 6, 90)
        source.following = [before]
        before.following = [inside]
        inside.following = [departure]
        mapping = types.SimpleNamespace(to_opendrive=lambda: XODR,
            get_spawn_points=lambda: [types.SimpleNamespace(location=Point())],
            get_waypoint=lambda location: source)
        result = runner.choose_turn(mapping)
        self.assertIs(result[0], source)
        self.assertIs(result[1], departure)
        self.assertEqual(len(result[2]), 4)
        departure.transform.rotation.yaw = -90
        with self.assertRaisesRegex(ValueError, 'one-way to two-way'):
            runner.choose_turn(mapping)
        departure.transform.rotation.yaw = 90
        departure.lane_id = 1
        with self.assertRaisesRegex(ValueError, 'one-way to two-way'):
            runner.choose_turn(mapping)
        departure.lane_id = -1
        source.lane_id = -2
        with self.assertRaisesRegex(ValueError, 'one-way to two-way'):
            runner.choose_turn(mapping)

    def test_original_reference_boundary_and_lateral_target(self):
        source = Waypoint(1, -1, 0, 0)
        continuation = Waypoint(1, -1, 5, 0)
        source.following = [continuation]
        self.assertEqual(runner.reference_line(source), [[0.0, -0.75], [5.0, -0.75]])
        carla = types.SimpleNamespace(Location=lambda **kw: Point(**kw),
                                      Transform=lambda location, rotation: types.SimpleNamespace(location=location, rotation=rotation))
        near = runner.center_offset_transform(carla, source, 1.25).location
        far = runner.center_offset_transform(carla, source, 2.20).location
        opposite = runner.center_offset_transform(carla, source, -1.0).location
        self.assertLess(near.y, far.y)
        self.assertLess(opposite.y, near.y)

    def test_pursuit_control_steers_toward_target(self):
        ego = types.SimpleNamespace(get_transform=lambda: types.SimpleNamespace(location=Point(), rotation=types.SimpleNamespace(yaw=0)))
        left = runner.control_to(ego, Point(10, 10))
        right = runner.control_to(ego, Point(10, -10))
        self.assertGreater(left['steer'], 0)
        self.assertLess(right['steer'], 0)


if __name__ == '__main__':
    unittest.main()
