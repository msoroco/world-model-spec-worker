"""Bind paragraph (c)(2) alternative source-shape fixtures."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
CASE=HERE.parent
ROOT=CASE.parents[1]
OUT=HERE/'current-c2'

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def build():
    import build_current_c1_fixtures as fixture
    fixture.OUT=OUT
    fixture.DISTANCES={'exception_3_1':85.0,'exception_3_2':85.0}
    fixture.build()
    manifest=json.loads((OUT/'manifest.json').read_text())
    for row in manifest['cases']:
        suffix=row['case_id'].split('__')[-1]
        row['construction']='native/current-c2/'+row['construction']
        row['measurement_contract']='native/current-c2/'+row['measurement_contract']
        row['fixture_recipe']=str((OUT/suffix/'fixture-recipe.json').relative_to(ROOT))
    path=CASE/'preview-current-c2-manifest.json'
    path.write_text(json.dumps(manifest,indent=2,allow_nan=False)+'\n')
    return {'manifest_sha256':sha(path),'cases':len(manifest['cases'])}

if __name__=='__main__':print(json.dumps(build(),sort_keys=True))
