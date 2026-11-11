"""Run each exact rear candidate through pinned saved-only processing."""

import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
from time import time_ns


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / 'rear-provisional-manifest.json'
CASE = HERE.name + '__rear_pass_no_device'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def call(command, log):
    with log.open('w') as output:
        subprocess.run(command, cwd=ROOT, stdout=output,
                       stderr=subprocess.STDOUT, check=True)


def prove(candidate, entry):
    prefix = ROOT / '.runtime-work' / ('c109749-rear-saved-' + candidate + '-' + str(time_ns()))
    fixture = Path(str(prefix) + '-fixture')
    attempt = Path(str(prefix) + '-attempt')
    output = Path(str(prefix) + '-processing')
    call([sys.executable, 'runtime.py', 'fixture', '--recipe',
          str(ROOT / entry['fixture_recipe']), '--output', str(fixture)],
         HERE / ('rear-' + candidate + '-saved-fixture.log'))
    call([sys.executable, 'runtime.py', 'materialize', '--manifest',
          str(MANIFEST), '--case', CASE, '--candidate', candidate,
          '--output', str(attempt)],
         HERE / ('rear-' + candidate + '-saved-materialize.log'))
    for source in fixture.iterdir():
        target = attempt / source.name
        if target.exists():
            raise ValueError('Diagnostic source shadows construction: ' + source.name)
        if source.is_dir():
            shutil.copytree(source, target)
        else:
            shutil.copy2(source, target)
    command = [sys.executable, 'runtime.py', 'process-saved', '--manifest',
               str(MANIFEST), '--case', CASE, '--attempt', str(attempt),
               '--output', str(output), '--library', 'runtime/library',
               '--validator', str(ROOT / '.runtime-work/fire-decoder/.lake/build/bin/adapterCheck')]
    log = HERE / ('rear-' + candidate + '-saved-processing.log')
    call(command, log)
    receipt_path = output / 'v0001/processing.json'
    receipt = json.loads(receipt_path.read_text())
    construction = entry if candidate == 'primary' else next(
        item for item in entry['candidates'] if item['id'] == candidate)
    if (receipt.get('passed') is not True or receipt.get('missing_evidence') is not False
            or receipt.get('originals_preserved') is not True or
            receipt.get('analysis_revision', {}).get('construction_sha256')
            != construction['construction_sha256']):
        raise ValueError('Rear saved diagnostic did not bind current construction')
    (HERE / ('rear-' + candidate + '-saved-proof.json')).write_text(json.dumps({
        'format': 'worker-rear-saved-processing-proof', 'case_id': CASE,
        'candidate_id': candidate, 'construction_sha256': construction['construction_sha256'],
        'manifest_sha256': sha(MANIFEST), 'command': ' '.join(command),
        'exit_code': 0, 'log': log.name, 'log_sha256': sha(log),
        'receipt_sha256': sha(receipt_path),
        'originals_preserved': True, 'missing_evidence': False,
        'physical_acceptance_claimed': False}, indent=2) + '\n')


def main():
    entry = json.loads(MANIFEST.read_text())['cases'][0]
    for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
        prove(candidate, entry)


if __name__ == '__main__':
    main()
