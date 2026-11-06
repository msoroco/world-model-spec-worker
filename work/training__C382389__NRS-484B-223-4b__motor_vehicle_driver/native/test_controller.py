"""Synthetic controller diagnostics for adjacent/right-only straight routes."""
import math
import unittest

from controller import EngineeringKnobs, PathController
from geometry import CASE_APPROACH_Y_M, route
from engineering import parameters


class ControllerTest(unittest.TestCase):
    def test_nominal_and_two_motion_fallbacks(self):
        for suffix, lateral in CASE_APPROACH_Y_M.items():
            for candidate in ('primary','fallback1','fallback2'):
                with self.subTest(case=suffix, candidate=candidate):
                    plan=parameters(suffix,candidate)
                    path=plan['native_route_xy_m'];knobs=plan['controller_knobs']
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
                    self.assertGreater(x,7,"Synthetic route did not travel straight through")
                    self.assertLess(abs(y+lateral),1.0)
                    self.assertLess(maximum_error, 2.0)

    def test_rejects_discontinuous_route_and_nonfinite_pose(self):
        with self.assertRaisesRegex(ValueError,"discontinuous"):
            PathController([[0,0],[.1,0],[3,0]],2.7,35,EngineeringKnobs())
        controller = PathController(route(-5.25),2.7,35,
                                    EngineeringKnobs(max_steer_fraction=1.0))
        with self.assertRaisesRegex(ValueError,"Invalid measured Native pose"):
            controller.step(position_xy_m=(float("nan"),0),yaw_rad=0,speed_mps=0,dt_s=.05)


if __name__ == "__main__":
    unittest.main()
