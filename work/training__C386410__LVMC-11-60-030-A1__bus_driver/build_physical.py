"""Bind synthetic motion and ownership-order proofs to exact constructions."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SCRATCH = REPO / '.runtime-work/c386410-physical'
SCRIPT = ROOT / 'physical_proof.py'
MANIFEST = ROOT / 'execution-manifest.json'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2) + '\n')


def main():
    SCRATCH.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(MANIFEST.read_text())
    env = dict(os.environ, SCENARIO_PIPELINE_OUTPUT_ROOT=str(SCRATCH), TMPDIR=str(SCRATCH))
    for entry in manifest['cases']:
        if entry.get('physical_preparation'):
            continue
        suffix = entry['case_id'].rsplit('__', 1)[-1]
        attempt = REPO / '.runtime-work/c386410-variant-saved' / suffix / 'attempt'
        construction = json.loads((ROOT / entry['construction']).read_text())
        config = SCRATCH / (suffix + '-config.json')
        config.write_text(next(item['content'] for item in construction['files'] if item['path'] == 'config.json'))
        proof = ROOT / 'proofs' / suffix / 'physical'
        proof.mkdir(parents=True, exist_ok=True)
        receipts = []
        for kind in ('complete_motion', 'incomplete_motion', 'missing_evidence'):
            result_path, log_path = proof / (kind + '.json'), proof / (kind + '.log')
            command = [sys.executable, '-B', str(SCRIPT), '--fixture', str(attempt),
                       '--config', str(config), '--kind', kind, '--output', str(result_path)]
            run = subprocess.run(command, env=env, capture_output=True, text=True)
            if run.returncode:
                raise RuntimeError(kind + ': ' + run.stderr)
            log_path.write_text(run.stdout.rstrip() + '\n')
            receipts.append({'kind': kind, 'command': ' '.join(command), 'exit_code': 0,
                             'log': str(log_path.relative_to(ROOT)), 'log_sha256': sha(log_path),
                             'result': str(result_path.relative_to(ROOT)), 'result_sha256': sha(result_path)})
        life_log = proof / 'lifecycle.log'
        command = [sys.executable, '-B', str(SCRIPT), '--lifecycle']
        run = subprocess.run(command, env=env, capture_output=True, text=True)
        if run.returncode:
            raise RuntimeError(run.stderr)
        life_log.write_text(run.stdout.rstrip() + '\n')
        receipt = {'format': 'c386410-synthetic-physical-proof-v1',
                   'case_id': entry['case_id'], 'construction_sha256': entry['construction_sha256'],
                   'original_native_observed': False, 'diagnostic_only': True,
                   'fixtures': receipts,
                   'lifecycle': {'events': list(('capture_finished', 'encoders_closed',
                       'restoration_verified', 'native_exit', 'owner_released', 'saved_processing_started')),
                       'exit_code': 0, 'negative_premature_saved_processing_rejected': True,
                       'log': str(life_log.relative_to(ROOT)), 'log_sha256': sha(life_log)}}
        receipt_path = proof / 'proof.json'
        write(receipt_path, receipt)
        entry['physical_preparation'] = {'receipt': str(receipt_path.relative_to(ROOT)),
                                         'sha256': sha(receipt_path)}
    write(MANIFEST, manifest)
    print('Remaining exact bus physical and lifecycle receipts generated')


if __name__ == '__main__':
    main()
