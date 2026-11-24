"""CPU test physical motion outcomes and saved ownership ordering for 2(f)."""
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
    path.write_text(json.dumps(value, indent=2) + '\n')


def evaluate(poses, frames, requested_speed, stopped_referral=False):
    if len(poses) != 600 or len(frames) != 600:
        return 'unverified', {}
    for index, (pose, frame) in enumerate(zip(poses, frames)):
        if (pose.get('video_frame') != index or frame.get('video_frame') != index or
                pose.get('native_frame') != frame.get('native_frame') or
                abs(frame.get('time_s', -100) - index / 20) > 1e-4 or
                not isinstance(pose.get('ego'), dict) or
                not isinstance(pose.get('emergency'), dict)):
            return 'unverified', {}
    start = poses[0]
    mid = poses[120]
    end = poses[220]
    separation = lambda p: abs(p['ego']['x_m'] - p['emergency']['x_m'])
    after_ego = sum(p['ego']['speed_mps'] for p in poses[160:220]) / 60
    after_emergency = sum(p['emergency']['speed_mps'] for p in poses[160:220]) / 60
    lamps = {p['emergency'].get('special1_light_on') for p in poses}
    passed = next((i for i, p in enumerate(poses[120:], 120)
                   if p['emergency']['x_m'] + p['emergency']['half_length_m'] <
                   p['ego']['x_m'] - p['ego']['half_length_m']), None)
    right_edge_stop = (passed is not None and passed > 220 and
                       all(abs(p['ego']['y_m'] + 2.5) <= .15 and
                           p['ego']['speed_mps'] <= .15 for p in poses[120:passed]))
    continued_lane = all(abs(p['ego']['y_m'] + 1.75) <= .15 and
                         p['ego']['speed_mps'] >= 2.5 for p in poses[120:220])
    stopped_source = all(p['emergency']['speed_mps'] <= .15 for p in poses[220:300])
    right_edge_hold = all(abs(p['ego']['y_m'] + 2.5) <= .15 and
                          p['ego']['speed_mps'] <= .15 for p in poses[120:300])
    complete = (separation(poses[80]) < separation(start) and
                separation(end) < separation(mid) and after_emergency > .5 and
                abs(after_ego - requested_speed) <= .25 and lamps == {True, False} and
                (stopped_source and right_edge_hold and passed is None
                 if stopped_referral else
                 right_edge_stop if requested_speed == 0 else continued_lane))
    return ('met' if complete else 'not_met'), {
        'joined_frames': 600, 'initial_separation_m': separation(start),
        'subsequent_closing_m': separation(mid) - separation(end),
        'after_ego_speed_mps': after_ego,
        'after_emergency_speed_mps': after_emergency,
        'flashing_state_changes_present': lamps == {True, False},
        'right_edge_stop_until_passed': right_edge_stop,
        'stopped_source_observed': stopped_source,
        'right_edge_hold_observed': right_edge_hold,
        'emergency_pass_frame': passed,
        'source_kind': 'synthetic_scene_request'}


def fixture(suffix, kind, output):
    manifest = json.loads((HERE / 'current-execution-manifest.json').read_text())
    entry = next(c for c in manifest['cases'] if c['case_id'].endswith('__' + suffix))
    result = {'case_id': entry['case_id'],
              'construction_sha256': entry['construction_sha256'],
              'diagnostic_fixture': True, 'provenance_kind': 'synthetic_fixture',
              'original_native_observed': False, 'legal_verdict': None}
    if kind == 'lifecycle':
        receipt_path = HERE / 'current-public' / (suffix + '-primary-processing.json')
        receipt = json.loads(receipt_path.read_text())
        if not (receipt['passed'] and receipt['recorded_only'] and
                receipt['originals_preserved'] and not receipt['missing_evidence']):
            raise ValueError('Recorded-only saved lifecycle proof missing')
        premature = EVENTS[:-2] + list(reversed(EVENTS[-2:]))
        if premature.index('saved_processing_started') >= premature.index('owner_released'):
            raise ValueError('Premature saved processing not rejected')
        result.update(events=EVENTS, exit_code=0,
                      negative_premature_saved_processing_rejected=True,
                      recorded_only_receipt_sha256=sha(receipt_path))
    else:
        folder = HERE / 'current-fixture' / suffix
        path = folder / 'vehicle_poses.jsonl'
        poses = [json.loads(line) for line in path.read_text().splitlines()]
        frames = [json.loads(line) for line in
                  (folder / 'video_frames.jsonl').read_text().splitlines()]
        if kind == 'incomplete_motion':
            for row in poses[120:]:
                row['emergency']['speed_mps'] = 0.0
        elif kind == 'missing_evidence':
            poses.pop()
        requested = 3 if suffix == 'controlled_2' else 0
        status, measured = evaluate(poses, frames, requested,
                                    stopped_referral=suffix == 'stopped_referral')
        expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                    'missing_evidence': 'unverified'}[kind]
        if status != expected:
            raise ValueError('Physical diagnostic differs: ' + kind + '/' + status)
        result.update(physical_checks={'maneuver': {
            'status': status,
            'method': '600 joined synthetic ego/emergency samples, right-edge stop until passed or continued travel',
            'sources': [path.relative_to(ROOT).as_posix()]}},
            maneuver_completed=status == 'met',
            realized_observables=measured if status == 'met' else {},
            source_sha256=sha(path))
    put(output, result)
    print(json.dumps({'case': suffix, 'kind': kind,
                      'status': result.get('physical_checks', {}).get('maneuver', {}).get('status')}))


def build(only=None):
    manifest = json.loads((HERE / 'current-execution-manifest.json').read_text())
    index = []
    for entry in manifest['cases']:
        suffix = entry['case_id'].rsplit('__', 1)[-1]
        if only is not None and suffix != only:
            continue
        folder = HERE / 'physical-proof' / suffix
        refs = []
        for kind in (*KINDS, 'lifecycle'):
            output, log = folder / (kind + '.json'), folder / (kind + '.log')
            command = [sys.executable, str(Path(__file__).resolve()), '--case', suffix,
                       '--kind', kind, '--output', str(output)]
            folder.mkdir(parents=True, exist_ok=True)
            with log.open('w') as stream:
                done = subprocess.run(command, cwd=ROOT, stdout=stream,
                                      stderr=subprocess.STDOUT, timeout=30)
            if done.returncode:
                raise ValueError('Physical fixture failed: ' + str(log))
            refs.append({'kind': kind, 'command': ' '.join(command),
                         'exit_code': 0, 'log': log.relative_to(HERE).as_posix(),
                         'log_sha256': sha(log),
                         'result': output.relative_to(HERE).as_posix(),
                         'result_sha256': sha(output)})
        life = json.loads((folder / 'lifecycle.json').read_text())
        proof = {'format': 'c405647-2f-synthetic-physical-preparation',
                 'case_id': entry['case_id'],
                 'construction_sha256': entry['construction_sha256'],
                 'fixtures': refs[:3],
                 'lifecycle': {**life, 'log': refs[3]['log'],
                               'log_sha256': refs[3]['log_sha256']},
                 'diagnostic_only': True, 'original_native_observed': False}
        path = folder / 'proof.json'
        put(path, proof)
        index.append({'case_id': entry['case_id'],
                      'receipt': path.relative_to(HERE).as_posix(),
                      'sha256': sha(path)})
    put(HERE / 'physical-proof/index.json', {'cases': index,
                                             'diagnostic_only': True})
    print(json.dumps({'physical_fixture_cases': len(index)}))


if __name__ == '__main__':
    temporary = Path(os.environ.get('TMPDIR', '/')).resolve()
    if not temporary.is_relative_to(ROOT / '.runtime-work'):
        raise SystemExit('Set TMPDIR under .runtime-work')
    parser = argparse.ArgumentParser()
    parser.add_argument('--build', action='store_true')
    parser.add_argument('--case', choices=('controlled_1', 'controlled_2', 'official_approach', 'stopped_referral'))
    parser.add_argument('--kind', choices=(*KINDS, 'lifecycle'))
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.build:
        build(args.case)
    elif args.case and args.kind and args.output:
        fixture(args.case, args.kind, args.output)
    else:
        parser.error('Select --build or one fixture')
