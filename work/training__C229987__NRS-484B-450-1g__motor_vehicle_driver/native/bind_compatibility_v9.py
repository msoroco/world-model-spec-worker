"""Bind exact primary and fallback positive/negative source compatibility proofs."""
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
    suffix = entry['id']
    for candidate in ('primary', 'fallback1'):
        source = repo/'.runtime-work/c229987'/('compat-v9-'+suffix+'-'+candidate)
        receipt = json.loads((source/'compatibility.json').read_text())
        selected = entry if candidate == 'primary' else entry['candidates'][0]
        assert receipt['passed'] and receipt['case_id'] == entry['case_id']
        assert receipt['candidate_id'] == candidate
        assert receipt['construction_sha256'] == selected['construction_sha256']
        target = root/'compatibility'/suffix/candidate
        target.mkdir(parents=True, exist_ok=True)
        for name, dest in [('compatibility.json', 'compatibility.json'),
                           ('compatibility-analysis.log', 'analysis.log'),
                           ('negative-analysis.log', 'negative.log')]:
            shutil.copyfile(source/name, target/dest)
        selected['compatibility'] = {
            'receipt': str((target/'compatibility.json').relative_to(root)),
            'sha256': sha(target/'compatibility.json'),
            'log': str((target/'analysis.log').relative_to(root)),
            'negative_log': str((target/'negative.log').relative_to(root))}
        if candidate == 'primary':
            entry['negative'] = {'log': str((target/'negative.log').relative_to(root))}
    construction = json.loads((root/entry['construction']).read_text())
    config = json.loads(next(f['content'] for f in construction['files'] if f['path'] == 'config.json'))
    required = set(config['required_atoms']) | {
        channel['name'] for channel in construction['recording_description']['channels']}
    entry['acquisition'] = {
        name: {'entrypoint': 'runner.py',
               'method': 'Original same-tick Native signal, vehicle, context and road readback; survey retained',
               'evidence': 'signal_raw.json, trace.jsonl, video_frames.jsonl, capture/evidence.jsonl, road.xodr, context-survey.json'}
        for name in sorted(required)}
manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True)+'\n')
