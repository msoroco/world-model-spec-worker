"""Bind the late-horn exact primary to current offline, compatibility and saved receipts."""
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
CASE = ROOT.name + '__pedestrian_horn_after_onset'
sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))
from worker_exchange.runtime_cli import materialize
from worker_exchange.fixture_recipe import materialize as fixture_materialize


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def run(command, log):
    with log.open('w') as out:
        subprocess.run(command, cwd=REPO, stdout=out, stderr=subprocess.STDOUT, check=True)


def main():
    manifest = json.loads(MANIFEST.read_text())
    entry = next(item for item in manifest['cases'] if item['case_id'] == CASE)
    stem = 'pedestrian-horn-late-primary'
    token = entry['construction_sha256'][:10]
    relative = str(MANIFEST.relative_to(REPO))
    offline = [PY, 'runtime.py', 'offline', '--manifest', relative, '--case', CASE,
               '--output', f'.runtime-work/c111610-{stem}-offline-{token}', '--python', PY]
    offline_log = ROOT / (stem + '-offline.log')
    run(offline, offline_log)
    entry['offline'] = {'command': ' '.join(offline), 'exit_code': 0, 'log': offline_log.name,
                        'log_sha256': digest(offline_log),
                        'construction_sha256': entry['construction_sha256']}
    MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')

    compat_output = REPO / f'.runtime-work/c111610-{stem}-compat-{token}'
    compat = [PY, 'runtime.py', 'compatibility', '--manifest', relative, '--case', CASE,
              '--output', str(compat_output.relative_to(REPO)), '--library', 'runtime/library',
              '--validator', '.runtime-work/fire-decoder/.lake/build/bin/adapterCheck']
    run(compat, ROOT / (stem + '-stdout.log'))
    receipt = ROOT / (stem + '-receipt.json')
    negative = ROOT / (stem + '-negative.log')
    shutil.copy2(compat_output / 'compatibility.json', receipt)
    shutil.copy2(compat_output / 'negative-analysis.log', negative)
    proof = json.loads(receipt.read_text())
    if not proof['passed'] or proof['construction_sha256'] != entry['construction_sha256']:
        raise ValueError('Late horn source compatibility failed')
    analysis = ROOT / 'vehicle-indicator-analysis.log'
    if not analysis.is_file() or digest(analysis) != proof['log_sha256']:
        analysis = ROOT / (stem + '-analysis.log')
        shutil.copy2(compat_output / 'compatibility-analysis.log', analysis)
    entry['compatibility'] = {'receipt': receipt.name, 'sha256': digest(receipt),
                              'log': analysis.name, 'negative_log': negative.name}
    entry['negative'] = {'log': negative.name}
    MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')

    attempt = REPO / f'.runtime-work/c111610-{stem}-attempt-{token}'
    materialize(MANIFEST, CASE, attempt)
    with tempfile.TemporaryDirectory(dir=REPO / '.runtime-work', prefix='c111610-late-source-') as temp:
        fixture = Path(temp) / 'fixture'
        fixture_materialize(REPO, ROOT / 'pedestrian-horn-late-recipe.json', fixture)
        for source in fixture.iterdir():
            target = attempt / source.name
            if target.exists():
                raise ValueError('Fixture source shadows construction: ' + source.name)
            shutil.copytree(source, target) if source.is_dir() else shutil.copy2(source, target)
    saved_output = REPO / f'.runtime-work/c111610-{stem}-saved-{token}'
    saved = [PY, 'runtime.py', 'process-saved', '--manifest', relative, '--case', CASE,
             '--attempt', str(attempt.relative_to(REPO)), '--output', str(saved_output.relative_to(REPO)),
             '--library', 'runtime/library', '--validator',
             '.runtime-work/fire-decoder/.lake/build/bin/adapterCheck']
    saved_log = ROOT / (stem + '-saved.log')
    run(saved, saved_log)
    saved_receipt = ROOT / (stem + '-saved-receipt.json')
    shutil.copy2(saved_output / 'v0001/processing.json', saved_receipt)
    result = json.loads(saved_receipt.read_text())
    if not (result['passed'] and result['originals_preserved'] and not result['missing_evidence']):
        raise ValueError('Late horn saved processing failed')
    entry['saved_processing'] = {'command': ' '.join(saved), 'exit_code': 0,
                                 'log': saved_log.name, 'log_sha256': digest(saved_log),
                                 'receipt': saved_receipt.name,
                                 'receipt_sha256': digest(saved_receipt)}
    MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')
    print('Late horn primary offline, positive/missing-source compatibility and saved processing passed')


def candidates():
    manifest = json.loads(MANIFEST.read_text())
    entry = next(item for item in manifest['cases'] if item['case_id'] == CASE)
    relative = str(MANIFEST.relative_to(REPO))
    for candidate in entry['candidates']:
        ident = candidate['id']
        stem = 'pedestrian-horn-late-' + ident
        token = uuid4().hex[:10]
        offline = [PY, 'runtime.py', 'offline', '--manifest', relative, '--case', CASE,
                   '--candidate', ident, '--output', f'.runtime-work/c111610-{stem}-offline-{token}',
                   '--python', PY]
        offline_log = ROOT / (stem + '-offline.log')
        run(offline, offline_log)
        candidate['offline'] = {'command': ' '.join(offline), 'exit_code': 0,
                                'log': offline_log.name, 'log_sha256': digest(offline_log),
                                'construction_sha256': candidate['construction_sha256']}
        MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')
        output = REPO / f'.runtime-work/c111610-{stem}-compat-{token}'
        command = [PY, 'runtime.py', 'compatibility', '--manifest', relative, '--case', CASE,
                   '--candidate', ident, '--output', str(output.relative_to(REPO)),
                   '--library', 'runtime/library', '--validator',
                   '.runtime-work/fire-decoder/.lake/build/bin/adapterCheck']
        # Compatibility stdout stays in ignored work; returned receipts bind the analysis and rejection.
        run(command, REPO / f'.runtime-work/c111610-{stem}-compat-stdout.log')
        receipt = ROOT / (stem + '-receipt.json')
        negative = ROOT / (stem + '-negative.log')
        shutil.copy2(output / 'compatibility.json', receipt)
        shutil.copy2(output / 'negative-analysis.log', negative)
        proof = json.loads(receipt.read_text())
        if not proof['passed'] or proof['construction_sha256'] != candidate['construction_sha256']:
            raise ValueError('Late horn fallback source compatibility failed: ' + ident)
        analysis = ROOT / 'vehicle-indicator-analysis.log'
        if not analysis.is_file() or digest(analysis) != proof['log_sha256']:
            analysis = ROOT / (stem + '-analysis.log')
            shutil.copy2(output / 'compatibility-analysis.log', analysis)
        candidate['compatibility'] = {'receipt': receipt.name, 'sha256': digest(receipt),
                                      'log': analysis.name, 'negative_log': negative.name}
        MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')
        print(ident, 'offline and positive/missing-source compatibility passed', flush=True)


if __name__ == '__main__':
    candidates() if '--candidates' in sys.argv else main()
