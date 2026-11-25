"""Bind subsection (4) category request fixtures for CPU diagnostics."""
import copy
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
CASE=HERE.parent
ROOT=CASE.parents[1]
OUT=HERE/'subsection-4'
CATEGORIES={'exception_5_1':'tow_car','exception_5_2':'ordinary_vehicle'}
DISTANCES={name:61.06 for name in CATEGORIES}

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def put(path,value):path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')

def build():
    import build_current_c1_fixtures as fixture
    fixture.OUT=OUT
    fixture.DISTANCES=DISTANCES
    fixture.build()
    proposals=CASE/'proposals/cases.json'
    data=json.loads(proposals.read_text())
    source=next(row for row in data['cases'] if row['case_id'].endswith('__numeric_1_2'))
    for suffix,category in CATEGORIES.items():
        case_id=CASE.name+'__'+suffix
        data['cases']=[row for row in data['cases'] if row['case_id']!=case_id]
        row=copy.deepcopy(source)
        row['case_id']=case_id
        row['target_type']='controlled_attempt'
        row['rationale']='Subsection (4) synthetic request compares '+category+' against the ordinary category beyond 200 feet; qualification and legal result remain unverified.'
        row['unresolved_judgment_calls'].append('The requested vehicle category is not verified by the diagnostic capture.')
        data['cases'].append(row)
    put(proposals,data)
    manifest=json.loads((OUT/'manifest.json').read_text())
    for row in manifest['cases']:
        suffix=row['case_id'].split('__')[-1]
        row['construction']='native/subsection-4/'+row['construction']
        row['measurement_contract']='native/subsection-4/'+row['measurement_contract']
        row['fixture_recipe']=str((OUT/suffix/'fixture-recipe.json').relative_to(ROOT))
    put(CASE/'preview-subsection4-manifest.json',manifest)
    return {'manifest_sha256':sha(CASE/'preview-subsection4-manifest.json'),
            'proposal_cases':len(data['cases'])}

if __name__=='__main__':print(json.dumps(build(),sort_keys=True))
