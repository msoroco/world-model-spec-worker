"""Exercise current saved-only lifecycle on the unselected 600-frame diagnostic."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PACKAGE = HERE / 'rider-30s-primary'
CASE = HERE.name + '__rider_bicycle_clear'
FIXTURE = ROOT / '.runtime-work/c10052-rider-30s-profile-fixture'
DECODER = ROOT / '.runtime-work/c10052-current-decoder/.lake/build/bin/adapterCheck'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def command(args, env):
    return subprocess.run(args, cwd=ROOT, env=env, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=600)


def run():
    env = dict(os.environ)
    env['SCENARIO_PIPELINE_OUTPUT_ROOT'] = str(ROOT / '.runtime-work/c10052-rider-30s-saved')
    if not FIXTURE.is_dir() or not DECODER.is_file():
        raise ValueError('Current source fixture and decoder required')
    with tempfile.TemporaryDirectory(dir=ROOT / '.runtime-work',
                                     prefix='c10052-rider-saved-') as temp:
        scratch = Path(temp)
        attempt = scratch / 'attempt'
        materialize = command([sys.executable, str(ROOT / 'runtime.py'), 'materialize',
                               '--manifest', str(PACKAGE / 'draft-manifest.json'),
                               '--case', CASE, '--output', str(attempt)], env)
        if materialize.returncode:
            raise ValueError('Materialization failed: ' + materialize.stdout)
        for source in FIXTURE.iterdir():
            target = attempt / source.name
            if target.exists():
                raise ValueError('Fixture shadows construction: ' + source.name)
            if source.is_dir():
                shutil.copytree(source, target)
            else:
                shutil.copy2(source, target)
        before = {str(p.relative_to(attempt)): sha(p) for p in attempt.rglob('*') if p.is_file()}
        output = scratch / 'processed'
        args = [sys.executable, str(ROOT / 'runtime.py'), 'process-saved',
                '--manifest', str(PACKAGE / 'draft-manifest.json'), '--case', CASE,
                '--attempt', str(attempt), '--output', str(output),
                '--library', str(ROOT / 'runtime/library'),
                '--validator', str(DECODER)]
        processed = command(args, env)
        after = {name: sha(attempt / name) for name in before}
        if before != after:
            raise ValueError('Saved processing changed original acquisition')
        version = output / 'v0001'
        feedback = version / 'feedback.json'
        receipt = version / 'processing.json'
        receipt_present = receipt.is_file()
        if processed.returncode != 0 or not receipt_present:
            raise ValueError('Saved-only lifecycle did not produce a passing receipt: ' + processed.stdout[-1800:])
        processing_receipt = json.loads(receipt.read_text())
        if not processing_receipt.get('passed') or not processing_receipt.get('recorded_only'):
            raise ValueError('Saved-only receipt lacks passing recorded-only binding')
        result = {'format': 'c10052-rider-30s-process-saved-proof-v1',
                  'case_id': CASE, 'selected': False, 'exit_code': processed.returncode,
                  'originals_preserved': True, 'source_files': len(before),
                  'manifest_sha256': sha(PACKAGE / 'draft-manifest.json'),
                  'construction_sha256': sha(PACKAGE / 'construction.json'),
                  'processing_receipt': processing_receipt,
                  'processing_receipt_sha256': sha(receipt),
                  'feedback': json.loads(feedback.read_text()) if feedback.is_file() else None,
                  'error_tail': processed.stdout[-1800:] if processed.returncode else None,
                  'physical_acceptance_claimed': False, 'legal_verdict_claimed': False}
    (PACKAGE / 'process-saved-proof.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'exit_code': result['exit_code'], 'receipt': receipt_present,
                      'feedback': result['feedback'], 'error_tail': result['error_tail']}, indent=2))
    return result


if __name__ == '__main__':
    run()
