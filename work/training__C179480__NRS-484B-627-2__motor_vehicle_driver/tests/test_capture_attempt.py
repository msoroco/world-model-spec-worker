import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest


folder = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(folder))
spec = importlib.util.spec_from_file_location('c179480_capture_attempt',
                                               folder / 'capture_attempt.py')
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)

measurement_spec = importlib.util.spec_from_file_location(
    'c179480_source_measurement_for_capture', folder / 'source_measurement.py')
measurement = importlib.util.module_from_spec(measurement_spec)
sys.modules[measurement_spec.name] = measurement
measurement_spec.loader.exec_module(measurement)


class FakeSensor:
    def __init__(self):
        self.callback = None
        self.destroyed = False

    def listen(self, callback):
        self.callback = callback

    def stop(self):
        pass

    def destroy(self):
        self.destroyed = True


class FakeBlueprint:
    def set_attribute(self, *_):
        pass


class FakeLibrary:
    def find(self, name):
        assert name == 'sensor.camera.rgb'
        return FakeBlueprint()


class FakeVehicle:
    def __init__(self, x):
        self.location = types.SimpleNamespace(x=x, y=0.0, z=0.0)
        self.velocity = types.SimpleNamespace(x=2.0, y=0.0, z=0.0)
        self.controls = []

    def get_transform(self):
        return types.SimpleNamespace(location=self.location,
                                     rotation=types.SimpleNamespace(yaw=0.0))

    def get_velocity(self):
        return self.velocity

    def apply_control(self, value):
        self.controls.append(value)


class FakeWorld:
    def __init__(self, stale_camera=False):
        self.settings = types.SimpleNamespace(synchronous_mode=False,
                                              fixed_delta_seconds=None)
        self.sensors = []
        self.frame = 100
        self.stale_camera = stale_camera
        self.applied = []

    def get_settings(self):
        return self.settings

    def apply_settings(self, value):
        self.settings = value
        self.applied.append((value.synchronous_mode, value.fixed_delta_seconds))

    def spawn_actor(self, blueprint, transform, attach_to):
        sensor = FakeSensor()
        self.sensors.append(sensor)
        return sensor

    def tick(self):
        self.frame += 1
        for index, sensor in enumerate(self.sensors):
            frame = self.frame - 1 if self.stale_camera and index == 2 else self.frame
            sensor.callback(types.SimpleNamespace(frame=frame))
        return self.frame

    def get_snapshot(self):
        return types.SimpleNamespace(timestamp=types.SimpleNamespace(
            elapsed_seconds=(self.frame - 100) / 20))


class MemorySink:
    def __init__(self, path, width, height):
        self.path = path
        self.images = []
        self.closed = False

    def write(self, image):
        self.images.append(image.frame)

    def close(self):
        self.closed = True


class CaptureAttemptTest(unittest.TestCase):
    def setUp(self):
        self.carla = types.SimpleNamespace(
            Location=lambda **kw: kw, Rotation=lambda **kw: kw,
            Transform=lambda *args: args,
            VehicleControl=lambda **kw: types.SimpleNamespace(**kw))

    def sample(self, world, ego, follower):
        return dict(ego_speed_mps=0.0, ego_on_roadway=True,
                    ego_lane_overlap=True, following_speed_mps=1.0,
                    following_gap_m=10.0)

    def test_four_streams_join_original_native_frames_and_restore(self):
        with tempfile.TemporaryDirectory() as tmp:
            world = FakeWorld()
            sinks = []
            def factory(*args):
                sink = MemorySink(*args)
                sinks.append(sink)
                return sink
            attempt = Path(tmp) / 'attempt'
            result = module.acquire_with_world_restore(
                world, self.carla, FakeVehicle(0), FakeVehicle(-12),
                FakeLibrary(), (15.0, 0.0), attempt, frames=3,
                sample=self.sample, sink_factory=factory)
            self.assertEqual(result['source_frames'], 3)
            self.assertFalse(result['physical_completion_claimed'])
            self.assertEqual(len(sinks), 4)
            self.assertTrue(all(sink.images == [101, 102, 103] for sink in sinks))
            self.assertTrue(all(sink.closed for sink in sinks))
            self.assertTrue(all(sensor.destroyed for sensor in world.sensors))
            self.assertFalse(world.settings.synchronous_mode)
            measured = measurement.analyze(attempt / 'native-actors.jsonl',
                                           attempt / 'video_frames.jsonl')
            self.assertEqual(measured['roadway_stop_frames'], [101, 102, 103])

    def test_materialized_bundle_directory_accepts_first_capture_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            attempt = Path(tmp)/'materialized'
            attempt.mkdir()
            (attempt/'config.json').write_text('{"case_id":"source-preserved"}\n')
            first = module.acquire_with_world_restore(
                FakeWorld(), self.carla, FakeVehicle(0), FakeVehicle(-12),
                FakeLibrary(), (15.0,0.0), attempt, frames=2,
                sample=self.sample, sink_factory=MemorySink)
            self.assertEqual(first['source_frames'],2)
            self.assertTrue((attempt/'config.json').is_file())
            with self.assertRaisesRegex(ValueError,'Retain prior original source'):
                module.acquire_with_world_restore(
                    FakeWorld(), self.carla, FakeVehicle(0), FakeVehicle(-12),
                    FakeLibrary(), (15.0,0.0), attempt, frames=2,
                    sample=self.sample, sink_factory=MemorySink)

    def test_stale_camera_rejected_and_world_restored(self):
        with tempfile.TemporaryDirectory() as tmp:
            world = FakeWorld(stale_camera=True)
            with self.assertRaisesRegex(ValueError, 'camera frame join'):
                module.acquire_with_world_restore(
                    world, self.carla, FakeVehicle(0), FakeVehicle(-12),
                    FakeLibrary(), (15.0, 0.0), Path(tmp) / 'attempt',
                    frames=2, sample=self.sample, sink_factory=MemorySink)
            self.assertFalse(world.settings.synchronous_mode)
            self.assertTrue(all(sensor.destroyed for sensor in world.sensors))

    def test_follower_gap_fallback_changes_actual_control_request(self):
        with tempfile.TemporaryDirectory() as tmp:
            world = FakeWorld()
            follower = FakeVehicle(-10)
            module.acquire_with_world_restore(
                world, self.carla, FakeVehicle(0), follower,
                FakeLibrary(), (15., 0.), Path(tmp)/'attempt',
                frames=2, sample=self.sample, sink_factory=MemorySink,
                follower_brake_gap_m=12., approach_speed_mps=2.5,
                stop_radius_m=1.25)
            self.assertEqual(len(follower.controls), 2)
            self.assertTrue(all(control.brake == 1.0 and control.throttle == 0.0
                                for control in follower.controls))

    def test_hazard_actor_receives_hold_brake_during_capture(self):
        with tempfile.TemporaryDirectory() as tmp:
            world = FakeWorld()
            hazard = FakeVehicle(8)
            module.acquire_with_world_restore(
                world,self.carla,FakeVehicle(0),FakeVehicle(-12),
                FakeLibrary(),(15.,0.),Path(tmp)/'attempt',frames=2,
                sample=self.sample,sink_factory=MemorySink,hazard=hazard)
            self.assertEqual(len(hazard.controls),2)
            self.assertTrue(all(control.brake == 1.0 and control.hand_brake
                                for control in hazard.controls))

    def test_ffv1_sink_encodes_original_bgra_frames(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'tiny.mkv'
            sink = module.FFV1Sink(path, 2, 2)
            for _ in range(3):
                sink.write(types.SimpleNamespace(raw_data=bytes([0, 0, 255, 255])*4))
            sink.close()
            probe = subprocess.run(['ffprobe', '-v', 'error', '-count_frames',
                                    '-select_streams', 'v:0', '-show_entries',
                                    'stream=nb_read_frames', '-of', 'json', str(path)],
                                   capture_output=True, text=True, check=True)
            self.assertEqual(json.loads(probe.stdout)['streams'][0]['nb_read_frames'], '3')

    def test_live_body_and_lane_readback_not_planned_overlap(self):
        class Actor(FakeVehicle):
            def __init__(self, x):
                super().__init__(x)
                self.bounding_box = types.SimpleNamespace(
                    get_world_vertices=lambda transform: [
                        types.SimpleNamespace(x=transform.location.x + dx,
                                              y=transform.location.y + dy,
                                              z=0.0)
                        for dx, dy in ((-2, -1), (-2, 1), (2, -1), (2, 1))])
        class Map:
            def get_waypoint(self, position, **kwargs):
                if not kwargs['project_to_road'] and abs(position.y) > 1.85:
                    return None
                return types.SimpleNamespace(
                    transform=types.SimpleNamespace(
                        location=types.SimpleNamespace(x=position.x, y=0.0),
                        rotation=types.SimpleNamespace(yaw=0.0)),
                    lane_width=3.7, road_id=7, lane_id=-1)
        world = types.SimpleNamespace(get_map=lambda: Map())
        carla = types.SimpleNamespace(
            LaneType=types.SimpleNamespace(Driving='driving'))
        ego, follower = Actor(0), Actor(-10)
        in_lane = module.sample_native(world, carla, ego, follower)
        self.assertTrue(in_lane['ego_lane_overlap'])
        self.assertTrue(in_lane['ego_on_roadway'])
        self.assertEqual(in_lane['ego_velocity_xyz_mps'], [2.0, 0.0, 0.0])
        self.assertEqual(len(in_lane['ego_body_vertices_xyz_m']), 4)
        self.assertTrue(in_lane['following_on_driving_lane'])
        hazard = Actor(8)
        hazard_state = module.sample_native(world,carla,ego,follower,hazard)
        self.assertEqual(hazard_state['hazard_state']['ego_center_gap_m'],8.)
        self.assertEqual(len(hazard_state['hazard_state']['body_vertices_xyz_m']),4)
        ego.location.y = 3.0
        on_shoulder = module.sample_native(world, carla, ego, follower)
        self.assertFalse(on_shoulder['ego_lane_overlap'])
        self.assertFalse(on_shoulder['ego_on_roadway'])
        self.assertEqual(on_shoulder['source_kind'],
                         'original_carla_actor_and_map_readback')


if __name__ == '__main__':
    unittest.main()
