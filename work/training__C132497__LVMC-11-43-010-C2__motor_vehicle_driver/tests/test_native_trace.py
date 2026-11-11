"""The original capture trace is built from measured Native readback."""
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest

NATIVE=Path(__file__).resolve().parents[1]/'native'
sys.path.insert(0,str(NATIVE))
SPEC=importlib.util.spec_from_file_location('c132497_capture',NATIVE/'capture.py')
CAPTURE=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CAPTURE)


class TraceFromReadback(unittest.TestCase):
    def test_shared_measured_pose_velocity_join(self):
        measured={'center_native_xyz_m':[2.5,-7.0,1.5],
                  'velocity_native_xyz_mps':[3.0,4.0,0.0],
                  'yaw_deg':91.0,'speed_mps':5.0}
        row={'frame':1009,'time_s':.45,
             'position_m':measured['center_native_xyz_m'],
             'velocity_mps':measured['velocity_native_xyz_mps'],
             'speed_mps':5.0,'heading_deg':91.0}
        CAPTURE.check_shared_trace_point(row,1009,.45,measured)
        row['speed_mps']=6.0
        with self.assertRaisesRegex(ValueError,'trace differs'):
            CAPTURE.check_shared_trace_point(row,1009,.45,measured)

    def test_seal_requires_finished_capture_and_restoration(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            (root/'controller-intention.json').write_text('{"synthetic_test":true}\n')
            calls=[]
            def seal(*args,**kwargs):
                calls.append((args,kwargs))
                return {'synthetic_test_only':True}
            identity={'case_id':'reference','candidate_id':'primary'}
            closed={name:0 for name in CAPTURE.CAMERA_NAMES}
            args=(root,identity,240,{'restored':True},None,closed)
            self.assertEqual(CAPTURE.finish_original_capture(*args,seal=seal),
                             {'synthetic_test_only':True})
            self.assertEqual(len(calls),1)
            self.assertEqual(calls[0][1]['context']['controller_intention_sha256'],
                             CAPTURE.sha(root/'controller-intention.json'))
            self.assertEqual(calls[0][1]['encoder_exit_codes'],closed)
            for bad in ((239,{'restored':True},None,closed),
                        (240,{'restored':False},None,closed),
                        (240,{'restored':True},None,{'overview':0}),
                        (240,{'restored':True},None,{**closed,'approach':1}),
                        (240,{'restored':True},{'type':'test'},closed)):
                with self.assertRaises(RuntimeError):
                    CAPTURE.finish_original_capture(root,identity,*bad,seal=seal)
            self.assertEqual(len(calls),1)


if __name__=='__main__':unittest.main()
