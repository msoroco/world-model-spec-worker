"""Source joined CPU motion outcomes; diagnostic fixtures have no legal force."""
import argparse
import json
import shutil
import sys
from pathlib import Path


CASES = ('all_prerequisites', 'not_designated', 'not_dedicated',
         'no_prohibition_sign', 'emergency_vehicle', 'maintenance_vehicle')
KINDS = ('complete_motion', 'incomplete_motion', 'missing_evidence')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', choices=CASES, required=True)
    parser.add_argument('--kind', choices=KINDS, required=True)
    parser.add_argument('--scratch', type=Path, required=True)
    parser.add_argument('--result', type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, 'runtime')
    from scenario_pipeline.worker_exchange.native_output import physical_result

    package = Path(__file__).resolve().parent
    spec = json.loads((package / ('diagnostic-' + args.case + '.json')).read_text())
    stage = args.scratch / ('physical-' + args.case + '-' + args.kind)
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)
    shutil.copyfile(package / 'cases' / args.case / 'config.json', stage / 'config.json')
    (stage / 'video_frames.jsonl').write_text(spec['files']['video_frames.jsonl'])
    (stage / 'acquisition-provenance.json').write_text(json.dumps({
        'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True}) + '\n')
    if args.kind != 'missing_evidence':
        rows = [json.loads(line) for line in spec['files']['trace.jsonl'].splitlines()]
        if args.kind == 'complete_motion':
            for index, row in enumerate(rows):
                x = -2.0 + 130.0 * index / (len(rows) - 1)
                row['position_m'] = [x, 2.0, 0.0]
                row['position'] = {'x': x, 'y': 2.0, 'z': 0.0}
        else:
            for row in rows:
                row['position_m'] = [-2.0, 2.0, 0.0]
                row['position'] = {'x': -2.0, 'y': 2.0, 'z': 0.0}
                row['velocity_mps'] = [0.0, 0.0, 0.0]
                row['speed_mps'] = row['speed_mph'] = 0.0
        (stage / 'trace.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in rows))
    base = {'target_checks': [{'target': 'diagnostic motion', 'requested': True,
                              'measured': False, 'method': 'original trace',
                              'tolerance': 0, 'matched': False,
                              'physical_cause_confirmed': False,
                              'cause_evidence': 'CPU diagnostic only'}]}
    result = physical_result(stage, base)
    expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                'missing_evidence': 'unverified'}[args.kind]
    actual = result['physical_checks']['maneuver']['status']
    assert actual == expected, (actual, expected)
    assert result['maneuver_completed'] == (expected == 'met')
    assert result['provenance_kind'] == 'synthetic_fixture'
    assert result['diagnostic_fixture'] is True
    assert not result['physical_acceptance_claimed']
    args.result.write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    print(json.dumps({'case': args.case, 'kind': args.kind, 'status': actual,
                      'diagnostic_fixture': True, 'physical_acceptance_claimed': False}))


if __name__ == '__main__':
    main()
