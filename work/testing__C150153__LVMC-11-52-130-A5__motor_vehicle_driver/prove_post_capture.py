"""Prove selected exact-case saved processing and actionable failure feedback.

Only source-shaped synthetic fixtures are used. No Native replay or physical
acceptance is asserted by these checks.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / 'execution-manifest.json'
SCRATCH = ROOT / '.runtime-work/c150153-postcapture'
VALIDATOR = ROOT / '.runtime-work/c150153-owner/validator/.lake/build/bin/adapterCheck'


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(*args: object, success: bool = True) -> str:
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
    command = [str(ROOT / '.venv-cpu/bin/python'), str(ROOT / 'runtime.py'),
               *map(str, args)]
    completed = subprocess.run(command, cwd=ROOT, env=env, text=True,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               timeout=900)
    if (completed.returncode == 0) != success:
        raise ValueError(f'Unexpected exit {completed.returncode}: {completed.stdout[-3000:]}')
    return completed.stdout


def prove(entry: dict, ordinal: int) -> dict:
    case = entry['case_id']
    stem = case.rsplit('__', 1)[1]
    scratch = SCRATCH / f'case-{ordinal:02d}-{stem}'
    if scratch.exists():
        shutil.rmtree(scratch)
    scratch.mkdir(parents=True)
    attempt, fixture = scratch / 'attempt', scratch / 'fixture'
    run('materialize', '--manifest', MANIFEST, '--case', case, '--output', attempt)
    run('fixture', '--recipe', ROOT / entry['fixture_recipe'], '--output', fixture)
    for path in fixture.iterdir():
        target = attempt / path.name
        if target.exists():
            raise ValueError(f'Fixture shadows selected construction: {path.name}')
        if path.is_dir():
            shutil.copytree(path, target)
        else:
            shutil.copy2(path, target)
    seal_path = attempt / 'capture-seal.json'
    seal = json.loads(seal_path.read_text())
    if seal.get('provenance_kind') != 'synthetic_fixture':
        raise ValueError('Expected a synthetic fixture only')
    seal['events'] = ['capture_finished', 'encoders_closed', 'restoration_verified']
    seal['native_revision'] = {
        'construction_sha256': sha(attempt / 'construction.json'),
        'runner_sha256': sha(attempt / 'runner.py'),
    }
    seal_path.write_text(json.dumps(seal, indent=2) + '\n')
    sys.path.insert(0, str(ROOT / 'runtime/scenario_pipeline'))
    from worker_exchange.saved_processing import record_native_exit
    record_native_exit(attempt)

    positive = scratch / 'positive'
    run('process-saved', '--manifest', MANIFEST, '--case', case,
        '--attempt', attempt, '--output', positive,
        '--library', ROOT / 'runtime/library', '--validator', VALIDATOR)
    receipt = json.loads((positive / 'v0001/processing.json').read_text())
    if not (receipt['passed'] and receipt['recorded_only']
            and receipt['originals_preserved'] and not receipt['missing_evidence']
            and receipt['case_id'] == case):
        raise ValueError(f'Incomplete selected saved-only result: {stem}')

    no_validator = scratch / 'no-validator'
    run('process-saved', '--manifest', MANIFEST, '--case', case,
        '--attempt', attempt, '--output', no_validator,
        '--library', ROOT / 'runtime/library',
        '--validator', scratch / 'missing-adapterCheck', success=False)
    validator_feedback = json.loads((no_validator / 'v0001/feedback.json').read_text())
    if not (validator_feedback['recorded_only']
            and validator_feedback['native_replay_requested'] is False
            and validator_feedback['case_id'] == case
            and 'validator' in validator_feedback['error'].lower()):
        raise ValueError(f'Missing-validator feedback incomplete: {stem}')

    missing_source = scratch / 'missing-source-attempt'
    shutil.copytree(attempt, missing_source)
    source = missing_source / 'channels/reviewed_sidewalk_elevator_site.json'
    if not source.is_file():
        raise ValueError(f'Expected selected source absent: {source}')
    source.unlink()
    source_output = scratch / 'missing-source'
    run('process-saved', '--manifest', MANIFEST, '--case', case,
        '--attempt', missing_source, '--output', source_output,
        '--library', ROOT / 'runtime/library', '--validator', VALIDATOR,
        success=False)
    source_feedback = json.loads((source_output / 'v0001/feedback.json').read_text())
    if not (source_feedback['recorded_only']
            and source_feedback['native_replay_requested'] is False
            and source_feedback['case_id'] == case
            and source_feedback['error']):
        raise ValueError(f'Missing-source feedback incomplete: {stem}')
    return {'case_id': case, 'selected_construction': entry['construction_sha256'],
            'positive_processing_sha256': sha(positive / 'v0001/processing.json'),
            'missing_validator_feedback_sha256': sha(no_validator / 'v0001/feedback.json'),
            'missing_source_feedback_sha256': sha(source_output / 'v0001/feedback.json')}


if __name__ == '__main__':
    entries = json.loads(MANIFEST.read_text())['cases']
    proofs = [prove(entry, i) for i, entry in enumerate(entries)]
    print(json.dumps({'format': 'selected-post-capture-cpu-proof',
                      'diagnostic_fixture_only': True, 'proofs': proofs}, indent=2))
