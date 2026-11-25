"""Select two exact source-backed circulation-direction CPU bundles."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
FOLDER = HERE.parent
ASSIGNMENT = FOLDER.name
RUNTIME_SHA = '5e2dd81ac49dd2d9814a10b71ee30cf85323868a8369116020b06a69cbfcc5e3'
NAMES = ('raw_ego_motion', 'raw_other_motion', 'frame_join', 'st.roundabout',
         'rel.occupies', 'kin.heading', 'kin.position', 'kin.yaw_rate', 'drv.wrong_way')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def build():
    plan = json.loads((FOLDER / 'case-plan.json').read_text())
    ids = [ASSIGNMENT + '__probe_a', ASSIGNMENT + '__probe_b']
    plan['requirement_dispositions'] = [
        {'requirement': 'text-0', 'source': 'LVMC 11.43.010(A)',
         'source_text': 'The following regulations pertain to the operation of vehicles within a roundabout:',
         'status': 'selected_required', 'case_ids': ids,
         'evidence_or_gap': 'Roundabout setting selected; original island, roadway boundary and jurisdiction need review.'},
        {'requirement': 'text-1', 'source': 'LVMC 11.43.010(A)',
         'source_text': 'All vehicular travel shall be in a counterclockwise direction.',
         'status': 'selected_required', 'case_ids': ids,
         'evidence_or_gap': 'Exact opposite-direction comparison selected; original positions and continuous occupancy need review.'},
        ]
    plan['source_topic_inventory'] = [
        {'topic_id': 'text-0', 'kind': 'statutory_text',
         'text': 'The following regulations pertain to the operation of vehicles within a roundabout:',
         'source': 'LVMC 11.43.010(A)'},
        {'topic_id': 'text-1', 'kind': 'statutory_text',
         'text': 'All vehicular travel shall be in a counterclockwise direction.',
         'source': 'LVMC 11.43.010(A)'}]
    for case in plan['cases']:
        case['kind'] = 'selected_delivery_cpu_preparation'
        case['planning_status'] = 'selected_cpu_preparation_in_progress'
    for item in plan['comparisons']:
        item['status'] = 'selected_cpu_preparation_in_progress'
        item['audit_gap'] = 'Original Native physical outcomes pending.'
    for observation in plan['observations']:
        observation['status'] = 'source_channel_defined_original_review_pending'
    plan['source_observation_mapping'] = {name: {
        'evidence': 'Saved-only original actor/map/frame source join; original physical and legal review pending.',
        'channels': [name],
        'source_refs': ['native-raw-actors.jsonl', 'roundabout-map-readback.json',
                        'video_frames.jsonl']} for name in
        ('st.roundabout', 'rel.occupies', 'kin.heading', 'kin.position',
         'kin.yaw_rate', 'drv.wrong_way')}
    plan['camera_plan'] = {'profile': 'overview1080-capability', 'duration_s': 30,
        'composition': 'synchronized_four_view_primary',
        'coverage': [{'view': name, 'subject': 'ego and other circulating vehicle',
                      'interval': 'all 600 source frames'} for name in
                     ('overview', 'approach', 'reference_corner', 'driver_reference')]}
    plan['runtime_uncertainties'] = [
        'Original roundabout island, outer boundary, jurisdiction, participant lane occupancy and pixels require Native source review.',
        'Clockwise target may fail physically on the authored counterclockwise carriageway; source-measured fallback trigger applies.']
    write(FOLDER / 'case-plan.json', plan)
    description = {'channels': [{'name': name, 'unit': 'structured',
        'sampling_rate_hz': 20, 'time_window': '600 original frames',
        'method': 'source-joined Native pose/map/frame readback',
        'reference_frame': 'original Native frame and authored OpenDRIVE x/y',
        'uncertainty': '50 ms cadence; original boundary and pixels need review'}
        for name in NAMES],
        'context_inputs': [{'name': 'roundabout_map', 'unit': 'source_record',
                            'method': 'Native map readback and road.xodr'}],
        'limitations': ['Original roundabout boundary, jurisdiction and pixels require review; no statutory angular tolerance is assumed.']}
    entries, proposals = [], []
    for suffix, direction, sign in (('probe_a', 'counterclockwise', 1),
                                    ('probe_b', 'clockwise', -1)):
        case_id = ASSIGNMENT + '__' + suffix
        config = {'case_id': case_id, 'selected_case_id': case_id,
                  'law_id': 'LVMC-11-43-010-A', 'cell_id': 'C238396',
                  'actor': 'motor_vehicle_driver', 'rate_hz': 20,
                  'duration_s': 30, 'duration_frames': 600,
                  'candidate_id': 'primary', 'steer_gain': 1.3,
                  'max_steer': .75, 'required_atoms': ['kin.position'],
                  'source_actor_ids': ['ego', 'other'],
                  'cameras': [{'name': name, 'fps': 20, 'width': width,
                      'height': height, 'pose_strategy': 'fixed authored roundabout view',
                      'fov_deg': 85} for name, width, height in
                      (('overview', 1920, 1080), ('approach', 1280, 720),
                       ('reference_corner', 1280, 720),
                       ('driver_reference', 1280, 720))],
                  'condition': suffix, 'requested_direction': direction,
                  'physical_verified': False, 'legal_verdict': None,
                  'recording_description': description}
        config['case'] = {'case_id': case_id, 'recording_description': description}
        files = [{'path': path, 'content': (HERE / source).read_text()}
                 for path, source in [('runner.py', 'runner.py'),
                      ('geometry.py', 'geometry.py'),
                      ('roundabout_direction.py', 'roundabout_direction.py'),
                      ('roundabout-road.xodr', 'roundabout-road.xodr'),
                      ('finalize.py', 'finalize.py'),
                      ('tests/test_offline.py', 'test_selected_offline.py')]]
        files.insert(0, {'path': 'config.json',
                         'content': json.dumps(config, indent=2) + '\n'})
        construction = {'format': 'worker-inline-construction',
            'case_id': case_id, 'cell_id': 'C238396',
            'actor': 'motor_vehicle_driver', 'entrypoint': 'runner.py',
            'files': files, 'recording_description': description,
            'measurement_plan': 'Retain 600 original ego and other actor poses, map readback, exact frame joins and four synchronized camera sources; measure translational signed radial area after capture.',
            'static_checks': ['exact law/cell/actor', '600 frames at 20 Hz',
                              'two participants', 'four source cameras', 'no legal verdict'],
            'termination_rules': ['600 source frames or explicit Native capture failure'],
            'mechanisms': ['authored connected OpenDRIVE roundabout',
                           'two Native actor controllers', 'PipelineCapture and four FFV1 encodes',
                           'saved-only original-position direction meter'],
            'status': 'selected_delivery_cpu_in_progress'}
        path = FOLDER / 'native' / suffix / 'construction.json'
        write(path, construction)
        fallback = json.loads(json.dumps(construction))
        fallback_config = json.loads(next(x['content'] for x in fallback['files']
                                          if x['path'] == 'config.json'))
        fallback_config.update(candidate_id='fallback1', steer_gain=2.0, max_steer=.95)
        next(x for x in fallback['files'] if x['path'] == 'config.json')['content'] = (
            json.dumps(fallback_config, indent=2) + '\n')
        fallback['status'] = 'physical_steering_fallback_cpu_request'
        fallback_rel = f'fallbacks/{suffix}/fallback1/construction.json'
        write(FOLDER / fallback_rel, fallback)
        requirements = [
            {'disposition_index': 0, 'requirement': 'text-0',
             'source': 'LVMC 11.43.010(A)', 'output_key': 'roundabout_context',
             'method': 'measure_roundabout_context', 'value_type': 'object',
             'kind': 'sourced_context',
             'inputs': ['roundabout-map-readback.json', 'road.xodr']},
            {'disposition_index': 1, 'requirement': 'text-1',
             'source': 'LVMC 11.43.010(A)', 'output_key': 'circulation_direction',
             'method': 'measure_circulation_direction', 'value_type': 'object',
             'kind': 'measured',
             'inputs': ['native-raw-actors.jsonl', 'video_frames.jsonl']},
            ]
        contract_rel = f'selected-measurements/{suffix}/measurement-contract.json'
        write(FOLDER / contract_rel, {'format': 'worker-measurement-contract',
            'case_id': case_id, 'requirements': requirements,
            'negative': {'remove': ['roundabout-map-readback.json'],
                'error_contains': 'Missing required source: roundabout-map-readback.json'}})
        proposals.append({'case_id': case_id, 'target_law_id': 'LVMC-11-43-010-A',
            'target_type': 'compliant_attempt' if sign == 1 else 'violating_attempt',
            'rationale': 'Frozen within-roundabout direction witness',
            'paired_probe_id': 'c238396_circulation_direction',
            'deliberate_differences': ['direction_sign'],
            'probe': {'primary_variable': 'direction_sign',
                      'comparison_or_standard': 'counterclockwise source text',
                      'target_value_or_branch': direction},
            'variable_assignments': {'direction_sign': {'kind': 'controller',
                                                         'value': sign}},
            'recording_description': description,
            'unresolved_judgment_calls': []})
        entries.append({'case_id': case_id, 'kind': 'delivery',
            'construction': f'native/{suffix}/construction.json',
            'construction_sha256': sha(path),
            'candidate_risk': {'status': 'physical',
                'reason': 'Vehicle may leave the annulus or miss the commanded direction on a one-way authored ring.'},
            'candidates': [{'id': 'fallback1', 'construction': fallback_rel,
                'construction_sha256': sha(FOLDER / fallback_rel),
                'trigger': {'source': 'original Native actor poses and map readback',
                            'metric': 'ring occupancy and signed radial cross product',
                            'failure_condition': 'primary ego leaves ring or measured motion differs from requested direction'},
                'changed_knobs': ['steer_gain 1.3 to 2.0',
                                  'max_steer .75 to .95']}],
            'measurement_procedure': {'entrypoint': 'finalize.py'},
            'measurement_contract': contract_rel,
            'fixture_recipe': str((FOLDER / ('diagnostic-' + suffix + '-recipe.json')).relative_to(HERE.parents[2])),
            'delivery_readiness': 'incomplete', 'id': 'primary'})
    write(FOLDER / 'proposals/cases.json', {'cell_id': 'C238396',
        'actor': 'motor_vehicle_driver', 'status': 'draft',
        'cases': proposals, 'sweep_specs': [], 'sweeps_expanded': True})
    write(FOLDER / 'execution-manifest.json', {'format': 'worker-execution-manifest',
        'assignment_id': ASSIGNMENT, 'runtime_manifest_sha256': RUNTIME_SHA,
        'status': 'selected_delivery_cpu_in_progress', 'cases': entries})
    return {'cases': [{'case_id': e['case_id'],
                      'construction_sha256': e['construction_sha256']} for e in entries]}


if __name__ == '__main__':
    print(json.dumps(build(), indent=2))
