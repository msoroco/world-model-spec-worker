"""Build exact two-case current-runtime one-way Native construction drafts."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ASSIGNMENT = HERE.name
DIRECTIONS = ('designated', 'opposite')
CAMERAS = (('overview', 1920, 1080), ('approach', 1280, 720),
           ('reference_corner', 1280, 720), ('driver_reference', 1280, 720))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def make(direction, candidate):
    case_id = ASSIGNMENT + '__' + direction
    speed = 8 if candidate == 'primary' else 5
    channels = [
        {'name': name, 'unit': 'structured', 'sampling_rate_hz': 20,
         'method': method, 'time_window': '600 original Native frames',
         'reference_frame': 'directed governed one-way road',
         'uncertainty': '20 Hz sampling; original authority and sign pixel review pending'}
        for name, method in (
            ('ego_pose', 'original Native transform, bounding box and velocity'),
            ('travel_direction_vs_sign', 'saved trajectory, source-reviewed designated direction and sign'),
            ('st.one_way_roadway', 'independent one-way designation joined to original map'),
            ('dev.regulatory_sign', 'original signal inventory and sourced official sign review'),
            ('st.lane_direction', 'source-reviewed permitted direction and OpenDRIVE lane'),
            ('kin.heading', 'original Native yaw and velocity'),
            ('drv.wrong_way', 'measured velocity projection against sourced designation'),
            ('rel.occupies', 'original footprint projected into governed road extent'))]
    recording = {'channels': channels, 'context_inputs': [],
                 'limitations': ['authored sign request alone proves neither official authority nor physical visibility',
                                 'one-way designation needs an independent source',
                                 'actual Native motion and sign pixels require later physical review']}
    config = {'case_id': case_id, 'selected_case_id': case_id,
              'supported_case_ids': [ASSIGNMENT + '__' + d for d in DIRECTIONS],
              'candidate_id': candidate, 'law_id': 'NRS-484B-220-1',
              'cell_id': 'C150916', 'actor': 'motor_vehicle_driver',
              'assignment_sha256': sha(ROOT / 'inputs' / ASSIGNMENT / 'assignment.json'),
              'case_plan_sha256': sha(HERE / 'case-plan.json'),
              'requested_direction': direction, 'target_speed_mps': speed,
              'requested_speed_mps': speed,
              'reverse_motion': direction == 'opposite',
              'rate_hz': 20, 'duration_s': 30, 'required_atoms': [],
              'source_packets': [], 'case': {'case_id': case_id},
              'cameras': [{'name': name, 'width': width, 'height': height,
                           'pose_strategy': 'fixed roadside map survey; subject and governed sign review',
                           'fov_deg': 85} for name, width, height in CAMERAS],
              'recording_description': recording, 'status': 'selected_cpu_draft_physical_unverified'}
    files = [{'path': name, 'content': (HERE / 'selected' / name).read_text(),
              'source': 'work/' + ASSIGNMENT + '/selected/' + name}
             for name in ('runner.py', 'road_geometry.py', 'one_way_saved_measure.py',
                          'finalize.py', 'tests/test_native.py')]
    contract = HERE / 'cases' / direction / 'measurement-contract.json'
    files.append({'path': 'measurement-contract.json', 'content': contract.read_text(),
                  'source': 'work/' + ASSIGNMENT + '/cases/' + direction + '/measurement-contract.json'})
    files.append({'path': 'config.json', 'content': json.dumps(config, indent=2) + '\n'})
    construction = {'case_id': case_id, 'law_id': 'NRS-484B-220-1',
                    'cell_id': 'C150916', 'actor': 'motor_vehicle_driver',
                    'entrypoint': 'runner.py', 'files': files,
                    'recording_description': recording,
                    'measurement_plan': {'entrypoint': 'finalize.py',
                                         'required_sources': ['road.xodr', 'road-context.json',
                                                              'road-review.json', 'vehicle-pose.jsonl',
                                                              'video_frames.jsonl'],
                                         'source_review_required': True},
                    'static_checks': ['400 m two-lane one-way OpenDRIVE request',
                                      'R6-1 sign requests 101 and 102',
                                      '1920x1080 overview plus three 1280x720 views for 600 frames at 20 Hz'],
                    'mechanisms': ['Native map, lane and signal request readback',
                                   'subject traverses same lane in requested positive or negative direction',
                                   'original velocity, footprint, four camera joins and independent authority review feed saved measurement'],
                    'termination_rules': ['600 original frames',
                                          'restore Native world and release owned actors'],
                    'status': 'selected_cpu_draft_physical_unverified'}
    path = HERE / 'selected' / 'drafts' / direction / candidate / 'construction.json'
    write(path, construction)
    return path


def main():
    entries = []
    for direction in DIRECTIONS:
        primary = make(direction, 'primary')
        fallback = make(direction, 'fallback1')
        entries.append({'case_id': ASSIGNMENT + '__' + direction,
                        'id': 'primary', 'kind': 'delivery',
                        'construction': str(primary.relative_to(HERE)),
                        'construction_sha256': sha(primary),
                        'measurement_contract': 'cases/' + direction + '/measurement-contract.json',
                        'measurement_procedure': {'entrypoint': 'finalize.py'},
                        'fixture_recipe': 'work/' + ASSIGNMENT + '/cases/' + direction + '/fixture-recipe.json',
                        'native_handoff': {'python_env_var': 'CARLA_PYTHON',
                                           'host_env_var': 'CARLA_HOST',
                                           'port_env_var': 'CARLA_PORT'},
                        'candidate_risk': {'status': 'physical',
                                           'reason': '8 m/s subject may leave the governed segment or miss sign camera framing'},
                        'candidates': [{'id': 'fallback1',
                                        'construction': str(fallback.relative_to(HERE)),
                                        'construction_sha256': sha(fallback),
                                        'trigger': {'source': 'original Native vehicle-pose.jsonl and road-context.json',
                                                    'metric': '600-frame governed extent and sign-pixel coverage',
                                                    'failure_condition': 'subject leaves governed extent or requested sign is not visible in synchronized source cameras'},
                                        'changed_knobs': ['target speed reduced from 8 to 5 m/s']}]})
    manifest = {'format': 'worker-execution-manifest', 'assignment_id': ASSIGNMENT,
                'runtime_manifest_sha256': sha(ROOT / 'runtime' / 'SOURCE-MANIFEST.json'),
                'status': 'selected_cpu_proofs_in_progress', 'delivery_ready': False,
                'original_native_observed': False, 'cases': entries}
    write(HERE / 'execution-manifest.json', manifest)
    print(json.dumps({'cases': {e['case_id']: e['construction_sha256'] for e in entries},
                      'manifest_sha256': sha(HERE / 'execution-manifest.json')}))


if __name__ == '__main__':
    main()
