"""Check every physical fixture against the current exact construction."""

import hashlib
import json
from pathlib import Path

from worker_exchange.physical_preparation import validate


root = Path(__file__).resolve().parent
index = json.loads((root / 'physical-preparation-proofs.json').read_text())
manifest = json.loads((root / 'probe-compatibility-manifest.json').read_text())
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
if sha(root / index['probe_script']) != index['probe_script_sha256']:
    raise ValueError('Physical fixture generator changed')
if len(index['cases']) != len(manifest['cases']) != 9:
    raise ValueError('Six exact case physical fixtures required')
lookup = {entry['case_id']: entry for entry in manifest['cases']}
for item in index['cases']:
    entry = lookup[item['case_id']]
    if sha(root / item['receipt']) != item['sha256']:
        raise ValueError('Physical proof receipt changed')
    proof = json.loads((root / item['receipt']).read_text())
    if proof['case_id'] != item['case_id'] or proof['construction_sha256'] != sha(root / entry['construction']):
        raise ValueError('Physical proof binds another exact construction')
    if not proof['lifecycle']['premature_seal_rejected']:
        raise ValueError('Premature capture seal was accepted')
    for fixture in proof['fixtures']:
        result = json.loads((root / fixture['result']).read_text())
        if result.get('diagnostic_fixture') is not True or result.get('physical_acceptance_claimed') is not False:
            raise ValueError('Synthetic outcome was presented as delivery evidence')
        if result.get('fixture_scope') != 'synthetic CPU original-source protocol; no actual Native observation':
            raise ValueError('Physical fixture scope differs')
    validate(root.parents[1], root, {**entry, 'physical_preparation':
             {'receipt': item['receipt'], 'sha256': item['sha256']}})
    print(item['case_id'], 'complete/incomplete/missing and lifecycle checks pass')
