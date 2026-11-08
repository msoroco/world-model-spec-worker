"""Build exact inline paragraph (b) candidates for pinned offline preflight."""
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
from pathlib import Path
from check import check
from measure_saved import measure
from route_fallbacks import route

class ExactParagraphB(unittest.TestCase):
    def test_four_lane_parked_source(self):
        result=check(Path.cwd())
        self.assertTrue(result['four_lanes_authored'])
        self.assertFalse(result['original_native_observed'])
        self.assertFalse(result['delivery_ready'])

    def test_right_pass_or_stop(self):
        result=check(Path.cwd())
        if result['candidate_id']=='fallback3':
            self.assertEqual(result['requested_right_ahead_frames'],0)
        else:
            self.assertGreater(result['requested_right_ahead_frames'],0)

    def test_synthetic_saved_measurement(self):
        result=measure(Path.cwd(),Path.cwd()/'saved')
        self.assertEqual(result['frames'],240)
        self.assertEqual(result['human_reviewed_condition_frames'],0)
        self.assertFalse(result['delivery_ready'])

    def test_measured_fallback_eligibility(self):
        result=route(Path.cwd(),Path.cwd()/'saved')
        self.assertEqual(set(result['triggers']),
                         {'fallback1','fallback2','fallback3'})
        self.assertIsNone(result['selected_fallback'])
'''


def build():
    cases=[]
    for witness in ('exception_2_1','exception_2_2'):
        candidates=[]
        for candidate in ('primary','fallback1','fallback2','fallback3'):
            bundle=HERE/'offline/bundles'/witness/candidate
            names=('config.json','requested-tracks.jsonl','four-lane-pass.xodr',
                'assignment-source.json','case-plan.json','measurement-contract.json',
                'build.py','check.py','capture.py','measure_saved.py',
                'route_fallbacks.py','saved/native-observed.jsonl',
                'saved/camera-frames.jsonl','saved/readback.json')
            files=[{'path':name,'content':(bundle/name).read_text()} for name in names]
            files.append({'path':'tests/test_exact.py','content':TEST})
            construction={'case_id':CASE.name+'__'+witness,
                'cell_id':'C146314','law_id':'NRS-484B-210-1',
                'actor':'motor_vehicle_driver','entrypoint':'capture.py',
                'files':files,'status':'unselected_cpu_diagnostic',
                'recording_description':'Four authored driving lanes with a requested parked vehicle absent or present; original Native conditions unobserved.'}
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
                'reason':'Generated four lanes, parked occupancy, clear pavement and original body pass are unverified.'}})
    manifest={'format':'worker-unselected-draft-construction-manifest-v1',
        'assignment_id':CASE.name,'status':'draft_not_selected',
        'cases':cases,'original_native_observed':False,'delivery_ready':False}
    put(HERE/'draft-execution-manifest.json',manifest)
    return manifest


if __name__=='__main__':
    m=build()
    print(json.dumps({'cases':len(m['cases']),
        'constructions':sum(1+len(c['candidates']) for c in m['cases'])}))
