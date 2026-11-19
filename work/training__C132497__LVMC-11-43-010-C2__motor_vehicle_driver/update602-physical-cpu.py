"""Exercise roundabout physical outcome branches on labeled synthetic rows."""
import argparse
import copy
import hashlib
import json
import math
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CASES = ('reference', 'contrast')
KINDS = ('complete_motion', 'incomplete_motion', 'missing_evidence')
LIFECYCLE = ['capture_finished', 'encoders_closed', 'restoration_verified',
             'native_exit', 'owner_released', 'saved_processing_started']


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n')


def classify(actors, frames):
    if len(actors) != 240 or len(frames) != 240:
        return {'status': 'unverified', 'reason': 'Missing retained actor or camera-frame evidence'}
    if any(actor.get('frame') != i or frame.get('video_frame') != i or
           actor.get('native_frame') != frame.get('native_frame') or
           abs(actor.get('time_s', -1) - frame.get('time_s', -2)) > 1e-6 or
           actor.get('source_kind') != 'synthetic_native_sample' or
           frame.get('synthetic_frame_only') is not True
           for i, (actor, frame) in enumerate(zip(actors, frames))):
        return {'status': 'unverified', 'reason': 'Frame join or diagnostic provenance differs'}
    centers = [row['ego']['center_native_xyz_m'] for row in actors]
    distance = sum(math.dist(a[:2], b[:2]) for a, b in zip(centers, centers[1:]))
    roads = [row['observed_road_id'] for row in actors]
    phases = [row['requested_phase'] for row in actors]
    ordered = (roads[0] == 20 and 21 in roads and roads[-1] == 22 and
               phases[0] == 'entry' and 'circulation' in phases and phases[-1] == 'exit')
    result = {'status': 'met' if ordered and distance > 5 and centers[-1][0] - centers[0][0] > 5 else 'not_met',
              'path_length_m': distance, 'road_sequence': [roads[0], 21 if 21 in roads else None, roads[-1]],
              'exit_lane_id': actors[-1]['observed_lane_id'], 'joined_frames': len(actors)}
    return result


def fixture(case, kind, output, manifest_path):
    manifest = json.loads(manifest_path.read_text())
    entry = next(x for x in manifest['cases'] if x['case_id'].endswith('__' + case))
    source = HERE / 'update048-physical-sources' / case
    base = {'case_id': entry['case_id'], 'construction_sha256': entry['construction_sha256'],
            'cpu_fixture_mock': True, 'mock_input_provenance': 'synthetic_native_sample',
            'original_native_motion_verified': False, 'accepted': False,
            'legal_verdict_claimed': False}
    if kind == 'lifecycle':
        if LIFECYCLE.index('owner_released') >= LIFECYCLE.index('saved_processing_started'):
            raise ValueError('Premature saved processing accepted')
        wrong = LIFECYCLE.copy()
        wrong[-2:] = reversed(wrong[-2:])
        if wrong.index('owner_released') < wrong.index('saved_processing_started'):
            raise ValueError('Lifecycle negative did not fail')
        value = {**base, 'events': LIFECYCLE, 'exit_code': 0,
                 'negative_premature_processing_rejected': True,
                 'actual_owner_release_verified': False}
    else:
        actors_path = source / 'native-raw-actors.jsonl'
        frames_path = source / 'video_frames.jsonl'
        actors = read_rows(actors_path)
        frames = read_rows(frames_path)
        if kind == 'incomplete_motion':
            actors = copy.deepcopy(actors)
            first = actors[0]['ego']['center_native_xyz_m']
            for row in actors:
                row['ego']['center_native_xyz_m'] = first.copy()
        elif kind == 'missing_evidence':
            actors.pop()
        measured = classify(actors, frames)
        expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                    'missing_evidence': 'unverified'}[kind]
        if measured['status'] != expected:
            raise ValueError(f'{kind}: {measured["status"]} instead of {expected}')
        value = {**base, 'physical_checks': {'maneuver': {
                     'status': measured['status'],
                     'method': '240-frame retained body, road sequence, path distance and video-join CPU classifier',
                     'sources': [str(actors_path.relative_to(ROOT)), str(frames_path.relative_to(ROOT))]}},
                 'maneuver_completed': measured['status'] == 'met',
                 'realized_observables': measured if measured['status'] == 'met' else {},
                 'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True, 'mock_native_branch_only': True,
                 'source_sha256': {actors_path.name: sha(actors_path), frames_path.name: sha(frames_path)}}
    write(output, value)
    print(json.dumps({'case': case, 'kind': kind, 'cpu_fixture_mock': True,
                      'status': value.get('physical_checks', {}).get('maneuver', {}).get('status')}))


def build(manifest_path):
    manifest = json.loads(manifest_path.read_text())
    for case in CASES:
        entry = next(e for e in manifest['cases'] if e['case_id'].endswith('__' + case))
        folder = HERE / 'update602-physical' / case
        refs = []
        for kind in (*KINDS, 'lifecycle'):
            output = folder / f'{kind}.json'
            log = folder / f'{kind}.log'
            command = [sys.executable, str(Path(__file__).resolve()), '--case', case,
                       '--kind', kind, '--output', str(output), '--manifest', str(manifest_path)]
            folder.mkdir(parents=True, exist_ok=True)
            with log.open('w') as stream:
                result = subprocess.run(command, cwd=ROOT, stdout=stream,
                                        stderr=subprocess.STDOUT, timeout=60)
            if result.returncode:
                raise ValueError(f'Physical CPU fixture failed: {log}')
            refs.append({'kind': kind, 'command': ' '.join(command), 'exit_code': 0,
                         'log': str(log.relative_to(HERE)), 'log_sha256': sha(log),
                         'result': str(output.relative_to(HERE)), 'result_sha256': sha(output)})
        proof = {'format': 'c132497-physical-cpu-v1', 'case_id': entry['case_id'],
                 'construction_sha256': entry['construction_sha256'],
                 'cpu_fixture_mock': True, 'fixtures': refs[:3],
                 'lifecycle': {**json.loads((folder / 'lifecycle.json').read_text()),
                               'log': refs[3]['log'], 'log_sha256': refs[3]['log_sha256']},
                 'original_native_and_pixels_verified': False}
        proof_path = folder / 'proof.json'
        write(proof_path, proof)
        entry['physical_preparation'] = {'receipt': str(proof_path.relative_to(HERE)),
                                         'sha256': sha(proof_path)}
    write(manifest_path, manifest)
    print(json.dumps({'cases': len(CASES), 'cpu_fixture_mock': True}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--build', action='store_true')
    parser.add_argument('--manifest', type=Path, default=HERE / 'update048-execution-manifest.json')
    parser.add_argument('--case', choices=CASES)
    parser.add_argument('--kind', choices=(*KINDS, 'lifecycle'))
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.build:
        build(args.manifest)
    elif args.case and args.kind and args.output:
        fixture(args.case, args.kind, args.output, args.manifest)
    else:
        parser.error('Select --build or an exact --case/--kind/--output fixture')
