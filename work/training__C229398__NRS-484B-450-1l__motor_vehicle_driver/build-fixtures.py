"""Write source-shaped 600-frame two-vehicle diagnostics, never physical evidence."""
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
AID = HERE.name
BASE = ROOT / 'work/training__C135709__NRS-484B-450-1o__motor_vehicle_driver/diagnostic-false.json'
CASES = ('clear', 'stop', 'stand', 'park', 'traffic_conflict',
         'law_direction', 'police_direction', 'device_direction')
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
sys.path.insert(0, str(HERE / 'native'))
from geometry import CURB_START, CURB_END, open_drive


def sha(data):
    return hashlib.sha256(data.encode()).hexdigest()


def lines(rows):
    return ''.join(json.dumps(row, separators=(',', ':'), allow_nan=False) + '\n' for row in rows)


def rows(value):
    return [json.loads(line) for line in value.splitlines()]


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value)


def box(x, y, z=0):
    return [[x + dx, y + dy] for dx, dy in
            ((-2.25, -1), (-2.25, 1), (2.25, 1), (2.25, -1))]


def main():
    base = json.loads(BASE.read_text())
    for suffix in CASES:
        target = 12.0 if suffix == 'clear' else 0.0
        activity = 'neutral' if suffix == 'clear' else suffix if suffix in ('stop', 'stand', 'park') else 'park'
        files = {key: value for key, value in base['files'].items() if key in
            ('trace.jsonl', 'video_frames.jsonl', 'capture/recorder_info.txt',
             'capture/evidence.jsonl', 'capture/native/frames.jsonl',
             'capture/manifest.json')}
        files['road.xodr'] = open_drive()
        trace = rows(files['trace.jsonl'])
        mapping = rows(files['video_frames.jsonl'])
        evidence = rows(files['capture/evidence.jsonl'])
        frames = rows(files['capture/native/frames.jsonl'])
        poses, bodies = [], []
        for i in range(600):
            native = mapping[i]['native_frame']
            time = i / 20
            x = -80 + (target + 80) * min(i, 120) / 120
            speed = (target + 80) / 6 if i < 120 else 0.0
            y = -1.75
            corners = box(x, y)
            vertices = [[p[0], p[1], z] for p in corners for z in (0, 2)]
            camera_frames = {name: native for name in CAMERAS}
            mapping[i].update(time_s=time, camera_native_frames=camera_frames)
            trace[i].update(frame=native, time_s=time,
                position={'x': x, 'y': y, 'z': 0}, position_m=[x, y, 0],
                speed_mps=speed, speed_mph=speed * 2.2369362921,
                velocity_mps=[speed, 0, 0],
                control={'phase': 'approach' if i < 120 else 'hold'})
            evidence[i].update(original_frame=native, replay_frame=native,
                recording_time_s=time, replay_simulation_time_s=time)
            evidence[i]['ego'].update(position_m=[x, y, 0], speed_mps=speed,
                body_vertices_m=vertices)
            frames[i]['simulation_time'] = time
            original = evidence[i]['original_observations']
            original.update(frame=native, time_s=time)
            subject = next(a for a in original['participants']
                           if a['actor_id'] == evidence[i]['actor_id'])
            subject.update(position_m=[x, y, 0], velocity_mps=[speed, 0, 0],
                speed_mps=speed, body_vertices_m=vertices)
            poses.append({'native_frame': native, 'video_frame': i,
                'time_s': time, 'subject_actor_id': 205, 'curbside_actor_id': 206,
                'subject_xyz_m': [x, y, 0], 'curbside_xyz_m': [0, -5.2, 0],
                'observed_speed_mps': speed,
                'requested_control': {'phase': 'approach' if i < 120 else 'hold'},
                'requested_activity': activity, 'camera_native_frames': camera_frames,
                'legal_outcome_verified': False})
            bodies.append({'source_kind': 'original_actor_body_footprints',
                'frame': i, 'native_frame': native, 'time_s': time,
                'actors': {'ego': {'actor_id': 205, 'footprint_corners_xy_m': corners},
                           'curbside': {'actor_id': 206,
                                       'footprint_corners_xy_m': box(0, -5.2)}}})
        for name, value in (('trace.jsonl', trace), ('video_frames.jsonl', mapping),
                            ('capture/evidence.jsonl', evidence),
                            ('capture/native/frames.jsonl', frames),
                            ('vehicle-poses.jsonl', poses),
                            ('body-footprints.jsonl', bodies)):
            files[name] = lines(value)
        geometry = {'source_kind': 'surveyed_map_geometry', 'cell_id': 'C229398',
            'curb_start_xy_m': CURB_START, 'curb_end_xy_m': CURB_END,
            'road_interior_normal_sign': 1, 'native_lane_survey': [
                {'road_id': 1, 'lane_id': -1}, {'road_id': 1, 'lane_id': -2}],
            'highway_dedication_verified': False,
            'synthetic_diagnostic': True}
        files['map-geometry.json'] = json.dumps(geometry) + '\n'
        files['highway-review.json'] = json.dumps({
            'review_status': 'synthetic_diagnostic', 'reviewer': 'synthetic fixture',
            'source': 'synthetic road/curb shape', 'road_sha256': sha(files['road.xodr']),
            'map_sha256': sha(files['map-geometry.json']),
            'highway_authority_source': 'synthetic only; original authority pending',
            'curb_authority_source': 'synthetic only; original curb survey pending'}) + '\n'
        files['activity-review.json'] = json.dumps({
            'review_status': 'synthetic_diagnostic', 'reviewer': 'synthetic fixture',
            'source': 'synthetic actor activity shape',
            'body_sha256': sha(files['body-footprints.jsonl']),
            'activity': activity, 'purpose_source': 'synthetic request only; original purpose pending'}) + '\n'
        files['exception-review.json'] = json.dumps({
            'review_status': 'synthetic_diagnostic', 'reviewer': 'synthetic fixture',
            'source': 'synthetic exception context shape',
            'body_sha256': sha(files['body-footprints.jsonl']),
            'traffic_conflict_source': 'synthetic ' + suffix + '; original necessity pending',
            'law_compliance_source': 'synthetic ' + suffix + '; applicable law pending',
            'police_direction_source': 'synthetic ' + suffix + '; original officer direction pending',
            'device_direction_source': 'synthetic ' + suffix + '; original device authority pending'}) + '\n'
        files['pixel-review.json'] = json.dumps({
            'review_status': 'synthetic_diagnostic', 'reviewer': 'synthetic fixture',
            'source': 'synthetic four-camera pixel shape',
            'overview_sha256': 'synthetic_four_view_source',
            'actual_pixels_verified': False}) + '\n'
        files['fixture-provenance.json'] = json.dumps({
            'diagnostic_fixture': True, 'source': 'synthetic curbside two-vehicle shape',
            'physical_acceptance_claimed': False}) + '\n'
        capture_manifest = json.loads(files['capture/manifest.json'])
        capture_manifest.update(case_id=AID + '__' + suffix, frames=600,
            sources={'road.xodr': sha(files['road.xodr']),
                     'trace.jsonl': sha(files['trace.jsonl'])})
        files['capture/manifest.json'] = json.dumps(capture_manifest, separators=(',', ':')) + '\n'
        source_root = HERE / 'diagnostic-source' / suffix
        sources = []
        for name, value in files.items():
            path = source_root / name
            write(path, value)
            sources.append({'path': name, 'source': str(path.relative_to(ROOT)),
                            'sha256': sha(value)})
        generator = {'files': {},
            'graphs': [{'path': 'capture/native/graphs/base/%08d.adapter.json' % (1000 + i),
                'attributes': {'frame': 1000 + i,
                               'observed_evidence': evidence[i]['original_observations']},
                'nodes': [], 'edges': []}
                for i in range(600)],
            'videos': [{'path': name + '.mkv', 'frames': 600, 'fps': 20,
                        'width': 1920 if name == 'overview' else 1280,
                        'height': 1080 if name == 'overview' else 720,
                        'color': 'blue' if suffix == 'clear' else 'red'}
                       for name in CAMERAS]}
        generator_path = HERE / ('diagnostic-generator-' + suffix + '.json')
        write(generator_path, json.dumps(generator, separators=(',', ':')) + '\n')
        recipe = {'format': 'worker-fixture-recipe', 'sources': sources,
            'generator': {'source': str(generator_path.relative_to(ROOT)),
                          'sha256': sha(generator_path.read_text())}}
        write(HERE / ('diagnostic-' + suffix + '-recipe.json'),
              json.dumps(recipe, separators=(',', ':')) + '\n')
        print(suffix, 'source files', len(sources), 'largest bytes',
              max(len(v.encode()) for v in files.values()), flush=True)


if __name__ == '__main__':
    main()
