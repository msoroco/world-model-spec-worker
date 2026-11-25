"""Check the selected 0.45/0.55 request contrast and diagnostic source joins."""
import copy
import json
from pathlib import Path

from route import requested_rows


def verify(low, high):
    if len(low) != 600 or len(high) != 600:
        raise ValueError('Incomplete selected comparison')
    differences = set()
    for index, (a, b) in enumerate(zip(low, high)):
        if a['frame'] != index or b['frame'] != index or a['time_s'] != b['time_s']:
            raise ValueError('Selected frame/time context changed')
        changed = {key for key in set(a) | set(b) if a.get(key) != b.get(key)}
        if changed != {'ego_center_xyz_m', 'requested_ego_right_half_body_fraction'}:
            raise ValueError('Uncontrolled selected contrast')
        if a['ego_center_xyz_m'][0] != b['ego_center_xyz_m'][0] or a['ego_center_xyz_m'][2] != b['ego_center_xyz_m'][2]:
            raise ValueError('Selected route changed outside lateral setting')
        if a['ego_center_xyz_m'][1] != .1 or b['ego_center_xyz_m'][1] != -.1:
            raise ValueError('Selected lateral settings changed')
        differences.update(changed)
    return {'frames': 600, 'controlled_differences': sorted(differences),
            'fixed_context': ['opposite actor motion', 'authored paved bounds',
                              'ego longitudinal motion', 'four cameras', 'frame/time'],
            'legal_compliance': 'unassessed', 'physical_acceptance_claimed': False}


def main():
    low, high = list(requested_rows('0.45')), list(requested_rows('0.55'))
    proof = verify(low, high)
    corrupt = copy.deepcopy(high)
    corrupt[300]['oncoming_center_xyz_m'][0] += 1
    try:
        verify(low, corrupt)
    except ValueError as exc:
        proof['negative'] = str(exc)
    else:
        raise AssertionError('Changed opposite actor escaped comparison audit')
    print(json.dumps(proof, indent=2))


if __name__ == '__main__':
    main()
