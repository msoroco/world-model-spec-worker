"""Build two exact median-turn bundles and matching spawn-risk fallbacks."""
import hashlib
import json
from pathlib import Path
import sys

PKG = Path(__file__).resolve().parents[1]
NATIVE = Path(__file__).resolve().parent
sys.path.insert(0, str(PKG))
from median_scene import CAMERAS, CASES, request

ASSIGNMENT = PKG.name
CAMERA_CONFIG = [{'name': name, 'width': width, 'height': height,
    'fov_deg': 85,
    'pose_strategy': {'overview': 'fixed_divided_road_overview',
                      'approach': 'ego_attached_forward_turn',
                      'reference_corner': 'fixed_median_reference',
                      'driver_reference': 'fixed_opposing_roadway'}[name]}
    for name, width, height in CAMERAS]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def build(suffix, candidate='primary'):
    if suffix not in CASES or candidate not in ('primary', 'fallback1'):
        raise ValueError('Unknown median-turn candidate')
    cid = ASSIGNMENT+'__'+suffix
    folder = NATIVE/'bundles'/suffix
    folder.mkdir(parents=True, exist_ok=True)
    assignment = Path('inputs')/ASSIGNMENT/'assignment.json'
    req = request(suffix)
    request_text = json.dumps(req, indent=2)+'\n'
    config = {'case_id': cid, 'selected_case_id': cid, 'case': {'case_id': cid},
        'candidate_id': candidate, 'cell_id': 'C124163',
        'law_id': 'NRS-484B-227-1', 'actor': 'motor_vehicle_driver',
        'assignment_sha256': sha(assignment.read_bytes()),
        'law_text': json.loads(assignment.read_text())['law']['text'],
        'rate_hz': 20, 'duration_s': 30, 'frames': 600,
        'spawn_z_m': 1.5 if candidate == 'primary' else 1.8,
        'source_kind': 'synthetic_scene_request', 'native_observed': False,
        'physical_completion': {'criterion': 'turn',
            'motion_source': 'body_history.jsonl',
            'body_key': 'body_vertices_m', 'heading_key': 'heading_deg',
            'turn_degrees': 90, 'turn_tolerance_deg': 30, 'turn_sign': 1,
            'minimum_progress_m': 8.0,
            'completion_goal_method': 'Original 90-degree left-turn body and heading history; engineering milestone, not statutory outcome'},
        'required_atoms': [], 'source_packets': [],
        'cameras': CAMERA_CONFIG, 'supported_case_ids': [cid],
        'case_target': {'physical_target': req['physical_target'],
            'crossing_x_m': req['target_crossing_x_m'],
            'authority_establishment': 'pending_original_source'},
        'request_sha256': sha(request_text.encode())}
    files = [{'path': 'assignment-source.json', 'source': str(assignment),
              'content': assignment.read_text()},
             {'path': 'request.json', 'content': request_text},
             {'path': 'road.xodr', 'content': req['source_map']},
             {'path': 'config.json', 'content': json.dumps(config, indent=2)+'\n'}]
    sources = [('median_scene.py', PKG/'median_scene.py'),
        ('measure_median_turn.py', PKG/'measure_median_turn.py'),
        ('native/measure_median.py', NATIVE/'measure_median.py'),
        ('runner.py', NATIVE/'runner.py'),
        ('finalize.py', NATIVE/'finalize.py'),
        ('tests/test_request.py', NATIVE/'tests'/'test_request.py')]
    for name, source in sources:
        files.append({'path': name, 'source': str(source.relative_to(Path.cwd())),
                      'content': source.read_text()})
    description = {'channels': [
        {'name': name, 'unit': 'structured', 'method': method,
         'sampling_rate_hz': 20, 'time_window': '600 frames',
         'reference_frame': 'Native roadways 1241631 and 1241632',
         'uncertainty': 'Original body, median, roadway and authority review pending'}
        for name, method in (
            ('ego_pose', 'original Native transform and full-body vertices'),
            ('median_geometry', 'original map and divider readback'),
            ('roadway_occupancy', 'full-body footprint on each roadway'),
            ('turn_history', 'original heading, speed and route source history'),
            ('administrative_context', 'independent public-authority source review'),
            ('median_crossing_measurement', 'saved full-body polygon overlap'))],
        'context_inputs': [], 'limitations': [
            'Authored opening or divider geometry is not original Native physical proof.',
            'Public-authority establishment is an independent administrative fact.',
            'Original motion and every camera frame require source review.']}
    construction = {'case_id': cid, 'cell_id': 'C124163',
        'law_id': 'NRS-484B-227-1', 'actor': 'motor_vehicle_driver',
        'entrypoint': 'runner.py', 'files': files,
        'recording_description': description, 'status': 'selected_native_draft',
        'measurement_plan': {'metric': '600-frame full-body median, opening, divider and roadway occupancy',
            'window': 'all driven frames and crossing event', 'source_review_required': True},
        'static_checks': ['two opposing right-hand roadways',
            'physical median sections and exact opening',
            '600-frame left-turn request', 'four synchronized camera sources'],
        'termination_rules': ['600 frames', 'original capture seal and world restoration'],
        'mechanisms': ['CARLA Native two-roadway OpenDRIVE map',
            'median object readback and opening request',
            'source-bound waypoint steering and full-body capture']}
    path = folder/('construction.json' if candidate == 'primary' else 'fallback1.json')
    path.write_text(json.dumps(construction, indent=2)+'\n')
    return {'case_id': cid, 'candidate_id': candidate,
            'construction': str(path.relative_to(PKG)),
            'construction_sha256': sha(path.read_bytes()), 'kind': 'delivery'}


if __name__ == '__main__':
    print(json.dumps([build(suffix, candidate) for suffix in CASES
        for candidate in ('primary', 'fallback1')], indent=2))
