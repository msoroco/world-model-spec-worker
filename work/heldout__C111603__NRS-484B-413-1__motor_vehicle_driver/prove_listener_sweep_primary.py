"""Run fresh saved-only CPU processing for three route-relative listener primaries."""
from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PY = str(ROOT / '.venv-cpu/bin/python')
sys.path.insert(0, str(ROOT / 'runtime/scenario_pipeline'))
from worker_exchange.runtime_cli import materialize
from worker_exchange.fixture_recipe import materialize as materialize_fixture


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


for offset in (2, 4, 6):
    prefix = f'listener-{offset}m'
    case = HERE.name + f'__ped_horn_listener_{offset}m'
    manifest_path = HERE / f'{prefix}-manifest.json'
    attempt = ROOT / f'.runtime-work/c111603-{prefix}-saved-attempt-b'
    output = ROOT / f'.runtime-work/c111603-{prefix}-saved-output-b'
    materialize(manifest_path, case, attempt)
    with tempfile.TemporaryDirectory(prefix=f'c111603-{prefix}-fixture-', dir=ROOT / '.runtime-work') as temp:
        fixture = Path(temp) / 'fixture'
        materialize_fixture(ROOT, HERE / f'{prefix}-recipe.json', fixture)
        for path in fixture.iterdir():
            destination = attempt / path.name
            if destination.exists():
                raise ValueError('Diagnostic source shadows construction')
            if path.is_dir():
                shutil.copytree(path, destination)
            else:
                shutil.copy2(path, destination)
    command = [PY, 'runtime.py', 'process-saved', '--manifest', str(manifest_path.relative_to(ROOT)),
               '--case', case, '--attempt', str(attempt.relative_to(ROOT)),
               '--output', str(output.relative_to(ROOT)), '--library', 'runtime/library',
               '--validator', '.runtime-work/fire-decoder/.lake/build/bin/adapterCheck']
    log = HERE / f'{prefix}-saved.log'
    with log.open('w') as stream:
        subprocess.run(command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT, check=True)
    receipt = HERE / f'{prefix}-saved-receipt.json'
    shutil.copy2(output / 'v0001/processing.json', receipt)
    data = json.loads(receipt.read_text())
    if not (data['case_id'] == case and data['passed'] and data['originals_preserved']
            and not data['missing_evidence']):
        raise ValueError('Listener sweep saved processing incomplete')
    print(case, digest(receipt), flush=True)
