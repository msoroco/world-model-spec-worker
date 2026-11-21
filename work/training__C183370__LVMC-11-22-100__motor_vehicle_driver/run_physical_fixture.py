"""Exercise C183370 route and lifecycle checks with source-shaped CPU mocks."""
import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / 'native'))
from physical_outcome import EVENTS, check_lifecycle, classify


def sample_rows(*, crossing, kind):
    rows = []
    endpoint = 0.0 if kind == 'incomplete_motion' else 5.0
    y = 0.0 if crossing else 5.0
    for index in range(600):
        x = -5.0 + (endpoint + 5.0) * index / 599
        body = [[x + dx, y + dy, z] for z in (0.0, 1.0)
                for dx, dy in ((-0.5, -0.5), (0.5, -0.5),
                               (0.5, 0.5), (-0.5, 0.5))]
        rows.append({'frame': index, 'time_s': (index + 1) / 20,
                     'ego_position_xyz_m': [x, y, 1.0],
                     'ego_body_vertices_xyz_m': body,
                     'ego_speed_mps': 0.0 if index == 599 else 0.5})
    return rows[:-1] if kind == 'missing_evidence' else rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--manifest', type=Path, default=HERE / 'execution-manifest.json')
    parser.add_argument('--kind', required=True, choices=(
        'complete_motion', 'incomplete_motion', 'missing_evidence', 'lifecycle'))
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    entry = next((row for row in manifest['cases']
                  if row['case_id'] == args.case), None)
    if entry is None:
        raise ValueError('Select an exact C183370 case')
    if args.kind == 'lifecycle':
        outcome = check_lifecycle(EVENTS.copy(), 0)
        for invalid, code in ((EVENTS[:-2] + EVENTS[-1:] + EVENTS[-2:-1], 0),
                              (EVENTS, 1)):
            try:
                check_lifecycle(invalid, code)
            except ValueError:
                continue
            raise AssertionError('Invalid Native lifecycle accepted')
    else:
        short = args.case[len(HERE.name) + 2:]
        crossing = short == 'reference' or short.endswith('crossing')
        rows = sample_rows(crossing=crossing, kind=args.kind)
        outcome = classify(rows, [[-1, -1], [1, -1], [1, 1], [-1, 1]], crossing)
        expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                    'missing_evidence': 'unverified'}[args.kind]
        if outcome['physical_checks']['maneuver']['status'] != expected:
            raise AssertionError('Physical fixture classified another outcome')
        outcome['case_id'] = args.case
        outcome['construction_sha256'] = entry['construction_sha256']
    outcome['cpu_fixture_mock'] = True
    outcome['original_native_motion_verified'] = False
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.output.exists():
        raise ValueError('Retain previous fixture result')
    args.output.write_text(json.dumps(outcome, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'case_id': args.case, 'kind': args.kind,
                      'cpu_fixture_mock': True,
                      'original_native_motion_verified': False}))


if __name__ == '__main__':
    main()
