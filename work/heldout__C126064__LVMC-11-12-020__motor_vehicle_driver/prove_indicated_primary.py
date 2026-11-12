"""Bind first marked-turn primary's exact CPU source and saved proofs."""
from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from uuid import uuid4

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
PY = str(REPO / '.venv-cpu/bin/python')
MANIFEST = ROOT / 'execution-manifest.json'
CASE = ROOT.name + '__indicated_course'
sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))
from worker_exchange.runtime_cli import materialize
from worker_exchange.fixture_recipe import materialize as materialize_fixture


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def run(command, log):
    with (ROOT / log).open('w') as stream:
        subprocess.run(command, cwd=REPO, stdout=stream, stderr=subprocess.STDOUT, check=True)


def prove():
    manifest = json.loads(MANIFEST.read_text())
    entry = next(item for item in manifest['cases'] if item['case_id'] == CASE)
    token = uuid4().hex[:10]
    offline = [PY, 'runtime.py', 'offline', '--manifest', str(MANIFEST.relative_to(REPO)),
        '--case', CASE, '--output', f'.runtime-work/c126064-indicated-offline-{token}', '--python', PY]
    run(offline, 'indicated-offline.log')
    entry['offline'] = {'command': ' '.join(offline), 'exit_code': 0,
        'log': 'indicated-offline.log', 'log_sha256': digest(ROOT / 'indicated-offline.log'),
        'construction_sha256': entry['construction_sha256']}
    MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')
    compat_output = REPO / f'.runtime-work/c126064-indicated-compat-{token}'
    compat = [PY, 'runtime.py', 'compatibility', '--manifest', str(MANIFEST.relative_to(REPO)),
        '--case', CASE, '--output', str(compat_output.relative_to(REPO)),
        '--library', 'runtime/library',
        '--validator', '.runtime-work/fire-decoder/.lake/build/bin/adapterCheck']
    run(compat, 'indicated-compatibility-stdout.log')
    for source, target in [('compatibility.json', 'indicated-compatibility-receipt.json'),
                           ('compatibility-analysis.log', 'indicated-compatibility-analysis.log'),
                           ('negative-analysis.log', 'indicated-compatibility-negative.log')]:
        shutil.copy2(compat_output / source, ROOT / target)
    receipt = ROOT / 'indicated-compatibility-receipt.json'
    assert json.loads(receipt.read_text())['passed']
    entry['compatibility'] = {'receipt': receipt.name, 'sha256': digest(receipt),
        'log': 'indicated-compatibility-analysis.log',
        'negative_log': 'indicated-compatibility-negative.log'}
    entry['negative'] = {'log': 'indicated-compatibility-negative.log'}
    MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')
    attempt = REPO / f'.runtime-work/c126064-indicated-saved-attempt-{token}'
    materialize(MANIFEST, CASE, attempt)
    with tempfile.TemporaryDirectory(prefix='c126064-indicated-source-', dir=REPO / '.runtime-work') as temp:
        fixture = Path(temp) / 'fixture'
        materialize_fixture(REPO, ROOT / 'indicated-recipe.json', fixture)
        for source in fixture.iterdir():
            target = attempt / source.name
            if target.exists():
                raise ValueError('Diagnostic source shadows marked-turn construction: ' + source.name)
            if source.is_dir():
                shutil.copytree(source, target)
            else:
                shutil.copy2(source, target)
    saved_output = REPO / f'.runtime-work/c126064-indicated-saved-{token}'
    saved = [PY, 'runtime.py', 'process-saved', '--manifest', str(MANIFEST.relative_to(REPO)),
        '--case', CASE, '--attempt', str(attempt.relative_to(REPO)),
        '--output', str(saved_output.relative_to(REPO)), '--library', 'runtime/library',
        '--validator', '.runtime-work/fire-decoder/.lake/build/bin/adapterCheck']
    run(saved, 'indicated-saved.log')
    saved_receipt = ROOT / 'indicated-saved-receipt.json'
    shutil.copy2(saved_output / 'v0001/processing.json', saved_receipt)
    proof = json.loads(saved_receipt.read_text())
    assert proof['passed'] and proof['originals_preserved'] and not proof['missing_evidence']
    entry['saved_processing'] = {'command': ' '.join(saved), 'exit_code': 0,
        'log': 'indicated-saved.log', 'log_sha256': digest(ROOT / 'indicated-saved.log'),
        'receipt': saved_receipt.name, 'receipt_sha256': digest(saved_receipt)}
    MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')
    return {'case': CASE, 'offline': True, 'compatibility': True, 'saved_processing': True}


if __name__ == '__main__':
    print(prove())
