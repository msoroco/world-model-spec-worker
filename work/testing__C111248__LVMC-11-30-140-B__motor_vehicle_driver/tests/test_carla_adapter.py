import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

from PIL import Image
import io

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from carla_adapter import CarlaAdapter, CAMERAS


class Actor:
    def __init__(self, actor_id, x, extent):
        self.id = actor_id
        self.x = x
        self.bounding_box = SimpleNamespace(extent=SimpleNamespace(x=extent, y=0.5))
        self.controls = []

    def get_transform(self):
        return SimpleNamespace(location=SimpleNamespace(x=self.x, y=0))

    def get_velocity(self):
        return SimpleNamespace(x=2.0, y=0.0, z=0.0)

    def apply_control(self, control):
        self.controls.append(control)


class Sensor:
    def __init__(self):
        self.callback = None
        self.stopped = False
        self.destroyed = False

    def listen(self, callback):
        self.callback = callback

    def stop(self):
        self.stopped = True

    def destroy(self):
        self.destroyed = True


class World:
    def __init__(self, sensors):
        self.sensors = sensors
        self.frame = 99
        self.bad_camera = None

    def get_settings(self):
        return SimpleNamespace(synchronous_mode=True, fixed_delta_seconds=0.05)

    def tick(self):
        self.frame += 1
        for name, sensor in self.sensors.items():
            frame = self.frame + (1 if name == self.bad_camera else 0)
            sensor.callback(SimpleNamespace(frame=frame, width=2, height=2,
                                            raw_data=bytes([3, 2, 1, 255] * 4)))
        return self.frame

    def get_snapshot(self):
        return SimpleNamespace(frame=self.frame,
                               timestamp=SimpleNamespace(elapsed_seconds=
                                                         (self.frame - 99) * 0.05))


class CarlaAdapterTests(unittest.TestCase):
    def setUp(self):
        self.sensors = {name: Sensor() for name in CAMERAS}
        self.world = World(self.sensors)
        self.driver, self.person = Actor(10, 0, 2), Actor(20, 8, 0.3)
        self.context = lambda frame: {
            'frame': frame, 'driver_actor_id': 10, 'person_actor_id': 20,
            'person_in_path': True, 'person_clear': False,
            'contact': False, 'precaution': True}
        self.control = lambda **values: SimpleNamespace(**values)

    def adapter(self, reader=None):
        return CarlaAdapter(self.world, self.driver, self.person, self.sensors,
                            self.context if reader is None else reader,
                            self.control, timeout_seconds=0.01)

    def test_original_tick_body_proxy_and_four_camera_callbacks(self):
        adapter = self.adapter()
        frame, time_s = adapter.tick()
        self.assertEqual((frame, time_s), (100, 0.05))
        row = adapter.observe(frame)
        self.assertEqual(row['driver_speed_mps'], 2.0)
        self.assertGreater(row['body_gap_m'], 5)
        self.assertEqual(row['body_gap_kind'], 'circle_bound_proxy')
        for camera in CAMERAS:
            with Image.open(io.BytesIO(adapter.camera_png(camera, frame))) as image:
                self.assertEqual(image.size, (2, 2))
        adapter.apply_control({'throttle': 0.0, 'brake': 1.0})
        adapter.close()
        self.assertTrue(all(sensor.stopped for sensor in self.sensors.values()))
        self.assertEqual(self.driver.controls[-1].brake, 1.0)

    def test_pipeline_capture_uses_same_native_frame_and_closes(self):
        from native_factories import CaptureAdapter
        class Pipeline:
            def __init__(self):
                self.frames = []
                self.closed = False

            def capture(self, frame, time_s):
                self.frames.append((frame, time_s))

            def close(self):
                self.closed = True

        pipeline = Pipeline()
        collision = Sensor()
        adapter = CaptureAdapter(self.world, self.driver, self.person,
                                 self.sensors, collision, self.context,
                                 self.control, pipeline)
        frame, time_s = adapter.tick()
        adapter.observe(frame)
        self.assertEqual(pipeline.frames, [(frame, time_s)])
        adapter.close()
        self.assertTrue(pipeline.closed and collision.stopped and collision.destroyed)

    def test_wrong_actor_context_and_camera_frame_rejected(self):
        adapter = self.adapter(lambda frame: dict(self.context(frame), person_actor_id=999))
        frame, _ = adapter.tick()
        with self.assertRaisesRegex(ValueError, 'context identity'):
            adapter.observe(frame)
        adapter.close()
        self.sensors = {name: Sensor() for name in CAMERAS}
        self.world = World(self.sensors)
        self.world.bad_camera = 'rear'
        adapter = self.adapter()
        frame, _ = adapter.tick()
        with self.assertRaisesRegex(ValueError, 'camera frame'):
            adapter.camera_png('rear', frame)
        adapter.close()

    def test_unbounded_control_rejected_and_stopped(self):
        adapter = self.adapter()
        with self.assertRaisesRegex(ValueError, 'bounded'):
            adapter.apply_control({'throttle': 1.2, 'brake': 0.0})
        adapter.close()
        self.assertEqual(self.driver.controls[-1].brake, 1.0)

    def test_owned_original_cameras_destroyed_once(self):
        adapter = CarlaAdapter(self.world, self.driver, self.person, self.sensors,
                               self.context, self.control, destroy_sensors=True)
        adapter.close()
        controls = len(self.driver.controls)
        adapter.close()
        self.assertEqual(len(self.driver.controls), controls)
        self.assertTrue(all(sensor.stopped and sensor.destroyed
                            for sensor in self.sensors.values()))


if __name__ == '__main__':
    unittest.main()
