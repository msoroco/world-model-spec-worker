"""Generate synthetic source-shaped parking fixtures; no authority or physical claim."""
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


for suffix, target_x in (('probe_1', -30.0), ('probe_2', 40.0)):
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
        body = [[x + dx, y + dy, z] for dx, dy in ((-4, -1), (-4, 1), (4, -1), (4, 1)) for z in (0, 2)]
        cameras = {name: native for name in CAMERAS}
        mapping[i].update(time_s=time, camera_native_frames=cameras)
        trace[i].update(frame=native, time_s=time,
                        position={'x': x, 'y': y, 'z': 0}, position_m=[x, y, 0],
                        speed_mps=speed, speed_mph=speed * 2.2369362921,
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
            'bbox_half_length_m': 4, 'bbox_half_width_m': 1,
            'observed_speed_mps': speed,
            'requested_control': {'phase': 'hold' if i >= 120 else 'approach'},
            'camera_native_frames': cameras,
            'vehicle_class_verified': False, 'public_park_status_verified': False})
    for key, value in (('trace.jsonl', trace), ('video_frames.jsonl', mapping),
                       ('capture/evidence.jsonl', evidence), ('capture/native/frames.jsonl', frames),
                       ('vehicle-poses.jsonl', poses)):
        spec['files'][key] = lines(value)
    spec['files']['frontage-inventory.json'] = json.dumps({'source_kind': 'native_saved_sample',
        'cell_id': 'C135709', 'native_lane_survey': [{'road_id': 1, 'lane_id': -1}],
        'street_bounds_m': STREET_BOUNDS, 'park_bounds_m': PARK_BOUNDS,
        'public_park_status': None, 'external_status_review_required': True}) + '\n'
    road_hash = sha(spec['files']['road.xodr'])
    spec['files']['park-review.json'] = json.dumps({'review_status': 'synthetic_diagnostic',
        'reviewer': 'synthetic fixture generator', 'source': 'synthetic park status inventory',
        'road_sha256': road_hash, 'pixel_sha256': 'synthetic_rgb_source',
        'park_status': 'public_park', 'park_bounds_m': PARK_BOUNDS,
        'residence_district_300ft': False, 'public_school': False,
        'public_access': True, 'jurisdiction_reviewed': True,
        'designation_source': 'synthetic external public park status record'}) + '\n'
    spec['files']['vehicle-spec-review.json'] = json.dumps({'review_status': 'synthetic_diagnostic',
        'reviewer': 'synthetic fixture generator', 'source': 'synthetic commercial vehicle specification',
        'pose_sha256': sha(spec['files']['vehicle-poses.jsonl']),
        'vehicle_class': 'commercial_motor_vehicle', 'trailer_present': False, 'occupant_count': 1, 'vehicle_overall_length_m': 8.0,
        'vehicle_unladen_mass_kg': 4000.0,
        'commercial_enterprise_basis': 'synthetic enterprise design and use record',
        'design_maintenance_or_use': 'synthetic commercial maintenance and use'}) + '\n'
    spec['files']['exception-review.json'] = json.dumps({'review_status': 'synthetic_diagnostic',
        'reviewer': 'synthetic fixture generator', 'source': 'synthetic exception activity inventory',
        'road_sha256': road_hash, 'pixel_sha256': 'synthetic_rgb_source',
        'posted_permission': False, 'expeditious_loading': False,
        'essential_local_service': False, 'property_frontage': 'synthetic park frontage',
        'door_open_observed': False, 'service_ttc_observed': False,
        'loading_activity_source': 'synthetic no loading record',
        'service_activity_source': 'synthetic no essential local service record',
        'device_wording': 'synthetic parking restriction device; no permission wording',
        'device_authority': 'synthetic diagnostic authority record only',
        'governed_area': 'synthetic surveyed narrow-road frontage',
        'parking_purpose': 'synthetic stopped parking activity',
        'actual_transfer_activity': 'synthetic no goods or passenger transfer',
        'section_wide_exceptions_review': 'reserved for independent legal review',
        'storage_meaning_review': 'reserved for independent legal review',
        'modifier_scope_review': 'reserved for independent legal review'}) + '\n'
    spec['files']['fixture-provenance.json'] = json.dumps({'diagnostic_fixture': True,
        'source': 'synthetic parking source shape', 'physical_acceptance_claimed': False}) + '\n'
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
    recipe = {'format': 'worker-fixture-recipe',
              'sources': [{'path': 'diagnostic-input.json', 'source': str(target.relative_to(ROOT)),
                           'sha256': hashlib.sha256(target.read_bytes()).hexdigest()}],
              'generator': {'source': str(target.relative_to(ROOT)),
                            'sha256': hashlib.sha256(target.read_bytes()).hexdigest()}}
    (HERE / ('diagnostic-' + suffix + '-recipe.json')).write_text(json.dumps(recipe, indent=2) + '\n')
    print(suffix, target.stat().st_size)
