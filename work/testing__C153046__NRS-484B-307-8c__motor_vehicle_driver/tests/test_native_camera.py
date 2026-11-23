"""Exercise exact four-camera spawn and original frame join with fake CARLA APIs."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace as NS
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from native_camera import CameraRig, VIEWS, validate_plan
from native_runner import run_carla
from red_left_turn_controller import Observation
from tests.test_native_frame import Actor, World
from tests.test_source_bound_scene import fixture

REPO = Path(__file__).resolve().parents[3]


def packet_with_cameras(root):
    packet = fixture(root)
    packet['signal']['native_actor_id'] = '9'
    packet['cameras'] = [
        {'name': name, 'width': width, 'height': height, 'attachment': 'ego' if name == 'driver_reference' else 'world',
         'pose_source_citation': 'synthetic CPU pose protocol', 'reviewer': 'CPU test',
         'location_xyz_m': [0, 0, 5], 'rotation_rpy_deg': [0, 0, 0], 'fov_deg': 90}
        for name, width, height in VIEWS]
    path = root / 'site.json'
    path.write_text(json.dumps(packet))
    return path


class Sensor:
    def __init__(self, blueprint, transform, kwargs):
        self.blueprint, self.transform, self.kwargs = blueprint, transform, kwargs
        self.callback = None
        self.stopped = self.destroyed = False
    def listen(self, callback):
        self.callback = callback
    def stop(self):
        self.stopped = True
    def destroy(self):
        self.destroyed = True


class CameraWorld(World):
    def __init__(self):
        super().__init__()
        self.sensors = []
    def get_blueprint_library(self):
        return NS(find=lambda _: NS(attributes={}, set_attribute=lambda name, value: None))
    def get_settings(self):
        return NS(synchronous_mode=True, no_rendering_mode=False, fixed_delta_seconds=.05)
    def spawn_actor(self, blueprint, transform, **kwargs):
        sensor = Sensor(blueprint, transform, kwargs)
        self.sensors.append(sensor)
        return sensor
    def emit(self, frame, *, corrupt=None):
        for sensor, (_, width, height) in zip(self.sensors, VIEWS):
            data = bytes(width * height * 4)
            if corrupt is sensor:
                data = b'bad'
            sensor.callback(NS(frame=frame, timestamp=frame / 20, width=width, height=height,
                               raw_data=data))


class NativeCameraTests(unittest.TestCase):
    def test_four_source_bound_spawn_and_original_frame_join(self):
        (REPO / '.runtime-work').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=REPO / '.runtime-work') as temp:
            root = Path(temp)
            site = packet_with_cameras(root)
            world = CameraWorld()
            output = root / 'raw'
            ego = Actor(1)
            rig = CameraRig(world, ego, site, 'stopped_leftmost_clear', output,
                            lambda xyz, rpy: (xyz, rpy))
            self.assertEqual(len(world.sensors), 4)
            self.assertIs(world.sensors[3].kwargs['attach_to'], ego)
            world.emit(1)
            result = rig.await_frame(1, .05)
            self.assertEqual(set(result), {name for name, _, _ in VIEWS})
            for item in result.values():
                raw = output / item['raw_bgra']
                self.assertEqual(hashlib.sha256(raw.read_bytes()).hexdigest(), item['sha256'])
                self.assertEqual(item['source_packet_sha256'], rig.scene['source_packet_sha256'])
            rig.close()
            self.assertTrue(all(s.stopped and s.destroyed for s in world.sensors))

    def test_wrong_pose_pixels_time_and_duplicate_rejected(self):
        (REPO / '.runtime-work').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=REPO / '.runtime-work') as temp:
            root = Path(temp)
            site = packet_with_cameras(root)
            packet = json.loads(site.read_text())
            packet['cameras'][0]['location_xyz_m'] = [float('nan'), 0, 0]
            site.write_text(json.dumps(packet))
            with self.assertRaisesRegex(ValueError, 'finite overview location'):
                validate_plan(site, 'stopped_leftmost_clear')
            site = packet_with_cameras(root)
            class Unrendered(CameraWorld):
                def get_settings(self):
                    return NS(synchronous_mode=True, no_rendering_mode=True, fixed_delta_seconds=.05)
            with self.assertRaisesRegex(ValueError, 'rendered synchronous'):
                CameraRig(Unrendered(), Actor(1), site, 'stopped_leftmost_clear', root / 'unrendered',
                          lambda xyz, rpy: (xyz, rpy))
            world = CameraWorld()
            rig = CameraRig(world, Actor(1), site, 'stopped_leftmost_clear', root / 'raw',
                            lambda xyz, rpy: (xyz, rpy))
            world.emit(1, corrupt=world.sensors[0])
            with self.assertRaisesRegex(ValueError, 'callback failed'):
                rig.await_frame(1, .05)
            rig.close()
        with tempfile.TemporaryDirectory(dir=REPO / '.runtime-work') as temp:
            root = Path(temp)
            site = packet_with_cameras(root)
            world = CameraWorld()
            rig = CameraRig(world, Actor(1), site, 'stopped_leftmost_clear', root / 'raw',
                            lambda xyz, rpy: (xyz, rpy))
            world.emit(1)
            with self.assertRaisesRegex(ValueError, 'timestamps differ'):
                rig.await_frame(1, .5)
            world.emit(1)
            with self.assertRaisesRegex(ValueError, 'callback failed'):
                rig.await_frame(1, .05)
            rig.close()

    def test_runner_joins_four_views(self):
        class FakeRig:
            def __init__(self, site):
                from source_bound_scene import build
                self.scene = build(site, 'stopped_leftmost_clear')
            def await_frame(self, frame, time_s):
                return {name: {'frame': frame, 'time_s': time_s, 'sha256': 'source-hash'}
                        for name, _, _ in VIEWS}
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            site = packet_with_cameras(root)
            class Ego(Actor):
                def apply_control(self, control):
                    self.control = control
            trace = root / 'trace.jsonl'
            run_carla(World(), Ego(1), Actor(9), [Actor(2)], [Actor(3)],
                      packet_path=site, case_suffix='stopped_leftmost_clear', output_path=trace,
                      count=2, observation_from_frame=lambda frame, scene: Observation(
                          frame['time_s'], 1, 0, 'steady_red_alone', False, False),
                      control_factory=lambda **kw: kw, camera_rig=FakeRig(site))
            rows = [json.loads(line) for line in trace.read_text().splitlines()]
            self.assertEqual([r['native_frame']['original_cameras']['overview']['frame'] for r in rows], [1, 2])
            wrong = FakeRig(site)
            wrong.scene['case_id'] = 'another case'
            with self.assertRaisesRegex(ValueError, 'camera rig uses another'):
                run_carla(World(), Ego(1), Actor(9), [], [], packet_path=site,
                          case_suffix='stopped_leftmost_clear', output_path=root / 'wrong-trace.jsonl',
                          count=1, observation_from_frame=lambda frame, scene: Observation(
                              frame['time_s'], 1, 0, 'steady_red_alone', False, False),
                          control_factory=lambda **kw: kw, camera_rig=wrong)


if __name__ == '__main__':
    unittest.main()
