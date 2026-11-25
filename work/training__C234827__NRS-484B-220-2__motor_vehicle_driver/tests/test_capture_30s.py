"""Focused CPU checks for the prospective full-duration Native capture path."""
import math
import types
import unittest

from capture_30s import camera_plan,steering


class FakeCarla:
    @staticmethod
    def VehicleControl(**values):return types.SimpleNamespace(**values)


class FakeEgo:
    def __init__(self,yaw=0.0):self.yaw=yaw

    def get_transform(self):
        return types.SimpleNamespace(location=types.SimpleNamespace(x=0.0,y=-23.75),
                                     rotation=types.SimpleNamespace(yaw=self.yaw))

    def get_velocity(self):return types.SimpleNamespace(x=0.0,y=0.0,z=0.0)


class CaptureContract(unittest.TestCase):
    def test_four_source_profile(self):
        cameras=camera_plan()
        self.assertEqual([c[0] for c in cameras],
                         ['overview','approach','reference_corner','driver_reference'])
        self.assertEqual([(c[1],c[2]) for c in cameras],
                         [(1920,1080),(1280,720),(1280,720),(1280,720)])
        self.assertEqual([c[5] for c in cameras],['world','world','world','ego'])

    def test_opposite_rotation_requests_produce_opposite_steering(self):
        ego=FakeEgo()
        ccw=steering(FakeCarla,ego,{'ego_x_m':1.0,'ego_y_m':-23.7},8.0)
        cw=steering(FakeCarla,FakeEgo(180),{'ego_x_m':-1.0,'ego_y_m':-23.7},8.0)
        self.assertGreater(ccw.steer,0)
        self.assertLess(cw.steer,0)
        self.assertEqual(ccw.throttle,cw.throttle)
        self.assertTrue(math.isfinite(ccw.steer))


if __name__=='__main__':unittest.main()
