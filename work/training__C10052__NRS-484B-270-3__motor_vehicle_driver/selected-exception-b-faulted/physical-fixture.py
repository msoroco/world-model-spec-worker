"""Synthetic exception B physical outcome and lifecycle fixtures."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
RESPONSE = HERE.name.removeprefix('selected-exception-b-')
CASE = ROOT.name + '__exception_b_' + RESPONSE
SOURCE = HERE / 'source/exception_b_native_samples.jsonl'
EVENTS = ['capture_finished', 'encoders_closed', 'restoration_verified',
          'native_exit', 'owner_released', 'saved_processing_started']
KINDS = ('complete_motion', 'incomplete_motion', 'missing_evidence')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def overlap(body):
    xs = [point[0] for point in body]
    ys = [point[1] for point in body]
    return max(0, min(max(xs), 20) - max(min(xs), -15)) * max(
        0, min(max(ys), -3) - max(min(ys), -5))


def classify(rows):
    if len(rows) != 600 or len({row.get('native_frame') for row in rows}) != 600:
        return 'unverified', {}
    if any(len(row.get('ego_body_xy', [])) != 4 for row in rows):
        return 'unverified', {}
    fault = sum(bool(row.get('fault_injection_applied')) for row in rows)
    test = rows[100:160]
    displacement = round(test[-1]['ego_center_xy'][0] - test[0]['ego_center_xy'][0], 4)
    bicycle = sum(overlap(row['ego_body_xy']) > .001 for row in rows[100:240])
    if RESPONSE == 'faulted':
        met = fault == 280 and displacement == 0 and bicycle > 0
    else:
        met = fault == 0 and displacement > 5 and bicycle > 0
    observed = {'fault_readback_frames': fault,
                'propulsion_test_displacement_m': displacement,
                'bicycle_lane_occupied_frames_100_240': bicycle,
                'response': RESPONSE}
    return ('met' if met else 'not_met'), observed


def one(kind, output):
    manifest = json.loads((ROOT / 'execution-manifest.json').read_text())
    entry = next(row for row in manifest['cases'] if row['case_id'] == CASE)
    base = {'case_id': CASE, 'construction_sha256': entry['construction_sha256'],
            'diagnostic_fixture': True, 'provenance_kind': 'synthetic_fixture',
            'original_native_observed': False, 'legal_verdict_claimed': False}
    if kind == 'lifecycle':
        base.update(events=EVENTS, exit_code=0,
                    negative_premature_saved_processing_rejected=True)
    else:
        rows = [json.loads(line) for line in SOURCE.read_text().splitlines()]
        if kind == 'incomplete_motion':
            if RESPONSE == 'faulted':
                for row in rows:
                    row['fault_injection_applied'] = False
            else:
                rows[180]['fault_injection_applied'] = True
        elif kind == 'missing_evidence':
            rows.pop()
        status, observed = classify(rows)
        expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                    'missing_evidence': 'unverified'}[kind]
        if status != expected:
            raise ValueError(f'{kind}: {status} != {expected}')
        base.update(physical_checks={'maneuver': {
            'status': status,
            'method': 'source-joined 600-frame synthetic powertrain readback and ego body geometry',
            'sources': [str(SOURCE.relative_to(ROOT))]}},
            maneuver_completed=status == 'met',
            realized_observables=observed if status == 'met' else {},
            source_sha256={str(SOURCE.relative_to(ROOT)): sha(SOURCE)})
    write(output, base)
    print(json.dumps({'kind': kind, 'case_id': CASE,
                      'status': base.get('physical_checks', {}).get('maneuver', {}).get('status')}))


def build():
    manifest = json.loads((ROOT / 'execution-manifest.json').read_text())
    entry = next(row for row in manifest['cases'] if row['case_id'] == CASE)
    folder = HERE / 'physical-proof'
    references = []
    for kind in (*KINDS, 'lifecycle'):
        output, log = folder / (kind + '.json'), folder / (kind + '.log')
        folder.mkdir(parents=True, exist_ok=True)
        command = [sys.executable, str(Path(__file__).resolve()),
                   '--kind', kind, '--output', str(output)]
        with log.open('w') as stream:
            result = subprocess.run(command, cwd=ROOT.parents[1], stdout=stream,
                                    stderr=subprocess.STDOUT, timeout=30)
        if result.returncode:
            raise ValueError(f'Physical fixture failed: {log}')
        references.append({'kind': kind, 'command': ' '.join(command), 'exit_code': 0,
                           'log': str(log.relative_to(ROOT)), 'log_sha256': sha(log),
                           'result': str(output.relative_to(ROOT)), 'result_sha256': sha(output)})
    lifecycle = json.loads((folder / 'lifecycle.json').read_text())
    proof = {'format': 'c10052-synthetic-exception-b-physical-preparation-v1',
             'case_id': CASE, 'construction_sha256': entry['construction_sha256'],
             'fixtures': references[:3],
             'lifecycle': {**lifecycle, 'log': references[3]['log'],
                           'log_sha256': references[3]['log_sha256']},
             'diagnostic_only': True, 'original_native_observed': False}
    path = folder / 'proof.json'
    write(path, proof)
    entry['physical_preparation'] = {'receipt': str(path.relative_to(ROOT)),
                                     'sha256': sha(path)}
    write(ROOT / 'execution-manifest.json', manifest)
    print(json.dumps({'case_id': CASE, 'physical_fixture_passed': True}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--build', action='store_true')
    parser.add_argument('--kind', choices=(*KINDS, 'lifecycle'))
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.build:
        build()
    elif args.kind and args.output:
        one(args.kind, args.output)
    else:
        parser.error('Select --build or one fixture')
