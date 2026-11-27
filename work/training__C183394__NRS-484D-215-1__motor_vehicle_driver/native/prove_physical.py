"""Exercise the pinned physical assessor on source-shaped beam diagnostics."""
import argparse
import json
import os
from pathlib import Path
import shutil
import sys

HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parent
REPO = next(parent for parent in HERE.parents if (parent / 'batch.json').is_file())
sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))
from worker_exchange.native_output import assess_physical


def run(kind, case):
    if kind not in ('complete_motion', 'incomplete_motion', 'missing_evidence'):
        raise ValueError('Unknown physical fixture')
    source = PACKAGE / 'fixture-source' / case
    construction = json.loads((PACKAGE / 'constructions' / case / 'primary' / 'construction.json').read_text())
    config = json.loads(next(item['content'] for item in construction['files']
                             if item['path'] == 'config.json'))
    scratch = Path(os.environ['TMPDIR']).resolve() / ('physical-' + case + '-' + kind)
    if scratch.exists():
        shutil.rmtree(scratch)
    scratch.mkdir(parents=True)
    (scratch / 'config.json').write_text(json.dumps(config) + '\n')
    for name in ('video_frames.jsonl', 'trace.jsonl'):
        shutil.copyfile(source / name, scratch / name)
    if kind == 'incomplete_motion':
        rows = [json.loads(line) for line in (scratch / 'trace.jsonl').read_text().splitlines()]
        origin = rows[0]['position_m']
        for row in rows:
            row['position_m'] = origin
        (scratch / 'trace.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in rows))
    elif kind == 'missing_evidence':
        (scratch / 'trace.jsonl').unlink()
    assessment = assess_physical(scratch, config)
    expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                'missing_evidence': 'unverified'}[kind]
    maneuver = assessment['physical_checks']['maneuver']
    assert maneuver['status'] == expected, (kind, maneuver)
    result = {'case_id': config['selected_case_id'], 'fixture_kind': kind,
              'physical_checks': {'maneuver': maneuver},
              'maneuver_completed': expected == 'met',
              'realized_observables': assessment['realized_observables'] if expected == 'met' else {},
              'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True,
              'legal_verdict_claimed': False, 'physical_acceptance_claimed': False}
    destination = PACKAGE / 'native' / ('physical-' + case + '-' + kind + '.json')
    destination.write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    return {'kind': kind, 'case_id': config['selected_case_id'], 'status': expected,
            'diagnostic_only': True}


def lifecycle():
    events = ['capture_finished', 'encoders_closed', 'restoration_verified',
              'native_exit', 'owner_released', 'saved_processing_started']
    def check(actual):
        if actual != events:
            raise ValueError('Saved processing before Native ownership closure')
    check(events)
    for bad in (events[:-1], events[:3] + events[4:5] + events[3:4] + events[5:]):
        try:
            check(bad)
        except ValueError:
            pass
        else:
            raise AssertionError('Broken capture lifecycle accepted')
    return {'events': events, 'invalid_order_rejected': True,
            'native_run_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--kind', choices=('complete_motion', 'incomplete_motion',
                                           'missing_evidence', 'lifecycle'), required=True)
    parser.add_argument('--case', choices=('condition_a', 'condition_b',
        'distance_below_500ft', 'distance_at_500ft', 'distance_above_500ft'))
    args = parser.parse_args()
    if args.kind != 'lifecycle' and not args.case:
        parser.error('--case is required for motion fixtures')
    print(json.dumps(lifecycle() if args.kind == 'lifecycle' else run(args.kind, args.case)))
