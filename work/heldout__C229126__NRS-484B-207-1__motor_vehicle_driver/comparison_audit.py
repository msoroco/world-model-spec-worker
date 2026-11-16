"""Independent original-source audit of the C229126 left-gap comparison.

This checks software source isolation only. It cannot decide statutory safety or
establish that the planned geometry was realized in a Native recording.
"""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import shutil
import tempfile


PREFIX = 'heldout__C229126__NRS-484B-207-1__motor_vehicle_driver__'
CAMERAS = ('overview.mkv', 'approach.mkv', 'reference_corner.mkv',
           'driver_reference.mkv')
FIXED = ('road.xodr', 'capture/native_map_facts.json', 'trace.jsonl',
         'video_frames.jsonl', *CAMERAS)


def _read(path):
    if not path.is_file():
        raise ValueError(f'Missing original source: {path.name}')
    return path.read_bytes()


def _rows(path):
    return [json.loads(line) for line in _read(path).decode('utf-8').splitlines()
            if line.strip()]


def _gap(row):
    hx, hy = row['road_tangent_xy']
    lx, ly = -hy, hx
    ego = [x * lx + y * ly for x, y in row['ego_corners']]
    other = [x * lx + y * ly for x, y in row['other_corners']]
    return min(ego) - max(other)


def audit(wide, narrow):
    wide, narrow = Path(wide), Path(narrow)
    configs = [json.loads(_read(root / 'config.json')) for root in (wide, narrow)]
    expected = (PREFIX + 'left_pass_wide', PREFIX + 'left_pass_narrow')
    if tuple(c.get('selected_case_id') for c in configs) != expected:
        raise ValueError('Wrong exact comparison cases or order')
    if (configs[0].get('target_left_gap_m'),
            configs[1].get('target_left_gap_m')) != (1.5, 0.5):
        raise ValueError('Planned comparison gap changed')
    held = ('law_id', 'cell_id', 'actor', 'rate_hz', 'frames', 'duration_s',
            'requested_return_clearance_m', 'camera_names', 'required_atoms',
            'source_packets', 'cameras')
    for key in held:
        if configs[0].get(key) != configs[1].get(key):
            raise ValueError(f'Fixed configuration changed: {key}')
    if (configs[0].get('rate_hz'), configs[0].get('frames'),
            configs[0].get('duration_s')) != (20, 320, 16):
        raise ValueError('Capture timing changed')
    if set(configs[0].get('camera_names', [])) != {n[:-4] for n in CAMERAS}:
        raise ValueError('Four named cameras missing')
    fixed_hashes = {}
    for name in FIXED:
        a, b = (_read(root / name) for root in (wide, narrow))
        if a != b:
            raise ValueError(f'Fixed original source changed: {name}')
        fixed_hashes[name] = sha256(a).hexdigest()
    rows = [_rows(root / 'participant_footprints.jsonl') for root in (wide, narrow)]
    if not rows[0] or len(rows[0]) != len(rows[1]):
        raise ValueError('Original body history missing or unpaired')
    gaps = [[], []]
    for a, b in zip(*rows):
        if (a['frame'], a['time_s']) != (b['frame'], b['time_s']):
            raise ValueError('Original body frame join changed')
        for key in ('ego_id', 'other_id', 'other_corners', 'ego_heading_xy',
                    'other_heading_xy', 'road_tangent_xy', 'road_id',
                    'ego_lane_id', 'other_lane_id', 'other_speed_mps'):
            if a.get(key) != b.get(key):
                raise ValueError(f'Fixed original body condition changed: {key}')
        if len(a['ego_corners']) != 4 or len(b['ego_corners']) != 4:
            raise ValueError('Original four-corner bodies required')
        if [x for x, _ in a['ego_corners']] != [x for x, _ in b['ego_corners']]:
            raise ValueError('Longitudinal body motion changed')
        if a['ego_lane_id'] == a['other_lane_id'] and a['ego_corners'] != b['ego_corners']:
            raise ValueError('Fixed approach or return body changed')
        hx, hy = a['road_tangent_xy']
        if abs(hx * hx + hy * hy - 1) > 1e-6:
            raise ValueError('Invalid road tangent')
        along_a = [x * hx + y * hy for x, y in a['ego_corners']]
        along_other = [x * hx + y * hy for x, y in a['other_corners']]
        abreast = min(along_a) <= max(along_other) and min(along_other) <= max(along_a)
        if abreast and a['ego_lane_id'] != a['other_lane_id']:
            gaps[0].append(_gap(a))
            gaps[1].append(_gap(b))
    if not gaps[0] or min(gaps[0]) <= min(gaps[1]):
        raise ValueError('Deliberate measured left-gap difference missing')
    return {'format': 'worker-c229126-comparison-audit',
            'comparison_id': 'left_pass_clearance', 'case_ids': list(expected),
            'fixed_source_sha256': fixed_hashes,
            'measured_minimum_abreast_gap_m': [min(gaps[0]), min(gaps[1])],
            'physical_acceptance_claimed': False,
            'legal_acceptance_claimed': False}


def selftest(wide, narrow):
    result = audit(wide, narrow)
    assert result['measured_minimum_abreast_gap_m'] == [2.0, 0.5]
    with tempfile.TemporaryDirectory() as temp:
        changed = Path(temp) / 'narrow'
        shutil.copytree(narrow, changed)
        (changed / 'participant_footprints.jsonl').unlink()
        try:
            audit(wide, changed)
        except ValueError as error:
            assert 'Missing original source' in str(error)
        else:
            raise AssertionError('Missing body source accepted')
        shutil.copy2(Path(narrow) / 'participant_footprints.jsonl',
                     changed / 'participant_footprints.jsonl')
        (changed / 'road.xodr').write_text('changed fixed road\n')
        try:
            audit(wide, changed)
        except ValueError as error:
            assert 'Fixed original source changed' in str(error)
        else:
            raise AssertionError('Changed fixed road accepted')
    return result


def _first_return(rows):
    samples = []
    for row in rows:
        hx, hy = row['road_tangent_xy']
        left = (-hy, hx)
        ego_x = [x * hx + y * hy for x, y in row['ego_corners']]
        other_x = [x * hx + y * hy for x, y in row['other_corners']]
        ego_y = [x * left[0] + y * left[1] for x, y in row['ego_corners']]
        samples.append((row['frame'], sum(ego_y) / 4,
                        min(ego_x) - max(other_x),
                        min(ego_x) <= max(other_x) and min(other_x) <= max(ego_x)))
    first_abreast = next((i for i, row in enumerate(samples) if row[3]), None)
    if first_abreast is None:
        raise ValueError('Missing original abreast phase')
    for i in range(first_abreast + 1, len(samples)):
        if samples[i][1] < samples[i-1][1] - .1:
            return samples[i][0], samples[i][2]
    raise ValueError('Missing original rightward return')


def audit_return(before, after):
    before, after = Path(before), Path(after)
    roots = (before, after)
    configs = [json.loads(_read(root / 'config.json')) for root in roots]
    expected = (PREFIX + 'return_before_clear', PREFIX + 'return_after_clear')
    if tuple(c.get('selected_case_id') for c in configs) != expected:
        raise ValueError('Wrong exact return comparison cases or order')
    if tuple(c.get('requested_return_clearance_m') for c in configs) != (-.5, 1.5):
        raise ValueError('Return comparison control changed')
    fixed_keys = ('law_id', 'cell_id', 'actor', 'rate_hz', 'frames', 'duration_s',
                  'target_left_gap_m', 'camera_names', 'required_atoms',
                  'source_packets', 'cameras')
    for key in fixed_keys:
        if configs[0].get(key) != configs[1].get(key):
            raise ValueError(f'Fixed return configuration changed: {key}')
    if (configs[0]['rate_hz'], configs[0]['frames'], configs[0]['duration_s'],
            configs[0]['target_left_gap_m']) != (20, 320, 16, 1.0):
        raise ValueError('Return capture or left-pass target changed')
    fixed_hashes = {}
    for name in FIXED:
        a, b = (_read(root / name) for root in roots)
        if a != b:
            raise ValueError(f'Fixed original source changed: {name}')
        fixed_hashes[name] = sha256(a).hexdigest()
    histories = [_rows(root / 'participant_footprints.jsonl') for root in roots]
    if not histories[0] or len(histories[0]) != len(histories[1]):
        raise ValueError('Original return body history missing or unpaired')
    for a, b in zip(*histories):
        for key in ('frame', 'time_s', 'ego_id', 'other_id', 'other_corners',
                    'ego_heading_xy', 'other_heading_xy', 'road_tangent_xy',
                    'road_id', 'ego_lane_id', 'other_lane_id', 'other_speed_mps'):
            if a.get(key) != b.get(key):
                raise ValueError(f'Fixed original return condition changed: {key}')
        if [x for x, _ in a['ego_corners']] != [x for x, _ in b['ego_corners']]:
            raise ValueError('Longitudinal return motion changed')
    measured = [_first_return(rows) for rows in histories]
    if not (measured[0][0] < measured[1][0] and
            measured[0][1] <= 0 < measured[1][1]):
        raise ValueError('Measured before/after body clearance order missing')
    return {'format': 'worker-c229126-comparison-audit',
            'comparison_id': 'return_clearance_order', 'case_ids': list(expected),
            'fixed_source_sha256': fixed_hashes,
            'first_return_frame_and_clearance_m': measured,
            'physical_acceptance_claimed': False,
            'legal_acceptance_claimed': False}


def selftest_return(before, after):
    result = audit_return(before, after)
    assert result['first_return_frame_and_clearance_m'] == [(38037, -2.0), (38040, 7.0)]
    with tempfile.TemporaryDirectory() as temp:
        changed = Path(temp) / 'after'
        shutil.copytree(after, changed)
        config = json.loads((changed / 'config.json').read_text())
        config['target_left_gap_m'] = .5
        (changed / 'config.json').write_text(json.dumps(config))
        try:
            audit_return(before, changed)
        except ValueError as error:
            assert 'Fixed return configuration changed' in str(error)
        else:
            raise AssertionError('Changed left-pass policy accepted')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--wide')
    parser.add_argument('--narrow')
    parser.add_argument('--selftest', action='store_true')
    parser.add_argument('--return-before')
    parser.add_argument('--return-after')
    args = parser.parse_args()
    if bool(args.return_before) != bool(args.return_after):
        parser.error('Supply both return cases')
    if args.return_before:
        result = (selftest_return if args.selftest else audit_return)(
            args.return_before, args.return_after)
    else:
        if not args.wide or not args.narrow:
            parser.error('Supply both left-gap comparison cases')
        result = (selftest if args.selftest else audit)(args.wide, args.narrow)
    print(json.dumps(result, indent=2))
