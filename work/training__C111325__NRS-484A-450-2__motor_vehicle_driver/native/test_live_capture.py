"""CPU checks for the proposed original Native acquisition controller."""
import json
import unittest
from pathlib import Path

from live_capture import ASSIGNMENT, CAMERAS, FRAMES, command, requested_speed
from runner import check

HERE = Path(__file__).resolve().parent


class Point:
    def __init__(self, x=0.0, y=0.0, z=0.0):
        self.x, self.y, self.z = x, y, z


class Pose:
    def __init__(self, x=1.75, yaw=90.0):
        self.location = Point(x=x)
        self.rotation = type('Rotation', (), {'yaw': yaw})()


class Actor:
    def __init__(self, speed=4.0, x=1.75, yaw=90.0):
        self.pose, self.velocity = Pose(x, yaw), Point(y=speed)

    def get_transform(self):
        return self.pose

    def get_velocity(self):
        return self.velocity


class Carla:
    class VehicleControl:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)


class LiveCaptureCPU(unittest.TestCase):
    def test_exact_frame_and_geometry_preflight(self):
        data = json.loads((HERE.parent / 'draft-probe-1/construction.json').read_text())
        config = json.loads(next(f['content'] for f in data['files']
                                 if f['path'] == 'config.json'))
        result = check(config)
        self.assertEqual(result['frames'], FRAMES)
        self.assertEqual(len(result['cameras']), len(CAMERAS))

    def test_stop_is_a_request_and_margin_is_guarded(self):
        stop = ASSIGNMENT + '__probe_1'
        pass_through = ASSIGNMENT + '__probe_2'
        self.assertEqual(requested_speed(100, stop, -18), 0)
        self.assertEqual(requested_speed(179, stop, -18), 0)
        self.assertEqual(requested_speed(180, stop, -18), 4)
        self.assertEqual(requested_speed(140, pass_through, -10), 4)
        with self.assertRaisesRegex(RuntimeError, 'margin'):
            requested_speed(140, stop, -12)
        with self.assertRaisesRegex(ValueError, 'Exact frame'):
            requested_speed(600, stop, -18)

    def test_control_brakes_and_corrects_lateral_error(self):
        halt = command(Carla, Actor(speed=4), 0, 1.75)
        self.assertEqual((halt.throttle, halt.brake), (0, 1))
        travel = command(Carla, Actor(speed=0, x=0), 4, 1.75)
        self.assertGreater(travel.throttle, 0)
        self.assertGreater(travel.steer, 0)


if __name__ == '__main__':
    unittest.main()
