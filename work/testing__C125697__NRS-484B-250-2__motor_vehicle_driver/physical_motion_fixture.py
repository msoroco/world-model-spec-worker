"""CPU proof of each case's source-bound crossing completion classifier.

The fixture alters synthetic original bodies in a temporary directory. It does
not amend captured evidence or assert that CARLA can realize the path.
"""
import argparse
import copy
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))

from worker_exchange.common import sha  # noqa: E402
from worker_exchange.native_output import physical_result  # noqa: E402
from worker_exchange.native_output import seal_capture  # noqa: E402
from worker_exchange.saved_processing import (record_native_exit,
                                              acknowledge_owner_release)  # noqa: E402


CASE = HERE.name + '__off_ego_left_near_time'


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def run(kind, case=CASE, output=None):
    manifest = read(HERE / 'execution-manifest.json')
    entry = next(row for row in manifest['cases'] if row['case_id'] == case)
    construction_path = HERE / entry['construction']
    if sha(construction_path) != entry['construction_sha256']:
        raise ValueError('Exact primary construction changed')
    construction = read(construction_path)
    config = json.loads(next(row['content'] for row in construction['files']
                             if row['path'] == 'config.json'))
    recipe = read(REPO / entry['fixture_recipe'])
    source_path = REPO / recipe['generator']['source']
    if sha(source_path) != recipe['generator']['sha256']:
        raise ValueError('Synthetic diagnostic source changed')
    sources = read(source_path)['files']
    polygon = config['site']['crossing_polygon_xy_m']
    criterion = config.get('physical_completion', {})
    if (criterion.get('criterion') != 'intersection_clearance' or
            criterion.get('motion_source') != 'crossing_history.jsonl' or
            criterion.get('body_key') != 'ego_vertices_m' or
            criterion.get('intersection_polygon_xy_m') != polygon or
            criterion.get('exit_axis') != (1 if case.endswith('off_ego_right_near_time') else 0)
            or criterion.get('exit_sign') != 1):
        raise ValueError('Bundled primary physical completion criterion differs')
    with tempfile.TemporaryDirectory(prefix='c125697-motion-') as temporary:
        attempt = Path(temporary)
        write(attempt / 'config.json', config)
        for name in ('trace.jsonl', 'video_frames.jsonl', 'crossing_history.jsonl'):
            (attempt / name).write_text(sources[name])
        write(attempt / 'acquisition-provenance.json', {
            'provenance_kind': 'native', 'diagnostic_fixture': True,
            'scope': 'Synthetic CPU classifier fixture only',
        })
        if kind == 'lifecycle':
            saved_claims = []
            for claim in read(HERE / 'result.json')['tests']:
                name = claim.get('log', '')
                command = claim.get('command', '')
                if ('runtime.py process-saved' in command and '--case ' + case + ' ' in command
                        and '-primary-' in name and claim.get('exit_code') == 0):
                    path = HERE / name
                    if path.is_file() and sha(path) == claim.get('sha256'):
                        saved = read(path)
                        if (saved.get('passed') is True and saved.get('recorded_only') is True
                                and saved.get('native_revision', {}).get('construction_sha256')
                                == entry['construction_sha256']):
                            saved_claims.append((path, saved))
            if not saved_claims:
                raise ValueError('Current primary saved-processing proof missing')
            saved_path, saved = saved_claims[-1]
            write(attempt / 'construction.json', construction)
            (attempt / 'runner.py').write_text(next(row['content'] for row in construction['files']
                                                   if row['path'] == 'runner.py'))
            try:
                seal_capture(attempt, frames=60, restoration={'restored': True}, errors=[],
                             encoder_exit_codes={'fixture_encoder': 1},
                             context={'diagnostic_fixture': True})
            except ValueError as error:
                if 'unclosed/failed encoders' not in str(error):
                    raise
            else:
                raise AssertionError('Failed fixture encoder was sealed')
            sealed = seal_capture(attempt, frames=60, restoration={'restored': True}, errors=[],
                                  encoder_exit_codes={'fixture_encoder': 0},
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
            events = sealed['events'] + [native['event'], owner['event'], saved['events'][0]]
            expected_events = ['capture_finished', 'encoders_closed', 'restoration_verified',
                               'native_exit', 'owner_released', 'saved_processing_started']
            if events != expected_events:
                raise AssertionError('Saved processing preceded verified closure')
            result = {'case_id': case, 'events': events, 'diagnostic_fixture': True,
                      'failed_encoder_rejected': True, 'premature_release_rejected': True,
                      'saved_processing_log_sha256': sha(saved_path)}
            if output:
                write(output, result)
            return result
        motion = attempt / 'crossing_history.jsonl'
        if kind == 'missing_evidence':
            motion.unlink()
        else:
            rows = [json.loads(line) for line in motion.read_text().splitlines()]
            first = copy.deepcopy(rows[0]['ego_vertices_m'])
            for index, row in enumerate(rows):
                offset = (29.0 * index / (len(rows) - 1)) if kind == 'complete_motion' else 0.0
                body = [[x + offset, y] if criterion['exit_axis'] == 0 else [x, y + offset]
                        for x, y in first]
                row['ego_vertices_m'] = body
                row['ego']['body_vertices_xy_m'] = copy.deepcopy(body)
            motion.write_text(''.join(json.dumps(row, allow_nan=False) + '\n' for row in rows))
        result = physical_result(attempt, {'target_checks': []})
        expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                    'missing_evidence': 'unverified'}[kind]
        check = result['physical_checks']['maneuver']
        if check['status'] != expected or result['maneuver_completed'] != (expected == 'met'):
            raise AssertionError(f'Expected {expected}; got {check["status"]}')
        if not check['method'] or not check['sources']:
            raise AssertionError('Classifier omitted original source binding')
        if result['physical_acceptance_claimed'] is not False:
            raise AssertionError('Synthetic fixture claimed physical acceptance')
        if output:
            write(output, result)
        return {'case_id': case, 'fixture': kind, 'maneuver_status': expected,
                'diagnostic_fixture': True, 'source_hashes': check['sources']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--kind', required=True, choices=('complete_motion',
                        'incomplete_motion', 'missing_evidence', 'lifecycle'))
    parser.add_argument('--case', default=CASE)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
    print(json.dumps(run(args.kind, args.case, args.output), sort_keys=True))
