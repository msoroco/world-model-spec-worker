"""Synthetic source-bound crossing completion triad; no physical acceptance."""
import argparse
import json
import shutil
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--kind', choices=('complete_motion', 'incomplete_motion', 'missing_evidence'), required=True)
    parser.add_argument('--scratch', type=Path, required=True)
    parser.add_argument('--result', type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, 'runtime')
    from scenario_pipeline.worker_exchange.native_output import physical_result

    source = args.scratch / ('source-' + args.case)
    stage = args.scratch / ('physical-' + args.case + '-' + args.kind)
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)
    for name in ('config.json', 'trace.jsonl', 'video_frames.jsonl'):
        shutil.copyfile(source / name, stage / name)
    (stage / 'acquisition-provenance.json').write_text(json.dumps({
        'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True}) + '\n')
    if args.kind != 'missing_evidence':
        rows = [json.loads(line) for line in (source / 'ego-body-history.jsonl').read_text().splitlines()]
        if args.kind == 'complete_motion' and args.case == 'yield_wait_for_other_clear':
            # The wait diagnostic stops at release. Extend only this synthetic
            # software fixture to exercise the completion predicate.
            rows[-1]['body_vertices_xy_m'] = [
                [point[0] + 10.0, point[1]] for point in rows[-1]['body_vertices_xy_m']]
        if args.kind == 'incomplete_motion':
            initial = rows[0]['body_vertices_xy_m']
            for row in rows:
                row['body_vertices_xy_m'] = initial
        (stage / 'crossing_history.jsonl').write_text(''.join(json.dumps({
            'frame': row['frame'], 'time_s': row['time_s'],
            'ego_vertices_m': row['body_vertices_xy_m']}) + '\n' for row in rows))
    saved = args.scratch / ('saved-' + args.case) / 'v0001' / 'analysis' / 'result.json'
    result = physical_result(stage, json.loads(saved.read_text()))
    expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                'missing_evidence': 'unverified'}[args.kind]
    actual = result['physical_checks']['maneuver']['status']
    assert actual == expected, (actual, expected, result['physical_checks']['maneuver'])
    assert result['provenance_kind'] == 'synthetic_fixture'
    assert result['diagnostic_fixture'] is True
    assert result['maneuver_completed'] == (expected == 'met')
    args.result.write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    print(json.dumps({'case': args.case, 'kind': args.kind, 'status': actual,
                      'diagnostic_fixture': True, 'physical_acceptance_claimed': False}))


if __name__ == '__main__':
    main()
