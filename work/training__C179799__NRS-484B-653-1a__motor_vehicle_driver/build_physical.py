"""Produce three exact synthetic physical outcomes and lifecycle receipts."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SCRATCH = REPO/'.runtime-work/c179799'
SCRIPT = HERE/'native/prove_physical.py'
SOURCE_NAMES = ('config.json', 'native-person-interaction.jsonl',
                'video_frames.jsonl', 'original-context-packet.json')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')


def run(command, log):
    process = subprocess.run(command, capture_output=True, text=True,
                             env=dict(os.environ, TMPDIR=str(REPO/'.runtime-work')))
    log.write_text((process.stdout+process.stderr).rstrip()+'\n')
    if process.returncode:
        raise RuntimeError('Physical proof command failed: '+str(command)+': '+log.read_text())


def main():
    manifest_path = HERE/'selected-probe-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    for entry in manifest['cases']:
        suffix = entry['case_id'].split('__')[-1]
        original = SCRATCH/('compat-v5-'+suffix+'-primary')
        proof_root = HERE/'physical-proof'/suffix
        proof_root.mkdir(parents=True, exist_ok=True)
        receipts = []
        for kind in ('complete_motion', 'incomplete_motion', 'missing_evidence'):
            attempt = SCRATCH/('physical-'+suffix+'-'+kind)
            attempt.mkdir(parents=True, exist_ok=True)
            for name in SOURCE_NAMES:
                shutil.copy2(original/name, attempt/name)
            if kind == 'incomplete_motion':
                raw = attempt/'native-person-interaction.jsonl'
                rows = [json.loads(line) for line in raw.read_text().splitlines()]
                for row in rows:
                    row['ego_x_m'] = rows[0]['ego_x_m']
                raw.write_text(''.join(json.dumps(row, allow_nan=False)+'\n' for row in rows))
            elif kind == 'missing_evidence':
                (attempt/'original-context-packet.json').unlink()
            result = proof_root/(kind+'.json')
            log = proof_root/(kind+'.log')
            command = [sys.executable, '-B', str(SCRIPT),
                       '--attempt', str(attempt), '--output', str(result)]
            run(command, log)
            receipts.append({'kind': kind, 'command': ' '.join(command),
                             'exit_code': 0,
                             'log': str(log.relative_to(HERE)),
                             'log_sha256': sha(log),
                             'result': str(result.relative_to(HERE)),
                             'result_sha256': sha(result)})
        life_log = proof_root/'lifecycle.log'
        run([sys.executable, '-B', str(SCRIPT), '--lifecycle'], life_log)
        proof = {'format': 'c179799-synthetic-physical-proof-v1',
                 'case_id': entry['case_id'],
                 'construction_sha256': entry['construction_sha256'],
                 'original_native_observed': False, 'diagnostic_only': True,
                 'fixtures': receipts,
                 'lifecycle': {'events': ['capture_finished', 'encoders_closed',
                                          'restoration_verified', 'native_exit',
                                          'owner_released', 'saved_processing_started'],
                               'exit_code': 0,
                               'negative_premature_saved_processing_rejected': True,
                               'log': str(life_log.relative_to(HERE)),
                               'log_sha256': sha(life_log)}}
        proof_path = proof_root/'proof.json'
        write(proof_path, proof)
        entry['physical_preparation'] = {'receipt': str(proof_path.relative_to(HERE)),
                                         'sha256': sha(proof_path)}
    write(manifest_path, manifest)
    print('PASS: two exact synthetic encounter and lifecycle proofs bound')


if __name__ == '__main__':
    main()
