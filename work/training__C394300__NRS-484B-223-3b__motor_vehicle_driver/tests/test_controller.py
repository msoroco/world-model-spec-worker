"""Synthetic bicycle diagnostics for the proposed center-lane turn controller."""
import math
import unittest

from controller import EngineeringKnobs,PathController
from geometry import TARGET_FEET,route
from engineering import parameters


class ControllerTest(unittest.TestCase):
    def test_nominal_and_motion_fallback_requests(self):
        for suffix in TARGET_FEET:
            for candidate in ('primary','fallback1','fallback2'):
                with self.subTest(case=suffix,candidate=candidate):
                    plan=parameters(suffix,candidate)
                    path=plan['native_route_xy_m'];knobs=plan['controller_knobs']
                    controller=PathController(path,2.7,35,knobs)
                    x,y,yaw,speed=plan['route_start_x_m'],3.5,0.0,0.0
                    maximum_error=0.0
                    for _ in range(480):
                        command=controller.step(position_xy_m=(x,y),yaw_rad=yaw,
                                                speed_mps=speed,dt_s=.05)
                        self.assertLessEqual(abs(command['steer']),knobs.max_steer_fraction)
                        self.assertFalse(command['throttle'] and command['brake'])
                        maximum_error=max(maximum_error,command['route_error_m'])
                        # A simple diagnostic model, not CARLA dynamics.
                        acceleration=2.3*command['throttle']-4.0*command['brake']-.12*speed
                        speed=max(0,speed+acceleration*.05)
                        yaw+=speed/2.7*math.tan(command['steer']*math.radians(35))*.05
                        x+=speed*math.cos(yaw)*.05;y+=speed*math.sin(yaw)*.05
                    self.assertGreater(x,-10,'Synthetic model did not reach the turn')
                    self.assertLess(y,-5,'Synthetic model did not enter the destination')
                    self.assertLess(maximum_error,2.5)

    def test_rejects_discontinuous_route_and_nonfinite_pose(self):
        with self.assertRaisesRegex(ValueError,'discontinuous'):
            PathController([[0,0],[.1,0],[3,0]],2.7,35,EngineeringKnobs())
        controller=PathController([[x,-y] for x,y in route('witness_1')],2.7,35,
                                  EngineeringKnobs(max_steer_fraction=1.0))
        with self.assertRaisesRegex(ValueError,'Invalid measured Native pose'):
            controller.step(position_xy_m=(float('nan'),0),yaw_rad=0,speed_mps=0,dt_s=.05)


if __name__=='__main__':unittest.main()
