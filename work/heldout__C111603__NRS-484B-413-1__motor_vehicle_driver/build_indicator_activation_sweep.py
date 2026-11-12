"""Build three exact Native indicator activation-index probes."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
BASE_CASE = HERE.name + '__vehicle_no_indicator'
base_construction = json.loads((HERE / 'vehicle-no-indicator-construction.json').read_text())
base_diagnostic = json.loads((HERE / 'vehicle-no-indicator-diagnostic.json').read_text())
base_manifest = json.loads((HERE / 'vehicle-no-indicator-manifest.json').read_text())
plan_path = HERE / 'case-plan.json'
plan = json.loads(plan_path.read_text())
proposals_path = HERE / 'proposals/cases.json'
proposals = json.loads(proposals_path.read_text())

def sha(path):
    return sha256(path.read_bytes()).hexdigest()

def save(path, value, *, compact=False):
    path.write_text(json.dumps(value, separators=(',', ':') if compact else None,
                               indent=None if compact else 2, allow_nan=False) + '\n')

for activation in (2, 4, 6):
    suffix = f'indicator_activation_{activation}f'
    prefix = f'indicator-activation-{activation}f'
    case = HERE.name + '__' + suffix
    construction = deepcopy(base_construction)
    construction['case_id'] = case
    for item in construction['files']:
        if item['path'] == 'config.json':
            config = json.loads(item['content'])
            config['selected_case_id'] = case
            config['case']['case_id'] = case
            item['content'] = json.dumps(config, indent=2) + '\n'
        elif item['path'] in ('runner.py', 'turn_finalizer.py'):
            item['content'] = item['content'].replace(BASE_CASE, case)
            if item['path'] == 'runner.py':
                old = "        for index in range(config['frames']):\n"
                if item['content'].count(old) != 1:
                    raise ValueError('Native frame loop changed')
                item['content'] = item['content'].replace(old, old +
                    f"            if index == {activation}:\n"
                    "                ego.set_light_state(carla.VehicleLightState.LeftBlinker)\n")
    construction_path = HERE / f'{prefix}-construction.json'
    save(construction_path, construction)

    contract = json.loads((HERE / 'vehicle-no-indicator-measurement-contract.json').read_text())
    contract['case_id'] = case
    contract_path = HERE / f'{prefix}-measurement-contract.json'
    save(contract_path, contract)

    diagnostic = deepcopy(base_diagnostic)
    signal = [json.loads(line) for line in diagnostic['files']['ego_signal_audio.jsonl'].splitlines()]
    for index, row in enumerate(signal):
        row['indicator_readback'] = 'left' if index >= activation else 'off'
    diagnostic['files']['ego_signal_audio.jsonl'] = ''.join(json.dumps(row) + '\n' for row in signal)
    diagnostic['files']['turn_fixture_provenance.json'] = json.dumps({
        'diagnostic_fixture': True, 'source': 'C111603 synthetic indicator activation-index originals',
        'case_id': case, 'activation_frame_index': activation}) + '\n'
    diagnostic_path = HERE / f'{prefix}-diagnostic.json'
    save(diagnostic_path, diagnostic, compact=True)
    recipe_path = HERE / f'{prefix}-recipe.json'
    relative = str(diagnostic_path.relative_to(REPO))
    save(recipe_path, {'format': 'worker-fixture-recipe',
        'sources': [{'path': 'diagnostic-input.json', 'source': relative,
                     'sha256': sha(diagnostic_path)}],
        'generator': {'source': relative, 'sha256': sha(diagnostic_path)}})

    manifest = deepcopy(base_manifest)
    entry = manifest['cases'][0]
    for key in ('offline', 'compatibility', 'negative', 'delivery_acceptance',
                'saved_processing', 'post_capture', 'physical_preparation'):
        entry.pop(key, None)
    entry['case_id'] = case
    entry['construction'] = construction_path.name
    entry['construction_sha256'] = sha(construction_path)
    entry['measurement_contract'] = contract_path.name
    entry['fixture_recipe'] = str(recipe_path.relative_to(REPO))
    entry['candidate_risk']['reason'] = 'Native indicator activation index may not precede the measured turn onset or yield visible lamp pixels'
    entry['acquisition']['turn_signal_observation']['method'] = 'original 20 Hz Native turn with indicator readback after requested activation frame index'
    entry['candidates'] = []
    for number in (1, 2, 3):
        alternate = deepcopy(construction)
        cfg_item = next(item for item in alternate['files'] if item['path'] == 'config.json')
        cfg = json.loads(cfg_item['content'])
        if number == 1:
            cfg['engineering'].update(route_spacing_m=1.5, approach_steps=8)
            knobs = ['route sampling 2 m/6 steps to 1.5 m/8 steps']
            source, metric, condition = 'Native connected left-turn route inventory', 'eligible routes at 2 m sampling', 'Primary sampling finds no connected left turn'
        elif number == 2:
            cfg['engineering'].update(target_speed_mps=4., speed_gain=.2)
            knobs = ['target speed 5 to 4 m/s and gain .25 to .2']
            source, metric, condition = 'Original ego speed, yaw and indicator readback', 'approach speed settling and sampled turn onset', 'Primary speed destabilizes activation-index comparison timing'
        else:
            camera = next(item for item in alternate['files'] if item['path'] == 'turn_camera_capture.py')
            old = '"overview": ((-8, 0, 8), (-12, 0, 0), (1920, 1080), 95),'
            if camera['content'].count(old) != 1:
                raise ValueError('Primary overview mount changed')
            camera['content'] = camera['content'].replace(old,
                '"overview": ((-9, 0, 8), (-12, 0, 0), (1920, 1080), 95),')
            knobs = ['overview camera mount x -8 to -9 m']
            source, metric, condition = 'Original overview RGB decode', 'ego and affected vehicle visible pixel count', 'Primary overview crops participant or lamp context'
        cfg_item['content'] = json.dumps(cfg, indent=2) + '\n'
        path = HERE / f'{prefix}-fallback{number}-construction.json'
        save(path, alternate)
        entry['candidates'].append({'id': f'fallback{number}', 'construction': path.name,
            'construction_sha256': sha(path),
            'trigger': {'source': source, 'metric': metric, 'failure_condition': condition},
            'changed_knobs': knobs})
    save(HERE / f'{prefix}-manifest.json', manifest)

    if case not in plan['requirement_dispositions'][2]['case_ids']:
        plan['requirement_dispositions'][2]['case_ids'].append(case)
    if not any(item['case_id'] == case for item in plan['cases']):
        base = next(item for item in plan['cases'] if item['case_id'] == BASE_CASE)
        row = deepcopy(base)
        row['case_id'] = case
        row['description'] = f'Indicator requested at Native capture frame index {activation}; original preturn readback and appropriateness remain unresolved'
        plan['cases'].append(row)
    if not any(item['case_id'] == case for item in proposals['cases']):
        proposals['cases'].append({'case_id': case, 'target_law_id': 'NRS-484B-413-1',
            'target_type': 'boundary_probe',
            'rationale': f'Exact Native indicator activation index {activation} with original readback; physical timing and appropriate-signal judgment remain open.',
            'variable_assignments': {
                'indicator_activation_frame_index': {'kind': 'controller', 'value': activation},
                'turn_indicator_state': {'kind': 'controller', 'value': 'left'},
                'vehicle_may_be_affected': {'kind': 'world_setup', 'value': True},
                'pedestrian_may_be_affected': {'kind': 'world_setup', 'value': False}},
            'unresolved_judgment_calls': [],
            'recording_description': config['case']['recording_description']})
save(plan_path, plan)
save(proposals_path, proposals)
print('Three exact indicator activation-index primaries and nine fallbacks authored')
