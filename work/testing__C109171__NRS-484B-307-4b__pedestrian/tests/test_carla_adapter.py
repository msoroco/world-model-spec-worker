import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from carla_adapter import CarlaAdapter
from native_scene import SourceError


class Sensor:
    def __init__(self):
        self.callback = None
        self.stopped = False
    def listen(self, callback):
        self.callback = callback
    def stop(self):
        self.stopped = True


class Walker:
    def __init__(self):
        self.controls = []
    def get_location(self):
        return SimpleNamespace(x=-2.0, y=1.0)
    def apply_control(self, control):
        self.controls.append(control)


class World:
    def __init__(self, sensors, omit=None, drift=None):
        self.sensors = sensors
        self.frame = 100
        self.omit = omit
        self.drift = drift
    def get_settings(self):
        return SimpleNamespace(synchronous_mode=True, fixed_delta_seconds=0.05)
    def tick(self):
        self.frame += 1
        for name, sensor in self.sensors.items():
            if name != self.omit:
                frame = self.frame + (1 if name == self.drift else 0)
                image = SimpleNamespace(frame=frame, width=2, height=2,
                                        raw_data=bytes([1, 2, 3, 255] * 4))
                sensor.callback(image)
        return self.frame
    def get_snapshot(self):
        return SimpleNamespace(frame=self.frame,
                               timestamp=SimpleNamespace(elapsed_seconds=self.frame * 0.05))


class CarlaAdapterTest(unittest.TestCase):
    def setUp(self):
        self.sensors = {name: Sensor() for name in ('front', 'left', 'right', 'rear')}
        self.walker = Walker()
        self.site = {'pedestrian_route_xy': [[-2, 1], [-1, 1], [1, 1], [3, 1]]}
        self.factory = lambda **kw: SimpleNamespace(**kw)
        self.vector = lambda *xyz: xyz

    def make(self, world):
        return CarlaAdapter(world, self.walker, self.sensors,
                            lambda frame, world_frame: {'frame': frame,
                                'sim_time_seconds': world_frame * 0.05,
                                'world_frame': world_frame,
                                'pedestrian_xy': [-2.0, 1.0]},
                            self.factory, self.vector, timeout_seconds=0.01)

    def test_reads_original_camera_callbacks_and_stops(self):
        adapter = self.make(World(self.sensors))
        adapter.start(self.site, 'assignment__arrow_early_entry')
        result = adapter.read(0)
        self.assertEqual(result['event']['world_frame'], 101)
        self.assertEqual(set(result['cameras']), set(self.sensors))
        for item in result['cameras'].values():
            self.assertTrue(item['png'].startswith(b'\x89PNG'))
        self.assertGreater(self.walker.controls[0].speed, 0)
        adapter.close()
        self.assertTrue(all(sensor.stopped for sensor in self.sensors.values()))
        self.assertEqual(self.walker.controls[-1].speed, 0.0)

    def test_wait_case_does_not_move(self):
        adapter = self.make(World(self.sensors))
        adapter.start(self.site, 'assignment__arrow_wait')
        adapter.read(0)
        self.assertEqual(self.walker.controls[0].speed, 0.0)
        adapter.close()

    def test_reject_missing_camera_callback(self):
        adapter = self.make(World(self.sensors, omit='rear'))
        adapter.start(self.site, 'assignment__arrow_wait')
        with self.assertRaisesRegex(SourceError, 'missing original camera callback'):
            adapter.read(0)
        adapter.close()

    def test_reject_mismatched_world_frame(self):
        adapter = self.make(World(self.sensors, drift='left'))
        adapter.start(self.site, 'assignment__arrow_wait')
        with self.assertRaisesRegex(SourceError, 'world-frame drift'):
            adapter.read(0)
        adapter.close()

    def test_reject_async_world(self):
        world = World(self.sensors)
        world.get_settings = lambda: SimpleNamespace(synchronous_mode=False,
                                                     fixed_delta_seconds=0.05)
        with self.assertRaisesRegex(SourceError, 'synchronous 20 Hz'):
            self.make(world).start(self.site, 'assignment__arrow_wait')

    def test_reject_invented_pedestrian_position(self):
        adapter = self.make(World(self.sensors))
        adapter.original_state_reader = lambda frame, world_frame: {
            'frame': frame, 'world_frame': world_frame,
            'sim_time_seconds': world_frame * 0.05,
            'pedestrian_xy': [1.0, 1.0]}
        adapter.start(self.site, 'assignment__arrow_wait')
        with self.assertRaisesRegex(SourceError, 'pedestrian position'):
            adapter.read(0)
        adapter.close()

    def test_reject_invented_simulation_time(self):
        adapter = self.make(World(self.sensors))
        adapter.original_state_reader = lambda frame, world_frame: {
            'frame': frame, 'world_frame': world_frame,
            'sim_time_seconds': 999.0,
            'pedestrian_xy': [-2.0, 1.0]}
        adapter.start(self.site, 'assignment__arrow_wait')
        with self.assertRaisesRegex(SourceError, 'snapshot time'):
            adapter.read(0)
        adapter.close()

    def test_reject_snapshot_frame_drift(self):
        world = World(self.sensors)
        world.get_snapshot = lambda: SimpleNamespace(frame=world.frame + 1,
            timestamp=SimpleNamespace(elapsed_seconds=world.frame * 0.05))
        adapter = self.make(world)
        adapter.start(self.site, 'assignment__arrow_wait')
        with self.assertRaisesRegex(SourceError, 'snapshot world-frame drift'):
            adapter.read(0)
        adapter.close()


if __name__ == '__main__':
    unittest.main()
