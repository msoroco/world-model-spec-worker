"""Build source-bound C111588 CPU audit and physical-preparation receipts."""
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys

from rider_delivery_audit import audit_attempt

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
CASES = [
    ('bicycle_signal_once', 'first-execution-manifest.json', 'c111588-once-primary-compat-g'),
    ('bicycle_no_signal', 'no-signal-manifest.json', 'c111588-none-primary-compat-g'),
    ('bicycle_signal_continuous', 'continuous-manifest.json', 'c111588-continuous-primary-compat-g'),
]


def sha(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def run(command, log):
    env = dict(os.environ, PYTHONPATH=str(REPO / 'runtime/scenario_pipeline'))
    done = subprocess.run(command, cwd=REPO, env=env, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    log.write_text(done.stdout)
    if done.returncode:
        raise RuntimeError(f'{command} failed; see {log}')
    return {'command': ' '.join(command), 'exit_code': done.returncode,
            'log': str(log.relative_to(ROOT)), 'log_sha256': sha(log)}


def main():
    physical = ROOT / 'physical'
    physical.mkdir(exist_ok=True)
    life_log = physical / 'lifecycle.log'
    life = run([sys.executable, str(ROOT / 'rider_lifecycle_fixture.py')], life_log)
    for slug, manifest_name, source_name in CASES:
        source = REPO / '.runtime-work' / source_name
        manifest_path = ROOT / manifest_name
        manifest = json.loads(manifest_path.read_text())
        entry = manifest['cases'][0]
        report = json.loads((source / 'analysis-report.json').read_text())
        receipt = audit_attempt(source, report, receipt_dir=physical / (slug + '-decodes'))
        audit_path = physical / (slug + '-audit.json')
        save(audit_path, receipt)
        stale = json.loads(json.dumps(report))
        stale['measurements']['rider_turn_signal_observation']['sources']['rider_arm_bones.jsonl'] = '0' * 64
        try:
            audit_attempt(source, stale)
        except ValueError as exc:
            if 'Stale or missing original source' not in str(exc):
                raise
            negative = {'stale_original_rejected': True, 'error': str(exc),
                        'diagnostic_fixture': True}
        else:
            raise AssertionError('stale original accepted')
        negative_path = physical / (slug + '-stale-audit.json')
        save(negative_path, negative)
        fixtures = []
        for kind in ('complete_motion', 'incomplete_motion', 'missing_evidence'):
            result = physical / f'{slug}-{kind}.json'
            log = physical / f'{slug}-{kind}.log'
            command = [sys.executable, str(ROOT / 'rider_physical_fixture.py'),
                       '--source', str(source), '--kind', kind, '--output', str(result)]
            test = run(command, log)
            fixtures.append({'kind': kind, **test, 'result': str(result.relative_to(ROOT)),
                             'result_sha256': sha(result)})
        proof = {'format': 'worker-rider-physical-preparation',
                 'case_id': entry['case_id'], 'construction_sha256': entry['construction_sha256'],
                 'diagnostic_fixture_only': True, 'actual_native_capture': False,
                 'physical_acceptance_claimed': False,
                 'audit': {'receipt': str(audit_path.relative_to(ROOT)), 'sha256': sha(audit_path),
                           'stale_negative': str(negative_path.relative_to(ROOT)),
                           'stale_negative_sha256': sha(negative_path)},
                 'fixtures': fixtures,
                 'lifecycle': {'events': ['capture_finished', 'encoders_closed',
                         'restoration_verified', 'native_exit', 'owner_released',
                         'saved_processing_started'], **life}}
        proof_path = physical / (slug + '-proof.json')
        save(proof_path, proof)
        entry['physical_preparation'] = {'receipt': str(proof_path.relative_to(ROOT)),
                                         'sha256': sha(proof_path)}
        save(manifest_path, manifest)
        print(f'{slug}: independent audit and three physical fixtures passed')


if __name__ == '__main__':
    main()
