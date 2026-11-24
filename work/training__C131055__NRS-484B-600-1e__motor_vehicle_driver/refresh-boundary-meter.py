"""Refresh all selected bundles after exact-at source witness correction."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + '\n')


manifest_path = HERE / 'execution-manifest.json'
manifest = json.loads(manifest_path.read_text())
if len(manifest['cases']) != 3:
    raise ValueError('Expected exact below, above and at cases')
for entry in manifest['cases']:
    for candidate in (entry, *entry['candidates']):
        path = HERE / candidate['construction']
        bundle = json.loads(path.read_text())
        for item in bundle['files']:
            name = {'measure.py': 'measure.py', 'finalize.py': 'finalize_v2.py',
                    'tests/test_native.py': 'tests/test_native.py'}.get(item['path'])
            if name:
                item['content'] = (HERE / 'native' / name).read_text()
        write(path, bundle)
        candidate['construction_sha256'] = sha(path)
        candidate['preparation_status'] = 'exact_boundary_meter_reproof_pending'
        for key in ('offline', 'compatibility', 'negative', 'saved_processing',
                    'delivery_diagnostic', 'delivery_acceptance'):
            candidate.pop(key, None)
manifest['status'] = 'partial_exact_boundary_meter_reproof_pending'
write(manifest_path, manifest)
print(json.dumps({'manifest_sha256': sha(manifest_path),
                  'selected_construction_sha256': [case['construction_sha256']
                                                   for case in manifest['cases']]}))
