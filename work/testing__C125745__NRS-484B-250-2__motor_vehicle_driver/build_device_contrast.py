"""Build a source-hashed CPU plan for the still-unselected device contrast."""
import hashlib
import json
from pathlib import Path

from device_branch import build_presence_pair, validate_device_pair


HERE = Path(__file__).resolve().parent


def build():
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    entry = next(row for row in manifest['cases']
                 if row['case_id'].endswith('__stop_ego_left_near_time'))
    construction_path = HERE / entry['construction']
    construction_bytes = construction_path.read_bytes()
    if hashlib.sha256(construction_bytes).hexdigest() != entry['construction_sha256']:
        raise ValueError('Existing selected construction changed')
    construction = json.loads(construction_bytes)
    bundled_site = next(row for row in construction['files'] if row['path'] == 'site.json')
    site_path = HERE / 'site.json'
    site_bytes = site_path.read_bytes()
    if (bundled_site['content'] != site_bytes.decode() or
            not bundled_site['source'].endswith('/site.json')):
        raise ValueError('Selected site differs from construction')
    site = json.loads(site_bytes)
    if site['approach_relation'] != 'different_highways':
        raise ValueError('Device contrast requires the different-highway branch')
    present, absent = build_presence_pair(site)
    comparison = validate_device_pair(present, absent)
    return {'format': 'worker-c125745-device-presence-staged-construction',
            'status': 'staged_unselected', 'selected_reference_case': entry['case_id'],
            'selected_construction_sha256': entry['construction_sha256'],
            'selected_site_sha256': hashlib.sha256(site_bytes).hexdigest(),
            'world_setups': {'present': present, 'absent': absent},
            'comparison': comparison,
            'native_absence_or_presence_unverified': True,
            'official_status_requires_independent_original_source_review': True,
            'physical_acceptance_claimed': False,
            'legal_acceptance_claimed': False,
            'delivery_ready': False}


if __name__ == '__main__':
    print(json.dumps(build(), indent=2))
