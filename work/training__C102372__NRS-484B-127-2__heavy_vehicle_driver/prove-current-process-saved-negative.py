"""Verify current saved processing classifies removed Native evidence."""
from pathlib import Path
import hashlib
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
    positive = SCRATCH / 'attempt'
    negative = SCRATCH / 'negative-attempt'
    if negative.exists():
        raise ValueError('Retain prior negative attempt')
    shutil.copytree(positive, negative, copy_function=os.link)
    (negative / 'native_samples.jsonl').unlink()
    before = {p.relative_to(negative).as_posix(): sha(p) for p in negative.rglob('*') if p.is_file()}
    manifest = HERE / 'draft-execution-manifest.json'
    cmd = [sys.executable, str(ROOT / 'runtime.py'), 'process-saved',
           '--manifest', str(manifest), '--case', CASE, '--attempt', str(negative),
           '--output', str(SCRATCH / 'negative-processed'), '--library',
           str(ROOT / 'runtime/pipeline/library'), '--validator',
           str(ROOT / '.runtime-work/c10316-current-decoder/.lake/build/bin/adapterCheck')]
    run = subprocess.run(cmd, capture_output=True, text=True, timeout=1200)
    log = HERE / 'current-process-saved-negative.log'
    log.write_text(run.stdout + run.stderr)
    after = {p.relative_to(negative).as_posix(): sha(p) for p in negative.rglob('*') if p.is_file()}
    version = SCRATCH / 'negative-processed/v0001'
    processing = json.loads((version / 'processing.json').read_text()) if (version / 'processing.json').is_file() else None
    feedback = json.loads((version / 'feedback.json').read_text()) if (version / 'feedback.json').is_file() else None
    rejected = ((processing is not None and processing.get('missing_evidence') is True) or
                (feedback is not None and 'Missing required source: native_samples.jsonl' in feedback.get('error', '')))
    receipt = {'format': 'c102372-current-process-saved-missing-native-v1',
               'case_id': CASE, 'removed': 'native_samples.jsonl',
               'manifest_sha256': sha(manifest), 'exit_code': run.returncode,
               'log_sha256': sha(log), 'source_files_unchanged': before == after,
               'rejected_as_incomplete': rejected,
               'processing_missing_evidence': processing.get('missing_evidence') if processing else None,
               'feedback_classification': feedback.get('classification') if feedback else None,
               'native_replay_requested': feedback.get('native_replay_requested') if feedback else None,
               'physical_observation_claimed': False}
    (HERE / 'current-process-saved-negative-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt, sort_keys=True))
    if before != after or not rejected:
        raise ValueError('Removed Native source was not safely rejected')


if __name__ == '__main__':
    main()
