"""Select the authored reverse-approach recipe for fallback1 CPU diagnostics."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
MANIFEST = HERE / 'execution-manifest.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


canonical = json.loads(MANIFEST.read_text())
for entry in canonical['cases']:
    case = entry['case_id'].removeprefix(HERE.name + '__')
    candidate = next(x for x in entry['candidates'] if x['id'] == 'fallback1')
    if not candidate.get('fixture_recipe'):
        raise ValueError('Reverse-approach candidate lacks its diagnostic recipe')
    variant = json.loads(MANIFEST.read_text())
    selected = next(x for x in variant['cases'] if x['case_id'] == entry['case_id'])
    selected['fixture_recipe'] = candidate['fixture_recipe']
    path = HERE / f'update071-{case}-fallback1-manifest.json'
    path.write_text(json.dumps(variant, indent=2) + '\n')
    print(json.dumps({'case': case, 'manifest_sha256': sha(path),
                      'recipe': candidate['fixture_recipe']}))
