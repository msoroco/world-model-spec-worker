"""CPU preflight of the controlled conditions Native paths."""
import unittest
from conditions_engineering import ASSIGNMENT,CASES,CANDIDATES,check as check_plan,construction,request
from runner import cameras,check


class ConditionsNativeTests(unittest.TestCase):
    def config(self,case,candidate):
        return {'case_id':ASSIGNMENT+'__'+case,'case_suffix':case,
            'candidate_id':candidate,'law_id':'NRS-484B-127-2','cell_id':'C102372',
            'actor':'heavy_vehicle_driver','rate_hz':20,'duration_s':24,
            'knobs':construction(case,candidate)['knobs'],
            'cameras':[{key:camera[key] for key in ('name','width','height')}
                       for camera in cameras(candidate)],
            'recording_description':{'channels':[{'name':name} for name in
                ('ego_body_pose','lead_body_pose','surface_gap_m','camera_frame_join')]}}

    def test_eight_variants_keep_exact_native_window(self):
        self.assertTrue(check_plan()['passed'])
        for case in CASES:
            for candidate in CANDIDATES:
                value=check(self.config(case,candidate))
                self.assertTrue(value['passed'])
                self.assertFalse(value['native_imported'])

    def test_steady_and_braking_requests(self):
        self.assertEqual(request(CASES[0],'primary',200)['lead_speed_mps'],8)
        self.assertEqual(request(CASES[1],'primary',160)['lead_speed_mps'],8)
        self.assertEqual(request(CASES[1],'primary',200)['lead_speed_mps'],0)
        self.assertEqual(request(CASES[1],'fallback2',240)['ego_speed_mps'],0)
        self.assertEqual(request(CASES[1],'primary',240)['ego_speed_mps'],2)
        self.assertGreater(construction(CASES[1],'fallback3')['knobs']['obstacle_x_m'],
                           construction(CASES[1],'primary')['knobs']['obstacle_x_m'])

    def test_wrong_knob_rejected(self):
        config=self.config(CASES[1],'primary');config['knobs']['obstacle_x_m']=200
        with self.assertRaisesRegex(ValueError,'knobs differ'):check(config)


if __name__=='__main__':unittest.main()
