"""Bind the unselected camera-risk fallback to current saved-source analysis."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def main():
    manifest_path = HERE / 'current-diagnostic-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    for condition in ('condition_a', 'condition_b'):
        entry = next(item for item in manifest['cases'] if item['case_id'].endswith(condition))
        draft_path = HERE / f'draft-candidates/{condition}/fallback3/construction.json'
        primary_path = HERE / f'current-fixture/{condition}-primary-construction.json'
        draft = json.loads(draft_path.read_text())
        primary = json.loads(primary_path.read_text())
        finalizer = next(item['content'] for item in primary['files']
                         if item['path'] == 'finalize.py')
        for item in draft['files']:
            if item['path'] == 'finalize.py':
                item['content'] = finalizer
        target = HERE / f'current-fixture/{condition}-fallback3-construction.json'
        write(target, draft)
        fallback = next(item for item in entry['candidates'] if item['id'] == 'fallback3')
        fallback['construction'] = f'current-fixture/{condition}-fallback3-construction.json'
        fallback['construction_sha256'] = sha(target)
        fallback['fixture_recipe'] = entry['fixture_recipe']
        fallback['status'] = 'unselected_cpu_diagnostic'
    write(manifest_path, manifest)
    print(json.dumps({'manifest_sha256': sha(manifest_path),
                      'fallback3_constructions': [
                          sha(HERE / f'current-fixture/{c}-fallback3-construction.json')
                          for c in ('condition_a', 'condition_b')]}))


if __name__ == '__main__':
    main()
