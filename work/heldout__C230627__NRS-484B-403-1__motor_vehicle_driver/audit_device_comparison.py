"""Audit the added mapped-device observation against fixed C230627 centerline."""

import json
from pathlib import Path


def read(path):
    return json.loads(Path(path).read_text())


def audit(root):
    root = Path(root)
    a = read(root/'construction.json')
    b = read(root/'construction-prohibition_403_2.json')
    if not (a['case_id'].endswith('__safety_clear') and
            b['case_id'].endswith('__prohibition_403_2')):
        raise ValueError('Wrong mapped-device comparison cases')
    files_a = {e['path']: e['content'] for e in a['files']}
    files_b = {e['path']: e['content'] for e in b['files']}
    if files_a.keys() != files_b.keys() or any(
            files_a[k] != files_b[k] for k in files_a if k != 'config.json'):
        raise ValueError('Fixed runner or source implementation changed')
    config_a, config_b = (json.loads(files_a['config.json']),
                          json.loads(files_b['config.json']))
    for key in ('law_id', 'cell_id', 'actor', 'rate_hz', 'frames',
                'duration_s', 'cameras', 'required_atoms', 'source_packets',
                'engineering'):
        if config_a[key] != config_b[key]:
            raise ValueError('Fixed centerline construction changed: ' + key)
    description_a = config_a['case']['recording_description']
    description_b = config_b['case']['recording_description']
    if (description_a['channels'] != description_b['channels'] or
            description_a['limitations'] != description_b['limitations'] or
            description_b['context_inputs'][:len(description_a['context_inputs'])] !=
            description_a['context_inputs'] or
            len(description_b['context_inputs']) != len(description_a['context_inputs']) + 1 or
            description_b['context_inputs'][-1]['name'] != 'mapped_no_u_turn_device'):
        raise ValueError('Fixed measurement contract changed')
    source_a, source_b = (read(root/'diagnostic-safety_clear.json'),
                          read(root/'diagnostic-prohibition_403_2.json'))
    if source_a['graphs'] != source_b['graphs'] or source_a['videos'] != source_b['videos']:
        raise ValueError('Fixed source graph or camera media changed')
    files_a, files_b = source_a['files'], source_b['files']
    if set(files_b) != set(files_a) | {'u_turn_device.json'} or any(
            files_a[k] != files_b[k] for k in files_a):
        raise ValueError('Uncontrolled original source difference')
    device = json.loads(files_b['u_turn_device.json'])['mapped_no_u_turn_device']
    if not device.get('landmark_id') or device.get('official_device_status') is not None or device.get('governing_lane_status') is not None or device.get('pixel_visibility_status') is not None:
        raise ValueError('Mapped device source is missing or overclaims status')
    return {'comparison_id': 'prohibition_403_2',
            'case_ids': [a['case_id'], b['case_id']],
            'fixed_centerline_and_motion_verified': True,
            'added_source': 'u_turn_device.json',
            'official_device_status': None, 'governing_lane_status': None,
            'pixel_visibility_status': None,
            'statutory_applicability_judgment': None}


if __name__ == '__main__':
    print(json.dumps(audit(Path(__file__).resolve().parent), sort_keys=True))
