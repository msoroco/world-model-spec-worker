"""Bind saved-only processing results executed through the exact handoff manifest."""

import hashlib
import json
from pathlib import Path


root = Path(__file__).resolve().parent
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
manifest = json.loads((root / 'execution-manifest.json').read_text())
index = {'format': 'worker-exposure-execution-saved-cpu-proofs',
         'scope': 'synthetic diagnostic saved processing through exact execution manifest; no Native physical claim',
         'manifest': 'execution-manifest.json',
         'manifest_sha256': sha(root / 'execution-manifest.json'),
         'cases': []}
for entry in manifest['cases']:
    suffix = entry['case_id'].split('__')[-1]
    log = f'cases/execution-saved-{suffix}.log'
    receipt = f'cases/execution-saved-{suffix}.json'
    index['cases'].append({'case_id': entry['case_id'],
                           'construction_sha256': sha(root / entry['construction']),
                           'log': log, 'log_sha256': sha(root / log),
                           'receipt': receipt, 'receipt_sha256': sha(root / receipt)})
(root / 'execution-saved-proofs.json').write_text(json.dumps(index, indent=2) + '\n')
