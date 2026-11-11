"""CPU mechanics tests; these rows are synthetic and never accepted originals."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location('c132497_original_pair',
    ROOT/'native/audit_original_pair.py')
PAIR=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PAIR)


def config(name,lane,candidate='primary'):
    return {'assignment_id':PAIR.ASSIGNMENT,'law_id':'LVMC-11-43-010-C2',
        'cell_id':'C132497','actor':'motor_vehicle_driver','rate_hz':20,
        'frames':240,'road_sha256':'a'*64,'camera_policy':'standard',
        'requested_speed_mps':8,'pre_entry_dwell_s':0,
        'circulation_direction':'counterclockwise',
        'case_id':PAIR.CASES[name],'candidate_id':candidate,
        'requested_lane_id':lane,
        'controller_intention_sha256':('b' if name=='reference' else 'c')*64}


def actor_rows(lane):
    return [{'frame':i,'observed_road_id':20 if i<30 else 21 if i<210 else 22,
             'observed_lane_id':lane,'source_kind':'synthetic_native_sample'}
            for i in range(240)]


class OriginalPairMechanics(unittest.TestCase):
    def setUp(self):
        self.configs={'reference':config('reference',-2),
                      'contrast':config('contrast',-1)}
        self.observed={'reference':actor_rows(-2),'contrast':actor_rows(-1)}

    def test_source_independent_pair_shape(self):
        result=PAIR.compare(self.configs,self.observed)
        self.assertEqual(result['measured']['reference']['first_exit_lane_id'],-2)
        self.assertEqual(result['measured']['contrast']['first_exit_lane_id'],-1)
        self.assertEqual(result['candidate_id'],'primary')

    def test_changed_fixed_speed_rejected(self):
        changed=copy.deepcopy(self.configs)
        changed['contrast']['requested_speed_mps']=9
        with self.assertRaisesRegex(ValueError,'fixed condition changed: requested_speed_mps'):
            PAIR.compare(changed,self.observed)

    def test_changed_candidate_rejected(self):
        changed=copy.deepcopy(self.configs)
        changed['contrast']['candidate_id']='fallback1'
        with self.assertRaisesRegex(ValueError,'candidate policies differ'):
            PAIR.compare(changed,self.observed)

    def test_wrong_observed_exit_lane_rejected(self):
        changed=copy.deepcopy(self.observed)
        changed['contrast'][209]['observed_lane_id']=-2
        with self.assertRaisesRegex(ValueError,'observed exit lane differs'):
            PAIR.compare(self.configs,changed)

    def test_missing_exit_rejected(self):
        changed=copy.deepcopy(self.observed)
        for row in changed['contrast'][210:]:row['observed_road_id']=21
        with self.assertRaisesRegex(ValueError,'right-exit phases incomplete'):
            PAIR.compare(self.configs,changed)

    def test_missing_receipt_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            root=Path(root)
            with self.assertRaisesRegex(ValueError,'Missing original comparison source'):
                PAIR.audit(root/'reference',root/'contrast',root/'missing-reference.json',
                           root/'missing-contrast.json',root/'output.json')

    def test_synthetic_provenance_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            root=Path(root)
            receipts={}
            for name,lane in (('reference',-2),('contrast',-1)):
                attempt=root/name;attempt.mkdir()
                cfg=config(name,lane)
                intention={'source_kind':'authored_controller_route_before_motion',
                           'turn_direction':'right','intended_exit_road_id':22,
                           'case_id':cfg['case_id'],'candidate_id':'primary'}
                (attempt/'config.json').write_text(json.dumps(cfg))
                (attempt/'controller-intention.json').write_text(json.dumps(intention))
                (attempt/'native-raw-actors.jsonl').write_text(''.join(
                    json.dumps(row)+'\n' for row in actor_rows(lane)))
                (attempt/'video_frames.jsonl').write_text('{}\n')
                hashes={name:PAIR.sha(attempt/name) for name in
                    ('config.json','controller-intention.json','native-raw-actors.jsonl',
                     'video_frames.jsonl')}
                receipt={'format':'worker-delivery-audit','passed':True,
                         'case_id':cfg['case_id'],'candidate_id':'primary',
                         'original_native_observed':True,
                         'checks':{key:True for key in PAIR.RECEIPT_CHECKS},
                         'sources':hashes}
                path=root/(name+'-receipt.json');path.write_text(json.dumps(receipt))
                receipts[name]=path
            with self.assertRaisesRegex(ValueError,'provenance or intention differs'):
                PAIR.audit(root/'reference',root/'contrast',receipts['reference'],
                           receipts['contrast'],root/'output.json')


if __name__=='__main__':unittest.main()
