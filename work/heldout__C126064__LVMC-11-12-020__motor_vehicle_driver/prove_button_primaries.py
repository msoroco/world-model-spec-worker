"""Prove exact button cases through source-bound compatibility and saved processing."""
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
sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))
from worker_exchange.runtime_cli import materialize
from worker_exchange.fixture_recipe import materialize as materialize_fixture


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def run(command, log):
    with (ROOT / log).open('w') as stream:
        subprocess.run(command, cwd=REPO, stdout=stream,
                       stderr=subprocess.STDOUT, check=True)


def prove():
    manifest = json.loads(MANIFEST.read_text())
    token = uuid4().hex[:10]
    results = {}
    for variant, stem in (('indicated_course', 'button-indicated'),
                          ('divergent_course', 'button-divergent')):
        case = ROOT.name + '__button_' + variant
        entry = next(e for e in manifest['cases'] if e['case_id'] == case)
        output = REPO / f'.runtime-work/c126064-{stem}-compat-{token}'
        compat = [PY, 'runtime.py', 'compatibility', '--manifest',
                  str(MANIFEST.relative_to(REPO)), '--case', case,
                  '--output', str(output.relative_to(REPO)), '--library',
                  'runtime/library', '--validator',
                  '.runtime-work/fire-decoder/.lake/build/bin/adapterCheck']
        run(compat, stem + '-compatibility-stdout.log')
        for source, target in [('compatibility.json', stem + '-compatibility-receipt.json'),
                               ('compatibility-analysis.log', stem + '-compatibility-analysis.log'),
                               ('negative-analysis.log', stem + '-compatibility-negative.log')]:
            shutil.copy2(output / source, ROOT / target)
        receipt = ROOT / (stem + '-compatibility-receipt.json')
        assert json.loads(receipt.read_text())['passed']
        entry['compatibility'] = {'receipt': receipt.name, 'sha256': digest(receipt),
            'log': stem + '-compatibility-analysis.log',
            'negative_log': stem + '-compatibility-negative.log'}
        entry['negative'] = {'log': stem + '-compatibility-negative.log'}
        MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')

        attempt = REPO / f'.runtime-work/c126064-{stem}-saved-attempt-{token}'
        materialize(MANIFEST, case, attempt)
        with tempfile.TemporaryDirectory(prefix=f'c126064-{stem}-source-',
                                         dir=REPO / '.runtime-work') as temp:
            fixture = Path(temp) / 'fixture'
            materialize_fixture(REPO, ROOT / (stem + '-recipe.json'), fixture)
            for source in fixture.iterdir():
                target = attempt / source.name
                if target.exists():
                    raise ValueError('Diagnostic shadows construction: ' + source.name)
                if source.is_dir():
                    shutil.copytree(source, target)
                else:
                    shutil.copy2(source, target)
        saved_output = REPO / f'.runtime-work/c126064-{stem}-saved-{token}'
        saved = [PY, 'runtime.py', 'process-saved', '--manifest',
                 str(MANIFEST.relative_to(REPO)), '--case', case,
                 '--attempt', str(attempt.relative_to(REPO)),
                 '--output', str(saved_output.relative_to(REPO)),
                 '--library', 'runtime/library', '--validator',
                 '.runtime-work/fire-decoder/.lake/build/bin/adapterCheck']
        run(saved, stem + '-saved.log')
        processing = ROOT / (stem + '-saved-receipt.json')
        shutil.copy2(saved_output / 'v0001/processing.json', processing)
        proof = json.loads(processing.read_text())
        assert proof['passed'] and proof['originals_preserved'] and not proof['missing_evidence']
        entry['saved_processing'] = {'command': ' '.join(saved), 'exit_code': 0,
            'log': stem + '-saved.log', 'log_sha256': digest(ROOT / (stem + '-saved.log')),
            'receipt': processing.name, 'receipt_sha256': digest(processing)}
        MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')
        results[case] = {'compatibility_sha256': digest(receipt),
                         'saved_processing_sha256': digest(processing)}
    return results


if __name__ == '__main__':
    print(json.dumps(prove(), indent=2))
