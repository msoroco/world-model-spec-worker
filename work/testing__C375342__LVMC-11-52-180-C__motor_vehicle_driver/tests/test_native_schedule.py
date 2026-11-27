import importlib.util
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
spec=importlib.util.spec_from_file_location('alley_native',ROOT/'alley_native.py')
native=importlib.util.module_from_spec(spec)
spec.loader.exec_module(native)


class NativeScheduleTests(unittest.TestCase):
    def test_departure_and_return_plan(self):
        intervals=((300,1260),(1860,2760))
        self.assertFalse(native.desired_station(280,intervals,15))
        self.assertTrue(native.desired_station(290,intervals,15))
        self.assertFalse(native.desired_station(1300,intervals,15))
        self.assertTrue(native.desired_station(1850,intervals,15))

    def test_observed_intervals_from_original_samples(self):
        flags=[False,True,True,False,False,True,True]
        rows=[{'sample_index':i,'frame':100+i,'time_s':i*.05,'parked_observed':v,'vehicle_actor_id':9} for i,v in enumerate(flags)]
        got=native.observed_intervals(rows,9)
        self.assertEqual(len(got),2)
        self.assertAlmostEqual(got[0]['end_s']-got[0]['start_s'],.1)
        self.assertAlmostEqual(got[1]['end_s']-got[1]['start_s'],.1)
        rows[3]['frame']=200
        with self.assertRaisesRegex(ValueError,'frame or time gap'):
            native.observed_intervals(rows,9)

    def test_control_requests_actual_movement_and_hold(self):
        moving,state=native.drive_control((0,0),0,0,(12,0),True)
        self.assertEqual(state,'approach')
        self.assertGreater(moving['throttle'],0)
        held,state=native.drive_control((12,0),0,0,(12,0),True)
        self.assertEqual(state,'hold')
        self.assertTrue(held['hand_brake'])
        self.assertEqual(held['throttle'],0)


if __name__=='__main__':
    unittest.main()
