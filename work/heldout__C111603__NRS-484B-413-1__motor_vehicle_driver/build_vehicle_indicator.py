"""Author the first exact C111603 inline construction and source-complete CPU fixture."""
from hashlib import sha256
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
IDENT = ROOT.name
CASE = IDENT + '__vehicle_left_indicator'
BASE = REPO / 'work/heldout__C5191__LVMC-11-18-030-B__motor_vehicle_driver/diagnostic-left_turn_lane_contained_approach.json'
SOURCE = f'inputs/{IDENT}/assignment.json'
REQUIREMENT = 'Direct-course left turn with another vehicle potentially affected: original indicator readback, participant clearance and unresolved reasonable-safety judgment'


def save(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def sha(path):
    return sha256(path.read_bytes()).hexdigest()


plan_path = ROOT / 'case-plan.json'
plan = json.loads(plan_path.read_text())
plan['requirement_dispositions'] = [
    {'requirement': REQUIREMENT, 'source': SOURCE, 'status': 'selected_required',
     'case_ids': [CASE], 'evidence_or_gap': 'No accepted original; selected Native indicator/clearance acquisition and diagnostic proof.'},
    {'requirement': 'Pedestrian possibly affected: clearly audible pre-turn horn from original listener audio',
     'source': SOURCE, 'status': 'alternative_pending',
     'case_ids': [IDENT+'__ped_horn_audio', IDENT+'__ped_no_horn_audio'],
     'evidence_or_gap': 'No real listener source or horn actuation yet; pending exact construction.'},
    {'requirement': 'Other vehicle possibly affected: no indicator and hand-signal alternatives',
     'source': SOURCE, 'status': 'alternative_pending',
     'case_ids': [IDENT+'__vehicle_no_indicator', IDENT+'__vehicle_hand_signal'],
     'evidence_or_gap': 'Pending exact source-visible alternative constructions.'},
    {'requirement': 'Both pedestrian and vehicle possibly affected: conjunctive horn and appropriate signal',
     'source': SOURCE, 'status': 'alternative_pending',
     'case_ids': [IDENT+'__both_signals', IDENT+'__both_indicator_only'],
     'evidence_or_gap': 'Pending exact conjunctive source acquisition.'},
    {'requirement': 'Reasonable-safety body clearance comparison across wider and narrower turns',
     'source': SOURCE, 'status': 'alternative_pending',
     'case_ids': [IDENT+'__clearance_wide', IDENT+'__clearance_narrow'],
     'evidence_or_gap': 'Source measurement exists; exact controlled turn constructions pending.'}]
save(plan_path, plan)


recording = {'channels': [{
    'name': 'turn_signal_observation', 'unit': 'structured', 'sampling_rate_hz': 20,
    'method': 'original ego yaw, Native indicator readback, participant bounds and listener audio status',
    'time_window': 'all 8 s original frames', 'reference_frame': 'Native world and ego vehicle',
    'uncertainty': 'sampled 20 Hz state; lamp pixels and legal appropriateness require later review'}],
    'context_inputs': [], 'limitations': [
        'Source-shaped CPU diagnostic cannot verify physical lamp visibility, affected status, safety or legal appropriateness.']}
config = {'selected_case_id': CASE, 'law_id': 'NRS-484B-413-1', 'cell_id': 'C111603',
          'actor': 'motor_vehicle_driver', 'rate_hz': 20, 'frames': 160, 'duration_s': 8,
          'required_atoms': [], 'source_packets': [],
          'cameras': [{'name': name, 'width': spec[2][0], 'height': spec[2][1],
                       'pose_strategy': 'subject-mounted provisional turn and indicator visibility',
                       'fov_deg': spec[3]}
                      for name, spec in {
                          'overview': ((-8,0,8),(-12,0,0),(1920,1080),95),
                          'approach': ((1.2,0,2),(0,0,0),(1280,720),90),
                          'reference_corner': ((-3,2.5,2.6),(-7,0,0),(1280,720),100),
                          'driver_reference': ((.6,-.35,1.6),(0,0,0),(1280,720),85)}.items()],
          'case': {'case_id': CASE, 'recording_description': recording},
          'engineering': {'route_spacing_m': 2., 'approach_steps': 6,
                          'route_candidate_index': 0, 'target_speed_mps': 5., 'speed_gain': .25}}
save(ROOT / 'vehicle-indicator-config.json', config)
proposal_dir = ROOT / 'proposals'
proposal_dir.mkdir(exist_ok=True)
save(proposal_dir / 'cases.json', {
    'cell_id': 'C111603', 'actor': 'motor_vehicle_driver', 'status': 'draft',
    'cases': [{'case_id': CASE, 'target_law_id': 'NRS-484B-413-1',
               'target_type': 'boundary_probe',
               'rationale': 'Other vehicle may be affected by a left turn; Native indicator readback and body clearance are retained while physical and legal findings remain open.',
               'variable_assignments': {
                   'turn_indicator_state': {'kind': 'controller', 'value': 'left'},
                   'vehicle_may_be_affected': {'kind': 'world_setup', 'value': True},
                   'pedestrian_may_be_affected': {'kind': 'world_setup', 'value': False}},
               'unresolved_judgment_calls': [],
               'recording_description': recording}],
    'sweep_specs': []})
files = ['runner.py', 'turn_native_route.py', 'turn_native_sources.py',
         'turn_camera_capture.py', 'turn_signal_measurement.py',
         'listener_pcm_source.py', 'turn_finalizer.py',
         'tests/test_turn_signal_measurement.py',
         'tests/test_turn_native_sources.py', 'tests/test_listener_pcm_source.py']
construction = {'format': 'worker-construction-proposal', 'case_id': CASE,
                'law_id': config['law_id'], 'cell_id': config['cell_id'],
                'actor': config['actor'], 'entrypoint': 'runner.py',
                'recording_description': recording,
                'files': [{'path': 'config.json', 'content': json.dumps(config, indent=2) + '\n'}] +
                         [{'path': name, 'content': (ROOT / name).read_text()} for name in files]}
construction_path = ROOT / 'vehicle-indicator-construction.json'
save(construction_path, construction)
contract = {'format': 'worker-measurement-contract', 'case_id': CASE,
            'requirements': [{'disposition_index': 0,
                              'requirement': REQUIREMENT,
                              'source': SOURCE,
                              'output_key': 'turn_signal_observation', 'method': 'measure_turn_indicator',
                              'value_type': 'object', 'kind': 'measured',
                              'inputs': ['ego_turn_motion.jsonl', 'ego_signal_audio.jsonl',
                                         'affected_participants.json', 'participant_bodies.jsonl',
                                         'video_frames.jsonl', 'trace.jsonl',
                                         'overview.mkv', 'approach.mkv', 'reference_corner.mkv',
                                         'driver_reference.mkv'] }],
            'negative': {'remove': ['ego_signal_audio.jsonl'],
                         'error_contains': 'Missing required source: ego_signal_audio.jsonl'}}
save(ROOT / 'vehicle-indicator-measurement-contract.json', contract)
diagnostic = json.loads(BASE.read_text())
trace = [json.loads(line) for line in diagnostic['files']['trace.jsonl'].splitlines()]
motion = []
signal = []
participants = []
audio_original = []
for index, row in enumerate(trace):
    frame, time = row['frame'], row['time_s']
    motion.append({'frame': frame, 'time_s': time, 'ego_yaw_deg': row['heading_deg'],
                   'x_m': row['position']['x'], 'y_m': row['position']['y'],
                   'body_radius_m': 1.2})
    signal.append({'frame': frame, 'time_s': time, 'listener_id': 'ped_listener',
                   'indicator_readback': 'left' if index >= 1 else 'off',
                   'listener_audio_samples': None,
                   'listener_audio_status': 'not_collected_no_affected_pedestrian',
                   'listener_packet_sha256': None})
    participants.append({'frame': frame, 'time_s': time,
                         'bodies': {'ped_listener': {'x_m': 50, 'y_m': 50, 'body_radius_m': .3},
                                    'affected_vehicle': {'x_m': 5, 'y_m': 5, 'body_radius_m': 1.2}}})
    audio_original.append({'origin': 'not_collected_no_affected_pedestrian',
                           'frame': frame, 'listener_id': 'ped_listener', 'samples': None,
                           'sha256': None})
diagnostic['files'].update({
    'ego_turn_motion.jsonl': ''.join(json.dumps(row) + '\n' for row in motion),
    'ego_signal_audio.jsonl': ''.join(json.dumps(row) + '\n' for row in signal),
    'participant_bodies.jsonl': ''.join(json.dumps(row) + '\n' for row in participants),
    'listener_audio_original.jsonl': ''.join(json.dumps(row) + '\n' for row in audio_original),
    'affected_participants.json': json.dumps({
        'pedestrian_may_be_affected': False,
        'pedestrian_may_be_affected_source': 'diagnostic pedestrian trajectory outside selected turn corridor',
        'vehicle_may_be_affected': True,
        'vehicle_may_be_affected_source': 'diagnostic affected vehicle within selected left-turn path',
        'participant_types': {'ped_listener': 'pedestrian', 'affected_vehicle': 'vehicle'},
        'listener_id': 'ped_listener',
        'listener_position_source': 'diagnostic original pedestrian position rows',
        'participant_geometry_source': 'diagnostic original participant body rows'}) + '\n',
    'turn_fixture_provenance.json': json.dumps({'diagnostic_fixture': True,
        'source': 'C111603 synthetic vehicle indicator and turn-source originals',
        'case_id': CASE}) + '\n'})
diagnostic_path = ROOT / 'vehicle-indicator-diagnostic.json'
diagnostic_path.write_text(json.dumps(diagnostic, separators=(',', ':'), allow_nan=False) + '\n')
recipe = {'format': 'worker-fixture-recipe', 'sources': [
    {'path': 'diagnostic-input.json', 'source': str(diagnostic_path.relative_to(REPO)),
     'sha256': sha(diagnostic_path)}],
    'generator': {'source': str(diagnostic_path.relative_to(REPO)),
                  'sha256': sha(diagnostic_path)}}
save(ROOT / 'vehicle-indicator-recipe.json', recipe)
manifest = {'format': 'worker-execution-manifest', 'assignment_id': IDENT,
            'runtime_manifest_sha256': 'a4626c89ca4e80fb42351a8fdd4f6aa2601a670a9df51707d306bb45732cdaf3',
            'cases': [{'case_id': CASE, 'kind': 'delivery',
                       'construction': construction_path.name,
                       'construction_sha256': sha(construction_path),
                       'measurement_procedure': {'entrypoint': 'turn_finalizer.py'},
                       'measurement_contract': 'vehicle-indicator-measurement-contract.json',
                       'fixture_recipe': str((ROOT / 'vehicle-indicator-recipe.json').relative_to(REPO)),
                       'native_handoff': {'python_env_var': 'CARLA_PYTHON',
                                          'host_env_var': 'CARLA_HOST', 'port_env_var': 'CARLA_PORT'},
                       'candidate_risk': {'status': 'physical',
                                          'reason': 'Native connected turn, lamp pixel visibility and affected participant geometry may fail'},
                       'acquisition': {'turn_signal_observation': {
                           'entrypoint': 'turn_finalizer.py',
                           'method': 'original 20 Hz Native turn, indicator, participant and explicit no-pedestrian audio status',
                           'evidence': 'ego_turn_motion, ego_signal_audio, affected_participants, participant_bodies and four videos'}}}]}
save(ROOT / 'vehicle-indicator-manifest.json', manifest)
print('First exact vehicle-indicator construction, measurement contract and diagnostic recipe authored')
