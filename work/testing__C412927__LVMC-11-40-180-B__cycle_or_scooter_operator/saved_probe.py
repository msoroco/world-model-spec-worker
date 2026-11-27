"""Exercise immutable saved processing against a synthetic roadway acquisition."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--validator', type=Path, required=True)
    args = parser.parse_args()
    suffix = args.case.removeprefix(ROOT.name + '__')
    if suffix == args.case:
        raise ValueError('wrong exact signed roadway case')
    manifest = ROOT / 'execution-manifest.draft.json'
    entry = next(x for x in json.loads(manifest.read_text())['cases']
                 if x['case_id'] == args.case)
    source = REPO / '.runtime-work/c412927-owner/all-exact-v2/compat' / suffix
    output = args.output.resolve()
    if output.exists() or REPO / '.runtime-work' not in output.parents:
        raise ValueError('fresh scratch output under .runtime-work required')
    output.mkdir(parents=True)
    attempt = output / 'attempt'
    shutil.copytree(source, attempt, copy_function=os.link)
    for name in ('converted', 'traffic_spec', 'tests'):
        path = attempt / name
        if path.exists():
            shutil.rmtree(path)
    for name in ('result.json', 'analysis-report.json', 'compatibility.json',
                 'event_review.json', 'event_review.webm', 'event_review_encoder.log',
                 'event_review_frames.jsonl', 'review_label.txt',
                 'review_measured_speed.ass', 'review_render.lock',
                 'final-decode.json', 'four-view-receipt.json', 'raw.mkv',
                 'compatibility-analysis.log', 'negative-analysis.log'):
        (attempt / name).unlink(missing_ok=True)
    for path in attempt.glob('source-*.json'):
        path.unlink()
    (attempt / 'candidate-selection.json').write_text(json.dumps({
        'format': 'worker-candidate-selection', 'case_id': args.case,
        'candidate_id': 'primary',
        'construction_sha256': entry['construction_sha256'],
        'manifest_sha256': sha(manifest)}) + '\n')
    (attempt / 'acquisition-provenance.json').write_text(json.dumps({
        'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True}) + '\n')
    from worker_exchange.native_output import seal_capture
    from worker_exchange.saved_processing import record_native_exit, acknowledge_owner_release
    frames = len((attempt / 'video_frames.jsonl').read_text().splitlines())
    seal_capture(attempt, frames=frames,
                 restoration={'restored': True, 'settings_readback': 'CPU protocol fixture'},
                 errors=[], encoder_exit_codes={'synthetic': 0})
    record_native_exit(attempt)
    acknowledge_owner_release(attempt, attempt / 'owner-release.json', True)
    before = {p.name: sha(p) for p in attempt.iterdir() if p.is_file()}
    command = [sys.executable, str(REPO / 'runtime.py'), 'process-saved',
               '--manifest', str(manifest), '--case', args.case,
               '--attempt', str(attempt), '--output', str(output / 'processed'),
               '--library', str(REPO / 'runtime/library'),
               '--validator', str(args.validator.resolve()),
               '--owner-release-receipt', str(attempt / 'owner-release.json')]
    result = subprocess.run(command, cwd=REPO, text=True, capture_output=True,
                            timeout=600)
    (output / 'process-saved.log').write_text((result.stdout + result.stderr).rstrip() + '\n')
    if result.returncode:
        raise ValueError('saved-only processing failed: ' + result.stderr[-1200:])
    after = {p.name: sha(p) for p in attempt.iterdir() if p.is_file()}
    if before != after:
        raise ValueError('saved processing changed acquisition')
    receipt = json.loads((output / 'processed/v0001/processing.json').read_text())
    if (receipt.get('passed') is not True or receipt.get('recorded_only') is not True or
            receipt.get('case_id') != args.case or receipt.get('originals_preserved') is not True):
        raise ValueError('saved-only receipt incomplete')
    print(json.dumps({'case_id': args.case, 'saved_only_passed': True,
                      'diagnostic_fixture': True, 'acquisition_unchanged': True}))


if __name__ == '__main__':
    main()
