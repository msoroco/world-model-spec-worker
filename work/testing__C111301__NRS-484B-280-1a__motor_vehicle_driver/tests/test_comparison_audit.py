import importlib.util
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('wheelchair_comparison',ROOT/'comparison_audit.py')
comparison=importlib.util.module_from_spec(spec);spec.loader.exec_module(comparison)


def record(suffix,gap,brake):
    return {'format':'worker-delivery-audit','passed':True,
       'case_id':ROOT.name+'__'+suffix,
       'law_id':'NRS-484B-280-1a','cell_id':'C111301','actor_id':'driver',
       'map_sha256':'map','ego_route_sha256':'route','wheelchair_identity_sha256':'person-chair',
       'controller_policy_sha256':'policy',
       'camera_contract_sha256':'cameras','duration_s':30,'frame_count':20,
       'native_result_sha256':'result','frame_map_sha256':'frames',
       'video_sha256':'video','source_decode_receipt_sha256':'decode',
       'measurement':{'format':'worker-manual-wheelchair-measurements',
                      'sources':{'encounter-history.jsonl':'history',
                                 'intersection-context.json':'context'},
                      'frame_count':20,'minimum_surface_gap_m':gap,
                      'first_brake_frame':brake,'contact_frames':[],
                      'legal_due_care_verdict':'unresolved'}}


class ComparisonTests(unittest.TestCase):
    def test_accepts_physical_path_difference_without_legal_label(self):
        clear=record('wheelchair_clear_path',8,None)
        crossing=record('wheelchair_crossing',1,120)
        self.assertTrue(comparison.audit(clear,crossing)['passed'])
        changed=record('wheelchair_crossing',1,120);changed['ego_route_sha256']='other'
        with self.assertRaisesRegex(ValueError,'fixed condition differs'):
            comparison.audit(clear,changed)
        changed=record('wheelchair_crossing',1,120);changed['controller_policy_sha256']='other'
        with self.assertRaisesRegex(ValueError,'fixed condition differs'):
            comparison.audit(clear,changed)
        changed=record('wheelchair_crossing',1,None)
        with self.assertRaisesRegex(ValueError,'brake response'):
            comparison.audit(clear,changed)
        changed=record('wheelchair_crossing',1,120);changed['measurement']['contact_frames']=[115]
        with self.assertRaisesRegex(ValueError,'contact'):
            comparison.audit(clear,changed)
        changed=record('wheelchair_crossing',1,120);changed.pop('source_decode_receipt_sha256')
        with self.assertRaisesRegex(ValueError,'source-audited delivery receipt'):
            comparison.audit(clear,changed)


if __name__=='__main__':unittest.main()
