"""Build exact inline constructions for the pinned runtime offline preflight."""
import hashlib
import json
from pathlib import Path

CASE=Path(__file__).resolve().parent
NATIVE=CASE/'native'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')

TEST='''import json
from pathlib import Path
import unittest
import tempfile
from fixture_raw import build as build_raw
from prepare_raw import prepare
from measure_prepared import measure as measure_raw
from statutory_scope import BOOL_FACTS, evaluate
from check import check
from measure_saved import measure
from route_fallbacks import route

class ExactConstruction(unittest.TestCase):
    def test_request_and_frozen_sources(self):
        result=check(Path.cwd())
        self.assertTrue(result['source_bound'])
        self.assertFalse(result['delivery_ready'])

    def test_saved_measurement(self):
        result=measure(Path.cwd(),Path.cwd()/'saved')
        self.assertEqual(result['frames'],240)
        self.assertFalse(result['original_native_observed'])
        self.assertFalse(result['delivery_ready'])

    def test_measured_fallbacks(self):
        result=route(Path.cwd(),Path.cwd()/'saved')
        self.assertEqual(set(result['triggers']),{'fallback1','fallback2','fallback3'})
        self.assertIsNone(result['selected_fallback'])

    def test_raw_to_saved_cpu(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            build_raw(Path.cwd(),root/'raw')
            receipt=prepare(Path.cwd(),root/'raw',root/'prepared',synthetic_cpu=True)
            self.assertEqual(receipt['source_kind'],'synthetic_cpu')
            self.assertFalse(receipt['delivery_ready'])
            measured=measure_raw(Path.cwd(),root/'prepared')
            self.assertEqual(measured['frames'],240)
            self.assertFalse(measured['delivery_ready'])

    def test_statutory_source_and_or_alternatives(self):
        facts={key:False for key in BOOL_FACTS}
        facts.update(overtakes_on_right=True,pavement_unobstructed=True,
            pavement_unmarked=True,no_parked_vehicles=True,
            no_intersection_or_private_way_crossed=True,
            unmarked_excursion_m=61.01)
        result=evaluate(Path.cwd()/'case-plan.json',facts)
        self.assertTrue(result['branches']['1c'])
        self.assertIsNone(result['legal_verdict'])
'''


def build():
    entries=[]
    for witness in ('witness_1','witness_2'):
        candidates=[]
        for candidate in ('primary','fallback1','fallback2','fallback3'):
            bundle=CASE/'offline'/'bundles'/witness/candidate
            files=[]
            for name in ('config.json','requested-tracks.jsonl','one-way-pass.xodr',
                'assignment-source.json','case-plan.json','measurement-contract.json',
                'check.py','capture.py','fixture_raw.py','prepare_raw.py',
                'measure_prepared.py',
                'statutory_scope.py',
                'measure_saved.py','route_fallbacks.py',
                'saved/native-observed.jsonl','saved/camera-frames.jsonl',
                'saved/readback.json'):
                files.append({'path':name,'content':(bundle/name).read_text()})
            files.append({'path':'tests/test_exact.py','content':TEST})
            construction={'case_id':CASE.name+'__'+witness,
                'cell_id':'C146314','law_id':'NRS-484B-210-1',
                'actor':'motor_vehicle_driver','entrypoint':'capture.py',
                'files':files,'status':'unselected_cpu_diagnostic',
                'recording_description':'Original ego, lead and curb-object pose plus synchronized forward and overview video are required; no original capture was run.'}
            path=NATIVE/'runtime-drafts'/witness/candidate/'construction.json'
            write(path,construction)
            selected={'id':candidate,
                'construction':str(path.relative_to(CASE)),
                'construction_sha256':sha(path)}
            candidates.append(selected)
        entry={'case_id':CASE.name+'__'+witness,
               'construction':candidates[0]['construction'],
               'construction_sha256':candidates[0]['construction_sha256'],
               'candidates':candidates[1:],
               'candidate_risk':{'status':'physical',
                   'reason':'Original CARLA pass, object clearance, one-way designation and original pixels are unverified.'}}
        entries.append(entry)
    manifest={'format':'worker-unselected-draft-construction-manifest-v1',
              'assignment_id':CASE.name,'status':'draft_not_selected',
              'cases':entries,'original_native_observed':False,
              'delivery_ready':False}
    write(CASE/'draft-execution-manifest.json',manifest)
    return manifest


if __name__=='__main__':
    x=build();print(json.dumps({'cases':len(x['cases']),
                                'constructions':sum(1+len(c['candidates']) for c in x['cases'])}))
