"""Prove diagnostic delivery review and original-mode rejection for four sweep primaries."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
PYTHON = REPO / '.venv-cpu/bin/python'
sys.path.insert(0, str(REPO / 'runtime/pipeline/scenario_pipeline'))
from worker_exchange.fixture_recipe import materialize as make_fixture
from worker_exchange.runtime_cli import materialize as make_package
from worker_exchange.saved_processing import copy_sources


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def main():
    source_manifest = HERE / 'sweep-proof-bound-promotion-candidate.json'
    manifest = read(source_manifest)
    validator = REPO / '.runtime-work/decoder-update015-c10316/.lake/build/bin/adapterCheck'
    if not validator.is_file() or len(manifest['cases']) != 4:
        raise ValueError('Pinned validator or four-case sweep missing')
    staged_root = REPO / '.runtime-work/c111256-update033-sweep-delivery'
    if staged_root.exists():
        raise ValueError('Retain prior sweep delivery diagnostic output; use a fresh tag')
    staged_root.mkdir(parents=True)
    manifest_root = staged_root / 'manifest'
    manifest_root.mkdir()
    manifest_path = manifest_root / 'sweep-proof-bound-promotion-candidate.json'
    manifest_path.write_bytes(source_manifest.read_bytes())
    shutil.copytree(HERE / 'sweep-candidates', manifest_root / 'sweep-candidates')
    (manifest_root / 'proposals').mkdir()
    shutil.copyfile(HERE / 'proposals/sweep-stage-candidate.json',
                    manifest_root / 'proposals/cases.json')
    rows = []
    for entry in manifest['cases']:
        suffix = entry['case_id'].rsplit('__', 1)[-1]
        base = staged_root / suffix
        if base.exists():
            raise ValueError('Retain prior sweep delivery diagnostic output; use a fresh tag')
        fixture, attempt, processed = (base / name for name in ('fixture', 'attempt', 'processed'))
        base.mkdir(parents=True)
        make_fixture(REPO, HERE / 'update028-sweep-recipe.json', fixture)
        make_package(manifest_path, entry['case_id'], attempt, 'primary')
        copy_sources(fixture, attempt)
        command = [str(PYTHON), str(REPO / 'runtime.py'), 'process-saved',
                   '--manifest', str(manifest_path), '--case', entry['case_id'],
                   '--attempt', str(attempt), '--output', str(processed),
                   '--library', str(REPO / 'runtime/pipeline/library'),
                   '--validator', str(validator)]
        run = subprocess.run(command, cwd=REPO, capture_output=True, text=True, timeout=600)
        dest = HERE / 'update033-sweep-delivery' / suffix
        dest.mkdir(parents=True, exist_ok=True)
        process_log = dest / 'process-saved.log'
        process_log.write_text(run.stdout + run.stderr)
        if run.returncode:
            raise ValueError('Pinned process-saved failed: ' + (run.stdout + run.stderr)[-1200:])
        receipt = processed / 'v0001/processing.json'
        if not receipt.is_file():
            raise ValueError('Missing sweep saved-processing receipt')
        positive = dest / 'diagnostic.json'
        positive_log = dest / 'diagnostic.log'
        common = [str(PYTHON), str(HERE / 'sweep_delivery_audit.py'),
                  '--manifest', str(manifest_path), '--case', entry['case_id'],
                  '--candidate', 'primary', '--attempt', str(attempt),
                  '--processing', str(receipt)]
        command_positive = [*common, '--output', str(positive), '--diagnostic']
        good = subprocess.run(command_positive, cwd=REPO, capture_output=True,
                              text=True, timeout=300)
        positive_log.write_text(good.stdout + good.stderr)
        if good.returncode or not positive.is_file():
            raise ValueError('Sweep diagnostic delivery audit failed: ' +
                             (good.stdout + good.stderr)[-1200:])
        checked = read(positive)
        if (checked['passed'] is not False or checked['source_shaped_unit_test'] is not True
                or checked['case_id'] != entry['case_id'] or
                checked['original_physical_acceptance_claimed'] is not False):
            raise ValueError('Diagnostic audit claimed original acceptance')
        negative = dest / 'original-rejection.json'
        negative_log = dest / 'original-rejection.log'
        command_negative = [*common, '--output', str(negative)]
        bad = subprocess.run(command_negative, cwd=REPO, capture_output=True,
                             text=True, timeout=300)
        negative_log.write_text(bad.stdout + bad.stderr)
        if (bad.returncode == 0 or negative.exists() or
                'Original Native Walk source required' not in negative_log.read_text()):
            raise ValueError('Synthetic sweep source passed original delivery review')
        rows.append({'case_id': entry['case_id'], 'candidate_id': 'primary',
                     'construction_sha256': entry['construction_sha256'],
                     'processing_receipt_sha256': sha(receipt),
                     'process_command': ' '.join(command),
                     'process_log': process_log.relative_to(HERE).as_posix(),
                     'process_log_sha256': sha(process_log),
                     'diagnostic_command': ' '.join(command_positive),
                     'diagnostic_result': positive.relative_to(HERE).as_posix(),
                     'diagnostic_result_sha256': sha(positive),
                     'diagnostic_log': positive_log.relative_to(HERE).as_posix(),
                     'diagnostic_log_sha256': sha(positive_log),
                     'negative_command': ' '.join(command_negative),
                     'negative_log': negative_log.relative_to(HERE).as_posix(),
                     'negative_log_sha256': sha(negative_log),
                     'negative_exit_code': bad.returncode,
                     'negative_expected_error': 'Original Native Walk source required',
                     'original_recordings_accepted': 0})
        print(suffix, 'diagnostic and original-mode rejection passed', flush=True)
    result = {'format': 'c111256-unselected-sweep-delivery-audit-matrix-v1',
              'manifest_sha256': sha(manifest_path),
              'auditor_sha256': sha(HERE / 'sweep_delivery_audit.py'),
              'rows': rows, 'diagnostic_passed': len(rows),
              'original_rejections_passed': len(rows),
              'selected': False, 'original_recordings_accepted': 0}
    path = HERE / 'update033-sweep-delivery-audit-matrix.json'
    path.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'diagnostic_passed': len(rows),
                      'original_rejections_passed': len(rows),
                      'matrix_sha256': sha(path), 'selected': False}, sort_keys=True))


if __name__ == '__main__':
    main()
