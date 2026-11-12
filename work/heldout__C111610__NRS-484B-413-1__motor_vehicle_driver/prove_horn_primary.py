"""Prove the pedestrian-horn primary from separately materialized saved originals."""
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
CASE = ROOT.name + '__pedestrian_horn_before_turn'
MANIFEST = ROOT / 'execution-manifest.json'
sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))
from worker_exchange.runtime_cli import materialize
from worker_exchange.fixture_recipe import materialize as materialize_fixture

def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()

manifest = json.loads(MANIFEST.read_text())
entry = manifest['cases'][0]
compat = REPO / '.runtime-work/c111610-horn-primary-compat-v1'
assert json.loads((compat / 'compatibility.json').read_text())['passed']
for source, target in [('compatibility.json','pedestrian-horn-primary-receipt.json'), ('compatibility-analysis.log','pedestrian-horn-primary-analysis.log'), ('negative-analysis.log','pedestrian-horn-primary-negative.log')]:
    shutil.copy2(compat / source, ROOT / target)
entry['compatibility'] = {'receipt':'pedestrian-horn-primary-receipt.json', 'sha256': digest(ROOT / 'pedestrian-horn-primary-receipt.json'), 'log':'pedestrian-horn-primary-analysis.log', 'negative_log':'pedestrian-horn-primary-negative.log'}
entry['negative'] = {'log':'pedestrian-horn-primary-negative.log'}

attempt = REPO / '.runtime-work/c111610-horn-primary-saved-attempt-v1'
materialize(MANIFEST, CASE, attempt)
with tempfile.TemporaryDirectory(prefix='c111610-horn-source-', dir=REPO / '.runtime-work') as temporary:
    source = Path(temporary) / 'fixture'
    materialize_fixture(REPO, ROOT / 'pedestrian-horn-recipe.json', source)
    for path in source.iterdir():
        destination = attempt / path.name
        if destination.exists():
            raise ValueError('Diagnostic source shadows construction: ' + path.name)
        if path.is_dir():
            shutil.copytree(path, destination)
        else:
            shutil.copy2(path, destination)
command = [PY, 'runtime.py', 'process-saved', '--manifest', str(MANIFEST.relative_to(REPO)), '--case', CASE, '--attempt', str(attempt.relative_to(REPO)), '--output', '.runtime-work/c111610-horn-primary-saved-v1', '--library', 'runtime/library', '--validator', '.runtime-work/fire-decoder/.lake/build/bin/adapterCheck']
log = ROOT / 'pedestrian-horn-primary-saved.log'
with log.open('w') as stream:
    subprocess.run(command, cwd=REPO, stdout=stream, stderr=subprocess.STDOUT, check=True)
receipt = ROOT / 'pedestrian-horn-primary-saved-receipt.json'
shutil.copy2(REPO / '.runtime-work/c111610-horn-primary-saved-v1/v0001/processing.json', receipt)
saved = json.loads(receipt.read_text())
assert saved['passed'] and saved['originals_preserved'] and not saved['missing_evidence']
entry['saved_processing'] = {'command':' '.join(command), 'exit_code':0, 'log':log.name, 'log_sha256':digest(log), 'receipt':receipt.name, 'receipt_sha256':digest(receipt)}
MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')
print('primary compatibility and independently materialized saved processing passed')
