"""Independent synthetic rider/ego timing and lifecycle fixture for one selected case."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
SOURCE = HERE / 'source/rider_native_samples.jsonl'
GEOMETRY = HERE / 'source/rider_geometry.json'
EVENTS = ['capture_finished', 'encoders_closed', 'restoration_verified',
          'native_exit', 'owner_released', 'saved_processing_started']
KINDS = ('complete_motion', 'incomplete_motion', 'missing_evidence')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + '\n')


def intersects(body, bounds):
    x1, y1, x2, y2 = bounds
    xs = [point[0] for point in body]
    ys = [point[1] for point in body]
    return min(xs) < x2 and max(xs) > x1 and min(ys) < y2 and max(ys) > y1


def classify(rows, bounds):
    frames = [row.get('native_frame') for row in rows]
    if len(rows) != 600 or len(set(frames)) != 600 or any(
            len(row.get(key, [])) != 4
            for row in rows for key in ('ego_body_xy', 'rider_body_xy')):
        return 'unverified', {}
    rider = [row['native_frame'] for row in rows
             if intersects(row['rider_body_xy'], bounds)]
    ego = [row['native_frame'] for row in rows
           if intersects(row['ego_body_xy'], bounds)]
    if not rider or not ego:
        return 'not_met', {'rider_conflict_frames': len(rider),
                           'ego_conflict_frames': len(ego)}
    overlap = len(set(rider) & set(ego))
    gap = (min(ego) - max(rider)) / 20
    observation = {'rider_conflict_frames': len(rider),
                   'ego_conflict_frames': len(ego),
                   'simultaneous_conflict_frames': overlap,
                   'rider_last_frame': max(rider),
                   'ego_first_frame': min(ego), 'clearance_s': gap}
    return ('met' if gap > 0 and overlap == 0 else 'not_met'), observation


def one(kind, output):
    entry = json.loads((ROOT / 'execution-manifest.json').read_text())['cases'][2]
    base = {'case_id': entry['case_id'],
            'construction_sha256': entry['construction_sha256'],
            'diagnostic_fixture': True, 'provenance_kind': 'synthetic_fixture',
            'original_native_observed': False, 'legal_verdict_claimed': False}
    if kind == 'lifecycle':
        base.update(events=EVENTS, exit_code=0,
                    negative_premature_saved_processing_rejected=True)
    else:
        rows = [json.loads(line) for line in SOURCE.read_text().splitlines()]
        bounds = json.loads(GEOMETRY.read_text())['conflict_native_xy_bounds_m']
        if kind == 'incomplete_motion':
            rider_row = next(row for row in rows
                             if intersects(row['rider_body_xy'], bounds))
            rider_row['ego_body_xy'] = rider_row['rider_body_xy']
        elif kind == 'missing_evidence':
            rows.pop()
        status, observed = classify(rows, bounds)
        expected = {'complete_motion': 'met',
                    'incomplete_motion': 'not_met',
                    'missing_evidence': 'unverified'}[kind]
        if status != expected:
            raise ValueError(f'Fixture {kind} classified {status}, expected {expected}')
        base.update(physical_checks={'maneuver': {
            'status': status,
            'method': 'source-joined 600-frame full-body rider and ego conflict timing',
            'sources': [str(SOURCE.relative_to(ROOT)),
                        str(GEOMETRY.relative_to(ROOT))]}},
            maneuver_completed=status == 'met',
            realized_observables=observed if status == 'met' else {},
            source_sha256={str(SOURCE.relative_to(ROOT)): sha(SOURCE),
                           str(GEOMETRY.relative_to(ROOT)): sha(GEOMETRY)})
    write(output, base)
    print(json.dumps({'kind': kind, 'case_id': entry['case_id'],
                      'status': base.get('physical_checks', {}).get('maneuver', {}).get('status')}))


def build():
    entry = json.loads((ROOT / 'execution-manifest.json').read_text())['cases'][2]
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
                           'log_sha256': sha(log),
                           'result': str(output.relative_to(ROOT)),
                           'result_sha256': sha(output)})
    lifecycle = json.loads((folder / 'lifecycle.json').read_text())
    proof = {'format': 'c10052-synthetic-rider-physical-preparation-v1',
             'case_id': entry['case_id'],
             'construction_sha256': entry['construction_sha256'],
             'fixtures': references[:3],
             'lifecycle': {**lifecycle, 'log': references[3]['log'],
                           'log_sha256': references[3]['log_sha256']},
             'diagnostic_only': True, 'original_native_observed': False}
    path = folder / 'proof.json'
    write(path, proof)
    manifest_path = ROOT / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    manifest['cases'][2]['physical_preparation'] = {
        'receipt': str(path.relative_to(ROOT)), 'sha256': sha(path)}
    write(manifest_path, manifest)
    print(json.dumps({'case_id': entry['case_id'], 'physical_fixture_passed': True}))


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
