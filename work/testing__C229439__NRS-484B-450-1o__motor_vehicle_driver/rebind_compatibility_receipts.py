"""Rebind concurrently completed exact compatibility receipts without re-execution."""
import hashlib
import json
from pathlib import Path

folder = Path(__file__).resolve().parent
path = folder / 'execution-manifest.json'
manifest = json.loads(path.read_text())
for entry in manifest['cases']:
    short = entry['case_id'].rsplit('__', 1)[-1]
    receipt = folder / 'cases' / short / 'compatibility.json'
    data = json.loads(receipt.read_text())
    if data['case_id'] != entry['case_id'] or data['construction_sha256'] != entry['construction_sha256'] or data['passed'] is not True:
        raise ValueError('compatibility receipt differs from current construction: ' + short)
    entry['compatibility'] = {'receipt': f'cases/{short}/compatibility.json',
                              'sha256': hashlib.sha256(receipt.read_bytes()).hexdigest(),
                              'log': f'cases/{short}/cpu-compatibility-analysis.log'}
    entry['negative'] = {'log': f'cases/{short}/negative-analysis.log'}
path.write_text(json.dumps(manifest, indent=2) + '\n')
