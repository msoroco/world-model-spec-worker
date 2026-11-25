"""Bind paragraph (c)(1) draft fixtures for public CPU compatibility."""
import copy
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
CASE=HERE.parent
ROOT=CASE.parents[1]
OUT=HERE/'current-c1'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def put(path,value):
    path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')


def build():
    proposals=CASE/'proposals/cases.json'
    data=json.loads(proposals.read_text())
    source=next(row for row in data['cases'] if row['case_id'].endswith('__witness_1'))
    for suffix,distance in (('exception_3_1',61.06),('exception_3_2',60.96)):
        case_id=CASE.name+'__'+suffix
        data['cases']=[row for row in data['cases'] if row['case_id']!=case_id]
        row=copy.deepcopy(source)
        row['case_id']=case_id
        row['rationale']='Paragraph (c)(1) synthetic diagnostic requests an unmarked-shoulder span of '+str(distance)+' m; actual physical and legal facts remain unreviewed.'
        row['unresolved_judgment_calls'].append('Whether the sampled shoulder is pavement not marked as a traffic lane requires independent source review.')
        data['cases'].append(row)
    put(proposals,data)
    manifest=json.loads((OUT/'manifest.json').read_text())
    for row in manifest['cases']:
        suffix=row['case_id'].split('__')[-1]
        row['construction']='native/current-c1/'+row['construction']
        row['measurement_contract']='native/current-c1/'+row['measurement_contract']
        row['fixture_recipe']=str((OUT/suffix/'fixture-recipe.json').relative_to(ROOT))
    put(CASE/'preview-current-c1-manifest.json',manifest)
    return {'manifest_sha256':sha(CASE/'preview-current-c1-manifest.json'),
            'proposal_cases':len(data['cases'])}


if __name__=='__main__':
    print(json.dumps(build(),sort_keys=True))
