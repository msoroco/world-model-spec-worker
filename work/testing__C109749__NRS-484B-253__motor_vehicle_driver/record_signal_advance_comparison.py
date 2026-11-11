"""Bind fixed-condition signal-advance diagnostic comparison and negatives."""
import hashlib
import json
from pathlib import Path

folder = Path(__file__).resolve().parent
repo = folder.parent.parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


comparison = json.loads((folder / 'signal-advance-comparison-diagnostic.json').read_text())
signed = folder.name + '__signal_advance_100_at'
omitted = folder.name + '__signal_advance_100_omitted'
if (comparison.get('signalled_case_id') != signed or comparison.get('omitted_case_id') != omitted or
        comparison.get('fixed_samples') != 900 or comparison.get('software_checks_passed') is not True or
        comparison.get('delivery_passed') is not False or
        comparison.get('physical_acceptance_claimed') is not False or
        not 30.48 <= comparison.get('observed_continuous_approach_distance_m', 0) < 30.480001):
    raise ValueError('Matched source comparison incomplete')
roots = {signed: repo / '.runtime-work/c109749-signal-advance-delivery-v1/attempt',
         omitted: repo / '.runtime-work/c109749-signal-advance-omitted-delivery-v1/attempt'}
for case, root in roots.items():
    audit = json.loads((root / 'diagnostic-audit.json').read_text())
    if audit.get('case_id') != case or audit.get('software_checks_passed') is not True:
        raise ValueError('Source delivery audit changed: ' + case)
if comparison['signalled_source_sha256'] != sha(roots[signed] / 'interaction_history.jsonl'):
    raise ValueError('Signalled source changed')
if comparison['omitted_source_sha256'] != sha(roots[omitted] / 'interaction_history.jsonl'):
    raise ValueError('Omitted source changed')
negative = (folder / 'signal-advance-comparison-negative.log').read_text()
if 'Ran 6 tests' not in negative or 'OK' not in negative:
    raise ValueError('Fixed-condition rejection tests missing')
receipt = {'format': 'worker-signal-advance-comparison-diagnostic-proof',
           'signalled_case_id': signed, 'omitted_case_id': omitted,
           'software_checks_passed': True, 'delivery_passed': False,
           'physical_acceptance_claimed': False,
           'fixed_samples': 900,
           'command': f'.venv-cpu/bin/python work/{folder.name}/signal_advance_comparison_audit.py '
                      '--signalled .runtime-work/c109749-signal-advance-delivery-v1/attempt '
                      '--omitted .runtime-work/c109749-signal-advance-omitted-delivery-v1/attempt '
                      f'--output work/{folder.name}/signal-advance-comparison-diagnostic.json',
           'log': 'signal-advance-comparison-positive.log',
           'log_sha256': sha(folder / 'signal-advance-comparison-positive.log'),
           'audit_sha256': sha(folder / 'signal_advance_comparison_audit.py'),
           'diagnostic_sha256': sha(folder / 'signal-advance-comparison-diagnostic.json'),
           'negative_test_command': f'.venv-cpu/bin/python -m unittest discover -s work/{folder.name}/tests '
                                    '-p test_signal_advance_comparison.py -v',
           'negative_log': 'signal-advance-comparison-negative.log',
           'negative_log_sha256': sha(folder / 'signal-advance-comparison-negative.log'),
           'signalled_delivery_sha256': sha(roots[signed] / 'diagnostic-audit.json'),
           'omitted_delivery_sha256': sha(roots[omitted] / 'diagnostic-audit.json')}
(folder / 'signal-advance-comparison-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
print(json.dumps({'fixed_samples': 900, 'software_checks_passed': True,
                  'physical_acceptance_claimed': False}))
