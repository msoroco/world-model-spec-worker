"""Run exact CPU primary, fallback and saved proofs for three timing points."""
from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
PY = str(REPO / '.venv-cpu/bin/python')
sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))
from worker_exchange.runtime_cli import materialize
from worker_exchange.fixture_recipe import materialize as materialize_fixture

def sha(path):
    return sha256(Path(path).read_bytes()).hexdigest()

def run(command, log):
    with log.open('w') as stream:
        subprocess.run(command, cwd=REPO, stdout=stream,
                       stderr=subprocess.STDOUT, check=True)

for activation in (2, 4, 6):
    prefix = f'indicator-activation-{activation}f'
    manifest_path = HERE / f'{prefix}-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    entry = manifest['cases'][0]
    case = entry['case_id']
    for candidate in (None, 'fallback1', 'fallback2', 'fallback3'):
        name = candidate or 'primary'
        row = entry if candidate is None else next(item for item in entry['candidates']
                                                   if item['id'] == candidate)
        output = f'.runtime-work/c111603-{prefix}-{name}-offline-a'
        command = [PY, 'runtime.py', 'offline', '--manifest', str(manifest_path.relative_to(REPO)),
                   '--case', case, '--output', output, '--python', PY]
        if candidate:
            command += ['--candidate', candidate]
        log = HERE / f'{prefix}-{name}-offline.log'
        run(command, log)
        row['offline'] = {'command': ' '.join(command), 'exit_code': 0, 'log': log.name,
                          'log_sha256': sha(log), 'construction_sha256': row['construction_sha256']}

        output = f'.runtime-work/c111603-{prefix}-{name}-compat-a'
        command = [PY, 'runtime.py', 'compatibility', '--manifest',
                   str(manifest_path.relative_to(REPO)), '--case', case,
                   '--output', output, '--library', 'runtime/library',
                   '--validator', '.runtime-work/fire-decoder/.lake/build/bin/adapterCheck']
        if candidate:
            command += ['--candidate', candidate]
        log = HERE / f'{prefix}-{name}-compatibility.log'
        run(command, log)
        attempt = REPO / output
        receipt = HERE / f'{prefix}-{name}-receipt.json'
        analysis = HERE / f'{prefix}-{name}-analysis.log'
        negative = HERE / f'{prefix}-{name}-negative.log'
        shutil.copy2(attempt / 'compatibility.json', receipt)
        shutil.copy2(attempt / 'compatibility-analysis.log', analysis)
        shutil.copy2(attempt / 'negative-analysis.log', negative)
        row['compatibility'] = {'receipt': receipt.name, 'sha256': sha(receipt),
                                'log': analysis.name, 'negative_log': negative.name}
        if candidate is None:
            entry['negative'] = {'log': negative.name}
        print(activation, name, 'offline and compatibility passed', flush=True)

    attempt = REPO / f'.runtime-work/c111603-{prefix}-saved-attempt-a'
    materialize(manifest_path, case, attempt)
    with tempfile.TemporaryDirectory(prefix=f'c111603-{prefix}-source-',
                                     dir=REPO / '.runtime-work') as temporary:
        source = Path(temporary) / 'fixture'
        materialize_fixture(REPO, HERE / f'{prefix}-recipe.json', source)
        for path in source.iterdir():
            destination = attempt / path.name
            if destination.exists():
                raise ValueError('Diagnostic source shadows construction: ' + path.name)
            if path.is_dir():
                shutil.copytree(path, destination)
            else:
                shutil.copy2(path, destination)
    command = [PY, 'runtime.py', 'process-saved', '--manifest',
               str(manifest_path.relative_to(REPO)), '--case', case,
               '--attempt', str(attempt.relative_to(REPO)),
               '--output', f'.runtime-work/c111603-{prefix}-saved-a',
               '--library', 'runtime/library',
               '--validator', '.runtime-work/fire-decoder/.lake/build/bin/adapterCheck']
    log = HERE / f'{prefix}-saved.log'
    run(command, log)
    version = REPO / f'.runtime-work/c111603-{prefix}-saved-a/v0001'
    receipt = HERE / f'{prefix}-saved-receipt.json'
    shutil.copy2(version / 'processing.json', receipt)
    saved = json.loads(receipt.read_text())
    assert saved['passed'] and saved['originals_preserved'] and not saved['missing_evidence']
    entry['saved_processing'] = {'command': ' '.join(command), 'exit_code': 0,
                                 'log': log.name, 'log_sha256': sha(log),
                                 'receipt': receipt.name, 'receipt_sha256': sha(receipt)}
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
    print(activation, 'saved processing passed', flush=True)
