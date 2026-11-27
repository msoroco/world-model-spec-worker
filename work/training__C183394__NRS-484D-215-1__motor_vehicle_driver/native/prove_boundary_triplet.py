"""Exact authored 499/500/501-foot start and diagnostic source checks."""
import json
from math import hypot
from pathlib import Path

from probe_scene import FEET, request, validate_request


REPO = Path(__file__).resolve().parents[3]
SCRATCH = REPO / '.runtime-work/c183394'
for case, feet in FEET.items():
    source = request(case)
    result = validate_request(source)
    assert result['target_ft'] == feet and result['physical_verified'] is False
    attempt = SCRATCH / f'civil-compat-{case}-primary'
    row = json.loads((attempt / 'beam-rows.jsonl').read_text().splitlines()[0])
    distance_ft = hypot(row['ego_x_m']-row['oncoming_x_m'],
                        row['ego_y_m']-row['oncoming_y_m']) / .3048
    assert abs(distance_ft-feet) < 1e-9
    frame = json.loads((attempt / 'video_frames.jsonl').read_text().splitlines()[0])
    assert row['frame'] == 0 and row['native_frame'] == frame['native_frame']
    print('PASS', case, feet, 'authored and diagnostic start; original physical unverified')
