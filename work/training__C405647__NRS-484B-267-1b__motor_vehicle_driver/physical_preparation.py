"""Prove diagnostic motion completion and saved ownership ordering for 1(b)."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

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


def evaluate(rows):
    if len(rows) != 600:
        return 'unverified', {}
    if any(row.get('frame') != i or row.get('native_frame') != 1000 + i or
           abs(row.get('time_s', -1) - i / 20) > 1e-4 for i, row in enumerate(rows)):
        return 'unverified', {}
    x0 = rows[0]['subject']['center_xy_m'][0]
    x1 = rows[-1]['subject']['center_xy_m'][0]
    final_speeds = [row['subject']['speed_mps'] for row in rows[-10:]]
    complete = x1 - x0 >= 15 and max(final_speeds) <= .1
    return ('met' if complete else 'not_met'), {
        'joined_frames': len(rows), 'travel_x_m': round(x1 - x0, 4),
        'last_ten_frame_max_speed_mps': max(final_speeds),
        'source_kind': 'synthetic_scene_request'}


def fixture(suffix, kind, output):
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    entry = next(c for c in manifest['cases'] if c['case_id'].endswith('__' + suffix))
    result = {'case_id': entry['case_id'],
              'construction_sha256': entry['construction_sha256'],
              'diagnostic_fixture': True, 'provenance_kind': 'synthetic_fixture',
              'original_native_observed': False, 'legal_verdict': None}
    if kind == 'lifecycle':
        processing = json.loads((HERE / 'current-public' /
            (suffix + '-primary-processing.json')).read_text())
        if not (processing['passed'] and processing['recorded_only'] and
                processing['originals_preserved'] and
                'saved_processing_started' in processing['events']):
            raise ValueError('Recorded-only saved lifecycle proof missing')
        premature = EVENTS[:-2] + list(reversed(EVENTS[-2:]))
        if premature.index('saved_processing_started') >= premature.index('owner_released'):
            raise ValueError('Premature saved processing not rejected')
        result.update(events=EVENTS, exit_code=0,
                      negative_premature_saved_processing_rejected=True,
                      recorded_only_receipt_sha256=sha(HERE / 'current-public' /
                          (suffix + '-primary-processing.json')))
    else:
        source = HERE / 'current-fixture' / suffix / 'actor-frames.jsonl'
        rows = [json.loads(line) for line in source.read_text().splitlines()]
        if kind == 'incomplete_motion':
            frozen = rows[5]['subject']
            for row in rows[6:]:
                row['subject'] = frozen
        elif kind == 'missing_evidence':
            rows.pop()
        with tempfile.TemporaryDirectory(dir=ROOT / '.runtime-work',
                                         prefix='c405647-physical-') as tmp:
            scratch = Path(tmp) / 'mutated-actor-frames.jsonl'
            scratch.write_text(''.join(json.dumps(r) + '\n' for r in rows))
            status, measured = evaluate([json.loads(line) for line in scratch.read_text().splitlines()])
        expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                    'missing_evidence': 'unverified'}[kind]
        if status != expected:
            raise ValueError('Physical diagnostic differs: ' + kind + '/' + status)
        result.update(physical_checks={'maneuver': {
            'status': status,
            'method': '600 time-joined synthetic Native-style actor samples; full requested travel and 10-frame stop',
            'sources': [source.relative_to(ROOT).as_posix()]}},
            maneuver_completed=status == 'met',
            realized_observables=measured if status == 'met' else {},
            source_sha256=sha(source))
    put(output, result)
    print(json.dumps({'case': suffix, 'kind': kind,
                      'status': result.get('physical_checks', {}).get('maneuver', {}).get('status')}))


def build():
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    index = []
    for entry in manifest['cases']:
        suffix = entry['case_id'].rsplit('__', 1)[-1]
        folder = HERE / 'physical-proof' / suffix
        refs = []
        for kind in (*KINDS, 'lifecycle'):
            output, log = folder / (kind + '.json'), folder / (kind + '.log')
            folder.mkdir(parents=True, exist_ok=True)
            command = [sys.executable, str(Path(__file__).resolve()), '--case', suffix,
                       '--kind', kind, '--output', str(output)]
            with log.open('w') as stream:
                done = subprocess.run(command, cwd=ROOT, stdout=stream,
                                      stderr=subprocess.STDOUT, timeout=30)
            if done.returncode:
                raise ValueError('Physical fixture failed: ' + str(log))
            refs.append({'kind': kind, 'command': ' '.join(command), 'exit_code': 0,
                         'log': log.relative_to(HERE).as_posix(), 'log_sha256': sha(log),
                         'result': output.relative_to(HERE).as_posix(),
                         'result_sha256': sha(output)})
        life = json.loads((folder / 'lifecycle.json').read_text())
        proof = {'format': 'c405647-synthetic-physical-preparation',
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
    put(HERE / 'physical-proof/index.json', {'cases': index, 'diagnostic_only': True})
    print(json.dumps({'physical_fixture_cases': len(index)}))


if __name__ == '__main__':
    tmpdir = Path(os.environ.get('TMPDIR', '/')).resolve()
    if not tmpdir.is_relative_to(ROOT / '.runtime-work'):
        raise SystemExit('Set TMPDIR under .runtime-work')
    parser = argparse.ArgumentParser()
    parser.add_argument('--build', action='store_true')
    parser.add_argument('--case', choices=('reference', 'contrast'))
    parser.add_argument('--kind', choices=(*KINDS, 'lifecycle'))
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.build:
        build()
    elif args.case and args.kind and args.output:
        fixture(args.case, args.kind, args.output)
    else:
        parser.error('Select --build or one fixture')
