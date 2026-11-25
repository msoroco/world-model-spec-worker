"""Compare selected pedestrian cases from retained synthetic source bodies."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BOUNDS = (-2.5, -5.0, 2.5, -3.0)
SUFFIXES = ('pedestrian_clear', 'pedestrian_conflict')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def area(body):
    xs = [point[0] for point in body]
    ys = [point[1] for point in body]
    return max(0, min(max(xs), BOUNDS[2]) - max(min(xs), BOUNDS[0])) * max(
        0, min(max(ys), BOUNDS[3]) - max(min(ys), BOUNDS[1]))


def measure(source):
    pedestrian = [i for i, row in enumerate(source) if area(row['pedestrian_body_xy']) > .01]
    ego = [i for i, row in enumerate(source) if area(row['ego_body_xy']) > .01]
    if not pedestrian or not ego:
        raise ValueError('Pedestrian or ego conflict interval missing')
    return {'first_pedestrian_conflict_frame': pedestrian[0],
            'last_pedestrian_conflict_frame': pedestrian[-1],
            'first_ego_conflict_frame': ego[0],
            'simultaneous_conflict_frames': len(set(pedestrian) & set(ego))}


def check(negative=False):
    manifest = json.loads((ROOT / 'execution-manifest.json').read_text())
    cases = {row['case_id']: row for row in manifest['cases']}
    plan = json.loads((ROOT / 'case-plan.json').read_text())
    comparison = next(row for row in plan['comparisons']
                      if row['comparison_id'].endswith('__comparison_pedestrian_yield'))
    expected = [ROOT.name + '__' + suffix for suffix in SUFFIXES]
    if comparison['case_ids'] != expected or not set(expected) <= set(cases):
        raise ValueError('Selected pedestrian comparison identity changed')
    all_rows = []
    observations = []
    for suffix, case_id in zip(SUFFIXES, expected):
        folder = ROOT / ('selected-pedestrian-clear' if suffix.endswith('clear')
                         else 'selected-pedestrian-conflict')
        receipt_path = folder / 'compatibility.json'
        receipt = json.loads(receipt_path.read_text())
        entry = cases[case_id]
        if (receipt.get('passed') is not True or receipt.get('case_id') != case_id
                or receipt.get('construction_sha256') != entry['construction_sha256']
                or receipt.get('runtime_manifest_sha256') != manifest['runtime_manifest_sha256']):
            raise ValueError('Selected pedestrian package receipt changed')
        source = folder / 'source/pedestrian_native_samples.jsonl'
        data = rows(source)
        if len(data) != 600:
            raise ValueError('Selected pedestrian source incomplete')
        measured = measure(data)
        reported = receipt['measurement_examples']['pedestrian_conflict_observation']['value']
        for key in measured:
            if measured[key] != reported[key]:
                raise ValueError('Pedestrian timing differs from source: ' + key)
        observations.append({'case_id': case_id, 'source_sha256': sha(source),
                             'receipt_sha256': sha(receipt_path), **measured})
        all_rows.append(data)
    clear, conflict = all_rows
    for first, second in zip(clear, conflict):
        for key in ('native_frame', 'time_s', 'pedestrian_xy', 'pedestrian_body_xy',
                    'sidewalk_obstruction_body_xy', 'buffer_obstruction_body_xy'):
            if first[key] != second[key]:
                raise ValueError('Fixed pedestrian comparison condition changed: ' + key)
    if negative:
        observations[1]['simultaneous_conflict_frames'] = 0
    if (observations[0]['simultaneous_conflict_frames'] != 0
            or observations[1]['simultaneous_conflict_frames'] != 20
            or observations[0]['first_ego_conflict_frame'] <= observations[0]['last_pedestrian_conflict_frame']
            or observations[1]['first_ego_conflict_frame'] != observations[1]['first_pedestrian_conflict_frame']):
        raise ValueError('Selected pedestrian comparison contrast absent')
    result = {'format': 'c10052-selected-pedestrian-comparison-cpu-v1',
              'comparison_id': comparison['comparison_id'], 'cases': observations,
              'fixed_pedestrian_source_verified': True,
              'deliberate_difference': 'ego conflict entry shifted 75 source frames',
              'source_bound_cpu_passed': True, 'diagnostic_only': True,
              'original_native_observed': False, 'legal_verdict_claimed': False}
    (ROOT / 'selected-pedestrian-pair-comparison.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--negative', action='store_true')
    args = parser.parse_args()
    print(json.dumps(check(args.negative), indent=2))
