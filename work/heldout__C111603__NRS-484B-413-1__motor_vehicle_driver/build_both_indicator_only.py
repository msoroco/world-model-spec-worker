"""Build exact affected-pedestrian no-horn turn and source-complete CPU diagnostic."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
CASE = ROOT.name + '__both_indicator_only'
PREFIX = 'both-indicator-only'


def save(path, value, compact=False):
    path.write_text(json.dumps(value, separators=(',', ':') if compact else None,
                               indent=None if compact else 2, allow_nan=False) + '\n')


def sha(path):
    return sha256(path.read_bytes()).hexdigest()


construction = deepcopy(json.loads((ROOT / 'vehicle-indicator-construction.json').read_text()))
construction['case_id'] = CASE
description = deepcopy(construction['recording_description'])
description['channels'][0]['method'] = 'original ego yaw, Native indicator readback, participant bounds and independently captured listener PCM'
description['channels'][0]['uncertainty'] = 'microphone alignment and physical horn absence require original-source review; legal audibility stays unresolved'
construction['recording_description'] = description
for item in construction['files']:
    if item['path'] == 'config.json':
        config = json.loads(item['content'])
        config['selected_case_id'] = CASE
        config['case']['case_id'] = CASE
        config['case']['recording_description'] = description
        item['content'] = json.dumps(config, indent=2) + '\n'
    elif item['path'] == 'runner.py':
        item['content'] = (ROOT / 'runner_both_indicator_only.py').read_text()
    elif item['path'] == 'turn_finalizer.py':
        item['content'] = (ROOT / 'both_indicator_only_finalizer.py').read_text()
for name in ('turn_deferred_audio.py', 'turn_listener_capture.py'):
    construction['files'].append({'path': name, 'content': (ROOT / name).read_text()})
construction_path = ROOT / f'{PREFIX}-construction.json'
save(construction_path, construction)

plan_path = ROOT / 'case-plan.json'
plan = json.loads(plan_path.read_text())
plan['requirement_dispositions'][3]['status'] = 'selected_required'
plan['requirement_dispositions'][3]['evidence_or_gap'] = 'Both-affected horn-plus-indicator and indicator-only exact Native constructions selected; physical source review pending.'
save(plan_path, plan)
contract = json.loads((ROOT / 'vehicle-indicator-measurement-contract.json').read_text())
contract['case_id'] = CASE
contract['requirements'][0]['disposition_index'] = 3
contract['requirements'][0]['requirement'] = plan['requirement_dispositions'][3]['requirement']
contract['requirements'][0]['inputs'].append('listener_audio_original.jsonl')
contract['negative'] = {'remove': ['listener_audio_original.jsonl'],
                        'error_contains': 'Missing required source: listener_audio_original.jsonl'}
contract_path = ROOT / f'{PREFIX}-measurement-contract.json'
save(contract_path, contract)

diagnostic = json.loads((ROOT / 'vehicle-indicator-diagnostic.json').read_text())
signals = [json.loads(line) for line in diagnostic['files']['ego_signal_audio.jsonl'].splitlines()]
participants = [json.loads(line) for line in diagnostic['files']['participant_bodies.jsonl'].splitlines()]
originals = []
samples = [0.] * 8
sample_hash = sha256(json.dumps(samples, separators=(',', ':')).encode()).hexdigest()
for index, (signal, bodies) in enumerate(zip(signals, participants)):
    signal['indicator_readback'] = 'left' if index >= 1 else 'off'
    signal['listener_audio_samples'] = samples
    signal['listener_audio_status'] = 'original_pcm'
    signal['listener_packet_sha256'] = sample_hash
    bodies['bodies']['ped_listener']['x_m'] = 0
    bodies['bodies']['ped_listener']['y_m'] = 2
    bodies['bodies']['affected_vehicle']['x_m'] = 5
    bodies['bodies']['affected_vehicle']['y_m'] = 5
    originals.append({'origin': 'listener_pcm_capture', 'frame': signal['frame'],
                      'listener_id': 'ped_listener', 'capture_source': 'diagnostic listener PCM source',
                      'capture_source_sha256': sha256(b'C111603 diagnostic listener PCM').hexdigest(),
                      'capture_provenance': 'synthetic diagnostic PCM only',
                      'sample_rate_hz': 160, 'samples': samples, 'sha256': sample_hash})
diagnostic['files']['ego_signal_audio.jsonl'] = ''.join(json.dumps(row) + '\n' for row in signals)
diagnostic['files']['participant_bodies.jsonl'] = ''.join(json.dumps(row) + '\n' for row in participants)
diagnostic['files']['listener_audio_original.jsonl'] = ''.join(json.dumps(row) + '\n' for row in originals)
diagnostic['files']['affected_participants.json'] = json.dumps({
    'pedestrian_may_be_affected': True,
    'pedestrian_may_be_affected_source': 'diagnostic pedestrian close to selected turn corridor',
    'vehicle_may_be_affected': True,
    'vehicle_may_be_affected_source': 'diagnostic vehicle on selected turn exit',
    'participant_types': {'ped_listener': 'pedestrian', 'affected_vehicle': 'vehicle'},
    'listener_id': 'ped_listener',
    'listener_position_source': 'diagnostic original pedestrian position rows',
    'participant_geometry_source': 'diagnostic original participant body rows'}) + '\n'
diagnostic['files']['turn_fixture_provenance.json'] = json.dumps({
    'diagnostic_fixture': True, 'source': 'C111603 synthetic affected-pedestrian no-horn originals',
    'case_id': CASE}) + '\n'
diagnostic_path = ROOT / f'{PREFIX}-diagnostic.json'
save(diagnostic_path, diagnostic, compact=True)
recipe = {'format': 'worker-fixture-recipe', 'sources': [{
    'path': 'diagnostic-input.json', 'source': str(diagnostic_path.relative_to(REPO)),
    'sha256': sha(diagnostic_path)}], 'generator': {
        'source': str(diagnostic_path.relative_to(REPO)), 'sha256': sha(diagnostic_path)}}
save(ROOT / f'{PREFIX}-recipe.json', recipe)

manifest = deepcopy(json.loads((ROOT / 'vehicle-indicator-manifest.json').read_text()))
entry = manifest['cases'][0]
for key in ('offline', 'compatibility', 'negative', 'delivery_acceptance', 'candidates'):
    entry.pop(key, None)
entry.update(case_id=CASE, construction=construction_path.name,
             construction_sha256=sha(construction_path),
             measurement_contract=contract_path.name,
             fixture_recipe=str((ROOT / f'{PREFIX}-recipe.json').relative_to(REPO)))
entry['recording_description'] = description
entry['candidate_risk']['reason'] = 'Native pedestrian and vehicle effects, listener timing, absence of horn sound and indicator visibility need physical source review'
entry['acquisition']['turn_signal_observation']['method'] = 'original Native turn and both affected participants joined to indicator readback and independent listener PCM; no horn actuator command'
definitions = (
    ('fallback1', 'Native pedestrian and connected-route inventory',
     'pedestrian distance to sampled route', 'Primary placement does not make pedestrian potentially affected',
     ['pedestrian route-side offset 6/2 to 5/1.5 m']),
    ('fallback2', 'Original listener microphone PCM',
     '20 Hz audio packet continuity', 'Primary ALSA device loses or misaligns a listener packet',
     ['listener PCM rate 16000 to 32000 Hz']),
    ('fallback3', 'Original overview RGB decode',
     'pedestrian visible pixel count', 'Primary overview crops the potentially affected pedestrian',
     ['overview camera mount x -8 to -9 m']),
)
entry['candidates'] = []
for name, source, metric, condition, knobs in definitions:
    alternate = deepcopy(construction)
    if name == 'fallback1':
        runner = next(item for item in alternate['files'] if item['path'] == 'runner.py')
        old = 'carla.Location(x=6, y=2, z=.5)'
        if runner['content'].count(old) != 1:
            raise ValueError('Pedestrian route placement source changed')
        runner['content'] = runner['content'].replace(old, 'carla.Location(x=5, y=1.5, z=.5)')
    elif name == 'fallback2':
        runner = next(item for item in alternate['files'] if item['path'] == 'runner.py')
        old = "ListenerCaptureProcess(output / 'listener.wav', device=require_microphone_device())"
        if runner['content'].count(old) != 1:
            raise ValueError('Listener microphone source changed')
        runner['content'] = runner['content'].replace(old,
            "ListenerCaptureProcess(output / 'listener.wav', device=require_microphone_device(), sample_rate_hz=32000)")
    else:
        camera = next(item for item in alternate['files'] if item['path'] == 'turn_camera_capture.py')
        old = '"overview": ((-8, 0, 8), (-12, 0, 0), (1920, 1080), 95),'
        if camera['content'].count(old) != 1:
            raise ValueError('Overview camera source changed')
        camera['content'] = camera['content'].replace(old,
            '"overview": ((-9, 0, 8), (-12, 0, 0), (1920, 1080), 95),')
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
        'rationale': 'Potentially affected pedestrian and vehicle with left indicator but no horn actuation; physical signal effects remain unresolved.',
        'variable_assignments': {
            'horn_actuation': {'kind': 'controller', 'value': 'none'},
            'pedestrian_may_be_affected': {'kind': 'world_setup', 'value': True},
            'vehicle_may_be_affected': {'kind': 'world_setup', 'value': True},
            'turn_indicator_state': {'kind': 'controller', 'value': 'left'}},
        'unresolved_judgment_calls': [], 'recording_description': description})
    save(proposals_path, proposals)
print('Exact affected-pedestrian no-horn primary and three fallbacks authored')
