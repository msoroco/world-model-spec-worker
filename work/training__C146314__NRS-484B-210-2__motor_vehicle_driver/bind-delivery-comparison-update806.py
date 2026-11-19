"""Bind current saved-source comparison and original-only delivery CPU checks."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    path = HERE / 'execution-manifest.json'
    manifest = json.loads(path.read_text())
    comparison_log = HERE / 'update806-current-comparison.log'
    comparison = json.loads(comparison_log.read_text())
    if (comparison['passed'] is not True or
            len(comparison['positive_diagnostic_pairs']) != 4 or
            len(comparison['negative_rejections']) != 16 or
            comparison['original_native_observed'] is not False):
        raise ValueError('Current independent comparison incomplete')
    proof = HERE / 'update806-current-comparison.json'
    proof.write_text(json.dumps(comparison, indent=2) + '\n')
    delivery = json.loads((HERE / 'update806-current-delivery-diagnostic.log').read_text())
    if (delivery['passed'] is not True or
            len(delivery['source_shaped_diagnostics']) != 8 or
            len(delivery['negative_rejections']) != 24 or
            delivery['original_native_observed'] is not False):
        raise ValueError('Current saved-source delivery mechanics incomplete')
    manifest['comparison_audit'] = {
        'script': 'native/audit_saved_comparison_update806.py',
        'script_sha256': sha(HERE / 'native/audit_saved_comparison_update806.py'),
        'log': comparison_log.name, 'log_sha256': sha(comparison_log),
        'receipt': proof.name, 'receipt_sha256': sha(proof),
        'pairs': 4, 'original_native_accepted': False}
    manifest['current_saved_delivery_diagnostic'] = {
        'script': 'native/prove_delivery_audit-update806.py',
        'script_sha256': sha(HERE / 'native/prove_delivery_audit-update806.py'),
        'log': 'update806-current-delivery-diagnostic.log',
        'log_sha256': sha(HERE / 'update806-current-delivery-diagnostic.log'),
        'candidates': 8, 'original_native_accepted': False}
    for entry in manifest['cases']:
        witness = entry['case_id'].removeprefix(HERE.name + '__')
        positive = HERE / f'update806-{witness}-delivery-positive.log'
        negative = HERE / f'update806-{witness}-delivery-negative.log'
        if '"original_native_observed": false' not in positive.read_text() or \
                'EXPECTED CPU MOCK REJECTION: Original delivery sources changed' not in negative.read_text():
            raise ValueError('Original-only delivery branch proof differs')
        contract = entry['delivery_acceptance']
        contract.update({'test_exit_code': 0, 'test_log': positive.name,
                         'test_log_sha256': sha(positive), 'negative_exit_code': 2,
                         'negative_log': negative.name,
                         'negative_log_sha256': sha(negative)})
    manifest['status'] = 'selected_cpu_proofs_rebound_current_json_graphs_original_unverified'
    path.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'cases': 2, 'pairs': 4, 'manifest_sha256': sha(path)}))


if __name__ == '__main__':
    main()
