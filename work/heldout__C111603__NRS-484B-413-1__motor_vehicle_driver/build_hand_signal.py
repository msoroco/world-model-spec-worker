"""Build exact affected-vehicle hand-signal alternative from original bone readback."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
CASE = ROOT.name + '__vehicle_hand_signal'
PREFIX = 'hand-signal'


def save(path, value, compact=False):
    path.write_text(json.dumps(value, separators=(',', ':') if compact else None,
                               indent=None if compact else 2, allow_nan=False) + '\n')


def sha(path):
    return sha256(path.read_bytes()).hexdigest()


construction = deepcopy(json.loads((ROOT / 'vehicle-no-indicator-construction.json').read_text()))
construction['case_id'] = CASE
for item in construction['files']:
    if item['path'] == 'config.json':
        cfg = json.loads(item['content'])
        cfg['selected_case_id'] = cfg['case']['case_id'] = CASE
        cfg['case']['recording_description']['channels'].append({
            'name': 'hand_signal_observation', 'unit': 'structured', 'sampling_rate_hz': 20,
            'method': 'original Native attached driver-avatar left-arm bone world readback',
            'time_window': 'all 8 s original frames', 'reference_frame': 'Native world',
            'uncertainty': 'bone readback does not establish visible pixels or legal signal appropriateness'})
        cfg['case']['recording_description']['limitations'].append(
            'Attached avatar pose, hand pixels and signal recognizability require physical review.')
        item['content'] = json.dumps(cfg, indent=2) + '\n'
    elif item['path'] == 'runner.py':
        item['content'] = (ROOT / 'runner_hand_signal.py').read_text()
    elif item['path'] == 'turn_finalizer.py':
        item['content'] = (ROOT / 'hand_signal_finalizer.py').read_text()
construction['files'].append({'path': 'turn_hand_signal.py',
                              'content': (ROOT / 'turn_hand_signal.py').read_text()})
construction_path = ROOT / f'{PREFIX}-construction.json'
save(construction_path, construction)

contract = json.loads((ROOT / 'vehicle-no-indicator-measurement-contract.json').read_text())
contract['case_id'] = CASE
contract['requirements'][0]['inputs'].append('hand_signal_original.jsonl')
contract['negative'] = {'remove': ['hand_signal_original.jsonl'],
                        'error_contains': 'Missing required source: hand_signal_original.jsonl'}
contract_path = ROOT / f'{PREFIX}-measurement-contract.json'
save(contract_path, contract)

diagnostic = json.loads((ROOT / 'vehicle-no-indicator-diagnostic.json').read_text())
motion = [json.loads(s) for s in diagnostic['files']['ego_turn_motion.jsonl'].splitlines()]
hand_rows = []
for row in motion:
    x, y = row['x_m'], row['y_m']
    hand_rows.append({'frame': row['frame'], 'time_s': row['time_s'],
                      'avatar_actor_id': 811, 'origin': 'native_walker_bone_world_readback',
                      'bones_world_m': {'crl_arm__L': [x, y-1.0, 1.2],
                                        'crl_foreArm__L': [x-.3, y-1.3, 1.2],
                                        'crl_hand__L': [x-.7, y-1.5, 1.2]}})
diagnostic['files']['hand_signal_original.jsonl'] = ''.join(json.dumps(row) + '\n' for row in hand_rows)
diagnostic['files']['turn_fixture_provenance.json'] = json.dumps({
    'diagnostic_fixture': True, 'source': 'C111603 synthetic hand-bone Native-shaped originals',
    'case_id': CASE}) + '\n'
diagnostic_path = ROOT / f'{PREFIX}-diagnostic.json'
save(diagnostic_path, diagnostic, compact=True)
recipe_path = ROOT / f'{PREFIX}-recipe.json'
save(recipe_path, {'format': 'worker-fixture-recipe', 'sources': [{
    'path': 'diagnostic-input.json', 'source': str(diagnostic_path.relative_to(REPO)),
    'sha256': sha(diagnostic_path)}], 'generator': {
    'source': str(diagnostic_path.relative_to(REPO)), 'sha256': sha(diagnostic_path)}})

manifest = deepcopy(json.loads((ROOT / 'vehicle-no-indicator-manifest.json').read_text()))
entry = manifest['cases'][0]
for key in ('offline', 'compatibility', 'negative', 'delivery_acceptance',
            'saved_processing', 'candidates'):
    entry.pop(key, None)
entry['case_id'] = CASE
entry['construction'] = construction_path.name
entry['construction_sha256'] = sha(construction_path)
entry['measurement_contract'] = contract_path.name
entry['fixture_recipe'] = str(recipe_path.relative_to(REPO))
entry['candidate_risk']['reason'] = 'Attached Native walker arm pose and hand pixels may not yield an observable road signal'
entry['acquisition']['turn_signal_observation']['method'] = 'original 20 Hz Native turn, off indicator, affected vehicle and hand-bone source'
entry['acquisition']['hand_signal_observation'] = {
    'entrypoint': 'turn_finalizer.py', 'method': 'original Native attached avatar left-arm bone world readback',
    'evidence': 'hand_signal_original.jsonl, ego_turn_motion.jsonl and four videos'}
entry['candidates'] = []
for name, source, metric, condition, knobs in (
    ('fallback1', 'Native connected left-turn route inventory', 'eligible connected left-turn routes',
     'Primary route selection cannot spawn a complete turn', ['route spacing 2 m to 1.5 m']),
    ('fallback2', 'Original avatar actor and left-arm bone readback', 'attached avatar pose continuity',
     'Primary avatar overlaps ego or arm readback is occluded', ['avatar mount y -0.7 m to -0.8 m']),
    ('fallback3', 'Original driver-reference RGB stream', 'hand visible pixels',
     'Primary driver-reference camera crops the arm', ['driver camera mount x 0.6 m to 0.4 m'])):
    alternate = deepcopy(construction)
    if name == 'fallback1':
        cfg_item = next(i for i in alternate['files'] if i['path'] == 'config.json')
        cfg = json.loads(cfg_item['content'])
        cfg['engineering'].update(route_spacing_m=1.5, approach_steps=8)
        cfg_item['content'] = json.dumps(cfg, indent=2) + '\n'
    elif name == 'fallback2':
        runner = next(i for i in alternate['files'] if i['path'] == 'runner.py')
        old = 'carla.Location(x=.2, y=-.7, z=.4)'
        assert runner['content'].count(old) == 1
        runner['content'] = runner['content'].replace(old, 'carla.Location(x=.2, y=-.8, z=.4)')
    else:
        camera = next(i for i in alternate['files'] if i['path'] == 'turn_camera_capture.py')
        old = '"driver_reference": ((0.6, -0.35, 1.6),'
        if old not in camera['content']:
            raise ValueError('Driver-reference camera mount changed')
        camera['content'] = camera['content'].replace(old, '"driver_reference": ((0.4, -0.35, 1.6),')
    path = ROOT / f'{PREFIX}-{name}-construction.json'
    save(path, alternate)
    entry['candidates'].append({'id': name, 'construction': path.name,
        'construction_sha256': sha(path), 'trigger': {'source': source, 'metric': metric,
                                                      'failure_condition': condition},
        'changed_knobs': knobs})
save(ROOT / f'{PREFIX}-manifest.json', manifest)

proposals_path = ROOT / 'proposals/cases.json'
proposals = json.loads(proposals_path.read_text())
if not any(c['case_id'] == CASE for c in proposals['cases']):
    proposals['cases'].append({'case_id': CASE, 'target_law_id': 'NRS-484B-413-1',
        'target_type': 'boundary_probe',
        'rationale': 'Affected vehicle left turn with original attached driver-avatar left-arm bone readback and no Native indicator; physical and legal recognizability remain open.',
        'variable_assignments': {
            'turn_indicator_state': {'kind': 'controller', 'value': 'off'},
            'hand_signal_pose': {'kind': 'controller', 'value': 'left_arm_out'},
            'vehicle_may_be_affected': {'kind': 'world_setup', 'value': True},
            'pedestrian_may_be_affected': {'kind': 'world_setup', 'value': False}},
        'unresolved_judgment_calls': [],
        'recording_description': cfg['case']['recording_description']})
    save(proposals_path, proposals)
plan_path = ROOT / 'case-plan.json'
plan = json.loads(plan_path.read_text())
for case in plan['cases']:
    if case['case_id'] == CASE:
        case['construction_status'] = 'selected_required'
save(plan_path, plan)
print('Exact hand-signal primary, three fallbacks and source-complete diagnostic authored')
