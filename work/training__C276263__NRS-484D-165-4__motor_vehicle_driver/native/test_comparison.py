"""Independent positive/negative structural comparison CPU fixtures."""
import copy
import unittest
from comparison_audit import PREFIX,audit

class ComparisonTest(unittest.TestCase):
    def pair(self):
        context={'road_sha256':'a'*64,'ego_blueprint_id':'vehicle.lamp.test',
                 'curb_lane_id':-2,'duration_s':30,'rate_hz':20,
                 'source_cameras':['overview','approach','reference_corner',
                                   'driver_reference']}
        base={'frames':600,'fixed_context':context,'parked_activity_frames':600,
              'beam_pixel_reviewed_frames':600,'source_sha256':{'road.xodr':'a'*64},
              'beam_aim_elevation_deg_range':[-1.2,-1.1],
              'relative_intensity_range':[.5,.6],
              'original_native_observed':False,'legal_verdict':None}
        a=copy.deepcopy(base);b=copy.deepcopy(base)
        a.update(case_id=PREFIX+'probe_a',requested_beam_state='low_beam',
                 observed_beam_states=['low_beam'])
        b.update(case_id=PREFIX+'probe_b',requested_beam_state='high_beam',
                 observed_beam_states=['high_beam'])
        return a,b

    def test_structural_contrast_no_physical_claim(self):
        result=audit(*self.pair())
        self.assertFalse(result['original_native_observed'])
        self.assertIsNone(result['legal_verdict'])

    def test_missing_or_changed_fixed_source_rejected(self):
        for mutation in ('road','blueprint','camera','activity','beam','pixels'):
            a,b=self.pair()
            if mutation=='road':b['fixed_context']['road_sha256']='b'*64
            elif mutation=='blueprint':b['fixed_context']['ego_blueprint_id']='vehicle.other'
            elif mutation=='camera':b['fixed_context']['source_cameras'].pop()
            elif mutation=='activity':b['parked_activity_frames']=599
            elif mutation=='beam':b['observed_beam_states']=['low_beam']
            else:b['beam_pixel_reviewed_frames']=599
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):
                audit(a,b)

if __name__=='__main__':unittest.main()
