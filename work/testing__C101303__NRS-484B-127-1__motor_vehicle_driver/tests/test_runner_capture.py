import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as S

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from runner import load_scene
from native_capture import _lane_target, _spawn, _steer


class Waypoint:
    def __init__(self, lane):
        self.road_id = 12
        self.lane_id = lane
        self.transform = S(location=S(x=20, y=lane*3.5, z=0))
        self.left = None
        self.successor = None

    def next(self, distance):
        return [self.successor] if self.successor else []

    def get_left_lane(self):
        return self.left

    def get_right_lane(self):
        return None


class RunnerCaptureTest(unittest.TestCase):
    def test_all_exact_scene_drafts_check_without_carla(self):
        for path in (ROOT/'cases').glob('*/scene.json'):
            with self.subTest(path=path):
                self.assertEqual(load_scene(path)['case_id'], json.loads(path.read_text())['case_id'])
        with tempfile.TemporaryDirectory() as temp:
            value = load_scene()
            value['lane_change_start_s'] = 17
            path = Path(temp)/'bad.json'
            path.write_text(json.dumps(value))
            with self.assertRaisesRegex(ValueError, 'judgment window'):
                load_scene(path)

    def test_lane_target_uses_forward_adjacent_lane(self):
        source, adjacent = Waypoint(-1), Waypoint(-2)
        source.left = adjacent
        source.successor = Waypoint(-1)
        adjacent.successor = Waypoint(-2)
        actor = S(get_transform=lambda: S(location=S(x=0,y=0,z=0),
                                          rotation=S(yaw=0)))
        native_map = S(get_waypoint=lambda location: source)
        self.assertEqual(_lane_target(native_map, actor, -2, True).lane_id, -2)
        self.assertEqual(_lane_target(native_map, actor, -2, False).lane_id, -1)
        self.assertLess(_steer(actor, adjacent), 0)
        source.left = None
        with self.assertRaisesRegex(ValueError, 'target lane unavailable'):
            _lane_target(native_map, actor, -2, True)

    def test_partial_native_spawn_cleans_up(self):
        destroyed = []
        first = S(id=1, destroy=lambda: destroyed.append(1))
        calls = iter([first, None])
        world = S(spawn_actor=lambda blueprint, transform: next(calls))
        with self.assertRaisesRegex(ValueError, 'spawn failed'):
            _spawn(world, object(), [Waypoint(-1), Waypoint(-1)])
        self.assertEqual(destroyed, [1])


if __name__ == '__main__':
    unittest.main()
