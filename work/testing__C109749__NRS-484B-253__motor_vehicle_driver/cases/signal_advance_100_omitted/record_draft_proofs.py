"""Bind matched omitted-signal construction, processing and delivery proofs."""
import hashlib
import json
from pathlib import Path

folder = Path(__file__).resolve().parent
assignment = folder.parents[1]
case = assignment.name + '__signal_advance_100_omitted'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


manifest = json.loads((folder / 'draft-manifest.json').read_text())['cases'][0]
exact = json.loads((folder / 'exact-proof-receipt.json').read_text())
delivery = json.loads((folder / 'delivery-proof-receipt.json').read_text())
comparison_path = assignment / 'signal-advance-comparison-receipt.json'
comparison = json.loads(comparison_path.read_text())
if (manifest['case_id'] != case or exact.get('case_id') != case or
        delivery.get('case_id') != case or delivery.get('frames') != 900 or
        comparison.get('omitted_case_id') != case or
        exact.get('diagnostic_sha256') != sha(folder / 'diagnostic.json') or
        exact.get('fixture_recipe_sha256') != sha(folder / 'diagnostic-recipe.json') or
        exact.get('measurement_contract_sha256') != sha(folder / 'measurement-contract.json') or
        delivery.get('diagnostic_source_sha256') != sha(folder / 'diagnostic.json') or
        len(exact.get('proofs', [])) != 4):
    raise ValueError('Current omitted-signal draft proof binding incomplete')
offline = []
for label, entry in [('primary', manifest),
                     *[(candidate['id'], candidate) for candidate in manifest['candidates']]]:
    if sha(folder / entry['construction']) != entry['construction_sha256']:
        raise ValueError('Candidate construction changed: ' + label)
    log = folder / (label + '-offline.log')
    output = json.loads(log.read_text())
    if (output.get('case_id') != case or output.get('candidate_id') != label or
            output.get('offline_passed') is not True or output.get('simulation_started') is not False):
        raise ValueError('Exact offline proof missing: ' + label)
    offline.append({'candidate_id': label, 'construction_sha256': entry['construction_sha256'],
                    'log': log.name, 'log_sha256': sha(log),
                    'command': f'.venv-cpu/bin/python runtime.py offline --manifest '
                               f'work/{assignment.name}/cases/{folder.name}/draft-manifest.json '
                               f'--case {case} --output '
                               f'.runtime-work/c109749-signal-advance-omitted-{label}-offline-v1' +
                               ('' if label == 'primary' else ' --candidate ' + label)})
if not all(item['compatibility']['passed'] and item['saved']['passed'] for item in exact['proofs']):
    raise ValueError('Exact positive/negative and saved proofs incomplete')
if delivery['software_checks_passed'] is not True or delivery['passed'] is not False:
    raise ValueError('Diagnostic delivery proof missing')
receipt = {'format': 'worker-signal-advance-omitted-construction-draft',
           'case_id': case, 'canonical_selected': False,
           'physical_acceptance_claimed': False,
           'offline': offline,
           'runner_check_sha256': sha(folder / 'runner-check.log'),
           'exact_proof_receipt_sha256': sha(folder / 'exact-proof-receipt.json'),
           'delivery_proof_receipt_sha256': sha(folder / 'delivery-proof-receipt.json'),
           'comparison_receipt_sha256': sha(comparison_path),
           'remaining_cpu_work': [
               'integrate both matched signal-advance cases into canonical plan, semantic proposal and manifest',
               'rebind every affected exact primary, fallback, physical, delivery and comparison proof',
               'complete other uncovered statutory alternatives and assignment packages']}
(folder / 'draft-proof-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
print(json.dumps({'case_id': case, 'offline_candidates': 4,
                  'compatibility_saved_candidates': 4,
                  'delivery_software_check': True,
                  'fixed_condition_comparison': True,
                  'status': 'partial draft'}))
