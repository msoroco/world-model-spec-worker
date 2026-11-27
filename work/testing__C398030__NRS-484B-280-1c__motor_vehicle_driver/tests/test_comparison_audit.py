"""Independent school comparison isolation and response measurement checks."""
import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from comparison_audit import audit


def receipt(case, delay):
    fixed = {'law_id': 'NRS-484B-280-1c', 'cell_id': 'C398030',
             'actor_id': 'motor_vehicle_driver', 'map_sha256': 'a'*64,
             'school_site_sha256': 'b'*64, 'fixed_scene_sha256': 'c'*64,
             'participant_classes': ['motor_vehicle', 'pedestrian'],
             'camera_contract_sha256': 'd'*64, 'duration_s': 30}
    return dict(fixed, case_id=ROOT.name+'__'+case, format='worker-delivery-audit',
                passed=True, response_policy=case, native_result_sha256='e'*64,
                frame_map_sha256='f'*64, video_sha256='1'*64,
                source_decode_receipt_sha256='2'*64, human_observation_claimed=False,
                legal_verdict=None, frame_count=9,
                measurement={'format':'worker-school-setting-pedestrian-measurements',
                             'sources':{k:'3'*64 for k in ('school-site.json','map.xodr',
                               'encounter-history.jsonl','video_frames.jsonl')},
                             'frame_count':9,'first_observation':{'frame':102},
                             'observed_response_delay_s':delay,
                             'legal_proper_caution_verdict':'unresolved'})


class ComparisonTests(unittest.TestCase):
    def setUp(self):
        self.prompt=receipt('prompt_brake',0.0)
        self.deferred=receipt('deferred_brake',.15)

    def test_positive(self):
        self.assertEqual(audit(self.prompt,self.deferred)['comparison_id'],
                         'school_observation_response_timing')

    def test_changed_school_site_rejected(self):
        other=copy.deepcopy(self.deferred)
        other['school_site_sha256']='4'*64
        with self.assertRaisesRegex(ValueError,'fixed condition differs'):
            audit(self.prompt,other)

    def test_unobserved_delay_rejected(self):
        other=copy.deepcopy(self.deferred)
        other['measurement']['observed_response_delay_s']=0.0
        with self.assertRaisesRegex(ValueError,'not physically observed'):
            audit(self.prompt,other)

    def test_missing_source_rejected(self):
        other=copy.deepcopy(self.deferred)
        del other['measurement']['sources']['school-site.json']
        with self.assertRaisesRegex(ValueError,'source-bound'):
            audit(self.prompt,other)


if __name__=='__main__': unittest.main()
