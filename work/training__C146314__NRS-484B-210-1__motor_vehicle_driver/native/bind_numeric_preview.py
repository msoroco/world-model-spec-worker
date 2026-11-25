"""Bind numeric boundary fixtures and proposals for CPU diagnostics."""
import copy
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
CASE=HERE.parent
ROOT=CASE.parents[1]
OUT=HERE/'numeric-boundary'
DISTANCES={'numeric_1_0':60.86,'numeric_1_1':60.96,'numeric_1_2':61.06}

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def put(path,value):path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')

def build():
    import build_current_c1_fixtures as fixture
    fixture.OUT=OUT
    fixture.DISTANCES=DISTANCES
    fixture.build()
    proposals=CASE/'proposals/cases.json'
    data=json.loads(proposals.read_text())
    source=next(row for row in data['cases'] if row['case_id'].endswith('__exception_3_1'))
    for suffix,distance in DISTANCES.items():
        case_id=CASE.name+'__'+suffix
        data['cases']=[row for row in data['cases'] if row['case_id']!=case_id]
        row=copy.deepcopy(source)
        row['case_id']=case_id
        row['target_type']={'numeric_1_0':'below','numeric_1_1':'at','numeric_1_2':'above'}[suffix]
        row['rationale']='Synthetic source diagnostic requests '+str(distance)+' m near the inclusive 200-foot boundary; pavement and legal facts remain unreviewed.'
        data['cases'].append(row)
    put(proposals,data)
    manifest=json.loads((OUT/'manifest.json').read_text())
    for row in manifest['cases']:
        suffix=row['case_id'].split('__')[-1]
        row['construction']='native/numeric-boundary/'+row['construction']
        row['measurement_contract']='native/numeric-boundary/'+row['measurement_contract']
        row['fixture_recipe']=str((OUT/suffix/'fixture-recipe.json').relative_to(ROOT))
    put(CASE/'preview-numeric-manifest.json',manifest)
    return {'manifest_sha256':sha(CASE/'preview-numeric-manifest.json'),
            'proposal_cases':len(data['cases'])}

if __name__=='__main__':print(json.dumps(build(),sort_keys=True))
