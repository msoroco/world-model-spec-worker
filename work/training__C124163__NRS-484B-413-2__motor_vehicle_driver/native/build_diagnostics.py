"""Six source-shaped synthetic fixtures for public CPU compatibility, never physical evidence."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NATIVE = ROOT/'native'
VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')
REQUESTS = {'other_long': 100.0, 'other_at': 91.44, 'other_short': 70.0,
            'district_long': 35.2, 'district_at': 30.48, 'district_short': 20.0}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, separators=(',', ':'), ensure_ascii=False)+'\n')


def lines(rows):
    return ''.join(json.dumps(row, separators=(',', ':'))+'\n' for row in rows)


def main():
    core = json.loads((NATIVE/'diagnostic-core-template.json').read_text())
    road = NATIVE/'road.xodr'
    for condition, requested in REQUESTS.items():
        prefix = 'diagnostic-'+condition+'-primary'
        frames, signal, trace, events = [], [], [], []
        start = 120.0-requested
        district = 'other_area' if condition.startswith('other_') else 'business_or_residential'
        weather = 'clear' if district == 'other_area' else 'rain'
        for i in range(600):
            native = 1000+i
            time = round(i/20, 5)
            odometer = round(i*.4, 5)
            position = [odometer, 0, .7]
            frames.append({'video_frame': i, 'carla_frame': native,
                'native_frame': native, 'time_s': time,
                'camera_native_frames': {view: native for view in VIEWS}})
            signal.append({'video_frame': i, 'native_frame': native,
                'time_s': time, 'odometer_native_m': odometer,
                'left_blinker_state': odometer >= start,
                'signal_requested': odometer >= start,
                'course_change_requested': odometer >= 120.0,
                'yaw_deg': 0 if i < 300 else (i-300)*.08,
                'position_m': position, 'velocity_mps': [8, 0, 0],
                'signal_visible_pixels_reviewed': False,
                'source_kind': 'synthetic_native_sample'})
            trace.append({'frame': native, 'time_s': time,
                'position': {'x': position[0], 'y': position[1], 'z': position[2]},
                'position_m': position, 'heading_deg': 0,
                'speed_mps': 8, 'speed_mph': 8/.44704,
                'velocity_mps': [8, 0, 0],
                'control': {'throttle': 0, 'steer': 0, 'brake': 0,
                            'hand_brake': False}})
            events.append({'original_frame': native, 'replay_frame': native,
                'recording_time_s': time, 'replay_simulation_time_s': time,
                'actor_id': 71,
                'ego': {'position_m': position, 'heading_deg': 0,
                        'speed_mps': 8,
                        'body_vertices_m': [[odometer-.3, -.22, 0],
                                            [odometer+.3, -.22, 0],
                                            [odometer+.3, .22, 0],
                                            [odometer-.3, .22, 0]],
                        'speed_provenance': 'synthetic_native_sample'},
                'world': {'weather': {'cloudiness': 70 if weather == 'rain' else 0,
                                     'precipitation': 40 if weather == 'rain' else 0,
                                     'wetness': 40 if weather == 'rain' else 0,
                                     'fog_density': 0},
                          'road_projection': {'road_id': 1, 'section_id': 0,
                                              'lane_id': -1, 's_m': 50+odometer}}})
        context = {'assignment_id': ROOT.name, 'review_kind': 'synthetic_diagnostic',
            'district_class_requested': district, 'weather_requested': weather,
            'district_class_originally_verified': False,
            'weather_originally_verified': False,
            'turn_route_originally_verified': False,
            'visible_signal_originally_verified': False,
            'legal_verdict': None}
        sources = [{'path': 'road.xodr', 'source': f'work/{ROOT.name}/native/road.xodr',
                    'sha256': sha(road)}]
        for name, content in [('video_frames.jsonl', lines(frames)),
                              ('signal-source.jsonl', lines(signal)),
                              ('context-review.json', json.dumps(context,separators=(',', ':'))+'\n')]:
            path = ROOT/(prefix+'-'+name)
            path.write_text(content)
            sources.append({'path': name, 'source': f'work/{ROOT.name}/{path.name}',
                            'sha256': sha(path)})
        trace_text = lines(trace)
        manifest = {'frames': 600, 'extraction_confirmed': True,
            'synthetic_diagnostic': True, 'case_id': ROOT.name+'__'+condition,
            'required_observations': [],
            'sources': {'road.xodr': sha(road),
                        'trace.jsonl': hashlib.sha256(trace_text.encode()).hexdigest()}}
        spec = {'files': {'trace.jsonl': trace_text,
            'capture/evidence.jsonl': lines(events),
            'capture/native/frames.jsonl': core['files']['capture/native/frames.jsonl'],
            'capture/manifest.json': json.dumps(manifest)+'\n',
            'capture/recorder_info.txt': 'Synthetic CPU diagnostic; no CARLA recording.\nCreate 71: vehicle.tesla.model3 (0)\n'},
            'graphs': core['graphs'],
            'videos': [{'path': name+'.mkv', 'frames': 600,
                        'width': 1920 if name == 'overview' else 1280,
                        'height': 1080 if name == 'overview' else 720,
                        'fps': 20, 'color': 'black'} for name in VIEWS]}
        spec_path = ROOT/(prefix+'.json')
        write(spec_path, spec)
        recipe = {'format': 'worker-fixture-recipe', 'sources': sources,
            'generator': {'source': f'work/{ROOT.name}/{spec_path.name}',
                          'sha256': sha(spec_path)}}
        recipe_path = ROOT/(prefix+'-recipe.json')
        write(recipe_path, recipe)
        print(json.dumps({'condition': condition, 'recipe_sha256': sha(recipe_path)}))


if __name__ == '__main__':
    main()
