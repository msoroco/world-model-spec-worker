"""CPU fixtures for the exact speed-case motion and capture lifecycle gates."""

import argparse
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))

from worker_exchange.common import sha
from worker_exchange.native_output import physical_result, seal_capture
from worker_exchange.saved_processing import record_native_exit, acknowledge_owner_release


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def sources(root, entry, speed_mps):
    construction_path = HERE / entry['construction']
    if sha(construction_path) != entry['construction_sha256']:
        raise ValueError('Exact construction changed')
    construction = read(construction_path)
    files = {row['path']: row['content'] for row in construction['files']}
    config = json.loads(files['config.json'])
    if config['selected_case_id'] != entry['case_id'] or config['rate_hz'] != 20:
        raise ValueError('Exact speed case or rate differs')
    write(root / 'config.json', config)
    write(root / 'construction.json', construction)
    (root / 'runner.py').write_text(files['runner.py'])
    write(root / 'acquisition-provenance.json', {
        'provenance_kind': 'native', 'diagnostic_fixture': True,
        'scope': 'Synthetic Native-shaped CPU classifier fixture only'})
    trace, mapping = [], []
    for index in range(61):
        time = index / 20
        position = speed_mps * time
        trace.append({'frame': 1000 + index, 'time_s': time,
                      'position': {'x': position, 'y': 0, 'z': 0},
                      'position_m': [position, 0, 0], 'heading_deg': 0,
                      'speed_mps': speed_mps, 'speed_mph': speed_mps / .44704})
        mapping.append({'video_frame': index, 'carla_frame': 1000 + index,
                        'time_s': time})
    (root / 'trace.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in trace))
    (root / 'video_frames.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in mapping))


def motion(entry, kind, output):
    with tempfile.TemporaryDirectory(prefix='c10301-physical-') as temporary:
        root = Path(temporary)
        sources(root, entry, 30 if kind == 'complete_motion' else 1)
        if kind == 'missing_evidence':
            (root / 'trace.jsonl').unlink()
        result = physical_result(root, {'target_checks': []})
        expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                    'missing_evidence': 'unverified'}[kind]
        check = result['physical_checks']['maneuver']
        if check['status'] != expected or result['maneuver_completed'] != (expected == 'met'):
            raise ValueError('Physical motion classifier differs from source fixture')
        if not check['sources'] or not check['method'] or not result['diagnostic_fixture']:
            raise ValueError('Physical fixture lost source provenance')
        if result['physical_acceptance_claimed'] is not False:
            raise ValueError('CPU fixture claimed physical acceptance')
        if kind == 'missing_evidence' and 'trace.jsonl' not in check['missing_evidence']:
            raise ValueError('Missing original trace was not reported')
        write(output, result)
        print(json.dumps({'case_id': entry['case_id'], 'kind': kind,
                          'maneuver_status': expected, 'diagnostic_fixture': True}))


def lifecycle(entry, output):
    receipt_path = HERE / entry['saved_processing']['receipt']
    if sha(receipt_path) != entry['saved_processing']['sha256']:
        raise ValueError('Saved processing receipt changed')
    saved = read(receipt_path)
    if not saved.get('passed') or not saved.get('recorded_only') or saved['case_id'] != entry['case_id']:
        raise ValueError('Current recorded-only saved path missing')
    with tempfile.TemporaryDirectory(prefix='c10301-lifecycle-') as temporary:
        root = Path(temporary)
        sources(root, entry, 1)
        try:
            seal_capture(root, frames=61, restoration={'restored': True}, errors=[],
                         encoder_exit_codes={'fixture_encoder': 1})
        except ValueError as error:
            if 'unclosed/failed encoders' not in str(error):
                raise
        else:
            raise ValueError('Failed encoder was sealed')
        seal = seal_capture(root, frames=61, restoration={'restored': True}, errors=[],
                            encoder_exit_codes={'fixture_encoder': 0},
                            context={'diagnostic_fixture': True})
        try:
            acknowledge_owner_release(root, root / 'owner-release.json', True)
        except ValueError as error:
            if 'Native process has not exited' not in str(error):
                raise
        else:
            raise ValueError('Owner release preceded Native exit')
        native = record_native_exit(root)
        owner = acknowledge_owner_release(root, root / 'owner-release.json', True)
        events = seal['events'] + [native['event'], owner['event'], saved['events'][0]]
        expected = ['capture_finished', 'encoders_closed', 'restoration_verified',
                    'native_exit', 'owner_released', 'saved_processing_started']
        if events != expected:
            raise ValueError('Saved processing preceded verified ownership closure')
        write(output, {'events': events, 'diagnostic_fixture': True,
                       'failed_encoder_rejected': True, 'premature_release_rejected': True,
                       'capture_seal_sha256': sha(root / 'capture-seal.json'),
                       'native_exit_sha256': sha(root / 'native-exit.json'),
                       'owner_release_sha256': sha(root / 'owner-release.json'),
                       'saved_processing_receipt_sha256': sha(receipt_path)})
        print(json.dumps({'case_id': entry['case_id'], 'events': events,
                          'diagnostic_fixture': True}))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--kind', required=True, choices=(
        'complete_motion', 'incomplete_motion', 'missing_evidence', 'lifecycle'))
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    manifest = read(HERE / 'execution-manifest.json')
    entry = next((row for row in manifest['cases'] if row['case_id'] == args.case), None)
    if entry is None:
        raise ValueError('Unknown exact physical fixture case')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.kind == 'lifecycle':
        lifecycle(entry, args.output)
    else:
        motion(entry, args.kind, args.output)


if __name__ == '__main__':
    main()
