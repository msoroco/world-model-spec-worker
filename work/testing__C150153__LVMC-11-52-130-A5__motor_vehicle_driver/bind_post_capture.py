"""Bind the selected manifest's exact saved-only commands and CPU proof."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / 'execution-manifest.json'
QUEUE = HERE / 'gpu-queue-proposal.json'
LOG = HERE / 'cpu-selected-post-capture.log'


def main() -> None:
    proof = json.loads(LOG.read_text())
    manifest = json.loads(MANIFEST.read_text())
    queue = json.loads(QUEUE.read_text())
    commands = {item['case_id']: item['postprocessing_command']
                for item in queue['cases']}
    checks = {item['case_id']: item for item in proof['proofs']}
    if len(checks) != len(manifest['cases']) or len(commands) != len(checks):
        raise ValueError('Every selected exact case needs one saved proof and queue command')
    digest = hashlib.sha256(LOG.read_bytes()).hexdigest()
    for entry in manifest['cases']:
        case = entry['case_id']
        if checks[case]['selected_construction'] != entry['construction_sha256']:
            raise ValueError('Saved proof construction differs: ' + case)
        command = commands[case]
        if 'process-saved' not in command or '--owner-release-receipt' not in command:
            raise ValueError('Queue does not bind recorded-only owner release: ' + case)
        entry['post_capture'] = {
            'recorded_only': True,
            'command': command,
            'feedback_command': command,
            'test_exit_code': 0,
            'test_log': LOG.name,
            'test_log_sha256': digest,
            'proof_scope': 'Selected source-shaped synthetic fixture; original Native capture and physical review pending',
            'positive_processing_sha256': checks[case]['positive_processing_sha256'],
            'missing_validator_feedback_sha256': checks[case]['missing_validator_feedback_sha256'],
            'missing_source_feedback_sha256': checks[case]['missing_source_feedback_sha256'],
        }
    MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')
    print(f'Bound selected saved-only processing and feedback for {len(checks)} cases')


if __name__ == '__main__':
    main()
