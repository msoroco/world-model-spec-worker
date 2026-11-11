"""Bind current offline and sealed signal-distance CPU draft proofs."""
import hashlib
import json
from pathlib import Path

folder = Path(__file__).resolve().parent
assignment = folder.parents[1]
manifest = json.loads((folder / 'draft-manifest.json').read_text())['cases'][0]
case = manifest['case_id']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


claims = []
for label, item in [('primary', manifest),
                    *[(candidate['id'], candidate) for candidate in manifest['candidates']]]:
    path = folder / item['construction']
    if sha(path) != item['construction_sha256']:
        raise ValueError('Draft construction changed: ' + label)
    log = folder / (label + '-offline.log')
    output = json.loads(log.read_text())
    if (output.get('case_id') != case or output.get('candidate_id') != label or
            output.get('offline_passed') is not True or output.get('simulation_started') is not False):
        raise ValueError('Exact offline proof missing: ' + label)
    command = (f'.venv-cpu/bin/python runtime.py offline --manifest '
               f'work/{assignment.name}/cases/{folder.name}/draft-manifest.json '
               f'--case {case} --output '
                   f'.runtime-work/c109749-signal-advance-100-at-{label}-offline-v3')
    if label != 'primary':
        command += ' --candidate ' + label
    claims.append({'candidate_id': label, 'construction_sha256': sha(path),
                   'command': command, 'log': log.name, 'log_sha256': sha(log),
                   'exit_code': 0, 'simulation_started': False})
proof_log = folder / 'signal-distance-proof.log'
summary = json.loads(proof_log.read_text())
if (summary.get('software_checks_passed') is not True or
        summary.get('physical_acceptance_claimed') is not False or
        summary.get('legal_verdict_asserted') is not False or
        len(summary.get('results', [])) != 6 or
        not summary.get('interrupted_rejected') or
        not summary.get('changed_seal_rejected')):
    raise ValueError('Six source-bound signal contrasts are not proved')
exact = json.loads((folder / 'exact-proof-receipt.json').read_text())
if (exact.get('case_id') != case or len(exact.get('proofs', [])) != 4 or
        exact.get('fixture_recipe_sha256') != sha(folder / 'diagnostic-recipe.json') or
        exact.get('diagnostic_sha256') != sha(folder / 'diagnostic.json') or
        exact.get('measurement_contract_sha256') != sha(folder / 'measurement-contract.json') or
        any(not p['compatibility']['passed'] or not p['saved']['passed']
            for p in exact['proofs'])):
    raise ValueError('Current exact diagnostic proofs incomplete')
delivery = json.loads((folder / 'delivery-proof-receipt.json').read_text())
if (delivery.get('case_id') != case or delivery.get('frames') != 900 or
        delivery.get('software_checks_passed') is not True or
        delivery.get('passed') is not False or
        delivery.get('auditor_sha256') != sha(assignment / 'signal_advance_delivery_audit.py') or
        delivery.get('diagnostic_source_sha256') != sha(folder / 'diagnostic.json')):
    raise ValueError('Current full-duration diagnostic audit incomplete')
comparison_path = assignment / 'signal-advance-comparison-receipt.json'
comparison = json.loads(comparison_path.read_text())
if (comparison.get('signalled_case_id') != case or
        comparison.get('software_checks_passed') is not True or
        comparison.get('fixed_samples') != 900 or
        comparison.get('audit_sha256') != sha(assignment / 'signal_advance_comparison_audit.py')):
    raise ValueError('Current fixed-condition comparison proof incomplete')
receipt = {'format': 'worker-signal-advance-construction-draft',
           'case_id': case, 'canonical_selected': False,
           'physical_acceptance_claimed': False, 'legal_verdict_asserted': False,
           'offline': claims,
           'signal_source_proof': {
               'command': f'.venv-cpu/bin/python work/{assignment.name}/cases/{folder.name}/signal_distance_fixture_proof.py '
                          '--output-root .runtime-work/c109749-signal-distance-fixture-v2',
               'script_sha256': sha(folder / 'signal_distance_fixture_proof.py'),
               'auditor_sha256': sha(assignment / 'signal_advance_audit.py'),
               'log': proof_log.name, 'log_sha256': sha(proof_log),
               'diagnostic_fixture': True, 'frames_per_branch': 900,
               'results': summary['results']},
           'measurement_draft': {
               'finalizer_sha256': sha(folder / 'finalizer.py'),
               'contract_sha256': sha(folder / 'measurement-contract.json'),
               'validation_command': f'.venv-cpu/bin/python work/{assignment.name}/cases/{folder.name}/validate_measurement_draft.py',
               'validation_script_sha256': sha(folder / 'validate_measurement_draft.py'),
               'validation_log': 'measurement-draft-validation.log',
               'validation_log_sha256': sha(folder / 'measurement-draft-validation.log'),
               'contract_validated': True,
               'sealed_source_threshold_checked': True,
               'exact_compatibility_passed': True,
               'saved_processing_passed': True},
           'exact_diagnostic_proof': {
               'receipt': 'exact-proof-receipt.json',
               'sha256': sha(folder / 'exact-proof-receipt.json'),
               'diagnostic_frames': 210,
               'positive_compatibility_candidates': 4,
               'recorded_only_saved_candidates': 4,
               'full_duration_delivery_proved': True},
           'delivery_diagnostic_proof': {'receipt': 'delivery-proof-receipt.json',
                                         'sha256': sha(folder / 'delivery-proof-receipt.json'),
                                         'software_checks_passed': True,
                                         'physical_acceptance_claimed': False},
           'fixed_condition_comparison': {'receipt': '../..' + '/signal-advance-comparison-receipt.json',
                                          'sha256': sha(comparison_path),
                                          'fixed_samples': 900,
                                          'software_checks_passed': True},
           'delivery_audit_draft': {
               'auditor_sha256': sha(assignment / 'signal_advance_delivery_audit.py'),
               'test_command': f'.venv-cpu/bin/python -m unittest discover -s work/{assignment.name}/tests -p test_signal_advance_delivery_audit.py -v',
               'test_log': 'signal-advance-delivery-tests.log',
               'test_log_sha256': sha(assignment / 'signal-advance-delivery-tests.log'),
               'full_audit_passed': True,
               'physical_acceptance_claimed': False},
           'remaining_cpu_work': [
               'integrate the exact case into the canonical plan, semantic proposal and execution manifest and rebind affected proofs']}
(folder / 'draft-proof-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
print(json.dumps({'case_id': case, 'offline_candidates': len(claims),
                  'signal_contrasts': len(summary['results']), 'status': 'partial draft'}))
