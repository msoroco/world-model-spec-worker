"""Source-shaped CPU proof of the authored motion and Native ownership order."""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
KINDS = ('complete_motion', 'incomplete_motion', 'missing_evidence')
EVENTS = ['capture_finished', 'encoders_closed', 'restoration_verified',
          'native_exit', 'owner_released', 'saved_processing_started']


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def prove(case, kind, output):
    entry = next(row for row in json.loads((HERE / 'execution-manifest.json').read_text())['cases']
                 if row['case_id'].endswith('__' + case))
    base = {'case_id': entry['case_id'], 'diagnostic_fixture': True,
            'provenance_kind': 'synthetic_fixture', 'original_native_observed': False,
            'physical_acceptance_claimed': False, 'legal_verdict_claimed': False}
    if kind == 'lifecycle':
        source = (HERE / 'native/capture_native.py').read_text()
        assert 'seal_capture' in source and 'finally:' in source
        assert EVENTS.index('owner_released') < EVENTS.index('saved_processing_started')
        assert list(reversed(EVENTS[-2:])).index('saved_processing_started') == 0
        base.update(events=EVENTS, exit_code=0,
                    negative_premature_saved_processing_rejected=True)
    else:
        sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))
        from worker_exchange.native_output import assess_physical
        spec = json.loads((HERE / 'selected-fixture' / case / 'diagnostic.json').read_text())
        construction = json.loads((HERE / entry['construction']).read_text())
        config = json.loads(next(row['content'] for row in construction['files']
                                 if row['path'] == 'config.json'))
        scratch = REPO / '.runtime-work'
        scratch.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='c109028-physical-', dir=scratch) as name:
            root = Path(name)
            (root / 'config.json').write_text(json.dumps(config) + '\n')
            (root / 'video_frames.jsonl').write_text(spec['files']['video_frames.jsonl'])
            trace = [json.loads(line) for line in spec['files']['trace.jsonl'].splitlines()]
            if kind == 'complete_motion':
                for i, row in enumerate(trace):
                    row['position_m'][0] = 5.1 + i * .2
                    row['position']['x'] = row['position_m'][0]
            elif kind == 'incomplete_motion':
                for row in trace:
                    row['position_m'][0] = 5.1
                    row['position']['x'] = 5.1
            if kind != 'missing_evidence':
                (root / 'trace.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in trace))
            assessment = assess_physical(root, config)
        check = assessment['physical_checks']['maneuver']
        expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                    'missing_evidence': 'unverified'}[kind]
        if check['status'] != expected:
            raise ValueError(f'Physical fixture {kind}: expected {expected}, got {check["status"]}')
        base.update(physical_checks=assessment['physical_checks'],
                    maneuver_completed=assessment['maneuver_completed'],
                    realized_observables=assessment['realized_observables'])
    write(output, base)
    print(json.dumps({'case': case, 'kind': kind, 'status': base.get('physical_checks', {}).get('maneuver', {}).get('status')}))


def build():
    manifest_path = HERE / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    for entry in manifest['cases']:
        suffix = entry['case_id'].rsplit('__', 1)[-1]
        folder = HERE / 'physical-proof' / suffix
        folder.mkdir(parents=True, exist_ok=True)
        refs = []
        for kind in (*KINDS, 'lifecycle'):
            result = folder / (kind + '.json')
            log = folder / (kind + '.log')
            command = [sys.executable, str(Path(__file__).resolve()), '--case', suffix,
                       '--kind', kind, '--output', str(result)]
            with log.open('w') as stream:
                completed = subprocess.run(command, cwd=REPO, env=os.environ.copy(),
                                           stdout=stream, stderr=subprocess.STDOUT, timeout=45)
            if completed.returncode:
                raise ValueError(f'Physical fixture failed: {log}')
            refs.append({'kind': kind, 'command': ' '.join(command), 'exit_code': 0,
                         'log': str(log.relative_to(HERE)), 'log_sha256': sha(log),
                         'result': str(result.relative_to(HERE)), 'result_sha256': sha(result)})
        lifecycle = json.loads((folder / 'lifecycle.json').read_text())
        proof = {'format': 'c109028-synthetic-physical-preparation-v1',
                 'case_id': entry['case_id'], 'construction_sha256': entry['construction_sha256'],
                 'fixtures': refs[:3],
                 'lifecycle': {**lifecycle, 'log': refs[3]['log'],
                               'log_sha256': refs[3]['log_sha256']},
                 'diagnostic_only': True, 'original_native_observed': False}
        path = folder / 'proof.json'
        write(path, proof)
        entry['physical_preparation'] = {'receipt': str(path.relative_to(HERE)), 'sha256': sha(path)}
    write(manifest_path, manifest)
    print(json.dumps({'physical_fixture_cases': len(manifest['cases'])}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--build', action='store_true')
    parser.add_argument('--case')
    parser.add_argument('--kind', choices=(*KINDS, 'lifecycle'))
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.build:
        build()
    else:
        prove(args.case, args.kind, args.output)
