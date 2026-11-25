"""CPU fixture checks for source-derived motion and Native closure order."""
import argparse
import json
import os
import shutil
from pathlib import Path

from worker_exchange.native_output import physical_result, seal_capture
from worker_exchange.saved_processing import record_native_exit, acknowledge_owner_release, _closure

HERE = Path(__file__).resolve().parent
EXPECTED = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
            'missing_evidence': 'unverified'}


def scratch(name):
    root = Path(os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT']).resolve()
    if '.runtime-work' not in root.parts:
        raise ValueError('Physical fixture scratch must be under .runtime-work')
    path = root / name
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True)
    return path


def construction(index):
    return json.loads((HERE / f'selected-probe-{index}-primary-construction.json').read_text())


def prepare(index, kind):
    root = scratch(f'physical-{index}-{kind}')
    bundle = construction(index)
    for item in bundle['files']:
        if item['path'] == 'config.json':
            (root / 'config.json').write_text(item['content'])
    source = HERE / f'selected-source-probe-{index}'
    for name in ('trace.jsonl', 'video_frames.jsonl',
                 'stop_history.jsonl', 'crosswalk_geometry.json'):
        shutil.copyfile(source / name, root / name)
    return root, bundle


def outcome(index, kind):
    if index not in (1, 2) or kind not in EXPECTED:
        raise ValueError('Exact case/physical outcome required')
    root, bundle = prepare(index, kind)
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
    target = HERE / 'physical-preparation' / str(index)
    target.mkdir(parents=True, exist_ok=True)
    (target / f'{kind}-result.json').write_text(json.dumps(result, indent=2) + '\n')
    print('PASS', bundle['case_id'], kind, status)


def lifecycle(index):
    if index not in (1, 2):
        raise ValueError('Exact case required')
    root, bundle = prepare(index, 'lifecycle')
    (root / 'construction.json').write_text(json.dumps(bundle, indent=2) + '\n')
    for item in bundle['files']:
        if item['path'] == 'runner.py':
            (root / 'runner.py').write_text(item['content'])
    (root / 'acquisition-provenance.json').write_text(json.dumps({'diagnostic_fixture': True}) + '\n')
    seal_capture(root, frames=600, restoration={'restored': True}, errors=[],
                 encoder_exit_codes={name: 0 for name in
                                     ('overview', 'approach', 'reference_corner', 'driver_reference')})
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
    events = ['capture_finished', 'encoders_closed', 'restoration_verified',
              'native_exit', 'owner_released', 'saved_processing_started']
    print('PASS', bundle['case_id'], 'synthetic lifecycle', json.dumps(events))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--probe', type=int, required=True)
    parser.add_argument('--kind', choices=(*EXPECTED, 'lifecycle'), required=True)
    args = parser.parse_args()
    lifecycle(args.probe) if args.kind == 'lifecycle' else outcome(args.probe, args.kind)
