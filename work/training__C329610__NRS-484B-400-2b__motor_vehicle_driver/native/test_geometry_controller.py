import math
import unittest
from controller import EngineeringKnobs,PathController
from geometry import EXIT_X_M,check,route


class ExitSideTest(unittest.TestCase):
    def test_authored_surface_and_distinct_destination_sides(self):
        report=check();self.assertTrue(report['passed'])
        self.assertEqual({r['destination_side'] for r in report['cases'].values()},
                         {'right_of_centerline','left_of_centerline'})
        self.assertFalse(report['native_verified'])

    def test_synthetic_controller_follows_both_exit_routes(self):
        for suffix,exit_x in EXIT_X_M.items():
            with self.subTest(case=suffix):
                native_route=[[x,-y] for x,y in route(exit_x)]
                controller=PathController(native_route,2.7,35,EngineeringKnobs())
                x,y,yaw,speed=-50,1.75,0,0
                for _ in range(600):
                    request=controller.step(position_xy_m=(x,y),yaw_rad=yaw,
                                            speed_mps=speed,dt_s=.05)
                    acceleration=2.3*request['throttle']-4.0*request['brake']-.12*speed
                    speed=max(0,speed+acceleration*.05)
                    yaw+=speed/2.7*math.tan(request['steer']*math.radians(35))*.05
                    x+=speed*math.cos(yaw)*.05;y+=speed*math.sin(yaw)*.05
                self.assertLess(y,-7)
                self.assertLess(abs(x-exit_x),1)


if __name__=='__main__':unittest.main()
