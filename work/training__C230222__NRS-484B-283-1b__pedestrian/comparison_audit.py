"""Check source-bound curb comparison without inferring a legal verdict."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_rows(path):
    if not path.is_file():
        raise ValueError('Missing original curb source rows')
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    if len(rows) != 600:
        raise ValueError('Complete 600-frame curb source required')
    return rows


def audit(first, second):
    first, second = Path(first), Path(second)
    a, b = read_rows(first), read_rows(second)
    fixed = ('native_frame', 'time_s', 'vehicle_id', 'vehicle_xy_m',
             'vehicle_speed_mps', 'pedestrian_id')
    if any(x[key] != y[key] for x, y in zip(a, b) for key in fixed):
        raise ValueError('Fixed vehicle, clock or actor context differs')
    if [x['native_frame'] for x in a] != list(range(100, 700)):
        raise ValueError('Original source-frame identity gap')
    def departure(rows):
        return next((row['native_frame'] for row in rows
                     if row['pedestrian_xy_m'][0] > -4.5), None)
    departures = [departure(a), departure(b)]
    if any(value is None for value in departures) or departures[0] == departures[1]:
        raise ValueError('Deliberate curb departure timing difference absent')
    if any(x['pedestrian_xy_m'] == y['pedestrian_xy_m'] for x, y in zip(a, b)) is False:
        raise ValueError('No shared pre-departure pedestrian context')
    return {'format': 'c230222-curb-comparison-audit-v1',
            'source_kind': 'synthetic_scene_request', 'frames': 600,
            'source_sha256': [sha(first), sha(second)],
            'fixed_vehicle_and_clock': True,
            'departure_frames': departures,
            'deliberate_difference': 'curb departure timing; conditional stopping range only',
            'actual_driver_capability_proven': False,
            'physical_or_legal_acceptance_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--first', type=Path, required=True)
    parser.add_argument('--second', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(json.dumps(audit(args.first, args.second), indent=2) + '\n')
