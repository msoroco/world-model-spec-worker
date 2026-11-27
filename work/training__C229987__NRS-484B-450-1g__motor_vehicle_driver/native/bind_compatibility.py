"""Bind successful source-specific fixture diagnostics without regenerating them."""
import hashlib
import json
import shutil
from pathlib import Path

root = Path(__file__).resolve().parents[1]
repo = root.parents[1]
manifest_path = root/'execution-manifest.json'
manifest = json.loads(manifest_path.read_text())

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

for entry in manifest['cases']:
    suffix = entry['case_id'].rsplit('__',1)[-1]
    version = 'v7'
    source = repo/'.runtime-work/c229987'/f'compat-{version}-{suffix}'
    receipt = json.loads((source/'compatibility.json').read_text())
    assert receipt['passed'] and receipt['case_id'] == entry['case_id']
    assert receipt['construction_sha256'] == entry['construction_sha256']
    target = root/'compatibility'/suffix
    target.mkdir(parents=True,exist_ok=True)
    names = {'compatibility.json':'compatibility.json',
             'compatibility-analysis.log':'analysis.log',
             'negative-analysis.log':'negative.log'}
    for name, dest in names.items():
        shutil.copyfile(source/name,target/dest)
    entry['compatibility'] = {'receipt':str((target/'compatibility.json').relative_to(root)),
                              'sha256':sha(target/'compatibility.json'),
                              'log':str((target/'analysis.log').relative_to(root)),
                              'negative_log':str((target/'negative.log').relative_to(root))}
    entry['negative'] = {'log':str((target/'negative.log').relative_to(root))}
    construction = json.loads((root/entry['construction']).read_text())
    files = {f['path'] for f in construction['files']}
    channels = {c['name'] for c in construction['recording_description']['channels']}
    required = set(json.loads(next(f['content'] for f in construction['files'] if f['path']=='config.json'))['required_atoms']) | channels
    entry['acquisition'] = {name:{'entrypoint':'runner.py',
                                  'method':'Original same-tick Native signal, vehicle and road readback; source survey retained',
                                  'evidence':'signal_raw.json, trace.jsonl, video_frames.jsonl, capture/evidence.jsonl, road.xodr, context-survey.json'}
                            for name in sorted(required)}
    assert 'runner.py' in files
manifest_path.write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
