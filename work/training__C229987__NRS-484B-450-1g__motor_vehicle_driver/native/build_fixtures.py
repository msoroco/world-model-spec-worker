"""Create source-shaped 600-frame diagnostic recipes for three requested stops."""
import hashlib
import json
from pathlib import Path

from road import SIGNAL_STATION_M, open_drive

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
AID = ROOT.name
FRAMES = 600
RATE = 20
TARGETS = {'25': 25.0, '30': 30.0, '35': 35.0}


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value if isinstance(value, str) else json.dumps(value, indent=2, sort_keys=True)+'\n')


def lines(rows):
    return ''.join(json.dumps(row, separators=(',', ':'), sort_keys=True)+'\n' for row in rows)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def vertices(x, y):
    return [[x+dx, y+dy, z] for dx in (-2.25, 2.25)
            for dy in (-.9, .9) for z in (0, 1.5)]


def make(suffix, feet):
    root = HERE/'diagnostic'/suffix
    sources = root/'sources'
    case = AID+'__'+suffix
    front_gap = feet*.3048
    centre_x = SIGNAL_STATION_M-front_gap-2.25
    frame_map, trace, evidence, raw_frames, native_frames, graphs = [], [], [], [], [], []
    for index in range(FRAMES):
        t = round(index/RATE, 6)
        x, y = centre_x, -1.85
        polygon = [{'x_m': x+dx, 'y_m': y+dy}
                   for dx in (-2.25, 2.25) for dy in (-.9, .9)]
        frame_map.append({'video_frame': index, 'native_frame': index,
                          'carla_frame': index, 'time_s': t,
                          'camera_native_frames': {name: index for name in (
                              'overview', 'approach', 'reference_corner', 'driver_reference')}})
        raw_frames.append({'time_s': t, 'speed_mps': 0.0,
                           'vehicle_footprint_xy_m': polygon,
                           'native_frame': index, 'signal_state': 'Green',
                           'signal_actor_id': 401, 'ego_actor_id': 10,
                           'road_id': 1, 'lane_id': -1,
                           'requested_front_gap_m': front_gap})
        trace.append({'frame': index, 'time_s': t, 'position_m': [x, y, .5],
                      'position': {'x': x, 'y': y, 'z': .5},
                      'velocity_mps': [0, 0, 0], 'speed_mps': 0,
                      'speed_mph': 0,
                      'heading_deg': 0, 'control': {'throttle': 0, 'brake': 1,
                                                   'hand_brake': True}})
        evidence.append({'actor_id': 10, 'original_frame': index,
                         'replay_frame': index, 'recording_time_s': t,
                         'replay_simulation_time_s': t,
                         'ego': {'position_m': [x, y, .5], 'body_vertices_m': vertices(x, y),
                                 'heading_deg': 0, 'speed_mps': 0,
                                 'speed_provenance': 'synthetic_native_sample',
                                 'synthetic_diagnostic': True},
                         'other_actors': [],
                         'world': {'road_projection': {'road_id': 1, 'lane_id': -1,
                                                       'section_id': 0, 's_m': x},
                                   'weather': {'cloudiness': 0, 'fog_density': 0,
                                               'precipitation': 0, 'wetness': 0}}})
        name = f'capture/native/graphs/base/{index:08d}.adapter.json'
        native_frames.append({'frame': index, 'simulation_time': t,
                              'adapter_graph': f'graphs/base/{index:08d}.adapter.json',
                              'base': f'graphs/base/{index:08d}.adapter.json',
                              'nodes': 1, 'edges': 0})
        graphs.append({'path': name,
                       'attributes': {'frame': index, 'simulation_time_s': t,
                                      'source': 'C229987 signal approach CPU diagnostic',
                                      'synthetic_diagnostic': True},
                       'nodes': [{'id': 'ego', 'attributes': {'entity_id': 10,
                                                            'sem_class': 'ego',
                                                            'vertex': [x, y, .5],
                                                            'forward': [1, 0, 0],
                                                            'threedbbox': vertices(x, y)}}],
                       'edges': []})
    survey = {'case_id': case, 'review_kind': 'synthetic_diagnostic',
              'highway_status': None, 'official_signal_status': None,
              'signal_governs_selected_lane_native': True,
              'signal_actor_id': 401, 'signal_opendrive_id': '401',
              'halt_purpose': 'synthetic voluntary stop request',
              'other_traffic_conflict': None, 'applicable_law_direction': None,
              'officer_direction': None, 'device_direction': None,
              'independent_reviewer': None}
    raw = {'assignment_id': AID, 'source_kind': 'native_raw_capture',
           'road_geometry': {'approach_origin': {'x_m': 0, 'y_m': 0},
                             'approach_tangent': {'x_m': 1, 'y_m': 0}},
           'signal': {'roadside_position': {'x_m': SIGNAL_STATION_M, 'y_m': -4.2},
                      'actor_id': 401, 'opendrive_id': '401', 'governs_lane': True},
           'geometry_uncertainty_m': .05,
           'context_sources': {key: 'context-survey.json' for key in (
               'highway_status_source', 'official_signal_status_source',
               'roadside_placement_source', 'governed_movement_source',
               'signal_indication_source', 'halt_purpose_source',
               'other_traffic_source', 'applicable_law_source',
               'officer_direction_source', 'device_direction_source')},
           'frames': raw_frames}
    for name, value in {
        'signal_raw.json': raw, 'context-survey.json': survey,
        'video_frames.jsonl': lines(frame_map), 'trace.jsonl': lines(trace),
        'capture/evidence.jsonl': lines(evidence), 'road.xodr': open_drive()+'\n',
    }.items():
        write(sources/name, value)
    write(sources/'capture/manifest.json', {
        'extraction_confirmed': True, 'frames': FRAMES,
        'synthetic_diagnostic': True,
        'sources': {'road.xodr': sha(sources/'road.xodr'),
                    'trace.jsonl': sha(sources/'trace.jsonl')}})
    spec = {'files': {
        'capture/native/frames.jsonl': lines(native_frames),
        'capture/recorder_info.txt': 'Synthetic CPU diagnostic; no Native recording or physical acceptance.\nCreate 10: vehicle.tesla.model3 (0)\n',
    }, 'graphs': graphs,
        'videos': [{'path': name+'.mkv', 'frames': FRAMES,
                    'width': 1920 if name == 'overview' else 1280,
                    'height': 1080 if name == 'overview' else 720,
                    'fps': RATE, 'color': 'black'} for name in (
                        'overview', 'approach', 'reference_corner', 'driver_reference')]}
    spec_path = root/'fixture-spec.json'
    write(spec_path, spec)
    repo = Path.cwd()
    recipe = {'format': 'worker-fixture-recipe',
              'generator': {'source': str(spec_path.relative_to(repo)),
                            'sha256': sha(spec_path)},
              'sources': [{'path': str(path.relative_to(sources)),
                           'source': str(path.relative_to(repo)), 'sha256': sha(path)}
                          for path in sorted(sources.rglob('*')) if path.is_file()]}
    write(root/'fixture-recipe.json', recipe)
    return {'case_id': case, 'recipe_sha256': sha(root/'fixture-recipe.json'),
            'source_files': len(recipe['sources'])}


if __name__ == '__main__':
    print(json.dumps([make(suffix, feet) for suffix, feet in TARGETS.items()]))
