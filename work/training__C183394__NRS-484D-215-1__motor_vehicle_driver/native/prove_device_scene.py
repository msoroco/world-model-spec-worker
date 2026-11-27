"""CPU smoke checks for authored same-road device and oncoming pair."""
from copy import deepcopy
import json
from pathlib import Path
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
sys.path.insert(0, str(ROOT / 'native'))
from device_scene import MODES, request, validate_request  # noqa: E402


def rejects(plan):
    try:
        validate_request(plan)
    except ValueError:
        return
    raise AssertionError('Invalid authored device request accepted')


for case in MODES:
    plan = request(case)
    outcome = validate_request(plan)
    assert outcome['signal_id'] == '100' and not outcome['official_status_verified']
    changed = deepcopy(plan)
    changed['device_request']['official_authority_verified'] = True
    rejects(changed)
    changed = deepcopy(plan)
    changed['device_request']['ego_applicability_verified'] = True
    rejects(changed)
    changed = deepcopy(plan)
    changed['road_opendrive'] = changed['road_opendrive'].replace('lamp_use_instruction', 'other_instruction')
    rejects(changed)
    for candidate in ('primary', 'fallback1'):
        construction = json.loads((ROOT / 'constructions' / case / candidate / 'construction.json').read_text())
        destination = REPO / '.runtime-work' / 'c183394' / ('device-smoke-' + case + '-' + candidate)
        if destination.exists():
            shutil.rmtree(destination)
        destination.mkdir(parents=True)
        for item in construction['files']:
            target = destination / item['path']
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(item['content'])
        for command in ([str(REPO / '.venv-cpu/bin/python'), 'runner.py', '--check'],
                        [str(REPO / '.venv-cpu/bin/python'), '-m', 'unittest', 'discover', '-s', 'tests']):
            result = subprocess.run(command, cwd=destination, capture_output=True, text=True)
            if result.returncode:
                raise RuntimeError(f'{case} {candidate}: {result.stdout}\n{result.stderr}')
        print('PASS', case, candidate, outcome)
print('Authored signal readback requested; official status and original CARLA visibility unverified')
