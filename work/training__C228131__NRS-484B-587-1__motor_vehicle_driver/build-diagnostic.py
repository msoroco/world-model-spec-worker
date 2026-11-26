"""Build source-shaped controlled-entry diagnostics, without physical or legal claims."""
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BASE = ROOT / 'work/training__C394566__LVMC-11-48-060__motor_vehicle_driver/diagnostic-probe_01.json'
AID = HERE.name
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
sys.path.insert(0, str(HERE / 'native'))
from geometry import open_drive
from route import target


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def lines(rows):
    return ''.join(json.dumps(row, separators=(',', ':'), allow_nan=False) + '\n' for row in rows)


def rows(text):
    return [json.loads(line) for line in text.splitlines()]


for suffix in ('witness_1', 'witness_2'):
    spec = json.loads(BASE.read_text())
    spec['files'] = {key: value for key, value in spec['files'].items() if key in
        ('trace.jsonl', 'video_frames.jsonl', 'capture/recorder_info.txt',
         'capture/evidence.jsonl', 'capture/native/frames.jsonl', 'capture/manifest.json')}
    spec['files']['road.xodr'] = open_drive()
    trace = rows(spec['files']['trace.jsonl'])
    mapping = rows(spec['files']['video_frames.jsonl'])
    evidence = rows(spec['files']['capture/evidence.jsonl'])
    frames = rows(spec['files']['capture/native/frames.jsonl'])
    poses = []
    for i in range(600):
        native = mapping[i]['native_frame']
        time = i / 20
        request = target(suffix, i)
        x, y = round(request['x_m'], 4), round(request['y_m'], 4)
        body = [[x+dx, y+dy, z] for dx, dy in ((-2.2, -.9), (-2.2, .9),
                                                 (2.2, -.9), (2.2, .9)) for z in (0, 2)]
        cameras = {name: native for name in CAMERAS}
        mapping[i].update(time_s=time, camera_native_frames=cameras)
        trace[i].update(frame=native, time_s=time,
                        position={'x': x, 'y': y, 'z': 0}, position_m=[x, y, 0],
                        speed_mps=2, speed_mph=4.4738725842, velocity_mps=[2, 0, 0])
        evidence[i].update(original_frame=native, replay_frame=native,
                           recording_time_s=time, replay_simulation_time_s=time)
        evidence[i]['ego'].update(position_m=[x, y, 0], speed_mps=2, body_vertices_m=body)
        frames[i]['simulation_time'] = time
        original = evidence[i]['original_observations']
        original.update(frame=native, time_s=time)
        subject = next(a for a in original['participants'] if a['actor_id'] == evidence[i]['actor_id'])
        subject.update(position_m=[x, y, 0], velocity_mps=[2, 0, 0],
                       speed_mps=2, body_vertices_m=body)
        graph = spec['graphs'][i]
        graph['attributes']['observed_evidence'] = original
        graph['nodes'][0]['attributes']['vertex'] = [x, y, 0]
        graph['nodes'][0]['attributes']['threedbbox'] = body
        poses.append({'native_frame': native, 'video_frame': i, 'time_s': time,
            'vehicle_id': 1, 'center_xy_m': [x, y],
            'footprint_half_width_m': .9, 'footprint_half_length_m': 2.2,
            'footprint_m': {'min_x': x-2.2, 'max_x': x+2.2,
                            'min_y': y-.9, 'max_y': y+.9},
            'camera_native_frames': cameras})
    for key, value in (('trace.jsonl', trace), ('video_frames.jsonl', mapping),
                       ('capture/evidence.jsonl', evidence), ('capture/native/frames.jsonl', frames),
                       ('actor-poses.jsonl', poses)):
        spec['files'][key] = lines(value)
    spec['files']['access-inventory.json'] = json.dumps({'source_kind': 'native_saved_sample',
        'cell_id': 'C228131', 'subject_id': 1, 'subject_blueprint_id': 'vehicle.tesla.model3',
        'device_actor_id': 2, 'device_blueprint_id': 'synthetic_sign_shape',
        'road_survey': [{'x_m': x, 'y_m': y, 'road_id': rid, 'lane_id': -1,
                         'waypoint_distance_m': 0} for x, y, rid in
                         ((-20, -9, 2), (0, -3.5, 3), (20, 0, 1), (60, -3.5, 2))],
        'highway_road_id_candidate': 1, 'frontage_road_id_candidate': 2,
        'paved_entry_road_id_candidate': 3, 'official_status_reviewed': False,
        'lane_connectivity_reviewed': False}) + '\n'
    authority = {
        'access-authority.txt': 'Synthetic diagnostic controlled-access public-authority determination shape; original authority unresolved.\n',
        'device-authority.txt': 'Synthetic diagnostic official-device authority shape; original official status unresolved.\n',
        'device-content.txt': 'Synthetic diagnostic indicated entrance/exit content shape; original content unresolved.\n',
        'device-erection.txt': 'Synthetic diagnostic installed-device shape; original erection unresolved.\n',
        'entrance-extent.txt': 'Synthetic diagnostic indicated entrance interval -12 m to +12 m; original extent unresolved.\n',
        'highway-dedication.txt': 'Synthetic diagnostic highway dedication shape; original dedication unresolved.\n',
        'public-use.txt': 'Synthetic diagnostic public vehicular use shape; original use unresolved.\n',
        'jurisdiction.txt': 'Synthetic diagnostic public-authority jurisdiction shape; original jurisdiction unresolved.\n',
        'vehicle-eligibility.txt': 'Synthetic diagnostic ordinary motor-vehicle eligibility shape; original status unresolved.\n'}
    spec['files'].update(authority)
    access_refs = ('access-authority.txt', 'highway-dedication.txt', 'public-use.txt',
                   'jurisdiction.txt', 'vehicle-eligibility.txt')
    device_refs = ('device-authority.txt', 'device-content.txt', 'device-erection.txt',
                   'entrance-extent.txt')
    spec['files']['access-review.json'] = json.dumps({'review_status': 'synthetic_diagnostic',
        'reviewer': 'synthetic fixture generator', 'source': 'synthetic highway access context',
        'road_sha256': sha(spec['files']['road.xodr']),
        'pose_sha256': sha(spec['files']['actor-poses.jsonl']),
        'source_sha256': {name: sha(authority[name]) for name in access_refs},
        'controlled_access_highway': True, 'highway_edge_y_m': -3.5,
        'original_public_authority_status': 'unresolved'}) + '\n'
    spec['files']['device-review.json'] = json.dumps({'review_status': 'synthetic_diagnostic',
        'reviewer': 'synthetic fixture generator', 'source': 'synthetic installed device context',
        'road_sha256': sha(spec['files']['road.xodr']),
        'overview_sha256': 'synthetic_rgb_source',
        'source_sha256': {name: sha(authority[name]) for name in device_refs},
        'device_official': True, 'device_erected': True, 'device_indicates_entry': True,
        'indicated_entrance_x_interval_m': [-12, 12],
        'original_device_authority_status': 'unresolved'}) + '\n'
    spec['files']['fixture-provenance.json'] = json.dumps({'diagnostic_fixture': True,
        'source': 'synthetic controlled-entry source shape',
        'physical_acceptance_claimed': False}) + '\n'
    manifest = json.loads(spec['files']['capture/manifest.json'])
    manifest.update(case_id=AID + '__' + suffix, frames=600,
                    sources={'road.xodr': sha(spec['files']['road.xodr']),
                             'trace.jsonl': sha(spec['files']['trace.jsonl'])})
    spec['files']['capture/manifest.json'] = json.dumps(manifest, separators=(',', ':')) + '\n'
    for video, name in zip(spec['videos'], CAMERAS):
        video['path'] = name + '.mkv'
        if name == 'overview':
            video['width'], video['height'] = 1920, 1080
    target_path = HERE / ('diagnostic-' + suffix + '.json')
    target_path.write_text(json.dumps(spec, separators=(',', ':'), allow_nan=False) + '\n')
    recipe = {'format': 'worker-fixture-recipe', 'sources': [
        {'path': 'diagnostic-input.json', 'source': str(target_path.relative_to(ROOT)),
         'sha256': hashlib.sha256(target_path.read_bytes()).hexdigest()}],
        'generator': {'source': str(target_path.relative_to(ROOT)),
                      'sha256': hashlib.sha256(target_path.read_bytes()).hexdigest()}}
    (HERE / ('diagnostic-' + suffix + '-recipe.json')).write_text(json.dumps(recipe, indent=2) + '\n')
    print(suffix, target_path.stat().st_size)
