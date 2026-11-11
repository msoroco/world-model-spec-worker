"""Bind current full-duration software audit and sealed-source rejection."""
import hashlib
import json
import shutil
from pathlib import Path

folder = Path(__file__).resolve().parent
assignment = folder.parents[1]
repo = assignment.parent.parent
source = repo / '.runtime-work/c109749-signal-advance-omitted-delivery-v1/attempt/diagnostic-audit.json'
negative = folder / 'delivery-negative.log'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


audit = json.loads(source.read_text())
case = assignment.name + '__signal_advance_100_omitted'
if (audit.get('case_id') != case or audit.get('frames') != 900 or
        audit.get('passed') is not False or audit.get('software_checks_passed') is not True or
        audit.get('diagnostic_fixture') is not True or
        audit.get('physical_acceptance_claimed') is not False or
        audit.get('signal_sequence', {}).get('branch') != 'omitted' or
        audit['signal_sequence'].get('ego_left_indicator_frames') != []):
    raise ValueError('Full-duration diagnostic audit incomplete')
if 'Sealed original source changed: interaction_history.jsonl' not in negative.read_text():
    raise ValueError('Missing-source audit rejection not retained')
target = folder / 'delivery-diagnostic.json'
shutil.copyfile(source, target)
receipt = {'format': 'worker-signal-advance-delivery-diagnostic-proof',
           'case_id': case, 'diagnostic_fixture': True,
           'software_checks_passed': True, 'passed': False,
           'physical_acceptance_claimed': False,
           'frames': 900,
           'diagnostic_source_sha256': sha(folder / 'diagnostic.json'),
           'fixture_generator_sha256': sha(assignment / 'signal_advance_omitted_delivery_fixture_proof.py'),
           'auditor_sha256': sha(assignment / 'signal_advance_omitted_delivery_audit.py'),
           'positive': {'command': f'.venv-cpu/bin/python work/{assignment.name}/signal_advance_omitted_delivery_fixture_proof.py '
                                   f'--case {case} --output-root .runtime-work/c109749-signal-advance-omitted-delivery-v1',
                        'log': 'delivery-positive.log', 'log_sha256': sha(folder / 'delivery-positive.log'),
                        'audit': 'delivery-diagnostic.json', 'audit_sha256': sha(target)},
           'negative': {'command': f'.venv-cpu/bin/python work/{assignment.name}/signal_advance_omitted_delivery_fixture_proof.py '
                                   f'--case {case} --output-root .runtime-work/c109749-signal-advance-omitted-delivery-negative-v1 '
                                   '--negative-source-root .runtime-work/c109749-signal-advance-omitted-delivery-v1',
                        'expected_exit_code': 1,
                        'log': 'delivery-negative.log', 'log_sha256': sha(negative),
                        'rejected_source': 'interaction_history.jsonl'}}
(folder / 'delivery-proof-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
print(json.dumps({'case_id': case, 'frames': 900,
                  'software_checks_passed': True, 'physical_acceptance_claimed': False}))
