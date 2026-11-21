"""Source-bound synthetic checks for the four stop-sign clearance cases."""
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
from worker_exchange.native_output import physical_result, seal_capture  # noqa: E402
from worker_exchange.saved_processing import record_native_exit, acknowledge_owner_release  # noqa: E402


def read(path):
    return json.loads(Path(path).read_text())


def run(case, kind, output=None):
    manifest = read(HERE / 'execution-manifest.json')
    entry = next((e for e in manifest['cases'] if e['case_id'] == case), None)
    if entry is None:
        raise ValueError('Unknown exact case')
    construction_path = HERE / entry['construction']
    if sha(construction_path) != entry['construction_sha256']:
        raise ValueError('Exact construction changed')
    construction = read(construction_path)
    config = json.loads(next(f['content'] for f in construction['files'] if f['path'] == 'config.json'))
    criterion = config['physical_completion']
    if (criterion['criterion'] != 'intersection_clearance' or
            criterion['motion_source'] != 'crossing_history.jsonl' or
            criterion['body_key'] != 'ego.body_vertices_xy_m' or
            criterion['exit_axis'] != 0 or criterion['exit_sign'] != 1 or
            len(criterion['intersection_polygon_xy_m']) != 4):
        raise ValueError('Authored clearance criterion changed')
    recipe = read(REPO / entry['fixture_recipe'])
    source = REPO / recipe['generator']['source']
    if sha(source) != recipe['generator']['sha256']:
        raise ValueError('Synthetic diagnostic source changed')
    files = read(source)['files']
    with tempfile.TemporaryDirectory(prefix='c125745-sub1-physical-') as temp:
        attempt = Path(temp)
        (attempt / 'config.json').write_text(json.dumps(config) + '\n')
        for name in ('trace.jsonl', 'video_frames.jsonl', 'crossing_history.jsonl'):
            (attempt / name).write_text(files[name])
        (attempt / 'acquisition-provenance.json').write_text(json.dumps({
            'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True}) + '\n')
        if kind == 'lifecycle':
            post = entry['post_capture']
            saved_log = HERE / post['test_log']
            if post['test_exit_code'] != 0 or sha(saved_log) != post['test_log_sha256']:
                raise ValueError('Current saved-processing log changed')
            saved_text = saved_log.read_text()
            if case not in saved_text or '"recorded_only": true' not in saved_text:
                raise ValueError('Saved-processing log lacks this recorded-only case')
            (attempt / 'construction.json').write_text(json.dumps(construction) + '\n')
            (attempt / 'runner.py').write_text(next(f['content'] for f in construction['files']
                                                   if f['path'] == 'runner.py'))
            try:
                seal_capture(attempt, frames=4, restoration={'restored': True}, errors=[],
                             encoder_exit_codes={'synthetic_encoder': 1},
                             context={'diagnostic_fixture': True})
            except ValueError as error:
                if 'unclosed/failed encoders' not in str(error):
                    raise
            else:
                raise AssertionError('Failed synthetic encoder was sealed')
            sealed = seal_capture(attempt, frames=4, restoration={'restored': True}, errors=[],
                                  encoder_exit_codes={'synthetic_encoder': 0},
                                  context={'diagnostic_fixture': True})
            try:
                acknowledge_owner_release(attempt, attempt / 'owner-release.json', True)
            except ValueError as error:
                if 'Native process has not exited' not in str(error):
                    raise
            else:
                raise AssertionError('Owner release preceded synthetic Native exit')
            native = record_native_exit(attempt)
            owner = acknowledge_owner_release(attempt, attempt / 'owner-release.json', True)
            events = sealed['events'] + [native['event'], owner['event'], 'saved_processing_started']
            expected = ['capture_finished', 'encoders_closed', 'restoration_verified',
                        'native_exit', 'owner_released', 'saved_processing_started']
            if events != expected:
                raise AssertionError('Saved processing preceded verified closure')
            result = {'case_id': case, 'events': events, 'diagnostic_fixture': True,
                      'failed_encoder_rejected': True, 'premature_release_rejected': True,
                      'saved_processing_log_sha256': sha(saved_log)}
            if output:
                Path(output).write_text(json.dumps(result, indent=2) + '\n')
            return result
        motion = attempt / 'crossing_history.jsonl'
        if kind == 'missing_evidence':
            motion.unlink()
        else:
            rows = [json.loads(line) for line in motion.read_text().splitlines()]
            first = copy.deepcopy(rows[0]['ego']['body_vertices_xy_m'])
            for index, row in enumerate(rows):
                offset = 29.0 * index / (len(rows) - 1) if kind == 'complete_motion' else 0.0
                body = [[x + offset, y] for x, y in first]
                row['ego']['body_vertices_xy_m'] = body
                row['ego_vertices_m'] = copy.deepcopy(body)
            motion.write_text(''.join(json.dumps(row) + '\n' for row in rows))
        result = physical_result(attempt, {'target_checks': []})
    expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                'missing_evidence': 'unverified'}[kind]
    check = result['physical_checks']['maneuver']
    if (check['status'] != expected or result['maneuver_completed'] != (expected == 'met') or
            not check['method'] or not check['sources'] or
            result['provenance_kind'] != 'synthetic_fixture' or
            result['diagnostic_fixture'] is not True or
            result['physical_acceptance_claimed'] is not False):
        raise AssertionError('Physical classifier did not establish expected synthetic outcome')
    if expected == 'met' and not result['realized_observables']:
        raise AssertionError('Complete synthetic motion has no diagnostic observations')
    if output:
        Path(output).write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    return {'case_id': case, 'kind': kind, 'status': expected,
            'diagnostic_fixture': True, 'physical_acceptance_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--kind', choices=('complete_motion', 'incomplete_motion', 'missing_evidence', 'lifecycle'), required=True)
    parser.add_argument('--output')
    args = parser.parse_args()
    print(json.dumps(run(args.case, args.kind, args.output), sort_keys=True))
