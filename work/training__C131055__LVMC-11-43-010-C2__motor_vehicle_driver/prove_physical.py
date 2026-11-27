"""Exercise source-bound motion assessment and Native ownership ordering."""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from worker_exchange.native_output import physical_result
from worker_exchange.saved_processing import _closure

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
EVENTS = ['capture_finished', 'encoders_closed', 'restoration_verified',
          'native_exit', 'owner_released', 'saved_processing_started']
KINDS = ('complete_motion', 'incomplete_motion', 'missing_evidence')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, allow_nan=False) + '\n')


def one(short, kind, output):
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    entry = next(c for c in manifest['cases'] if c['case_id'].endswith('__' + short))
    base = {'case_id': entry['case_id'], 'construction_sha256': entry['construction_sha256'],
            'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True,
            'original_native_observed': False, 'physical_acceptance_claimed': False}
    scratch = REPO / '.runtime-work/c131055-c2/physical'
    scratch.mkdir(parents=True, exist_ok=True)
    if kind == 'lifecycle':
        with tempfile.TemporaryDirectory(prefix='closure-', dir=scratch) as temporary:
            try:
                _closure(Path(temporary), None, 'native', False)
            except ValueError as error:
                if 'owner-release receipt' not in str(error):
                    raise
            else:
                raise AssertionError('Saved processing preceded Native owner release')
        saved = HERE / 'saved' / (short + '-processing.json')
        receipt = json.loads(saved.read_text())
        if receipt.get('passed') is not True or receipt.get('recorded_only') is not True:
            raise ValueError('Missing recorded-only source-processing receipt')
        base.update(events=EVENTS, exit_code=0, premature_saved_processing_rejected=True,
                    recorded_only_diagnostic_receipt_sha256=sha(saved))
    else:
        with tempfile.TemporaryDirectory(prefix='motion-', dir=scratch) as temporary:
            root = Path(temporary)
            source = REPO / '.runtime-work/c131055-c2' / (short.split('_')[0] + '-saved-attempt')
            for name in ('config.json', 'video_frames.jsonl', 'trace.jsonl', 'acquisition-provenance.json'):
                shutil.copyfile(source / name, root / name)
            if kind in ('complete_motion', 'incomplete_motion'):
                path = root / 'trace.jsonl'
                rows = [json.loads(line) for line in path.read_text().splitlines()]
                for index, row in enumerate(rows):
                    x = index * 0.2 if kind == 'complete_motion' else 0.0
                    row['position_m'] = [x, 0.0, 0.0]
                    row['position'] = {'x': x, 'y': 0.0, 'z': 0.0}
                path.write_text(''.join(json.dumps(row, allow_nan=False) + '\n' for row in rows))
            if kind == 'missing_evidence':
                (root / 'video_frames.jsonl').unlink()
            assessed = physical_result(root, {'target_checks': [{'matched': True}]})
            expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                        'missing_evidence': 'unverified'}[kind]
            status = assessed['physical_checks']['maneuver']['status']
            if status != expected or assessed['maneuver_completed'] is not (expected == 'met'):
                raise ValueError('Unexpected source motion outcome: ' + short + '/' + kind + '/' + status)
            base.update({key: assessed[key] for key in ('physical_checks', 'maneuver_completed',
                                                       'realized_observables')})
    write(output, base)
    print(json.dumps({'case_id': entry['case_id'], 'kind': kind,
                      'maneuver_status': base.get('physical_checks', {}).get('maneuver', {}).get('status')}))


def build():
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    for entry in manifest['cases']:
        short = entry['case_id'].split('__')[-1]
        folder = HERE / 'physical-proof' / short
        refs = []
        for kind in (*KINDS, 'lifecycle'):
            output = folder / (kind + '.json')
            log = folder / (kind + '.log')
            command = [sys.executable, '-B', str(Path(__file__).resolve()), '--case', short,
                       '--kind', kind, '--output', str(output)]
            folder.mkdir(parents=True, exist_ok=True)
            with log.open('w') as stream:
                completed = subprocess.run(command, cwd=REPO, env=os.environ,
                                           stdout=stream, stderr=subprocess.STDOUT, timeout=90)
            log.write_text(log.read_text().rstrip() + '\n')
            if completed.returncode:
                raise ValueError('Physical diagnostic failed: ' + str(log))
            refs.append({'kind': kind, 'command': ' '.join(command), 'exit_code': 0,
                         'log': str(log.relative_to(HERE)), 'log_sha256': sha(log),
                         'result': str(output.relative_to(HERE)), 'result_sha256': sha(output)})
        life = json.loads((folder / 'lifecycle.json').read_text())
        proof = {'format': 'c131055-physical-cpu-v1', 'case_id': entry['case_id'],
                 'construction_sha256': entry['construction_sha256'], 'fixtures': refs[:3],
                 'lifecycle': {**life, 'log': refs[3]['log'], 'log_sha256': refs[3]['log_sha256']},
                 'diagnostic_only': True, 'original_native_observed': False}
        write(folder / 'proof.json', proof)
        entry['physical_preparation'] = {'receipt': str((folder / 'proof.json').relative_to(HERE)),
                                         'sha256': sha(folder / 'proof.json')}
        print(short, 'physical and lifecycle pass', flush=True)
    write(HERE / 'execution-manifest.json', manifest)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--build', action='store_true')
    parser.add_argument('--case')
    parser.add_argument('--kind', choices=(*KINDS, 'lifecycle'))
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.build:
        build()
    elif args.case and args.kind and args.output:
        one(args.case, args.kind, args.output)
    else:
        parser.error('Use --build or --case/--kind/--output')
