"""Build exact inline paragraph (c)(1) requests for pinned offline preflight."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
CASE=HERE.parent.parent


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def put(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')


TEST='''import unittest
import tempfile
from pathlib import Path
from check import check
from fixture_raw import build as fixture
from saved import prepare, measure

class ExactC1Boundary(unittest.TestCase):
    def test_source_and_inclusive_boundary(self):
        result=check(Path.cwd())
        expected=result['case_id'].endswith('__exception_3_2')
        self.assertEqual(result['requested_c1_within_200ft'],expected)
        self.assertFalse(result['c2_crossing_verified'])
        self.assertFalse(result['delivery_ready'])

    def test_pass_or_stop_request(self):
        result=check(Path.cwd())
        if result['candidate_id']=='fallback3':
            self.assertEqual(result['requested_right_ahead_frames'],0)
        else:
            self.assertGreater(result['requested_right_ahead_frames'],0)

    def test_synthetic_raw_to_saved_distance(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            fixture(Path.cwd(),root/'raw')
            receipt=prepare(Path.cwd(),root/'raw',root/'saved',True)
            measured=measure(Path.cwd(),root/'saved')
            self.assertEqual(receipt['source_kind'],'synthetic_cpu')
            self.assertFalse(measured['requested_distance_is_observed_distance'])
            self.assertFalse(measured['delivery_ready'])
'''


def build():
    cases=[]
    for witness in ('exception_3_1','exception_3_2'):
        candidates=[]
        for candidate in ('primary','fallback1','fallback2','fallback3'):
            bundle=HERE/'offline/bundles'/witness/candidate
            names=('assignment-source.json','case-plan.json','unmarked-pass.xodr',
                'config.json','requested-tracks.jsonl','build.py','check.py',
                'capture.py','measurement-contract.json','saved.py','fixture_raw.py')
            files=[{'path':name,'content':(bundle/name).read_text()} for name in names]
            files.append({'path':'tests/test_exact.py','content':TEST})
            construction={'case_id':CASE.name+'__'+witness,
                'cell_id':'C146314','law_id':'NRS-484B-210-1',
                'actor':'motor_vehicle_driver','entrypoint':'capture.py',
                'files':files,'status':'unselected_cpu_diagnostic',
                'recording_description':'Requested unmarked excursion at or 0.10 m above 200 feet; actual distance, right pass and paragraph c2 facts unobserved.'}
            path=HERE/'runtime-drafts'/witness/candidate/'construction.json'
            put(path,construction)
            candidates.append({'id':candidate,
                'construction':str(path.relative_to(HERE)),
                'construction_sha256':sha(path)})
        cases.append({'case_id':CASE.name+'__'+witness,
            'construction':candidates[0]['construction'],
            'construction_sha256':candidates[0]['construction_sha256'],
            'candidates':candidates[1:],
            'candidate_risk':{'status':'physical',
                'reason':'Original unmarked-pavement boundary distance, right pass and c2 crossing are unverified.'}})
    manifest={'format':'worker-unselected-draft-construction-manifest-v1',
        'assignment_id':CASE.name,'status':'draft_not_selected',
        'cases':cases,'original_native_observed':False,'delivery_ready':False}
    put(HERE/'draft-execution-manifest.json',manifest)
    return manifest


if __name__=='__main__':
    m=build();print(json.dumps({'cases':len(m['cases']),
        'constructions':sum(1+len(x['candidates']) for x in m['cases'])}))
