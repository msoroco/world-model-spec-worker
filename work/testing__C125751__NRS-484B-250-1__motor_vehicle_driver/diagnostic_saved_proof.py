"""Exercise saved-only failure feedback on an immutable synthetic attempt."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

from case_protocol import ASSIGNMENT

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    scratch = REPO / '.runtime-work' / 'c125751-diagnostic-runtime-3'
    base = json.loads((scratch / 'execution-manifest.json').read_text())
    case_id = ASSIGNMENT + '__precedence'
    for entry in base['cases']:
        entry['measurement_procedure'] = {'entrypoint': 'analysis.py'}
    base['runtime_manifest_sha256'] = 'diagnostic-only'
    manifest = scratch / 'saved-manifest.json'
    manifest.write_text(json.dumps(base, indent=2) + '\n')
    attempt = scratch / 'saved-attempt-negative-2'
    if attempt.exists():
        raise ValueError('Retain prior diagnostic saved attempt')
    shutil.copytree(scratch / 'offline' / 'precedence', attempt)
    (attempt / 'candidate-selection.json').unlink()
    (attempt / 'offline.log').unlink()
    (attempt / 'acquisition-provenance.json').write_text(json.dumps({
        'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True,
        'method': 'CPU saved-path rejection fixture'}) + '\n')
    (attempt / 'video_frames.jsonl').write_text(json.dumps({
        'video_frame': 0, 'carla_frame': 1, 'time_s': 0.0}) + '\n')
    (attempt / 'trace.jsonl').write_text(json.dumps({
        'frame': 1, 'time_s': 0.0}) + '\n')
    before = {p.name: sha(p) for p in attempt.iterdir() if p.is_file()}
    output = scratch / 'saved-negative-output-2'
    command = [str(REPO / '.venv-cpu/bin/python'), str(REPO / 'runtime.py'),
               'process-saved', '--manifest', str(manifest), '--case', case_id,
               '--attempt', str(attempt), '--output', str(output),
               '--library', str(REPO / 'runtime' / 'library'),
               '--validator', str(REPO / 'runtime' / 'library' / 'Main.lean')]
    env = dict(os.environ)
    env['SCENARIO_PIPELINE_OUTPUT_ROOT'] = str(REPO / '.runtime-work' / 'c125751-proof')
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    completed = subprocess.run(command, cwd=REPO, env=env, capture_output=True, text=True)
    log = scratch / 'saved-negative-2.log'
    log.write_text(completed.stdout + completed.stderr)
    feedback = json.loads((output / 'v0001' / 'feedback.json').read_text())
    after = {p.name: sha(p) for p in attempt.iterdir() if p.is_file()}
    if (completed.returncode == 0 or before != after or
            'Missing original camera source: overview' not in feedback.get('error', '') or
            feedback.get('native_replay_requested') is not False):
        raise ValueError('Saved-only rejection or original preservation did not hold')
    receipt = {'case_id': case_id, 'diagnostic_fixture': True,
               'process_saved_exit_code': completed.returncode,
               'expected_rejection': feedback['error'],
               'feedback_sha256': sha(output / 'v0001' / 'feedback.json'),
               'log_sha256': sha(log), 'originals_preserved': True,
               'native_replay_requested': False,
               'production_acceptance_claimed': False}
    (scratch / 'diagnostic-saved-proof-2.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    main()
