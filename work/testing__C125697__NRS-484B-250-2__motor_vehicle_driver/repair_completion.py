"""Bind the selected crossing to all five exact physical completion criteria.

This is an idempotent source repair. It deliberately clears proofs whose exact
construction hashes changed; rerun and rebind those proofs before readiness.
"""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def encoded(value):
    return json.dumps(value, indent=2, allow_nan=False) + '\n'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def repair():
    manifest_path = HERE / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    repaired = []
    for entry in manifest['cases']:
        suffix = entry['case_id'].split('__')[-1]
        axis = 1 if suffix == 'off_ego_right_near_time' else 0
        for selected in [entry, *entry['candidates']]:
            construction_path = HERE / selected['construction']
            construction = json.loads(construction_path.read_text())
            config_item = next(item for item in construction['files']
                               if item['path'] == 'config.json')
            config = json.loads(config_item['content'])
            polygon = config['site']['crossing_polygon_xy_m']
            if polygon != [[10, -5], [20, -5], [20, 5], [10, 5]]:
                raise ValueError('Selected crossing polygon changed: ' + suffix)
            config['physical_completion'] = {
                'criterion': 'intersection_clearance',
                'motion_source': 'crossing_history.jsonl',
                'body_key': 'ego_vertices_m',
                'intersection_polygon_xy_m': polygon,
                'exit_axis': axis,
                'exit_sign': 1,
                'minimum_progress_m': 0.25,
                'engineering_tolerances_not_legal': True,
            }
            config_item['content'] = encoded(config)
            if config_item.get('source'):
                source = REPO / config_item['source']
                source.write_text(config_item['content'])
            construction_path.write_text(encoded(construction))
            selected['construction_sha256'] = sha(construction_path)
            selected.pop('offline', None)
            selected.pop('compatibility', None)
            if selected is entry:
                selected.pop('negative', None)
                selected.pop('post_capture', None)
                selected.pop('physical_preparation', None)
                selected.pop('delivery_acceptance', None)
            repaired.append({'case_id': entry['case_id'],
                             'candidate': selected.get('id', 'primary'),
                             'construction_sha256': selected['construction_sha256'],
                             'exit_axis': axis})
    manifest['status'] = 'partial_crossing_completion_proofs_pending'
    manifest_path.write_text(encoded(manifest))
    return repaired


if __name__ == '__main__':
    print(json.dumps(repair(), indent=2))
