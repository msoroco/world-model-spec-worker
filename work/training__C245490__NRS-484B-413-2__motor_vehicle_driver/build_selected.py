"""Materialize six exact change-lane draft bundles, without running CARLA."""
import hashlib
import json
from pathlib import Path

from signal_scene import CASE_SUFFIXES, request, road_xml


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
IDENTITY = HERE.name
SHARED = ('runner.py', 'native_capture.py', 'signal_scene.py',
    'finalize.py', 'measure_signal.py', 'tests/test_offline.py')
CHANNELS = ('kin.position', 'kin.speed', 'sig.turn_indicator', 'sig.hand_signal',
    'drv.distance_while', 'kin.path_length', 'drv.turning', 'drv.lane_change',
    'env.precipitation', 'ego_pose',
    'continuous_signal_distance_before_course_change')


def encoded(value):
    return json.dumps(value, indent=2, allow_nan=False) + '\n'


def put(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def cameras():
    return [
        {'name': 'overview', 'width': 1920, 'height': 1080, 'fov_deg': 90,
         'xyz_m': [25, -20, 18], 'yaw_deg': 73, 'pitch_deg': -40,
         'attach_to_ego': False, 'pose_strategy': 'full original lane-change event and roadside context'},
        {'name': 'approach', 'width': 1280, 'height': 720, 'fov_deg': 90,
         'xyz_m': [-20, -15, 8], 'yaw_deg': 12, 'pitch_deg': -8,
         'attach_to_ego': False, 'pose_strategy': 'original approach and signal onset'},
        {'name': 'reference_corner', 'width': 1280, 'height': 720, 'fov_deg': 90,
         'xyz_m': [30, -15, 8], 'yaw_deg': 90, 'pitch_deg': -25,
         'attach_to_ego': False, 'pose_strategy': 'original lane marking and full-body crossing'},
        {'name': 'driver_reference', 'width': 1280, 'height': 720, 'fov_deg': 90,
         'xyz_m': [1, 0, 2], 'yaw_deg': 0, 'pitch_deg': -8,
         'attach_to_ego': True, 'pose_strategy': 'original driver-relative signal and lane reference'},
    ]


def description():
    return {'channels': [{'name': name, 'unit': 'structured',
        'sampling_rate_hz': 20, 'time_window': '600 original frames',
        'method': 'post-tick signal/pose/body/lane/weather joined by Native frame',
        'reference_frame': 'original Native frame',
        'uncertainty': 'Area class, pixels and legal judgment need independent original review'}
        for name in CHANNELS],
        'context_inputs': [{'name': name, 'unit': 'structured',
            'method': 'retained source for independent original review'}
            for name in ('area_class_source', 'original_video', 'lane_source',
                'weather_source')],
        'limitations': ['Signal command differs from observed light and visible pixels.',
            'Requested area class is not legal classification.']}


def one(suffix):
    case_id = IDENTITY + '__' + suffix
    folder = HERE if suffix == '90' else HERE / 'native' / 'selected-drafts' / suffix / 'primary'
    source = (REPO / 'inputs' / IDENTITY / 'assignment.json').read_text()
    road = road_xml() + '\n'
    plan = request(suffix)
    config = dict(plan, selected_case_id=case_id, case_id=case_id,
        law_id='NRS-484B-413-2', cell_id='C245490', actor='motor_vehicle_driver',
        supported_case_ids=[IDENTITY + '__' + name for name in CASE_SUFFIXES],
        assignment_sha256=sha(source), road_sha256=sha(road),
        vehicle_blueprint='vehicle.tesla.model3', controller_gain=1.5,
        required_atoms=['kin.position', 'kin.speed'], source_packets=[],
        course='change_lane', legal_verdict=None, cameras=cameras(),
        recording_description=description(),
        physical_completion={'criterion': 'lane_transition',
            'motion_source': 'body_history.jsonl', 'body_key': 'body_vertices_m',
            'lane_key': 'lane_id',
            'destination_lane': -2 if plan['signal_side'] == 'right' else -1,
            'minimum_progress_m': 1.0, 'engineering_tolerances_not_legal': True})
    put(folder / 'config.json', encoded(config))
    put(folder / 'road.xodr', road)
    put(folder / 'assignment-source.json', source)
    files = []
    for name in SHARED:
        path = HERE / name
        files.append({'path': name, 'source': str(path.relative_to(REPO)),
            'content': path.read_text()})
    for name in ('config.json', 'road.xodr', 'assignment-source.json'):
        path = folder / name
        files.append({'path': name, 'source': str(path.relative_to(REPO)),
            'content': path.read_text()})
    construction = {'case_id': case_id, 'law_id': 'NRS-484B-413-2',
        'cell_id': 'C245490', 'actor': 'motor_vehicle_driver',
        'entrypoint': 'runner.py', 'status': 'selected_cpu_construction',
        'files': files, 'recording_description': config['recording_description'],
        'mechanisms': ['post-tick 20 Hz Native source', 'four synchronized original cameras',
            'full-body lane-history and observed light readback'],
        'measurement_plan': 'Join original signal/light/body/lane/weather sources; measure sampled continuous path distance before independently observed lane change; no legal verdict.',
        'static_checks': ['exact six-case identity', '600 frames at 20 Hz',
            'same-direction OpenDRIVE readback', 'four-camera profile'],
        'termination_rules': ['600 original frames or explicit source failure']}
    put(folder / 'construction.json', encoded(construction))
    return folder


if __name__ == '__main__':
    print('\n'.join(str(one(suffix).relative_to(REPO)) for suffix in CASE_SUFFIXES))
