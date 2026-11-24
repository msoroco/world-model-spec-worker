"""CPU diagnostic outcomes from source-bound saved case observations.

Run with SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work. The returned
fixtures are synthetic and never assert a physical or legal acceptance.
"""
import argparse
import json
import shutil
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', choices=('below', 'equal', 'above'), required=True)
    parser.add_argument('--kind', choices=('complete_motion', 'incomplete_motion', 'missing_evidence'), required=True)
    parser.add_argument('--scratch', type=Path, required=True)
    parser.add_argument('--result', type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, 'runtime')
    from scenario_pipeline.worker_exchange.native_output import physical_result

    source = args.scratch / f'compat-{args.case}-postbind'
    stage = args.scratch / f'physical-{args.case}-{args.kind}'
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir()
    for name in ('config.json', 'video_frames.jsonl'):
        shutil.copyfile(source / name, stage / name)
    (stage / 'acquisition-provenance.json').write_text(
        json.dumps({'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True}) + '\n')
    if args.kind == 'complete_motion':
        shutil.copyfile(source / 'trace.jsonl', stage / 'trace.jsonl')
    elif args.kind == 'incomplete_motion':
        rows = [json.loads(line) for line in (source / 'trace.jsonl').read_text().splitlines()]
        for row in rows:
            row['position_m'] = [0.0, 0.0, 0.0]
            row['position'] = {'x': 0.0, 'y': 0.0, 'z': 0.0}
            row['velocity_mps'] = [0.0, 0.0, 0.0]
            row['speed_mps'] = 0.0
            row['speed_mph'] = 0.0
        (stage / 'trace.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in rows))
    result = physical_result(stage, json.loads((source / 'result.json').read_text()))
    expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                'missing_evidence': 'unverified'}[args.kind]
    actual = result['physical_checks']['maneuver']['status']
    assert actual == expected, (actual, expected)
    assert result['provenance_kind'] == 'synthetic_fixture'
    assert result['diagnostic_fixture'] is True
    assert result['maneuver_completed'] == (expected == 'met')
    args.result.write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    print(json.dumps({'case': args.case, 'kind': args.kind, 'status': actual,
                      'diagnostic_fixture': True, 'physical_acceptance_claimed': False}))


if __name__ == '__main__':
    main()
