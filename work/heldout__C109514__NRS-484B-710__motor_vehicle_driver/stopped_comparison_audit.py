"""Independent source-bound audit of the stopped drive-to distance triple."""
from hashlib import sha256
import importlib.util
import json
from math import isclose
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('fire_comparison_audit', HERE / 'fire_comparison_audit.py')
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
FEET_PER_METRE = 3.280839895013123


def audit(rows):
    if len(rows) != 3 or [r.get('target_ft') for r in rows] != [499, 500, 501]:
        raise ValueError('Stopped comparison requires ordered 499/500/501 ft cases')
    measured = [base._read_case(row) for row in rows]
    if len({row['case_id'] for row in measured}) != 3:
        raise ValueError('Stopped comparison has duplicate case IDs')
    values = [json.loads(Path(row['measurement_path']).read_text()) for row in rows]
    if any(value['branch'] != 'stopped_drive_to' for value in values):
        raise ValueError('Stopped comparison changed branch')
    for key in ('apparatus_answered_alarm', 'authorized_emergency', 'official_business', 'branch'):
        if len({row['fixed'][key] for row in measured}) != 1:
            raise ValueError('Stopped comparison changed fixed context: ' + key)
    if len({value['state_source_sha256'] for value in values}) != 1:
        raise ValueError('Stopped comparison changed participant motion state')
    footprints = [[json.loads(line) for line in Path(row['participant_path']).read_text().splitlines()]
                  for row in rows]
    for frame_rows in zip(*footprints):
        baseline = frame_rows[1]
        for target, row in zip((499, 500, 501), frame_rows):
            if (row['frame'], row['time_s'], row['ego_id'], row['apparatus_id'], row['ego_corners']) != (
                    baseline['frame'], baseline['time_s'], baseline['ego_id'],
                    baseline['apparatus_id'], baseline['ego_corners']):
                raise ValueError('Stopped comparison changed subject or original frame')
            for corner, reference in zip(row['apparatus_corners'], baseline['apparatus_corners']):
                if not isclose(corner[0] - reference[0], (target - 500) / FEET_PER_METRE,
                               rel_tol=0, abs_tol=1e-8) or not isclose(corner[1], reference[1], abs_tol=1e-8):
                    raise ValueError('Stopped comparison changed apparatus geometry beyond target shift')
    first = [next(item['centre_distance_ft'] for item in value['observations']
                  if item['branch_active']) for value in values]
    if not (first[0] < first[1] < first[2]) or any(
            not isclose(b - a, 1, abs_tol=1e-6) for a, b in zip(first, first[1:])):
        raise ValueError('Stopped comparison did not realize ordered one-foot probes')
    return {'comparison_id': 'stopped_drive_to_500_boundary', 'passed': True,
            'case_ids': [row['case_id'] for row in measured],
            'measurement_sha256': [row['measurement_sha256'] for row in measured],
            'first_active_centre_distance_ft': first,
            'legal_judgment': None}


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(); parser.add_argument('spec')
    args = parser.parse_args()
    print(json.dumps(audit(json.loads(Path(args.spec).read_text())['cases']), indent=2))
