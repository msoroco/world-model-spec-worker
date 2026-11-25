"""Compare selected exception B pair from source-bound synthetic measurements."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SUFFIXES = ('exception_b_faulted', 'exception_b_healthy')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def check(negative=False):
    manifest = json.loads((ROOT / 'execution-manifest.json').read_text())
    cases = {row['case_id']: row for row in manifest['cases']}
    plan = json.loads((ROOT / 'case-plan.json').read_text())
    comparison = next(row for row in plan['comparisons']
                      if row['comparison_id'].endswith('__comparison_exception_b'))
    expected = [ROOT.name + '__' + suffix for suffix in SUFFIXES]
    if comparison['case_ids'] != expected or not set(expected) <= set(cases):
        raise ValueError('Selected exception B comparison identity changed')
    observations, all_rows = [], []
    for suffix, case_id in zip(SUFFIXES, expected):
        response = suffix.removeprefix('exception_b_')
        folder = ROOT / ('selected-exception-b-' + response)
        receipt_path = folder / 'compatibility.json'
        receipt = json.loads(receipt_path.read_text())
        entry = cases[case_id]
        if (receipt.get('passed') is not True or receipt.get('case_id') != case_id
                or receipt.get('construction_sha256') != entry['construction_sha256']
                or receipt.get('runtime_manifest_sha256') != manifest['runtime_manifest_sha256']):
            raise ValueError('Selected exception B package receipt changed')
        source = folder / 'source/exception_b_native_samples.jsonl'
        data = rows(source)
        if len(data) != 600:
            raise ValueError('Selected exception B source incomplete')
        reported = receipt['measurement_examples']['exception_b_observation']['value']
        fault = sum(bool(row['fault_injection_applied']) for row in data)
        if fault != reported['fault_readback_frames']:
            raise ValueError('Exception B fault count differs from source')
        observations.append({'case_id': case_id, 'source_sha256': sha(source),
                             'receipt_sha256': sha(receipt_path),
                             'fault_readback_frames': fault,
                             'bicycle_lane_occupied_frames_100_240': reported['bicycle_lane_occupied_frames_100_240'],
                             'propulsion_test_displacement_m': reported['propulsion_test_displacement_m']})
        all_rows.append(data)
    faulted, healthy = all_rows
    for first, second in zip(faulted, healthy):
        if (first['native_frame'] != second['native_frame'] or first['time_s'] != second['time_s']
                or first['throttle_command'] != second['throttle_command']
                or first['brake_command'] != second['brake_command']):
            raise ValueError('Fixed exception B frame/time condition changed')
    first, second = observations
    if negative:
        first['fault_readback_frames'] = 0
    if (first['fault_readback_frames'] != 280
            or first['propulsion_test_displacement_m'] != 0
            or first['bicycle_lane_occupied_frames_100_240'] <= 0
            or second['fault_readback_frames'] != 0
            or second['propulsion_test_displacement_m'] <= 5
            or second['bicycle_lane_occupied_frames_100_240'] <= 0):
        raise ValueError('Selected exception B comparison contrast absent')
    result = {'format': 'c10052-selected-exception-b-comparison-cpu-v1',
              'comparison_id': comparison['comparison_id'], 'cases': observations,
              'fixed_frame_time_verified': True,
              'deliberate_difference': 'synthetic powertrain fault and propulsion response',
              'source_bound_cpu_passed': True, 'diagnostic_only': True,
              'original_native_observed': False, 'legal_verdict_claimed': False}
    if not negative:
        (ROOT / 'selected-exception-b-pair-comparison.json').write_text(
            json.dumps(result, indent=2) + '\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--negative', action='store_true')
    args = parser.parse_args()
    print(json.dumps(check(args.negative), indent=2))
