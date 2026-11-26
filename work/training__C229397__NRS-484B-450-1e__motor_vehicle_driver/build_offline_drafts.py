"""Build exact unselected branch drafts for pinned offline source checks."""
import hashlib
import json
from pathlib import Path

CASE = Path(__file__).resolve().parent
ROOT = CASE.parents[1]

ENTRY = (CASE / 'native/runner.py').read_text()

TEST = '''import json
import unittest
from pathlib import Path
from capture import check

class ExactDraft(unittest.TestCase):
    def test_source_bound(self):
        result=check()
        self.assertTrue(result['passed'])
        self.assertFalse(result['native_imported'])
        self.assertFalse(result['physical_acceptance_claimed'])

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
        variant=('clear' if number=='1' else 'occupy') if branch in ('witness','stop','stand') else ('absent' if number=='1' else 'present')
        config={'assignment_id':CASE.name,'case_id':case_id,'law_id':plan['law_id'],
                'cell_id':plan['cell_id'],'actor':plan['actor'],'frozen_cell':plan['frozen_cell'],
                'branch':branch,'target_variant':variant,
                'rate_hz':20,'frames':600,'duration_s':30,
                'source_cameras':['overview','approach','reference_corner','driver_reference'],
                'crosswalk_geometry_required':True,'original_vehicle_footprint_required':True,
                'exception_context_source_required':branch.startswith('exception_'),
                'authored_target_xy_m':[1.75,-18.0] if variant=='clear' else [1.75,-10.0],
                'native_execution_implemented':True}
        files=[{'path':'capture.py','content':ENTRY},
               {'path':'tests/test_draft.py','content':TEST},
               {'path':'config.json','content':json.dumps(config,indent=2)+'\n'},
               {'path':'assignment-source.json','content':json.dumps(source,indent=2)+'\n'},
               {'path':'case-plan.json','content':json.dumps(plan,indent=2)+'\n'},
               {'path':'measure_crosswalk.py','content':(CASE/'measure_crosswalk.py').read_text()}]
        files.append({'path':'geometry.py','content':(CASE/'native/geometry.py').read_text()})
        proposal={'case_id':case_id,'law_id':plan['law_id'],'cell_id':plan['cell_id'],
                  'actor':plan['actor'],'entrypoint':'capture.py','files':files,
                  'status':'unselected_native_draft',
                  'recording_description':'Native runner captures original rest, crosswalk map readback, footprint and four synchronized cameras; exception authority still requires source review.'}
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
