"""Check each exact selected case's portable delivery acceptance contract."""

import json
from pathlib import Path

from worker_exchange.delivery_handoff import validate_case


root = Path(__file__).resolve().parent
manifest = json.loads((root / 'execution-manifest.json').read_text())
if len(manifest['cases']) != 6:
    raise ValueError('Six exact exposure delivery cases required')
for entry in manifest['cases']:
    validate_case(root, entry, expected_sets={'held-out'})
    print(entry['case_id'], 'handoff acceptance contract pass')
