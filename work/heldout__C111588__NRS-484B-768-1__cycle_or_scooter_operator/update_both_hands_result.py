"""Record truthful C111588 both-hands CPU checkpoint in the return report."""
from hashlib import sha256
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FOLDER = ROOT / 'cases/both_hands_no_signal'
CASE = 'heldout__C111588__NRS-484B-768-1__cycle_or_scooter_operator__both_hands_no_signal'
MANIFEST = 'work/heldout__C111588__NRS-484B-768-1__cycle_or_scooter_operator/both-hands-manifest.json'
RESULT = ROOT / 'result.json'
result = json.loads(RESULT.read_text())
result['status'] = 'partial'
result['applied_update'] = 0
result['reason'] = ('Partial: seven exact CPU diagnostic cases now include the both-hands no-signal primary and '
    'three tested fallbacks. Its offline, positive/missing-hand-original compatibility, saved processing, '
    'independent source/video audit and synthetic physical-preparation fixtures pass. Black diagnostic video '
    'leaves physical hand contact, both-hands safety necessity and the legal exception unverified. Electric '
    'bicycle and electric scooter cases remain unconstructed; actual rider/arm visibility, participant conflict '
    'time, physical completion, judgment sweeps and delivery acceptance remain open.')
result['tests'] = [test for test in result['tests']
                   if 'both-hands-manifest.json' not in test.get('command', '')]


def sha(path):
    return sha256(path.read_bytes()).hexdigest()


def add(command, relative):
    path = ROOT / relative
    result['tests'].append({'command': command, 'exit_code': 0,
                            'log': relative, 'sha256': sha(path)})


python = '/scratch/fsw/portfolios/av/projects/av_alpamayo_reasoning/users/wcong/scenario-worker-held/.venv-cpu/bin/python'
add(f'.venv-cpu/bin/python runtime.py offline --manifest {MANIFEST} --case {CASE} '
    f'--output .runtime-work/c111588-both-hands-primary-offline-b --python {python}',
    'cases/both_hands_no_signal/proof-offline-log.log')
add(f'.venv-cpu/bin/python runtime.py compatibility --manifest {MANIFEST} --case {CASE} '
    '--output .runtime-work/c111588-both-hands-primary-compat-b --library runtime/library '
    '--validator .runtime-work/fire-decoder/.lake/build/bin/adapterCheck',
    'cases/both_hands_no_signal/proof-compatibility-receipt.json')
add(f'.venv-cpu/bin/python runtime.py process-saved --manifest {MANIFEST} --case {CASE} '
    '--attempt .runtime-work/c111588-both-hands-original-b --output .runtime-work/c111588-both-hands-saved-b '
    '--library runtime/library --validator .runtime-work/fire-decoder/.lake/build/bin/adapterCheck',
    'cases/both_hands_no_signal/proof-saved-receipt.json')
add('.venv-cpu/bin/python work/heldout__C111588__NRS-484B-768-1__cycle_or_scooter_operator/'
    'both_hands_comparison_check.py', 'cases/both_hands_no_signal/comparison-check.log')
RESULT.write_text(json.dumps(result, indent=2) + '\n')
