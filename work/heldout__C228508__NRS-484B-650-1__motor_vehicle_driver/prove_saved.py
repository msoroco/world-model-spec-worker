"""Exercise the repeated-following bundle through saved-only CPU processing."""

from hashlib import sha256
import json
import shutil
import subprocess
import sys
from pathlib import Path
from time import time_ns

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / 'execution-manifest.json'


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def call(command, log):
    with log.open('w') as stream:
        subprocess.run(command, cwd=ROOT, stdout=stream,
                       stderr=subprocess.STDOUT, check=True)


def prove(entry, candidate):
    case = entry['case_id']
    short = case.rsplit('__', 1)[-1]
    label = short + '-' + candidate
    selected = (entry if candidate == 'primary' else
                next(item for item in entry['candidates'] if item['id'] == candidate))
    prefix = ROOT / '.runtime-work' / ('c228508-saved-' + label + '-' + str(time_ns()))
    fixture, attempt, output = (Path(str(prefix) + suffix)
                                for suffix in ('-fixture', '-attempt', '-processing'))
    call([sys.executable, 'runtime.py', 'fixture', '--recipe',
          str(ROOT / entry['fixture_recipe']), '--output', str(fixture)],
         HERE / (label + '-saved-fixture.log'))
    call([sys.executable, 'runtime.py', 'materialize', '--manifest',
          str(MANIFEST), '--case', case, '--candidate', candidate,
          '--output', str(attempt)],
         HERE / (label + '-saved-materialize.log'))
    for source in fixture.iterdir():
        target = attempt / source.name
        if target.exists():
            raise ValueError('Fixture shadows construction: ' + source.name)
        if source.is_dir():
            shutil.copytree(source, target)
        else:
            shutil.copy2(source, target)
    command = [sys.executable, 'runtime.py', 'process-saved', '--manifest',
               str(MANIFEST), '--case', case, '--attempt', str(attempt),
               '--output', str(output), '--library', 'runtime/library',
               '--validator', str(ROOT / '.runtime-work/fire-decoder/.lake/build/bin/adapterCheck')]
    log = HERE / (label + '-saved-processing.log')
    call(command, log)
    receipt = output / 'v0001/processing.json'
    data = json.loads(receipt.read_text())
    if (data.get('passed') is not True or data.get('missing_evidence') is not False
            or data.get('originals_preserved') is not True
            or data.get('analysis_revision', {}).get('construction_sha256')
            != selected['construction_sha256']):
        raise ValueError('Repeated-following saved processing failed')
    proof = {'format': 'worker-saved-processing-proof', 'case_id': case,
             'candidate_id': candidate,
             'construction_sha256': selected['construction_sha256'],
             'manifest_sha256': digest(MANIFEST),
             'command': ' '.join(command), 'exit_code': 0, 'log': log.name,
             'log_sha256': digest(log), 'receipt_sha256': digest(receipt),
             'originals_preserved': True, 'missing_evidence': False,
             'physical_acceptance_claimed': False}
    (HERE / (label + '-saved-proof.json')).write_text(
        json.dumps(proof, indent=2) + '\n')


def main():
    for entry in json.loads(MANIFEST.read_text())['cases']:
        for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
            prove(entry, candidate)


if __name__ == '__main__':
    main()
