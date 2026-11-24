"""Rebind the existing eight draft constructions to the pinned JSON runtime."""
import hashlib
import json
from pathlib import Path

FOLDER = Path(__file__).resolve().parent
ROOT = FOLDER.parents[1]

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    source = json.loads((FOLDER / 'draft-proof-manifest.json').read_text())
    source['runtime_manifest_sha256'] = sha(ROOT / 'runtime/pipeline/SOURCE-MANIFEST.json')
    source['status'] = 'draft_current_v2_diagnostic'
    for entry in source['cases']:
        entry.pop('offline', None)
        for candidate in entry['candidates']:
            candidate.pop('offline', None)
    target = FOLDER / 'current-v2-draft-manifest.json'
    target.write_text(json.dumps(source, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'manifest_sha256': sha(target), 'cases': len(source['cases']),
                      'runtime_manifest_sha256': source['runtime_manifest_sha256']}))

if __name__ == '__main__':
    main()
