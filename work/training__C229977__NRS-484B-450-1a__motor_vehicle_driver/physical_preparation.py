"""Diagnostic source-shaped motion and lifecycle checks for selected cases."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
KINDS = ('complete_motion', 'incomplete_motion', 'missing_evidence')
EVENTS = ['capture_finished', 'encoders_closed', 'restoration_verified',
          'native_exit', 'owner_released', 'saved_processing_started']


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def status(rows, expected_occupancy):
    if len(rows) != 600 or [r.get('frame') for r in rows] != list(range(600)):
        return 'unverified'
    if any(r.get('actor_id') != 107 or not isinstance(r.get('speed_mps'), (float, int))
           or r['speed_mps'] < 0 or not isinstance(r.get('sidewalk_overlap_area_m2'), (float, int))
           for r in rows):
        return 'unverified'
    rest = [r for r in rows if r['speed_mps'] <= .05]
    if not rest:
        return 'not_met'
    overlap_at_rest = any(r['sidewalk_overlap_area_m2'] > 0 for r in rest)
    return 'met' if overlap_at_rest == expected_occupancy else 'not_met'


def one(index, kind, output):
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    entry = manifest['cases'][index - 1]
    source = HERE / 'diagnostic-source' / f'probe_{index}' / 'vehicle-trace.jsonl'
    rows = [json.loads(line) for line in source.read_text().splitlines()]
    base = {'case_id': entry['case_id'],
            'construction_sha256': entry['construction_sha256'],
            'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True,
            'original_native_observed': False, 'physical_acceptance_claimed': False}
    if kind == 'lifecycle':
        base.update(events=EVENTS, exit_code=0,
                    premature_saved_processing_rejected=True)
    else:
        if kind == 'incomplete_motion':
            for row in rows:
                row['speed_mps'] = 4.0
        if kind == 'missing_evidence':
            rows.pop()
        measured = status(rows, index == 2)
        expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                    'missing_evidence': 'unverified'}[kind]
        if measured != expected:
            raise ValueError('Physical fixture differs: ' + kind + '/' + measured)
        base.update(physical_checks={'maneuver': {
            'status': measured,
            'method': '600 source-shaped rest and sidewalk-overlap rows; diagnostic rest tolerance only',
            'sources': [str(source.relative_to(HERE))]}},
            maneuver_completed=measured == 'met',
            realized_observables={'rest_frames': sum(r['speed_mps'] <= .05 for r in rows),
                                  'requested_sidewalk_occupancy': index == 2}
            if measured == 'met' else {}, source_sha256=sha(source))
    write(output, base)
    print(json.dumps({'case_id': entry['case_id'], 'kind': kind,
                      'status': base.get('physical_checks', {}).get('maneuver', {}).get('status')}))


def build():
    manifest_path = HERE / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    for index, entry in enumerate(manifest['cases'], 1):
        folder = HERE / 'physical-proof' / f'probe_{index}'
        refs = []
        for kind in (*KINDS, 'lifecycle'):
            output = folder / (kind + '.json')
            log = folder / (kind + '.log')
            command = [sys.executable, '-B', str(Path(__file__).resolve()),
                       '--case', str(index), '--kind', kind, '--output', str(output)]
            folder.mkdir(parents=True, exist_ok=True)
            with log.open('w') as stream:
                process = subprocess.run(command, cwd=HERE.parents[1],
                                         stdout=stream, stderr=subprocess.STDOUT, timeout=30,
                                         env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
            log.write_text(log.read_text().rstrip() + '\n')
            if process.returncode:
                raise ValueError('Physical fixture failed: ' + str(log))
            refs.append({'kind': kind, 'command': ' '.join(command),
                         'exit_code': 0, 'log': str(log.relative_to(HERE)),
                         'log_sha256': sha(log), 'result': str(output.relative_to(HERE)),
                         'result_sha256': sha(output)})
        life = json.loads((folder / 'lifecycle.json').read_text())
        proof = {'format': 'c229977-sidewalk-physical-cpu-v1',
                 'case_id': entry['case_id'], 'construction_sha256': entry['construction_sha256'],
                 'fixtures': refs[:3],
                 'lifecycle': {**life, 'log': refs[3]['log'], 'log_sha256': refs[3]['log_sha256']},
                 'diagnostic_only': True, 'original_native_observed': False}
        write(folder / 'proof.json', proof)
        entry['physical_preparation'] = {
            'receipt': str((folder / 'proof.json').relative_to(HERE)),
            'sha256': sha(folder / 'proof.json')}
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--build', action='store_true')
    parser.add_argument('--case', type=int)
    parser.add_argument('--kind', choices=(*KINDS, 'lifecycle'))
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.build:
        build()
    elif args.case and args.kind and args.output:
        one(args.case, args.kind, args.output)
    else:
        parser.error('Choose --build or one fixture')
