"""Build source-shaped adjacent-vehicle diagnostics; no original physical claim."""
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


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def lines(rows):
    return ''.join(json.dumps(row, separators=(',', ':'), allow_nan=False) + '\n' for row in rows)


def rows(text):
    return [json.loads(line) for line in text.splitlines()]


for suffix, y, moving, machine, police in (
        ('probe_1', 0.6, False, 'motorcycle', False),
        ('probe_2', 3.0, False, 'motorcycle', False),
        ('probe_3', 3.0, True, 'motorcycle', False),
        ('probe_4', 3.0, False, 'moped', False),
        ('probe_5', 3.0, False, 'motorcycle', True)):
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
        x = round(-30 + 2 * time, 3)
        body = [[x + dx, y + dy, z] for dx, dy in ((-.9, -.35), (-.9, .35), (.9, -.35), (.9, .35)) for z in (0, 2)]
        cameras = {name: native for name in CAMERAS}
        mapping[i].update(time_s=time, camera_native_frames=cameras)
        trace[i].update(frame=native, time_s=time, position={'x': x, 'y': y, 'z': 0},
                        position_m=[x, y, 0], speed_mps=2, speed_mph=4.4738725842,
                        velocity_mps=[2, 0, 0])
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
        other_x = round(time if moving else 0, 3)
        poses.append({'native_frame': native, 'video_frame': i, 'time_s': time,
            'subject_id': 1,
            'subject_footprint_m': {'min_x': x-.9, 'max_x': x+.9, 'min_y': y-.35, 'max_y': y+.35},
            'other_vehicle_ids': [2, 3],
            'other_vehicle_footprints_m': [
                {'min_x': other_x-1, 'max_x': other_x+1, 'min_y': 1.15, 'max_y': 1.85},
                {'min_x': other_x-1, 'max_x': other_x+1, 'min_y': 4.15, 'max_y': 4.85}],
            'other_vehicle_speeds_mps': [1 if moving else 0, 1 if moving else 0],
            'camera_native_frames': cameras})
    for key, value in (('trace.jsonl', trace), ('video_frames.jsonl', mapping),
                       ('capture/evidence.jsonl', evidence), ('capture/native/frames.jsonl', frames),
                       ('actor-poses.jsonl', poses)):
        spec['files'][key] = lines(value)
    spec['files']['lane-inventory.json'] = json.dumps({'source_kind': 'native_saved_sample',
        'cell_id': 'C178141', 'lane_survey': [{'x_m': x, 'y_m': lane_y, 'road_id': 1, 'lane_id': lane}
            for x in (-50, -30, 0, 30, 50) for lane_y, lane in ((4.5, -1), (1.5, -2))],
        'subject_blueprint_id': 'vehicle.vespa.zx125' if machine == 'moped' else 'vehicle.kawasaki.ninja',
        'subject_kind_candidate': machine,
        'other_vehicle_ids': [2, 3], 'other_vehicle_lane_ids': [-2, -1],
        'surrounding_mode_request': 'moving' if moving else 'stationary',
        'police_duty_requested': police, 'police_duty_source': None,
        'physical_collision_clearance_verified': False}) + '\n'
    spec['files']['split-review.json'] = json.dumps({'review_status': 'synthetic_diagnostic',
        'reviewer': 'synthetic fixture generator', 'source': 'synthetic split context shape',
        'road_sha256': sha(spec['files']['road.xodr']),
        'pose_sha256': sha(spec['files']['actor-poses.jsonl']),
        'overview_sha256': 'synthetic_rgb_source',
        'lane_occupancy': 'synthetic adjacent lane occupant assignment',
        'marking_source': 'synthetic authored lane boundary',
        'legal_status': 'unassessed'}) + '\n'
    spec['files']['classification-review.json'] = json.dumps({'review_status': 'synthetic_diagnostic',
        'reviewer': 'synthetic fixture generator', 'source': 'synthetic machine classification shape',
        'pose_sha256': sha(spec['files']['actor-poses.jsonl']), 'subject_kind': machine,
        'chapter_definition_status': 'unavailable_NRS_482_0295_and_482_029; unresolved_autocycle'}) + '\n'
    spec['files']['duty-review.json'] = json.dumps({'review_status': 'synthetic_diagnostic',
        'reviewer': 'synthetic fixture generator', 'source': 'synthetic police duty shape',
        'pose_sha256': sha(spec['files']['actor-poses.jsonl']),
        'subject_is_police_officer': police, 'subject_performing_police_duty': police,
        'officer_identity_source': 'synthetic identity shape',
        'performance_of_duty_source': 'synthetic separate duty shape',
        'legal_exception_status': 'unassessed'}) + '\n'
    spec['files']['fixture-provenance.json'] = json.dumps({'diagnostic_fixture': True,
        'source': 'synthetic adjacent-lane shape', 'physical_acceptance_claimed': False}) + '\n'
    manifest = json.loads(spec['files']['capture/manifest.json'])
    manifest.update(case_id=AID + '__' + suffix, frames=600,
                    sources={'road.xodr': sha(spec['files']['road.xodr']),
                             'trace.jsonl': sha(spec['files']['trace.jsonl'])})
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
