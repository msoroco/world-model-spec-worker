"""Freeze candidate-specific diagnostic recipes without changing delivery manifest."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]
BASE=json.loads((ROOT/'draft-execution-manifest.json').read_text())


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build():
    rows=[]
    for case in ('reference','contrast','divided_reference','divided_opening'):
        for candidate in ('fallback1','fallback2','fallback3'):
            source=ROOT/f'update015-current-{case}-{candidate}-recipe.json'
            value=json.loads(json.dumps(BASE))
            value['diagnostic_candidate']=candidate
            value['diagnostic_case']=ROOT.name+'__'+case
            for entry in value['cases']:
                if entry['case_id']==value['diagnostic_case']:
                    entry['fixture_recipe']=source.relative_to(REPO).as_posix()
            target=ROOT/f'draft-execution-manifest-{case}-{candidate}.json'
            target.write_text(json.dumps(value,indent=2)+'\n')
            rows.append({'case':case,'candidate':candidate,'manifest':target.name,
                         'sha256':sha(target),'recipe_sha256':sha(source)})
    (ROOT/'update015-candidate-manifests.json').write_text(json.dumps({
        'format':'c111662-candidate-diagnostic-manifests-v1',
        'base_manifest_sha256':sha(ROOT/'draft-execution-manifest.json'),
        'variants':rows},indent=2)+'\n')
    print(json.dumps({'candidate_variants':len(rows)}))


if __name__=='__main__':build()
