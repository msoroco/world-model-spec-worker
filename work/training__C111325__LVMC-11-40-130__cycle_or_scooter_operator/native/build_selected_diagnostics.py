"""Source-hashed synthetic bicycle diagnostics; never evidence of actual CARLA execution."""
import hashlib
import json
from pathlib import Path
from speed import requested

HERE = Path(__file__).resolve().parent
FOLDER = HERE.parent
REPO = FOLDER.parents[1]
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def lines(rows):
    return ''.join(json.dumps(row, separators=(',', ':'))+'\n' for row in rows)


def write(path, value):
    path.write_text(json.dumps(value, separators=(',', ':'), ensure_ascii=False)+'\n')
    if path.stat().st_size > 2*1024*1024:
        raise ValueError('Returned file too large: '+str(path))


def build(condition):
    source = requested(condition)
    trace_source, mapping, trace, evidence, frames, graphs = [], [], [], [], [], []
    for index, item in enumerate(source):
        x, y = item['bicycle_center_xy_m']
        previous_x = source[index-1]['bicycle_center_xy_m'][0] if index else x
        frame = 1000+index
        time_s = item['time_s']
        speed = round((x-previous_x)*20, 6)
        row = {'sample_index': index, 'native_frame': frame, 'time_s': time_s,
               'source_kind': 'synthetic_native_mock', 'blueprint': 'vehicle.bh.crossbike',
               'actor_id': 71, 'condition': condition,
               'fixed_conditions_id': 'c111325-dry-clear-stop-v1',
               'center_xy_m': [x, y], 'velocity_xy_mps': [speed, 0.0],
               'legal_verdict': None}
        trace_source.append(row)
        mapping.append({'video_frame': index, 'carla_frame': frame,
                        'native_frame': frame, 'time_s': time_s,
                        'camera_native_frames': {name: frame for name in CAMERAS}})
        trace.append({'frame': frame, 'time_s': time_s,
                      'position': {'x': x, 'y': y, 'z': .7},
                      'position_m': [x, y, .7], 'heading_deg': 0.0,
                      'speed_mps': speed, 'speed_mph': speed/.44704,
                      'velocity_mps': [speed, 0.0, 0.0],
                      'control': {'throttle': 0, 'steer': 0, 'brake': 0,
                                  'hand_brake': False},
                      'bicycle_source': {'sample_index': index, 'native_frame': frame}})
        vertices = [[x-.3,y-.25,0],[x+.3,y-.25,0],[x+.3,y+.25,0],[x-.3,y+.25,0]]
        evidence.append({'original_frame': frame, 'replay_frame': frame,
                         'recording_time_s': time_s, 'replay_simulation_time_s': time_s,
                         'actor_id': 71,
                         'ego': {'position_m': [x,y,.7], 'heading_deg': 0.0,
                                 'speed_mps': speed, 'body_vertices_m': vertices,
                                 'speed_provenance': 'synthetic_native_sample'},
                         'world': {'weather': {'cloudiness': 0, 'precipitation': 0,
                                               'wetness': 0, 'fog_density': 0},
                                   'road_projection': {'road_id': 1, 'section_id': 0,
                                                       'lane_id': -1, 's_m': x+50}}})
        graph = f'graphs/base/{frame:08d}.adapter.json'
        frames.append({'abstract': graph, 'adapter_graph': graph,
                       'base': graph, 'edges': 0, 'frame': frame, 'nodes': 0,
                       'simulation_time': time_s, 'time_s': time_s,
                       'synthetic_diagnostic': True})
        graphs.append({'path': 'capture/native/'+graph,
                       'attributes': {'frame': frame}, 'nodes': [], 'edges': []})
    context = {'source_kind': 'synthetic_native_mock', 'cell_id': 'C111325',
               'law_id': 'LVMC-11-40-130', 'actor': 'cycle_or_scooter_operator',
               'bicycle_blueprint': 'vehicle.bh.crossbike',
               'stop_sign_governs_route': True, 'approach_lane_verified': True,
               'municipal_jurisdiction_review_pending': True,
               'fixed_conditions_id': 'c111325-dry-clear-stop-v1',
               'legal_prudence_verdict': None,
               'pedestrian_count': 0, 'clear_weather': True, 'wetness': 0}
    source_path = FOLDER/('diagnostic-bicycle-'+condition+'.jsonl')
    context_path = FOLDER/('diagnostic-context-'+condition+'.json')
    source_path.write_text(lines(trace_source))
    write(context_path, context)
    spec = {'files': {'video_frames.jsonl': lines(mapping),
                      'trace.jsonl': lines(trace),
                      'capture/evidence.jsonl': lines(evidence),
                      'capture/native/frames.jsonl': lines(frames),
                      'capture/manifest.json': json.dumps({
                          'frames': 600, 'extraction_confirmed': True,
                          'synthetic_diagnostic': True,
                          'case_id': FOLDER.name+'__selected_01149d06__'+condition,
                          'sources': {'road.xodr': sha(HERE/'road.xodr'),
                                      'trace.jsonl': hashlib.sha256(lines(trace).encode()).hexdigest()},
                          'required_observations': []}),
                      'capture/recorder_info.txt':
                          'Synthetic CPU diagnostic; no CARLA recording.\nCreate 71: vehicle.bh.crossbike (0)\n'},
            'graphs': graphs,
            'videos': [{'path': name+'.mkv', 'frames': 600,
                        'width': 1920 if name=='overview' else 1280,
                        'height': 1080 if name=='overview' else 720,
                        'fps': 20, 'color': 'black'} for name in CAMERAS]}
    spec_path = FOLDER/('diagnostic-'+condition+'.json')
    write(spec_path, spec)
    recipe = {'format': 'worker-fixture-recipe',
              'sources': [{'path': target, 'source': str(path.relative_to(REPO)),
                           'sha256': sha(path)} for target, path in (
                               ('native-bicycle-trace.jsonl', source_path),
                               ('context.json', context_path))],
              'generator': {'source': str(spec_path.relative_to(REPO)),
                            'sha256': sha(spec_path)}}
    recipe_path = FOLDER/('diagnostic-'+condition+'-recipe.json')
    write(recipe_path, recipe)
    return {'condition': condition, 'source_sha256': sha(source_path),
            'recipe_sha256': sha(recipe_path), 'spec_bytes': spec_path.stat().st_size}


if __name__ == '__main__':
    print(json.dumps([build(c) for c in ('condition_a', 'condition_b')]))
