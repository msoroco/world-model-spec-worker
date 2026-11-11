"""Check the four current source-comparison behavior receipts."""

import hashlib
import json
from pathlib import Path


root = Path(__file__).resolve().parent
index = json.loads((root / 'comparison-diagnostic-proofs.json').read_text())
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
if index['script_sha256'] != sha(root / index['script']):
    raise ValueError('Comparison audit code changed')
if len(index['pairs']) != 4:
    raise ValueError('Four controlled comparisons required')
for item in index['pairs']:
    for key in ('result', 'positive_log', 'negative_log'):
        if sha(root / item[key]) != item[key + '_sha256']:
            raise ValueError('Comparison receipt changed')
    result = json.loads((root / item['result']).read_text())
    if result['comparison_id'] != item['comparison_id'] or result['physical_acceptance_claimed'] is not False or result['legal_acceptance_claimed'] is not False:
        raise ValueError('Diagnostic comparison claims a physical or legal outcome')
    if 'Comparison fixed road geometry changed' not in (root / item['negative_log']).read_text():
        raise ValueError('Fixed-road tamper was not rejected')
    print(item['comparison_id'], 'source comparison and fixed-road rejection pass')
