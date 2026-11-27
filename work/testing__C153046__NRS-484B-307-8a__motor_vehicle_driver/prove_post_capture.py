"""Exercise recorded-only processing and failure feedback for each selected case."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


ASSIGNMENT = 'testing__C153046__NRS-484B-307-8a__motor_vehicle_driver'
ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / 'work' / ASSIGNMENT
SCRATCH = ROOT / '.runtime-work' / 'c153046-post-capture-nov27'
VALIDATOR = ROOT / '.runtime-work/c150099-decoder-v2/.lake/build/bin/adapterCheck'
MISSING = 'original-attempt/site-packet.json'


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make_attempt(suffix: str, variant: str) -> Path:
    source = ROOT / '.runtime-work' / f'c153046-saved-source-{suffix}-v8'
    assert source.is_dir(), source
    attempt = SCRATCH / f'{suffix}-{variant}-attempt'
    if attempt.exists():
        shutil.rmtree(attempt)
    for item in source.rglob('*'):
        target = attempt / item.relative_to(source)
        if item.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        elif item.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            os.link(item, target)
    selection_path = attempt / 'candidate-selection.json'
    if selection_path.is_file():
        selection = json.loads(selection_path.read_text())
        assert selection['candidate_id'] == 'primary'
        selection['manifest_sha256'] = sha(WORK / 'execution-manifest.json')
        selection_path.unlink()
        selection_path.write_text(json.dumps(selection, indent=2) + '\n')
    if variant == 'missing-source':
        (attempt / MISSING).unlink()
    return attempt


def run(suffix: str, variant: str) -> dict:
    SCRATCH.mkdir(parents=True, exist_ok=True)
    case_id = ASSIGNMENT + '__' + suffix
    attempt = make_attempt(suffix, variant)
    output = SCRATCH / f'{suffix}-{variant}-output'
    if output.exists():
        shutil.rmtree(output)
    validator = VALIDATOR if variant != 'missing-validator' else SCRATCH / 'absent-adapterCheck'
    command = [sys.executable, str(ROOT / 'runtime.py'), 'process-saved',
               '--manifest', str(WORK / 'execution-manifest.json'), '--case', case_id,
               '--attempt', str(attempt), '--output', str(output),
               '--library', str(ROOT / 'runtime/library'), '--validator', str(validator)]
    env = os.environ.copy()
    env.update(PYTHONDONTWRITEBYTECODE='1',
               SCENARIO_PIPELINE_OUTPUT_ROOT=str(SCRATCH), TMPDIR=str(SCRATCH))
    proc = subprocess.run(command, cwd=ROOT, env=env,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    version = output / 'v0001'
    receipt_path = version / 'processing.json'
    feedback_path = version / 'feedback.json'
    receipt = json.loads(receipt_path.read_text()) if receipt_path.is_file() else None
    feedback = json.loads(feedback_path.read_text()) if feedback_path.is_file() else None
    if variant == 'positive':
        assert proc.returncode == 0 and receipt and receipt['recorded_only'] and receipt['originals_preserved'] and not receipt['missing_evidence'], (case_id, proc.stdout[-1000:])
    elif variant == 'missing-source':
        assert proc.returncode == 0 and receipt and receipt['missing_evidence'] and feedback and feedback['recorded_only'] and not feedback['native_replay_requested'] and 'Missing required source: ' + MISSING in feedback['error'], (case_id, proc.stdout[-1000:])
    else:
        assert proc.returncode != 0 and feedback and feedback['recorded_only'] and not feedback['native_replay_requested'] and feedback['error_type'] == 'FileNotFoundError' and 'absent-adapterCheck' in feedback['error'], (case_id, proc.stdout[-1000:])
    log = WORK / f'cpu-post-capture-{suffix}-{variant}.log'
    detail = {'case_id': case_id, 'variant': variant, 'command': command,
              'exit_code': proc.returncode, 'recorded_only': True,
              'processing_sha256': sha(receipt_path) if receipt else None,
              'feedback_sha256': sha(feedback_path) if feedback else None,
              'feedback': feedback, 'stdout_tail': proc.stdout[-2000:]}
    log.write_text(json.dumps(detail, indent=2, ensure_ascii=False).rstrip() + '\n')
    result = {'exit_code': proc.returncode, 'log': log.name,
              'log_sha256': sha(log)}
    if receipt:
        result['processing_sha256'] = sha(receipt_path)
    if feedback:
        result['feedback_sha256'] = sha(feedback_path)
        result['feedback_classification'] = feedback.get('classification')
        result['feedback_error_type'] = feedback.get('error_type')
    if variant == 'positive':
        result['required_source_hashes'] = {MISSING: sha(attempt / MISSING)}
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('suffix')
    parser.add_argument('variant', choices=['positive', 'missing-source', 'missing-validator'])
    args = parser.parse_args()
    print(json.dumps(run(args.suffix, args.variant), sort_keys=True))
