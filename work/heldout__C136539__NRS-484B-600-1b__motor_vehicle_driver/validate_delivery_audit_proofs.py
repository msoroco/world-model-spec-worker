"""Check exact-case diagnostic audit and tamper rejection receipts."""

import hashlib
import json
from pathlib import Path


root = Path(__file__).resolve().parent
index = json.loads((root / 'delivery-audit-proofs.json').read_text())
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
if sha(root / index['script']) != index['script_sha256']:
    raise ValueError('Independent audit script changed')
if len(index['cases']) != 6:
    raise ValueError('Six exact delivery audit cases required')
for case in index['cases']:
    for name in ('positive', 'negative'):
        if sha(root / case[name]['log']) != case[name]['sha256']:
            raise ValueError('Delivery audit receipt changed')
    positive = json.loads((root / case['positive']['log']).read_text())
    if (positive['case_id'] != case['case_id'] or
            positive['scope'] != 'diagnostic software audit only' or
            positive['physical_acceptance_claimed'] is not False or
            positive['legal_acceptance_claimed'] is not False or
            set(positive['cameras']) != {'overview', 'approach', 'reference_corner', 'driver_reference'}):
        raise ValueError('Diagnostic audit claims an unproved delivery')
    if 'Original exposure source hash differs from saved report' not in (root / case['negative']['log']).read_text():
        raise ValueError('Missing tampered-source rejection')
    print(case['case_id'], 'diagnostic source pass; tamper rejected')
native_negative = index['native_required_negative']
if (sha(root / native_negative['log']) != native_negative['sha256'] or
        'Native capture closure or owner exit is unverified' not in (root / native_negative['log']).read_text()):
    raise ValueError('Unsealed fixture was accepted as Native delivery')
