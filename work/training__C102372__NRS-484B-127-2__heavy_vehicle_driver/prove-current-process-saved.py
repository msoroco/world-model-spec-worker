"""Exercise current saved processing on one unselected 600-frame diagnostic."""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRATCH = ROOT / '.runtime-work' / 'c102372-current-process-saved'
CASE = HERE.name + '__probe_1'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    output_root = Path(os.environ.get('SCENARIO_PIPELINE_OUTPUT_ROOT', '')).resolve()
    if ROOT / '.runtime-work' not in output_root.parents:
        raise ValueError('Set SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work first')
    if SCRATCH.exists():
        raise ValueError('Retain earlier diagnostic; choose a fresh scratch directory')
    SCRATCH.mkdir(parents=True)
    spec = importlib.util.spec_from_file_location('c102372_probe_package', HERE / 'probe-package.py')
    package = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(package)
    source_build = SCRATCH / 'source-build'
    source_build.mkdir()
    source = package.make_source('probe_1', source_build)
    manifest = HERE / 'draft-execution-manifest.json'
    attempt = SCRATCH / 'attempt'
    cmd = [sys.executable, str(ROOT / 'runtime.py'), 'materialize',
           '--manifest', str(manifest), '--case', CASE, '--output', str(attempt)]
    subprocess.run(cmd, check=True, capture_output=True, text=True)
    from worker_exchange.saved_processing import copy_sources
    copy_sources(source, attempt)
    before = {p.relative_to(attempt).as_posix(): sha(p) for p in attempt.rglob('*') if p.is_file()}
    cmd = [sys.executable, str(ROOT / 'runtime.py'), 'process-saved',
           '--manifest', str(manifest), '--case', CASE, '--attempt', str(attempt),
           '--output', str(SCRATCH / 'processed'), '--library',
           str(ROOT / 'runtime/pipeline/library'), '--validator',
           str(ROOT / '.runtime-work/c10316-current-decoder/.lake/build/bin/adapterCheck')]
    run = subprocess.run(cmd, capture_output=True, text=True, timeout=1200)
    (HERE / 'current-process-saved-primary.log').write_text(run.stdout + run.stderr)
    after = {p.relative_to(attempt).as_posix(): sha(p) for p in attempt.rglob('*') if p.is_file()}
    feedback = SCRATCH / 'processed/v0001/feedback.json'
    receipt = {'format': 'c102372-current-process-saved-primary-probe-v1',
               'case_id': CASE, 'candidate_id': 'primary',
               'manifest_sha256': sha(manifest), 'source_files_unchanged': before == after,
               'exit_code': run.returncode,
               'log_sha256': sha(HERE / 'current-process-saved-primary.log'),
               'feedback': json.loads(feedback.read_text()) if feedback.is_file() else None,
               'physical_observation_claimed': False, 'delivery_ready': False}
    (HERE / 'current-process-saved-primary-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'exit_code': run.returncode, 'source_files_unchanged': before == after,
                      'feedback': receipt['feedback']}, sort_keys=True))
    if before != after:
        raise ValueError('Original attempt changed during saved processing')


if __name__ == '__main__':
    main()
