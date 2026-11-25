"""CPU check for exact yielding requests and the frozen C154537 cell."""
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
    case = config['case_suffix']
    if case not in ('controlled_5', 'controlled_6', 'controlled_7') or \
            sha(root / 'assignment-source.json') != config['assignment_sha256'] or \
            sha(root / 'request.jsonl') != config['request_sha256'] or \
            assignment['law']['text'] != config['law_text'] or \
            assignment['cell']['cell_id'] != 'C154537' or \
            assignment['cell']['control'] != 'inoperative_signal' or \
            assignment['cell']['layout'] != 'one_way_to_one_way_intersection':
        raise ValueError('Frozen exact law, source or cell differs')
    if config['rate_hz'] != RATE_HZ or config['duration_s'] != 30 or \
            rows != list(requested_rows(case)):
        raise ValueError('Exact yielding request differs')
    if len(rows) != FRAMES or any(row['ego_center_xy_m'][0] != -9.0
                                  for row in rows[130:221]):
        raise ValueError('Full-frame ego stop plateau missing')
    if case == 'controlled_5' and not (all(row['other_center_xy_m'][1] == -27.0
                                         for row in rows[40:60]) and
                                         rows[225]['other_center_xy_m'][1] > 8):
        raise ValueError('Prior-stop and clearance request differs')
    if case in ('controlled_6', 'controlled_7') and not all(
            row['other_center_xy_m'][1] == 0.0 for row in rows[175:260]):
        raise ValueError('Inside-intersection request differs')
    if case == 'controlled_7' and not all(row['ego_center_xy_m'][0] == -9.0
                                          for row in rows[220:301]):
        raise ValueError('Ego yielding hold request differs')
    return {'passed': True, 'case_id': config['case_id'], 'frames': FRAMES,
            'rate_hz': RATE_HZ, 'native_observed': False,
            'original_native_observed': False,
            'driver_view_nearest_point_proven': False,
            'official_signal_authority_proven': False,
            'physical_acceptance_claimed': False, 'legal_verdict': None}
