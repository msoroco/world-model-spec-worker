"""Synthetic pedestrian timing and capture lifecycle fixture for one selected case."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
RESPONSE = HERE.name.rsplit('-', 1)[-1]
CASE = ROOT.name + '__pedestrian_' + RESPONSE
SOURCE = HERE / 'source/pedestrian_native_samples.jsonl'
GEOMETRY = HERE / 'source/pedestrian_geometry.json'
BOUNDS = (-2.5, -5.0, 2.5, -3.0)
EVENTS = ['capture_finished', 'encoders_closed', 'restoration_verified',
          'native_exit', 'owner_released', 'saved_processing_started']
KINDS = ('complete_motion', 'incomplete_motion', 'missing_evidence')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + '\n')


def area(body):
    xs = [point[0] for point in body]
    ys = [point[1] for point in body]
    return max(0, min(max(xs), BOUNDS[2]) - max(min(xs), BOUNDS[0])) * max(
        0, min(max(ys), BOUNDS[3]) - max(min(ys), BOUNDS[1]))


def classify(rows):
    frames = [row.get('native_frame') for row in rows]
    if len(rows) != 600 or len(set(frames)) != 600 or any(
            len(row.get(key, [])) != 4 for row in rows
            for key in ('ego_body_xy', 'pedestrian_body_xy')):
        return 'unverified', {}
    pedestrian = [i for i, row in enumerate(rows) if area(row['pedestrian_body_xy']) > .01]
    ego = [i for i, row in enumerate(rows) if area(row['ego_body_xy']) > .01]
    if not pedestrian or not ego:
        return 'not_met', {'pedestrian_conflict_frames': len(pedestrian),
                           'ego_conflict_frames': len(ego)}
    overlap = len(set(pedestrian) & set(ego))
    target = 0 if RESPONSE == 'clear' else 20
    observed = {'pedestrian_conflict_frames': len(pedestrian),
                'ego_conflict_frames': len(ego),
                'simultaneous_conflict_frames': overlap,
                'pedestrian_last_frame': max(pedestrian),
                'ego_first_frame': min(ego), 'target_frames': target}
    return ('met' if overlap == target else 'not_met'), observed


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
            index = next(i for i, row in enumerate(rows) if area(row['pedestrian_body_xy']) > .01)
            if RESPONSE == 'clear':
                rows[index]['ego_body_xy'] = rows[index]['pedestrian_body_xy']
            else:
                rows[index]['pedestrian_body_xy'] = [[30, -7], [31, -7], [31, -6], [30, -6]]
        elif kind == 'missing_evidence':
            rows.pop()
        status, observed = classify(rows)
        expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                    'missing_evidence': 'unverified'}[kind]
        if status != expected:
            raise ValueError(f'Fixture {kind} classified {status}, expected {expected}')
        base.update(physical_checks={'maneuver': {
            'status': status,
            'method': 'source-joined 600-frame full-body pedestrian and ego conflict timing',
            'sources': [str(SOURCE.relative_to(ROOT)), str(GEOMETRY.relative_to(ROOT))]}},
            maneuver_completed=status == 'met',
            realized_observables=observed if status == 'met' else {},
            source_sha256={str(SOURCE.relative_to(ROOT)): sha(SOURCE),
                           str(GEOMETRY.relative_to(ROOT)): sha(GEOMETRY)})
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
        command = [sys.executable, str(Path(__file__).resolve()),
                   '--kind', kind, '--output', str(output)]
        folder.mkdir(parents=True, exist_ok=True)
        with log.open('w') as stream:
            result = subprocess.run(command, cwd=ROOT.parents[1], stdout=stream,
                                    stderr=subprocess.STDOUT, timeout=30)
        if result.returncode:
            raise ValueError(f'Physical fixture failed: {log}')
        references.append({'kind': kind, 'command': ' '.join(command),
                           'exit_code': 0, 'log': str(log.relative_to(ROOT)),
                           'log_sha256': sha(log), 'result': str(output.relative_to(ROOT)),
                           'result_sha256': sha(output)})
    lifecycle = json.loads((folder / 'lifecycle.json').read_text())
    proof = {'format': 'c10052-synthetic-pedestrian-physical-preparation-v1',
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
