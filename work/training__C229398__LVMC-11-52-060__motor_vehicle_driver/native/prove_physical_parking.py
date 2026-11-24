"""Exercise parked-interval physical outcome branches with synthetic sources."""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent.parent
ROOT = PACKAGE.parents[1]
MANIFEST = PACKAGE / 'execution-manifest.json'
SUFFIXES = ('below_15_ft', 'at_15_ft', 'above_15_ft')
KINDS = ('complete_motion', 'incomplete_motion', 'missing_evidence')
EVENTS = ['capture_finished', 'encoders_closed', 'restoration_verified',
          'native_exit', 'owner_released', 'saved_processing_started']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + '\n')


def source(suffix):
    return PACKAGE / 'diagnostic-fixture' / suffix / 'sources'


def classify(trace, frames, raw, reviewed):
    if (len(trace) != 600 or len(frames) != 600 or len(raw) != 600 or
            reviewed.get('reviewed') is not True or
            reviewed.get('source_kind') != 'synthetic_native_sample'):
        return {'status': 'unverified', 'reason': 'Incomplete synthetic source inventory'}
    for index, (pose, image, actors) in enumerate(zip(trace, frames, raw)):
        if (pose.get('frame') != 1000 + index or
                image.get('native_frame') != pose['frame'] or
                image.get('video_frame') != index or
                actors.get('frame') != index or
                actors.get('native_frame') != pose['frame'] or
                abs(image.get('time_s', -1) - pose.get('time_s', -2)) > 1e-6 or
                pose.get('speed_source_kind') != 'synthetic_native_sample'):
            return {'status': 'unverified', 'reason': 'Frame join or source provenance differs'}
    parked = all(row.get('speed_mps') == 0 and row['control'].get('hand_brake') is True
                 for row in trace)
    return {'status': 'met' if parked else 'not_met', 'joined_frames': len(trace),
            'duration_s': trace[-1]['time_s'], 'stationary_with_brake': parked}


def fixture(suffix, kind, output):
    manifest = json.loads(MANIFEST.read_text())
    entry = next(item for item in manifest['cases']
                 if item['case_id'].endswith('__' + suffix))
    folder = source(suffix)
    result = {'case_id': entry['case_id'], 'construction_sha256': entry['construction_sha256'],
              'diagnostic_fixture': True, 'original_native_observed': False,
              'physical_acceptance_claimed': False, 'legal_verdict_claimed': False}
    if kind == 'lifecycle':
        wrong = EVENTS[:-2] + list(reversed(EVENTS[-2:]))
        assert EVENTS.index('owner_released') < EVENTS.index('saved_processing_started')
        assert wrong.index('saved_processing_started') < wrong.index('owner_released')
        result.update({'events': EVENTS, 'exit_code': 0,
                       'negative_premature_saved_processing_rejected': True,
                       'actual_native_owner_released': False})
    else:
        trace_path = folder / 'trace.jsonl'
        frames_path = folder / 'video_frames.jsonl'
        raw_path = folder / 'native-raw-actors.jsonl'
        curb_path = folder / 'reviewed-curb.json'
        trace = [json.loads(line) for line in trace_path.read_text().splitlines()]
        frames = [json.loads(line) for line in frames_path.read_text().splitlines()]
        raw = [json.loads(line) for line in raw_path.read_text().splitlines()]
        reviewed = json.loads(curb_path.read_text())
        if kind == 'incomplete_motion':
            for row in trace[-100:]:
                row['speed_mps'] = 2.0
                row['control']['hand_brake'] = False
        elif kind == 'missing_evidence':
            frames.pop()
        observed = classify(trace, frames, raw, reviewed)
        expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                    'missing_evidence': 'unverified'}[kind]
        if observed['status'] != expected:
            raise ValueError('Unexpected synthetic parking classification: ' + kind)
        result.update({'physical_checks': {'maneuver': {
                           'status': observed['status'],
                           'method': '600-frame synthetic stationary interval, brake and camera join classifier',
                           'sources': [str(path.relative_to(ROOT)) for path in
                                       (trace_path, frames_path, raw_path, curb_path)]}},
                       'maneuver_completed': expected == 'met',
                       'realized_observables': observed if expected == 'met' else {},
                       'provenance_kind': 'synthetic_fixture',
                       'source_sha256': {path.name: sha(path) for path in
                                         (trace_path, frames_path, raw_path, curb_path)},
                       'mutation': kind if kind != 'complete_motion' else None})
    write(output, result)
    print(json.dumps({'case_id': entry['case_id'], 'kind': kind,
                      'status': result.get('physical_checks', {}).get('maneuver', {}).get('status')}))


def build():
    manifest = json.loads(MANIFEST.read_text())
    summary = []
    for suffix in SUFFIXES:
        entry = next(item for item in manifest['cases']
                     if item['case_id'].endswith('__' + suffix))
        folder = PACKAGE / 'diagnostic-fixture' / suffix / 'physical-proof'
        refs = []
        for kind in (*KINDS, 'lifecycle'):
            output = folder / (kind + '.json')
            log = folder / (kind + '.log')
            command = [sys.executable, str(Path(__file__).resolve()), '--case', suffix,
                       '--kind', kind, '--output', str(output)]
            folder.mkdir(parents=True, exist_ok=True)
            with log.open('w') as stream:
                completed = subprocess.run(command, cwd=ROOT, stdout=stream,
                                           stderr=subprocess.STDOUT, timeout=60)
            if completed.returncode:
                raise ValueError('Physical CPU fixture failed: ' + str(log))
            refs.append({'kind': kind, 'command': ' '.join(command), 'exit_code': 0,
                         'log': str(log.relative_to(PACKAGE)), 'log_sha256': sha(log),
                         'result': str(output.relative_to(PACKAGE)),
                         'result_sha256': sha(output)})
        lifecycle = json.loads((folder / 'lifecycle.json').read_text())
        proof = {'format': 'c229398-synthetic-physical-preparation-v1',
                 'case_id': entry['case_id'],
                 'construction_sha256': entry['construction_sha256'],
                 'fixtures': refs[:3],
                 'lifecycle': {**lifecycle, 'log': refs[3]['log'],
                               'log_sha256': refs[3]['log_sha256']},
                 'original_native_observed': False,
                 'physical_acceptance_claimed': False}
        proof_path = folder / 'proof.json'
        write(proof_path, proof)
        summary.append({'case_id': entry['case_id'],
                        'receipt': str(proof_path.relative_to(PACKAGE)),
                        'sha256': sha(proof_path)})
    write(PACKAGE / 'diagnostic-fixture/physical-proof-index.json',
          {'format': 'c229398-synthetic-physical-index-v1',
           'manifest_sha256': sha(MANIFEST), 'cases': summary,
           'diagnostic_only': True, 'original_native_observed': False})
    print(json.dumps({'physical_fixture_cases': len(summary)}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--build', action='store_true')
    parser.add_argument('--case', choices=SUFFIXES)
    parser.add_argument('--kind', choices=(*KINDS, 'lifecycle'))
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.build:
        build()
    elif args.case and args.kind and args.output:
        fixture(args.case, args.kind, args.output)
    else:
        parser.error('Select --build or one exact fixture')
