"""Reprove the exact hand-signal construction and all three candidates."""
from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import uuid

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
PY = str(REPO / '.venv-cpu/bin/python')
CASE = ROOT.name + '__vehicle_hand_signal'
MANIFEST = ROOT / 'hand-signal-manifest.json'
PREFIX = 'hand-signal'
sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))
from worker_exchange.runtime_cli import materialize
from worker_exchange.fixture_recipe import materialize as materialize_fixture


def sha(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def run(command, log):
    with log.open('w') as stream:
        subprocess.run(command, cwd=REPO, stdout=stream,
                       stderr=subprocess.STDOUT, check=True)


manifest = json.loads(MANIFEST.read_text())
entry = manifest['cases'][0]
for name in ('primary', 'fallback1', 'fallback2', 'fallback3'):
    selected = entry if name == 'primary' else next(c for c in entry['candidates'] if c['id'] == name)
    candidate_args = [] if name == 'primary' else ['--candidate', name]
    run_id = uuid.uuid4().hex[:8]
    offline_command = [PY, 'runtime.py', 'offline', '--manifest', str(MANIFEST.relative_to(REPO)),
                       '--case', CASE, *candidate_args,
                       '--output', f'.runtime-work/c111603-hand-{name}-{run_id}-offline', '--python', PY]
    offline_log = ROOT / f'{PREFIX}-{name}-offline.log'
    run(offline_command, offline_log)
    selected['offline'] = {'command': ' '.join(offline_command), 'exit_code': 0,
                           'log': offline_log.name, 'log_sha256': sha(offline_log),
                           'construction_sha256': selected['construction_sha256']}
    compat_command = [PY, 'runtime.py', 'compatibility', '--manifest', str(MANIFEST.relative_to(REPO)),
                      '--case', CASE, *candidate_args,
                      '--output', f'.runtime-work/c111603-hand-{name}-{run_id}-compat',
                      '--library', 'runtime/library',
                      '--validator', '.runtime-work/fire-decoder/.lake/build/bin/adapterCheck']
    compat_log = ROOT / f'{PREFIX}-{name}-compatibility.log'
    run(compat_command, compat_log)
    output = REPO / compat_command[compat_command.index('--output') + 1]
    receipt = ROOT / f'{PREFIX}-{name}-receipt.json'
    analysis = ROOT / f'{PREFIX}-{name}-analysis.log'
    negative = ROOT / f'{PREFIX}-{name}-negative.log'
    shutil.copy2(output / 'compatibility.json', receipt)
    shutil.copy2(output / 'compatibility-analysis.log', analysis)
    shutil.copy2(output / 'negative-analysis.log', negative)
    selected['compatibility'] = {'receipt': receipt.name, 'sha256': sha(receipt),
                                 'log': analysis.name, 'negative_log': negative.name}
    print(name, 'offline and positive/missing-hand-source compatibility passed', flush=True)

MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')
run_id = uuid.uuid4().hex[:8]
attempt = REPO / f'.runtime-work/c111603-hand-saved-attempt-{run_id}'
materialize(MANIFEST, CASE, attempt)
with tempfile.TemporaryDirectory(prefix='c111603-hand-source-', dir=REPO / '.runtime-work') as temporary:
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
saved_command = [PY, 'runtime.py', 'process-saved', '--manifest', str(MANIFEST.relative_to(REPO)),
                 '--case', CASE, '--attempt', str(attempt.relative_to(REPO)),
                 '--output', f'.runtime-work/c111603-hand-saved-{run_id}',
                 '--library', 'runtime/library',
                 '--validator', '.runtime-work/fire-decoder/.lake/build/bin/adapterCheck']
saved_log = ROOT / f'{PREFIX}-saved.log'
run(saved_command, saved_log)
version = REPO / saved_command[saved_command.index('--output') + 1] / 'v0001'
saved_receipt = ROOT / f'{PREFIX}-saved-receipt.json'
shutil.copy2(version / 'processing.json', saved_receipt)
saved = json.loads(saved_receipt.read_text())
assert saved['passed'] and saved['originals_preserved'] and not saved['missing_evidence']
entry['saved_processing'] = {'command': ' '.join(saved_command), 'exit_code': 0,
                             'log': saved_log.name, 'log_sha256': sha(saved_log),
                             'receipt': saved_receipt.name, 'receipt_sha256': sha(saved_receipt)}
MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')
print('Hand-signal saved processing passed with retained original sources')
