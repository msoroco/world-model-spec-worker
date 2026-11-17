"""Add the opposite approach as a measured sightline fallback for both cases.

This changes the Native lane, bus heading, rail approach and generated camera
poses through ``direction=-1``.  It does not assert that the sightline improves
until original pixels can be reviewed.
"""
import copy
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / 'execution-manifest.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def build():
    manifest = json.loads(MANIFEST.read_text())
    made = []
    for entry in manifest['cases']:
        case_id = entry['case_id']
        if any(item.get('id') == 'fallback1' for item in entry.get('candidates', [])):
            raise ValueError('Retain existing fallback1 and its receipts: ' + case_id)
        primary = json.loads((ROOT / entry['construction']).read_text())
        alternate = copy.deepcopy(primary)
        config = next(item for item in alternate['files'] if item['path'] == 'config.json')
        settings = json.loads(config['content'])
        if settings['direction'] != 1:
            raise ValueError('Primary approach changed: ' + case_id)
        settings['direction'] = -1
        settings['fallback_reason'] = 'Review the opposite Native approach if the primary officer gesture is occluded'
        config['content'] = json.dumps(settings, indent=2, sort_keys=True) + '\n'
        alternate['mechanisms'].append('opposite Native lane and camera poses for sightline review')
        path = ROOT / 'constructions' / (case_id.rsplit('__', 1)[-1] + '-fallback1.json')
        if path.exists():
            raise ValueError('Retain existing fallback construction: ' + str(path))
        write(path, alternate)
        entry.setdefault('candidates', []).append({
            'id': 'fallback1',
            'trigger': {'source': 'overview/driver-view original Native video and officer signal rows',
                        'metric': 'governing-frame officer gesture visibility at the bus approach',
                        'failure_condition': 'No unoccluded governing gesture in either primary view'},
            'changed_knobs': ['direction=+1 to -1: Native opposite lane, bus heading, rail approach and camera poses'],
            'construction': str(path.relative_to(ROOT)),
            'construction_sha256': sha(path),
        })
        made.append({'case_id': case_id, 'construction_sha256': sha(path)})
    write(MANIFEST, manifest)
    return made


if __name__ == '__main__':
    print(json.dumps(build(), indent=2))
