"""Check exact manifest saved-processing receipts and source preservation."""

import hashlib
import json
from pathlib import Path


root = Path(__file__).resolve().parent
index = json.loads((root / 'execution-saved-proofs.json').read_text())
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
if sha(root / index['manifest']) != index['manifest_sha256']:
    raise ValueError('Execution manifest changed after saved processing proof')
manifest = json.loads((root / index['manifest']).read_text())
entries = {entry['case_id']: entry for entry in manifest['cases']}
if len(index['cases']) != len(entries) or len(entries) != 9:
    raise ValueError('Nine exact saved execution proofs required')
for item in index['cases']:
    entry = entries[item['case_id']]
    if (sha(root / entry['construction']) != item['construction_sha256'] or
            sha(root / item['log']) != item['log_sha256'] or
            sha(root / item['receipt']) != item['receipt_sha256']):
        raise ValueError('Saved execution proof changed')
    receipt = json.loads((root / item['receipt']).read_text())
    if (receipt.get('case_id') != item['case_id'] or receipt.get('passed') is not True or
            receipt.get('recorded_only') is not True or
            receipt.get('originals_preserved') is not True or
            receipt.get('missing_evidence') is not False or
            receipt.get('physical_acceptance_claimed') is not False or
            receipt.get('legal_acceptance_claimed') is not False):
        raise ValueError('Saved execution receipt claims an unsupported outcome')
    if entry['post_capture']['test_log'] != item['log'] or entry['post_capture']['test_log_sha256'] != item['log_sha256']:
        raise ValueError('Handoff post-capture command lacks this exact proof')
    print(item['case_id'], 'saved processing and original preservation pass')
