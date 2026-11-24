"""Independent checks over the retained current v2 diagnostic receipts."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
P = HERE / 'witness_1/proofs'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


manifest = json.loads((ROOT / 'v2-primary-manifest.json').read_text())
case = manifest['cases'][0]
compat = json.loads((P / 'compatibility.json').read_text())
processing = json.loads((P / 'processing.json').read_text())
analysis = json.loads((P / 'analysis-report.json').read_text())
selection = json.loads((P / 'candidate-selection.json').read_text())
assert compat['passed'] is True and processing['passed'] is True
assert compat['case_id'] == case['case_id']
assert compat['construction_sha256'] == case['construction_sha256']
assert compat['scope'] == 'diagnostic software compatibility only'
assert compat['analysis_report_sha256'] == sha(P / 'analysis-report.json')
assert compat['negative_log_sha256'] == sha(P / 'negative-analysis.log')
assert compat['measurement_contract_sha256'] == sha(ROOT / case['measurement_contract'])
assert compat['fixture_recipe_sha256'] == sha(ROOT.parents[1] / case['fixture_recipe'])
assert compat['measurement_keys'] == ['arrow_movement']
assert compat['negative_removed'] == 'native-raw-actors.jsonl'
assert compat['negative_error_contains'] in (P / 'negative-analysis.log').read_text()
assert processing['missing_evidence'] is False
assert processing['physical_acceptance_claimed'] is False
assert processing['legal_acceptance_claimed'] is False
assert analysis['physical_acceptance_claimed'] is False
assert analysis['legal_acceptance_claimed'] is False
assert selection['case_id'] == case['case_id']
value = compat['measurement_examples']['arrow_movement']['value']
assert value['frames'] == value['observed_steady_red_frames'] == value['observed_green_head_frames'] == 600
assert value['observed_heading_change_deg'] == 90.0
for key in ('arrow_pixels_verified', 'governing_direction_verified',
            'other_traffic_lawfulness_verified', 'native_provenance'):
    assert value[key] is False
print(json.dumps({'passed': True, 'manifest_sha256': sha(ROOT / 'v2-primary-manifest.json'),
                  'compatibility_sha256': sha(P / 'compatibility.json'),
                  'processing_sha256': sha(P / 'processing.json'),
                  'analysis_sha256': sha(P / 'analysis-report.json'),
                  'negative_sha256': sha(P / 'negative-analysis.log')}))

other_manifest = json.loads((ROOT / 'v2-witness2-manifest.json').read_text())
other_case = other_manifest['cases'][0]
Q = HERE / 'witness_2/proofs'
other_compat = json.loads((Q / 'compatibility.json').read_text())
other_processing = json.loads((Q / 'processing.json').read_text())
assert other_compat['passed'] is True and other_processing['passed'] is True
assert other_compat['case_id'] == other_case['case_id']
assert other_compat['construction_sha256'] == other_case['construction_sha256']
assert other_compat['analysis_report_sha256'] == sha(Q / 'analysis-report.json')
assert other_compat['negative_log_sha256'] == sha(Q / 'negative-analysis.log')
assert other_compat['measurement_contract_sha256'] == sha(ROOT / other_case['measurement_contract'])
assert other_compat['fixture_recipe_sha256'] == sha(ROOT.parents[1] / other_case['fixture_recipe'])
assert other_compat['negative_removed'] == 'native-raw-actors.jsonl'
assert other_compat['negative_error_contains'] in (Q / 'negative-analysis.log').read_text()
assert other_processing['missing_evidence'] is False
assert other_processing['physical_acceptance_claimed'] is False
assert other_processing['legal_acceptance_claimed'] is False
other_value = other_compat['measurement_examples']['arrow_movement']['value']
assert other_value['frames'] == other_value['observed_steady_red_frames'] == other_value['observed_green_head_frames'] == 600
assert other_value['observed_heading_change_deg'] == 0.0
assert value['observed_heading_change_deg'] - other_value['observed_heading_change_deg'] == 90.0
for key in ('arrow_pixels_verified', 'governing_direction_verified',
            'other_traffic_lawfulness_verified', 'native_provenance'):
    assert other_value[key] is False
print(json.dumps({'passed': True, 'manifest_sha256': sha(ROOT / 'v2-witness2-manifest.json'),
                  'compatibility_sha256': sha(Q / 'compatibility.json'),
                  'processing_sha256': sha(Q / 'processing.json'),
                  'analysis_sha256': sha(Q / 'analysis-report.json'),
                  'negative_sha256': sha(Q / 'negative-analysis.log'),
                  'diagnostic_heading_delta_deg': 90.0}))
