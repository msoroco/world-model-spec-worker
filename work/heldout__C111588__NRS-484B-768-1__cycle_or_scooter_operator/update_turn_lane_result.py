"""Record truthful C111588 turn-lane CPU checkpoint in the return report."""
from hashlib import sha256
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FOLDER = ROOT / 'cases/turn_lane_no_signal'
CASE = 'heldout__C111588__NRS-484B-768-1__cycle_or_scooter_operator__turn_lane_no_signal'
MANIFEST = 'work/heldout__C111588__NRS-484B-768-1__cycle_or_scooter_operator/turn-lane-manifest.json'
RESULT = ROOT / 'result.json'
result = json.loads(RESULT.read_text())
result['status'] = 'partial'
result['applied_update'] = 0
result['reason'] = ('Partial: six exact CPU diagnostic cases now include the no-signal turn-lane primary and three '
    'tested fallbacks. Its offline, positive/missing-lane-original compatibility, saved processing, independent '
    'source/video audit and synthetic physical-preparation fixtures pass. The black diagnostic video leaves '
    'turn-lane designation and legal exception unverified. Electric bicycle, electric scooter and both-hands '
    'cases remain unconstructed; actual rider/arm visibility, participant conflict time, physical completion, '
    'judgment sweeps and delivery acceptance remain open.')
result['tests'] = [test for test in result['tests']
                   if 'turn-lane-manifest.json' not in test.get('command', '')]


def sha(path):
    return sha256(path.read_bytes()).hexdigest()


def add(command, relative):
    path = ROOT / relative
    result['tests'].append({'command': command, 'exit_code': 0,
                            'log': relative, 'sha256': sha(path)})


python = '/scratch/fsw/portfolios/av/projects/av_alpamayo_reasoning/users/wcong/scenario-worker-held/.venv-cpu/bin/python'
add(f'.venv-cpu/bin/python runtime.py offline --manifest {MANIFEST} --case {CASE} '
    f'--output .runtime-work/c111588-turn-lane-primary-offline-b --python {python}',
    'cases/turn_lane_no_signal/proof-offline-log.log')
add(f'.venv-cpu/bin/python runtime.py compatibility --manifest {MANIFEST} --case {CASE} '
    '--output .runtime-work/c111588-turn-lane-primary-compat-b --library runtime/library '
    '--validator .runtime-work/fire-decoder/.lake/build/bin/adapterCheck',
    'cases/turn_lane_no_signal/proof-compatibility-receipt.json')
add(f'.venv-cpu/bin/python runtime.py process-saved --manifest {MANIFEST} --case {CASE} '
    '--attempt .runtime-work/c111588-turn-lane-original-b --output .runtime-work/c111588-turn-lane-saved-b '
    '--library runtime/library --validator .runtime-work/fire-decoder/.lake/build/bin/adapterCheck',
    'cases/turn_lane_no_signal/proof-saved-receipt.json')
add('.venv-cpu/bin/python work/heldout__C111588__NRS-484B-768-1__cycle_or_scooter_operator/'
    'turn_lane_comparison_check.py', 'cases/turn_lane_no_signal/comparison-check.log')
RESULT.write_text(json.dumps(result, indent=2) + '\n')
