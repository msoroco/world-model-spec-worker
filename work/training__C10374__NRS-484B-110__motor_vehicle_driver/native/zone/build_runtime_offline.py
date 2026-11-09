"""Pin eight exact zone constructions to the offline runtime."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
CASE=HERE.parent.parent


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

TEST='''import unittest
from pathlib import Path
from check import check
from fixture_raw import build as fixture
from saved import prepare, measure
from route_fallbacks import route

class ExactSafetyZone(unittest.TestCase):
    def test_exact_source_and_unverified_physics(self):
        result=check(Path.cwd())
        self.assertFalse(result['actual_zone_overlap_observed'])
        self.assertFalse(result['delivery_ready'])
        self.assertEqual(result['requested_zone_route'],
                         result['case_id'].endswith('condition_a'))

    def test_distinct_stop_request(self):
        result=check(Path.cwd())
        if result['candidate_id']=='fallback3':
            self.assertEqual(result['requested_encounter_frames'],0)
        else:
            self.assertGreater(result['requested_encounter_frames'],0)

    def test_synthetic_raw_to_saved_overlap(self):
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            fixture(Path.cwd(),root/'raw')
            receipt=prepare(Path.cwd(),root/'raw',root/'saved',True)
            measurement=measure(Path.cwd(),root/'saved')
            routed=route(Path.cwd(),root/'saved')
            self.assertEqual(receipt['source_kind'],'synthetic_cpu')
            self.assertFalse(measurement['authored_rectangle_is_designated_zone'])
            self.assertFalse(measurement['delivery_ready'])
            self.assertIsNone(routed['selected_fallback'])
'''


def build():
    cases=[]
    for suffix in ('selected_c5852cfd__condition_a','selected_c5852cfd__condition_b'):
        choices=[]
        for candidate in ('primary','fallback1','fallback2','fallback3'):
            bundle=HERE/'offline/bundles'/suffix/candidate
            names=('assignment-source.json','case-plan.json','alley-zone.xodr',
                   'config.json','requested-tracks.jsonl','build.py','check.py',
                   'capture.py','measurement-contract.json','saved.py','fixture_raw.py',
                   'route_fallbacks.py')
            files=[{'path':name,'content':(bundle/name).read_text()} for name in names]
            files.append({'path':'tests/test_exact.py','content':TEST})
            construction={'case_id':CASE.name+'__'+suffix,'cell_id':'C10374',
                'law_id':'NRS-484B-110','actor':'motor_vehicle_driver',
                'entrypoint':'capture.py','files':files,
                'status':'unselected_cpu_diagnostic',
                'recording_description':'Authored alley zone route pair; physical safety-zone designation and original body overlap unverified.'}
            path=HERE/'runtime-drafts'/suffix/candidate/'construction.json'
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text(json.dumps(construction,indent=2,allow_nan=False)+'\n')
            choices.append({'id':candidate,'construction':str(path.relative_to(HERE)),
                            'construction_sha256':sha(path)})
        cases.append({'case_id':CASE.name+'__'+suffix,
            'construction':choices[0]['construction'],
            'construction_sha256':choices[0]['construction_sha256'],
            'candidates':choices[1:],
            'candidate_risk':{'status':'physical',
                'reason':'Original Native zone delimiter, legal designation, body overlap and pixel review absent.'}})
    manifest={'format':'worker-unselected-draft-construction-manifest-v1',
        'assignment_id':CASE.name,'status':'draft_not_selected','cases':cases,
        'original_native_observed':False,'delivery_ready':False}
    (HERE/'draft-execution-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return manifest


if __name__=='__main__':
    m=build();print(json.dumps({'cases':len(m['cases']),
        'constructions':sum(1+len(row['candidates']) for row in m['cases'])}))
