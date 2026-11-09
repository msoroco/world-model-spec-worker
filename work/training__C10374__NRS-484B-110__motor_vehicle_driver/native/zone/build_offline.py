"""Copy exact safety-zone requests and sources into eight CPU bundles."""
import hashlib
import json
from pathlib import Path
import shutil

HERE=Path(__file__).resolve().parent
CASE=HERE.parent.parent
ROOT=CASE.parents[1]
NAMES=('assignment-source.json','case-plan.json','alley-zone.xodr',
       'config.json','requested-tracks.jsonl','build.py','check.py','capture.py',
       'measurement-contract.json','saved.py','fixture_raw.py',
       'route_fallbacks.py')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build():
    manifest=json.loads((HERE/'manifest.json').read_text())
    entries=[]
    for row in manifest['entries']:
        suffix='__'.join(row['case_id'].split('__')[-2:])
        candidate=row['candidate_id']
        target=HERE/'offline/bundles'/suffix/candidate
        target.mkdir(parents=True,exist_ok=True)
        sources={
            'assignment-source.json':ROOT/'inputs'/CASE.name/'assignment.json',
            'case-plan.json':CASE/'case-plan.json',
            'alley-zone.xodr':HERE/'alley-zone.xodr',
            'config.json':HERE/'drafts'/suffix/candidate/'config.json',
            'requested-tracks.jsonl':HERE/'drafts'/suffix/candidate/'requested-tracks.jsonl',
            'build.py':HERE/'build.py','check.py':HERE/'check.py',
            'capture.py':HERE/'capture.py',
            'measurement-contract.json':HERE/'measurement-contract.json',
            'saved.py':HERE/'saved.py','fixture_raw.py':HERE/'fixture_raw.py',
            'route_fallbacks.py':HERE/'route_fallbacks.py'}
        for name,source in sources.items():shutil.copyfile(source,target/name)
        entries.append({'case_id':row['case_id'],'candidate_id':candidate,
            'bundle':str(target.relative_to(HERE)),
            'file_sha256':{name:sha(target/name) for name in NAMES}})
    result={'format':'c10374-safety-zone-copied-offline-v1',
            'construction_sha256':sha(HERE/'manifest.json'),
            'entries':entries,'original_native_observed':False,
            'delivery_ready':False}
    (HERE/'offline/manifest.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__=='__main__':print(json.dumps({'bundles':len(build()['entries'])}))
