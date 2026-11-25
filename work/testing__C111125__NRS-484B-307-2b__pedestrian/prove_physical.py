"""Exercise the pinned motion classifier on source-bound synthetic trajectories."""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--kind', choices=('complete_motion', 'incomplete_motion', 'missing_evidence'), required=True)
    parser.add_argument('--scratch', type=Path, required=True)
    parser.add_argument('--result', type=Path, required=True)
    args = parser.parse_args()
    repo = ROOT.parents[1]
    if repo / '.runtime-work' not in args.scratch.resolve().parents:
        raise ValueError('scratch must be under .runtime-work')
    if ROOT not in args.result.resolve().parents:
        raise ValueError('result must be under this assignment')
    suffix = args.case.removeprefix(ROOT.name + '__')
    if ROOT.name + '__' + suffix != args.case or not (ROOT / 'cases' / suffix).is_dir():
        raise ValueError('foreign exact case')
    construction = json.loads((ROOT / 'cases' / suffix / 'delivery-construction.draft.json').read_text())
    config = json.loads(next(item['content'] for item in construction['files'] if item['path'] == 'config.json'))
    stage = args.scratch / (suffix + '-' + args.kind)
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)
    (stage / 'config.json').write_text(json.dumps(config) + '\n')
    (stage / 'acquisition-provenance.json').write_text(json.dumps({
        'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True}) + '\n')
    mapping = [{'video_frame': i, 'carla_frame': i, 'time_s': i / 20} for i in range(900)]
    (stage / 'video_frames.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in mapping))
    if args.kind != 'missing_evidence':
        distance = 120 if args.kind == 'complete_motion' else 0
        rows = [{'frame': i, 'time_s': i / 20,
                 'position_m': [-10 + distance * i / 899, 5, 0]}
                for i in range(900)]
        (stage / 'trace.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in rows))
    sys.path.insert(0, str(repo / 'runtime/scenario_pipeline'))
    from worker_exchange.native_output import physical_result
    result = physical_result(stage, {'target_checks': []})
    expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                'missing_evidence': 'unverified'}[args.kind]
    actual = result['physical_checks']['maneuver']['status']
    if actual != expected or result['maneuver_completed'] != (expected == 'met'):
        raise ValueError('diagnostic physical outcome differs: ' + actual)
    if result['provenance_kind'] != 'synthetic_fixture' or result['diagnostic_fixture'] is not True:
        raise ValueError('synthetic provenance lost')
    args.result.write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    print(json.dumps({'case_id': args.case, 'kind': args.kind, 'status': actual,
                      'physical_acceptance_claimed': False}))


if __name__ == '__main__':
    main()
