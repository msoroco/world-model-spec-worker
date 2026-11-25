import struct
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from carla_adapter import CarlaCrossingAdapter, CAMERAS


class Obj:
    def __init__(self, **kw): self.__dict__.update(kw)


class Actor:
    id = 19
    def __init__(self): self.xy = [0.0, 0.0]; self.controls = []; self.destroyed = False
    def get_location(self): return Obj(x=self.xy[0], y=self.xy[1])
    def apply_control(self, control): self.controls.append(control)
    def destroy(self): self.destroyed = True


class Sensor:
    def __init__(self): self.callback = None; self.stopped = False
    def listen(self, callback): self.callback = callback
    def stop(self): self.stopped = True


class World:
    def __init__(self, sensors): self.sensors = sensors; self.frame = 0; self.actor = Actor()
    def get_settings(self): return Obj(synchronous_mode=True, fixed_delta_seconds=0.05)
    def try_spawn_actor(self, blueprint, transform): return self.actor
    def tick(self):
        self.frame += 1
        if self.actor.controls:
            control = self.actor.controls[-1]
            self.actor.xy[0] += control.speed * control.direction.x * .05
            self.actor.xy[1] += control.speed * control.direction.y * .05
        for sensor in self.sensors.values():
            sensor.callback(Obj(frame=self.frame, width=2, height=2, raw_data=b'\x00\x00\xff\xff' * 4))
        return self.frame
    def get_snapshot(self): return Obj(frame=self.frame, timestamp=Obj(elapsed_seconds=self.frame * .05))


class CarlaAdapterTests(unittest.TestCase):
    def factories(self):
        return {'blueprint_library': Obj(find=lambda name: name),
                'location_factory': lambda **kw: Obj(**kw),
                'transform_factory': lambda location: Obj(location=location),
                'vector_factory': lambda **kw: Obj(**kw),
                'walker_control_factory': lambda **kw: Obj(**kw), 'spawn_z': 0.4}

    def test_original_world_camera_and_controller(self):
        sensors = {name: Sensor() for name in CAMERAS}
        world = World(sensors)
        adapter = CarlaCrossingAdapter(world, sensors,
                                      lambda w, frame: [{'id': 'device', 'state': 'permissive'}],
                                      **self.factories())
        actor = adapter.spawn_walker('walker.pedestrian.0001', (0, 0))
        adapter.drive_walker_route(actor, [(0, 0), (2, 0)])
        tick = adapter.tick()
        self.assertEqual(tick['original_frame'], 1)
        self.assertGreater(actor.get_location().x, 0)
        self.assertEqual(set(adapter.camera_frames()), set(CAMERAS))
        self.assertEqual(adapter.read_devices()[0]['id'], 'device')
        for camera in CAMERAS:
            self.assertTrue(adapter.camera_png(camera, 1).startswith(b'\x89PNG\r\n\x1a\n'))
        with self.assertRaisesRegex(ValueError, 'unavailable'):
            adapter.camera_png('overview', 2)
        adapter.destroy_actor(actor)
        self.assertTrue(actor.destroyed)
        self.assertTrue(all(s.stopped for s in sensors.values()))

    def test_sync_and_four_camera_contracts(self):
        sensors = {name: Sensor() for name in CAMERAS}
        world = World(sensors)
        with self.assertRaisesRegex(ValueError, 'four named'):
            CarlaCrossingAdapter(world, {'overview': sensors['overview']}, lambda w, f: [], **self.factories())
        world.get_settings = lambda: Obj(synchronous_mode=False, fixed_delta_seconds=0.05)
        with self.assertRaisesRegex(ValueError, 'synchronous'):
            CarlaCrossingAdapter(world, sensors, lambda w, f: [], **self.factories())


if __name__ == '__main__':
    unittest.main()
