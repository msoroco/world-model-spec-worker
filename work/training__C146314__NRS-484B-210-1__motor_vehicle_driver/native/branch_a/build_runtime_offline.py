"""Build inline paragraph (a) constructions for pinned offline preflight."""
import hashlib
import json
from pathlib import Path

BRANCH=Path(__file__).resolve().parent
CASE=BRANCH.parent.parent
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')

TEST='''import unittest
from pathlib import Path
from check import check

class ExactParagraphA(unittest.TestCase):
    def test_source_and_signal_request(self):
        result=check(Path.cwd())
        self.assertTrue(result['source_bound'])
        self.assertFalse(result['delivery_ready'])

    def test_pass_or_stop_request(self):
        result=check(Path.cwd())
        if result['candidate_id']=='fallback3':
            self.assertEqual(result['requested_right_ahead_frames'],0)
        else:
            self.assertGreater(result['requested_right_ahead_frames'],0)
'''

def build():
    cases=[]
    for witness in ('exception_1_1','exception_1_2'):
        candidates=[]
        for candidate in ('primary','fallback1','fallback2','fallback3'):
            bundle=BRANCH/'offline/bundles'/witness/candidate
            names=('config.json','requested-tracks.jsonl','one-way-pass.xodr',
                'assignment-source.json','case-plan.json','measurement-contract.json',
                'check.py','capture.py')
            files=[{'path':name,'content':(bundle/name).read_text()} for name in names]
            files.append({'path':'tests/test_exact.py','content':TEST})
            construction={'case_id':CASE.name+'__'+witness,
                'cell_id':'C146314','law_id':'NRS-484B-210-1',
                'actor':'motor_vehicle_driver','entrypoint':'capture.py',
                'files':files,'status':'unselected_cpu_diagnostic',
                'recording_description':'Right pass with lead left indicator requested off or on; original light state and pixels are unobserved.'}
            path=BRANCH/'runtime-drafts'/witness/candidate/'construction.json'
            write(path,construction)
            candidates.append({'id':candidate,
                'construction':str(path.relative_to(BRANCH)),
                'construction_sha256':sha(path)})
        cases.append({'case_id':CASE.name+'__'+witness,
            'construction':candidates[0]['construction'],
            'construction_sha256':candidates[0]['construction_sha256'],
            'candidates':candidates[1:],
            'candidate_risk':{'status':'physical',
                'reason':'Original lead light state, indicator pixels and physical right pass are unverified.'}})
    manifest={'format':'worker-unselected-draft-construction-manifest-v1',
        'assignment_id':CASE.name,'status':'draft_not_selected',
        'cases':cases,'original_native_observed':False,'delivery_ready':False}
    write(BRANCH/'draft-execution-manifest.json',manifest)
    return manifest

if __name__=='__main__':
    m=build();print(json.dumps({'cases':len(m['cases']),
                                'constructions':sum(1+len(c['candidates']) for c in m['cases'])}))
