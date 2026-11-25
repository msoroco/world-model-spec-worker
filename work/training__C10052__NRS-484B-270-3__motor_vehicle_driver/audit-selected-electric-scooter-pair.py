"""Independent source-bound comparison of the selected electric-scooter timing pair."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SUFFIXES = ('rider_electric_scooter_clear', 'rider_electric_scooter_conflict')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def intersects(body, bounds):
    xs = [point[0] for point in body]
    ys = [point[1] for point in body]
    return (min(xs) < bounds[2] and max(xs) > bounds[0]
            and min(ys) < bounds[3] and max(ys) > bounds[1])


def measure(rows_, bounds):
    rider = [row['native_frame'] for row in rows_
             if intersects(row['rider_body_xy'], bounds)]
    ego = [row['native_frame'] for row in rows_
           if intersects(row['ego_body_xy'], bounds)]
    if not rider or not ego:
        raise ValueError('Rider or ego conflict interval missing')
    return {'simultaneous_conflict_frames': len(set(rider) & set(ego)),
            'clearance_s': (min(ego) - max(rider)) / 20,
            'first_ego_frame': min(ego), 'last_rider_frame': max(rider)}


def check(negative=False):
    manifest = json.loads((ROOT / 'execution-manifest.json').read_text())
    cases = {row['case_id']: row for row in manifest['cases']}
    plan = json.loads((ROOT / 'case-plan.json').read_text())
    comparison = next(c for c in plan['comparisons']
                      if c['comparison_id'].endswith('__comparison_rider_electric_scooter'))
    expected = [ROOT.name + '__' + suffix for suffix in SUFFIXES]
    if comparison['case_ids'] != expected or not set(expected) <= set(cases):
        raise ValueError('Selected rider comparison identity changed')
    observations = []
    source_rows = []
    for suffix, case_id in zip(SUFFIXES, expected):
        folder = ROOT / ('selected-rider-electric-scooter-clear' if suffix.endswith('clear')
                         else 'selected-rider-electric-scooter-conflict')
        receipt_path = folder / 'compatibility.json'
        receipt = json.loads(receipt_path.read_text())
        entry = cases[case_id]
        if (receipt.get('passed') is not True or receipt.get('case_id') != case_id
                or receipt.get('construction_sha256') != entry['construction_sha256']
                or receipt.get('runtime_manifest_sha256') != manifest['runtime_manifest_sha256']):
            raise ValueError('Selected rider package receipt changed')
        source = folder / 'source/rider_native_samples.jsonl'
        geometry = folder / 'source/rider_geometry.json'
        if not source.is_file() or len(rows(source)) != 600:
            raise ValueError('Selected rider source incomplete')
        data = rows(source)
        if any(row.get('rider_type') != 'electric_scooter' for row in data):
            raise ValueError('Rider type changed')
        bounds = json.loads(geometry.read_text())['conflict_native_xy_bounds_m']
        measured = measure(data, bounds)
        reported = receipt['measurement_examples']['rider_conflict_observation']['value']
        for key in measured:
            if measured[key] != reported[key]:
                raise ValueError('Rider timing differs from source: ' + key)
        observations.append({'case_id': case_id, 'source_sha256': sha(source),
                             'receipt_sha256': sha(receipt_path), **measured})
        source_rows.append(data)
    clear, conflict = source_rows
    for first, second in zip(clear, conflict):
        for key in ('native_frame', 'time_s', 'ego_body_xy', 'ego_speed_mps',
                    'ego_native_road_id', 'rider_actor_id', 'rider_type'):
            if first[key] != second[key]:
                raise ValueError('Fixed comparison condition changed: ' + key)
    if negative:
        observations[1]['simultaneous_conflict_frames'] = 0
    if (observations[0]['simultaneous_conflict_frames'] != 0
            or observations[0]['clearance_s'] <= 0
            or observations[1]['simultaneous_conflict_frames'] <= 0
            or observations[1]['clearance_s'] >= 0):
        raise ValueError('Selected rider comparison contrast absent')
    result = {'format': 'c10052-selected-rider-comparison-cpu-v1',
              'comparison_id': comparison['comparison_id'],
              'cases': observations, 'fixed_ego_source_verified': True,
              'deliberate_difference': 'rider conflict arrival shifted 65 source frames',
              'source_bound_cpu_passed': True, 'diagnostic_only': True,
              'original_native_observed': False, 'legal_verdict_claimed': False}
    (ROOT / 'selected-electric-scooter-pair-comparison.json').write_text(
        json.dumps(result, indent=2) + '\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--negative', action='store_true')
    args = parser.parse_args()
    print(json.dumps(check(args.negative), indent=2))
