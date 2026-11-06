"""CPU preflight of the proposed passing-and-return Native capture path."""
import unittest
from passing_engineering import ASSIGNMENT,CANDIDATES,check as check_plan,construction,request
from runner import cameras,check


class PassingNativeTests(unittest.TestCase):
    def config(self,candidate):
        case=ASSIGNMENT+'__passing_overtake'
        return {'case_id':case,'case_suffix':'passing_overtake',
            'candidate_id':candidate,'law_id':'NRS-484B-127-2',
            'cell_id':'C102372','actor':'heavy_vehicle_driver',
            'rate_hz':20,'duration_s':24,'knobs':construction(candidate)['knobs'],
            'cameras':[{key:camera[key] for key in ('name','width','height')}
                       for camera in cameras(candidate)],
            'recording_description':{'channels':[{'name':name} for name in
                ('ego_body_pose','lead_body_pose','body_clearance_m','camera_frame_join')]}}

    def test_four_variants_keep_exact_case_and_native_window(self):
        self.assertTrue(check_plan()['passed'])
        for candidate in CANDIDATES:
            value=check(self.config(candidate))
            self.assertTrue(value['passed'])
            self.assertFalse(value['native_imported'])
            self.assertEqual(value['camera_names'],[
                'overview','ego_forward','lead_gap','crest_context'])

    def test_lateral_request_and_three_distinct_knobs(self):
        self.assertEqual(request('primary',0)['intended_lane_id'],-1)
        self.assertEqual(request('primary',200)['intended_lane_id'],1)
        self.assertEqual(request('primary',479)['intended_lane_id'],-1)
        self.assertGreater(request('fallback1',200)['ego_speed_mps'],
                           request('primary',200)['ego_speed_mps'])
        self.assertGreater(request('fallback2',200)['ego_target_y_m'],
                           request('primary',200)['ego_target_y_m'])
        self.assertNotEqual(request('fallback3',50)['ego_target_y_m'],
                            request('primary',50)['ego_target_y_m'])

    def test_wrong_knob_rejected(self):
        value=self.config('primary');value['knobs']['ego_speed_mps']=15
        with self.assertRaisesRegex(ValueError,'knobs differ'):check(value)


if __name__=='__main__':unittest.main()
