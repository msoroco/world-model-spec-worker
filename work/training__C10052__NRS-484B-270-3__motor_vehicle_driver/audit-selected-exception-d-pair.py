"""Compare selected exception D pair from source-bound synthetic measurements."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SUFFIXES = ('exception_d_duty', 'exception_d_routine')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def check(negative=False):
    manifest = json.loads((ROOT / 'execution-manifest.json').read_text())
    cases = {row['case_id']: row for row in manifest['cases']}
    plan = json.loads((ROOT / 'case-plan.json').read_text())
    comparison = next(row for row in plan['comparisons']
                      if row['comparison_id'].endswith('__comparison_exception_d'))
    expected = [ROOT.name + '__' + suffix for suffix in SUFFIXES]
    if comparison['case_ids'] != expected or not set(expected) <= set(cases):
        raise ValueError('Selected exception D comparison identity changed')
    observations, all_rows = [], []
    for suffix, case_id in zip(SUFFIXES, expected):
        response = suffix.removeprefix('exception_d_')
        folder = ROOT / ('selected-exception-d-' + response)
        receipt_path = folder / 'compatibility.json'
        receipt = json.loads(receipt_path.read_text())
        entry = cases[case_id]
        if (receipt.get('passed') is not True or receipt.get('case_id') != case_id
                or receipt.get('construction_sha256') != entry['construction_sha256']
                or receipt.get('runtime_manifest_sha256') != manifest['runtime_manifest_sha256']):
            raise ValueError('Selected exception D package receipt changed')
        source = folder / 'source/exception_d_native_samples.jsonl'
        data = rows(source)
        if len(data) != 600:
            raise ValueError('Selected exception D source incomplete')
        reported = receipt['measurement_examples']['exception_d_observation']['value']
        active = sum(bool(row['duty_active']) for row in data)
        occupied = sum(row['bicycle_lane_body_occupied'] for row in data)
        joined = sum(bool(row['duty_active']) and row['bicycle_lane_body_occupied'] for row in data)
        if (active != reported['duty_active_frames'] or
                occupied != reported['bicycle_lane_occupied_frames'] or
                joined != reported['duty_occupied_frames']):
            raise ValueError('Exception F incident counts differ from source')
        observations.append({'case_id': case_id, 'source_sha256': sha(source),
                             'receipt_sha256': sha(receipt_path),
                             'duty_active_frames': active,
                             'bicycle_lane_occupied_frames': occupied,
                             'duty_occupied_frames': joined})
        all_rows.append(data)
    duty, routine = all_rows
    for first, second in zip(duty, routine):
        if first['native_frame'] != second['native_frame'] or first['time_s'] != second['time_s']:
            raise ValueError('Fixed exception D frame/time condition changed')
    first, second = observations
    if negative:
        first['duty_active_frames'] = 0
    if (first['duty_active_frames'] != 140 or first['duty_occupied_frames'] != 70
            or first['bicycle_lane_occupied_frames'] != 70
            or second['duty_active_frames'] != 0
            or second['duty_occupied_frames'] != 0
            or second['bicycle_lane_occupied_frames'] != 0):
        raise ValueError('Selected exception D comparison contrast absent')
    result = {'format': 'c10052-selected-exception-d-comparison-cpu-v1',
              'comparison_id': comparison['comparison_id'], 'cases': observations,
              'fixed_frame_time_verified': True,
              'deliberate_difference': 'synthetic assignment duty and associated ego lane occupancy',
              'source_bound_cpu_passed': True, 'diagnostic_only': True,
              'original_native_observed': False, 'legal_verdict_claimed': False}
    if not negative:
        (ROOT / 'selected-exception-d-pair-comparison.json').write_text(
            json.dumps(result, indent=2) + '\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--negative', action='store_true')
    args = parser.parse_args()
    print(json.dumps(check(args.negative), indent=2))
