"""Bind final-current source audits without claiming original Native acceptance."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / 'execution-manifest.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


manifest = json.loads(MANIFEST.read_text())
comparison = HERE / 'update072-comparison-proof.json'
comparison_log = HERE / 'update072-comparison-proof.log'
if json.loads(comparison.read_text())['passed'] is not True:
    raise ValueError('Current comparison did not pass')
manifest['comparison_diagnostic'] = {
    'receipt': comparison.name, 'sha256': sha(comparison),
    'log': comparison_log.name, 'log_sha256': sha(comparison_log),
    'source_kind': 'synthetic_native_sample',
    'physical_acceptance_claimed': False,
}
for entry in manifest['cases']:
    case = entry['case_id'].removeprefix(HERE.name + '__')
    attempt = ('.runtime-work/c177225-update071/reference/primary/compatibility'
               if case == 'reference' else
               '.runtime-work/c177225-update071b/contrast/primary/compatibility')
    physical = HERE / f'update069-{case}-complete_motion-physical.json'
    physical_log = HERE / f'update069-{case}-complete_motion-physical.log'
    audit = HERE / f'update072-{case}-delivery-audit.json'
    audit_log = HERE / f'update072-{case}-delivery-audit.log'
    acceptance = HERE / f'update072-{case}-delivery-acceptance.json'
    acceptance_log = HERE / f'update072-{case}-delivery-acceptance.log'
    negative_log = HERE / f'update072-{case}-delivery-negative.log'
    if (json.loads(physical.read_text())['physical_checks']['maneuver']['status'] != 'met' or
            json.loads(audit.read_text())['delivery_accepted'] is not False or
            json.loads(acceptance.read_text())['delivery_accepted'] is not False or
            'Missing delivery source: capture-seal.json' not in negative_log.read_text()):
        raise ValueError('Current diagnostic acceptance claims differ')
    entry['diagnostic_physical_outcome'] = {
        'result': physical.name, 'sha256': sha(physical),
        'log': physical_log.name, 'log_sha256': sha(physical_log),
        'scope': 'synthetic fixture measured target; original Native unobserved',
    }
    entry['delivery_audit_diagnostic'] = {
        'script': 'audit_delivery.py', 'script_sha256': sha(HERE / 'audit_delivery.py'),
        'receipt': audit.name, 'receipt_sha256': sha(audit),
        'log': audit_log.name, 'log_sha256': sha(audit_log),
        'scope': 'synthetic source audit only; delivery_accepted=false',
    }
    claim = entry['delivery_acceptance']
    claim['command'] = (f'.venv-cpu/bin/python work/{HERE.name}/delivery_acceptance.py '
                        f'--attempt {attempt} --case {entry["case_id"]} --diagnostic '
                        f'--output work/{HERE.name}/{acceptance.name}')
    claim['test_exit_code'] = 0
    claim['test_log'] = acceptance_log.name
    claim['test_log_sha256'] = sha(acceptance_log)
    claim['negative_command'] = (
        f'.venv-cpu/bin/python work/{HERE.name}/delivery_acceptance.py '
        f'--attempt {attempt} --case {entry["case_id"]} '
        '--owner-receipt .runtime-work/nonexistent-owner-receipt.json '
        '--processing-receipt .runtime-work/nonexistent-processing-receipt.json '
        f'--output work/{HERE.name}/update072-{case}-delivery-negative.json')
    claim['negative_exit_code'] = 1
    claim['negative_expected_error'] = 'Missing delivery source: capture-seal.json'
    claim['negative_log'] = negative_log.name
    claim['negative_log_sha256'] = sha(negative_log)
    claim['dependencies_sha256'] = {name: sha(HERE / name) for name in
                                    ('audit_delivery.py', 'physical_outcome.py',
                                     'lifecycle_preparation.py')}
MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')
print(json.dumps({'manifest_sha256': sha(MANIFEST), 'cases': len(manifest['cases'])}))
