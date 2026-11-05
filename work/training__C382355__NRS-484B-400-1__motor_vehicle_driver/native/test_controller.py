"""Synthetic controller diagnostics for both C382355 approach lanes."""
import math
import unittest

from controller import EngineeringKnobs, PathController
from geometry import CASE_APPROACH_Y_M, route


class ControllerTest(unittest.TestCase):
    def test_nominal_and_two_motion_fallbacks(self):
        settings = {
            "primary": (route, EngineeringKnobs(max_steer_fraction=1.0)),
            "fallback1": (lambda y: route(y, turn_entry_x_m=-10), EngineeringKnobs(max_steer_fraction=1.0)),
            "fallback2": (route, EngineeringKnobs(lookahead_base_m=3.0,max_steer_fraction=1.0)),
        }
        for suffix, lateral in CASE_APPROACH_Y_M.items():
            for candidate, (make_route, knobs) in settings.items():
                with self.subTest(case=suffix, candidate=candidate):
                    path = [[x,-y] for x,y in make_route(lateral)]
                    controller = PathController(path, wheelbase_m=2.7,
                                                max_steer_deg=35, knobs=knobs)
                    x, y, yaw, speed = -50.0, -lateral, 0.0, 0.0
                    maximum_error = 0.0
                    for _ in range(600):
                        command = controller.step(position_xy_m=(x,y), yaw_rad=yaw,
                                                  speed_mps=speed, dt_s=.05)
                        self.assertLessEqual(abs(command["steer"]), knobs.max_steer_fraction)
                        self.assertFalse(command["throttle"] and command["brake"])
                        maximum_error = max(maximum_error, command["route_error_m"])
                        # A deliberately simple bicycle approximation. This is
                        # not CARLA physics or a physical completion proof.
                        acceleration = 2.3*command["throttle"] - 4.0*command["brake"] - .12*speed
                        speed = max(0, speed + acceleration*.05)
                        yaw += speed/2.7 * math.tan(command["steer"]*math.radians(35))*.05
                        x += speed*math.cos(yaw)*.05
                        y += speed*math.sin(yaw)*.05
                    self.assertGreater(y, 7, "Synthetic route did not reach destination leg")
                    self.assertLess(abs(x+5.25), 1.0)
                    self.assertLess(maximum_error, 2.0)

    def test_rejects_discontinuous_route_and_nonfinite_pose(self):
        with self.assertRaisesRegex(ValueError,"discontinuous"):
            PathController([[0,0],[.1,0],[3,0]],2.7,35,EngineeringKnobs())
        controller = PathController([[x,-y] for x,y in route(-5.25)],2.7,35,
                                    EngineeringKnobs(max_steer_fraction=1.0))
        with self.assertRaisesRegex(ValueError,"Invalid measured Native pose"):
            controller.step(position_xy_m=(float("nan"),0),yaw_rad=0,speed_mps=0,dt_s=.05)


if __name__ == "__main__":
    unittest.main()
