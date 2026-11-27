"""CPU checks for the exact controlled-fog 1000-foot beam pair."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
sys.path.insert(0, str(ROOT / 'native'))
from visibility_scene import MODES, request, validate_request  # noqa: E402


def rejects(plan):
    try:
        validate_request(plan)
    except ValueError:
        return
    raise AssertionError('Invalid visibility request accepted')


for case in MODES:
    plan = request(case)
    outcome = validate_request(plan)
    assert outcome['target_ft'] == 1000 and not outcome['physical_verified']
    assert plan['lighting']['fog_density_request'] == 80
    changed = deepcopy(plan)
    changed['oncoming']['start_xyz_m'][0] += .3048
    rejects(changed)
    changed = deepcopy(plan)
    changed['lighting']['fog_density_request'] = 0
    rejects(changed)
    changed = deepcopy(plan)
    changed['visibility_target']['discernibility_claimed'] = True
    rejects(changed)
    for candidate in ('primary', 'fallback1'):
        source = ROOT / 'constructions' / case / candidate / 'construction.json'
        construction = json.loads(source.read_text())
        destination = REPO / '.runtime-work' / 'c183394' / ('visibility-check-' + case + '-' + candidate)
        if destination.exists():
            import shutil
            shutil.rmtree(destination)
        destination.mkdir(parents=True)
        for item in construction['files']:
            target = destination / item['path']
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(item['content'])
        commands = ([str(REPO / '.venv-cpu/bin/python'), 'runner.py', '--check'],
                    [str(REPO / '.venv-cpu/bin/python'), '-m', 'unittest', 'discover', '-s', 'tests'])
        for command in commands:
            result = subprocess.run(command, cwd=destination, text=True, capture_output=True)
            if result.returncode:
                raise RuntimeError(f'{case} {candidate}: {result.stdout}\n{result.stderr}')
        print('PASS', case, candidate, outcome)
print('Synthetic request and materialized runner checks only; original range and pixels unreviewed')
