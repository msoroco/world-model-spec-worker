"""Test three source-bound motion outcomes without claiming physical acceptance."""

import argparse
import json
from pathlib import Path
import shutil
import sys


KINDS = ('complete_motion', 'incomplete_motion', 'missing_evidence')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--kind', choices=KINDS, required=True)
    parser.add_argument('--scratch', type=Path, required=True)
    parser.add_argument('--result', type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    repo = root.parents[1]
    scratch = args.scratch.resolve()
    result_path = args.result.resolve()
    if repo / '.runtime-work' not in scratch.parents:
        raise ValueError('Physical fixture scratch belongs under .runtime-work')
    if root not in result_path.parents:
        raise ValueError('Physical proof result belongs under this assignment')
    suffix = args.case.removeprefix(root.name + '__')
    if args.case != root.name + '__' + suffix:
        raise ValueError('Foreign exact case')
    construction = json.loads((root / 'cases' / suffix / 'construction.json').read_text())
    if construction['case_id'] != args.case:
        raise ValueError('Construction identity differs')
    config = json.loads(next(item['content'] for item in construction['files']
                             if item['path'] == 'config.json'))
    sys.path.insert(0, str(repo / 'runtime/scenario_pipeline'))
    from worker_exchange.native_output import physical_result

    stage = scratch / (suffix + '-' + args.kind)
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)
    (stage / 'config.json').write_text(json.dumps(config) + '\n')
    (stage / 'acquisition-provenance.json').write_text(json.dumps({
        'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True}) + '\n')
    mapping = [{'video_frame': i, 'carla_frame': 38033 + i,
                'time_s': round((i + 1) / 20, 10)} for i in range(900)]
    (stage / 'video_frames.jsonl').write_text(''.join(json.dumps(row) + '\n'
                                                     for row in mapping))
    if args.kind != 'missing_evidence':
        distance = 120 if args.kind == 'complete_motion' else 0
        trace = [{'frame': frame['carla_frame'], 'time_s': frame['time_s'],
                  'position_m': [distance * i / 899, 0.0, 0.0]}
                 for i, frame in enumerate(mapping)]
        (stage / 'trace.jsonl').write_text(''.join(json.dumps(row) + '\n'
                                                for row in trace))
    result = physical_result(stage, {'target_checks': []})
    expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                'missing_evidence': 'unverified'}[args.kind]
    observed = result['physical_checks']['maneuver']['status']
    if observed != expected or result['maneuver_completed'] != (expected == 'met'):
        raise ValueError('Diagnostic motion outcome differs: ' + observed)
    if result['provenance_kind'] != 'synthetic_fixture' or result['diagnostic_fixture'] is not True:
        raise ValueError('Diagnostic provenance lost')
    result_path.write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    print(json.dumps({'case_id': args.case, 'kind': args.kind,
                      'status': observed, 'physical_acceptance_claimed': False}))


if __name__ == '__main__':
    main()
