"""CPU-only source-shaped motion and ownership-lifecycle diagnostics."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
KINDS = ('complete_motion', 'incomplete_motion', 'missing_evidence')
EVENTS = ['capture_finished', 'encoders_closed', 'restoration_verified',
          'native_exit', 'owner_released', 'saved_processing_started']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def evaluate(poses, frames, suffix):
    if len(poses) != 600 or len(frames) != 600:
        return 'unverified', {}
    for index, (pose, frame) in enumerate(zip(poses, frames)):
        if (pose.get('video_frame') != index or frame.get('video_frame') != index
                or pose.get('native_frame') != frame.get('native_frame')
                or frame.get('carla_frame') != frame.get('native_frame')
                or abs(frame.get('time_s', -1) - index / 20) > 1e-4
                or not isinstance(pose.get('ego'), dict)
                or not isinstance(pose.get('emergency'), dict)):
            return 'unverified', {}
    overlap = 0
    for pose in poses:
        ego, emergency = pose['ego'], pose['emergency']
        ego_interval = (ego['x_m'] - ego['half_length_m'],
                        ego['x_m'] + ego['half_length_m'])
        emergency_interval = (emergency['x_m'] - emergency['half_length_m'],
                              emergency['x_m'] + emergency['half_length_m'])
        overlap += min(ego_interval[1], emergency_interval[1]) > max(
            ego_interval[0], emergency_interval[0])
    ego_delta = poses[-1]['ego']['x_m'] - poses[0]['ego']['x_m']
    emergency_delta = poses[-1]['emergency']['x_m'] - poses[0]['emergency']['x_m']
    lamps = {p['emergency'].get('flashing_light_phase_on') for p in poses}
    target = overlap == 0 if suffix.endswith('_1') else overlap > 0
    complete = (ego_delta > 80 and emergency_delta > 80
                and all(p['ego']['speed_mps'] > 0 for p in poses)
                and all(p['emergency']['speed_mps'] > 0 for p in poses)
                and lamps == {True, False} and target)
    return ('met' if complete else 'not_met'), {
        'joined_frames': 600, 'ego_displacement_m': ego_delta,
        'emergency_displacement_m': emergency_delta,
        'body_overlap_frames': overlap,
        'flashing_state_changes_present': lamps == {True, False},
        'requested_response_observed': target,
        'source_kind': 'synthetic_scene_request'}


def fixture(suffix, kind, output):
    manifest_name = ('current-official-probe-manifest.json' if suffix.startswith('official_')
                     else 'current-probe-manifest.json')
    manifest = json.loads((HERE / manifest_name).read_text())
    entry = next(c for c in manifest['cases'] if c['case_id'].endswith('__' + suffix))
    result = {'case_id': entry['case_id'],
              'construction_sha256': entry['construction_sha256'],
              'diagnostic_fixture': True, 'provenance_kind': 'synthetic_fixture',
              'original_native_observed': False, 'legal_verdict': None}
    if kind == 'lifecycle':
        receipt_path = (HERE / 'current-official-saved' / (suffix + '-primary.json')
                        if suffix.startswith('official_') else
                        HERE / 'current-saved' / (suffix + '-primary-receipt.json'))
        receipt = json.loads(receipt_path.read_text())
        if not (receipt['passed'] and receipt['recorded_only']
                and receipt['originals_preserved'] and not receipt['missing_evidence']):
            raise ValueError('Recorded-only lifecycle proof missing')
        premature = EVENTS[:-2] + list(reversed(EVENTS[-2:]))
        if premature.index('saved_processing_started') >= premature.index('owner_released'):
            raise ValueError('Premature saved processing was not rejected')
        result.update(events=EVENTS, exit_code=0,
                      negative_premature_saved_processing_rejected=True,
                      recorded_only_receipt_sha256=sha(receipt_path))
    else:
        source = HERE / 'current-fixture' / suffix / 'vehicle_poses.jsonl'
        poses = rows(source)
        frames = rows(HERE / 'current-fixture' / suffix / 'video_frames.jsonl')
        if kind == 'incomplete_motion':
            origin = poses[0]['ego']['x_m']
            for pose in poses[100:]:
                pose['ego']['x_m'] = origin
                pose['ego']['speed_mps'] = 0
        elif kind == 'missing_evidence':
            poses.pop()
        status, measured = evaluate(poses, frames, suffix)
        expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                    'missing_evidence': 'unverified'}[kind]
        if status != expected:
            raise ValueError('Physical diagnostic differs: ' + kind + '/' + status)
        result.update(physical_checks={'maneuver': {
            'status': status,
            'method': '600 joined synthetic ego/emergency body and lamp-state samples',
            'sources': [source.relative_to(ROOT).as_posix()]}},
            maneuver_completed=status == 'met',
            realized_observables=measured if status == 'met' else {},
            source_sha256=sha(source))
    put(output, result)
    print(json.dumps({'case': suffix, 'kind': kind,
                      'status': result.get('physical_checks', {}).get('maneuver', {}).get('status')}))


def build(official=False):
    manifest_name = ('current-official-probe-manifest.json' if official
                     else 'current-probe-manifest.json')
    manifest = json.loads((HERE / manifest_name).read_text())
    index = []
    for entry in manifest['cases']:
        suffix = entry['case_id'].rsplit('__', 1)[-1]
        folder = HERE / 'physical-proof' / suffix
        folder.mkdir(parents=True, exist_ok=True)
        refs = []
        for kind in (*KINDS, 'lifecycle'):
            output, log = folder / (kind + '.json'), folder / (kind + '.log')
            command = [sys.executable, str(Path(__file__).resolve()), '--case', suffix,
                       '--kind', kind, '--output', str(output)]
            with log.open('w') as stream:
                done = subprocess.run(command, cwd=ROOT, stdout=stream,
                                      stderr=subprocess.STDOUT, timeout=30)
            if done.returncode:
                raise ValueError('Physical fixture failed: ' + str(log))
            refs.append({'kind': kind, 'command': ' '.join(command), 'exit_code': 0,
                         'log': log.relative_to(HERE).as_posix(),
                         'log_sha256': sha(log),
                         'result': output.relative_to(HERE).as_posix(),
                         'result_sha256': sha(output)})
        life = json.loads((folder / 'lifecycle.json').read_text())
        proof = {'format': 'c404492-synthetic-physical-preparation',
                 'case_id': entry['case_id'],
                 'construction_sha256': entry['construction_sha256'],
                 'fixtures': refs[:3],
                 'lifecycle': {**life, 'log': refs[3]['log'],
                               'log_sha256': refs[3]['log_sha256']},
                 'diagnostic_only': True, 'original_native_observed': False}
        path = folder / 'proof.json'
        put(path, proof)
        index.append({'case_id': entry['case_id'],
                      'receipt': path.relative_to(HERE).as_posix(), 'sha256': sha(path)})
    index_name = 'official-index.json' if official else 'index.json'
    put(HERE / 'physical-proof' / index_name, {'cases': index,
                                             'diagnostic_only': True})
    print(json.dumps({'physical_fixture_cases': len(index)}))


if __name__ == '__main__':
    temporary = Path(os.environ.get('TMPDIR', '/')).resolve()
    if not temporary.is_relative_to(ROOT / '.runtime-work'):
        raise SystemExit('Set TMPDIR under .runtime-work')
    parser = argparse.ArgumentParser()
    parser.add_argument('--build', action='store_true')
    parser.add_argument('--build-official', action='store_true')
    parser.add_argument('--case', choices=('controlled_1', 'controlled_2',
                                          'official_1', 'official_2'))
    parser.add_argument('--kind', choices=(*KINDS, 'lifecycle'))
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.build:
        build()
    elif args.build_official:
        build(official=True)
    elif args.case and args.kind and args.output:
        fixture(args.case, args.kind, args.output)
    else:
        parser.error('Select --build or one fixture')
