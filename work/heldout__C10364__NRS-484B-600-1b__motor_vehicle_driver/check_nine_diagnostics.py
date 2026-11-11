"""Check current exact nine-case CPU diagnostic receipts and source hashes."""

from hashlib import sha256
import json
from pathlib import Path

from worker_exchange.package_compatibility import check_receipts
from worker_exchange.candidate_constructions import validate as validate_candidates


root = Path(__file__).resolve().parent
repo = root.parents[1]
read = lambda path: json.loads(path.read_text())
digest = lambda path: sha256(path.read_bytes()).hexdigest()
construction = read(root / 'construction-probe-manifest.json')
compatibility = read(root / 'probe-compatibility-manifest.json')
if len(construction['cases']) != 9 or len(compatibility['cases']) != 9:
    raise ValueError('Nine exact alley cases required')
check_receipts(repo, root, compatibility)
by_id = {entry['case_id']: entry for entry in compatibility['cases']}
for entry in construction['cases']:
    case_id = entry['case_id']
    if case_id not in by_id or entry['construction_sha256'] != digest(root / entry['construction']):
        raise ValueError('Current exact construction hash differs: ' + case_id)
    suffix = case_id.split('__')[-1]
    offline = read(root / 'cases' / ('case-offline-' + suffix + '-primary.log'))
    if offline['case_id'] != case_id or offline['offline_passed'] is not True:
        raise ValueError('Exact offline proof failed: ' + case_id)
    receipt = read(root / by_id[case_id]['compatibility']['receipt'])
    if receipt['construction_sha256'] != entry['construction_sha256'] or not receipt['passed']:
        raise ValueError('Compatibility construction revision differs: ' + case_id)
    saved = read(root / 'cases' / ('saved-' + suffix + '.json'))
    if (saved['case_id'] != case_id or saved['passed'] is not True or
            saved['recorded_only'] is not True or
            saved['originals_preserved'] is not True or
            saved['missing_evidence'] is not False or
            saved['physical_acceptance_claimed'] is not False or
            saved['legal_acceptance_claimed'] is not False or
            saved['analysis_revision']['construction_sha256'] != entry['construction_sha256']):
        raise ValueError('Saved diagnostic proof differs: ' + case_id)
    validate_candidates(root, by_id[case_id], 'NRS-484B-600-1b', 'C10364',
                        required=True, require_alternate=True, candidate_count=4)
print('Nine exact primary/saved and 27 fallback offline/compatibility alley diagnostics validate')
