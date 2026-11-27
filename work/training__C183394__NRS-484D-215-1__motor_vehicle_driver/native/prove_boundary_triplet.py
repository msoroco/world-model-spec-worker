"""Exact authored 499/500/501-foot start and diagnostic source checks."""
import json
from math import hypot
from pathlib import Path
import shutil
import sys
import tempfile

from probe_scene import FEET, request, validate_request


REPO = Path(__file__).resolve().parents[3]
SCRATCH = REPO / '.runtime-work/c183394'
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from boundary_comparison_audit import check_triplet
attempts = []
for case, feet in FEET.items():
    source = request(case)
    result = validate_request(source)
    assert result['target_ft'] == feet and result['physical_verified'] is False
    attempt = SCRATCH / f'civil-compat-{case}-primary'
    attempts.append(attempt)
    row = json.loads((attempt / 'beam-rows.jsonl').read_text().splitlines()[0])
    distance_ft = hypot(row['ego_x_m']-row['oncoming_x_m'],
                        row['ego_y_m']-row['oncoming_y_m']) / .3048
    assert abs(distance_ft-feet) < 1e-9
    frame = json.loads((attempt / 'video_frames.jsonl').read_text().splitlines()[0])
    assert row['frame'] == 0 and row['native_frame'] == frame['native_frame']
    print('PASS', case, feet, 'authored and diagnostic start; original physical unverified')
value = check_triplet(attempts)
assert value['measured_start_distance_ft'] == [499, 500, 501]
assert value['original_500ft_boundary_sample_confirmed'] is False
with tempfile.TemporaryDirectory(dir=SCRATCH) as temporary:
    altered = Path(temporary) / 'at'
    shutil.copytree(attempts[1], altered)
    config_path = altered / 'config.json'
    config = json.loads(config_path.read_text())
    config['duration_s'] = 29
    config_path.write_text(json.dumps(config)+'\n')
    try:
        check_triplet([attempts[0],altered,attempts[2]])
    except ValueError as error:
        assert 'fixed configuration' in str(error)
    else:
        raise AssertionError('Changed comparison duration accepted')
print('PASS boundary triplet fixed-source audit and changed-duration rejection')
