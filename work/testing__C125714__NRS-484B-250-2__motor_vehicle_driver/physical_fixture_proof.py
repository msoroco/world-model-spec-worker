"""C125714 CPU fixtures for physical classification and closure ordering.

The Native marker is a classifier input inside a synthetic fixture. No CARLA
run, physical visibility, or legal acceptance is claimed by these proofs.
"""
import argparse
import copy
import json
import shlex
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent.parent
sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))
from worker_exchange.common import sha  # noqa: E402
from worker_exchange.native_output import physical_result, seal_capture  # noqa: E402
from worker_exchange.saved_processing import record_native_exit, acknowledge_owner_release  # noqa: E402


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def inputs(root, entry):
    construction = read(ROOT / entry['construction'])
    config = json.loads(next(item['content'] for item in construction['files']
                             if item['path'] == 'config.json'))
    recipe = read(REPO / entry['fixture_recipe'])
    generator = REPO / recipe['generator']['source']
    if sha(generator) != recipe['generator']['sha256']:
        raise ValueError('Changed original diagnostic generator')
    files = read(generator)['files']
    write(root / 'config.json', config)
    for name in ('trace.jsonl', 'video_frames.jsonl', 'crossing_history.jsonl',
                 'road_geometry.json'):
        if name not in files:
            raise ValueError('Missing generated source: ' + name)
        (root / name).write_text(files[name])
    write(root / 'acquisition-provenance.json', {
        'provenance_kind': 'native', 'diagnostic_fixture': True,
        'scope': 'Synthetic CPU physical-classifier fixture only'})
    return construction


def motion(entry, kind, output):
    with tempfile.TemporaryDirectory(prefix='c125714-motion-') as temp:
        root = Path(temp)
        inputs(root, entry)
        source = root / 'crossing_history.jsonl'
        if kind == 'incomplete_motion':
            rows = [json.loads(line) for line in source.read_text().splitlines()]
            first = copy.deepcopy(rows[0]['ego_vertices_m'])
            for row in rows:
                row['ego_vertices_m'] = copy.deepcopy(first)
            source.write_text(''.join(json.dumps(row) + '\n' for row in rows))
        elif kind == 'missing_evidence':
            source.unlink()
        result = physical_result(root, {'target_checks': []})
        expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                    'missing_evidence': 'unverified'}[kind]
        check = result['physical_checks']['maneuver']
        if check['status'] != expected or result['maneuver_completed'] != (expected == 'met'):
            raise ValueError('Physical classifier mismatch: ' + check['status'] + ' expected ' + expected)
        if not check['sources'] or not check['method']:
            raise ValueError('Physical outcome lacks original source hashes/method')
        if result['diagnostic_fixture'] is not True or result['physical_acceptance_claimed'] is not False:
            raise ValueError('CPU fixture was misclassified as physical acceptance')
        if kind == 'missing_evidence' and 'crossing_history.jsonl' not in check['missing_evidence']:
            raise ValueError('Missing original body history was not reported')
        write(output, result)
        print(json.dumps({'case_id': entry['case_id'], 'fixture': kind,
                          'maneuver_status': check['status'], 'diagnostic_fixture': True}))


def saved_receipt(entry):
    claims = read(ROOT / 'result.json')['tests']
    case_id = entry['case_id']
    matches = []
    for claim in claims:
        tokens = shlex.split(claim['command'])
        if ('process-saved' in tokens and '--case' in tokens
                and tokens[tokens.index('--case') + 1] == case_id):
            attempt = REPO / tokens[tokens.index('--attempt') + 1]
            selection = read(attempt / 'candidate-selection.json')
            if selection.get('candidate_id') != 'primary':
                continue
            if sha(ROOT / claim['log']) != claim['sha256']:
                raise ValueError('Recorded-only saved proof log changed')
            matches.append(REPO / tokens[tokens.index('--output') + 1] / 'v0001/processing.json')
    if len(matches) != 1:
        raise ValueError('One primary recorded-only saved proof required')
    path = matches[0]
    receipt = read(path)
    if (receipt.get('format') != 'worker-saved-processing' or receipt.get('passed') is not True
            or receipt.get('recorded_only') is not True or receipt.get('case_id') != case_id
            or receipt['analysis_revision']['construction_sha256'] != entry['construction_sha256']):
        raise ValueError('Current selected recorded-only saved proof missing')
    return path, receipt


def lifecycle(entry, output):
    saved_path, saved = saved_receipt(entry)
    with tempfile.TemporaryDirectory(prefix='c125714-lifecycle-') as temp:
        root = Path(temp)
        construction = inputs(root, entry)
        write(root / 'construction.json', construction)
        (root / 'runner.py').write_text(next(item['content'] for item in construction['files']
                                          if item['path'] == 'runner.py'))
        try:
            seal_capture(root, frames=60, restoration={'restored': True}, errors=[],
                         encoder_exit_codes={'fixture_encoder': 1}, context={'diagnostic_fixture': True})
        except ValueError as error:
            if 'unclosed/failed encoders' not in str(error):
                raise
        else:
            raise ValueError('Failed fixture encoder was sealed')
        seal = seal_capture(root, frames=60, restoration={'restored': True}, errors=[],
                            encoder_exit_codes={'fixture_encoder': 0}, context={'diagnostic_fixture': True})
        try:
            acknowledge_owner_release(root, root / 'owner-release.json', True)
        except ValueError as error:
            if 'Native process has not exited' not in str(error):
                raise
        else:
            raise ValueError('Owner release preceded Native exit')
        exit_receipt = record_native_exit(root)
        owner = acknowledge_owner_release(root, root / 'owner-release.json', True)
        if (exit_receipt['capture_seal_sha256'] != sha(root / 'capture-seal.json')
                or owner['native_exit_sha256'] != sha(root / 'native-exit.json')):
            raise ValueError('Closure hash join differs')
        events = seal['events'] + [exit_receipt['event'], owner['event'], saved['events'][0]]
        expected = ['capture_finished', 'encoders_closed', 'restoration_verified',
                    'native_exit', 'owner_released', 'saved_processing_started']
        if events != expected:
            raise ValueError('Saved processing preceded verified closure')
        write(output, {'events': events, 'diagnostic_fixture': True,
                       'fixture_frames': 60, 'failed_encoder_rejected': True,
                       'premature_release_rejected': True,
                       'capture_seal_sha256': sha(root / 'capture-seal.json'),
                       'native_exit_sha256': sha(root / 'native-exit.json'),
                       'owner_release_sha256': sha(root / 'owner-release.json'),
                       'saved_processing_receipt_sha256': sha(saved_path)})
        print(json.dumps({'case_id': entry['case_id'], 'events': events,
                          'diagnostic_fixture': True}))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--manifest', required=True, type=Path)
    parser.add_argument('--case', required=True)
    parser.add_argument('--kind', required=True, choices=(
        'complete_motion', 'incomplete_motion', 'missing_evidence', 'lifecycle'))
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    entry = next((x for x in read(args.manifest)['cases'] if x['case_id'] == args.case), None)
    if entry is None:
        raise ValueError('Unknown exact physical fixture case')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.kind == 'lifecycle':
        lifecycle(entry, args.output)
    else:
        motion(entry, args.kind, args.output)


if __name__ == '__main__':
    main()
