"""Independent source/channel checks on every selected saved diagnostic fixture."""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

from delivery_audit import audit_saved_channels

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def main() -> None:
    report = {'format': 'worker-fire-lane-saved-audit-diagnostics',
              'auditor_sha256': hashlib.sha256((ROOT / 'delivery_audit.py').read_bytes()).hexdigest(),
              'cases': {}, 'negative': {}, 'physical_acceptance_claimed': False}
    manifest = json.loads((ROOT / 'execution-manifest.json').read_text())
    for entry in manifest['cases']:
        case_id = entry['case_id']
        suffix = case_id.removeprefix(ROOT.name + '__')
        attempt = REPO / '.runtime-work' / ('c150099-saved-proof-' + suffix + '-v8/v0001/analysis')
        report['cases'][case_id] = audit_saved_channels(attempt, case_id, allow_diagnostic=True)
    first = manifest['cases'][0]['case_id']
    source = REPO / '.runtime-work/c150099-saved-proof-public_park_attended-v8/v0001/analysis'
    tampered = REPO / '.runtime-work/c150099-saved-audit-tamper-v5'
    if tampered.exists():
        raise ValueError('retain prior tamper fixture; choose a new version')
    shutil.copytree(source, tampered)
    channel = tampered / 'channels/activity.jsonl'
    rows = channel.read_text().splitlines()
    changed = json.loads(rows[0]); changed['value'] = 'moving'
    rows[0] = json.dumps(changed)
    channel.write_text('\n'.join(rows) + '\n')
    try:
        audit_saved_channels(tampered, first, allow_diagnostic=True)
    except ValueError as error:
        if 'saved channel differs from original: activity' not in str(error):
            raise
        report['negative'] = {'case_id': first, 'expected_error': str(error)}
    else:
        raise ValueError('tampered saved channel was accepted')
    (ROOT / 'cpu-saved-channel-audit.json').write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
    print('saved source/channel audit passed:', len(report['cases']),
          'positive, 1 tamper negative')


if __name__ == '__main__':
    main()
