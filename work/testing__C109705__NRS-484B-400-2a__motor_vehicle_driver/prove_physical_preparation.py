"""Source-shaped CPU outcome and lifecycle proofs; no physical acceptance."""
import argparse
import copy
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

DIAGNOSTICS = ('diagnostic.json', 'second-diagnostic.json',
               'imaginary-near-diagnostic.json', 'imaginary-far-diagnostic.json')


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def run(case, kind, output):
    manifest = read(HERE / 'execution-manifest.json')
    matches = [(i, entry) for i, entry in enumerate(manifest['cases']) if entry['case_id'] == case]
    if len(matches) != 1:
        raise ValueError('Select one exact case')
    index, entry = matches[0]
    construction_path = HERE / entry['construction']
    if sha(construction_path) != entry['construction_sha256']:
        raise ValueError('Exact construction changed')
    construction = read(construction_path)
    config = json.loads(next(f['content'] for f in construction['files'] if f['path'] == 'config.json'))
    criterion = config.get('physical_completion', {})
    if config['selected_case_id'] != case or criterion.get('criterion') != 'intersection_clearance' or criterion.get('exit_axis') != 1 or criterion.get('exit_sign') != 1 or criterion.get('motion_source') != 'body_history.jsonl':
        raise ValueError('Exact positive-y physical completion criterion absent')
    sources = read(HERE / DIAGNOSTICS[index])['files']
    with tempfile.TemporaryDirectory(dir=REPO / '.runtime-work', prefix='c109705-physical-') as temp:
        attempt = Path(temp)
        write(attempt / 'config.json', config)
        for name in ('trace.jsonl', 'video_frames.jsonl', 'body_history.jsonl', 'road_geometry.json'):
            (attempt / name).write_text(sources[name])
        write(attempt / 'acquisition-provenance.json', {'provenance_kind': 'native', 'diagnostic_fixture': True,
                                                       'scope': 'source-shaped CPU protocol proof only'})
        if kind == 'lifecycle':
            saved = read(HERE / entry['post_capture']['test_log'])
            if sha(HERE / entry['post_capture']['test_log']) != entry['post_capture']['test_log_sha256'] or saved.get('passed') is not True or saved.get('recorded_only') is not True or saved.get('candidate_id') != 'primary' or saved.get('events', [None])[0] != 'saved_processing_started':
                raise ValueError('Current primary saved-processing proof absent')
            write(attempt / 'construction.json', construction)
            (attempt / 'runner.py').write_text(next(f['content'] for f in construction['files'] if f['path'] == 'runner.py'))
            try:
                seal_capture(attempt, frames=9, restoration={'restored': True}, errors=[],
                             encoder_exit_codes={'fixture_encoder': 1}, context={'diagnostic_fixture': True})
            except ValueError as error:
                if 'unclosed/failed encoders' not in str(error):
                    raise
            else:
                raise AssertionError('Failed encoder was sealed')
            seal = seal_capture(attempt, frames=9, restoration={'restored': True}, errors=[],
                                encoder_exit_codes={'fixture_encoder': 0}, context={'diagnostic_fixture': True})
            try:
                acknowledge_owner_release(attempt, attempt / 'owner-release.json', True)
            except ValueError as error:
                if 'Native process has not exited' not in str(error):
                    raise
            else:
                raise AssertionError('Premature owner release passed')
            native = record_native_exit(attempt)
            owner = acknowledge_owner_release(attempt, attempt / 'owner-release.json', True)
            events = seal['events'] + [native['event'], owner['event'], saved['events'][0]]
            expected = ['capture_finished', 'encoders_closed', 'restoration_verified',
                        'native_exit', 'owner_released', 'saved_processing_started']
            if events != expected:
                raise AssertionError('Lifecycle ordering differs')
            print(json.dumps({'case_id': case, 'kind': kind, 'events': events,
                              'failed_encoder_rejected': True, 'premature_release_rejected': True,
                              'diagnostic_fixture': True}, sort_keys=True))
            return
        if kind == 'missing_evidence':
            (attempt / 'body_history.jsonl').unlink()
        elif kind == 'incomplete_motion':
            rows = [json.loads(line) for line in (attempt / 'body_history.jsonl').read_text().splitlines()]
            for row in rows:
                if row['road_id'] == 2:
                    row['road_id'] = 3
                    row['body_vertices_m'] = [[x, 0.0, z] for x, _y, z in row['body_vertices_m']]
            (attempt / 'body_history.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in rows))
        result = physical_result(attempt, {'case_id': case, 'target_checks': []})
        expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                    'missing_evidence': 'unverified'}[kind]
        check = result['physical_checks']['maneuver']
        if check['status'] != expected or result['maneuver_completed'] != (expected == 'met') or not check['method'] or not check['sources'] or result['physical_acceptance_claimed'] is not False:
            raise AssertionError('Physical outcome fixture differs: ' + kind)
        if expected == 'met' and (result['provenance_kind'] != 'native' or not result['realized_observables']):
            raise AssertionError('Complete fixture lacks realized original motion')
        write(output, result)
        print(json.dumps({'case_id': case, 'kind': kind, 'status': expected,
                          'source_hashes': check['sources'], 'diagnostic_fixture': True}, sort_keys=True))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case')
    parser.add_argument('--kind', choices=('complete_motion', 'incomplete_motion', 'missing_evidence', 'lifecycle'))
    parser.add_argument('--output', type=Path)
    parser.add_argument('--all', action='store_true', help='prove all exact primary cases and outcomes')
    args = parser.parse_args()
    if args.all:
        if args.case or args.kind or args.output:
            parser.error('--all has no case/kind/output arguments')
        manifest = read(HERE / 'execution-manifest.json')
        for index, entry in enumerate(manifest['cases']):
            for kind in ('complete_motion', 'incomplete_motion', 'missing_evidence', 'lifecycle'):
                output = None if kind == 'lifecycle' else HERE / 'physical-proofs' / f'case{index}' / (kind + '.json')
                if output:
                    output.parent.mkdir(parents=True, exist_ok=True)
                run(entry['case_id'], kind, output)
        print('All four source-shaped physical outcome and lifecycle proofs passed')
        sys.exit(0)
    if not args.case or not args.kind:
        parser.error('--case and --kind are required without --all')
    if args.kind != 'lifecycle' and args.output is None:
        parser.error('--output required for outcome fixture')
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
    run(args.case, args.kind, args.output)
