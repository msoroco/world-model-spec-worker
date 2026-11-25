"""Run current recorded-only processing against the public fixture inventory."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CASE = HERE.name + '__probe_1'
MANIFEST = HERE / 'current-v2-probe-1-primary-manifest.json'
SCRATCH = ROOT / '.runtime-work/c111294-geometry-output/saved-probe-1'
VALIDATOR = ROOT / '.runtime-work/c111250-current-decoder/.lake/build/bin/adapterCheck'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    source = ROOT / '.runtime-work/c111294-geometry-output/compat-probe-1-r2'
    compatibility = json.loads((source / 'compatibility.json').read_text())
    if compatibility.get('passed') is not True or len(compatibility['fixture_manifest']) < 600:
        raise ValueError('Public compatibility source inventory unavailable')
    if SCRATCH.exists():
        raise ValueError('Saved-processing scratch must be fresh')
    attempt = SCRATCH / 'attempt'
    output = SCRATCH / 'processed'
    SCRATCH.mkdir(parents=True)
    subprocess.run([sys.executable, str(ROOT / 'runtime.py'), 'materialize',
                    '--manifest', str(MANIFEST), '--case', CASE, '--output', str(attempt)],
                   check=True, stdout=subprocess.DEVNULL)
    for relative, digest in compatibility['fixture_manifest'].items():
        target = attempt / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / relative, target)
        if target.suffix != '.mkv' and sha(target) != digest:
            raise ValueError('Original source copied incorrectly: ' + relative)
    before = {relative: sha(attempt / relative) for relative in compatibility['fixture_manifest']}
    command = [sys.executable, str(ROOT / 'runtime.py'), 'process-saved',
               '--manifest', str(MANIFEST), '--case', CASE, '--attempt', str(attempt),
               '--output', str(output), '--library', str(ROOT / 'runtime/library'),
               '--validator', str(VALIDATOR)]
    run = subprocess.run(command, text=True, stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, timeout=1800)
    log = HERE / 'current-v2-probe-1-saved-command.log'
    log.write_text(run.stdout)
    if run.returncode:
        raise RuntimeError(f'process-saved exit {run.returncode}; see {log}')
    receipt = json.loads(run.stdout)
    preserved = all(sha(attempt / relative) == digest for relative, digest in before.items())
    if not receipt.get('passed') or receipt.get('missing_evidence') or not receipt.get('originals_preserved') or not preserved:
        raise ValueError('Recorded-only source preservation failed')
    proof = {'format': 'c111294-current-v2-saved-diagnostic-v1', 'passed': True,
             'case_id': CASE, 'manifest_sha256': sha(MANIFEST),
             'compatibility_sha256': sha(source / 'compatibility.json'),
             'command_log_sha256': sha(log), 'source_files': len(before),
             'source_hashes_preserved': preserved, 'processing_receipt': receipt,
             'original_native_observed': False, 'selected_delivery': False,
             'physical_acceptance_claimed': False, 'legal_verdict_claimed': False}
    target = HERE / 'current-v2-probe-1-saved-proof.json'
    target.write_text(json.dumps(proof, indent=2) + '\n')
    print(json.dumps({'passed': True, 'source_files': len(before), 'proof_sha256': sha(target)}))


if __name__ == '__main__':
    os.environ.setdefault('SCENARIO_PIPELINE_OUTPUT_ROOT', str(ROOT / '.runtime-work/c111294-v2'))
    main()
