"""Bind current exact-case CPU receipts without claiming Native acceptance."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from native_packet import AID

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRATCH = ROOT / '.runtime-work/c149752'


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind() -> None:
    path = HERE / 'execution-manifest.json'
    manifest = json.loads(path.read_text(encoding='utf-8'))
    if manifest['assignment_id'] != AID or len(manifest['cases']) != 9:
        raise ValueError('nine exact truck-following cases required')
    for entry in manifest['cases']:
        case_id = entry['case_id']
        suffix = case_id.removeprefix(AID + '__')
        if sha(HERE / entry['construction']) != entry['construction_sha256']:
            raise ValueError('changed construction: ' + suffix)
        receipt = HERE / ('cpu-compat-' + suffix + '-receipt.json')
        proof = json.loads(receipt.read_text(encoding='utf-8'))
        if proof.get('passed') is not True or proof.get('construction_sha256') != entry['construction_sha256']:
            raise ValueError('stale compatibility: ' + suffix)
        processing_paths = sorted((SCRATCH / ('saved-truck-v5-' + suffix)).glob('v*/processing.json'))
        if not processing_paths:
            raise ValueError('saved-only replay absent: ' + suffix)
        processed = json.loads(processing_paths[-1].read_text(encoding='utf-8'))
        if not (processed.get('passed') is True and processed.get('recorded_only') is True
                and processed.get('originals_preserved') is True
                and processed.get('native_revision', {}).get('construction_sha256') == entry['construction_sha256']):
            raise ValueError('saved-only current-hash proof failed: ' + suffix)
        log = HERE / ('cpu-saved-' + suffix + '.log')
        log.write_text('recorded_only=true\noriginals_preserved=true\nconstruction_sha256='
                       + entry['construction_sha256'] + '\nprocessing_sha256='
                       + sha(processing_paths[-1]) + '\n', encoding='utf-8')
        physical = HERE / ('physical-' + suffix + '-receipt.json')
        delivery = HERE / ('delivery-acceptance-' + suffix + '.json')
        entry['physical_preparation'] = {'receipt': physical.name, 'sha256': sha(physical)}
        entry['saved_replay'] = {'log': log.name, 'sha256': sha(log)}
        entry['post_capture'] = {
            'command': '.venv-cpu/bin/python runtime.py process-saved --manifest work/' + AID
                       + '/execution-manifest.json --case ' + case_id
                       + ' --attempt $ATTEMPT --output $PROCESSED --library runtime/library --validator $LEAN_VALIDATOR --owner-release-receipt $OWNER_RELEASE_RECEIPT',
            'feedback_command': '.venv-cpu/bin/python work/' + AID
                                + '/delivery_audit.py --case ' + case_id
                                + ' --attempt $ATTEMPT --processed $PROCESSED --output $AUDIT',
            'recorded_only': True, 'test_exit_code': 0,
            'test_log': log.name, 'test_log_sha256': sha(log)}
        entry['delivery_acceptance'] = json.loads(delivery.read_text(encoding='utf-8'))
        entry['native_handoff']['reviewed_packet_env_var'] = 'C149752_REVIEWED_PACKET'
    manifest['status'] = 'selected_cpu_proofs_bound_native_review_pending'
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


if __name__ == '__main__':
    bind()
    print('nine current-hash cases bound')
