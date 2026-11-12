"""Pinned process-saved proof for first sweep primary in an isolated package copy."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
PYTHON = REPO / '.venv-cpu/bin/python'
sys.path.insert(0, str(REPO / 'runtime/pipeline/scenario_pipeline'))
from worker_exchange.fixture_recipe import materialize as make_fixture
from worker_exchange.runtime_cli import materialize as make_package
from worker_exchange.saved_processing import copy_sources


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def copy(relative, folder):
    target = folder / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(HERE / relative, target)


def main():
    source_manifest = HERE / 'sweep-execution-candidate.json'
    source = json.loads(source_manifest.read_text())
    case = source['cases'][0]
    validator = REPO / '.runtime-work/decoder-update015-c10316/.lake/build/bin/adapterCheck'
    if not validator.is_file():
        raise ValueError('Pinned diagnostic validator missing')
    with tempfile.TemporaryDirectory(prefix='c111256-sweep-process-', dir=REPO / '.runtime-work') as scratch:
        mini = Path(scratch)
        folder = mini / 'work' / HERE.name
        folder.mkdir(parents=True)
        write(folder / 'proposals/cases.json',
              json.loads((HERE / 'proposals/sweep-stage-candidate.json').read_text()))
        for relative in ('update028-sweep-diagnostic.json', 'update028-sweep-recipe.json',
                         case['measurement_contract'], case['construction']):
            copy(relative, folder)
        manifest = folder / 'execution-manifest.json'
        write(manifest, source)
        fixture = mini / '.runtime-work/source-fixture'
        attempt = mini / '.runtime-work/selected-attempt'
        output = mini / '.runtime-work/processed'
        make_fixture(mini, folder / 'update028-sweep-recipe.json', fixture)
        make_package(manifest, case['case_id'], attempt, 'primary')
        copy_sources(fixture, attempt)
        command = [str(PYTHON), str(REPO / 'runtime.py'), 'process-saved',
                   '--manifest', str(manifest), '--case', case['case_id'],
                   '--attempt', str(attempt), '--output', str(output),
                   '--library', str(REPO / 'runtime/pipeline/library'),
                   '--validator', str(validator)]
        run = subprocess.run(command, cwd=REPO, capture_output=True,
                             text=True, timeout=600)
        log = HERE / 'update028-sweep-staged-process-saved.log'
        log.write_text(run.stdout + run.stderr)
        if run.returncode:
            raise ValueError('Pinned sweep process-saved failed: ' + (run.stdout + run.stderr)[-1300:])
        receipt = output / 'v0001/processing.json'
        if not receipt.is_file():
            raise ValueError('Pinned saved processing receipt missing')
        value = json.loads(receipt.read_text())
        if (value.get('passed') is not True or value.get('recorded_only') is not True or
                value.get('case_id') != case['case_id'] or
                value.get('missing_evidence') is not False or
                value.get('physical_acceptance_claimed') is not False):
            raise ValueError('Pinned saved processing receipt incomplete')
        proof = {'format': 'c111256-staged-sweep-process-saved-v1',
                 'case_id': case['case_id'], 'candidate_id': 'primary',
                 'staged_manifest_sha256': sha(source_manifest),
                 'analysis_revision_construction_sha256': value['analysis_revision']['construction_sha256'],
                 'processing_receipt_sha256': sha(receipt),
                 'log_sha256': sha(log), 'recorded_only': True,
                 'staging_copy_only': True, 'original_recordings_accepted': 0}
    path = HERE / 'update028-sweep-staged-process-saved-proof.json'
    write(path, proof)
    print(json.dumps({'proof': path.name, 'sha256': sha(path),
                      'recorded_only': True, 'staging_copy_only': True}, sort_keys=True))


if __name__ == '__main__':
    main()
