"""Run the first ending-road construction through frozen saved-only processing."""

from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess
import sys
from time import time_ns

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / 'execution-manifest.json'
CASE = HERE.name + '__official_device_control'


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def call(command, log):
    with log.open('w') as output:
        subprocess.run(command, cwd=ROOT, stdout=output,
                       stderr=subprocess.STDOUT, check=True)


def main():
    entry = next(row for row in json.loads(MANIFEST.read_text())['cases']
                 if row['case_id'] == CASE)
    prefix = ROOT / '.runtime-work' / ('c111294-official-device-saved-' + str(time_ns()))
    fixture = Path(str(prefix) + '-fixture')
    attempt = Path(str(prefix) + '-attempt')
    output = Path(str(prefix) + '-processing')
    call([sys.executable, 'runtime.py', 'fixture', '--recipe',
          str(ROOT / entry['fixture_recipe']), '--output', str(fixture)],
         HERE / 'official-device-saved-fixture.log')
    call([sys.executable, 'runtime.py', 'materialize', '--manifest',
          str(MANIFEST), '--case', CASE, '--output', str(attempt)],
         HERE / 'official-device-saved-materialize.log')
    for path in fixture.iterdir():
        target = attempt / path.name
        if target.exists():
            raise ValueError('Diagnostic source shadows construction: ' + path.name)
        if path.is_dir():
            shutil.copytree(path, target)
        else:
            shutil.copy2(path, target)
    command = [sys.executable, 'runtime.py', 'process-saved', '--manifest',
               str(MANIFEST), '--case', CASE, '--attempt', str(attempt),
               '--output', str(output), '--library', 'runtime/library',
               '--validator', str(ROOT / '.runtime-work/fire-decoder/.lake/build/bin/adapterCheck')]
    log = HERE / 'official-device-saved-processing.log'
    call(command, log)
    receipt_path = output / 'v0001/processing.json'
    receipt = json.loads(receipt_path.read_text())
    if (receipt.get('passed') is not True or receipt.get('missing_evidence') is not False
            or receipt.get('originals_preserved') is not True
            or receipt.get('analysis_revision', {}).get('construction_sha256')
            != entry['construction_sha256']):
        raise ValueError('First saved ending-road diagnostic did not complete')
    (HERE / 'official-device-saved-proof.json').write_text(json.dumps({
        'format': 'worker-first-saved-processing-proof', 'case_id': CASE,
        'construction_sha256': entry['construction_sha256'],
        'manifest_sha256': digest(MANIFEST), 'command': ' '.join(command),
        'exit_code': 0, 'log': log.name, 'log_sha256': digest(log),
        'receipt_sha256': digest(receipt_path),
        'originals_preserved': True, 'missing_evidence': False,
        'physical_acceptance_claimed': False}, indent=2) + '\n')


if __name__ == '__main__':
    main()
