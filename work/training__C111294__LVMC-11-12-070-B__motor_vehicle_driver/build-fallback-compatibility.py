"""Bind current-runtime public diagnostic recipes to the paired fallbacks."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


for number in (1, 2):
    base = HERE / f'current-v2-probe-{number}-primary-manifest.json'
    manifest = json.loads(base.read_text())
    construction = HERE / 'cases' / f'probe_{number}' / 'fallback1' / 'construction.json'
    entry = manifest['cases'][0]
    entry['construction'] = construction.relative_to(HERE).as_posix()
    entry['construction_sha256'] = sha(construction)
    entry['candidate_risk'] = {'status': 'none', 'reason': 'Fallback construction is the subject of this unselected diagnostic manifest.'}
    entry['candidates'] = []
    path = HERE / f'fallback-probe-{number}-compatibility-manifest.json'
    path.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'case': entry['case_id'], 'manifest_sha256': sha(path),
                      'construction_sha256': sha(construction)}, sort_keys=True))
