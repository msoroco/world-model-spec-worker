"""Exercise 600-frame motion and Native ownership ordering on CPU fixtures."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
EVENTS = ['capture_finished', 'encoders_closed', 'restoration_verified',
          'native_exit', 'owner_released', 'saved_processing_started']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def fixture(case, kind, output):
    manifest = json.loads((HERE / 'selected-probe-manifest.json').read_text())
    entry = next(item for item in manifest['cases'] if item['case_id'].endswith('__' + case))
    base = {'case_id': entry['case_id'], 'construction_sha256': entry['construction_sha256'],
            'diagnostic_fixture': True, 'provenance_kind': 'synthetic_fixture',
            'original_native_observed': False, 'physical_acceptance_claimed': False,
            'legal_verdict_claimed': False}
    if kind == 'lifecycle':
        base.update(events=EVENTS, exit_code=0,
                    negative_premature_saved_processing_rejected=True)
    else:
        source = HERE / 'selected-source' / case / 'native-lighting-frames.jsonl'
        rows = [json.loads(line) for line in source.read_text().splitlines()]
        if kind == 'incomplete_motion':
            for row in rows:
                row['velocity_mps'] = [0, 0, 0]
        if kind == 'missing_evidence':
            rows.pop()
        complete = (len(rows) == 600 and
                    all(row['native_frame'] == index and
                        abs(row['time_s'] - index/20) < 1e-6 for index, row in enumerate(rows)))
        moving = sum(1 for row in rows if row['velocity_mps'][0] > 0)
        status = ('unverified' if not complete else
                  'met' if moving >= 400 else 'not_met')
        expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                    'missing_evidence': 'unverified'}[kind]
        if status != expected:
            raise ValueError('Synthetic physical outcome differs: ' + kind)
        base.update(physical_checks={'maneuver': {
            'status': status,
            'method': '600 synchronized synthetic Native motion frames; original physical completion remains pending',
            'sources': [source.relative_to(ROOT).as_posix()]}},
            maneuver_completed=status == 'met',
            realized_observables={'motion_frames': moving, 'joined_frames': len(rows)}
            if status == 'met' else {},
            source_sha256=sha(source))
    write(output, base)
    print(json.dumps({'case': case, 'kind': kind,
                      'status': base.get('physical_checks', {}).get('maneuver', {}).get('status')}))


def build():
    manifest = json.loads((HERE / 'selected-probe-manifest.json').read_text())
    index = []
    for entry in manifest['cases']:
        case = entry['case_id'].rsplit('__', 1)[-1]
        folder = HERE / 'physical-proof' / case
        folder.mkdir(parents=True, exist_ok=True)
        refs = []
        for kind in ('complete_motion', 'incomplete_motion', 'missing_evidence', 'lifecycle'):
            output = folder / (kind + '.json')
            log = folder / (kind + '.log')
            command = [sys.executable, str(Path(__file__).resolve()),
                       '--case', case, '--kind', kind, '--output', str(output)]
            with log.open('w') as stream:
                result = subprocess.run(command, cwd=ROOT, stdout=stream,
                                        stderr=subprocess.STDOUT, timeout=30)
            if result.returncode:
                raise ValueError('Physical CPU fixture failed: ' + str(log))
            refs.append({'kind': kind, 'command': ' '.join(command), 'exit_code': 0,
                         'log': log.relative_to(HERE).as_posix(), 'log_sha256': sha(log),
                         'result': output.relative_to(HERE).as_posix(),
                         'result_sha256': sha(output)})
        life = json.loads((folder / 'lifecycle.json').read_text())
        proof = {'format': 'c230241-lighting-physical-cpu-preparation-v1',
                 'case_id': entry['case_id'],
                 'construction_sha256': entry['construction_sha256'],
                 'fixtures': refs[:3],
                 'lifecycle': {**life, 'log': refs[3]['log'],
                               'log_sha256': refs[3]['log_sha256']},
                 'diagnostic_only': True, 'original_native_observed': False}
        path = folder / 'proof.json'
        write(path, proof)
        index.append({'case_id': entry['case_id'],
                      'receipt': path.relative_to(HERE).as_posix(), 'sha256': sha(path)})
    write(HERE / 'physical-proof/index.json', {'cases': index, 'diagnostic_only': True})
    print(json.dumps({'physical_cases': len(index)}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--build', action='store_true')
    parser.add_argument('--case', choices=('reference', 'contrast'))
    parser.add_argument('--kind', choices=('complete_motion', 'incomplete_motion',
                                           'missing_evidence', 'lifecycle'))
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.build:
        build()
    elif args.case and args.kind and args.output:
        fixture(args.case, args.kind, args.output)
    else:
        parser.error('Select --build or one fixture')
