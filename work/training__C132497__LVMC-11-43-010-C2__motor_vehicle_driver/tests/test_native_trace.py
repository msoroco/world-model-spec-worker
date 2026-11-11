"""The original capture trace is built from measured Native readback."""
import importlib.util
from pathlib import Path
import sys
import unittest

NATIVE=Path(__file__).resolve().parents[1]/'native'
sys.path.insert(0,str(NATIVE))
SPEC=importlib.util.spec_from_file_location('c132497_capture',NATIVE/'capture.py')
CAPTURE=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CAPTURE)


class TraceFromReadback(unittest.TestCase):
    def test_measured_pose_velocity_and_applied_control(self):
        class Control:
            throttle=.3;brake=.1;hand_brake=False
        measured={'center_native_xyz_m':[2.5,-7.0,1.5],
                  'velocity_native_xyz_mps':[3.0,4.0,0.0],
                  'yaw_deg':91.0,'speed_mps':5.0}
        row=CAPTURE.trace_point(1009,.45,measured,Control())
        self.assertEqual(row['position_m'],measured['center_native_xyz_m'])
        self.assertEqual(row['velocity_mps'],measured['velocity_native_xyz_mps'])
        self.assertEqual(row['speed_mps'],measured['speed_mps'])
        self.assertEqual(row['control']['throttle'],.3)
        self.assertEqual(row['frame'],1009)


if __name__=='__main__':unittest.main()
