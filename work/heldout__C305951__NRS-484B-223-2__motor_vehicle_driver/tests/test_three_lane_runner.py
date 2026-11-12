import sys
import unittest
from pathlib import Path
from types import SimpleNamespace as NS

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from three_lane_runner import CASE, check_config, control_step
from three_lane_camera import CAMERAS, ThreeLaneCameraCapture


def config():
    return {'selected_case_id': CASE, 'law_id': 'NRS-484B-223-2',
            'cell_id': 'C305951', 'actor': 'motor_vehicle_driver',
            'rate_hz': 20, 'frames': 160, 'duration_s': 8, 'lane_role': 'right',
            'cameras': [{'name': name} for name in CAMERAS]}


class ThreeLaneRunnerTests(unittest.TestCase):
    def test_exact_identity_and_four_cameras(self):
        check_config(config())
        wrong = config()
        wrong['selected_case_id'] = CASE.replace('right_baseline', 'center_default')
        with self.assertRaisesRegex(ValueError, 'identity'):
            check_config(wrong)
        center = config()
        center['selected_case_id'] = CASE.replace('right_baseline', 'center_default')
        center['lane_role'] = 'center'
        check_config(center)
        wrong = config()
        wrong['cameras'] = wrong['cameras'][:-1]
        with self.assertRaisesRegex(ValueError, 'Four named'):
            check_config(wrong)

    def test_feedback_targets_route_without_unbounded_control(self):
        control = control_step((0, 0), (1, 0), (0, 0), (10, 1))
        self.assertGreater(control['throttle'], 0)
        self.assertGreater(control['steer'], 0)
        self.assertLessEqual(control['steer'], 0.55)
        with self.assertRaisesRegex(ValueError, 'too close'):
            control_step((0, 0), (1, 0), (0, 0), (0.1, 0))

    def test_four_original_camera_sensors_are_spawned_and_frame_joined(self):
        sensors = []
        class Blueprint:
            def __init__(self):
                self.attributes = {}
            def set_attribute(self, key, value):
                self.attributes[key] = value
        class Sensor:
            def listen(self, callback):
                self.callback = callback
            def stop(self):
                self.stopped = True
            def destroy(self):
                self.destroyed = True
        class World:
            def get_blueprint_library(self):
                return NS(find=lambda name: Blueprint())
            def spawn_actor(self, blueprint, transform, attach_to):
                sensor = Sensor()
                sensors.append((sensor, blueprint, transform, attach_to))
                return sensor
        carla = NS(Transform=lambda location, rotation: NS(location=location, rotation=rotation),
                   Location=lambda *xyz: xyz, Rotation=lambda *xyz: xyz)
        writes = {name: [] for name in CAMERAS}
        sinks = {name: NS(write=lambda image, key=name: writes[key].append(image.frame))
                 for name in CAMERAS}
        capture = ThreeLaneCameraCapture(World(), carla, object(), sinks)
        self.assertEqual(len(sensors), 4)
        for name, (sensor, blueprint, _, _) in zip(CAMERAS, sensors):
            width, height = CAMERAS[name][2]
            self.assertEqual(blueprint.attributes['image_size_x'], str(width))
            sensor.callback(NS(frame=41, width=width, height=height))
        capture.wait_for_frame(41, timeout_s=0.1)
        self.assertEqual(capture.verify([41]), {name: 1 for name in CAMERAS})
        capture.close()
        self.assertTrue(all(sensor.stopped and sensor.destroyed for sensor, _, _, _ in sensors))


if __name__ == '__main__':
    unittest.main()
