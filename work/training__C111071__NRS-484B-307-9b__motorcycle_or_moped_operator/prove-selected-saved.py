"""Prove selected case recorded-only processing on the current public fixture."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SUFFIX = sys.argv[1]
if SUFFIX not in ('probe_1', 'probe_2', 'yield_wait_for_clearance',
                  'yield_enter_during_occupancy'):
    raise ValueError('Unknown selected case')
CASE = HERE.name + '__' + SUFFIX
MANIFEST = HERE / 'execution-manifest.json'
SOURCE_SUFFIX = 'probe1' if SUFFIX == 'probe_1' else SUFFIX
SOURCE = ROOT / ('.runtime-work/c111071-selected-compat-' + SOURCE_SUFFIX + '-v2')
SCRATCH = ROOT / ('.runtime-work/c111071-selected-saved-' + SUFFIX + '-v1')
VALIDATOR = ROOT / '.runtime-work/c111250-current-decoder/.lake/build/bin/adapterCheck'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    compatibility = json.loads((SOURCE / 'compatibility.json').read_text())
    if compatibility.get('passed') is not True or len(compatibility['fixture_manifest']) < 600:
        raise ValueError('Current public fixture inventory unavailable')
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
        shutil.copyfile(SOURCE / relative, target)
        if target.suffix != '.mkv' and sha(target) != digest:
            raise ValueError('Original source copied incorrectly: ' + relative)
    before = {relative: sha(attempt / relative) for relative in compatibility['fixture_manifest']}
    command = [sys.executable, str(ROOT / 'runtime.py'), 'process-saved',
               '--manifest', str(MANIFEST), '--case', CASE, '--attempt', str(attempt),
               '--output', str(output), '--library', str(ROOT / 'runtime/library'),
               '--validator', str(VALIDATOR)]
    run = subprocess.run(command, text=True, stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, timeout=1800)
    log = HERE / 'selected-native' / SUFFIX / 'saved-command.log'
    log.write_text(run.stdout.rstrip() + '\n')
    if run.returncode:
        raise RuntimeError(f'process-saved exit {run.returncode}; see {log}')
    receipt = json.loads(run.stdout)
    preserved = all(sha(attempt / relative) == digest for relative, digest in before.items())
    if not receipt.get('passed') or receipt.get('missing_evidence') or not receipt.get('originals_preserved') or not preserved:
        raise ValueError('Recorded-only source preservation failed')
    proof = {'format': 'c111071-selected-saved-proof-v1', 'passed': True,
             'case_id': CASE, 'manifest_sha256': sha(MANIFEST),
             'compatibility_sha256': sha(SOURCE / 'compatibility.json'),
             'command_log_sha256': sha(log), 'source_files': len(before),
             'source_hashes_preserved': preserved, 'processing_receipt': receipt,
             'original_native_observed': False, 'physical_acceptance_claimed': False,
             'legal_verdict_claimed': False}
    target = HERE / 'selected-native' / SUFFIX / 'saved-proof.json'
    target.write_text(json.dumps(proof, indent=2) + '\n')
    print(json.dumps({'passed': True, 'source_files': len(before), 'proof_sha256': sha(target)}))


if __name__ == '__main__':
    os.environ.setdefault('SCENARIO_PIPELINE_OUTPUT_ROOT', str(ROOT / '.runtime-work/c111071-selected-saved-root'))
    main()
