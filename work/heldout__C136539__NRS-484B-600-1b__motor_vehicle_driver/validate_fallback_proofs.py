"""Verify all exact exposure fallback constructions and CPU proof bindings."""

import json
from pathlib import Path

from worker_exchange.candidate_constructions import validate


root = Path(__file__).resolve().parent
manifest = json.loads((root / 'fallback-constructions-manifest.json').read_text())
if len(manifest['cases']) != 6:
    raise ValueError('All six exact exposure cases require fallback risk plans')
for entry in manifest['cases']:
    result = validate(root, entry, 'NRS-484B-600-1b', 'C136539',
                      required=True, require_alternate=True, candidate_count=4)
    print(result['case_id'], ','.join(result['fallbacks']))
