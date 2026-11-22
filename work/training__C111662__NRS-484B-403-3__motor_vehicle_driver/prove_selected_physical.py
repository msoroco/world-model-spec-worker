"""Prove current selected synthetic motion outcomes and lifecycle on CPU."""
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
MANIFEST = HERE / 'selected-current-staging.json'
OUTPUT = HERE / 'selected-current-physical'
CASES = ('reference', 'contrast', 'divided_reference', 'divided_opening')
KINDS = ('complete_motion', 'incomplete_motion', 'missing_evidence')
EVENTS = ['capture_finished', 'encoders_closed', 'restoration_verified',
          'native_exit', 'owner_released', 'saved_processing_started']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def source(case):
    if case == 'reference':
        return HERE / 'directional-approach-experiment/raw.json'
    if case == 'contrast':
        return HERE / 'directional-approach-experiment/contrast-raw.json'
    return HERE / 'current-16-experiment' / case / 'primary/raw.json'


def classify(rows):
    if len(rows) != 800 or [r.get('frame') for r in rows] != list(range(800)):
        return {'status': 'unverified', 'reason': 'Missing synchronized frame evidence'}
    if any(r.get('video_frame') != r['frame'] or r.get('source_kind') != 'synthetic_fixture'
           for r in rows):
        return {'status': 'unverified', 'reason': 'Frame provenance or video join differs'}
    centers = [r['ego']['center_xyz_m'] for r in rows]
    headings = [r['ego']['heading_rad'] for r in rows]
    reversal = abs((headings[-1] - headings[0] + math.pi) % (2 * math.pi) - math.pi)
    westbound = max(p[0] for p in centers) - centers[-1][0]
    lane_change = centers[-1][1] - centers[0][1]
    status = 'met' if reversal > 2.5 and westbound > 5 and lane_change > 8 else 'not_met'
    return {'status': status, 'heading_reversal_rad': reversal,
            'westbound_after_turn_m': westbound, 'lateral_crossing_m': lane_change,
            'joined_frames': len(rows)}


def fixture(case, kind, output):
    entry = next(e for e in read(MANIFEST)['cases'] if e['case_id'].endswith('__' + case))
    base = {'case_id': entry['case_id'], 'construction_sha256': entry['construction_sha256'],
            'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True,
            'original_native_motion_verified': False, 'accepted': False,
            'legal_verdict_claimed': False}
    if kind == 'lifecycle':
        if EVENTS.index('owner_released') >= EVENTS.index('saved_processing_started'):
            raise ValueError('Saved processing preceded owner release')
        wrong = EVENTS.copy()
        wrong[-2:] = reversed(wrong[-2:])
        if wrong.index('owner_released') < wrong.index('saved_processing_started'):
            raise ValueError('Premature processing negative not rejected')
        value = {**base, 'events': EVENTS, 'exit_code': 0,
                 'negative_premature_processing_rejected': True,
                 'actual_owner_release_verified': False}
    else:
        path = source(case)
        raw = read(path)
        if raw.get('original_native_observed') is not False or raw.get('synthetic') is not True:
            raise ValueError('Motion source is not explicitly synthetic')
        rows = copy.deepcopy(raw['rows'])
        if kind == 'incomplete_motion':
            start = rows[0]['ego']['center_xyz_m']
            heading = rows[0]['ego']['heading_rad']
            for row in rows:
                row['ego']['center_xyz_m'] = start.copy()
                row['ego']['heading_rad'] = heading
        elif kind == 'missing_evidence':
            rows.pop()
        measurement = classify(rows)
        expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                    'missing_evidence': 'unverified'}[kind]
        if measurement['status'] != expected:
            raise ValueError(f'{case}/{kind}: {measurement["status"]} != {expected}')
        value = {**base, 'physical_checks': {'maneuver': {
            'status': measurement['status'],
            'method': '800-frame synthetic body, heading, reversal and video-join CPU classifier',
            'sources': [str(path.relative_to(ROOT))]}},
            'maneuver_completed': measurement['status'] == 'met',
            'realized_observables': measurement if expected == 'met' else {},
            'source_sha256': sha(path)}
    write(output, value)
    print(json.dumps({'case': case, 'kind': kind, 'status': value.get('physical_checks', {}).get('maneuver', {}).get('status'),
                      'synthetic': True}))


def build():
    manifest = read(MANIFEST)
    for case in CASES:
        entry = next(e for e in manifest['cases'] if e['case_id'].endswith('__' + case))
        refs = []
        for kind in (*KINDS, 'lifecycle'):
            target = OUTPUT / case / (kind + '.json')
            log = OUTPUT / case / (kind + '.log')
            command = [sys.executable, str(Path(__file__).resolve()), '--case', case,
                       '--kind', kind, '--output', str(target)]
            log.parent.mkdir(parents=True, exist_ok=True)
            with log.open('w') as stream:
                result = subprocess.run(command, cwd=ROOT, stdout=stream,
                                        stderr=subprocess.STDOUT, timeout=60)
            if result.returncode:
                raise ValueError('Physical proof failed: ' + str(log))
            refs.append({'kind': kind, 'command': ' '.join(command), 'exit_code': 0,
                         'log': str(log.relative_to(HERE)), 'log_sha256': sha(log),
                         'result': str(target.relative_to(HERE)), 'result_sha256': sha(target)})
        proof = {'format': 'c111662-selected-current-physical-cpu-v1',
                 'case_id': entry['case_id'], 'construction_sha256': entry['construction_sha256'],
                 'fixtures': refs[:3],
                 'lifecycle': {**read(OUTPUT / case / 'lifecycle.json'),
                               'log': refs[3]['log'], 'log_sha256': refs[3]['log_sha256']},
                 'original_native_and_pixels_verified': False}
        target = OUTPUT / case / 'proof.json'
        write(target, proof)
        entry['physical_preparation'] = {'receipt': str(target.relative_to(HERE)),
                                         'sha256': sha(target)}
    write(MANIFEST, manifest)
    stage = HERE / 'selected-current-proof/stage-evidence.json'
    evidence = read(stage)
    evidence['manifest_sha256'] = sha(MANIFEST)
    evidence['physical_receipts_rebound'] = True
    write(stage, evidence)
    print(json.dumps({'cases': len(CASES), 'manifest_sha256': sha(MANIFEST),
                      'scope': 'synthetic physical CPU proof only'}))


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
        parser.error('Select --build or exact fixture arguments')
