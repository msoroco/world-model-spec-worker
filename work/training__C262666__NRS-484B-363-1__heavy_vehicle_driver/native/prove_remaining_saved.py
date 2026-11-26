"""Run canonical recorded-only processing for seven exact synthetic cases.

The scratch attempts are diagnostic fixtures. Their selection receipts are
rebound to the current manifest without modifying any returned acquisition.
"""
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parent
REPO = PACKAGE.parents[1]
SCRATCH = REPO / '.runtime-work' / 'c262666-test'
MANIFEST = PACKAGE / 'execution-manifest.json'
VALIDATOR = SCRATCH / 'decoder/.lake/build/bin/adapterCheck'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + '\n')


def command(case, attempt, output):
    return [sys.executable, '-B', str(REPO / 'runtime.py'), 'process-saved',
            '--manifest', str(MANIFEST), '--case', case, '--attempt', str(attempt),
            '--output', str(output), '--library', str(REPO / 'runtime/library'),
            '--validator', str(VALIDATOR)]


def main():
    manifest = json.loads(MANIFEST.read_text())
    env = dict(os.environ, SCENARIO_PIPELINE_OUTPUT_ROOT=str(SCRATCH / 'output'),
               TMPDIR=str(SCRATCH / 'tmp'), PYTHONDONTWRITEBYTECODE='1')
    (SCRATCH / 'tmp').mkdir(parents=True, exist_ok=True)
    (SCRATCH / 'output').mkdir(parents=True, exist_ok=True)
    for entry in manifest['cases']:
        suffix = entry['case_id'].rsplit('__', 1)[1]
        if suffix == 'probe_03':
            continue
        old = SCRATCH / f'saved-attempt-{suffix}-r1'
        attempt = SCRATCH / f'saved-attempt-{suffix}-r2'
        if attempt.exists():
            shutil.rmtree(attempt)
        shutil.copytree(old, attempt)
        selection = json.loads((attempt / 'candidate-selection.json').read_text())
        if selection['construction_sha256'] != entry['construction_sha256']:
            raise ValueError(suffix + ': fixture construction changed')
        selection['manifest_sha256'] = sha(MANIFEST)
        write(attempt / 'candidate-selection.json', selection)
        before = {str(p.relative_to(attempt)): sha(p) for p in attempt.rglob('*') if p.is_file()}
        output = SCRATCH / f'saved-output-{suffix}-r2'
        positive = subprocess.run(command(entry['case_id'], attempt, output),
                                  text=True, capture_output=True, env=env)
        if positive.returncode:
            raise ValueError(suffix + ': positive failed: ' + positive.stderr[-1000:])
        receipt = json.loads(positive.stdout)
        if not receipt.get('passed') or not receipt.get('recorded_only'):
            raise ValueError(suffix + ': positive receipt incomplete')
        write(HERE / 'saved' / f'{suffix}-positive-processing.json', receipt)
        after = {str(p.relative_to(attempt)): sha(p) for p in attempt.rglob('*') if p.is_file()}
        if before != after:
            raise ValueError(suffix + ': original source changed')
        negative_attempt = SCRATCH / f'saved-attempt-{suffix}-negative-r2'
        if negative_attempt.exists():
            shutil.rmtree(negative_attempt)
        shutil.copytree(attempt, negative_attempt)
        (negative_attempt / 'school_zone_context.json').unlink()
        negative = subprocess.run(command(entry['case_id'], negative_attempt,
                                         SCRATCH / f'saved-output-{suffix}-negative-r2'),
                                  text=True, capture_output=True, env=env)
        if negative.returncode:
            raise ValueError(suffix + ': negative processing failed: ' + negative.stderr[-1000:])
        rejection = json.loads(negative.stdout)
        feedback = json.loads((Path(rejection['version']) / 'feedback.json').read_text())
        if feedback.get('classification') != 'incomplete_or_unavailable_law_evidence' or \
                'Missing required source: school_zone_context.json' not in feedback.get('error', ''):
            raise ValueError(suffix + ': missing context accepted')
        write(HERE / 'saved' / f'{suffix}-negative-processing.json', rejection)
        write(HERE / 'saved' / f'{suffix}-negative-feedback.json', feedback)
        print(suffix, 'recorded-only positive and missing-context rejection pass', flush=True)


if __name__ == '__main__':
    main()
