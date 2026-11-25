"""Compare selected exception C pair from source-bound synthetic measurements."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SUFFIXES = ('exception_c_avoid', 'exception_c_no_conflict')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def check(negative=False):
    manifest = json.loads((ROOT / 'execution-manifest.json').read_text())
    cases = {row['case_id']: row for row in manifest['cases']}
    plan = json.loads((ROOT / 'case-plan.json').read_text())
    comparison = next(row for row in plan['comparisons']
                      if row['comparison_id'].endswith('__comparison_exception_c'))
    expected = [ROOT.name + '__' + suffix for suffix in SUFFIXES]
    if comparison['case_ids'] != expected or not set(expected) <= set(cases):
        raise ValueError('Selected exception C comparison identity changed')
    observations, all_rows = [], []
    for suffix, case_id in zip(SUFFIXES, expected):
        response = suffix.removeprefix('exception_c_')
        folder = ROOT / ('selected-exception-c-' + response)
        receipt_path = folder / 'compatibility.json'
        receipt = json.loads(receipt_path.read_text())
        entry = cases[case_id]
        if (receipt.get('passed') is not True or receipt.get('case_id') != case_id
                or receipt.get('construction_sha256') != entry['construction_sha256']
                or receipt.get('runtime_manifest_sha256') != manifest['runtime_manifest_sha256']):
            raise ValueError('Selected exception C package receipt changed')
        source = folder / 'source/exception_c_native_samples.jsonl'
        data = rows(source)
        if len(data) != 600:
            raise ValueError('Selected exception C source incomplete')
        reported = receipt['measurement_examples']['exception_c_observation']['value']
        active = sum(bool(row['conflict_actor_active']) for row in data)
        if active != reported['active_conflict_actor_frames']:
            raise ValueError('Exception C actor count differs from source')
        observations.append({'case_id': case_id, 'source_sha256': sha(source),
                             'receipt_sha256': sha(receipt_path),
                             'active_conflict_actor_frames': active,
                             'bicycle_lane_occupied_frames': reported['bicycle_lane_occupied_frames'],
                             'actual_collision_frames': reported['actual_collision_frames'],
                             'counterfactual_straight_collision_frames':
                                 reported['counterfactual_straight_collision_frames']})
        all_rows.append(data)
    avoid, clear = all_rows
    for first, second in zip(avoid, clear):
        if first['native_frame'] != second['native_frame'] or first['time_s'] != second['time_s']:
            raise ValueError('Fixed exception C frame/time condition changed')
    first, second = observations
    if negative:
        first['active_conflict_actor_frames'] = 0
    if (first['active_conflict_actor_frames'] != 71
            or first['counterfactual_straight_collision_frames'] <= 0
            or first['actual_collision_frames'] != 0
            or first['bicycle_lane_occupied_frames'] <= 0
            or second['active_conflict_actor_frames'] != 0
            or second['bicycle_lane_occupied_frames'] != 0):
        raise ValueError('Selected exception C comparison contrast absent')
    result = {'format': 'c10052-selected-exception-c-comparison-cpu-v1',
              'comparison_id': comparison['comparison_id'], 'cases': observations,
              'fixed_frame_time_verified': True,
              'deliberate_difference': 'synthetic other-traffic conflict and avoidance diversion',
              'source_bound_cpu_passed': True, 'diagnostic_only': True,
              'original_native_observed': False, 'legal_verdict_claimed': False}
    if not negative:
        (ROOT / 'selected-exception-c-pair-comparison.json').write_text(
            json.dumps(result, indent=2) + '\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--negative', action='store_true')
    args = parser.parse_args()
    print(json.dumps(check(args.negative), indent=2))
