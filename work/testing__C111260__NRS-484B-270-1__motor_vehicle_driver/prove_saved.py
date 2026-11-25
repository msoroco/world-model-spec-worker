"""Run the pinned saved-only processor on an exact diagnostic acquisition."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--donor', type=Path, required=True)
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    folder = Path(__file__).resolve().parent
    repo = folder.parents[1]
    manifest = folder / 'execution-manifest.json'
    entry = next(e for e in json.loads(manifest.read_text())['cases']
                 if e['case_id'] == args.case)
    donor = args.donor.resolve()
    attempt = args.attempt.resolve()
    output = args.output.resolve()
    if any(repo / '.runtime-work' not in path.parents for path in (donor, attempt, output)):
        raise ValueError('diagnostic source, attempt and output belong under .runtime-work')
    if attempt.exists() or output.exists():
        raise ValueError('saved-only proof requires fresh attempt and derived output')
    python = repo / '.venv-cpu/bin/python'
    runtime = repo / 'runtime.py'
    materialize = [str(python), str(runtime), 'materialize', '--manifest', str(manifest),
                   '--case', args.case, '--output', str(attempt)]
    subprocess.run(materialize, check=True, capture_output=True, text=True)
    shutil.copytree(donor / 'capture', attempt / 'capture')
    for name in ('overview.mkv', 'approach.mkv', 'reference_corner.mkv',
                 'driver_reference.mkv', 'raw.mkv', 'trace.jsonl',
                 'video_frames.jsonl', 'acquisition-provenance.json',
                 'road.xodr'):
        shutil.copyfile(donor / name, attempt / name)
    originals = {path.relative_to(attempt).as_posix(): sha(path)
                 for path in attempt.rglob('*') if path.is_file()}
    command = [str(python), str(runtime), 'process-saved', '--manifest', str(manifest),
               '--case', args.case, '--attempt', str(attempt), '--output', str(output),
               '--library', str(repo / 'runtime/library'), '--validator',
               str(repo / '.runtime-work/c111260-owner/validator/.lake/build/bin/adapterCheck')]
    completed = subprocess.run(command, capture_output=True, text=True, env=os.environ.copy())
    if completed.returncode:
        raise ValueError('saved-only processor failed: ' + completed.stdout[-800:] +
                         completed.stderr[-800:])
    receipt = json.loads((output / 'v0001/processing.json').read_text())
    if (receipt.get('case_id') != args.case or receipt.get('recorded_only') is not True
            or receipt.get('passed') is not True or receipt.get('originals_preserved') is not True
            or receipt.get('missing_evidence') is not False
            or receipt.get('final_video_checks') is None
            or receipt.get('candidate_id') != 'primary'
            or receipt['analysis_revision']['construction_sha256'] != entry['construction_sha256']):
        raise ValueError('saved-only receipt incomplete or wrong case')
    if originals != {path.relative_to(attempt).as_posix(): sha(path)
                     for path in attempt.rglob('*') if path.is_file()}:
        raise ValueError('saved-only processing changed original acquisition')
    print(json.dumps({'case_id': args.case, 'recorded_only': True,
                      'originals_preserved': True, 'analysis_complete': True,
                      'final_video_decoded': True,
                      'scope': 'synthetic diagnostic only; no Native physical acceptance'}))


if __name__ == '__main__':
    main()
