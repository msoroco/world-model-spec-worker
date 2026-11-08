"""Copy exact paragraph (c)(1) boundary requests for CPU proof."""
import hashlib
import json
import shutil
from pathlib import Path

HERE=Path(__file__).resolve().parent
CASE=HERE.parent.parent
ROOT=CASE.parents[1]
NAMES=('assignment-source.json','case-plan.json','unmarked-pass.xodr',
       'config.json','requested-tracks.jsonl','build.py','check.py',
       'capture.py','measurement-contract.json')


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build():
    manifest=json.loads((HERE/'manifest.json').read_text())
    entries=[]
    for row in manifest['entries']:
        witness=row['case_id'].split('__')[-1]
        candidate=row['candidate_id']
        target=HERE/'offline/bundles'/witness/candidate
        target.mkdir(parents=True,exist_ok=True)
        sources={
            'assignment-source.json':ROOT/'inputs'/CASE.name/'assignment.json',
            'case-plan.json':CASE/'case-plan.json',
            'unmarked-pass.xodr':HERE/'unmarked-pass.xodr',
            'config.json':HERE/'drafts'/witness/candidate/'config.json',
            'requested-tracks.jsonl':HERE/'drafts'/witness/candidate/'requested-tracks.jsonl',
            'build.py':HERE/'build.py','check.py':HERE/'check.py',
            'capture.py':HERE/'capture.py',
            'measurement-contract.json':HERE/'measurement-contract.json'}
        for name,source in sources.items():shutil.copyfile(source,target/name)
        entries.append({'case_id':row['case_id'],'candidate_id':candidate,
            'bundle':str(target.relative_to(HERE)),
            'file_sha256':{name:sha(target/name) for name in NAMES}})
    result={'format':'c146314-paragraph-c1-offline-v1',
        'construction_sha256':sha(HERE/'manifest.json'),
        'entries':entries,'original_native_observed':False,'delivery_ready':False}
    (HERE/'offline/manifest.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__=='__main__':print(json.dumps({'bundles':len(build()['entries'])}))
