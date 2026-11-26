"""Build five rail-stop source-shaped CPU diagnostics; no physical claim."""
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BASE = ROOT / 'work/training__C228131__NRS-484B-587-1__motor_vehicle_driver/diagnostic-witness_1.json'
AID = HERE.name
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
TARGETS = {'probe_1': 25, 'probe_2': 10, 'probe_3': 15,
           'probe_4': 50, 'probe_5': 50.5}
sys.path.insert(0, str(HERE))
from rail_stop_scene import open_drive


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def lines(rows):
    return ''.join(json.dumps(row, separators=(',', ':'), allow_nan=False) + '\n' for row in rows)


def rows(text):
    return [json.loads(line) for line in text.splitlines()]


def motion(i, feet):
    stop = -feet / 3.280839895013123
    if i < 150:
        x = -30 + (stop + 30) * i / 150
        speed = (stop + 30) / 7.5
    elif i < 210:
        x, speed = stop, 0.0
    elif i < 340:
        x = stop + (12 - stop) * (i - 210) / 130
        speed = (12 - stop) / 6.5
    else:
        x, speed = 12.0, 0.0
    return round(x, 5), speed


def main():
    for suffix, feet in TARGETS.items():
        spec = json.loads(BASE.read_text())
        spec['files'] = {key: value for key, value in spec['files'].items() if key in
            ('trace.jsonl', 'video_frames.jsonl', 'capture/recorder_info.txt',
             'capture/evidence.jsonl', 'capture/native/frames.jsonl', 'capture/manifest.json')}
        spec['files']['road.xodr'] = open_drive()
        trace = rows(spec['files']['trace.jsonl'])
        mapping = rows(spec['files']['video_frames.jsonl'])
        evidence = rows(spec['files']['capture/evidence.jsonl'])
        frames = rows(spec['files']['capture/native/frames.jsonl'])
        rail_trace = []
        for i in range(600):
            native = mapping[i]['native_frame']
            time = i / 20
            x, speed = motion(i, feet)
            y = -1.75
            body = [[x + dx, y + dy, z] for dx, dy in
                    ((-2, -.9), (-2, .9), (2, -.9), (2, .9)) for z in (0, 2)]
            cameras = {name: native for name in CAMERAS}
            mapping[i].update(time_s=time, camera_native_frames=cameras)
            trace[i].update(frame=native, time_s=time,
                            position={'x': x, 'y': y, 'z': 0},
                            position_m=[x, y, 0], speed_mps=speed,
                            speed_mph=speed * 2.2369362921,
                            velocity_mps=[speed, 0, 0])
            evidence[i].update(original_frame=native, replay_frame=native,
                               recording_time_s=time, replay_simulation_time_s=time)
            evidence[i]['ego'].update(position_m=[x, y, 0], speed_mps=speed,
                                      body_vertices_m=body)
            frames[i]['simulation_time'] = time
            original = evidence[i]['original_observations']
            original.update(frame=native, time_s=time)
            subject = next(a for a in original['participants']
                           if a['actor_id'] == evidence[i]['actor_id'])
            subject.update(position_m=[x, y, 0], velocity_mps=[speed, 0, 0],
                           speed_mps=speed, body_vertices_m=body)
            graph = spec['graphs'][i]
            graph['attributes']['observed_evidence'] = original
            graph['nodes'][0]['attributes']['vertex'] = [x, y, 0]
            graph['nodes'][0]['attributes']['threedbbox'] = body
            rail_trace.append({'native_frame': native, 'video_frame': i,
                'time_s': time, 'vehicle_actor_id': 1,
                'vehicle_center_x_m': x,
                'vehicle_extent': {'front_x_m': x + 2, 'rear_x_m': x - 2,
                                   'centre_x_m': x, 'length_m': 4},
                'observed_speed_mps': speed,
                'rail_approach_visibility': 'occluded' if i < 210 else 'clear',
                'train_state': 'none_observed',
                'source_cameras': {name: i for name in CAMERAS}})
        for key, value in (('trace.jsonl', trace), ('video_frames.jsonl', mapping),
                           ('capture/evidence.jsonl', evidence),
                           ('capture/native/frames.jsonl', frames),
                           ('rail-trace.jsonl', rail_trace)):
            spec['files'][key] = lines(value)
        spec['files']['rail-inventory.json'] = json.dumps({
            'source_kind': 'native_saved_sample', 'cell_id': 'C25835',
            'road_survey': [{'x_m': x, 'road_id': 25835, 'lane_id': -1}
                            for x in (-65, -25, -15, 0, 2)],
            'vehicle_actor_id': 1, 'vehicle_blueprint_id': 'vehicle.tesla.model3',
            'rail_actor_ids': [2, 3], 'rail_blueprint_ids': ['synthetic_rail_shape'] * 2,
            'rail_track_x_m': [0, 1.5], 'sign_actor_id': 4,
            'sign_blueprint_id': 'synthetic_sign_shape', 'occluder_actor_id': 5,
            'designation_reviewed': False, 'official_sign_reviewed': False,
            'physical_crossing_status_reviewed': False}) + '\n'
        spec['files']['designation-authority.txt'] = (
            'Synthetic diagnostic DOT dangerous-crossing designation shape; original administrative authority unresolved.\n')
        spec['files']['sign-authority.txt'] = (
            'Synthetic diagnostic officially erected crossing stop-sign shape; original sign authority unresolved.\n')
        common = {'review_status': 'synthetic_diagnostic',
                  'inventory_sha256': sha(spec['files']['rail-inventory.json'])}
        spec['files']['designation-review.json'] = json.dumps({**common,
            'reviewer': 'synthetic designation source probe',
            'source_sha256': sha(spec['files']['designation-authority.txt']),
            'road_sha256': sha(spec['files']['road.xodr']),
            'crossing_kind': 'highway_rail_at_grade',
            'designation_authority': 'department_of_transportation',
            'original_administrative_status': 'unresolved'}) + '\n'
        spec['files']['sign-review.json'] = json.dumps({**common,
            'reviewer': 'synthetic sign source probe',
            'source_sha256': sha(spec['files']['sign-authority.txt']),
            'overview_sha256': 'synthetic_rgb_source',
            'official_stop_sign': True,
            'sign_governs': 'rail_crossing_approach',
            'original_official_sign_status': 'unresolved'}) + '\n'
        spec['files']['occluder-review.json'] = json.dumps({**common,
            'reviewer': 'synthetic occluder source probe',
            'occluder_geometry_observed': True,
            'original_visibility_effect': 'unresolved'}) + '\n'
        spec['files']['fixture-provenance.json'] = json.dumps({
            'diagnostic_fixture': True, 'source': 'synthetic grade-crossing shape',
            'physical_acceptance_claimed': False}) + '\n'
        native_manifest = json.loads(spec['files']['capture/manifest.json'])
        native_manifest.update(case_id=AID + '__' + suffix, frames=600,
            sources={'road.xodr': sha(spec['files']['road.xodr']),
                     'trace.jsonl': sha(spec['files']['trace.jsonl'])})
        spec['files']['capture/manifest.json'] = json.dumps(native_manifest, separators=(',', ':')) + '\n'
        for video, name in zip(spec['videos'], CAMERAS):
            video['path'] = name + '.mkv'
            if name == 'overview':
                video['width'], video['height'] = 1920, 1080
        target_path = HERE / ('diagnostic-' + suffix + '.json')
        target_path.write_text(json.dumps(spec, separators=(',', ':'), allow_nan=False) + '\n')
        recipe = {'format': 'worker-fixture-recipe', 'sources': [
            {'path': 'diagnostic-input.json', 'source': str(target_path.relative_to(ROOT)),
             'sha256': sha(target_path.read_text())}],
            'generator': {'source': str(target_path.relative_to(ROOT)),
                          'sha256': sha(target_path.read_text())}}
        (HERE / ('diagnostic-' + suffix + '-recipe.json')).write_text(json.dumps(recipe, indent=2) + '\n')
        print(suffix, target_path.stat().st_size)


if __name__ == '__main__':
    main()
