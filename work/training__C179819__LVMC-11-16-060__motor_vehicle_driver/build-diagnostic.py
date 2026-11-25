"""Generate source-shaped software fixtures; they are not Native recordings."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BASE = ROOT / 'work/training__C394566__LVMC-11-48-060__motor_vehicle_driver/diagnostic-probe_01.json'
ASSIGNMENT = HERE.name
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def lines(rows):
    return ''.join(json.dumps(row, separators=(',', ':'), allow_nan=False) + '\n' for row in rows)


def rows(text):
    return [json.loads(line) for line in text.splitlines()]


for suffix, mph in (('probe_1', 20), ('probe_2', 25), ('probe_3', 30), ('posted_35', 30)):
    spec = json.loads(BASE.read_text())
    spec['files'] = {key: value for key, value in spec['files'].items() if key in
        ('road.xodr', 'trace.jsonl', 'video_frames.jsonl', 'capture/recorder_info.txt',
         'capture/evidence.jsonl', 'capture/native/frames.jsonl', 'capture/manifest.json')}
    source_trace = rows(spec['files']['trace.jsonl'])
    mapping = rows(spec['files']['video_frames.jsonl'])
    evidence = rows(spec['files']['capture/evidence.jsonl'])
    frames = rows(spec['files']['capture/native/frames.jsonl'])
    poses = []
    speed = mph * .44704
    for index in range(600):
        frame = mapping[index]['native_frame']
        time = index / 20
        mapping[index]['time_s'] = time
        position = min(500, speed * index / 20)
        source_trace[index].update(frame=frame, time_s=time,
            position={'x': position, 'y': 0, 'z': 0}, position_m=[position, 0, 0],
            speed_mps=speed, speed_mph=mph, velocity_mps=[speed, 0, 0])
        evidence[index].update(original_frame=frame, replay_frame=frame,
                               recording_time_s=time, replay_simulation_time_s=time)
        frames[index]['simulation_time'] = time
        body = [[position + dx, dy, z]
                for dx, dy in ((-2, -1), (-2, 1), (2, -1), (2, 1)) for z in (0, 2)]
        evidence[index]['ego'].update(position_m=[position, 0, 0], speed_mps=speed,
                                      heading_deg=0, body_vertices_m=body)
        graph = spec['graphs'][index]
        observed = evidence[index].get('original_observations')
        if observed:
            observed.update(frame=frame, time_s=time)
            subject = next(a for a in observed['participants'] if a['actor_id'] == evidence[index]['actor_id'])
            subject.update(position_m=[position, 0, 0], velocity_mps=[speed, 0, 0],
                           speed_mps=speed, heading_deg=0,
                           body_vertices_m=body)
            graph['attributes']['observed_evidence'] = observed
        graph['nodes'][0]['attributes']['vertex'] = [position, 0, 0]
        graph['nodes'][0]['attributes']['threedbbox'] = subject['body_vertices_m']
        poses.append({'video_frame': index, 'native_frame': frame, 'time_s': time,
                      'route_position_m': position, 'observed_speed_mps': speed,
                      'source_cameras': {name: index for name in CAMERAS}})
    spec['files']['trace.jsonl'] = lines(source_trace)
    spec['files']['video_frames.jsonl'] = lines(mapping)
    spec['files']['capture/evidence.jsonl'] = lines(evidence)
    spec['files']['capture/native/frames.jsonl'] = lines(frames)
    spec['files']['actor-poses.jsonl'] = lines(poses)
    road_hash = sha(spec['files']['road.xodr'])
    spec['files']['street-status.json'] = json.dumps({'source_kind': 'independent_street_status',
        'review_status': 'synthetic_diagnostic', 'reviewer': 'synthetic fixture generator',
        'street_status': 'city_street',
        'road_sha256': road_hash, 'synthetic_diagnostic': True}) + '\n'
    spec['files']['sign-survey.json'] = json.dumps({'source_kind': 'native_complete_sign_survey',
        'review_status': 'synthetic_diagnostic', 'reviewer': 'synthetic fixture generator',
        'road_sha256': road_hash,
        'surveyed_route_interval_m': [0, 500], 'survey_complete_both_directions': True,
        'pixel_source': 'reference_corner.mkv',
        'applicable_posted_signs': [{'governs_from_m': 100, 'governs_to_m': 500,
            'limit_mph': 35 if suffix == 'posted_35' else 25,
            'pixel_sha256': '6f2ee6d23fc46044ddef5604518b5dbdffbfebfea32d9987e8b00a77734ed938'}],
        'synthetic_diagnostic': True}) + '\n'
    spec['files']['fixture-provenance.json'] = json.dumps({'diagnostic_fixture': True,
        'source': 'synthetic C179819 speed and sign shape', 'physical_acceptance_claimed': False}) + '\n'
    spec['files']['law-text.json'] = json.dumps({'source': 'LVMC 11.16.060',
        'text': 'The prima facie speed limit is twenty-five miles per hour on all streets and highways unless a different speed limit is posted as set forth in this Title.'}) + '\n'
    manifest = json.loads(spec['files']['capture/manifest.json'])
    manifest.update(case_id=ASSIGNMENT + '__' + suffix, frames=600,
                    sources={'road.xodr': road_hash, 'trace.jsonl': sha(spec['files']['trace.jsonl'])})
    spec['files']['capture/manifest.json'] = json.dumps(manifest, separators=(',', ':')) + '\n'
    path = HERE / ('diagnostic-' + suffix + '.json')
    path.write_text(json.dumps(spec, separators=(',', ':'), allow_nan=False) + '\n')
    recipe = {'format': 'worker-fixture-recipe',
        'sources': [{'path': 'diagnostic-input.json', 'source': str(path.relative_to(ROOT)),
                     'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}],
        'generator': {'source': str(path.relative_to(ROOT)),
                      'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}}
    (HERE / ('diagnostic-' + suffix + '-recipe.json')).write_text(json.dumps(recipe, indent=2) + '\n')
    print(suffix, path.stat().st_size)
