"""Rebind the two unselected motion candidates to retained-source analysis."""
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest_path = HERE / 'current-diagnostic-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    for condition in ('condition_a', 'condition_b'):
        entry = next(c for c in manifest['cases'] if c['case_id'].endswith(condition))
        primary = json.loads((HERE / entry['construction']).read_text())
        finalizer = next(f['content'] for f in primary['files'] if f['path'] == 'finalize.py')
        for candidate_id in ('fallback1', 'fallback2'):
            candidate = next(c for c in entry['candidates'] if c['id'] == candidate_id)
            draft = json.loads((HERE / candidate['construction']).read_text())
            next(f for f in draft['files'] if f['path'] == 'finalize.py')['content'] = finalizer
            target = HERE / 'current-fixture' / f'{condition}-{candidate_id}-construction.json'
            target.write_text(json.dumps(draft, indent=2) + '\n')
            candidate['construction'] = str(target.relative_to(HERE))
            candidate['construction_sha256'] = sha(target)
            candidate['fixture_recipe'] = entry['fixture_recipe']
            candidate['status'] = 'unselected_cpu_diagnostic'
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'manifest_sha256': sha(manifest_path), 'constructions': {
        f'{condition}-{candidate_id}': sha(HERE / 'current-fixture' / f'{condition}-{candidate_id}-construction.json')
        for condition in ('condition_a', 'condition_b')
        for candidate_id in ('fallback1', 'fallback2')}}))


if __name__ == '__main__':
    main()
