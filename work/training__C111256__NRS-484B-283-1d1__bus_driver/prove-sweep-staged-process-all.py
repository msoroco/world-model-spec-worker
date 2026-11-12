"""Pinned recorded-only process-saved path for all 16 staged sweep bundles."""
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
    validator = REPO / '.runtime-work/decoder-update015-c10316/.lake/build/bin/adapterCheck'
    if not validator.is_file():
        raise ValueError('Pinned diagnostic validator missing')
    matrix_path = HERE / 'update028-sweep-staged-process-matrix.json'
    if matrix_path.exists():
        raise ValueError('Retain prior staged processing matrix')
    rows = []
    with tempfile.TemporaryDirectory(prefix='c111256-sweep-process-all-', dir=REPO / '.runtime-work') as scratch:
        mini = Path(scratch)
        folder = mini / 'work' / HERE.name
        folder.mkdir(parents=True)
        write(folder / 'proposals/cases.json',
              json.loads((HERE / 'proposals/sweep-stage-candidate.json').read_text()))
        for relative in ('update028-sweep-diagnostic.json', 'update028-sweep-recipe.json'):
            copy(relative, folder)
        for case in source['cases']:
            copy(case['measurement_contract'], folder)
            copy(case['construction'], folder)
            for fallback in case['candidates']:
                copy(fallback['construction'], folder)
        manifest = folder / 'execution-manifest.json'
        write(manifest, source)
        for case in source['cases']:
            suffix = case['case_id'].rsplit('__', 1)[-1]
            for candidate in ('primary', *(item['id'] for item in case['candidates'])):
                base = mini / '.runtime-work' / suffix / candidate
                fixture, attempt, output = (base / name for name in
                                            ('source-fixture', 'attempt', 'processed'))
                base.mkdir(parents=True)
                make_fixture(mini, folder / 'update028-sweep-recipe.json', fixture)
                make_package(manifest, case['case_id'], attempt, candidate)
                copy_sources(fixture, attempt)
                command = [str(PYTHON), str(REPO / 'runtime.py'), 'process-saved',
                           '--manifest', str(manifest), '--case', case['case_id'],
                           '--attempt', str(attempt), '--output', str(output),
                           '--library', str(REPO / 'runtime/pipeline/library'),
                           '--validator', str(validator)]
                run = subprocess.run(command, cwd=REPO, capture_output=True,
                                     text=True, timeout=600)
                dest = HERE / 'update028-sweep-staged-process' / suffix / candidate
                dest.mkdir(parents=True, exist_ok=True)
                (dest / 'runtime-command.log').write_text(run.stdout + run.stderr)
                if run.returncode:
                    raise ValueError(f'Pinned process-saved failed {suffix} {candidate}: {(run.stdout + run.stderr)[-1200:]}')
                receipt = output / 'v0001/processing.json'
                if not receipt.is_file():
                    raise ValueError('Pinned saved processing receipt missing')
                value = json.loads(receipt.read_text())
                if (value.get('passed') is not True or value.get('recorded_only') is not True or
                        value.get('case_id') != case['case_id'] or
                        value.get('candidate_id') != candidate or
                        value.get('missing_evidence') is not False or
                        value.get('physical_acceptance_claimed') is not False):
                    raise ValueError('Pinned saved processing receipt incomplete')
                shutil.copy2(receipt, dest / 'processing.json')
                shutil.copy2(output / 'v0001/analysis.log', dest / 'analysis.log')
                rows.append({'case_id': case['case_id'], 'candidate_id': candidate,
                             'construction_sha256': value['analysis_revision']['construction_sha256'],
                             'receipt': (dest / 'processing.json').relative_to(HERE).as_posix(),
                             'receipt_sha256': sha(dest / 'processing.json'),
                             'analysis_log_sha256': sha(dest / 'analysis.log'),
                             'runtime_command_log_sha256': sha(dest / 'runtime-command.log')})
                write(matrix_path, {'format': 'c111256-staged-sweep-process-matrix-v1',
                      'status': 'complete_diagnostic' if len(rows) == 16 else 'partial',
                      'staged_manifest_sha256': sha(source_manifest),
                      'rows': rows, 'recorded_only': True,
                      'original_recordings_accepted': 0})
                print(suffix, candidate, 'passed', flush=True)
    print(json.dumps({'staged_process_saved_passed': len(rows),
                      'matrix_sha256': sha(matrix_path), 'selected': False}, sort_keys=True))


if __name__ == '__main__':
    main()
