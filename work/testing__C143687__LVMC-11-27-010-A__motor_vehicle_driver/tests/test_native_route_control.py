import importlib.util
import unittest
from pathlib import Path

from test_trail import site_for, trail


MODULE = Path(__file__).resolve().parents[1] / 'native_route_control.py'
spec = importlib.util.spec_from_file_location('trail_native_route_control', MODULE)
controller = importlib.util.module_from_spec(spec)
spec.loader.exec_module(controller)


class Carla:
    @staticmethod
    def VehicleControl(**kwargs):
        return kwargs


class Vehicle:
    def __init__(self, x, y, yaw=0, vx=0):
        self.x, self.y, self.yaw, self.vx = x, y, yaw, vx
        self.control = None

    def get_transform(self):
        loc = type('Location', (), {'x': self.x, 'y': self.y})()
        rot = type('Rotation', (), {'yaw': self.yaw})()
        return type('Transform', (), {'location': loc, 'rotation': rot})()

    def get_velocity(self):
        return type('Velocity', (), {'x': self.vx, 'y': 0})()

    def apply_control(self, control):
        self.control = control


class NativeRouteControlTests(unittest.TestCase):
    def test_requests_forward_route_and_brakes_at_endpoint(self):
        site = site_for(trail.CASES[0])
        vehicle = Vehicle(1, 2)
        result = controller.command(vehicle, site, Carla, 0)
        self.assertEqual(result['target_xy'], [10, 2])
        self.assertGreater(vehicle.control['throttle'], 0)
        self.assertEqual(vehicle.control['brake'], 0)
        vehicle = Vehicle(18.7, 2, vx=3)
        result = controller.command(vehicle, site, Carla, 899)
        self.assertLess(result['final_distance_m'], 1.5)
        self.assertEqual(vehicle.control['throttle'], 0)
        self.assertGreater(vehicle.control['brake'], 0)

    def test_steering_and_nonfinite_readback(self):
        site = site_for(trail.CASES[0])
        vehicle = Vehicle(1, 1, yaw=0)
        controller.command(vehicle, site, Carla, 0)
        self.assertGreater(vehicle.control['steer'], 0)
        vehicle = Vehicle(float('nan'), 2)
        with self.assertRaisesRegex(ValueError, 'nonfinite'):
            controller.command(vehicle, site, Carla, 1)


if __name__ == '__main__':
    unittest.main()
