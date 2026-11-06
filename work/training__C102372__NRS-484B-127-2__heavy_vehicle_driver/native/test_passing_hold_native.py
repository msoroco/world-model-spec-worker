"""CPU preflight of the law-preserving no-passing Native path."""
import unittest
from passing_hold_engineering import ASSIGNMENT,CANDIDATES,check as check_plan,construction,speed_requests
from runner import cameras,check


class PassingHoldNativeTests(unittest.TestCase):
    def config(self,candidate):
        return {'case_id':ASSIGNMENT+'__passing_hold','case_suffix':'passing_hold',
            'candidate_id':candidate,'law_id':'NRS-484B-127-2','cell_id':'C102372',
            'actor':'heavy_vehicle_driver','rate_hz':20,'duration_s':24,
            'knobs':construction(candidate)['knobs'],
            'cameras':[{key:camera[key] for key in ('name','width','height')}
                       for camera in cameras(candidate)],
            'recording_description':{'channels':[{'name':name} for name in
                ('ego_body_pose','lead_body_pose','body_clearance_m','camera_frame_join')]}}

    def test_four_variants_and_exact_capture(self):
        self.assertTrue(check_plan()['passed'])
        for candidate in CANDIDATES:
            result=check(self.config(candidate))
            self.assertTrue(result['passed'])
            self.assertFalse(result['native_imported'])

    def test_distinct_following_responses(self):
        self.assertLess(speed_requests('fallback1',26)[0],speed_requests('primary',26)[0])
        self.assertGreater(speed_requests('fallback2',26)[1],speed_requests('primary',26)[1])
        self.assertGreater(construction('fallback3')['knobs']['lane_center_gain'],
                           construction('primary')['knobs']['lane_center_gain'])

    def test_wrong_knob_rejected(self):
        config=self.config('primary');config['knobs']['target_gap_m']=4
        with self.assertRaisesRegex(ValueError,'knobs differ'):check(config)


if __name__=='__main__':unittest.main()
