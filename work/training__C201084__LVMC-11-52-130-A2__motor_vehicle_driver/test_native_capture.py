"""CPU tests for Native control, source readback and capture rejection."""
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from fire_lane_survey import build
from native_capture import CAMERA_SPECS, OriginalFrameMap, acquire, sample_native
from native_controller import command

HERE = Path(__file__).resolve().parent


def location(x, y, z=0):
    return SimpleNamespace(x=x, y=y, z=z)


def plan():
    survey = json.loads((HERE/'draft-fire-lane-survey.json').read_text())
    def probe(xy):
        return {'map_name': survey['map_name'], 'road_id': 17,
                'lane_id': -1, 'drivable_access': True,
                'source_kind': 'synthetic_construction_probe'}
    return build(survey, probe)


def ego():
    transform = SimpleNamespace(location=location(10, 1),
                                rotation=SimpleNamespace(yaw=0))
    actor = SimpleNamespace(id=41, get_transform=lambda: transform,
                            get_velocity=lambda: location(0, 0),
                            bounding_box=SimpleNamespace(get_world_vertices=lambda t: [
                                location(9.5, 0.7), location(10.5, 0.7),
                                location(10.5, 1.3), location(9.5, 1.3)]))
    actor.apply_control = lambda control: None
    return actor


def follower():
    actor = ego()
    actor.id = 42
    actor.get_transform = lambda: SimpleNamespace(location=location(-2, 1),
                                                   rotation=SimpleNamespace(yaw=0))
    return actor


class CaptureTests(unittest.TestCase):
    def test_frame_map_retains_exact_order_and_rejects_time_reversal(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'video_frames.jsonl'
            frames = OriginalFrameMap(path)
            try:
                frames.append(81, 0.0)
                frames.append(82, 0.05)
                with self.assertRaisesRegex(ValueError, 'must increase'):
                    frames.append(83, 0.04)
            finally:
                frames.close()
            rows = [json.loads(line) for line in path.read_text().splitlines()]
            self.assertEqual(rows, [
                {'video_frame': 0, 'carla_frame': 81, 'native_frame': 81,
                 'time_s': 0.0},
                {'video_frame': 1, 'carla_frame': 82, 'native_frame': 82,
                 'time_s': 0.05}])

    def test_controller_approach_and_stop(self):
        approaching = command([0, 1], 0, [2, 0, 0], [10, 1])
        self.assertEqual(approaching['phase'], 'approach')
        self.assertGreater(approaching['throttle'], 0)
        stopped = command([10, 1], 0, [0, 0, 0], [10, 1])
        self.assertEqual(stopped['phase'], 'target_braking')
        self.assertTrue(stopped['hand_brake'])
        self.assertEqual(stopped['brake'], 1)

    def test_original_source_reader_needs_same_road_and_sign(self):
        p = plan()
        sign = SimpleNamespace(id=101, get_transform=lambda:
                               SimpleNamespace(location=location(6, -1)))
        mapping = SimpleNamespace(get_waypoint=lambda *args, **kwargs:
                                  SimpleNamespace(road_id=17, lane_id=-1))
        world = SimpleNamespace(get_map=lambda: mapping)
        carla = SimpleNamespace(LaneType=SimpleNamespace(Driving=1))
        row = sample_native(world, carla, ego(), follower(), sign, p)
        self.assertEqual(row['sign_actor_id'], 101)
        self.assertEqual(row['driving_road_id'], 17)
        mapping.get_waypoint = lambda *args, **kwargs: SimpleNamespace(road_id=19)
        with self.assertRaisesRegex(ValueError, 'departed surveyed road'):
            sample_native(world, carla, ego(), follower(), sign, p)

    def test_four_camera_frame_mismatch_rejected_and_closed(self):
        p = plan()
        self.assertEqual([row[0] for row in CAMERA_SPECS], p['camera_names'])
        closed = []
        class Sink:
            def __init__(self, path, width, height):
                self.path = path
            def write(self, image):
                pass
            def close(self):
                closed.append(self.path.name)
        class Sensor:
            def stop(self):
                pass
            def destroy(self):
                pass
        def install(world, carla, actor, callback):
            for name in p['camera_names']:
                callback(name, SimpleNamespace(frame=999 if name == 'approach' else 1))
            return [Sensor() for _ in p['camera_names']]
        settings = SimpleNamespace(synchronous_mode=True, fixed_delta_seconds=0.05)
        world = SimpleNamespace(get_settings=lambda: settings, tick=lambda: 1)
        carla = SimpleNamespace(VehicleControl=lambda **kwargs: kwargs)
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, 'camera frame join differs: approach'):
                acquire(world, carla, ego(), follower(), None, p, 'reference', Path(tmp),
                        sink_factory=Sink, camera_installer=install)
        self.assertEqual(len(closed), 4)

    def test_short_capture_contract_rejected(self):
        p = plan()
        p['capture_frames'] = 10
        with self.assertRaisesRegex(ValueError, 'capture contract differs'):
            acquire(SimpleNamespace(), SimpleNamespace(), ego(), follower(), None, p,
                    'reference', Path('/tmp/unused-c201084-test'))


if __name__ == '__main__':
    unittest.main()
