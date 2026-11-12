"""Rebind all selected constructions to complete-body entry analysis.

Proof bindings are removed until the exact offline/compatibility runs are redone.
"""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def promote():
    source = (HERE/'simultaneous_entries.py').read_text()
    if 'inside=polygon.covers(body)' not in source:
        raise ValueError('Complete-body predicate absent')
    manifest_path = HERE/'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    changed = []
    for entry in manifest['cases']:
        for selected in [entry, *entry.get('candidates', [])]:
            path = HERE/selected['construction']
            bundle = json.loads(path.read_text())
            item = next(f for f in bundle['files'] if f['path'] == 'simultaneous_entries.py')
            if item['content'] != source:
                item['content'] = source
                path.write_text(json.dumps(bundle, indent=2, allow_nan=False)+'\n')
                selected['construction_sha256'] = sha(path)
                changed.append(selected['construction'])
            selected.pop('offline', None)
            selected.pop('compatibility', None)
            if selected is entry:
                selected.pop('negative', None)
    manifest['status'] = 'partial_complete_body_reproof_pending'
    manifest_path.write_text(json.dumps(manifest, indent=2, allow_nan=False)+'\n')
    return {'changed_constructions': changed, 'count': len(changed)}


if __name__ == '__main__':
    print(json.dumps(promote(), indent=2))
