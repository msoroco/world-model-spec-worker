"""Materialize eight exact C109137 packages for pinned runtime offline."""
import hashlib
import json
from pathlib import Path
from build import CASES, POLICIES

HERE=Path(__file__).resolve().parent
CASE=HERE.parent.parent
FILES=('assignment-source.json','case-plan.json','zone-adjoining.xodr',
       'config.json','requested-tracks.jsonl','build.py','check.py','capture.py',
       'saved.py','prove_saved.py','measurement-contract.json')
TEST='''import tempfile
import unittest
from pathlib import Path
from check import check
from prove_saved import fixture
from saved import process

class ExactZone(unittest.TestCase):
    def test_source_and_unselected(self):
        row=check(Path.cwd())
        self.assertFalse(row['delivery_ready'])
        self.assertFalse(row['physical_crossing_observed'])
    def test_request(self):
        row=check(Path.cwd())
        if row['candidate_id']=='fallback3':
            self.assertIsNone(row['requested_crossing_frame'])
        else:
            self.assertIsNotNone(row['requested_crossing_frame'])
    def test_synthetic_saved(self):
        with tempfile.TemporaryDirectory() as folder:
            raw,video,review=fixture(Path.cwd(),Path(folder))
            row=process(Path.cwd(),raw,video,review,synthetic=True)
            self.assertEqual(row['frames'],400)
            self.assertFalse(row['delivery_ready'])
            self.assertIsNone(row['physical_legal_verdict'])
'''

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def build():
    cases=[]
    for suffix in CASES:
        choices=[]
        for candidate in POLICIES:
            bundle=HERE/'drafts'/suffix/candidate
            files=[{'path':name,'content':(bundle/name).read_text() if (bundle/name).is_file() else (HERE/name).read_text()} for name in FILES]
            files.append({'path':'tests/test_exact.py','content':TEST})
            construction={'case_id':CASE.name+'__'+suffix,'cell_id':'C109137',
                'law_id':'NRS-484B-217-2','actor':'motor_vehicle_driver',
                'entrypoint':'capture.py','files':files,
                'status':'unselected_cpu_diagnostic',
                'recording_description':'Authored striped-road/adjoining-highway request; designation, original physical crossing and legal safety unverified.'}
            path=HERE/'runtime-drafts'/suffix/candidate/'construction.json'
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text(json.dumps(construction,indent=2,allow_nan=False)+'\n')
            choices.append({'id':candidate,'construction':str(path.relative_to(HERE)),
                            'construction_sha256':sha(path)})
        cases.append({'case_id':CASE.name+'__'+suffix,
            'construction':choices[0]['construction'],
            'construction_sha256':choices[0]['construction_sha256'],
            'candidates':choices[1:],
            'candidate_risk':{'status':'physical','reason':'Original Native, visual statutory evidence and no-impediment proof absent.'}})
    manifest={'format':'worker-unselected-draft-construction-manifest-v1',
        'assignment_id':CASE.name,'status':'draft_not_selected','cases':cases,
        'original_native_observed':False,'delivery_ready':False}
    (HERE/'draft-execution-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return manifest

if __name__=='__main__':
    print(json.dumps({'cases':len(build()['cases']),'constructions':8}))
