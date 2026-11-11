"""Exercise one exact overtaking fallback through the frozen saved path."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess
import sys
from time import time_ns

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def call(command, log):
    with log.open('w') as output:
        subprocess.run(command, cwd=ROOT, stdout=output,
                       stderr=subprocess.STDOUT, check=True)


def prove(suffix, candidate):
    manifest = HERE / ('delivery-construction-manifest.json' if suffix == 'left_pass_wide'
                       else 'variant-construction-manifest.json')
    case = HERE.name + '__' + suffix
    entry = next(row for row in json.loads(manifest.read_text())['cases']
                 if row['case_id'] == case)
    selected = next(row for row in entry['candidates'] if row['id'] == candidate)
    stem = 'delivery-' + suffix + '-' + candidate
    prefix = ROOT / '.runtime-work' / ('c110161-' + suffix + '-' + candidate + '-saved-' + str(time_ns()))
    fixture = Path(str(prefix) + '-fixture')
    attempt = Path(str(prefix) + '-attempt')
    output = Path(str(prefix) + '-processing')
    call([sys.executable, 'runtime.py', 'fixture', '--recipe',
          str(ROOT / entry['fixture_recipe']), '--output', str(fixture)],
         HERE / (stem + '-fixture.log'))
    call([sys.executable, 'runtime.py', 'materialize', '--manifest', str(manifest),
          '--case', case, '--candidate', candidate, '--output', str(attempt)],
         HERE / (stem + '-materialize.log'))
    for path in fixture.iterdir():
        target = attempt / path.name
        if target.exists():
            raise ValueError('Diagnostic source shadows construction: ' + path.name)
        if path.is_dir():
            shutil.copytree(path, target)
        else:
            shutil.copy2(path, target)
    command = [sys.executable, 'runtime.py', 'process-saved', '--manifest',
               str(manifest), '--case', case, '--attempt', str(attempt),
               '--output', str(output), '--library', 'runtime/library',
               '--validator', str(ROOT / '.runtime-work/fire-decoder/.lake/build/bin/adapterCheck')]
    log = HERE / (stem + '-saved.log')
    call(command, log)
    receipt_path = output / 'v0001/processing.json'
    receipt = json.loads(receipt_path.read_text())
    if (receipt.get('passed') is not True or receipt.get('missing_evidence') is not False
            or receipt.get('originals_preserved') is not True
            or receipt.get('candidate_id') != candidate
            or receipt.get('analysis_revision', {}).get('construction_sha256')
            != selected['construction_sha256']):
        raise ValueError('Fallback saved processing did not bind selected construction')
    (HERE / (stem + '-saved-proof.json')).write_text(json.dumps({
        'format': 'worker-exact-fallback-saved-proof', 'case_id': case,
        'candidate_id': candidate, 'construction_sha256': selected['construction_sha256'],
        'manifest_sha256': digest(manifest), 'command': ' '.join(command),
        'exit_code': 0, 'log': log.name, 'log_sha256': digest(log),
        'receipt_sha256': digest(receipt_path), 'originals_preserved': True,
        'missing_evidence': False, 'physical_acceptance_claimed': False}, indent=2) + '\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('suffix', choices=('left_pass_wide', 'left_pass_narrow',
                                           'return_before_clear', 'return_after_clear'))
    parser.add_argument('candidate', choices=('fallback1', 'fallback2', 'fallback3'))
    args = parser.parse_args()
    prove(args.suffix, args.candidate)
