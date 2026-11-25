"""CPU check for the near-side crosswalk request and frozen assignment."""
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
    if config['case_suffix'] != 'controlled_4' or config['rate_hz'] != RATE_HZ or config['duration_s'] != 30 or len(rows) != FRAMES:
        raise ValueError('Exact 600-frame crosswalk case differs')
    if rows != list(requested_rows('controlled_4')):
        raise ValueError('Crosswalk requested track differs')
    if rows[120]['ego_front_x_m'] != -10 or rows[215]['ego_front_x_m'] != -10:
        raise ValueError('Near-side crosswalk stop plateau differs')
    return {'passed': True, 'case_id': config['case_id'], 'frames': FRAMES,
            'rate_hz': RATE_HZ, 'native_observed': False,
            'driver_view_nearest_point_proven': False,
            'official_signal_authority_proven': False, 'legal_verdict': None}
