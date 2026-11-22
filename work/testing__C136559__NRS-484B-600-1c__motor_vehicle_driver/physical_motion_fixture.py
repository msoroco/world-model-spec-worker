"""Synthetic source-bound travel and capture lifecycle probes for posted-speed cases."""
import argparse
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))
from worker_exchange.common import sha  # noqa: E402
from worker_exchange.native_output import physical_result, seal_capture  # noqa: E402
from worker_exchange.saved_processing import record_native_exit, acknowledge_owner_release  # noqa: E402


def read(path):
    return json.loads(Path(path).read_text())


def run(case, kind, output=None):
    manifest = read(HERE / 'execution-manifest.json')
    entry = next((item for item in manifest['cases'] if item['case_id'] == case), None)
    if entry is None:
        raise ValueError('Unknown exact selected case')
    construction_path = HERE / entry['construction']
    if sha(construction_path) != entry['construction_sha256']:
        raise ValueError('Exact construction changed')
    construction = read(construction_path)
    config = json.loads(next(item['content'] for item in construction['files']
                             if item['path'] == 'config.json'))
    recipe = read(REPO / entry['fixture_recipe'])
    source = REPO / recipe['generator']['source']
    if sha(source) != recipe['generator']['sha256']:
        raise ValueError('Synthetic diagnostic source changed')
    files = read(source)['files']
    with tempfile.TemporaryDirectory(prefix='c136559-physical-', dir=REPO / '.runtime-work') as temp:
        attempt = Path(temp)
        (attempt / 'config.json').write_text(json.dumps(config) + '\n')
        for name in ('trace.jsonl', 'video_frames.jsonl'):
            (attempt / name).write_text(files[name])
        (attempt / 'acquisition-provenance.json').write_text(json.dumps({
            'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True}) + '\n')
        if kind == 'lifecycle':
            saved = HERE / entry['saved_processing']['receipt']
            if sha(saved) != entry['saved_processing']['sha256']:
                raise ValueError('Saved-processing receipt changed')
            receipt = read(saved)
            if (receipt.get('case_id') != case or receipt.get('passed') is not True
                    or receipt.get('recorded_only') is not True):
                raise ValueError('No exact recorded-only saved proof')
            (attempt / 'construction.json').write_text(json.dumps(construction) + '\n')
            (attempt / 'runner.py').write_text(next(item['content'] for item in construction['files']
                                                   if item['path'] == 'runner.py'))
            try:
                seal_capture(attempt, frames=9, restoration={'restored': True}, errors=[],
                             encoder_exit_codes={'synthetic_encoder': 1},
                             context={'diagnostic_fixture': True})
            except ValueError as error:
                if 'unclosed/failed encoders' not in str(error):
                    raise
            else:
                raise AssertionError('Failed encoder was sealed')
            sealed = seal_capture(attempt, frames=9, restoration={'restored': True}, errors=[],
                                  encoder_exit_codes={'synthetic_encoder': 0},
                                  context={'diagnostic_fixture': True})
            try:
                acknowledge_owner_release(attempt, attempt / 'owner-release.json', True)
            except ValueError as error:
                if 'Native process has not exited' not in str(error):
                    raise
            else:
                raise AssertionError('Owner release preceded Native exit')
            native = record_native_exit(attempt)
            owner = acknowledge_owner_release(attempt, attempt / 'owner-release.json', True)
            events = sealed['events'] + [native['event'], owner['event'], 'saved_processing_started']
            expected = ['capture_finished', 'encoders_closed', 'restoration_verified',
                        'native_exit', 'owner_released', 'saved_processing_started']
            if events != expected:
                raise AssertionError('Closure sequence changed')
            result = {'case_id': case, 'events': events, 'diagnostic_fixture': True,
                      'failed_encoder_rejected': True, 'premature_release_rejected': True,
                      'saved_processing_receipt_sha256': sha(saved)}
        else:
            motion = attempt / 'trace.jsonl'
            if kind == 'missing_evidence':
                motion.unlink()
            elif kind == 'complete_motion':
                rows = [json.loads(line) for line in motion.read_text().splitlines()]
                for index, row in enumerate(rows):
                    row['position_m'][0] = 100 + 10 * index
                    row['position']['x'] = 100 + 10 * index
                motion.write_text(''.join(json.dumps(row) + '\n' for row in rows))
            result = physical_result(attempt, {'target_checks': []})
            expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                        'missing_evidence': 'unverified'}[kind]
            check = result['physical_checks']['maneuver']
            if (check['status'] != expected or result['maneuver_completed'] != (expected == 'met')
                    or not check['method'] or not check['sources']
                    or result['provenance_kind'] != 'synthetic_fixture'
                    or result['diagnostic_fixture'] is not True
                    or result['physical_acceptance_claimed'] is not False):
                raise AssertionError('Physical classifier changed')
            if expected == 'met' and not result['realized_observables']:
                raise AssertionError('Complete synthetic travel lacks measured values')
    if output:
        Path(output).write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    return {'case_id': case, 'kind': kind, 'diagnostic_fixture': True,
            'physical_acceptance_claimed': False,
            'status': result.get('physical_checks', {}).get('maneuver', {}).get('status', 'lifecycle_passed')}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--kind', required=True,
                        choices=('complete_motion', 'incomplete_motion', 'missing_evidence', 'lifecycle'))
    parser.add_argument('--output')
    args = parser.parse_args()
    print(json.dumps(run(args.case, args.kind, args.output), sort_keys=True))
