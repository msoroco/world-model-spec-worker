import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as S
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from runner import load_scene
from native_capture import CameraCapture, _lane_target, _set_tire_friction, _spawn, _steer


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

    def test_camera_close_releases_all_sensors_after_encoder_failure(self):
        events = []
        camera = CameraCapture.__new__(CameraCapture)
        camera.closed = False
        camera.sensors = [S(stop=lambda: events.append('stop1'),
                            destroy=lambda: events.append('destroy1')),
                          S(stop=lambda: events.append('stop2'),
                            destroy=lambda: events.append('destroy2'))]
        camera.encoders = {'first': S(stdin=S(closed=False,
            close=lambda: events.append('close1')),
            wait=lambda timeout: 1),
            'second': S(stdin=S(closed=False,
            close=lambda: events.append('close2')),
            wait=lambda timeout: 0)}
        with self.assertRaisesRegex(RuntimeError, 'camera encoder failed: first'):
            camera.close()
        self.assertEqual(events, ['stop2', 'stop1', 'close1', 'close2',
                                  'destroy2', 'destroy1'])

    def test_fog_and_wheel_friction_targets_are_validated_and_applied(self):
        scene = load_scene()
        scene['fog_density_percent'] = 38
        scene['tire_friction'] = 2.1
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'scene.json'
            path.write_text(json.dumps(scene))
            self.assertEqual(load_scene(path)['fog_density_percent'], 38)
            wheels = [S(tire_friction=1.0), S(tire_friction=1.0)]
            applied = []
            actor = S(get_physics_control=lambda: S(wheels=wheels),
                      apply_physics_control=lambda physics: applied.append(physics))
            _set_tire_friction([actor], 2.1)
            self.assertEqual([w.tire_friction for w in applied[0].wheels], [2.1, 2.1])
            scene['fog_density_percent'] = 101
            path.write_text(json.dumps(scene))
            with self.assertRaisesRegex(ValueError, 'fog target'):
                load_scene(path)

    def test_all_camera_views_follow_the_selected_ego_route(self):
        mounted = []
        ego = object()
        blueprint = S(set_attribute=lambda *args: None)
        library = S(find=lambda name: blueprint)
        def spawn(_blueprint, _transform, attach_to):
            mounted.append(attach_to)
            return S(listen=lambda callback: None, stop=lambda: None,
                     destroy=lambda: None)
        world = S(get_blueprint_library=lambda: library, spawn_actor=spawn)
        carla = S(Location=lambda **value: value,
                 Rotation=lambda **value: value,
                 Transform=lambda location, rotation: (location, rotation))
        process = S(stdin=S(closed=False, close=lambda: None),
                    wait=lambda timeout: 0)
        with tempfile.TemporaryDirectory() as temp, patch(
                'native_capture.subprocess.Popen', return_value=process):
            camera = CameraCapture(world, ego, Path(temp), carla)
            camera.close()
        self.assertEqual(mounted, [ego]*4)


if __name__ == '__main__':
    unittest.main()
