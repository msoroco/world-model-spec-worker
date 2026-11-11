import sys
import unittest
from pathlib import Path
from types import SimpleNamespace as NS

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))
from u_turn_control import UTurnController

ROUTE = [[-10, 0, 0], [0, 0, 0], [4, 3, 0], [-5, 5, 0], [-10, 5, 0]]


def actor(x, y, yaw, speed):
    captured = []
    value = NS(get_transform=lambda: NS(location=NS(x=x, y=y), rotation=NS(yaw=yaw)),
               get_velocity=lambda: NS(x=speed, y=0, z=0),
               apply_control=lambda control: captured.append(control))
    return value, captured


class UTurnControlTests(unittest.TestCase):
    def test_requests_route_then_requires_measured_exit_and_reversal(self):
        controller = UTurnController(ROUTE)
        carla = NS(VehicleControl=lambda: NS())
        start, controls = actor(-10, 0, 0, 0)
        first = controller.step(carla, start, 0)
        self.assertFalse(first["geometric_completion_observed"])
        self.assertGreater(controls[0].throttle, 0)
        near, _ = actor(-10, 5, 0, 0)
        self.assertFalse(controller.step(carla, near, 10)["geometric_completion_observed"])
        exit_actor, controls = actor(-10, 5, 180, 0)
        last = controller.step(carla, exit_actor, 20)
        self.assertTrue(last["geometric_completion_observed"])
        self.assertEqual(last["brake"], 1.0)
        self.assertEqual(controls[0].throttle, 0)

    def test_timeout_and_bad_route(self):
        with self.assertRaisesRegex(ValueError, "route required"):
            UTurnController([[0, 0, 0]])
        controller = UTurnController(ROUTE, max_frame=10)
        carla = NS(VehicleControl=lambda: NS())
        start, _ = actor(-10, 0, 0, 0)
        with self.assertRaisesRegex(ValueError, "exceeded planned capture"):
            controller.step(carla, start, 11)


if __name__ == "__main__":
    unittest.main()
