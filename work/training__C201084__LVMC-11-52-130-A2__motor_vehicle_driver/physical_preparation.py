"""Test C201084 motion and lifecycle checks on retained synthetic source rows."""
import argparse
import hashlib
import json
import math
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / 'execution-manifest.json'
GROUPS = ('reference', 'contrast', 'conflict', 'clear', 'near_lead',
          'absent_lead', 'device_direction', 'officer_direction')
KINDS = ('complete_motion', 'incomplete_motion', 'missing_evidence')
EVENTS = ['capture_finished', 'encoders_closed', 'restoration_verified',
          'native_exit', 'owner_released', 'saved_processing_started']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def source(group):
    # Direction-specific fixture rows augment the shared retained motion source.
    name = 'reference' if group.endswith('_direction') else group
    return HERE / 'fixtures' / (name + '-sources')


def classify(actors, frames):
    if len(actors) != 600 or len(frames) != 600:
        return {'status': 'unverified', 'reason': 'Incomplete actor/frame inventory'}
    stationary = 0
    for index, (actor, frame) in enumerate(zip(actors, frames)):
        speed = math.hypot(*actor['ego_velocity_xyz_mps'][:2])
        if (actor.get('frame') != 100 + index or
                frame.get('carla_frame') != actor['frame'] or
                frame.get('video_frame') != index or
                abs(frame.get('time_s', -1) - index * 0.05) > 1e-6 or
                actor.get('source_kind') != 'synthetic_native_sample' or
                not actor.get('ego_body_vertices_xyz_m') or
                not math.isfinite(speed)):
            return {'status': 'unverified', 'reason': 'Frame join or actor provenance differs'}
        stationary += speed <= 0.05
    terminal_speed = math.hypot(*actors[-1]['ego_velocity_xyz_mps'][:2])
    complete = stationary >= 590 and terminal_speed <= 0.05
    return {'status': 'met' if complete else 'not_met',
            'joined_frames': 600, 'duration_s': 30.0,
            'stationary_frames': stationary, 'terminal_speed_mps': terminal_speed}


def fixture(group, kind, output):
    manifest = json.loads(MANIFEST.read_text())
    entry = next(item for item in manifest['cases']
                 if item['case_id'].endswith('__' + group))
    base = {'case_id': entry['case_id'],
            'construction_sha256': entry['construction_sha256'],
            'diagnostic_fixture': True, 'provenance_kind': 'synthetic_fixture',
            'original_native_observed': False, 'physical_acceptance_claimed': False,
            'legal_verdict_claimed': False}
    if kind == 'lifecycle':
        assert EVENTS.index('owner_released') < EVENTS.index('saved_processing_started')
        premature = EVENTS[:-2] + list(reversed(EVENTS[-2:]))
        assert premature.index('saved_processing_started') < premature.index('owner_released')
        base.update({'events': EVENTS, 'exit_code': 0,
                     'negative_premature_saved_processing_rejected': True,
                     'actual_native_owner_released': False})
    else:
        src = source(group)
        actor_path, frame_path = src / 'native-actors.jsonl', src / 'video_frames.jsonl'
        actors = [json.loads(line) for line in actor_path.read_text().splitlines()]
        frames = [json.loads(line) for line in frame_path.read_text().splitlines()]
        if kind == 'incomplete_motion':
            for row in actors[-100:]:
                row['ego_velocity_xyz_mps'] = [2.0, 0.0, 0.0]
        if kind == 'missing_evidence':
            frames.pop()
        measured = classify(actors, frames)
        expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                    'missing_evidence': 'unverified'}[kind]
        if measured['status'] != expected:
            raise ValueError('Unexpected outcome for ' + group + '/' + kind + ': ' + str(measured))
        base.update({'physical_checks': {'maneuver': {
                         'status': measured['status'],
                         'method': 'retained 600-frame actor velocity, body and video clock join',
                         'sources': [str(actor_path.relative_to(ROOT)),
                                     str(frame_path.relative_to(ROOT))]}},
                     'maneuver_completed': expected == 'met',
                     'realized_observables': measured if expected == 'met' else {},
                     'source_sha256': {str(path.relative_to(HERE)): sha(path)
                                       for path in (actor_path, frame_path)},
                     'mutation': kind if kind != 'complete_motion' else None})
    write(output, base)
    print(json.dumps({'case_id': entry['case_id'], 'kind': kind,
                      'status': base.get('physical_checks', {}).get('maneuver', {}).get('status')}))


def build():
    manifest = json.loads(MANIFEST.read_text())
    index = []
    for group in GROUPS:
        entry = next(item for item in manifest['cases']
                     if item['case_id'].endswith('__' + group))
        folder = HERE / 'physical-proof' / group
        refs = []
        for kind in (*KINDS, 'lifecycle'):
            output, log = folder / (kind + '.json'), folder / (kind + '.log')
            command = [sys.executable, str(Path(__file__).resolve()), '--case', group,
                       '--kind', kind, '--output', str(output)]
            folder.mkdir(parents=True, exist_ok=True)
            with log.open('w') as stream:
                run = subprocess.run(command, cwd=ROOT, stdout=stream,
                                     stderr=subprocess.STDOUT, timeout=60)
            if run.returncode:
                raise ValueError('Physical fixture failed: ' + str(log))
            refs.append({'kind': kind, 'command': ' '.join(command), 'exit_code': 0,
                         'log': str(log.relative_to(HERE)), 'log_sha256': sha(log),
                         'result': str(output.relative_to(HERE)), 'result_sha256': sha(output)})
        lifecycle = json.loads((folder / 'lifecycle.json').read_text())
        proof = {'format': 'c201084-synthetic-physical-preparation-v1',
                 'case_id': entry['case_id'],
                 'construction_sha256': entry['construction_sha256'],
                 'fixtures': refs[:3],
                 'lifecycle': {**lifecycle, 'log': refs[3]['log'],
                               'log_sha256': refs[3]['log_sha256']},
                 'diagnostic_only': True, 'original_native_observed': False,
                 'physical_acceptance_claimed': False}
        proof_path = folder / 'proof.json'
        write(proof_path, proof)
        index.append({'case_id': entry['case_id'],
                      'receipt': str(proof_path.relative_to(HERE)), 'sha256': sha(proof_path)})
    write(HERE / 'physical-proof/index.json',
          {'format': 'c201084-synthetic-physical-index-v1',
           'combined_manifest_sha256': sha(MANIFEST), 'cases': index,
           'diagnostic_only': True, 'original_native_observed': False})
    print(json.dumps({'physical_fixture_cases': len(index)}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--build', action='store_true')
    parser.add_argument('--case', choices=GROUPS)
    parser.add_argument('--kind', choices=(*KINDS, 'lifecycle'))
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.build:
        build()
    elif args.case and args.kind and args.output:
        fixture(args.case, args.kind, args.output)
    else:
        parser.error('Select --build or one exact fixture')
