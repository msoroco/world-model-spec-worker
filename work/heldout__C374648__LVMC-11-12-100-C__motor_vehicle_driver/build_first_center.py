"""Bind the first exact center-turn construction to source-shaped CPU inputs."""

from hashlib import sha256
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ASSIGNMENT = HERE.name
CASE = ASSIGNMENT + '__left_center_east'
INPUT = f'inputs/{ASSIGNMENT}/assignment.json'


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def build():
    plan = json.loads((HERE/'case-plan.json').read_text())
    case_ids = [row['case_id'] for row in plan['cases']]
    description = {
        'channels': [{'name': 'turn_origin_observation', 'unit': 'structured',
                      'sampling_rate_hz': 20,
                      'method': 'joined original Native lane and heading rows',
                      'time_window': 'all original frames',
                      'reference_frame': 'Native road/lane identity',
                      'uncertainty': 'map projection and legal designation authority'}],
        'context_inputs': [{'name': 'case_context', 'unit': 'structured',
                            'method': 'authored actor/target/frame intent and original marking review'}],
        'limitations': ['Map markings are candidate topology, not designation authority.',
                        'Actual completion, pixels and legal applicability require review.']}
    cameras = [('overview', 1920, 1080, 95), ('approach', 1280, 720, 90),
               ('reference_corner', 1280, 720, 100),
               ('driver_reference', 1280, 720, 85)]
    config = {'selected_case_id': CASE, 'law_id': 'LVMC-11-12-100-C',
              'cell_id': 'C374648', 'actor': 'motor_vehicle_driver',
              'rate_hz': 20, 'frames': 80, 'duration_s': 4,
              'required_atoms': [], 'source_packets': [],
              'cameras': [{'name': name, 'width': width, 'height': height,
                           'fov_deg': fov,
                           'pose_strategy': 'subject-mounted provisional lane and marking source view'}
                          for name, width, height, fov in cameras],
              'case': {'case_id': CASE, 'recording_description': description},
              'supported_case_ids': case_ids}
    write(HERE/'config.json', config)
    paths = ['config.json', 'runner.py', 'center_turn_cameras.py',
             'center_turn_construction.py', 'turn_origin_capture.py',
             'turn_origin_measurement.py', 'turn_origin_finalizer.py',
             'tests/test_center_turn_construction.py',
             'tests/test_turn_origin_measurement.py',
             'tests/test_turn_origin_finalizer.py',
             'tests/test_runner_config.py']
    construction = {'format': 'worker-construction', 'case_id': CASE,
                    'law_id': 'LVMC-11-12-100-C', 'cell_id': 'C374648',
                    'actor': 'motor_vehicle_driver', 'entrypoint': 'runner.py',
                    'recording_description': description,
                    'files': [{'path': path, 'content': (HERE/path).read_text()}
                              for path in paths],
                    'measurement_plan': {
                        'original_sources': ['turn_origin_native.jsonl',
                                             'case_context.json', 'video_frames.jsonl',
                                             'trace.jsonl',
                                             *[name+'.mkv' for name, *_ in cameras]],
                        'derived_channels': ['turn_origin_observation'],
                        'saved_only_finalizer': 'turn_origin_finalizer.py'},
                    'static_checks': ['Exact first C374648 case and 80 Native ticks at 20 Hz',
                                      'Marked connected center/outer approach and left exit',
                                      'Four synchronized source cameras and original lane/heading rows',
                                      'Authored actor/target/frame intent, authority unresolved'],
                    'termination_rules': ['Stop after 80 original ticks',
                                          'Fail on missing subject, frame, lane or camera source',
                                          'Close source encoders and restore world settings'],
                    'mechanisms': {'route': 'marked Native center/outer connected selector',
                                   'control': 'bounded center-lane left route feedback',
                                   'capture': 'four FFV1 cameras, PipelineCapture, FrameMap and turn-origin source',
                                   'construction_status': 'first_exact_primary_cpu_proof_pending'}}
    write(HERE/'construction.json', construction)
    contract = {'format': 'worker-measurement-contract', 'case_id': CASE,
                'requirements': [
                    {'disposition_index': 0,
                     'requirement': plan['requirement_dispositions'][0]['requirement'],
                     'source': plan['requirement_dispositions'][0]['source'],
                     'output_key': 'center_lane_use',
                     'method': 'analyze', 'value_type': 'object', 'kind': 'sourced_context',
                     'inputs': ['turn_origin_native.jsonl', 'case_context.json',
                                'video_frames.jsonl', 'trace.jsonl']},
                    {'disposition_index': 1,
                     'requirement': plan['requirement_dispositions'][1]['requirement'],
                     'source': plan['requirement_dispositions'][1]['source'],
                     'output_key': 'turn_origin_observation',
                     'method': 'analyze', 'value_type': 'object', 'kind': 'measured',
                     'inputs': ['turn_origin_native.jsonl', 'case_context.json',
                                'video_frames.jsonl', 'trace.jsonl']}],
                'negative': {'remove': ['turn_origin_native.jsonl'],
                             'error_contains': 'Missing required source: turn_origin_native.jsonl'}}
    write(HERE/'measurement-contract-left_center_east.json', contract)
    proposal_dir = HERE/'proposals'
    proposal_dir.mkdir(exist_ok=True)
    proposal = {'case_id': CASE, 'target_law_id': 'LVMC-11-12-100-C',
                'target_type': 'boundary_probe',
                'rationale': 'Original lane of origin and observed left deflection for a marked center-lane candidate; authority and legal preparation remain unresolved.',
                'variable_assignments': {
                    'origin_lane': {'kind': 'controller', 'value': 'center candidate'},
                    'approach_direction': {'kind': 'world_setup', 'value': 'east'}},
                'unresolved_judgment_calls': ['statutory two-way left-turn lane designation',
                                              'preparing for or making a left turn'],
                'recording_description': description}
    write(proposal_dir/'cases.json', {'cases': [proposal]})
    template = next(ROOT.glob('work/heldout__C230259*/diagnostic-baseline_left.json'))
    diagnostic = json.loads(template.read_text())
    for key in ('ego_road_frames.jsonl', 'road_exception_context.json',
                'right_half_fixture_provenance.json'):
        diagnostic['files'].pop(key, None)
    trace = [json.loads(line) for line in diagnostic['files']['trace.jsonl'].splitlines() if line]
    if len(trace) != 9:
        raise ValueError('Expected nine source-shaped diagnostic Native frames')
    headings = [(1., 0.), (1., 0.), (1., 0.), (1., 0.),
                (.94, -.34), (.7, -.71), (.5, -.866), (.26, -.97), (0., -1.)]
    rows = []
    for i, (packet, heading) in enumerate(zip(trace, headings)):
        rows.append({'frame': packet['frame'], 'time_s': packet['time_s'],
                     'ego_id': '31', 'ego_forward_xy': list(heading),
                     'is_junction': 4 <= i < 8, 'road_id': 17 if i < 8 else 25,
                     'lane_id': 1, 'center_turn_road_id': 17,
                     'center_turn_lane_id': 1,
                     'designation_source': 'authored candidate plus synthetic map markings; authority undecided',
                     'center_marking_source_ids': ['road:17:lane:1:left:Solid:Yellow',
                                                   'road:17:lane:1:right:Broken:Yellow']})
    diagnostic['files']['turn_origin_native.jsonl'] = ''.join(
        json.dumps(row)+'\n' for row in rows)
    context = {
        'format': 'worker-authored-turn-intent', 'case_id': CASE,
        'ego_actor_id': 31, 'target_start_frame': rows[0]['frame'],
        'target_exit_road_id': 25, 'target_exit_lane_id': 1,
        'requested_maneuver': 'left turn',
        'designation_authority_verified': False,
        'physical_completion_verified': False,
        'legal_acceptance_claimed': False}
    context['case_context'] = {key: value for key, value in context.items()}
    diagnostic['files']['case_context.json'] = json.dumps(context)+'\n'
    diagnostic['files']['center_turn_fixture_provenance.json'] = json.dumps({
        'kind': 'diagnostic_text', 'source': str(template.relative_to(ROOT)),
        'meaning': 'Synthetic lane/heading join only; no Native physical or legal claim'})+'\n'
    diagnostic_path = HERE/'diagnostic-left_center_east.json'
    diagnostic_path.write_text(json.dumps(diagnostic, separators=(',', ':'),
                                          ensure_ascii=False)+'\n')
    ref = f'work/{ASSIGNMENT}/{diagnostic_path.name}'
    recipe = {'format': 'worker-fixture-recipe',
              'sources': [{'path': 'diagnostic-input.json', 'source': ref,
                           'sha256': digest(diagnostic_path)}],
              'generator': {'source': ref, 'sha256': digest(diagnostic_path)}}
    write(HERE/'fixture-recipe-left_center_east.json', recipe)
    manifest = {'format': 'worker-execution-manifest', 'assignment_id': ASSIGNMENT,
                'runtime_manifest_sha256': digest(ROOT/'runtime/SOURCE-MANIFEST.json'),
                'cases': [{'case_id': CASE, 'kind': 'delivery',
                           'construction': 'construction.json',
                           'construction_sha256': digest(HERE/'construction.json'),
                           'measurement_procedure': {'entrypoint': 'turn_origin_finalizer.py'},
                           'measurement_contract': 'measurement-contract-left_center_east.json',
                           'fixture_recipe': ref.replace(diagnostic_path.name,
                                                         'fixture-recipe-left_center_east.json'),
                           'candidate_risk': {'status': 'physical',
                                              'reason': 'Actual center-lane designation, map suitability, turn motion and camera visibility require Native review'},
                           'candidates': []}]}
    write(HERE/'execution-manifest.json', manifest)
    plan['observations'] = [{'name': 'turn_origin_observation', 'mandatory': True,
                             'source': 'original 20 Hz Native lane and heading rows with authored candidate designation context',
                             'measurement': 'lane of origin and observed left deflection without legal designation finding',
                             'case_ids': case_ids}]
    plan['camera_plan'] = {'profile': 'overview1080-capability', 'duration_s': 4,
                           'composition': 'synchronized_four_view_primary',
                           'coverage': [{'view': name, 'subject': 'ego, center/outer lane markings and left-turn junction',
                                         'interval': 'entire original case sequence'}
                                        for name, *_ in cameras]}
    mapping = {}
    for item in json.loads((ROOT/INPUT).read_text()).get('source_observation_terms', []):
        term = item['term']
        mapping[term] = {'evidence': f'original lane/heading/map source for {term}; designation authority unresolved',
                         'channels': ['turn_origin_observation'],
                         'source_refs': ['turn_origin_native.jsonl', 'case_context.json']}
    plan['source_observation_mapping'] = mapping
    write(HERE/'case-plan.json', plan)
    return {'manifest_sha256': digest(HERE/'execution-manifest.json'),
            'diagnostic_bytes': diagnostic_path.stat().st_size}


if __name__ == '__main__':
    print(json.dumps(build()))
