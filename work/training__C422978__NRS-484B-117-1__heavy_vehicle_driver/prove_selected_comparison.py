"""Bind the selected primary diagnostic pair to the existing source audit."""
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from prove_controlled_comparison import compare_bundles


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


manifest = json.loads((HERE / 'selected-draft-execution-manifest.json').read_text())
entries = {entry['case_id'].rsplit('__', 1)[-1]: entry for entry in manifest['cases']}
source = HERE / 'native/saved-fixtures'
reference = source / 'reference/primary'
contrast = source / 'contrast/primary'
metric = compare_bundles(reference, contrast)
assert metric['reference_moving_overlap_frames'] == 0
assert metric['contrast_moving_overlap_frames'] >= 390
receipts = {}
for suffix in ('reference', 'contrast'):
    entry = entries[suffix]
    spec = entry['compatibility']
    proof_path = HERE / spec['receipt']
    assert sha(proof_path) == spec['sha256']
    proof = json.loads(proof_path.read_text())
    observed = source / suffix / 'primary/native-observed.jsonl'
    assert proof['fixture_manifest']['native-observed.jsonl'] == sha(observed)
    receipts[suffix] = {'case_id': entry['case_id'],
                        'construction_sha256': entry['construction_sha256'],
                        'compatibility_sha256': sha(proof_path),
                        'native_observed_sha256': sha(observed)}
result = {'format': 'c422978-selected-controlled-comparison-cpu-v1',
          'selected_manifest_sha256': sha(HERE / 'selected-draft-execution-manifest.json'),
          'prior_comparison_sha256': sha(HERE / 'controlled-comparison.json'),
          'prior_independent_audit_sha256': sha(HERE / 'controlled-comparison-audit.json'),
          'selected_receipts': receipts, 'diagnostic_metric': metric,
          'synthetic_only': True, 'original_native_observed': False,
          'city_sidewalk_verified': False, 'operator_exception_verified': False,
          'legal_verdict': None, 'accepted_comparison': False}
(HERE / 'selected-controlled-comparison.json').write_text(
    json.dumps(result, indent=2, sort_keys=True) + '\n')
print(json.dumps({'passed': True, 'metric': metric}, sort_keys=True))
