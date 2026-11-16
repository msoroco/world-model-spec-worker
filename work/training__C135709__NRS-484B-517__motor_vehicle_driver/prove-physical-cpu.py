"""Exercise stand motion outcomes and Native closure on explicit CPU mocks."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
sys.path.insert(0, str(ROOT/'native'))
sys.path.insert(0, str(REPO/'runtime/pipeline/scenario_pipeline'))
from finalize_selected import assess_physical_stand
from worker_exchange.saved_processing import (
    record_native_exit, acknowledge_owner_release, _closure)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2)+'\n')


def fixture(case, kind, output):
    spec_path = ROOT/'selected-diagnostics'/case/'primary.json'
    spec = json.loads(spec_path.read_text())['files']
    cfg = json.loads(next(item['content'] for item in json.loads(
        (ROOT/'selected-all'/case/'primary/construction.json').read_text())['files']
        if item['path'] == 'config.json'))
    base = {'case_id': cfg['case_id'], 'candidate_id': 'primary',
        'construction_sha256': sha(ROOT/'selected-all'/case/'primary/construction.json'),
        'cpu_fixture_mock': True, 'original_native_motion_verified': False,
        'actual_owner_release_verified': False, 'accepted': False,
        'legal_verdict_claimed': False}
    if kind == 'lifecycle':
        construction = ROOT/'selected-all'/case/'primary/construction.json'
        with tempfile.TemporaryDirectory(dir=REPO/'.runtime-work',
                                         prefix='c135709-lifecycle-') as temporary:
            attempt = Path(temporary)
            (attempt/'construction.json').write_bytes(construction.read_bytes())
            (attempt/'runner.py').write_text(next(item['content'] for item in
                json.loads(construction.read_text())['files']
                if item['path'] == 'runner.py'))
            seal = {'events': ['capture_finished', 'encoders_closed',
                               'restoration_verified'],
                'native_revision': {'construction_sha256': sha(attempt/'construction.json'),
                                    'runner_sha256': sha(attempt/'runner.py')},
                'sources': {'construction.json': sha(attempt/'construction.json'),
                            'runner.py': sha(attempt/'runner.py')}}
            write(attempt/'capture-seal.json', seal)
            exit_record = record_native_exit(attempt)
            owner_path = attempt/'owner-release.json'
            owner = acknowledge_owner_release(attempt, owner_path, True)
            _closure(attempt, owner_path, 'native', False)
            wrong = copy.deepcopy(seal)
            wrong['events'] = ['capture_finished', 'restoration_verified',
                               'encoders_closed']
            write(attempt/'capture-seal.json', wrong)
            try:
                _closure(attempt, owner_path, 'native', False)
            except ValueError:
                negative_rejected = True
            else:
                raise AssertionError('Premature Native closure was accepted')
        value = {**base, 'events': ['capture_finished', 'encoders_closed',
            'restoration_verified', 'native_exit', 'owner_released',
            'saved_processing_started'], 'exit_code': 0,
            'negative_premature_processing_rejected': negative_rejected,
            'runtime_native_exit_event': exit_record['event'],
            'runtime_owner_release_event': owner['event']}
    else:
        actors = [json.loads(s) for s in spec['native-raw-actors.jsonl'].splitlines()]
        frames = [json.loads(s) for s in spec['video_frames.jsonl'].splitlines()]
        reviews = [json.loads(s) for s in spec['stand-review.jsonl'].splitlines()]
        for actor, review in zip(actors, reviews):
            actor['source_kind'] = 'original_native'
            actor['speed_source'] = 'original_native'
            review['review_provenance'] = 'human_frame_review'
        if kind == 'incomplete_motion':
            actors[-1]['ego']['speed_mps'] = 2.0
        elif kind == 'missing_evidence':
            reviews.pop()
        sources = {name: hashlib.sha256(spec[name].encode()).hexdigest() for name in
            ('native-raw-actors.jsonl', 'video_frames.jsonl',
             'stand-review.jsonl', 'native-map-readback.json')}
        physical = assess_physical_stand(actors, frames, reviews, cfg, sources)
        expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                    'missing_evidence': 'unverified'}[kind]
        if physical['status'] != expected:
            raise ValueError(kind+': '+physical['status']+' instead of '+expected)
        value = {**base, 'physical_checks': {'maneuver': physical},
            'maneuver_completed': expected == 'met',
            'realized_observables': physical['details'] if expected == 'met' else {},
            'provenance_kind': 'native', 'mock_native_branch_only': True,
            'mock_source_spec': spec_path.relative_to(REPO).as_posix(),
            'mock_source_spec_sha256': sha(spec_path)}
    write(output, value)
    print(json.dumps({'case': case, 'kind': kind,
                      'cpu_fixture_mock': True,
                      'status': value.get('physical_checks', {}).get('maneuver', {}).get('status')}))


def build():
    manifest = json.loads((ROOT/'execution-manifest-draft.json').read_text())
    for case in ('reference', 'contrast'):
        entry = next(item for item in manifest['cases']
                     if item['case_id'].endswith('__'+case))
        folder = ROOT/'update052-physical'/case
        rows = []
        for kind in ('complete_motion', 'incomplete_motion',
                     'missing_evidence', 'lifecycle'):
            output = folder/(kind+'.json')
            log = folder/(kind+'.log')
            command = [sys.executable, str(Path(__file__).resolve()), '--case',
                       case, '--kind', kind, '--output', str(output)]
            folder.mkdir(parents=True, exist_ok=True)
            with log.open('w') as stream:
                result = subprocess.run(command, cwd=REPO, stdout=stream,
                                        stderr=subprocess.STDOUT, timeout=60)
            if result.returncode:
                raise ValueError('Physical CPU mock failed; inspect '+str(log))
            rows.append({'kind': kind, 'command': ' '.join(command),
                         'exit_code': 0, 'log': log.relative_to(ROOT).as_posix(),
                         'log_sha256': sha(log),
                         'result': output.relative_to(ROOT).as_posix(),
                         'result_sha256': sha(output)})
        proof = {'format': 'c135709-physical-cpu-mock-v1',
            'case_id': entry['case_id'],
            'construction_sha256': entry['construction_sha256'],
            'cpu_fixture_mock': True, 'fixtures': rows[:3],
            'lifecycle': {**json.loads((folder/'lifecycle.json').read_text()),
                          'log': rows[3]['log'],
                          'log_sha256': rows[3]['log_sha256']},
            'original_native_and_pixels_verified': False}
        write(folder/'proof.json', proof)
    print(json.dumps({'cases': 2, 'fixture_branches': 6,
                      'lifecycle_branches': 2, 'cpu_fixture_mock': True}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--build', action='store_true')
    parser.add_argument('--case', choices=('reference', 'contrast'))
    parser.add_argument('--kind', choices=('complete_motion', 'incomplete_motion',
                                          'missing_evidence', 'lifecycle'))
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.build:
        build()
    elif args.case and args.kind and args.output:
        fixture(args.case, args.kind, args.output)
    else:
        parser.error('Supply --build or --case/--kind/--output')
