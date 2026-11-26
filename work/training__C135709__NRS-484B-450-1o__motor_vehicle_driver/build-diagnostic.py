"""Build source-shaped device-zone fixtures; no physical or authority claim."""
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
from geometry import PARK_BOUNDS, STREET_BOUNDS, open_drive


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def lines(rows):
    return ''.join(json.dumps(row, separators=(',', ':'), allow_nan=False) + '\n' for row in rows)


def rows(text):
    return [json.loads(line) for line in text.splitlines()]


for suffix, target_x in (('false', 12.0), ('true', -10.0)):
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
        x = -80 + (target_x + 80) * min(i, 120) / 120
        speed = abs((target_x + 80) / 6) if i < 120 else 0
        y = -1.75
        body = [[x + dx, y + dy, z] for dx, dy in ((-2.25, -1), (-2.25, 1), (2.25, -1), (2.25, 1)) for z in (0, 2)]
        cameras = {name: native for name in CAMERAS}
        mapping[i].update(time_s=time, camera_native_frames=cameras)
        trace[i].update(frame=native, time_s=time, position={'x': x, 'y': y, 'z': 0},
                        position_m=[x, y, 0], speed_mps=speed, speed_mph=speed * 2.2369362921,
                        velocity_mps=[speed, 0, 0])
        evidence[i].update(original_frame=native, replay_frame=native,
                           recording_time_s=time, replay_simulation_time_s=time)
        evidence[i]['ego'].update(position_m=[x, y, 0], speed_mps=speed, body_vertices_m=body)
        frames[i]['simulation_time'] = time
        original = evidence[i]['original_observations']
        original.update(frame=native, time_s=time)
        subject = next(a for a in original['participants'] if a['actor_id'] == evidence[i]['actor_id'])
        subject.update(position_m=[x, y, 0], velocity_mps=[speed, 0, 0],
                       speed_mps=speed, body_vertices_m=body)
        graph = spec['graphs'][i]
        graph['attributes']['observed_evidence'] = original
        graph['nodes'][0]['attributes']['vertex'] = [x, y, 0]
        graph['nodes'][0]['attributes']['threedbbox'] = body
        poses.append({'native_frame': native, 'video_frame': i, 'time_s': time,
            'vehicle_id': 1, 'vehicle_xyz_m': [x, y, 0], 'vehicle_yaw_deg': 0,
            'bbox_half_length_m': 2.25, 'bbox_half_width_m': 1,
            'observed_speed_mps': speed,
            'requested_control': {'phase': 'hold' if i >= 120 else 'approach'},
            'camera_native_frames': cameras, 'device_authority_verified': False,
            'legal_outcome_verified': False})
    for key, value in (('trace.jsonl', trace), ('video_frames.jsonl', mapping),
                       ('capture/evidence.jsonl', evidence), ('capture/native/frames.jsonl', frames),
                       ('vehicle-poses.jsonl', poses)):
        spec['files'][key] = lines(value)
    road_hash = sha(spec['files']['road.xodr'])
    pose_hash = sha(spec['files']['vehicle-poses.jsonl'])
    spec['files']['device-inventory.json'] = json.dumps({'source_kind': 'native_saved_sample',
        'cell_id': 'C135709', 'native_lane_survey': [{'road_id': 1, 'lane_id': -1}],
        'street_bounds_m': STREET_BOUNDS, 'authored_zone_bounds_m': PARK_BOUNDS,
        'authored_device_id': 'authored-no-parking-135709',
        'official_status': None, 'external_authority_review_required': True}) + '\n'
    device = {'review_status': 'synthetic_diagnostic', 'reviewer': 'synthetic fixture generator',
        'source': 'synthetic device identity and authority shape', 'road_sha256': road_hash,
        'pixel_sha256': 'synthetic_rgb_source', 'device_code': 'no_parking',
        'governed_zone_bounds_m': PARK_BOUNDS, 'official_status': 'unresolved_from_synthetic',
        'authority_source': 'synthetic shape only; installation authority unverified',
        'traffic_purpose': 'synthetic shape only; original purpose unverified',
        'legal_consistency': 'unresolved_incorporated_law'}
    spec['files']['device-review.json'] = json.dumps(device) + '\n'
    spec['files']['condition-review.json'] = json.dumps({'review_status': 'synthetic_diagnostic',
        'reviewer': 'synthetic fixture generator', 'source': 'synthetic device condition shape',
        'device_review_sha256': sha(spec['files']['device-review.json']),
        'condition': 'all_hours_all_vehicle_classes', 'civil_time': 'synthetic 2026-11-25T12:00:00-08:00',
        'vehicle_class': 'motor_vehicle'}) + '\n'
    spec['files']['activity-review.json'] = json.dumps({'review_status': 'synthetic_diagnostic',
        'reviewer': 'synthetic fixture generator', 'source': 'synthetic vehicle activity shape',
        'pose_sha256': pose_hash, 'activity': 'requested_park', 'purpose': 'synthetic parking request',
        'responsible_person_source': 'synthetic driver assignment',
        'actual_service_activity': 'none observed in synthetic shape'}) + '\n'
    spec['files']['exception-review.json'] = json.dumps({'review_status': 'synthetic_diagnostic',
        'reviewer': 'synthetic fixture generator', 'source': 'synthetic exception circumstances shape',
        'pose_sha256': pose_hash,
        'traffic_conflict_source': 'synthetic no conflict observation; necessity unresolved',
        'law_compliance_source': 'other-law status unresolved',
        'police_direction_source': 'synthetic no police direction observation',
        'device_direction_source': 'authored prohibition sign only; direction exception unresolved'}) + '\n'
    spec['files']['fixture-provenance.json'] = json.dumps({'diagnostic_fixture': True,
        'source': 'synthetic device-zone shape', 'physical_acceptance_claimed': False}) + '\n'
    manifest = json.loads(spec['files']['capture/manifest.json'])
    manifest.update(case_id=AID + '__' + suffix, frames=600,
                    sources={'road.xodr': road_hash, 'trace.jsonl': sha(spec['files']['trace.jsonl'])})
    spec['files']['capture/manifest.json'] = json.dumps(manifest, separators=(',', ':')) + '\n'
    for video, name in zip(spec['videos'], CAMERAS):
        video['path'] = name + '.mkv'
        if name == 'overview':
            video['width'], video['height'] = 1920, 1080
    target = HERE / ('diagnostic-' + suffix + '.json')
    target.write_text(json.dumps(spec, separators=(',', ':'), allow_nan=False) + '\n')
    recipe = {'format': 'worker-fixture-recipe', 'sources': [
        {'path': 'diagnostic-input.json', 'source': str(target.relative_to(ROOT)),
         'sha256': hashlib.sha256(target.read_bytes()).hexdigest()}],
        'generator': {'source': str(target.relative_to(ROOT)),
                      'sha256': hashlib.sha256(target.read_bytes()).hexdigest()}}
    (HERE / ('diagnostic-' + suffix + '-recipe.json')).write_text(json.dumps(recipe, indent=2) + '\n')
    print(suffix, target.stat().st_size)
