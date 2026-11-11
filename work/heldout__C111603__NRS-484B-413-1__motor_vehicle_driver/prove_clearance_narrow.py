"""Run exact CPU fallback and saved proofs for the narrower-clearance sibling."""
from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
PY = str(REPO / '.venv-cpu/bin/python')
CASE = ROOT.name + '__clearance_narrow'
MANIFEST = ROOT / 'clearance-narrow-manifest.json'
PREFIX = 'clearance-narrow'
sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))
from worker_exchange.runtime_cli import materialize
from worker_exchange.fixture_recipe import materialize as materialize_fixture


def sha(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def run(command, log):
    with Path(log).open('w') as stream:
        subprocess.run(command, cwd=REPO, stdout=stream, stderr=subprocess.STDOUT, check=True)


manifest = json.loads(MANIFEST.read_text())
entry = manifest['cases'][0]
for candidate in entry['candidates']:
    name = candidate['id']
    base = [PY, 'runtime.py', 'offline', '--manifest', str(MANIFEST.relative_to(REPO)),
            '--case', CASE, '--candidate', name]
    output = f'.runtime-work/c111603-clearance-narrow-{name}-offline-b'
    command = base + ['--output', output, '--python', PY]
    log = ROOT / f'{PREFIX}-{name}-offline.log'
    run(command, log)
    candidate['offline'] = {'command': ' '.join(command), 'exit_code': 0, 'log': log.name,
                            'log_sha256': sha(log), 'construction_sha256': candidate['construction_sha256']}
    output = f'.runtime-work/c111603-clearance-narrow-{name}-compat-b'
    command = [PY, 'runtime.py', 'compatibility', '--manifest', str(MANIFEST.relative_to(REPO)),
               '--case', CASE, '--candidate', name, '--output', output,
               '--library', 'runtime/library',
               '--validator', '.runtime-work/fire-decoder/.lake/build/bin/adapterCheck']
    log = ROOT / f'{PREFIX}-{name}-compatibility.log'
    run(command, log)
    receipt = ROOT / f'{PREFIX}-{name}-receipt.json'
    analysis = ROOT / f'{PREFIX}-{name}-analysis.log'
    negative = ROOT / f'{PREFIX}-{name}-negative.log'
    shutil.copy2(REPO / output / 'compatibility.json', receipt)
    shutil.copy2(REPO / output / 'compatibility-analysis.log', analysis)
    shutil.copy2(REPO / output / 'negative-analysis.log', negative)
    candidate['compatibility'] = {'receipt': receipt.name, 'sha256': sha(receipt),
                                  'log': analysis.name, 'negative_log': negative.name}
    print(name, 'offline and compatibility passed', flush=True)

# A fresh source-complete attempt is materialized independently from compatibility.
attempt = REPO / '.runtime-work/c111603-clearance-narrow-saved-attempt-a'
materialize(MANIFEST, CASE, attempt)
with tempfile.TemporaryDirectory(prefix='c111603-clearance-narrow-source-', dir=REPO / '.runtime-work') as temporary:
    source = Path(temporary) / 'fixture'
    materialize_fixture(REPO, ROOT / f'{PREFIX}-recipe.json', source)
    for path in source.iterdir():
        destination = attempt / path.name
        if destination.exists():
            raise ValueError('Diagnostic source shadows construction: ' + path.name)
        if path.is_dir():
            shutil.copytree(path, destination)
        else:
            shutil.copy2(path, destination)
command = [PY, 'runtime.py', 'process-saved', '--manifest', str(MANIFEST.relative_to(REPO)),
           '--case', CASE, '--attempt', str(attempt.relative_to(REPO)),
           '--output', '.runtime-work/c111603-clearance-narrow-saved-a',
           '--library', 'runtime/library',
           '--validator', '.runtime-work/fire-decoder/.lake/build/bin/adapterCheck']
log = ROOT / f'{PREFIX}-saved.log'
run(command, log)
version = REPO / '.runtime-work/c111603-clearance-narrow-saved-a/v0001'
receipt = ROOT / f'{PREFIX}-saved-receipt.json'
shutil.copy2(version / 'processing.json', receipt)
saved = json.loads(receipt.read_text())
assert saved['passed'] and saved['originals_preserved'] and not saved['missing_evidence']
entry['saved_processing'] = {'command': ' '.join(command), 'exit_code': 0, 'log': log.name,
                             'log_sha256': sha(log), 'receipt': receipt.name, 'receipt_sha256': sha(receipt)}
MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')
print('Three exact narrower-clearance fallbacks and fresh saved processing passed')
