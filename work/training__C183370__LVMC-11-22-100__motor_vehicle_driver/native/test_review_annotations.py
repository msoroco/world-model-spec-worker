import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from review_annotations import evaluate


def sources():
    analysis = {
        'format':'c183370-original-source-analysis-v1',
        'source_kind':'original_carla_capture',
        'case':'reference',
        'observations':{'source_first_frame':100,'source_last_frame':699,
                        'source_frames':600,
                        'pavement_footprint_contact_frames':[300]},
        'camera_sources':[{'name':name,'source_sha256':str(i)*64}
                          for i,name in enumerate(
                              ('overview','approach','reference_corner','driver_reference'),1)],
    }
    review = {'reviewer_id':'independent-reviewer',
              'source_analysis_sha256':'a'*64,
              'annotations':{
                  'warning_act':{
                      'observed':True,'camera':'approach','camera_sha256':'2'*64,
                      'frame_interval':[390,410],
                      'observation':'Person visibly directs vehicles away from this pavement.',
                      'warning_content':'against_riding_or_driving_over_identified_pavement'},
                  'newly_repaired_pavement':{
                      'observed':True,'camera':'overview','camera_sha256':'1'*64,
                      'frame_interval':[380,420],
                      'observation':'The identified surface shows newly repaired pavement.',
                      'condition':'newly_repaired'},
                  'paving_employee_exception':{'status':'unreviewed'},
              }}
    return analysis,review


class ReviewTest(unittest.TestCase):
    def test_overlapping_source_review_binds_contact_without_verdict(self):
        analysis,review=sources()
        result=evaluate(analysis,review,analysis_sha256='a'*64)
        self.assertEqual(result['contact_during_reviewed_context_frames'],[400])
        self.assertTrue(result['requested_contact_context_observed'])
        self.assertFalse(result['legal_verdict_claimed'])
        self.assertFalse(result['physical_acceptance_claimed'])

    def test_proximity_does_not_substitute_for_warning(self):
        analysis,review=sources()
        review['annotations']['warning_act']['observed']=False
        with self.assertRaisesRegex(ValueError,'affirmatively observed'):
            evaluate(analysis,review,analysis_sha256='a'*64)

    def test_camera_hash_and_time_binding(self):
        analysis,review=sources()
        wrong=copy.deepcopy(review)
        wrong['annotations']['warning_act']['camera_sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'hash differs'):
            evaluate(analysis,wrong,analysis_sha256='a'*64)
        wrong=copy.deepcopy(review)
        wrong['annotations']['warning_act']['frame_interval']=[700,710]
        with self.assertRaisesRegex(ValueError,'outside original source'):
            evaluate(analysis,wrong,analysis_sha256='a'*64)

    def test_disjoint_warning_and_repair_rejected(self):
        analysis,review=sources()
        review['annotations']['warning_act']['frame_interval']=[500,510]
        with self.assertRaisesRegex(ValueError,'do not overlap'):
            evaluate(analysis,review,analysis_sha256='a'*64)

    def test_employee_exception_needs_independent_source(self):
        analysis,review=sources()
        review['annotations']['paving_employee_exception']={'status':'not_actually_engaged'}
        with self.assertRaisesRegex(ValueError,'independent source'):
            evaluate(analysis,review,analysis_sha256='a'*64)


if __name__=='__main__':
    unittest.main()
