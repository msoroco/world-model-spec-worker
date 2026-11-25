"""Independently audit six selected exact construction/compatibility receipts."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
MANIFEST = HERE / 'selected-30s-draft-execution-manifest.json'
CHECKS = {'actual_analysis', 'native_validation', 'mandatory_observations',
          'lean_decoder', 'render', 'final_decode', 'four_camera_sources',
          'selected_measurements', 'negative_case_source', 'acquisition_unchanged',
          'derived_outputs_rebuilt'}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


manifest = read(MANIFEST)
index = read(HERE / 'selected-30s/proof/index.json')
assert len(index['rows']) == 6 and len(manifest['cases']) == 2
rows = []
for entry in manifest['cases']:
    witness = entry['case_id'].rsplit('__', 1)[-1]
    recipe = REPO / entry['fixture_recipe']
    for selected in [entry, *entry['candidates']]:
        candidate = selected['id']
        path = HERE / selected['construction']
        proof = HERE / 'selected-30s/proof' / witness / candidate
        receipt_path = proof / 'compatibility.json'
        receipt = read(receipt_path)
        offline = proof / 'offline.log'
        assert sha(path) == selected['construction_sha256'] == receipt['construction_sha256']
        assert receipt['case_id'] == entry['case_id'] and receipt['candidate_id'] == candidate
        assert receipt['runtime_manifest_sha256'] == manifest['runtime_manifest_sha256']
        assert receipt['fixture_recipe_sha256'] == sha(recipe)
        assert receipt['measurement_contract_sha256'] == sha(HERE / entry['measurement_contract'])
        assert receipt['passed'] is True and CHECKS <= set(receipt['checks'])
        assert receipt['scope'] == 'diagnostic software compatibility only'
        assert receipt['log_sha256'] == sha(proof / 'positive.log')
        assert receipt['negative_log_sha256'] == sha(proof / 'negative.log')
        assert receipt['negative_removed'] == 'native-observed.jsonl'
        assert receipt['negative_error_contains'] in (proof / 'negative.log').read_text()
        offline_lines = offline.read_text().splitlines()
        assert json.loads(offline_lines[0])['passed'] is True
        assert 'Ran 2 tests' in offline.read_text() and 'OK' in offline.read_text()
        ref = next(row for row in index['rows'] if row['case_id'] == entry['case_id']
                   and row['candidate_id'] == candidate)
        assert ref['compatibility_receipt_sha256'] == sha(receipt_path)
        assert ref['offline_log_sha256'] == sha(offline)
        assert ref['positive_log_sha256'] == sha(proof / 'positive.log')
        assert ref['negative_log_sha256'] == sha(proof / 'negative.log')
        rows.append({'case_id': entry['case_id'], 'candidate_id': candidate,
                     'construction_sha256': selected['construction_sha256'],
                     'receipt_sha256': sha(receipt_path)})
out = {'format': 'c422978-selected-compat-audit-v1', 'passed': True,
       'original_native_observed': False, 'rows': rows}
path = HERE / 'selected-30s/proof/audit.json'
path.write_text(json.dumps(out, sort_keys=True, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'passed': True, 'receipts': len(rows), 'audit_sha256': sha(path)}))
