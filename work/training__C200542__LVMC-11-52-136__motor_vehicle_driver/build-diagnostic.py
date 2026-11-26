"""Generate synthetic Native-shaped aisle fixtures; no physical or legal claim."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BASE = ROOT / 'work/training__C394566__LVMC-11-48-060__motor_vehicle_driver/diagnostic-probe_01.json'
AID = HERE.name
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def lines(rows):
    return ''.join(json.dumps(row, separators=(',', ':'), allow_nan=False) + '\n' for row in rows)


def rows(text):
    return [json.loads(line) for line in text.splitlines()]


for suffix, y in (('controlled_1', -2.0), ('controlled_2', -6.0)):
    spec = json.loads(BASE.read_text())
    spec['files'] = {key: value for key, value in spec['files'].items() if key in
        ('trace.jsonl', 'video_frames.jsonl', 'capture/recorder_info.txt',
         'capture/evidence.jsonl', 'capture/native/frames.jsonl', 'capture/manifest.json')}
    from sys import path
    path.insert(0, str(HERE / 'runtime_native'))
    from layout import AISLE, BAY, ROUTE, open_drive
    spec['files']['road.xodr'] = open_drive()
    trace = rows(spec['files']['trace.jsonl'])
    mapping = rows(spec['files']['video_frames.jsonl'])
    evidence = rows(spec['files']['capture/evidence.jsonl'])
    frames = rows(spec['files']['capture/native/frames.jsonl'])
    motions = []
    for i in range(600):
        native = mapping[i]['native_frame']
        time = i / 20
        x = -20 + min(i, 118) * .2
        speed = 4 if i < 118 else 0
        body = [[x + dx, y + dy, z] for dx, dy in ((-2, -1), (-2, 1), (2, -1), (2, 1)) for z in (0, 2)]
        mapping[i].update(time_s=time, camera_native_frames={name: native for name in CAMERAS})
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
        motions.append({'native_frame': native, 'video_frame': i, 'time_s': time,
                        'body_xy_m': body, 'speed_mps': speed})
    spec['files']['trace.jsonl'] = lines(trace)
    spec['files']['video_frames.jsonl'] = lines(mapping)
    spec['files']['capture/evidence.jsonl'] = lines(evidence)
    spec['files']['capture/native/frames.jsonl'] = lines(frames)
    spec['files']['native-vehicle.jsonl'] = lines(motions)
    spec['files']['aisle-context.json'] = json.dumps({'source_kind': 'original_native',
        'cell_id': 'C200542', 'access_aisle': AISLE, 'adjacent_accessible_bay': BAY,
        'accessible_route_diagnostic_extent': ROUTE,
        'premises_public_access_reviewed': False, 'access_aisle_designation_reviewed': False,
        'parked_classification_reviewed': False}) + '\n'
    road_hash = sha(spec['files']['road.xodr'])
    spec['files']['premises-review.json'] = json.dumps({'review_status': 'synthetic_diagnostic',
        'reviewer': 'synthetic fixture generator', 'source': 'synthetic premises record',
        'road_sha256': road_hash, 'public_access': True,
        'jurisdiction_reviewed': True}) + '\n'
    spec['files']['aisle-designation-review.json'] = json.dumps({'review_status': 'synthetic_diagnostic',
        'reviewer': 'synthetic fixture generator', 'source': 'synthetic aisle designation record',
        'road_sha256': road_hash, 'official_access_aisle': True,
        'access_aisle': AISLE, 'adjacent_accessible_bay': BAY,
        'accessible_route_diagnostic_extent': ROUTE,
        'contrasting_marking_or_paving': 'synthetic diagonal stripes',
        'vehicle_ingress_egress': True, 'accessible_route_connectivity': True,
        'designation_route': 'direct_marking_and_accessible_bay',
        'conditional_11_52_135A_sign': None,
        'pixel_sha256': '6f2ee6d23fc46044ddef5604518b5dbdffbfebfea32d9987e8b00a77734ed938'}) + '\n'
    spec['files']['parking-review.json'] = json.dumps({'review_status': 'synthetic_diagnostic',
        'reviewer': 'synthetic fixture generator', 'source': 'synthetic parking activity record',
        'motion_sha256': sha(spec['files']['native-vehicle.jsonl']), 'parked': True,
        'vehicle_class': 'motor_vehicle', 'responsible_person': 'subject_driver',
        'occupancy': 'synthetic unreviewed', 'loading_purpose': 'synthetic unreviewed',
        'actual_loading_activity': 'synthetic unreviewed'}) + '\n'
    spec['files']['fixture-provenance.json'] = json.dumps({'diagnostic_fixture': True,
        'source': 'synthetic aisle source shape', 'physical_acceptance_claimed': False}) + '\n'
    spec['files']['law-text.json'] = json.dumps({'source': 'LVMC 11.52.136',
        'text': 'No person shall park a vehicle in an access aisle.'}) + '\n'
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
