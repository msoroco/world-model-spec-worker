"""CPU fixture checks for exact stop-line motion and Native closure order."""
import argparse
import json
import os
import shutil
from pathlib import Path

from worker_exchange.native_output import physical_result, seal_capture
from worker_exchange.saved_processing import record_native_exit, acknowledge_owner_release, _closure

HERE = Path(__file__).resolve().parent
EXPECTED = {'complete_motion': 'met', 'incomplete_motion': 'not_met', 'missing_evidence': 'unverified'}


def scratch(name):
    root = Path(os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT']).resolve()
    if '.runtime-work' not in root.parts:
        raise ValueError('Physical fixture scratch must be under .runtime-work')
    path = root / name
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True)
    return path


def prepare(condition, kind):
    root = scratch(f'physical-{condition}-{kind}')
    bundle = json.loads((HERE / f'selected-condition-{condition}-primary-construction.json').read_text())
    for item in bundle['files']:
        if item['path'] == 'config.json':
            (root / 'config.json').write_text(item['content'])
    source = HERE / f'selected-source-condition-{condition}'
    for name in ('trace.jsonl', 'video_frames.jsonl', 'stop_history.jsonl', 'crosswalk_geometry.json'):
        shutil.copyfile(source / name, root / name)
    return root, bundle


def outcome(condition, kind):
    root, bundle = prepare(condition, kind)
    if kind == 'incomplete_motion':
        rows = [json.loads(line) for line in (root / 'stop_history.jsonl').read_text().splitlines()]
        first = rows[0]['body_vertices_m']
        for row in rows:
            row['body_vertices_m'] = first
        (root / 'stop_history.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in rows))
    if kind == 'missing_evidence':
        (root / 'stop_history.jsonl').unlink()
    result = physical_result(root, {'case_id': bundle['case_id'], 'target_checks': [],
                                    'physical_acceptance_claimed': False,
                                    'legal_verdict_claimed': False})
    status = result['physical_checks']['maneuver']['status']
    if status != EXPECTED[kind] or result['maneuver_completed'] != (kind == 'complete_motion'):
        raise AssertionError('Physical source assessment differs: ' + status)
    if result['provenance_kind'] != 'synthetic_fixture' or result['diagnostic_fixture'] is not True:
        raise AssertionError('Fixture provenance lost')
    target = HERE / 'physical-preparation' / condition
    target.mkdir(parents=True, exist_ok=True)
    (target / f'{kind}-result.json').write_text(json.dumps(result, indent=2) + '\n')
    print('PASS', bundle['case_id'], kind, status)


def lifecycle(condition):
    root, bundle = prepare(condition, 'lifecycle')
    (root / 'construction.json').write_text(json.dumps(bundle, indent=2) + '\n')
    for item in bundle['files']:
        if item['path'] == 'runner.py':
            (root / 'runner.py').write_text(item['content'])
    (root / 'acquisition-provenance.json').write_text(json.dumps({'diagnostic_fixture': True}) + '\n')
    seal_capture(root, frames=600, restoration={'restored': True}, errors=[],
                 encoder_exit_codes={name: 0 for name in ('overview', 'approach', 'reference_corner', 'driver_reference')})
    try:
        acknowledge_owner_release(root, root / 'owner-release.json', True)
    except ValueError as error:
        if 'Native process has not exited' not in str(error):
            raise
    else:
        raise AssertionError('Premature owner release accepted')
    record_native_exit(root)
    acknowledge_owner_release(root, root / 'owner-release.json', True)
    _closure(root, root / 'owner-release.json', 'native', True)
    print('PASS', bundle['case_id'], 'synthetic lifecycle')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--condition', choices=('a', 'b'), required=True)
    parser.add_argument('--kind', choices=(*EXPECTED, 'lifecycle'), required=True)
    args = parser.parse_args()
    lifecycle(args.condition) if args.kind == 'lifecycle' else outcome(args.condition, args.kind)
