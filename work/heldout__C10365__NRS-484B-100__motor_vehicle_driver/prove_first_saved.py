"""Run first exact C10365 diagnostic saved-only processing on retained originals."""

from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
import tempfile

from worker_exchange.runtime_cli import materialize
from worker_exchange.fixture_recipe import materialize as fixture_materialize
from worker_exchange.saved_processing import copy_sources


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
CASE = ROOT.name + '__stop_responds'
MANIFEST = ROOT / 'probe-compatibility-manifest.json'


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def main():
    attempt = REPO / '.runtime-work/c10365-stop_responds-attempt-first'
    output = REPO / '.runtime-work/c10365-stop_responds-saved-first'
    if attempt.exists():
        raise ValueError('Retain prior C10365 diagnostic acquisition')
    materialize(MANIFEST, CASE, attempt)
    with tempfile.TemporaryDirectory(dir=REPO / '.runtime-work', prefix='c10365-source-') as temporary:
        fixture = Path(temporary) / 'source'
        entry = json.loads(MANIFEST.read_text())['cases'][0]
        fixture_materialize(REPO, REPO / entry['fixture_recipe'], fixture)
        copy_sources(fixture, attempt)
    before = {path.relative_to(attempt).as_posix(): digest(path)
              for path in attempt.rglob('*') if path.is_file()}
    command = [sys.executable, str(REPO / 'runtime.py'), 'process-saved',
               '--manifest', str(MANIFEST), '--case', CASE,
               '--attempt', str(attempt), '--output', str(output),
               '--library', str(REPO / 'runtime/library'),
               '--validator', str(REPO / '.runtime-work/c125714-validator/.lake/build/bin/adapterCheck')]
    process = subprocess.run(command, cwd=REPO, capture_output=True, text=True)
    (ROOT / 'saved-first.log').write_text(process.stdout + process.stderr)
    if process.returncode:
        raise ValueError('First exact C10365 saved processing failed')
    receipt = json.loads(process.stdout)
    if (receipt.get('case_id') != CASE or not receipt.get('passed')
            or receipt.get('candidate_id') != 'primary'
            or receipt.get('physical_acceptance_claimed')
            or receipt.get('legal_acceptance_claimed')
            or not receipt.get('originals_preserved')
            or any(digest(attempt / path) != value for path, value in before.items())):
        raise ValueError('First exact C10365 saved receipt/original source differs')
    (ROOT / 'saved-first.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print('First exact C10365 marked diagnostic saved processing passed with originals preserved')


if __name__ == '__main__':
    main()
