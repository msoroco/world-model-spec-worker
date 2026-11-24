"""Run recorded-only saved processing on public compatibility source sets."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CASE_PREFIX = HERE.name + '__selected_109a5dbc__'
VALIDATOR = ROOT / '.runtime-work/c104538-decoder/.lake/build/bin/adapterCheck'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(condition):
    if condition not in ('condition_a', 'condition_b'):
        raise ValueError('Unknown condition')
    letter = condition[-1]
    source = ROOT / f'.runtime-work/c110919-8d-v2/compat-{letter}'
    receipt = json.loads((HERE / f'current-v2-{letter}-compatibility.json').read_text())
    if receipt['passed'] is not True or len(receipt['fixture_manifest']) != 614:
        raise ValueError('Exact public source inventory unavailable')
    manifest = HERE / f'current-v2-{condition}-primary-manifest.json'
    case = CASE_PREFIX + condition
    scratch = ROOT / f'.runtime-work/c110919-8d-v2/saved-{letter}'
    attempt = scratch / 'attempt'
    output = scratch / 'processed'
    if scratch.exists():
        raise ValueError('Use a fresh saved-processing location')
    scratch.mkdir(parents=True)
    materialize = [sys.executable, str(ROOT / 'runtime.py'), 'materialize',
                   '--manifest', str(manifest), '--case', case, '--output', str(attempt)]
    subprocess.run(materialize, check=True, stdout=subprocess.DEVNULL)
    for relative in receipt['fixture_manifest']:
        target = attempt / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / relative, target)
        if target.suffix != '.mkv' and sha(target) != receipt['fixture_manifest'][relative]:
            raise ValueError('Source changed during saved attempt: ' + relative)
    before = {relative: sha(attempt / relative) for relative in receipt['fixture_manifest']}
    command = [sys.executable, str(ROOT / 'runtime.py'), 'process-saved',
               '--manifest', str(manifest), '--case', case, '--attempt', str(attempt),
               '--output', str(output), '--library', str(ROOT / 'runtime/pipeline/library'),
               '--validator', str(VALIDATOR)]
    run = subprocess.run(command, text=True, stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, timeout=1800)
    log = HERE / f'current-v2-{letter}-saved-command.log'
    log.write_text(run.stdout)
    if run.returncode:
        raise RuntimeError(f'Saved processing exit {run.returncode}: see {log}')
    processed = json.loads(run.stdout)
    if not processed.get('passed') or processed.get('missing_evidence') or not processed.get('originals_preserved'):
        raise ValueError('Saved processing did not pass as recorded-only positive')
    if any(sha(attempt / relative) != digest for relative, digest in before.items()):
        raise ValueError('Recorded-only processing changed an original')
    proof = {'format': 'c110919-current-v2-saved-diagnostic-v1', 'passed': True,
             'case_id': case, 'manifest_sha256': sha(manifest),
             'compatibility_sha256': sha(HERE / f'current-v2-{letter}-compatibility.json'),
             'command_log_sha256': sha(log), 'source_files': len(before),
             'source_hashes_preserved': True, 'processing_receipt': processed,
             'original_native_observed': False, 'selected_delivery': False,
             'physical_acceptance_claimed': False, 'legal_verdict_claimed': False}
    target = HERE / f'current-v2-{letter}-saved-proof.json'
    target.write_text(json.dumps(proof, indent=2) + '\n')
    print(json.dumps({'passed': True, 'proof_sha256': sha(target), 'source_files': len(before)}))


if __name__ == '__main__':
    os.environ.setdefault('SCENARIO_PIPELINE_OUTPUT_ROOT', str(ROOT / '.runtime-work/c110919-8d-v2'))
    run(sys.argv[1])
