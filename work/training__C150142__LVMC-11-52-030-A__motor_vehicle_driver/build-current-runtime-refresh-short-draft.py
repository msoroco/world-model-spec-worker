"""Stage current-runtime short cases without treating historical receipts as current."""

import hashlib
import json
from pathlib import Path


WORK = Path(__file__).resolve().parent
REPO = WORK.parents[1]
SOURCE = WORK / 'current-runtime-runner-short-bound-manifest.json'
TARGET = WORK / 'current-runtime-refresh-short-draft-manifest.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run():
    data = json.loads(SOURCE.read_text())
    current = sha(REPO / 'runtime/SOURCE-MANIFEST.json')
    old = data['runtime_manifest_sha256']
    if current == old:
        raise ValueError('Runtime has not changed; use retained validated proofs')
    if len(data['cases']) != 30:
        raise ValueError('Expected 30 exact selected draft cases')
    for entry in data['cases']:
        entry.pop('compatibility', None)
        entry.pop('negative', None)
        for candidate in entry['candidates']:
            candidate.pop('compatibility', None)
            candidate.pop('negative', None)
    data['runtime_manifest_sha256'] = current
    data['status'] = 'draft_current_runtime_refresh_short_proofs_pending'
    data['delivery_ready'] = False
    TARGET.write_text(json.dumps(data, sort_keys=True, indent=2) + '\n')
    return {'source_manifest_sha256': sha(SOURCE),
            'prior_runtime_manifest_sha256': old,
            'current_runtime_manifest_sha256': current,
            'draft_manifest_sha256': sha(TARGET),
            'cases': len(data['cases']), 'short_cases_to_reprove': 14,
            'delivery_ready': False}


if __name__ == '__main__':
    print(json.dumps(run(), sort_keys=True))
