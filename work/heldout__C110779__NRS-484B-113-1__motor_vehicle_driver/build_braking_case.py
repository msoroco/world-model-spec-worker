"""Build the controlled other-vehicle braking probe from the backed corridor.

The diagnostic sources are synthetic; the Native runner must still measure the
other vehicle's actual response. This builder does not assign a legal cutoff.
"""

from hashlib import sha256
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORK = Path(__file__).resolve().parent
STAGE = ROOT / '.runtime-work/c110779-native-stage'
PREFIX = WORK.name + '__'
CLEAR = PREFIX + 'backing_clear_vehicle'
BRAKES = PREFIX + 'backing_vehicle_brakes'


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')
    return sha256(path.read_bytes()).hexdigest()


def main():
    primary = json.loads((STAGE / 'diagnostic-first-primary.json').read_text())
    files = primary['files']
    capture = json.loads(files['capture/manifest.json'])
    capture['case_id'] = BRAKES
    files['capture/manifest.json'] = json.dumps(capture, indent=2) + '\n'
    motions = [json.loads(line) for line in files['backing_motion.jsonl'].splitlines() if line]
    # Preserve the initial other-vehicle position, ego motion and all other
    # source fields. Decrease only its subsequent sampled speed and travel.
    x = motions[0]['participants']['20']['x_m']
    for index, row in enumerate(motions):
        other = row['participants']['20']
        if index:
            x += .2 if index < 4 else .05
        other['x_m'] = x
        other['speed_mps'] = 1.0 if index < 4 else .25
    files['backing_motion.jsonl'] = ''.join(json.dumps(row) + '\n' for row in motions)
    diagnostic = STAGE / 'diagnostic-braking-vehicle.json'
    diagnostic_sha = write(diagnostic, primary)
    recipe = {
        'format': 'worker-fixture-recipe',
        'sources': [{'path': 'diagnostic-input.json',
                     'source': str(diagnostic.relative_to(ROOT)), 'sha256': diagnostic_sha}],
        'generator': {'source': str(diagnostic.relative_to(ROOT)), 'sha256': diagnostic_sha},
    }
    recipe_path = STAGE / 'diagnostic-recipe-braking-vehicle.json'
    write(recipe_path, recipe)

    base = json.loads((STAGE / 'construction-first-primary.json').read_text())
    construction = json.loads(json.dumps(base))
    construction['case_id'] = BRAKES
    construction['mechanisms'].append(
        'Other vehicle is commanded to brake after the fourth original 20 Hz frame; '
        'actual deceleration remains an original-source measurement')
    for file in construction['files']:
        if file['path'] == 'config.json':
            config = json.loads(file['content'])
            config['selected_case_id'] = BRAKES
            config['supported_case_ids'] = [BRAKES]
            config['case']['case_id'] = BRAKES
            config['other_brake_after_frame'] = 4
            file['content'] = json.dumps(config, indent=2) + '\n'
        elif file['path'] == 'runner.py':
            runner = file['content'].replace(
                "SUFFIXES={'backing_clear_vehicle','backing_near_vehicle'}",
                "SUFFIXES={'backing_clear_vehicle','backing_near_vehicle','backing_vehicle_brakes'}")
            runner = runner.replace(
                "if config.get('other_throttle',.15) not in (.15,.25):",
                "if config.get('other_brake_after_frame') not in (None,4):\n"
                "        raise ValueError('Unsupported other-vehicle brake onset')\n"
                "    if config.get('other_throttle',.15) not in (.15,.25):")
            runner = runner.replace(
                "for _ in range(config['frames']):",
                "for frame_index in range(config['frames']):")
            runner = runner.replace(
                "other.apply_control(carla.VehicleControl(throttle=config.get('other_throttle',.15),steer=0))",
                "braking = config.get('other_brake_after_frame') is not None and frame_index >= config['other_brake_after_frame']\n"
                "            other.apply_control(carla.VehicleControl(throttle=0 if braking else config.get('other_throttle',.15),\n"
                "                                                   brake=.5 if braking else 0,steer=0))")
            if runner == file['content'] or 'brake=.5 if braking else 0' not in runner:
                raise ValueError('Native braking runner patch did not apply')
            file['content'] = runner
    construction_path = STAGE / 'construction-braking-primary.json'
    construction_sha = write(construction_path, construction)
    contract = json.loads((STAGE / 'measurement-first-primary.json').read_text())
    contract['case_id'] = BRAKES
    contract_path = STAGE / 'measurement-braking-primary.json'
    write(contract_path, contract)
    manifest = json.loads((STAGE / 'execution-manifest.json').read_text())
    manifest['cases'] = [case for case in manifest['cases'] if case['case_id'] != BRAKES]
    manifest['cases'].append({
        'case_id': BRAKES, 'kind': 'delivery',
        'construction': construction_path.name, 'construction_sha256': construction_sha,
        'measurement_contract': contract_path.name,
        'measurement_procedure': {'entrypoint': 'backing_finalizer.py'},
        'fixture_recipe': str(recipe_path.relative_to(ROOT)),
        'native_handoff': {'python_env_var': 'CARLA_PYTHON',
                           'host_env_var': 'CARLA_HOST', 'port_env_var': 'CARLA_PORT'},
        'candidate_risk': {'status': 'physical', 'reason':
                           'Native through-vehicle braking onset may not produce an observable deceleration.'},
        'candidates': [],
    })
    write(STAGE / 'execution-manifest.json', manifest)
    return {'case_id': BRAKES, 'construction_sha256': construction_sha,
            'diagnostic_sha256': diagnostic_sha}


if __name__ == '__main__':
    print(json.dumps(main(), indent=2))
