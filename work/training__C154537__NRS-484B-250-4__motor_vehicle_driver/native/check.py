"""Check exact frozen source and final fallback request; no CARLA import at CPU check."""
import hashlib
import json
from pathlib import Path

from route import FRAMES, RATE_HZ, requested_rows


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check():
    root = Path.cwd()
    config = json.loads((root / 'config.json').read_text())
    assignment = json.loads((root / 'assignment-source.json').read_text())
    rows = [json.loads(line) for line in (root / 'request.jsonl').read_text().splitlines()]
    if (sha(root / 'assignment-source.json') != config['assignment_sha256'] or
            sha(root / 'request.jsonl') != config['request_sha256'] or
            assignment['law']['text'] != config['law_text'] or
            assignment['cell']['cell_id'] != 'C154537' or
            assignment['cell']['layout'] != 'one_way_to_one_way_intersection' or
            assignment['cell']['control'] != 'inoperative_signal'):
        raise ValueError('Frozen law, cell or source hash differs')
    if len(rows) != FRAMES or config['rate_hz'] != RATE_HZ or config['duration_s'] != 30:
        raise ValueError('Full 600-frame 30-second request required')
    expected = list(requested_rows(config['case_suffix']))
    if rows != expected:
        raise ValueError('Exact requested track or source context differs')
    if not all(not row['requested_stop_line_present'] and
               not row['requested_near_side_crosswalk_present'] and
               row['requested_signal_state'] == 'installed_uncovered_inoperative'
               for row in rows):
        raise ValueError('Final stopping-location hierarchy differs')
    if config['case_suffix'] == 'controlled_1':
        if any(rows[i]['ego_center_xy_m'][0] != -9.0 for i in range(130, 221)):
            raise ValueError('Stop plateau request differs')
        if rows[220]['ego_front_x_m'] >= -6:
            raise ValueError('Requested stop is after intersection entry')
    else:
        if any(rows[i+1]['ego_center_xy_m'][0] <= rows[i]['ego_center_xy_m'][0]
               for i in range(220)):
            raise ValueError('Rolling contrast request differs')
    return {'passed': True, 'case_id': config['case_id'], 'frames': FRAMES,
            'rate_hz': RATE_HZ, 'native_observed': False,
            'driver_view_nearest_point_proven': False,
            'official_signal_authority_proven': False, 'legal_verdict': None}


if __name__ == '__main__':
    print(json.dumps(check()))
