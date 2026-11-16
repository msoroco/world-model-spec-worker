"""Bind a placement member's exact compatibility and fresh saved proof."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MANIFEST = ROOT / 'indication-provisional-manifest.json'
PYTHON = str(REPO / '.venv-cpu/bin/python')
sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))
from worker_exchange.runtime_cli import materialize
from worker_exchange.fixture_recipe import materialize as materialize_fixture


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def prove(point):
    stem = 'c126064_indication_offset-' + point
    case = ROOT.name + '__' + stem
    manifest = json.loads(MANIFEST.read_text())
    entry = next(e for e in manifest['cases'] if e['case_id'] == case)
    compatible = REPO / ('.runtime-work/c126064-indication-offset-' + point + '-compatibility' +
                         ('-3' if point == '0000' else ''))
    receipt = ROOT / (stem + '-compatibility-receipt.json')
    analysis_log = ROOT / (stem + '-compatibility-analysis.log')
    negative_log = ROOT / (stem + '-negative.log')
    shutil.copy2(compatible / 'compatibility-analysis.log', analysis_log)
    shutil.copy2(compatible / 'negative-analysis.log', negative_log)
    if not json.loads(receipt.read_text())['passed']:
        raise ValueError('Exact primary compatibility did not pass')
    if digest(negative_log) != json.loads(receipt.read_text())['negative_log_sha256']:
        raise ValueError('Exact missing-source proof changed')
    entry['compatibility'] = {'receipt': receipt.name, 'sha256': digest(receipt),
                              'log': analysis_log.name, 'negative_log': negative_log.name}
    entry['negative'] = {'log': negative_log.name}

    attempt = REPO / ('.runtime-work/c126064-indication-offset-' + point + '-saved-attempt')
    output = REPO / ('.runtime-work/c126064-indication-offset-' + point + '-saved')
    materialize(MANIFEST, case, attempt)
    with TemporaryDirectory(prefix='c126064-indication-source-', dir=REPO / '.runtime-work') as td:
        fixture = Path(td) / 'fixture'
        materialize_fixture(REPO, ROOT / (stem + '-recipe.json'), fixture)
        for source in fixture.iterdir():
            target = attempt / source.name
            if target.exists():
                raise ValueError('Diagnostic source shadows construction')
            if source.is_dir():
                shutil.copytree(source, target)
            else:
                shutil.copy2(source, target)
    command = [PYTHON, 'runtime.py', 'process-saved', '--manifest',
               str(MANIFEST.relative_to(REPO)), '--case', case,
               '--attempt', str(attempt.relative_to(REPO)),
               '--output', str(output.relative_to(REPO)),
               '--library', 'runtime/library', '--validator',
               '.runtime-work/fire-decoder/.lake/build/bin/adapterCheck']
    log = ROOT / (stem + '-saved.log')
    with log.open('w') as stream:
        subprocess.run(command, cwd=REPO, stdout=stream,
                       stderr=subprocess.STDOUT, check=True)
    saved = ROOT / (stem + '-saved-receipt.json')
    shutil.copy2(output / 'v0001/processing.json', saved)
    proof = json.loads(saved.read_text())
    if not (proof['passed'] and proof['originals_preserved'] and
            proof['missing_evidence'] is False):
        raise ValueError('Fresh original saved proof did not pass')
    entry['saved_processing'] = {'command': ' '.join(command), 'exit_code': 0,
                                 'log': log.name, 'log_sha256': digest(log),
                                 'receipt': saved.name, 'receipt_sha256': digest(saved)}
    MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')
    return {'case_id': case, 'compatibility_sha256': digest(receipt),
            'saved_sha256': digest(saved), 'missing_evidence': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--point', choices=('0000', '0001', '0002'), required=True)
    print(json.dumps(prove(parser.parse_args().point), indent=2))
