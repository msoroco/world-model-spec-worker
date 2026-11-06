"""Exact bundle tests for map, source measurement and fallback identity."""
import json
from pathlib import Path
import tempfile
import unittest

from engineering import CANDIDATES,parameters
from geometry import check,open_drive
from measure import synthetic,measure,sha
from runner_capture import bicycle_velocity_x,motorist_hold
from trigger_measure import projected_margin

HERE=Path(__file__).resolve().parent
ROAD=HERE/'road.xodr' if (HERE/'road.xodr').is_file() else HERE.parent/'road.xodr'

class NativeDraftTests(unittest.TestCase):
    def test_two_through_connectors(self):
        value=check()
        self.assertTrue(value['passed'])
        self.assertEqual(value['route_samples'],801)
        self.assertEqual(value['motor_route_samples'],801)
        if ROAD.is_file():
            self.assertEqual(open_drive(),ROAD.read_text().strip())

    def test_source_bound_interaction(self):
        outcomes=[]
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);road=root/'road.xodr';road.write_text(open_drive())
            for case in ('witness_1','witness_2'):
                path=root/(case+'.json')
                path.write_text(json.dumps(synthetic(case,sha(road)))+'\n')
                result=measure(path,sha(path),road)
                self.assertFalse(result['intent_physically_verified'])
                self.assertFalse(result['legal_interference_claimed'])
                outcomes.append(result['motor_braking_frames'])
        self.assertEqual(outcomes,[0,175])

    def test_distinct_law_preserving_knobs(self):
        plans=[parameters('witness_1',candidate) for candidate in CANDIDATES]
        self.assertEqual(len({json.dumps(p['knobs'],sort_keys=True) for p in plans}),4)
        self.assertTrue(all(p['law_id']=='NRS-484B-270-7a' and p['cell_id']=='C111294'
                            and not p['intent_asserted'] for p in plans))
        self.assertEqual(len({p['fallback_trigger']['metric'] for p in plans[1:]}),3)

    def test_fallback_controls_change_original_capture_requests(self):
        primary=parameters('witness_2','primary')['knobs']
        shorter=parameters('witness_2','fallback1')['knobs']
        buffer=parameters('witness_2','fallback2')['knobs']
        self.assertGreater(abs(bicycle_velocity_x(2.25,2.6,shorter['bicycle_route_tracking_lookahead_m'])),
                           abs(bicycle_velocity_x(2.25,2.6,primary['bicycle_route_tracking_lookahead_m'])))
        self.assertFalse(motorist_hold(265,'witness_2',primary['motorist_clearance_buffer_s']))
        self.assertTrue(motorist_hold(265,'witness_2',buffer['motorist_clearance_buffer_s']))
        self.assertFalse(motorist_hold(265,'witness_1',buffer['motorist_clearance_buffer_s']))

    def test_wider_overview_fov_increases_projected_body_margin(self):
        base={'pose':{'xyz_m':[0,0,5],'yaw_deg':0,'pitch_deg':0},
              'width':1920,'height':1080,'fov_deg':90}
        point=[10,7,5]
        narrow=projected_margin(point,base)
        wide=projected_margin(point,{**base,'fov_deg':105})
        self.assertGreater(wide,narrow)

if __name__=='__main__':unittest.main()
