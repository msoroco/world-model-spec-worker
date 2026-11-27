"""Replay each diagnostic capture through the recorded-only CPU processor."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SCRATCH = REPO / '.runtime-work/c312865-nov27/saved-v6'
os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT'] = str(REPO / '.runtime-work/c312865-nov27/output')
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))
from worker_exchange.native_output import seal_capture
from worker_exchange.saved_processing import record_native_exit, acknowledge_owner_release


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')


def main():
    SCRATCH.mkdir(parents=True, exist_ok=True)
    manifest_path = ROOT / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    proof_root = REPO / '.runtime-work/c312865-nov27/proofs-v5'
    validator = REPO / '.runtime-work/c110969-decoder/.lake/build/bin/adapterCheck'
    for entry in manifest['cases']:
        suffix = entry['case_id'].removeprefix(manifest['assignment_id'] + '__')
        original = proof_root / ('compatible-' + suffix + '-primary')
        attempt = SCRATCH / ('attempt-' + suffix)
        shutil.copytree(original, attempt, copy_function=os.link)
        shutil.rmtree(attempt / 'converted', ignore_errors=True)
        selection = attempt / 'candidate-selection.json'
        if selection.is_file():
            selection.unlink()
        write(attempt / 'acquisition-provenance.json', {
            'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True})
        frames = len((attempt / 'video_frames.jsonl').read_text().splitlines())
        seal_capture(attempt, frames=frames,
                     restoration={'restored': True, 'settings_readback': 'CPU fixture protocol'},
                     errors=[], encoder_exit_codes={'synthetic': 0})
        record_native_exit(attempt)
        owner = attempt / 'owner-release.json'
        acknowledge_owner_release(attempt, owner, True)
        output = SCRATCH / ('processed-' + suffix)
        command = [sys.executable, str(REPO / 'runtime.py'), 'process-saved',
                   '--manifest', str(manifest_path), '--case', entry['case_id'],
                   '--attempt', str(attempt), '--output', str(output),
                   '--library', str(REPO / 'runtime/library'), '--validator', str(validator),
                   '--owner-release-receipt', str(owner)]
        env = os.environ.copy()
        env['TMPDIR'] = str(REPO / '.runtime-work')
        result = subprocess.run(command, cwd=REPO, env=env, capture_output=True, text=True)
        log = ROOT / ('proof-saved-' + suffix + '.log')
        log.write_text((result.stdout + result.stderr).rstrip() + '\n', encoding='utf-8')
        if result.returncode:
            raise RuntimeError(log.read_text()[-3000:])
        entry['post_capture'] = {
            'recorded_only': True,
            'command': '.venv-cpu/bin/python runtime.py process-saved --manifest work/' +
                       manifest['assignment_id'] + '/execution-manifest.json --case ' +
                       entry['case_id'] + ' --attempt "$ATTEMPT" --output "$PROCESSED"' +
                       ' --library runtime/library --validator "$LEAN_VALIDATOR"' +
                       ' --owner-release-receipt "$OWNER_RELEASE_RECEIPT"',
            'feedback_command': '.venv-cpu/bin/python runtime.py process-saved --manifest work/' +
                       manifest['assignment_id'] + '/execution-manifest.json --case ' +
                       entry['case_id'] + ' --attempt "$ATTEMPT" --output "$PROCESSED"' +
                       ' --library runtime/library --validator "$LEAN_VALIDATOR"' +
                       ' --owner-release-receipt "$OWNER_RELEASE_RECEIPT"',
            'test_log': log.name, 'test_log_sha256': digest(log), 'test_exit_code': 0,
            'scope': 'source-shaped diagnostic saved-only replay; original highway tunnel and actual pixels pending'}
        write(manifest_path, manifest)
        print('saved-only proof', suffix, flush=True)


if __name__ == '__main__':
    main()
