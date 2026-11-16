"""Exercise U-turn motion and ownership ordering on clearly synthetic CPU sources."""
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
CASES = ('reference', 'contrast', 'divided_reference', 'divided_opening')
KINDS = ('complete_motion', 'incomplete_motion', 'missing_evidence')
LIFECYCLE = ['capture_finished', 'encoders_closed', 'restoration_verified',
             'native_exit', 'owner_released', 'saved_processing_started']


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def classify(rows):
    if len(rows) != 800 or [r.get('frame') for r in rows] != list(range(800)):
        return {'status': 'unverified', 'reason': 'Missing synchronized frame evidence'}
    if any(r.get('video_frame') != r['frame'] or r.get('source_kind') != 'synthetic_fixture'
           for r in rows):
        return {'status': 'unverified', 'reason': 'Frame provenance or video join differs'}
    centers = [r['ego']['center_xyz_m'] for r in rows]
    headings = [r['ego']['heading_rad'] for r in rows]
    reversal = abs((headings[-1] - headings[0] + math.pi) % (2 * math.pi) - math.pi)
    east_extent = max(p[0] for p in centers)
    westbound = east_extent - centers[-1][0]
    lane_change = centers[-1][1] - centers[0][1]
    status = 'met' if reversal > 2.5 and westbound > 5 and lane_change > 8 else 'not_met'
    return {'status': status, 'heading_reversal_rad': reversal,
            'westbound_after_turn_m': westbound, 'lateral_crossing_m': lane_change,
            'joined_frames': len(rows)}


def fixture(case, kind, output):
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    entry = next(e for e in manifest['cases'] if e['case_id'].endswith('__' + case))
    base = {'case_id': entry['case_id'], 'construction_sha256': entry['construction_sha256'],
            'cpu_fixture_mock': True, 'mock_input_provenance': 'synthetic_cpu_fixture',
            'original_native_motion_verified': False, 'accepted': False,
            'legal_verdict_claimed': False}
    if kind == 'lifecycle':
        if LIFECYCLE.index('owner_released') >= LIFECYCLE.index('saved_processing_started'):
            raise ValueError('Saved processing started before owner release')
        wrong = LIFECYCLE.copy()
        wrong[-2:] = reversed(wrong[-2:])
        if wrong.index('owner_released') < wrong.index('saved_processing_started'):
            raise ValueError('Lifecycle negative did not fail')
        value = {**base, 'events': LIFECYCLE, 'exit_code': 0,
                 'negative_premature_processing_rejected': True,
                 'actual_owner_release_verified': False}
    else:
        source = HERE / 'update043-current-fixtures' / case / 'fallback2' / 'raw.json'
        raw = json.loads(source.read_text())
        if raw.get('original_native_observed') is not False or raw.get('synthetic') is not True:
            raise ValueError('CPU mock source must remain synthetic')
        rows = copy.deepcopy(raw['rows'])
        if kind == 'incomplete_motion':
            start = rows[0]['ego']['center_xyz_m']
            heading = rows[0]['ego']['heading_rad']
            for row in rows:
                row['ego']['center_xyz_m'] = start.copy()
                row['ego']['heading_rad'] = heading
        elif kind == 'missing_evidence':
            rows.pop()
        measure = classify(rows)
        expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                    'missing_evidence': 'unverified'}[kind]
        if measure['status'] != expected:
            raise ValueError(f'{kind} measured {measure["status"]}, expected {expected}')
        value = {**base, 'physical_checks': {'maneuver': {
                     'status': measure['status'],
                     'method': '800-frame body, heading, reversal and video-join CPU classifier',
                     'sources': [str(source.relative_to(ROOT))]}},
                 'maneuver_completed': measure['status'] == 'met',
                 'realized_observables': measure if measure['status'] == 'met' else {},
                 'provenance_kind': 'native', 'mock_native_branch_only': True,
                 'source_sha256': sha(source)}
    write(output, value)
    print(json.dumps({'case': case, 'kind': kind, 'cpu_fixture_mock': True,
                      'status': value.get('physical_checks', {}).get('maneuver', {}).get('status')}))


def build():
    manifest_path = HERE / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    for case in CASES:
        entry = next(e for e in manifest['cases'] if e['case_id'].endswith('__' + case))
        folder = HERE / 'update044-physical' / case
        refs = []
        for kind in (*KINDS, 'lifecycle'):
            output = folder / f'{kind}.json'
            log = folder / f'{kind}.log'
            command = [sys.executable, str(Path(__file__).resolve()), '--case', case,
                       '--kind', kind, '--output', str(output)]
            folder.mkdir(parents=True, exist_ok=True)
            with log.open('w') as stream:
                result = subprocess.run(command, cwd=ROOT, stdout=stream,
                                        stderr=subprocess.STDOUT, timeout=60)
            if result.returncode:
                raise ValueError(f'Physical CPU fixture failed: {log}')
            ref = {'kind': kind, 'command': ' '.join(command), 'exit_code': 0,
                   'log': str(log.relative_to(HERE)), 'log_sha256': sha(log),
                   'result': str(output.relative_to(HERE)), 'result_sha256': sha(output)}
            refs.append(ref)
        proof = {'format': 'c111662-physical-cpu-v1', 'case_id': entry['case_id'],
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
    parser.add_argument('--case', choices=CASES)
    parser.add_argument('--kind', choices=(*KINDS, 'lifecycle'))
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.build:
        build()
    elif args.case and args.kind and args.output:
        fixture(args.case, args.kind, args.output)
    else:
        parser.error('Select --build or an exact --case/--kind/--output fixture')
