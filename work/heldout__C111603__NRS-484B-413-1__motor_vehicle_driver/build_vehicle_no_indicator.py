"""Build the controlled no-indicator sibling of the exact left-turn case."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
OLD = ROOT.name + '__vehicle_left_indicator'
CASE = ROOT.name + '__vehicle_no_indicator'
PREFIX = 'vehicle-no-indicator'


def save(path, value, compact=False):
    path.write_text(json.dumps(value, separators=(',', ':') if compact else None,
                               indent=None if compact else 2, allow_nan=False) + '\n')


def sha(path):
    return sha256(path.read_bytes()).hexdigest()


construction = deepcopy(json.loads((ROOT / 'vehicle-indicator-construction.json').read_text()))
construction['case_id'] = CASE
for item in construction['files']:
    if item['path'] == 'config.json':
        config = json.loads(item['content'])
        config['selected_case_id'] = CASE
        config['case']['case_id'] = CASE
        item['content'] = json.dumps(config, indent=2) + '\n'
    elif item['path'] in ('runner.py', 'turn_finalizer.py'):
        item['content'] = item['content'].replace(OLD, CASE)
        if item['path'] == 'runner.py':
            old = 'ego.set_light_state(carla.VehicleLightState.LeftBlinker)'
            if item['content'].count(old) != 1:
                raise ValueError('Primary Native indicator control changed')
            item['content'] = item['content'].replace(old, 'ego.set_light_state(carla.VehicleLightState(0))')
        else:
            item['content'] = item['content'].replace('left turn after indicator readback',
                                                     'left turn without indicator readback')
construction_path = ROOT / f'{PREFIX}-construction.json'
save(construction_path, construction)

contract = json.loads((ROOT / 'vehicle-indicator-measurement-contract.json').read_text())
contract['case_id'] = CASE
contract['requirements'][0]['disposition_index'] = 2
contract['requirements'][0]['requirement'] = 'Other vehicle possibly affected: no indicator and hand-signal alternatives'
contract_path = ROOT / f'{PREFIX}-measurement-contract.json'
save(contract_path, contract)

diagnostic = json.loads((ROOT / 'vehicle-indicator-diagnostic.json').read_text())
rows = [json.loads(line) for line in diagnostic['files']['ego_signal_audio.jsonl'].splitlines()]
for row in rows:
    row['indicator_readback'] = 'off'
diagnostic['files']['ego_signal_audio.jsonl'] = ''.join(json.dumps(row) + '\n' for row in rows)
diagnostic['files']['turn_fixture_provenance.json'] = json.dumps({
    'diagnostic_fixture': True, 'source': 'C111603 synthetic vehicle no-indicator turn originals',
    'case_id': CASE}) + '\n'
diagnostic_path = ROOT / f'{PREFIX}-diagnostic.json'
save(diagnostic_path, diagnostic, compact=True)
recipe = {'format': 'worker-fixture-recipe', 'sources': [{
    'path': 'diagnostic-input.json', 'source': str(diagnostic_path.relative_to(REPO)),
    'sha256': sha(diagnostic_path)}], 'generator': {
        'source': str(diagnostic_path.relative_to(REPO)), 'sha256': sha(diagnostic_path)}}
recipe_path = ROOT / f'{PREFIX}-recipe.json'
save(recipe_path, recipe)

manifest = deepcopy(json.loads((ROOT / 'vehicle-indicator-manifest.json').read_text()))
entry = manifest['cases'][0]
for key in ('offline', 'compatibility', 'negative', 'delivery_acceptance', 'candidates'):
    entry.pop(key, None)
entry['case_id'] = CASE
entry['construction'] = construction_path.name
entry['construction_sha256'] = sha(construction_path)
entry['measurement_contract'] = contract_path.name
entry['fixture_recipe'] = str(recipe_path.relative_to(REPO))
entry['candidate_risk']['reason'] = 'Native connected turn and the absence of indicator lamp pixels need physical source review'
entry['acquisition']['turn_signal_observation']['method'] = 'original 20 Hz Native turn, off indicator readback, participant and no-pedestrian-audio status'

definitions = (
    ('fallback1', 'Native connected left-turn route inventory',
     'eligible left-turn routes at 2 m sampling',
     'Primary route sampling finds no connected left turn',
     ['route sampling 2 m/6 steps to 1.5 m/8 steps']),
    ('fallback2', 'Original ego speed, yaw and off-indicator readback',
     'approach speed settling and turn onset frames',
     'Primary 5 m/s approach destabilizes the signal comparison timing',
     ['target speed 5 to 4 m/s and gain .25 to .2']),
    ('fallback3', 'Original overview RGB decode',
     'ego and affected vehicle visible pixel count',
     'Primary overview mount crops participant visibility',
     ['overview camera mount x -8 to -9 m']),
)
entry['candidates'] = []
for name, source, metric, condition, knobs in definitions:
    alternate = deepcopy(construction)
    cfg_item = next(item for item in alternate['files'] if item['path'] == 'config.json')
    cfg = json.loads(cfg_item['content'])
    if name == 'fallback1':
        cfg['engineering'].update(route_spacing_m=1.5, approach_steps=8)
    elif name == 'fallback2':
        cfg['engineering'].update(target_speed_mps=4., speed_gain=.2)
    else:
        camera = next(item for item in alternate['files'] if item['path'] == 'turn_camera_capture.py')
        old = '"overview": ((-8, 0, 8), (-12, 0, 0), (1920, 1080), 95),'
        if camera['content'].count(old) != 1:
            raise ValueError('Primary overview camera source changed')
        camera['content'] = camera['content'].replace(old,
            '"overview": ((-9, 0, 8), (-12, 0, 0), (1920, 1080), 95),')
    cfg_item['content'] = json.dumps(cfg, indent=2) + '\n'
    path = ROOT / f'{PREFIX}-{name}-construction.json'
    save(path, alternate)
    entry['candidates'].append({'id': name, 'construction': path.name,
        'construction_sha256': sha(path), 'trigger': {'source': source, 'metric': metric,
        'failure_condition': condition}, 'changed_knobs': knobs})
save(ROOT / f'{PREFIX}-manifest.json', manifest)
proposals_path = ROOT / 'proposals/cases.json'
proposals = json.loads(proposals_path.read_text())
if not any(item['case_id'] == CASE for item in proposals['cases']):
    proposals['cases'].append({'case_id': CASE, 'target_law_id': 'NRS-484B-413-1',
        'target_type': 'boundary_probe',
        'rationale': 'Controlled left turn with another vehicle possibly affected and original indicator readback off; physical and legal findings remain open.',
        'variable_assignments': {
            'turn_indicator_state': {'kind': 'controller', 'value': 'off'},
            'vehicle_may_be_affected': {'kind': 'world_setup', 'value': True},
            'pedestrian_may_be_affected': {'kind': 'world_setup', 'value': False}},
        'unresolved_judgment_calls': [],
        'recording_description': config['case']['recording_description']})
    save(proposals_path, proposals)
print('Exact no-indicator primary, three fallbacks and source-complete diagnostic authored')
