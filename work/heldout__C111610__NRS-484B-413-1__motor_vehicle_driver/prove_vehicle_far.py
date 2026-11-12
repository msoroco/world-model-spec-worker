"""Bind exact primary offline, source-negative compatibility, and saved proofs."""
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
CASE = ROOT.name + '__vehicle_clearance_far_before_turn'
sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))
from worker_exchange.runtime_cli import materialize
from worker_exchange.fixture_recipe import materialize as fixture_materialize


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def run(command, log):
    with log.open('w') as stream:
        subprocess.run(command, cwd=REPO, stdout=stream, stderr=subprocess.STDOUT, check=True)


def save(manifest):
    MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')


def prove():
    manifest = json.loads(MANIFEST.read_text())
    entry = next(item for item in manifest['cases'] if item['case_id'] == CASE)
    stem = 'vehicle-clearance-far-primary'
    attempt_token = sha256(MANIFEST.read_bytes()).hexdigest()[:10]
    offline = [PY, 'runtime.py', 'offline', '--manifest', str(MANIFEST.relative_to(REPO)),
        '--case', CASE, '--output', f'.runtime-work/c111610-{stem}-offline-{attempt_token}', '--python', PY]
    offline_log = ROOT / (stem + '-offline.log')
    run(offline, offline_log)
    entry['offline'] = {'command': ' '.join(offline), 'exit_code': 0,
        'log': offline_log.name, 'log_sha256': digest(offline_log),
        'construction_sha256': entry['construction_sha256']}
    save(manifest)

    output = REPO / f'.runtime-work/c111610-{stem}-compat-{attempt_token}'
    command = [PY, 'runtime.py', 'compatibility', '--manifest', str(MANIFEST.relative_to(REPO)),
        '--case', CASE, '--output', str(output.relative_to(REPO)), '--library', 'runtime/library',
        '--validator', '.runtime-work/fire-decoder/.lake/build/bin/adapterCheck']
    run(command, ROOT / (stem + '-compatibility-stdout.log'))
    receipt = ROOT / (stem + '-receipt.json')
    negative = ROOT / (stem + '-negative.log')
    shutil.copy2(output / 'compatibility.json', receipt)
    shutil.copy2(output / 'negative-analysis.log', negative)
    analysis = ROOT / 'vehicle-indicator-analysis.log'
    if not analysis.is_file() or digest(analysis) != json.loads(receipt.read_text())['log_sha256']:
        analysis = ROOT / (stem + '-analysis.log')
        shutil.copy2(output / 'compatibility-analysis.log', analysis)
    assert json.loads(receipt.read_text())['passed']
    entry['compatibility'] = {'receipt': receipt.name, 'sha256': digest(receipt),
        'log': analysis.name, 'negative_log': negative.name}
    entry['negative'] = {'log': negative.name}
    save(manifest)

    attempt = REPO / f'.runtime-work/c111610-{stem}-saved-attempt-{attempt_token}'
    materialize(MANIFEST, CASE, attempt)
    with tempfile.TemporaryDirectory(prefix='c111610-vehicle-clearance-source-', dir=REPO / '.runtime-work') as temp:
        fixture = Path(temp) / 'fixture'
        fixture_materialize(REPO, ROOT / 'vehicle-clearance-far-recipe.json', fixture)
        for source in fixture.iterdir():
            target = attempt / source.name
            if target.exists():
                raise ValueError('Diagnostic source shadows construction: ' + source.name)
            if source.is_dir():
                shutil.copytree(source, target)
            else:
                shutil.copy2(source, target)
    saved = REPO / f'.runtime-work/c111610-{stem}-saved-{attempt_token}'
    command = [PY, 'runtime.py', 'process-saved', '--manifest', str(MANIFEST.relative_to(REPO)),
        '--case', CASE, '--attempt', str(attempt.relative_to(REPO)),
        '--output', str(saved.relative_to(REPO)), '--library', 'runtime/library',
        '--validator', '.runtime-work/fire-decoder/.lake/build/bin/adapterCheck']
    saved_log = ROOT / (stem + '-saved.log')
    run(command, saved_log)
    saved_receipt = ROOT / (stem + '-saved-receipt.json')
    shutil.copy2(saved / 'v0001/processing.json', saved_receipt)
    proof = json.loads(saved_receipt.read_text())
    assert proof['passed'] and proof['originals_preserved'] and not proof['missing_evidence']
    entry['saved_processing'] = {'command': ' '.join(command), 'exit_code': 0,
        'log': saved_log.name, 'log_sha256': digest(saved_log),
        'receipt': saved_receipt.name, 'receipt_sha256': digest(saved_receipt)}
    save(manifest)
    return {'case': CASE, 'offline': True, 'compatibility': True, 'saved_processing': True}


def prove_candidates():
    manifest = json.loads(MANIFEST.read_text())
    entry = next(item for item in manifest['cases'] if item['case_id'] == CASE)
    for candidate in entry['candidates']:
        candidate_id = candidate['id']
        stem = 'vehicle-clearance-far-' + candidate_id
        token = uuid4().hex[:10]
        offline = [PY, 'runtime.py', 'offline', '--manifest', str(MANIFEST.relative_to(REPO)),
            '--case', CASE, '--candidate', candidate_id,
            '--output', f'.runtime-work/c111610-{stem}-offline-{token}', '--python', PY]
        offline_log = ROOT / (stem + '-offline.log')
        run(offline, offline_log)
        candidate['offline'] = {'command': ' '.join(offline), 'exit_code': 0,
            'log': offline_log.name, 'log_sha256': digest(offline_log),
            'construction_sha256': candidate['construction_sha256']}
        save(manifest)
        output = REPO / f'.runtime-work/c111610-{stem}-compat-{token}'
        command = [PY, 'runtime.py', 'compatibility', '--manifest', str(MANIFEST.relative_to(REPO)),
            '--case', CASE, '--candidate', candidate_id,
            '--output', str(output.relative_to(REPO)), '--library', 'runtime/library',
            '--validator', '.runtime-work/fire-decoder/.lake/build/bin/adapterCheck']
        run(command, ROOT / (stem + '-compatibility-stdout.log'))
        receipt = ROOT / (stem + '-receipt.json')
        negative = ROOT / (stem + '-negative.log')
        shutil.copy2(output / 'compatibility.json', receipt)
        shutil.copy2(output / 'negative-analysis.log', negative)
        proof = json.loads(receipt.read_text())
        assert proof['passed'] and proof['construction_sha256'] == candidate['construction_sha256']
        analysis = ROOT / 'vehicle-indicator-analysis.log'
        if not analysis.is_file() or digest(analysis) != proof['log_sha256']:
            analysis = ROOT / (stem + '-analysis.log')
            shutil.copy2(output / 'compatibility-analysis.log', analysis)
        candidate['compatibility'] = {'receipt': receipt.name, 'sha256': digest(receipt),
            'log': analysis.name, 'negative_log': negative.name}
        save(manifest)
    return {'case': CASE, 'candidates_proved': [candidate['id'] for candidate in entry['candidates']]}


if __name__ == '__main__':
    print(prove_candidates() if '--candidates' in sys.argv else prove())
