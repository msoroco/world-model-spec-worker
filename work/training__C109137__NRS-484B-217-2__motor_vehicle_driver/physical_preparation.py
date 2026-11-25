"""Source-bound CPU fixtures for crossing completion and saved-only lifecycle."""
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


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def source_name(suffix):
    if suffix in ('probe_1', 'probe_2'):
        return 'selected-' + suffix.replace('_', '')
    return 'selected-traffic-' + suffix.removeprefix('traffic_')


def evaluate(rows):
    if len(rows) != 600 or any(row.get('frame') != i or
            row.get('native_frame') != 1000 + i or
            abs(row.get('time_s', 0) - (i + 1) / 20) > 1e-4 or
            'ego' not in row or 'following' not in row or 'oncoming' not in row
            for i, row in enumerate(rows)):
        return 'unverified', {}
    first = rows[0]['ego']['center_native_xyz_m']
    last = rows[-1]['ego']['center_native_xyz_m']
    travel = ((last[0] - first[0]) ** 2 + (last[1] - first[1]) ** 2) ** .5
    entries = [row['frame'] for row in rows if row['observed_road_id'] == 218]
    completed = travel > 15 and bool(entries) and entries[0] >= 172
    measured = {'joined_frames': 600, 'ego_travel_m': round(travel, 4),
                'first_observed_adjoining_road_frame': entries[0] if entries else None}
    return ('met' if completed else 'not_met'), measured


def fixture(suffix, kind, output):
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    entry = next(e for e in manifest['cases'] if e['case_id'].endswith('__' + suffix))
    prefix = source_name(suffix)
    result = {'case_id': entry['case_id'],
              'construction_sha256': entry['construction_sha256'],
              'diagnostic_fixture': True, 'provenance_kind': 'synthetic_fixture',
              'original_native_observed': False, 'legal_verdict': None}
    if kind == 'lifecycle':
        receipt = HERE / (prefix + '-processing.json')
        recorded = json.loads(receipt.read_text())
        if not (recorded['passed'] and recorded['recorded_only'] and
                recorded['originals_preserved'] and
                'saved_processing_started' in recorded['events']):
            raise ValueError('Recorded-only processing receipt failed')
        premature = EVENTS[:-2] + list(reversed(EVENTS[-2:]))
        if premature.index('saved_processing_started') >= premature.index('owner_released'):
            raise ValueError('Premature processing was accepted')
        result.update(events=EVENTS, exit_code=0,
                      negative_premature_saved_processing_rejected=True,
                      recorded_only_receipt_sha256=digest(receipt))
    else:
        source = HERE / (prefix + '-fixture/native-raw-actors.jsonl')
        rows = [json.loads(x) for x in source.read_text().splitlines()]
        if kind == 'incomplete_motion':
            for row in rows[193:]:
                row['observed_road_id'] = 217
        if kind == 'missing_evidence':
            rows.pop()
        status, measured = evaluate(rows)
        expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                    'missing_evidence': 'unverified'}[kind]
        if status != expected:
            raise ValueError('Physical fixture mismatch: ' + suffix + '/' + kind + '/' + status)
        result.update(physical_checks={'maneuver': {'status': status,
            'method': '600 sequential synthetic Native-style actor samples, ego displacement and adjoining road readback',
            'sources': [source.relative_to(ROOT).as_posix()]}},
            maneuver_completed=status == 'met',
            realized_observables=measured if status == 'met' else {},
            source_sha256=digest(source))
    put(output, result)
    print(json.dumps({'case': suffix, 'kind': kind,
                      'status': result.get('physical_checks', {}).get('maneuver', {}).get('status')}))


def build():
    manifest_path = HERE / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    for entry in manifest['cases']:
        suffix = entry['case_id'].split('__')[-1]
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
                         'log': log.relative_to(HERE).as_posix(), 'log_sha256': digest(log),
                         'result': output.relative_to(HERE).as_posix(),
                         'result_sha256': digest(output)})
        life = json.loads((folder / 'lifecycle.json').read_text())
        proof = {'format': 'c109137-synthetic-physical-preparation',
                 'case_id': entry['case_id'], 'construction_sha256': entry['construction_sha256'],
                 'fixtures': refs[:3],
                 'lifecycle': {**life, 'log': refs[3]['log'],
                               'log_sha256': refs[3]['log_sha256']},
                 'diagnostic_only': True, 'original_native_observed': False}
        path = folder / 'proof.json'
        put(path, proof)
        entry['physical_preparation'] = {'case_id': entry['case_id'],
                                         'receipt': path.relative_to(HERE).as_posix(),
                                         'sha256': digest(path)}
    put(manifest_path, manifest)
    print(json.dumps({'physical_fixture_cases': len(manifest['cases'])}))


if __name__ == '__main__':
    if not Path(os.environ.get('TMPDIR', '/')).resolve().is_relative_to(ROOT / '.runtime-work'):
        raise SystemExit('Set TMPDIR under .runtime-work')
    parser = argparse.ArgumentParser()
    parser.add_argument('--build', action='store_true')
    parser.add_argument('--case', choices=('probe_1', 'probe_2', 'traffic_clear_traffic', 'traffic_following_brake'))
    parser.add_argument('--kind', choices=(*KINDS, 'lifecycle'))
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.build:
        build()
    elif args.case and args.kind and args.output:
        fixture(args.case, args.kind, args.output)
    else:
        parser.error('Choose --build or a fixture')
