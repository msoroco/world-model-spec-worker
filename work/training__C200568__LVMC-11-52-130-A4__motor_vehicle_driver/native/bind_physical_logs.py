"""Bind completed CPU fixture logs into each physical preparation receipt."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for path in sorted((ROOT / 'native').glob('physical-*/physical-preparation.json')):
    receipt = json.loads(path.read_text())
    log = path.parent / 'physical.log'
    digest = hashlib.sha256(log.read_bytes()).hexdigest()
    for fixture in receipt['fixtures']:
        fixture['log_sha256'] = digest
    receipt['lifecycle']['log_sha256'] = digest
    path.write_text(json.dumps(receipt, indent=2) + '\n')
print('bound', len(list((ROOT / 'native').glob('physical-*/physical-preparation.json'))))
