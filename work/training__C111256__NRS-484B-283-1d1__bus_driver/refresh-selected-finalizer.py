"""Rebind selected bundles after a change to original Walk finalization code."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
NATIVE = HERE / 'native'
MODULES = ('finalize.py', 'physical_walk_audit.py',
           'official_walk_source_audit.py')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    path = HERE / 'execution-manifest.json'
    manifest = json.loads(path.read_text())
    for case in manifest['cases']:
        for candidate in (case, *case['candidates']):
            construction_path = HERE / candidate['construction']
            construction = json.loads(construction_path.read_text())
            files = {entry['path']: entry for entry in construction['files']}
            for name in MODULES:
                content = (NATIVE / name).read_text()
                if name in files:
                    files[name]['content'] = content
                else:
                    construction['files'].append({'path': name, 'content': content})
            construction_path.write_text(json.dumps(construction, indent=2) + '\n')
            candidate['construction_sha256'] = sha(construction_path)
            candidate.pop('offline', None)
            candidate.pop('compatibility', None)
        case.pop('negative', None)
        case.pop('physical_preparation', None)
        case['preparation_status'] = 'selected; finalizer changed; current CPU proofs pending'
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps({'selected_cases': len(manifest['cases']),
                      'candidates_rebound': sum(1 + len(c['candidates'])
                                                for c in manifest['cases']),
                      'manifest_sha256': sha(path),
                      'proofs_invalidated': True}))


if __name__ == '__main__':
    main()
