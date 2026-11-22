"""Prepare source-bound alternate head-slot bundles for both exact cases."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest_path=ROOT/'execution-manifest.json'
    manifest=json.loads(manifest_path.read_text())
    for entry in manifest['cases']:
        primary=json.loads((ROOT/entry['construction']).read_text())
        alternate=json.loads(json.dumps(primary))
        for item in alternate['files']:
            if item['path']=='scene.json':
                scene=json.loads(item['content'])
                scene['candidate_head_slot']=1
                item['content']=json.dumps(scene,indent=2)+'\n'
        target=ROOT/'cases'/entry['case_id'].rsplit('__',1)[-1]/'fallback1-construction.json'
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(json.dumps(alternate,indent=2,ensure_ascii=False)+'\n')
        candidate={'id':'fallback1','construction':str(target.relative_to(ROOT)),
                   'construction_sha256':sha(target),
                   'trigger':{'source':'original signal-head inventory and frame readback',
                              'metric':'count of independently source-verified sole straight-arrow heads facing the ego approach',
                              'failure_condition':'primary selected head has no verified sole straight-arrow readback at the exhibition frame, while an alternate facing head is independently verified'},
                   'changed_knobs':['scene.json candidate_head_slot: 0 to 1; select second verified facing head in stable head-ID order']}
        for old in entry.get('candidates',[]):
            if old.get('id')=='fallback1' and old.get('construction_sha256')==candidate['construction_sha256']:
                candidate=old
        entry['candidates']=[candidate]
    manifest_path.write_text(json.dumps(manifest,indent=2)+'\n')


if __name__=='__main__':main()
