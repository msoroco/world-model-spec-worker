"""Verify recorded-only synthetic processing receipts without mutating the manifest."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
MANIFEST = HERE / 'execution-manifest.source-bound-diagnostic.json'
OUTPUT = HERE / 'diagnostic-saved-index.json'


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind() -> None:
    manifest = json.loads(MANIFEST.read_text())
    manifest_hash = sha(MANIFEST)
    if manifest['status'] != 'synthetic_diagnostic_only_unselected_original_capture_pending':
        raise ValueError('Only unselected synthetic diagnostic receipts can be indexed')
    rows = []
    for entry in manifest['cases']:
        case_id = entry['case_id']
        kind = case_id.removeprefix(HERE.name + '__')
        receipt_path = HERE / ('cpu-saved-' + kind + '.json')
        receipt = json.loads(receipt_path.read_text())
        selection_path = Path(receipt['version']).parents[1] / (
            'saved-source-' + kind.replace('_', '-') + '-bound') / 'candidate-selection.json'
        if not selection_path.is_file():
            selection_path = Path(receipt['version']).parents[1] / (
                'saved-source-' + kind.replace('_', '-')) / 'candidate-selection.json'
        selection = json.loads(selection_path.read_text())
        if (receipt.get('format') != 'worker-saved-processing' or
                receipt.get('case_id') != case_id or receipt.get('passed') is not True or
                receipt.get('recorded_only') is not True or
                receipt.get('originals_preserved') is not True or
                receipt.get('missing_evidence') is not False or
                receipt.get('physical_acceptance_claimed') is not False or
                receipt.get('legal_acceptance_claimed') is not False or
                receipt.get('candidate_id') != 'primary' or
                receipt.get('timestamp_joins', {}).get('frames') != 900 or
                receipt.get('final_video_checks', {}).get('frames') != 900 or
                selection.get('manifest_sha256') != manifest_hash or
                selection.get('construction_sha256') != entry['construction_sha256']):
            raise ValueError('Incomplete or stale recorded-only proof: ' + case_id)
        rows.append({'case_id': case_id, 'receipt': receipt_path.name,
                     'receipt_sha256': sha(receipt_path),
                     'candidate_selection_sha256': sha(selection_path),
                     'recorded_only': True, 'physical_acceptance_claimed': False})
    OUTPUT.write_text(json.dumps({'format': 'c150153-diagnostic-saved-index',
                                  'status': 'synthetic_diagnostic_only',
                                  'manifest_sha256': manifest_hash,
                                  'cases': rows}, indent=2) + '\n')
    print('Recorded-only exact diagnostic cases:', len(rows))


if __name__ == '__main__':
    bind()
