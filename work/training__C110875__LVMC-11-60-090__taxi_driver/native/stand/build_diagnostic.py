"""Build source-shaped taxi diagnostics; black video is software only."""
import hashlib
import json
from pathlib import Path

from geometry import open_drive

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
ASSIGNMENT = HERE.parents[1].name
BASE = ROOT / 'work/training__C179819__LVMC-11-16-060__motor_vehicle_driver/diagnostic-probe_1.json'
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha_text(value):
    return hashlib.sha256(value.encode()).hexdigest()


def lines(rows):
    return ''.join(json.dumps(row, separators=(',', ':'), allow_nan=False) + '\n' for row in rows)


def build(suffix):
    source = json.loads(BASE.read_text())
    source['files'] = {key: value for key, value in source['files'].items() if key in (
        'road.xodr', 'trace.jsonl', 'video_frames.jsonl',
        'capture/recorder_info.txt', 'capture/evidence.jsonl',
        'capture/native/frames.jsonl', 'capture/manifest.json')}
    actors = [json.loads(x) for x in (HERE / 'current-profile-sources' / suffix / 'native-actors.jsonl').read_text().splitlines()]
    mapping = [json.loads(x) for x in source['files']['video_frames.jsonl'].splitlines()]
    trace = [json.loads(x) for x in source['files']['trace.jsonl'].splitlines()]
    evidence = [json.loads(x) for x in source['files']['capture/evidence.jsonl'].splitlines()]
    frames = [json.loads(x) for x in source['files']['capture/native/frames.jsonl'].splitlines()]
    poses = []
    for index, actor in enumerate(actors):
        frame = mapping[index]['native_frame']
        time_s = index / 20
        x, y = actor['ego_xy_m']
        heading = actor['heading_deg']
        speed = 5.0
        vx = speed if heading == 0 else 0.0
        vy = -speed if heading == -90 else 0.0
        body = [[x + dx, y + dy, z] for dx, dy in
                ((-2, -1), (-2, 1), (2, -1), (2, 1)) for z in (0, 2)]
        trace[index].update(frame=frame, time_s=time_s,
            position={'x': x, 'y': y, 'z': 0}, position_m=[x, y, 0],
            heading_deg=heading, speed_mps=speed, speed_mph=speed / .44704,
            velocity_mps=[vx, vy, 0])
        mapping[index]['time_s'] = time_s
        evidence[index].update(original_frame=frame, replay_frame=frame,
            recording_time_s=time_s, replay_simulation_time_s=time_s)
        evidence[index]['ego'].update(position_m=[x, y, 0],
            speed_mps=speed, heading_deg=heading, body_vertices_m=body)
        evidence[index]['world']['road_projection']['road_id'] = 3 if y < -5 else 2 if x > 81 else 1
        frames[index]['simulation_time'] = time_s
        observed = evidence[index]['original_observations']
        observed.update(frame=frame, time_s=time_s)
        participant = next(item for item in observed['participants']
                           if item['actor_id'] == evidence[index]['actor_id'])
        participant.update(position_m=[x, y, 0], heading_deg=heading,
            velocity_mps=[vx, vy, 0], speed_mps=speed, body_vertices_m=body,
            blueprint='vehicle.tesla.model3')
        graph = source['graphs'][index]
        graph['attributes']['observed_evidence'] = observed
        graph['nodes'][0]['attributes'].update(vertex=[x, y, 0],
            threedbbox=body, forward=[1 if heading == 0 else 0,
            -1 if heading == -90 else 0, 0])
        poses.append({'video_frame': index, 'native_frame': frame,
            'time_s': time_s, 'subject_id': 205,
            'subject_blueprint_id': 'vehicle.tesla.model3',
            'subject_xyz_m': [x, y, 0], 'heading_deg': heading,
            'observed_speed_mps': speed,
            'source_cameras': {name: index for name in CAMERAS}})
    source['files']['road.xodr'] = open_drive()
    source['files']['trace.jsonl'] = lines(trace)
    source['files']['video_frames.jsonl'] = lines(mapping)
    source['files']['capture/evidence.jsonl'] = lines(evidence)
    source['files']['capture/native/frames.jsonl'] = lines(frames)
    source['files']['actor-poses.jsonl'] = lines(poses)
    source['files']['law-text.json'] = json.dumps({'source': 'LVMC 11.60.090',
        'text': 'Any cab, upon leaving any stand designated in accordance with the provisions of this Section, shall execute a right-hand turn, when a sign is posted giving notice of this requirement, at the first street intersection after it leaves such stand.'}) + '\n'
    source['files']['route-survey.json'] = json.dumps({
        'review_status': 'synthetic_diagnostic',
        'reviewer': 'synthetic fixture generator',
        'road_sha256': sha_text(source['files']['road.xodr']),
        'first_intersection_station_m': 80,
        'later_intersection_station_m': 130,
        'stand_notice_pixel_source': 'reference_corner.mkv',
        'stand_notice_pixel_sha256': '6f2ee6d23fc46044ddef5604518b5dbdffbfebfea32d9987e8b00a77734ed938',
        'stand_designation_review': 'unverified',
        'posted_notice_review': 'unverified',
        'taxi_license_review': 'unverified',
        'street_identity_review': 'unverified',
        'diagnostic_fixture': True}) + '\n'
    source['files']['fixture-provenance.json'] = json.dumps({
        'diagnostic_fixture': True, 'source': 'synthetic taxi route',
        'physical_acceptance_claimed': False}) + '\n'
    manifest = json.loads(source['files']['capture/manifest.json'])
    manifest.update(case_id=ASSIGNMENT + '__' + suffix, frames=600,
        sources={'road.xodr': sha_text(source['files']['road.xodr']),
                 'trace.jsonl': sha_text(source['files']['trace.jsonl'])})
    source['files']['capture/manifest.json'] = json.dumps(manifest, separators=(',', ':')) + '\n'
    path = HERE.parents[1] / ('diagnostic-' + suffix + '.json')
    path.write_text(json.dumps(source, separators=(',', ':'), allow_nan=False) + '\n')
    if path.stat().st_size > 2 * 1024 * 1024:
        path.unlink()
        raise ValueError('Fixture spec exceeds return file cap')
    recipe = {'format': 'worker-fixture-recipe',
        'sources': [{'path': 'diagnostic-input.json',
            'source': str(path.relative_to(ROOT)),
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}],
        'generator': {'source': str(path.relative_to(ROOT)),
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}}
    recipe_path = HERE.parents[1] / ('diagnostic-' + suffix + '-recipe.json')
    recipe_path.write_text(json.dumps(recipe, indent=2) + '\n')
    return {'case_id': ASSIGNMENT + '__' + suffix,
            'spec_bytes': path.stat().st_size,
            'spec_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'recipe_sha256': hashlib.sha256(recipe_path.read_bytes()).hexdigest()}


if __name__ == '__main__':
    print(json.dumps([build(suffix) for suffix in ('probe_01', 'probe_02')], indent=2))
