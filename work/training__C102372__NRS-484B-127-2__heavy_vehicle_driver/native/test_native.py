"""CPU checks of the exact C102372 proposed Native construction."""
import json
from pathlib import Path
import unittest

from engineering import CANDIDATES,parameters,speed_requests
from geometry import check as check_geometry
from runner import cameras,check


def config(case,candidate):
    return {'case_id':'training__C102372__NRS-484B-127-2__heavy_vehicle_driver__'+case,
            'case_suffix':case,'candidate_id':candidate,
            'law_id':'NRS-484B-127-2','cell_id':'C102372','actor':'heavy_vehicle_driver',
            'rate_hz':20,'duration_s':24,'knobs':parameters(case,candidate)['knobs'],
            'cameras':[{key:camera[key] for key in ('name','width','height')}
                       for camera in cameras(candidate)],'recording_description':{'channels':[
                {'name':name} for name in ('ego_body_pose','lead_body_pose',
                                          'surface_gap_m','camera_frame_join')]}}


class NativeTruckPlan(unittest.TestCase):
    def test_geometry_and_eight_preflights(self):
        self.assertTrue(check_geometry()['passed'])
        for case in ('probe_1','probe_2'):
            for candidate in CANDIDATES:
                self.assertTrue(check(config(case,candidate))['passed'])

    def test_three_fallback_knobs_are_distinct(self):
        base=parameters('probe_1','primary')['knobs']
        for candidate in CANDIDATES[1:]:
            self.assertNotEqual(base,parameters('probe_1',candidate)['knobs'])
        self.assertEqual(4,len({json.dumps(parameters('probe_1',c)['knobs'],sort_keys=True)
                                for c in CANDIDATES}))

    def test_speed_controls_change_requests(self):
        base=speed_requests(parameters('probe_1','primary'),160.)
        slow=speed_requests(parameters('probe_1','fallback1'),160.)
        lead=speed_requests(parameters('probe_1','fallback2'),160.)
        self.assertLess(slow[0],base[0]);self.assertGreater(lead[1],base[1])

    def test_camera_fallback_changes_calibration(self):
        base=cameras('primary')[0];wide=cameras('fallback3')[0]
        self.assertGreater(wide['fov_deg'],base['fov_deg'])
        self.assertGreater(wide['xyz_m'][2],base['xyz_m'][2])

    def test_mismatched_identity_and_camera_rejected(self):
        wrong=config('probe_1','primary');wrong['cell_id']='C102304'
        with self.assertRaisesRegex(ValueError,'Frozen'):check(wrong)
        wrong=config('probe_1','primary');wrong['cameras'][0]['width']=5
        with self.assertRaisesRegex(ValueError,'camera'):check(wrong)


if __name__=='__main__':unittest.main()
