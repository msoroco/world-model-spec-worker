"""Exercise recorded-only processing for the exact paired fallback bundles."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = next(p for p in HERE.parents if (p / 'batch.json').is_file())
VALIDATOR = ROOT / '.runtime-work/c111250-current-decoder/.lake/build/bin/adapterCheck'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prove(number):
    case = HERE.name + f'__probe_{number}'
    manifest = HERE / f'fallback-probe-{number}-compatibility-manifest.json'
    source = ROOT / f'.runtime-work/c111294-v2-fallback-{number}-public'
    scratch = ROOT / f'.runtime-work/c111294-branch-v2-fallback-{number}-saved'
    if scratch.exists():
        raise ValueError('Saved-processing scratch must be fresh')
    compatibility = json.loads((source / 'compatibility.json').read_text())
    if compatibility.get('passed') is not True or len(compatibility['fixture_manifest']) < 600:
        raise ValueError('Public fallback source inventory unavailable')
    attempt, output = scratch / 'attempt', scratch / 'processed'
    scratch.mkdir(parents=True)
    subprocess.run([sys.executable, str(ROOT / 'runtime.py'), 'materialize',
                    '--manifest', str(manifest), '--case', case,
                    '--output', str(attempt)], check=True, stdout=subprocess.DEVNULL)
    for relative, digest in compatibility['fixture_manifest'].items():
        target = attempt / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / relative, target)
        if target.suffix != '.mkv' and sha(target) != digest:
            raise ValueError('Original fallback source copied incorrectly: ' + relative)
    before = {relative: sha(attempt / relative) for relative in compatibility['fixture_manifest']}
    command = [sys.executable, str(ROOT / 'runtime.py'), 'process-saved',
               '--manifest', str(manifest), '--case', case, '--attempt', str(attempt),
               '--output', str(output), '--library', str(ROOT / 'runtime/library'),
               '--validator', str(VALIDATOR)]
    run = subprocess.run(command, text=True, stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, timeout=1800)
    log = HERE / f'fallback-probe-{number}-saved-command.log'
    log.write_text(run.stdout.rstrip() + '\n')
    if run.returncode:
        raise RuntimeError(f'Fallback process-saved exit {run.returncode}; see {log}')
    receipt = json.loads(run.stdout)
    preserved = all(sha(attempt / relative) == digest for relative, digest in before.items())
    if not receipt.get('passed') or receipt.get('missing_evidence') or not receipt.get('originals_preserved') or not preserved:
        raise ValueError('Fallback recorded-only source preservation failed')
    proof = {'format': 'c111294-fallback-saved-diagnostic-v1', 'passed': True,
             'case_id': case, 'manifest_sha256': sha(manifest),
             'compatibility_sha256': sha(source / 'compatibility.json'),
             'command_log_sha256': sha(log), 'source_files': len(before),
             'source_hashes_preserved': preserved, 'processing_receipt': receipt,
             'original_native_observed': False, 'selected_delivery': False,
             'physical_acceptance_claimed': False, 'legal_verdict_claimed': False}
    target = HERE / f'fallback-probe-{number}-saved-proof.json'
    target.write_text(json.dumps(proof, indent=2) + '\n')
    return {'case': case, 'source_files': len(before), 'proof_sha256': sha(target)}


if __name__ == '__main__':
    output_root = Path(os.environ.get('SCENARIO_PIPELINE_OUTPUT_ROOT', '')).resolve()
    if not output_root.is_relative_to(ROOT / '.runtime-work'):
        raise SystemExit('Set SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work')
    if len(sys.argv) != 2 or sys.argv[1] not in ('1', '2'):
        raise SystemExit('Usage: prove-fallback-saved.py 1|2')
    print(json.dumps(prove(int(sys.argv[1])), sort_keys=True))
