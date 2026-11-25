"""Check three U-turn completion outcomes on explicit synthetic CPU sources."""

import argparse
import json
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SUFFIXES = ('source_verified_single_movement_uturn',
            'source_verified_multiple_movement_uturn',
            'divider_encroachment_before_opening_uturn')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--kind', choices=('complete_motion', 'incomplete_motion',
                                           'missing_evidence'), required=True)
    parser.add_argument('--suffix', choices=SUFFIXES, required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    runtime_root = Path(os.environ.get('SCENARIO_PIPELINE_OUTPUT_ROOT', '')).resolve()
    if not runtime_root.is_relative_to(REPO / '.runtime-work'):
        raise ValueError('Set SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work')
    sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))
    from worker_exchange.native_output import physical_result

    spec = json.loads((ROOT / 'cases' / args.suffix /
                       (args.suffix + '-diagnostic-sources.json')).read_text())
    construction = ROOT / ('construction.json' if args.suffix == SUFFIXES[0]
                           else 'cases/' + args.suffix + '/construction.json')
    config = next(item['content'] for item in json.loads(construction.read_text())['files']
                  if item['path'] == 'config.json')
    scratch = runtime_root / args.suffix / args.kind
    if scratch.exists():
        raise ValueError('Retain previous physical proof; use a fresh output root')
    scratch.mkdir(parents=True)
    (scratch / 'config.json').write_text(config)
    for name in ('trace.jsonl', 'video_frames.jsonl', 'movement_history.jsonl',
                 'acquisition-provenance.json'):
        (scratch / name).write_text(spec['files'][name])
    if args.kind == 'incomplete_motion':
        path = scratch / 'movement_history.jsonl'
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        for row in rows:
            row['heading_deg'] = 0
        path.write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows))
    elif args.kind == 'missing_evidence':
        (scratch / 'movement_history.jsonl').unlink()
    case_id = ROOT.name + '__' + args.suffix
    result = physical_result(scratch, {'case_id': case_id, 'target_checks': [],
                                       'diagnostic_fixture': True})
    result['case_id'] = case_id
    output = Path(args.output)
    if output.exists():
        raise ValueError('Retain previous physical result')
    output.write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                'missing_evidence': 'unverified'}[args.kind]
    actual = result['physical_checks']['maneuver']['status']
    print(json.dumps({'case_id': case_id, 'kind': args.kind, 'status': actual,
                      'provenance_kind': result['provenance_kind']}))
    if actual != expected or result['maneuver_completed'] != (expected == 'met'):
        raise SystemExit('Unexpected physical outcome')


if __name__ == '__main__':
    main()
