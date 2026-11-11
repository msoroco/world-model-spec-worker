"""Reprocess all seven exact officer cases from retained synthetic sources."""
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from worker_exchange.fixture_recipe import materialize as fixture_materialize
from worker_exchange.runtime_cli import materialize
from worker_exchange.saved_processing import copy_sources

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MANIFEST = ROOT / 'execution-manifest.json'
VALIDATOR = REPO / '.runtime-work/c125714-validator/.lake/build/bin/adapterCheck'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest['cases']:
        case = entry['case_id']
        slug = case.split('__')[-1]
        attempt = REPO / '.runtime-work' / f'c10365-{slug}-delivery-attempt-v9'
        output = REPO / '.runtime-work' / f'c10365-{slug}-delivery-output-v9'
        materialize(MANIFEST, case, attempt)
        with tempfile.TemporaryDirectory(dir=REPO / '.runtime-work', prefix='officer-source-') as temporary:
            fixture = Path(temporary) / 'source'
            fixture_materialize(REPO, REPO / entry['fixture_recipe'], fixture)
            copy_sources(fixture, attempt)
        originals = {path.relative_to(attempt).as_posix(): sha(path)
                     for path in attempt.rglob('*') if path.is_file()}
        command = [sys.executable, str(REPO / 'runtime.py'), 'process-saved',
                   '--manifest', str(MANIFEST), '--case', case,
                   '--attempt', str(attempt), '--output', str(output),
                   '--library', str(REPO / 'runtime/library'), '--validator', str(VALIDATOR)]
        completed = subprocess.run(command, cwd=REPO, capture_output=True, text=True)
        log = ROOT / 'cases' / f'delivery-saved-{slug}.log'
        log.write_text(completed.stdout + completed.stderr)
        if completed.returncode:
            raise ValueError('Exact saved delivery proof failed: ' + str(log))
        result = json.loads(completed.stdout)
        if (not result.get('passed') or result.get('case_id') != case
                or result.get('physical_acceptance_claimed') or result.get('legal_acceptance_claimed')
                or not result.get('originals_preserved')
                or any(sha(attempt / name) != value for name, value in originals.items())):
            raise ValueError('Exact saved delivery source or identity changed: ' + case)
        receipt = ROOT / 'cases' / f'delivery-saved-{slug}.json'
        receipt.write_text(json.dumps(result, indent=2) + '\n')
        print(slug, 'saved-only delivery proof passes', flush=True)


if __name__ == '__main__':
    main()
