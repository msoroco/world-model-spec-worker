"""CPU fixture tests for original-versus-request source separation."""
import copy
import unittest
from parked_lamps import measure


class SourceMeterTest(unittest.TestCase):
    def rows(self):
        return [{
            'frame':i,'time_s':(i+1)/20,'source_kind':'original_native',
            'ego_center_xyz_m':[4.85,0,2.4],'ego_speed_mps':0,
            'requested_headlamp_lit':True,'requested_beam_state':'low_beam',
            'observed_light_state_bits':1,'observed_beam_state':'low_beam',
            'observed_parking_activity':'parked','observed_curb_lane_id':-2,
            'observed_footprint_xyz_m':[[4,0,2],[5,0,2],[4,1,2],[5,1,2]],
            'beam_pixel_review':{'status':'reviewed','source_path':'overview.mkv',
                'source_sha256':'a'*64,'aim_elevation_deg':-1.2,
                'relative_intensity':.5}
        } for i in range(600)]

    def test_source_shaped_positive(self):
        result=measure(self.rows(),'original_native')
        self.assertEqual(result['parked_activity_frames'],600)
        self.assertEqual(result['beam_pixel_reviewed_frames'],600)
        self.assertIsNone(result['legal_verdict'])
        self.assertFalse(result['beam_depressed_or_dimmed_observed'])

    def test_request_relabel_rejected(self):
        rows=self.rows()
        for row in rows:
            row.pop('observed_light_state_bits')
        with self.assertRaisesRegex(ValueError,'light-state'):
            measure(rows,'original_native')

    def test_missing_observation_rejected(self):
        alterations=(('observed_beam_state','requested'),
                     ('observed_parking_activity','requested'),
                     ('observed_curb_lane_id',None),
                     ('observed_footprint_xyz_m',None),
                     ('beam_pixel_review',{'status':'reviewed'}))
        for key,value in alterations:
            with self.subTest(key=key):
                rows=self.rows()
                rows[20][key]=value
                with self.assertRaises(ValueError):measure(rows,'original_native')

    def test_pending_is_not_completion(self):
        rows=self.rows()
        for row in rows:
            row['beam_pixel_review']={'status':'pending'}
            row['observed_parking_activity']='unknown'
        result=measure(rows,'original_native')
        self.assertEqual(result['beam_pixel_reviewed_frames'],0)
        self.assertFalse(result['actual_parking_observed'])


if __name__=='__main__':unittest.main()
