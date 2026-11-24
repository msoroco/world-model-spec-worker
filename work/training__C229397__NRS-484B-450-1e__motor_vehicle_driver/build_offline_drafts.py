"""Build exact unselected branch drafts for pinned offline source checks."""
import hashlib
import json
from pathlib import Path

CASE = Path(__file__).resolve().parent
ROOT = CASE.parents[1]

ENTRY = '''"""Source-bound CPU preflight; Native capture has not been implemented."""
import argparse
import json
from pathlib import Path

def check():
    root=Path.cwd()
    source=json.loads((root/'assignment-source.json').read_text())
    plan=json.loads((root/'case-plan.json').read_text())
    config=json.loads((root/'config.json').read_text())
    assert source['assignment_id']==plan['assignment_id']==config['assignment_id']
    assert source['law']['text']==plan['source_law']['text']
    assert source['law_sha256']==plan['source_law']['sha256']
    assert config['case_id'] in {c['case_id'] for c in plan['cases']}
    assert config['rate_hz']==20 and config['frames']==600
    assert config['source_cameras']==['overview','approach','reference_corner','driver_reference']
    assert config['frozen_cell']==plan['frozen_cell']
    return {'source_bound':True,'native_executed':False,'delivery_ready':False}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true')
    args=parser.parse_args()
    if not args.check:raise RuntimeError('Native execution remains unimplemented for this draft')
    print(json.dumps(check()))
'''

TEST = '''import json
import unittest
from pathlib import Path
from capture import check

class ExactDraft(unittest.TestCase):
    def test_source_bound(self):
        result=check()
        self.assertTrue(result['source_bound'])
        self.assertFalse(result['delivery_ready'])
        self.assertFalse(result['native_executed'])

    def test_branch_variable(self):
        cfg=json.loads(Path('config.json').read_text())
        suffix=cfg['case_id'].rsplit('__',1)[-1]
        self.assertEqual(cfg['branch'],suffix.rsplit('_',1)[0])
        self.assertIn(cfg['target_variant'],('clear','occupy','absent','present'))
'''


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + '\n')


def build():
    assignment=json.loads((ROOT/'inputs'/CASE.name/'assignment.json').read_text())
    plan=json.loads((CASE/'case-plan.json').read_text())
    source={'assignment_id':CASE.name,'law':assignment['law'],
            'law_sha256':assignment['local_snapshot']['law_sha256']}
    entries=[]
    for case in plan['cases']:
        case_id=case['case_id']
        suffix=case_id[len(CASE.name)+2:]
        branch,number=suffix.rsplit('_',1)
        variant=('clear' if number=='1' else 'occupy') if branch=='witness' else ('absent' if number=='1' else 'present')
        config={'assignment_id':CASE.name,'case_id':case_id,'law_id':plan['law_id'],
                'cell_id':plan['cell_id'],'actor':plan['actor'],'frozen_cell':plan['frozen_cell'],
                'branch':branch,'target_variant':variant,
                'rate_hz':20,'frames':600,'duration_s':30,
                'source_cameras':['overview','approach','reference_corner','driver_reference'],
                'crosswalk_geometry_required':True,'original_vehicle_footprint_required':True,
                'exception_context_source_required':branch!='witness',
                'native_execution_implemented':False}
        files=[{'path':'capture.py','content':ENTRY},
               {'path':'tests/test_draft.py','content':TEST},
               {'path':'config.json','content':json.dumps(config,indent=2)+'\n'},
               {'path':'assignment-source.json','content':json.dumps(source,indent=2)+'\n'},
               {'path':'case-plan.json','content':json.dumps(plan,indent=2)+'\n'},
               {'path':'measure_crosswalk.py','content':(CASE/'measure_crosswalk.py').read_text()}]
        proposal={'case_id':case_id,'law_id':plan['law_id'],'cell_id':plan['cell_id'],
                  'actor':plan['actor'],'entrypoint':'capture.py','files':files,
                  'status':'unselected_cpu_diagnostic',
                  'recording_description':'Original Native rest, crosswalk geometry, footprint and exception context remain unrecorded.'}
        path=CASE/'offline'/'drafts'/suffix/'construction.json'
        write(path,proposal)
        entries.append({'case_id':case_id,'construction':str(path.relative_to(CASE)),
                        'construction_sha256':sha(path),'candidates':[],
                        'candidate_risk':{'status':'physical',
                          'reason':'Native crosswalk geometry, exact footprint and exception context are unverified.'}})
    manifest={'format':'worker-unselected-draft-construction-manifest-v1',
              'assignment_id':CASE.name,'status':'draft_not_selected',
              'cases':entries,'original_native_observed':False,'delivery_ready':False}
    path=CASE/'draft-execution-manifest.json';write(path,manifest)
    return path


if __name__=='__main__':print(build())
