"""Run and bind source-derived taxi physical episode CPU fixtures."""
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parents[1]
KINDS = ('complete_motion', 'incomplete_motion', 'missing_evidence')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest_path = BASE / 'selected-draft-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    lifecycle_log = BASE / 'native' / 'selected-focused-tests.log'
    lifecycle_text = lifecycle_log.read_text()
    if ('test_full_synthetic_world_lifecycle' not in lifecycle_text or
            'test_tick_failure_restores_without_seal' not in lifecycle_text or
            not lifecycle_text.rstrip().endswith('OK')):
        raise ValueError('Capture lifecycle tests did not pass')
    for suffix in ('probe_a', 'probe_b'):
        entry = next(e for e in manifest['cases']
                     if e['case_id'] == BASE.name + '__' + suffix)
        saved = json.loads((BASE / 'native' / 'saved' / suffix /
                            'primary' / 'processing.json').read_text())
        if (saved.get('recorded_only') is not True or
                saved.get('originals_preserved') is not True or
                'saved_processing_started' not in saved.get('events', [])):
            raise ValueError('Saved lifecycle evidence absent')
        location = BASE / 'native' / 'physical' / suffix
        location.mkdir(parents=True, exist_ok=True)
        fixtures = []
        for kind in KINDS:
            result = location / (kind + '-result.json')
            log = location / (kind + '.log')
            command = [sys.executable, '-B', str(BASE / 'native' / 'prove_physical.py'),
                       '--case', suffix, '--kind', kind, '--output', str(result)]
            env = dict(os.environ)
            env['TMPDIR'] = str(ROOT / '.runtime-work' / 'lead-current-audits')
            env['SCENARIO_PIPELINE_OUTPUT_ROOT'] = env['TMPDIR']
            completed = subprocess.run(command, cwd=ROOT, env=env,
                                       text=True, capture_output=True)
            log.write_text((completed.stdout + completed.stderr).rstrip('\n') + '\n')
            if completed.returncode:
                raise ValueError('Physical fixture failed: ' + kind)
            observed = json.loads(result.read_text())
            expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                        'missing_evidence': 'unverified'}[kind]
            if observed['physical_checks']['maneuver']['status'] != expected:
                raise ValueError('Physical fixture status differs: ' + kind)
            fixtures.append({
                'kind': kind, 'command': ' '.join(command), 'exit_code': 0,
                'log': str(log.relative_to(BASE)), 'log_sha256': sha(log),
                'result': str(result.relative_to(BASE)),
                'result_sha256': sha(result)})
        proof = {'format': 'worker-physical-preparation',
                 'case_id': entry['case_id'],
                 'construction_sha256': entry['construction_sha256'],
                 'fixtures': fixtures,
                 'lifecycle': {
                     'events': ['capture_finished', 'encoders_closed',
                                'restoration_verified', 'native_exit',
                                'owner_released', 'saved_processing_started'],
                     'exit_code': 0,
                     'log': str(lifecycle_log.relative_to(BASE)),
                     'log_sha256': sha(lifecycle_log),
                     'saved_receipt': 'native/saved/' + suffix + '/primary/processing.json',
                     'saved_receipt_sha256': sha(BASE / 'native' / 'saved' / suffix /
                                                  'primary' / 'processing.json')}}
        proof_path = location / 'physical-preparation.json'
        proof_path.write_text(json.dumps(proof, indent=2, allow_nan=False) + '\n')
        entry['physical_preparation'] = {
            'receipt': str(proof_path.relative_to(BASE)),
            'sha256': sha(proof_path)}
    manifest_path.write_text(json.dumps(manifest, indent=2, allow_nan=False) + '\n')


if __name__ == '__main__':
    main()
