import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
manifest_path = HERE / 'execution-manifest.json'
manifest = json.loads(manifest_path.read_text())

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

for entry in manifest['cases']:
    suffix = entry['case_id'].removeprefix(HERE.name + '__')
    primary = json.loads((HERE / entry['construction']).read_text())
    fallback = json.loads(json.dumps(primary))
    for file in fallback['files']:
        if file['path'] == 'runner.py':
            text = file['content']
            assert 'thickness=.08' in text and 'thickness=.09' in text
            file['content'] = text.replace('thickness=.08', 'thickness=.16').replace('thickness=.09', 'thickness=.16')
        if file['path'] == 'config.json':
            config = json.loads(file['content'])
            config['candidate_id'] = 'fallback1'
            file['content'] = json.dumps(config, indent=2) + '\n'
    fallback['status'] = 'partial_native_fallback_draft_physical_unverified'
    path = HERE / 'draft-exact' / suffix / 'fallback1' / 'construction.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(fallback, indent=2) + '\n')
    entry['candidates'] = [{
        'id': 'fallback1',
        'construction': str(path.relative_to(HERE)),
        'construction_sha256': sha(path),
        'trigger': {
            'source': 'original Native four-camera frames and blind-person context',
            'metric': 'cane marker stroke visibility in crossing interval',
            'failure_condition': 'primary white or red-tipped cane marker is not visible in source frames',
        },
        'changed_knobs': ['authored cane debug stroke thickness: 0.08/0.09 to 0.16'],
    }]
manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
print('fallbacks', len(manifest['cases']), sha(manifest_path))
