"""Prove C80909 opening physical status on three synthetic CPU sources."""

import argparse
import json
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
DEFAULT_SUFFIX = 'left_through_opening'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--kind', choices=('complete_motion', 'incomplete_motion',
                                           'missing_evidence'), required=True)
    parser.add_argument('--suffix', default=DEFAULT_SUFFIX)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    suffix = args.suffix
    if suffix not in ('left_through_opening', 'left_across_blocked_divider',
                      'left_at_established_crossover', 'left_right_roadway_continuation'):
        raise ValueError('Unknown exact C80909 physical fixture')
    case = ROOT.name + '__' + suffix
    runtime_root = Path(os.environ.get('SCENARIO_PIPELINE_OUTPUT_ROOT', '')).resolve()
    if runtime_root != REPO / '.runtime-work/c80909-physical-fixtures':
        raise ValueError('Set SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work before runtime imports')
    sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))
    from worker_exchange.native_output import physical_result

    stem = 'opening' if suffix == DEFAULT_SUFFIX else suffix
    spec = json.loads((ROOT / 'cases' / suffix / (stem + '-diagnostic-sources.json')).read_text())
    construction_path = ROOT / 'construction.json' if suffix == DEFAULT_SUFFIX else ROOT / 'cases' / suffix / 'construction.json'
    construction = json.loads(construction_path.read_text())
    config = next(item['content'] for item in construction['files'] if item['path'] == 'config.json')
    scratch = runtime_root / suffix / args.kind
    if scratch.exists():
        raise ValueError('Retain prior physical proof source; use a new output root')
    scratch.mkdir(parents=True)
    (scratch / 'config.json').write_text(config)
    for name in ('trace.jsonl', 'video_frames.jsonl', 'movement_history.jsonl',
                 'acquisition-provenance.json'):
        (scratch / name).write_text(spec['files'][name])
    if args.kind == 'incomplete_motion':
        rows = [json.loads(line) for line in
                (scratch / 'movement_history.jsonl').read_text().splitlines()]
        for row in rows:
            row['heading_deg'] = 0
            if suffix == 'left_right_roadway_continuation':
                row['ego_body_vertices_xy_m'] = rows[0]['ego_body_vertices_xy_m']
        (scratch / 'movement_history.jsonl').write_text(''.join(
            json.dumps(row, sort_keys=True) + '\n' for row in rows))
    if args.kind == 'missing_evidence':
        (scratch / 'movement_history.jsonl').unlink()
    result = physical_result(scratch, {'case_id': case, 'target_checks': [],
                                      'diagnostic_fixture': True})
    result['case_id'] = case
    output = Path(args.output)
    if output.exists():
        raise ValueError('Retain prior physical result')
    output.write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                'missing_evidence': 'unverified'}[args.kind]
    actual = result['physical_checks']['maneuver']['status']
    print(json.dumps({'case_id': case, 'kind': args.kind, 'status': actual,
                      'provenance_kind': result['provenance_kind']}))
    if actual != expected or result['maneuver_completed'] != (expected == 'met'):
        raise SystemExit('Unexpected physical fixture outcome')


if __name__ == '__main__':
    main()
