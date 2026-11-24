"""Bind staged left/straight CPU constructions to the selected opposite case."""
import hashlib
import json
from pathlib import Path

from turn_branch import build_turn_pair, validate_turn_pair


HERE = Path(__file__).resolve().parent


def build():
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    entry = next(row for row in manifest['cases']
                 if row['case_id'].endswith('__stop_opposite_left_turn'))
    construction_path = HERE / entry['construction']
    payload = construction_path.read_bytes()
    if hashlib.sha256(payload).hexdigest() != entry['construction_sha256']:
        raise ValueError('Selected opposite construction changed')
    bundled = next(row for row in json.loads(payload)['files']
                   if row['path'] == 'site.json')
    site_path = HERE / 'fourth-site.json'
    site_bytes = site_path.read_bytes()
    if (bundled['content'] != site_bytes.decode() or
            not bundled['source'].endswith('/fourth-site.json')):
        raise ValueError('Selected opposite site changed')
    left, straight = build_turn_pair(json.loads(site_bytes))
    comparison = validate_turn_pair(left, straight)
    return {'format': 'worker-c125745-turn-intent-staged-construction',
            'status': 'staged_unselected',
            'selected_reference_case': entry['case_id'],
            'selected_construction_sha256': entry['construction_sha256'],
            'selected_site_sha256': hashlib.sha256(site_bytes).hexdigest(),
            'world_setups': {'left': left, 'straight': straight},
            'comparison': comparison,
            'native_motion_unverified': True,
            'legal_turn_judgment_unresolved': True,
            'physical_acceptance_claimed': False,
            'legal_acceptance_claimed': False,
            'delivery_ready': False}


if __name__ == '__main__':
    print(json.dumps(build(), indent=2))
