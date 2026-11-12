"""Check canonical clearance policy, exact paths and independent audit bindings."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ASSIGNMENT = HERE.parents[1]
REPO = ASSIGNMENT.parent.parent
STAGE = HERE / 'clearance_guard'
LABELS = ('primary', 'fallback1', 'fallback2', 'fallback3')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def validate():
    manifest_path = ASSIGNMENT / 'execution-manifest.json'
    entry = next(x for x in read(manifest_path)['cases'] if x['case_id'].endswith('__approaching_far'))
    policy = (ASSIGNMENT / 'hazard_sweep_policy.py').read_text()
    paths = []
    for label in LABELS:
        row = entry if label == 'primary' else next(x for x in entry['candidates'] if x['id'] == label)
        bundle = ASSIGNMENT / row['construction']
        if sha(bundle) != row['construction_sha256']:
            raise ValueError('Canonical construction changed: ' + label)
        embedded = [x['content'] for x in read(bundle)['files'] if x['path'] == 'hazard_sweep_policy.py']
        if embedded != [policy]:
            raise ValueError('Canonical policy differs: ' + label)
        offline = row['offline']
        if (offline['construction_sha256'] != row['construction_sha256'] or
                offline['log_sha256'] != sha(ASSIGNMENT / offline['log'])):
            raise ValueError('Canonical offline receipt changed: ' + label)
        spec = row['compatibility']
        receipt_path = ASSIGNMENT / spec['receipt']
        receipt = read(receipt_path)
        if (sha(receipt_path) != spec['sha256'] or
                receipt['construction_sha256'] != row['construction_sha256'] or
                receipt['candidate_id'] != label or receipt['passed'] is not True or
                receipt['negative_log_sha256'] != sha(ASSIGNMENT / spec['negative_log'])):
            raise ValueError('Canonical compatibility receipt changed: ' + label)
        post = row['post_capture']
        if (post['recorded_only'] is not True or post['test_exit_code'] != 0 or
                post['test_log_sha256'] != sha(ASSIGNMENT / post['test_log'])):
            raise ValueError('Canonical saved path changed: ' + label)
        processing = STAGE / 'promoted-proofs' / label / 'processing.json'
        saved = read(processing)
        if (saved['analysis_revision']['construction_sha256'] != row['construction_sha256'] or
                saved['recorded_only'] is not True or saved['passed'] is not True):
            raise ValueError('Canonical saved receipt changed: ' + label)
        paths.append({'candidate_id': label, 'construction_sha256': row['construction_sha256'],
                      'offline_log_sha256': offline['log_sha256'],
                      'compatibility_sha256': spec['sha256'],
                      'saved_processing_sha256': sha(processing)})
    physical_path = ASSIGNMENT / entry['physical_preparation']['receipt']
    if (sha(physical_path) != entry['physical_preparation']['sha256'] or
            read(physical_path)['construction_sha256'] != entry['construction_sha256']):
        raise ValueError('Canonical physical receipt changed')
    delivery = entry['delivery_acceptance']
    if (delivery['test_log_sha256'] != sha(ASSIGNMENT / delivery['test_log']) or
            delivery['negative_log_sha256'] != sha(ASSIGNMENT / delivery['negative_log'])):
        raise ValueError('Canonical delivery logs changed')
    audit = REPO / '.runtime-work/c109749-clearance-guard-far-delivery/attempt/far-diagnostic-audit.json'
    if (read(audit)['software_checks_passed'] is not True or
            read(audit)['physical_acceptance_claimed'] is not False):
        raise ValueError('Canonical delivery audit invalid')
    plan = read(ASSIGNMENT / 'case-plan.json')
    comparison = next(x for x in plan['comparisons'] if x['comparison_id'] == 'far_near_approach_margin')
    compare_path = ASSIGNMENT / comparison['diagnostic_receipt']
    source_path = ASSIGNMENT / comparison['source_comparison_receipt']
    if (sha(compare_path) != comparison['diagnostic_receipt_sha256'] or
            sha(source_path) != comparison['source_comparison_receipt_sha256'] or
            read(compare_path)['far_delivery_audit_sha256'] != sha(audit) or
            read(compare_path)['missing_camera_rejected'] is not True):
        raise ValueError('Canonical far/near comparison changed')
    result = {'format': 'worker-promoted-clearance-guard-proof',
              'case_id': entry['case_id'], 'manifest_sha256': sha(manifest_path),
              'policy_sha256': sha(ASSIGNMENT / 'hazard_sweep_policy.py'),
              'exact_paths': paths, 'physical_receipt_sha256': sha(physical_path),
              'delivery_audit_sha256': sha(audit), 'comparison_sha256': sha(compare_path),
              'source_comparison_sha256': sha(source_path),
              'canonical_cpu_rebind_passed': True, 'native_feasibility_proven': False,
              'legal_result_asserted': False}
    output = STAGE / 'promotion-proof-index.json'
    output.write_text(json.dumps(result, indent=2) + '\n')
    return {'exact_paths': len(paths), 'promotion_proof_index_sha256': sha(output)}


if __name__ == '__main__':
    print(json.dumps(validate(), sort_keys=True))
