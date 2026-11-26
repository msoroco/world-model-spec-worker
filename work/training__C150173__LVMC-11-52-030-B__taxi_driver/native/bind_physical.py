"""Bind exact current-construction physical CPU receipts into selected cases."""
import hashlib
import json
from pathlib import Path


PACKAGE = Path(__file__).resolve().parent.parent
MANIFEST = PACKAGE / 'selected-draft-manifest.json'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest['cases']:
        suffix = entry['case_id'].rsplit('__', 1)[1]
        path = PACKAGE / 'native-selected' / suffix / 'physical-preparation.json'
        receipt = json.loads(path.read_text())
        if receipt['case_id'] != entry['case_id'] or receipt['construction_sha256'] != entry['construction_sha256']:
            raise ValueError('Physical proof binds another selected construction: ' + suffix)
        entry['physical_preparation'] = {
            'receipt': str(path.relative_to(PACKAGE)), 'sha256': sha(path)}
    MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'cases': len(manifest['cases']), 'manifest_sha256': sha(MANIFEST)}))


if __name__ == '__main__':
    main()
