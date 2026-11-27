"""Run positive and changed-worker negative controlled comparison proofs."""

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
SCRIPT = HERE/'comparison_audit.py'
COMPARISON = HERE.name+'__selected_ce719cfa__comparison'
SOURCE_NAMES = ('config.json', 'road.xodr', 'original-context-packet.json',
                'native-person-interaction.jsonl', 'video_frames.jsonl')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(command, log, expected):
    result = subprocess.run(command, capture_output=True, text=True,
                            env=dict(os.environ, TMPDIR=str(REPO/'.runtime-work')))
    log.write_text((result.stdout+result.stderr).rstrip()+'\n')
    if (expected == 0 and result.returncode) or (expected != 0 and
            (result.returncode == 0 or 'Fixed actor, road, or worker state changed' not in log.read_text())):
        raise RuntimeError('Comparison proof failed: '+log.read_text())
    return result.returncode


def main():
    positive_left = SCRATCH/'compat-v5-condition_a-primary'
    positive_right = SCRATCH/'compat-v5-condition_b-primary'
    bad = SCRATCH/'comparison-negative-right'
    bad.mkdir(parents=True, exist_ok=True)
    for name in SOURCE_NAMES:
        shutil.copy2(positive_right/name, bad/name)
    raw_path = bad/'native-person-interaction.jsonl'
    raw = [json.loads(line) for line in raw_path.read_text().splitlines()]
    raw[100]['person_y_m'] = -4.0
    raw_path.write_text(''.join(json.dumps(row, allow_nan=False)+'\n' for row in raw))
    proof = HERE/'comparison-proof'
    proof.mkdir(exist_ok=True)
    def command(right, output):
        return [sys.executable, '-B', str(SCRIPT), '--comparison', COMPARISON,
                '--left', str(positive_left), '--right', str(right), '--output', str(output)]
    positive_out = proof/'positive.json'
    positive_command = command(positive_right, positive_out)
    run(positive_command, proof/'positive.log', 0)
    negative_command = command(bad, SCRATCH/'comparison-negative.json')
    negative_code = run(negative_command, proof/'negative.log', 1)
    receipt = {'format': 'c179799-comparison-proof-v1',
               'comparison_id': COMPARISON, 'script': 'comparison_audit.py',
               'script_sha256': sha(SCRIPT),
               'positive_command': ' '.join(positive_command),
               'positive_exit_code': 0,
               'positive_log': 'comparison-proof/positive.log',
               'positive_log_sha256': sha(proof/'positive.log'),
               'positive_result': 'comparison-proof/positive.json',
               'positive_result_sha256': sha(positive_out),
               'negative_command': ' '.join(negative_command),
               'negative_exit_code': negative_code,
               'negative_expected_error': 'Fixed actor, road, or worker state changed',
               'negative_log': 'comparison-proof/negative.log',
               'negative_log_sha256': sha(proof/'negative.log'),
               'diagnostic_fixture_only': True}
    (proof/'proof.json').write_text(json.dumps(receipt, indent=2, allow_nan=False)+'\n')
    print('PASS: controlled earlier/later response and changed-worker rejection')


if __name__ == '__main__':
    main()
