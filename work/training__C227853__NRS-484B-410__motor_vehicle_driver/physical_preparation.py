"""Synthetic source and lifecycle fixtures for selected parked departures."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
EVENTS = ['capture_finished', 'encoders_closed', 'restoration_verified',
          'native_exit', 'owner_released', 'saved_processing_started']
KINDS = ('complete_motion', 'incomplete_motion', 'missing_evidence')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + '\n')


def classify(rows, suffix):
    if len(rows) != 600 or len({r.get('native_frame') for r in rows}) != 600:
        return 'unverified'
    if any(len(r.get('ego_footprint_xy_m', [])) != 4 for r in rows):
        return 'unverified'
    beginning_x = sum(pt[0] for pt in rows[0]['ego_footprint_xy_m']) / 4
    ending_x = sum(pt[0] for pt in rows[-1]['ego_footprint_xy_m']) / 4
    beginning_y = sum(pt[1] for pt in rows[0]['ego_footprint_xy_m']) / 4
    ending_y = sum(pt[1] for pt in rows[-1]['ego_footprint_xy_m']) / 4
    if not all(row.get('ego_speed_mps',1) <= .1 for row in rows[:100]):
        return 'unverified'
    return 'met' if ending_x > beginning_x + 10 and ending_y > beginning_y + 2 else 'not_met'


def fixture(suffix, kind, output):
    manifest = json.loads((HERE / 'draft-departure-manifest.json').read_text())
    entry = next(e for e in manifest['cases'] if e['case_id'].endswith('__' + suffix))
    base = {'case_id': entry['case_id'], 'construction_sha256': entry['construction_sha256'],
            'diagnostic_fixture': True, 'provenance_kind': 'synthetic_fixture',
            'original_native_observed': False, 'physical_acceptance_claimed': False,
            'legal_verdict_claimed': False}
    if kind == 'lifecycle':
        base.update(events=EVENTS, exit_code=0,
                    negative_premature_saved_processing_rejected=True)
    else:
        source = HERE / 'selected-source' / suffix / 'departure-trace.jsonl'
        rows = [json.loads(line) for line in source.read_text().splitlines()]
        if kind == 'incomplete_motion':
            for row in rows[150:]:
                row['ego_footprint_xy_m'] = [[x - row['ego_xy_m'][0], y - row['ego_xy_m'][1] - 5]
                                              for x, y in row['ego_footprint_xy_m']]
        elif kind == 'missing_evidence':
            rows.pop()
        status = classify(rows, suffix)
        expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                    'missing_evidence': 'unverified'}[kind]
        if status != expected:
            raise ValueError('Physical fixture outcome differs: ' + kind + '/' + status)
        base.update(physical_checks={'maneuver': {
                        'status': status,
                        'method': '600 joined synthetic original footprints, start-from-rest and departure displacement; no safety conclusion',
                        'sources': [str(source.relative_to(HERE))]}},
                    maneuver_completed=status == 'met',
                    realized_observables={'joined_frames': 600,
                                          'final_body_lateral_center_m': sum(pt[1] for pt in rows[-1]['ego_footprint_xy_m']) / 4}
                    if status == 'met' else {},
                    source_sha256=sha(source))
    write(output, base)
    print(json.dumps({'case_id': entry['case_id'], 'kind': kind,
                      'status': base.get('physical_checks', {}).get('maneuver', {}).get('status')}))


def build():
    manifest = json.loads((HERE / 'draft-departure-manifest.json').read_text())
    index = []
    for entry in manifest['cases']:
        suffix = entry['case_id'].rsplit('__', 1)[-1]
        folder = HERE / 'physical-proof' / suffix
        refs = []
        for kind in (*KINDS, 'lifecycle'):
            output, log = folder / (kind + '.json'), folder / (kind + '.log')
            command = [sys.executable, str(Path(__file__).resolve()),
                       '--case', suffix, '--kind', kind, '--output', str(output)]
            folder.mkdir(parents=True, exist_ok=True)
            with log.open('w') as stream:
                result = subprocess.run(command, cwd=HERE.parents[1], stdout=stream,
                                        stderr=subprocess.STDOUT, timeout=30)
            if result.returncode:
                raise ValueError('Physical fixture failed: ' + str(log))
            refs.append({'kind': kind, 'command': ' '.join(command), 'exit_code': 0,
                         'log': str(log.relative_to(HERE)), 'log_sha256': sha(log),
                         'result': str(output.relative_to(HERE)),
                         'result_sha256': sha(output)})
        lifecycle = json.loads((folder / 'lifecycle.json').read_text())
        proof = {'format': 'c227853-synthetic-physical-preparation-v1',
                 'case_id': entry['case_id'], 'construction_sha256': entry['construction_sha256'],
                 'fixtures': refs[:3],
                 'lifecycle': {**lifecycle, 'log': refs[3]['log'],
                               'log_sha256': refs[3]['log_sha256']},
                 'diagnostic_only': True, 'original_native_observed': False}
        path = folder / 'proof.json'
        write(path, proof)
        index.append({'case_id': entry['case_id'],
                      'receipt': str(path.relative_to(HERE)), 'sha256': sha(path)})
    write(HERE / 'physical-proof/index.json', {'cases': index, 'diagnostic_only': True})
    print(json.dumps({'physical_fixture_cases': len(index)}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--build', action='store_true')
    parser.add_argument('--case', choices=tuple('controlled_'+str(i) for i in range(1,9)))
    parser.add_argument('--kind', choices=(*KINDS, 'lifecycle'))
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.build:
        build()
    elif args.case and args.kind and args.output:
        fixture(args.case, args.kind, args.output)
    else:
        parser.error('Select --build or one fixture')
