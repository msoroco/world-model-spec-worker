"""Check all six synthetic saved-processing receipts against current sources."""

import hashlib
import json
from pathlib import Path


root = Path(__file__).resolve().parent
proof = json.loads((root / 'primary-saved-proofs.json').read_text())
manifest = json.loads((root / proof['manifest']).read_text())
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
if len(proof['cases']) != len(manifest['cases']) != 9:
    raise ValueError('Nine exact primary cases required')
if sha(root / proof['manifest']) != proof['manifest_sha256']:
    raise ValueError('Primary manifest changed')
entries = {entry['case_id']: entry for entry in manifest['cases']}
for case in proof['cases']:
    entry = entries[case['case_id']]
    if sha(root / entry['construction']) != case['construction_sha256']:
        raise ValueError('Primary construction changed')
    construction = json.loads((root / entry['construction']).read_text())
    files = {item['path']: item['content'] for item in construction['files']}
    if files['runner.py'] != files['native_exposure_cases.py']:
        raise ValueError('Capture seal runner alias differs from executed Native entrypoint')
    for name, expected in (
        ('compatibility_receipt', 'compatibility_sha256'),
        ('negative_log', 'negative_log_sha256'),
        ('saved_receipt', 'saved_receipt_sha256'),
        ('saved_log', 'saved_log_sha256')):
        if sha(root / case[name]) != case[expected]:
            raise ValueError(f'{case["case_id"]}: {name} changed')
    saved = json.loads((root / case['saved_receipt']).read_text())
    if (saved.get('passed') is not True or saved.get('originals_preserved') is not True
            or saved.get('missing_evidence') is not False
            or saved.get('physical_acceptance_claimed') is not False
            or saved.get('legal_acceptance_claimed') is not False):
        raise ValueError('Saved proof claims wrong processing outcome')
    print(case['case_id'], 'saved software pass; physical/legal false')
