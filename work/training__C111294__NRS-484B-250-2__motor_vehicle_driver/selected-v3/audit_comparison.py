"""Independent body-based comparison of selected CPU diagnostic sources."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ASSIGNMENT = ROOT.parent
EXPECTED_ASSIGNMENT_SHA = 'd005cde0eec41f63fcc0dc8aedb3a3d81c39daa3ed8b2d193fca4161769dd738'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def entry_time(rows, actor):
    for row in rows:
        body = row[actor]['body_xyz_m']
        front = max(vertex[0 if actor == 'ego' else 1] for vertex in body)
        if front >= -20:
            return row['time_s']
    raise ValueError(actor + ' never entered the measured boundary')


def audit(probe_other_history=None):
    frozen = ASSIGNMENT.parents[1] / 'inputs' / ASSIGNMENT.name / 'assignment.json'
    if sha(frozen) != EXPECTED_ASSIGNMENT_SHA:
        raise ValueError('Frozen assignment source changed')
    result = {'format': 'c111294-2502-selected-synthetic-comparison-v1',
              'assignment_id': ASSIGNMENT.name, 'assignment_sha256': sha(frozen),
              'candidate_pairs': {}, 'synthetic_cpu_diagnostic': True,
              'original_native_observed': False, 'legal_verdict': None}
    for candidate in ('primary', 'fallback1', 'fallback2'):
        paths = [ROOT / suffix / candidate for suffix in ('controlled_1', 'controlled_2')]
        histories = []
        for index, path in enumerate(paths):
            source = path / 'sources/actor-history.json'
            recipe = read(path / 'fixture-recipe.json')
            binding = next(item for item in recipe['sources'] if item['path'] == 'actor-history.json')
            if sha(source) != binding['sha256']:
                raise ValueError('Selected actor source hash changed')
            chosen = Path(probe_other_history) if index == 1 and probe_other_history else source
            history = read(chosen)
            if history.get('synthetic') is not True or len(history['rows']) != 600:
                raise ValueError('Expected 600 synthetic source rows')
            rows = history['rows']
            if any(row['frame'] != i or row['time_s'] != i / 20 for i, row in enumerate(rows)):
                raise ValueError('Frame/time source join changed')
            histories.append((rows, sha(source)))
        left, right = histories[0][0], histories[1][0]
        if [r['other'] for r in left] != [r['other'] for r in right]:
            raise ValueError('Other participant changed across controlled pair')
        if [r['ego'] for r in left] == [r['ego'] for r in right]:
            raise ValueError('Ego timing contrast absent')
        roads = [sha(p / 'sources/road.xodr') for p in paths]
        if roads[0] != roads[1]:
            raise ValueError('Controlled pair road differs')
        entry = [entry_time(rows, 'ego') for rows in (left, right)]
        other_entry = entry_time(left, 'other')
        result['candidate_pairs'][candidate] = {
            'source_sha256': [histories[0][1], histories[1][1]],
            'road_sha256': roads[0], 'frames': 600,
            'other_actor_body_fixed': True,
            'ego_entry_time_s': entry, 'other_entry_time_s': other_entry,
            'ego_minus_other_entry_s': [round(v-other_entry, 6) for v in entry]}
        gap = result['candidate_pairs'][candidate]['ego_minus_other_entry_s']
        if not (0 <= gap[1] <= 0.75 and 0.75 <= gap[0] <= 1.75 and gap[0] > gap[1]):
            raise ValueError('Controlled entry contrast left the measured near-simultaneous window')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--probe-other-history')
    parser.add_argument('--output')
    args = parser.parse_args()
    report = audit(args.probe_other_history)
    if args.output:
        Path(args.output).write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'candidate_pairs': len(report['candidate_pairs']),
                      'synthetic_cpu_diagnostic': True}))
