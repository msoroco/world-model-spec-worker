"""Exercise source-shaped right-pass completion outcomes on CPU fixtures.

These synthetic rows prove the physical assessment path only. Neither the
reviewed highway/pavement context nor an actual CARLA run is asserted.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path


def vertices(x, y):
    return [[x + dx, y + dy, 0.0]
            for dx in (-2.0, 2.0) for dy in (-0.9, 0.9)]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--kind', choices=('complete_motion', 'incomplete_motion', 'missing_evidence'),
                        required=True)
    parser.add_argument('--scratch', type=Path, required=True)
    parser.add_argument('--result', type=Path, required=True)
    args = parser.parse_args()
    base = Path(__file__).resolve().parent
    repo = base.parents[1]
    if repo / '.runtime-work' not in args.scratch.resolve().parents:
        raise ValueError('physical fixture scratch must stay under .runtime-work')
    if base not in args.result.resolve().parents:
        raise ValueError('physical fixture result must stay under owned assignment')
    suffix = args.case.removeprefix(base.name + '__')
    if args.case != base.name + '__' + suffix:
        raise ValueError('foreign exact case')
    construction = json.loads((base / ('construction-' + suffix + '.json')).read_text())
    config = json.loads(next(f['content'] for f in construction['files'] if f['path'] == 'config.json'))
    stage = args.scratch / (suffix + '-' + args.kind)
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)
    (stage / 'config.json').write_text(json.dumps(config) + '\n')
    (stage / 'acquisition-provenance.json').write_text(json.dumps({
        'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True}) + '\n')
    mapping = [{'video_frame': i, 'carla_frame': i + 100,
                'time_s': i / 20} for i in range(900)]
    (stage / 'video_frames.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in mapping))
    rows = []
    for index, row in enumerate(mapping):
        fraction = index / 899
        ego_s = 50 + (35 * fraction if args.kind == 'complete_motion' else 0)
        target_s = 55 + 10 * fraction
        rows.append({'frame': row['carla_frame'], 'time_s': row['time_s'],
                     'ego_vertices_m': vertices(ego_s, 7),
                     'target_vertices_m': vertices(target_s, 10)})
    (stage / 'trace.jsonl').write_text(''.join(json.dumps({
        'frame': row['carla_frame'], 'time_s': row['time_s'],
        'position_m': [50 + 35 * i / 899, 7, 0]}) + '\n'
        for i, row in enumerate(mapping)))
    if args.kind != 'missing_evidence':
        (stage / 'pass_history.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in rows))
    sys.path.insert(0, str(repo / 'runtime/scenario_pipeline'))
    from worker_exchange.native_output import physical_result
    result = physical_result(stage, {'target_checks': []})
    expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                'missing_evidence': 'unverified'}[args.kind]
    actual = result['physical_checks']['maneuver']['status']
    if actual != expected or result['maneuver_completed'] != (expected == 'met'):
        raise ValueError('source-shaped diagnostic maneuver assessment differs: ' + actual)
    if result['provenance_kind'] != 'synthetic_fixture' or result['diagnostic_fixture'] is not True:
        raise ValueError('diagnostic provenance lost')
    args.result.write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    print(json.dumps({'case_id': args.case, 'kind': args.kind,
                      'status': actual, 'physical_acceptance_claimed': False}))


if __name__ == '__main__':
    main()
