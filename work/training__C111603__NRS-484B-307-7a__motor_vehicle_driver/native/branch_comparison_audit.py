"""Independently audit one-intervention statutory branch source pairs."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAIRS = {
    'pedestrian_yield': ('pedestrian_clearance', 'pedestrian_overlap'),
    'concurrent_indication': ('concurrent_absent', 'concurrent_present'),
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def audit_pair(first, second, branch):
    if len(first) != 600 or len(second) != 600:
        raise ValueError('Comparison source frame inventory differs')
    if branch not in PAIRS:
        raise ValueError('Unknown statutory comparison')
    fixed = ('requested_arrow', 'requested_other_xy_m',
             'requested_pedestrian_xy_m', 'requested_movement')
    intervention = ('requested_ego_release_frame' if branch == 'pedestrian_yield'
                    else 'requested_concurrent_left_indication')
    for index, (a, b) in enumerate(zip(first, second)):
        if (a.get('frame') != index or b.get('frame') != index
                or a.get('time_s') != index / 20 or b.get('time_s') != index / 20):
            raise ValueError('Comparison source time join differs')
        for key in fixed:
            if a.get(key) != b.get(key):
                raise ValueError('Fixed comparison source differs: ' + key)
        if branch == 'pedestrian_yield':
            if a['requested_concurrent_left_indication'] != b['requested_concurrent_left_indication']:
                raise ValueError('Uncontrolled concurrent signal difference')
        else:
            if a['requested_ego_xy_m'] != b['requested_ego_xy_m']:
                raise ValueError('Uncontrolled ego turn path difference')
            if a['requested_ego_release_frame'] != b['requested_ego_release_frame']:
                raise ValueError('Uncontrolled ego release difference')
        for row in (a, b):
            if (row.get('original_native_observed') is not False
                    or row.get('pedestrian_lawful_status') is not None
                    or row.get('other_traffic_lawful_status') is not None
                    or row.get('cautiousness_legal_judgment') is not None):
                raise ValueError('Comparison source asserts physical or legal result')
    if first[0][intervention] == second[0][intervention]:
        raise ValueError('Declared comparison intervention did not vary')
    if branch == 'pedestrian_yield':
        if any(a['requested_movement'] != 'right' or b['requested_movement'] != 'right'
               for a, b in zip(first, second)):
            raise ValueError('Pedestrian pair leaves selected turn movement')
    else:
        if any(a['requested_movement'] != 'left' or b['requested_movement'] != 'left'
               for a, b in zip(first, second)):
            raise ValueError('Concurrent pair leaves frozen turn maneuver')
    return {'branch': branch, 'frames': 600,
            'intervention': intervention,
            'first': first[0][intervention], 'second': second[0][intervention],
            'legal_verdict_claimed': False}


def audit():
    results = []
    for branch, (left, right) in PAIRS.items():
        paths = [ROOT / ('selected-source-' + name) / 'turn-history.jsonl'
                 for name in (left, right)]
        for path in paths:
            if not path.is_file():
                raise ValueError('Missing comparison source: ' + str(path))
        first, second = map(rows, paths)
        result = audit_pair(first, second, branch)
        result['source_sha256'] = {name: sha(path) for name, path in zip((left, right), paths)}
        results.append(result)
    return {'format': 'worker-branch-comparison-audit', 'passed': True,
            'source_kind': 'synthetic_cpu_diagnostic',
            'original_native_observed': False, 'comparisons': results}


def proof():
    result = audit()
    for branch, names in PAIRS.items():
        left = rows(ROOT / ('selected-source-' + names[0]) / 'turn-history.jsonl')
        right = rows(ROOT / ('selected-source-' + names[1]) / 'turn-history.jsonl')
        changed = [dict(row) for row in right]
        changed[220] = dict(changed[220], requested_other_xy_m=[0, 0])
        try:
            audit_pair(left, changed, branch)
        except ValueError as error:
            if 'Fixed comparison source differs' not in str(error):
                raise
        else:
            raise ValueError('Fixed-source negative passed')
    result['negative_fixed_source_rejections'] = len(PAIRS)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = proof()
    if args.output:
        args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'passed': True, 'comparisons': len(result['comparisons']),
                      'negative_fixed_source_rejections': result['negative_fixed_source_rejections']}))
