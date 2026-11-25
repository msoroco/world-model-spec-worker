import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRATCH = ROOT.parents[1] / '.runtime-work'
sys.path.insert(0, str(ROOT))
import native_crest_runner as runner
from saved_crest_audit import ASSIGNMENT


class Blueprint:
    def __init__(self):
        self.attributes = {}

    def set_attribute(self, name, value):
        self.attributes[name] = value


class Actor:
    def __init__(self, ident, station):
        self.id = ident
        self.station = station
        self.destroyed = False
        self.bounding_box = SimpleNamespace(extent=SimpleNamespace(x=1, y=1))

    def get_transform(self):
        return SimpleNamespace(location=SimpleNamespace(x=self.station, y=self.id, z=0),
                               rotation=SimpleNamespace(yaw=0))

    def get_velocity(self):
        return SimpleNamespace(x=10, y=0, z=0)

    def apply_control(self, control):
        self.control = control

    def destroy(self):
        self.destroyed = True


class Camera(Actor):
    def listen(self, callback):
        self.callback = callback

    def stop(self):
        self.stopped = True


class World:
    def __init__(self, wrong_camera=False, fail_restore=False):
        self.settings = SimpleNamespace(synchronous_mode=False,
            fixed_delta_seconds=None, no_rendering_mode=True)
        self.ego = Actor(1, 170)
        self.other = Actor(2, 270)
        self.cameras = []
        self.frame = 99
        self.wrong_camera = wrong_camera
        self.fail_restore = fail_restore
        self.map = SimpleNamespace(
            to_opendrive=lambda: '<OpenDRIVE/>',
            get_waypoint_xodr=lambda road, lane, station: SimpleNamespace(
                transform=SimpleNamespace(location=SimpleNamespace(
                    x=station, y=lane, z=0))),
            get_waypoint=self.waypoint)

    def waypoint(self, location, **kwargs):
        lane = -1 if location.y == 1 else 1
        return SimpleNamespace(road_id=603, lane_id=lane, s=location.x)

    def get_map(self):
        return self.map

    def get_settings(self):
        s = self.settings
        return SimpleNamespace(synchronous_mode=s.synchronous_mode,
            fixed_delta_seconds=s.fixed_delta_seconds,
            no_rendering_mode=s.no_rendering_mode)

    def apply_settings(self, settings):
        if not (self.fail_restore and settings.synchronous_mode is False):
            self.settings = settings

    def get_blueprint_library(self):
        return SimpleNamespace(find=lambda name: Blueprint())

    def try_spawn_actor(self, blueprint, transform):
        return self.ego if transform.location.y == -1 else self.other

    def spawn_actor(self, blueprint, pose, attach_to):
        camera = Camera(10 + len(self.cameras), 0)
        self.cameras.append(camera)
        return camera

    def tick(self):
        self.frame += 1
        self.ego.station += 0.5
        for index, camera in enumerate(self.cameras):
            frame = self.frame - 1 if self.wrong_camera and index == 3 else self.frame
            camera.callback(SimpleNamespace(frame=frame, width=1, height=1,
                                            raw_data=b'xxxx'))
        return self.frame


class Encoder:
    all = []

    def __init__(self, path, width, height):
        self.path = path
        self.count = 0
        self.closed = False
        self.all.append(self)

    def append(self, image):
        self.count += 1

    def close(self):
        self.closed = True

    def abort(self):
        self.closed = True


class NativeRunnerTests(unittest.TestCase):
    def test_ffv1_encoder_retains_complete_original_bgra_stream(self):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as temp:
            path = Path(temp) / 'original.mkv'
            encoder = runner.FFV1Encoder(path, 2, 2)
            for index in range(900):
                encoder.append(SimpleNamespace(width=2, height=2,
                    raw_data=bytes((index % 256, 0, 255, 255)) * 4))
            receipt = encoder.close()
            self.assertEqual(receipt['frame_count'], 900)
            self.assertEqual(receipt['sha256'], hashlib.sha256(path.read_bytes()).hexdigest())
            probe = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0',
                '-show_entries', 'stream=codec_name,width,height',
                '-of', 'json', str(path)], capture_output=True, text=True, check=True)
            stream = json.loads(probe.stdout)['streams'][0]
            self.assertEqual((stream['codec_name'], stream['width'], stream['height']),
                             ('ffv1', 2, 2))

    def test_ffv1_encoder_rejects_wrong_dimensions_and_incomplete_stream(self):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as temp:
            encoder = runner.FFV1Encoder(Path(temp) / 'short.mkv', 2, 2)
            with self.assertRaisesRegex(ValueError, 'dimensions'):
                encoder.append(SimpleNamespace(width=3, height=2, raw_data=b'bad'))
            encoder.append(SimpleNamespace(width=2, height=2, raw_data=b'\x00' * 16))
            with self.assertRaisesRegex(ValueError, 'incomplete'):
                encoder.close()

    def run_case(self, wrong_camera=False, fail_restore=False):
        world = World(wrong_camera, fail_restore)
        bound = {'world': world, 'native_map_sha256': 'a' * 64,
            'native_spawn_stations': {'ego_road_s_m': 170.0,
                                      'other_road_s_m': 270.0},
            'routes': {'forward': {'waypoints': [
                {'s_m': s, 'z_m': z, 'source_ref': 'map'}
                for s, z in ((0, 0), (10, 2), (20, 4), (30, 2), (40, 0))],
                'crest_station_m': 20},
                'opposing': {'waypoints': [
                    {'s_m': s, 'source_ref': 'map'} for s in (0, 10, 20, 30, 40)]}}}
        carla = SimpleNamespace(VehicleControl=lambda **kw: SimpleNamespace(**kw),
            Transform=lambda location, rotation: SimpleNamespace(location=location,
                                                                  rotation=rotation),
            Location=lambda **kw: SimpleNamespace(**kw),
            Rotation=lambda **kw: SimpleNamespace(**kw),
            LaneType=SimpleNamespace(Driving='driving'))
        with tempfile.TemporaryDirectory(dir=SCRATCH) as temp:
            source = Path(temp) / 'map.xodr'
            source.write_text('map')
            limit = Path(temp) / 'limit.json'
            limit.write_text(json.dumps({'road_id': 603,
                'source_kind': 'reviewed_original_limit',
                'prescribed_limit_mps': 15}) + '\n')
            limit_ref = f'limit.json:{hashlib.sha256(limit.read_bytes()).hexdigest()}'
            captured = {}
            def inspect_assemble(spec, destination, *, expected_case):
                captured['context'] = json.loads(Path(spec['sources']['context_source']).read_text())
                captured['grade'] = json.loads(Path(spec['sources']['grade_source']).read_text())
                captured['other_route'] = json.loads(Path(spec['sources']['other_route_source']).read_text())
                captured['spec'] = spec
                Path(destination).mkdir()
                return {'case_id': expected_case}
            with patch.object(runner, 'load_and_bind', return_value=bound), \
                 patch.object(runner, 'FRAME_COUNT', 3), \
                 patch.object(runner.NativeTickRecorder, 'write') as write, \
                 patch.object(runner, 'assemble', side_effect=inspect_assemble) as assemble:
                arguments = dict(map_path=source, map_sha256='b' * 64,
                    case_id=ASSIGNMENT + '__early_decrease',
                    destination=Path(temp) / 'saved', limit_mps=15,
                    limit_source_ref=limit_ref, limit_path=limit,
                    capture_ref='native-001',
                    scratch_root=Path(temp), encoder_factory=Encoder)
                if wrong_camera:
                    with self.assertRaisesRegex(ValueError, 'camera world-frame'):
                        runner.capture(None, carla, **arguments)
                    assemble.assert_not_called()
                elif fail_restore:
                    with self.assertRaisesRegex(ValueError, 'not restored'):
                        runner.capture(None, carla, **arguments)
                    self.assertFalse(arguments['destination'].exists())
                else:
                    self.assertEqual(runner.capture(None, carla, **arguments),
                                     {'case_id': ASSIGNMENT + '__early_decrease'})
                    write.assert_called_once()
                    spec = captured['spec']
                    self.assertEqual(spec['profile'], 'early_decrease')
                    self.assertEqual(spec['native_map_sha256'], 'a' * 64)
                    self.assertEqual(captured['context']['limit_source_ref'],
                                     f'reviewed-limit.json:{hashlib.sha256(limit.read_bytes()).hexdigest()}')
                    self.assertEqual(captured['context']['map_grade_sha256'],
                                     hashlib.sha256((json.dumps(captured['grade'],
                                         sort_keys=True, allow_nan=False) + '\n').encode()).hexdigest())
                    self.assertEqual([row['s_m'] for row in captured['other_route']],
                                     [40, 30, 20, 10, 0])
            if not fail_restore:
                self.assertFalse(world.settings.synchronous_mode)
            self.assertTrue(world.ego.destroyed)
            self.assertTrue(world.other.destroyed)
            self.assertTrue(all(camera.destroyed for camera in world.cameras))
            self.assertTrue(all(encoder.closed for encoder in Encoder.all))

    def test_three_tick_lifecycle_and_source_binding(self):
        self.run_case()

    def test_mismatched_camera_aborts_and_restores_world(self):
        self.run_case(wrong_camera=True)

    def test_failed_world_restoration_never_publishes_capture(self):
        self.run_case(fail_restore=True)

    def test_exact_case_and_scratch_required_before_loading(self):
        with self.assertRaisesRegex(ValueError, 'exact selected crest'):
            runner.capture(None, None, map_path='missing', map_sha256='a' * 64,
                case_id=ASSIGNMENT + '__bad', destination='missing', limit_mps=15,
                limit_source_ref='reviewed', limit_path='missing',
                capture_ref='run', scratch_root=SCRATCH)


if __name__ == '__main__':
    unittest.main()
