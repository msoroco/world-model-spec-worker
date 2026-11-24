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
            name = {'runner.py': 'runner.py', 'measure.py': 'measure.py', 'finalize.py': 'finalize_v2.py',
                    'tests/test_native.py': 'tests/test_native.py'}.get(item['path'])
            if name:
                item['content'] = (HERE / 'native' / name).read_text()
                if item['path'] == 'runner.py' and candidate is not entry:
                    old = 'throttle = min(1.0, max(0.0, (target - speed) * .35))'
                    assert item['content'].count(old) == 1
                    item['content'] = item['content'].replace(old, 'throttle = min(1.0, max(0.0, (target - speed) * .55))')
            if item['path'] == 'config.json':
                config = json.loads(item['content'])
                cameras = [
                    ('overview', 1920, 1080, 'fixed_roundabout_arc_exit', 85),
                    ('approach', 1280, 720, 'fixed_entry_arc', 85),
                    ('reference_corner', 1280, 720, 'fixed_exit_tangent', 85),
                    ('driver_reference', 1280, 720, 'vehicle_chase', 85),
                ]
                config['cameras'] = [dict(name=n, width=w, height=h, fps=20,
                                          pose_strategy=pose, fov_deg=fov)
                                     for n, w, h, pose, fov in cameras]
                item['content'] = json.dumps(config, sort_keys=True, indent=2) + '\n'
        write(path, bundle)
        candidate['construction_sha256'] = sha(path)
        candidate['preparation_status'] = 'exact_boundary_meter_reproof_pending'
        for key in ('offline', 'compatibility', 'negative', 'saved_processing',
                    'delivery_diagnostic', 'delivery_acceptance'):
            candidate.pop(key, None)
    entry.pop('physical_preparation', None)
    entry.pop('post_capture', None)
manifest['status'] = 'partial_exact_boundary_meter_reproof_pending'
write(manifest_path, manifest)
print(json.dumps({'manifest_sha256': sha(manifest_path),
                  'selected_construction_sha256': [case['construction_sha256']
                                                   for case in manifest['cases']]}))
