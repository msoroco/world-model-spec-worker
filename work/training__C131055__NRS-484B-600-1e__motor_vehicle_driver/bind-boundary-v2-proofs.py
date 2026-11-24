"""Bind current exact-boundary CPU receipts without claiming physical acceptance."""
import hashlib
import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRATCH = ROOT / '.runtime-work/owner199'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text())


def save(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def proof(name):
    path = HERE / name
    return {'receipt': name, 'sha256': sha(path)}


manifest_path = HERE / 'execution-manifest.json'
manifest = load(manifest_path)
assert len(manifest['cases']) == 3
for index, entry in enumerate(manifest['cases'], 1):
    case = HERE.name + f'__controlled_{index}'
    assert entry['case_id'] == case
    for kind, target in (('primary', entry), ('fallback', entry['candidates'][0])):
        prefix = f'boundary-v2-{index}-{kind}'
        receipt = load(HERE / f'{prefix}-compatibility-receipt.json')
        saved = load(HERE / f'{prefix}-saved-receipt.json')
        audit = load(HERE / f'{prefix}-delivery-diagnostic-receipt.json')
        assert receipt['passed'] and receipt['case_id'] == case
        assert receipt['construction_sha256'] == target['construction_sha256']
        assert saved['passed'] and saved['recorded_only']
        assert audit['source_shape_passed'] and audit['physical_completion'] is False
        assert audit['selected_construction_sha256'] == target['construction_sha256']
        target['compatibility'] = proof(f'{prefix}-compatibility-receipt.json')
        target['negative'] = proof(f'{prefix}-negative-analysis.log')
        target['saved_processing'] = proof(f'{prefix}-saved-receipt.json')
        target['delivery_diagnostic'] = proof(f'{prefix}-delivery-diagnostic-receipt.json')
        target['preparation_status'] = 'current_v2_cpu_diagnostic_passed_original_native_pending'
    prefix = f'boundary-v2-{index}-primary'
    command = (f'.venv-cpu/bin/python work/{HERE.name}/delivery_audit.py '
               f'--case {case} --candidate primary '
               f'--attempt .runtime-work/owner199/{prefix}-compat '
               f'--processing .runtime-work/owner199/{prefix}-saved/v0001/processing.json '
               f'--output .runtime-work/owner199/{prefix}-audit.json --diagnostic')
    negative_command = command.replace(f'{prefix}-audit.json --diagnostic',
                                       f'{prefix}-negative-audit.json')
    negative_log = f'{prefix}-delivery-negative.log'
    entry['delivery_acceptance'] = {
        'case_id': case,
        'sets': ['full-train'],
        'checks': ['native_source', 'all_participants', 'time_join',
                   'full_video_decode', 'actual_pixels', 'physical_completion'],
        'script': 'delivery_audit.py',
        'script_sha256': sha(HERE / 'delivery_audit.py'),
        'command': command,
        'test_exit_code': 0,
        'test_log': f'{prefix}-delivery-diagnostic-receipt.json',
        'test_log_sha256': sha(HERE / f'{prefix}-delivery-diagnostic-receipt.json'),
        'negative_command': negative_command,
        'negative_exit_code': 1,
        'negative_expected_error': 'Original Native roundabout source required',
        'negative_log': negative_log,
        'negative_log_sha256': sha(HERE / negative_log),
        'physical_acceptance': False,
    }

comparison = HERE / 'boundary-v2-selected-comparison-receipt.json'
shutil.copyfile(SCRATCH / 'boundary-v2-selected-comparison.json', comparison)
assert load(comparison)['passed']
manifest['selected_comparison_diagnostic'] = proof(comparison.name)
manifest['fallback_isolation_diagnostic'] = proof('fallback-isolation-v3-receipt.json')
manifest['canonical_semantic_local_validation'] = proof('semantic-validation.log')
manifest['canonical_delivery_local_validation'] = proof('delivery-contract-validation.log')
manifest['physical_audit_source_shape_tests'] = [
    proof('boundary-v2-source-shape-2.log'),
    proof('boundary-v2-source-shape-3.log'),
]
manifest['boundary_disposition']['sha256'] = sha(HERE / 'boundary-disposition.json')
manifest['boundary_disposition']['script_sha256'] = sha(HERE / 'boundary_disposition.py')
manifest['status'] = 'partial_three_case_current_v2_cpu_proved_original_native_pending'
save(manifest_path, manifest)

plan_path = HERE / 'case-plan.json'
plan = load(plan_path)
plan['boundary_disposition']['sha256'] = sha(HERE / 'boundary-disposition.json')
save(plan_path, plan)

result_path = HERE / 'result.json'
result = load(result_path)
result.update({
    'status': 'partial',
    'boundary_disposition_sha256': sha(HERE / 'boundary-disposition.json'),
    'canonical_semantic_status': 'three_case_cpu_validated_original_measured_at_unverified',
    'canonical_semantic_rejection_log_sha256': None,
    'canonical_semantic_validation_log_sha256': sha(HERE / 'semantic-validation.log'),
    'canonical_delivery_acceptance_status': 'three_case_cpu_contract_validated_original_native_pending',
    'canonical_delivery_cpu_contract_log_sha256': sha(HERE / 'delivery-contract-validation.log'),
    'selected_cpu_proof_count': 6,
    'selected_comparison_receipt_sha256': sha(comparison),
    'fallback_isolation_receipt_sha256': sha(HERE / 'fallback-isolation-v3-receipt.json'),
    'reason': ('Three exact selected below/at/above current-v2 CPU diagnostic cases and '
               'all three shared fallbacks passed source-negative public compatibility '
               'and recorded-only saved processing. Accepted at-membership has request '
               'only and zero reuse; original Native measured speed and pixels remain '
               'unverified.'),
})
save(result_path, result)
print(json.dumps({'manifest_sha256': sha(manifest_path),
                  'comparison_sha256': sha(comparison),
                  'fallback_sha256': sha(HERE / 'fallback-isolation-v3-receipt.json')}))
