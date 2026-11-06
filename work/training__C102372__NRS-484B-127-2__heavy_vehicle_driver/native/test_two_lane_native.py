"""CPU preflight of all four proposed two-lane Native capture variants."""
import unittest
from engineering import CANDIDATES
from runner import authored_road,cameras,check,plan_for
from two_lane_exception import geometry_check,two_lane_open_drive

ASSIGNMENT='training__C102372__NRS-484B-127-2__heavy_vehicle_driver'


def config(candidate):
    return {'case_id':ASSIGNMENT+'__two_lane_exception',
            'case_suffix':'two_lane_exception','candidate_id':candidate,
            'law_id':'NRS-484B-127-2','cell_id':'C102372','actor':'heavy_vehicle_driver',
            'rate_hz':20,'duration_s':24,'knobs':plan_for('two_lane_exception',candidate)['knobs'],
            'cameras':[{key:camera[key] for key in ('name','width','height')}
                       for camera in cameras(candidate)],'recording_description':{'channels':[
                {'name':name} for name in ('ego_body_pose','lead_body_pose',
                                          'surface_gap_m','camera_frame_join')]}}


class TwoLaneNativePlan(unittest.TestCase):
    def test_four_variant_preflights(self):
        self.assertTrue(geometry_check()['passed'])
        self.assertEqual(two_lane_open_drive(),authored_road('two_lane_exception'))
        for candidate in CANDIDATES:
            value=check(config(candidate))
            self.assertTrue(value['passed'])
            self.assertEqual([-1,-2],value['authored_geometry']['same_direction_lane_ids'])
            self.assertFalse(value['physical_success_claimed'])

    def test_identity_and_knob_mismatch_rejected(self):
        bad=config('primary');bad['cell_id']='C102304'
        with self.assertRaisesRegex(ValueError,'Frozen'):check(bad)
        bad=config('fallback2');bad['knobs']['lead_target_speed_mps']=8
        with self.assertRaisesRegex(ValueError,'knobs'):check(bad)


if __name__=='__main__':unittest.main()
