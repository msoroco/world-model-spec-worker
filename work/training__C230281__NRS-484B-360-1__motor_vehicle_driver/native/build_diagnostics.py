"""Create explicit synthetic school-bus speed fixtures for exact public checks."""
import hashlib
import json
from pathlib import Path

FOLDER = Path(__file__).resolve().parent.parent
REPO = FOLDER.parents[1]
AID = FOLDER.name
VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def lines(rows):
    return ''.join(json.dumps(row, separators=(',', ':')) + '\n' for row in rows)


def write(path, value):
    path.write_text(json.dumps(value, separators=(',', ':')) + '\n')


def main():
    core = json.loads((FOLDER / 'native/diagnostic-core-template.json').read_text())
    road = FOLDER / 'native/road.xodr'
    camera_hash = sha(REPO / '.runtime-work/c230281-hash-overview.mkv')
    detail_hash = sha(REPO / '.runtime-work/c230281-hash-detail.mkv')
    for label, mph in [('53', 53), ('55', 55), ('57', 57)]:
        for candidate, shift in [('primary', 0.0)]:
            prefix = f'diagnostic-{label}-{candidate}'
            frames, motion, trace, events = [], [], [], []
            speed = mph * .44704
            for i in range(600):
                native = 1000 + i
                t = round(i * .05, 5)
                position = [round(i * speed * .05, 5), shift, .7]
                frames.append({'video_frame': i, 'carla_frame': native, 'native_frame': native,
                               'time_s': t, 'camera_native_frames': {view: native for view in VIEWS}})
                motion.append({'video_frame': i, 'native_frame': native,
                               'velocity_mps': [speed, 0, 0],
                               'source_kind': 'synthetic_native_sample'})
                trace.append({'frame': native, 'time_s': t,
                              'position': {'x': position[0], 'y': position[1], 'z': position[2]},
                              'position_m': position, 'heading_deg': 0.0,
                              'speed_mps': speed, 'speed_mph': mph,
                              'velocity_mps': [speed, 0, 0],
                              'control': {'throttle': 0, 'steer': 0, 'brake': 0,
                                          'hand_brake': False}})
                events.append({'original_frame': native, 'replay_frame': native,
                               'recording_time_s': t, 'replay_simulation_time_s': t,
                               'actor_id': 71,
                               'ego': {'position_m': position, 'heading_deg': 0.0,
                                       'speed_mps': speed,
                                       'body_vertices_m': [[position[0]-.3, shift-.22, 0],
                                                           [position[0]+.3, shift-.22, 0],
                                                           [position[0]+.3, shift+.22, 0],
                                                           [position[0]-.3, shift+.22, 0]],
                                       'speed_provenance': 'synthetic_native_sample'},
                               'world': {'weather': {'cloudiness': 0, 'precipitation': 0,
                                                    'wetness': 0, 'fog_density': 0},
                                         'road_projection': {'road_id': 1, 'section_id': 0,
                                                             'lane_id': -1,
                                                             's_m': round(50 + i * speed * .05, 5)}}})
            review = {'assignment_id': AID, 'review_kind': 'synthetic_diagnostic',
                      'reviewer': 'synthetic fixture',
                      'judged_driver_actor_id': 71,
                      'bus_driver_actor_id': 71,
                      'bus_actor_id': 71,
                      'driver_bus_join_source': 'synthetic diagnostic actor join',
                      'bus_blueprint': 'diagnostic_school_bus_asset',
                      'school_bus_confirmed': True,
                      'trip_purpose': 'transporting pupils to or from school',
                      'trip_purpose_source': 'synthetic diagnostic context',
                      'pupils_aboard': True, 'observed_pupil_count': 3,
                      'pupil_evidence_frames': [0, 300, 599],
                      'camera_sha256': {name: (camera_hash if name == 'overview' else detail_hash) for name in VIEWS}}
            sources = [{'path': 'road.xodr', 'source': f'work/{AID}/native/road.xodr',
                        'sha256': sha(road)}]
            for name, data in [('video_frames.jsonl', lines(frames)),
                               ('bus_motion.jsonl', lines(motion)),
                               ('passenger_trip_review.json', json.dumps(review, separators=(',', ':')) + '\n')]:
                source = FOLDER / f'{prefix}-{name}'
                source.write_text(data)
                sources.append({'path': name, 'source': f'work/{AID}/{source.name}',
                                'sha256': sha(source)})
            trace_text = lines(trace)
            manifest = {'frames': 600, 'extraction_confirmed': True,
                        'synthetic_diagnostic': True, 'case_id': AID + '__' + label,
                        'required_observations': [],
                        'sources': {'road.xodr': sha(road),
                                    'trace.jsonl': hashlib.sha256(trace_text.encode()).hexdigest()}}
            spec = {'files': {'trace.jsonl': trace_text,
                              'capture/evidence.jsonl': lines(events),
                              'capture/native/frames.jsonl': core['files']['capture/native/frames.jsonl'],
                              'capture/manifest.json': json.dumps(manifest) + '\n',
                              'capture/recorder_info.txt': 'Synthetic CPU diagnostic; no CARLA recording.\nCreate 71: vehicle.school_bus (0)\n'},
                    'graphs': core['graphs'],
                    'videos': [{'path': name + '.mkv', 'frames': 600,
                                'width': 1920 if name == 'overview' else 1280,
                                'height': 1080 if name == 'overview' else 720, 'fps': 20,
                                'color': 'black'} for name in VIEWS]}
            spec_path = FOLDER / (prefix + '.json')
            write(spec_path, spec)
            recipe = {'format': 'worker-fixture-recipe', 'sources': sources,
                      'generator': {'source': f'work/{AID}/{spec_path.name}',
                                    'sha256': sha(spec_path)}}
            recipe_path = FOLDER / (prefix + '-recipe.json')
            write(recipe_path, recipe)
            print(json.dumps({'case': label, 'candidate': candidate,
                              'recipe_sha256': sha(recipe_path)}))


if __name__ == '__main__':
    main()
