"""Pin eight unselected C111662 Native requests into frozen offline constructions."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
CASE=HERE.parent
ROOT=CASE.parents[1]
PREFIX=f'work/{CASE.name}/native'
TEST='''import json
import sys
import tempfile
import unittest
from pathlib import Path

root=Path.cwd()
native=root/'work'/'NAME'/'native'
sys.path.insert(0,str(native))
from check import check
from saved import make_raw,process
from capture import control,camera_specs
from prove_original_processing import prove

class ExactTurn(unittest.TestCase):
    def setUp(self):
        self.bundle=native/'drafts'/'SUFFIX'/'CANDIDATE'

    def test_current_four_camera_profile(self):
        config=json.loads((self.bundle/'config.json').read_text())
        specs=camera_specs(config['camera_policy'])
        self.assertEqual([(row[0],row[1],row[2]) for row in specs],
                         [('overview',1920,1080),('approach',1280,720),
                          ('reference_corner',1280,720),('driver_reference',1280,720)])
        self.assertEqual(camera_specs('elevated_overview')[0][3][2],55)
        with self.assertRaisesRegex(ValueError,'Unknown camera policy'):
            camera_specs('unknown')

    def test_source_bound_request(self):
        result=check(self.bundle)
        self.assertEqual(result['frames'],800)
        self.assertFalse(result['delivery_ready'])

    def test_synthetic_saved_join(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'raw.json'
            path.write_text(json.dumps(make_raw(self.bundle)))
            result=process(self.bundle,path)
            self.assertEqual(result['frames_joined'],800)
            self.assertFalse(result['district_designation_verified'])

    def test_rehashed_road_mutation_rejected(self):
        import hashlib
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)
            for item in self.bundle.iterdir():
                (target/item.name).write_bytes(item.read_bytes())
            road=target/'district-crossroads.xodr'
            road.write_text(road.read_text().replace('x="-100"','x="-99"',1))
            cfg=json.loads((target/'config.json').read_text())
            cfg['road_sha256']=hashlib.sha256(road.read_bytes()).hexdigest()
            (target/'config.json').write_text(json.dumps(cfg))
            with self.assertRaises(ValueError):check(target)

    def test_original_processor_synthetic_fixture(self):
        result=prove(self.bundle)
        self.assertEqual(result['positive_count'],1)
        self.assertEqual(result['negative_count'],7)
        self.assertFalse(result['original_native_observed'])
        self.assertFalse(result['delivery_ready'])
'''


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    cases=[]
    for suffix in ('reference','contrast'):
        choices=[]
        for candidate in ('primary','fallback1','fallback2','fallback3'):
            bundle=HERE/'drafts'/suffix/candidate
            files=[]
            for name in ('assignment-source.json','case-plan.json','district-crossroads.xodr',
                         'requested-tracks.jsonl','config.json'):
                content=(bundle/name).read_text()
                files.append({'path':f'{PREFIX}/drafts/{suffix}/{candidate}/{name}','content':content})
                files.append({'path':name,'content':content})
            for name in ('build.py','check.py','saved.py','capture.py','process_original.py',
                         'prove_original_processing.py','measurement-contract.json'):
                files.append({'path':f'{PREFIX}/{name}','content':(HERE/name).read_text()})
            files.extend((
                {'path':f'work/{CASE.name}/case-plan.json','content':(CASE/'case-plan.json').read_text()},
                {'path':f'inputs/{CASE.name}/assignment.json',
                 'content':(ROOT/'inputs'/CASE.name/'assignment.json').read_text()},
                {'path':'tests/test_exact.py','content':TEST.replace('NAME',CASE.name).replace('SUFFIX',suffix).replace('CANDIDATE',candidate)},
            ))
            construction={'case_id':CASE.name+'__'+suffix,'cell_id':'C111662',
                          'law_id':'NRS-484B-403-3','actor':'motor_vehicle_driver',
                          'entrypoint':f'{PREFIX}/capture.py','files':files,
                          'status':'unselected_cpu_diagnostic',
                          'recording_description':'Authored six-lane U-turn location pair; district designation, physical path and legal exception unverified.'}
            path=HERE/'runtime-drafts'/suffix/candidate/'construction.json'
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text(json.dumps(construction,indent=2,allow_nan=False)+'\n')
            choices.append({'id':candidate,'construction':str(path.relative_to(HERE)),
                            'construction_sha256':sha(path)})
        cases.append({'case_id':CASE.name+'__'+suffix,'construction':choices[0]['construction'],
                      'construction_sha256':choices[0]['construction_sha256'],
                      'candidates':choices[1:],
                      'candidate_risk':{'status':'physical','reason':'Original district designation, generated intersection and physical U-turn unverified.'}})
    manifest={'format':'worker-unselected-draft-construction-manifest-v1',
              'assignment_id':CASE.name,'status':'draft_not_selected','cases':cases,
              'original_native_observed':False,'delivery_ready':False}
    (HERE/'draft-execution-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return manifest


if __name__=='__main__':print(json.dumps({'constructions':sum(1+len(c['candidates']) for c in build()['cases'])}))
