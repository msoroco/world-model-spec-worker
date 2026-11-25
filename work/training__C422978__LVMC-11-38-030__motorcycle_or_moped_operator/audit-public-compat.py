#!/usr/bin/env python3
"""Independently bind six current-runtime diagnostic compatibility receipts."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent.parent
BASE = ROOT / 'extended-primary'

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def read(path):
    return json.loads(path.read_text(encoding='utf-8'))

manifest = read(ROOT / 'current-30s-compatibility-manifest.json')
assert manifest['runtime_manifest_sha256'] == digest(REPO / 'runtime/SOURCE-MANIFEST.json')
expected_checks = {'acquisition_unchanged', 'actual_analysis', 'derived_outputs_rebuilt',
                   'final_decode', 'four_camera_sources', 'lean_decoder',
                   'mandatory_observations', 'native_validation', 'render',
                   'selected_measurements', 'negative_case_source'}
rows = []
for case in manifest['cases']:
    witness = case['case_id'].rsplit('__', 1)[-1]
    recipe = REPO / case['fixture_recipe']
    for candidate in ['primary'] + [x['id'] for x in case['candidates']]:
        selected = case if candidate == 'primary' else next(x for x in case['candidates'] if x['id'] == candidate)
        receipt_dir = BASE / 'public-compat' / witness / candidate
        receipt_path = receipt_dir / 'compatibility.json'
        receipt = read(receipt_path)
        assert receipt['passed'] is True and set(receipt['checks']) == expected_checks
        assert receipt['scope'] == 'diagnostic software compatibility only'
        assert receipt['case_id'] == case['case_id'] and receipt['candidate_id'] == candidate
        assert receipt['runtime_manifest_sha256'] == manifest['runtime_manifest_sha256']
        assert receipt['construction_sha256'] == selected['construction_sha256'] == digest(ROOT / selected['construction'])
        assert receipt['fixture_recipe_sha256'] == digest(recipe)
        assert receipt['measurement_contract_sha256'] == digest(ROOT / case['measurement_contract'])
        assert receipt['log_sha256'] == digest(receipt_dir / 'positive.log')
        assert receipt['negative_log_sha256'] == digest(receipt_dir / 'negative-analysis.log')
        assert receipt['negative_removed'] == 'native-observed.jsonl'
        assert receipt['negative_error_contains'] in (receipt_dir / 'negative-analysis.log').read_text(encoding='utf-8')
        rows.append({'case_id': case['case_id'], 'candidate_id': candidate,
                     'construction_sha256': receipt['construction_sha256'],
                     'fixture_recipe_sha256': receipt['fixture_recipe_sha256'],
                     'compatibility_receipt_sha256': digest(receipt_path),
                     'negative_log_sha256': receipt['negative_log_sha256'],
                     'checks': sorted(receipt['checks'])})
assert len(rows) == 6
out = {'format': 'c422978-public-compat-audit-v1',
       'scope': 'diagnostic CPU compatibility; no original Native or legal conclusion',
       'runtime_manifest_sha256': manifest['runtime_manifest_sha256'],
       'compatibility_manifest_sha256': digest(ROOT / 'current-30s-compatibility-manifest.json'),
       'rows': rows, 'passed': True}
(BASE / 'public-compat-audit.json').write_text(json.dumps(out, sort_keys=True, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'passed': True, 'receipt_count': len(rows), 'audit_sha256': digest(BASE / 'public-compat-audit.json')}))
