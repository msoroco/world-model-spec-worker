"""Retain source-shaped synthetic crossroads fixtures for CPU proofs only."""
import hashlib
import json
from pathlib import Path
from saved import make_raw
from build_selected import CASES, CANDIDATES, HERE, PACKAGE, REPO, put, sha


def lines(path, values):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(v, separators=(',', ':'), allow_nan=False) + '\n'
                            for v in values))


def build(suffix, candidate):
    draft = HERE / 'drafts' / suffix / candidate
    root = HERE / 'selected' / suffix / candidate
    sources = root / 'sources'
    sources.mkdir(parents=True, exist_ok=True)
    (sources / 'road.xodr').write_bytes((draft / 'crossroads.xodr').read_bytes())
    raw = make_raw(draft)
    put(sources / 'actor-history.json', raw)
    put(sources / 'road-context.json', {
        'source_kind': 'synthetic_cpu_diagnostic',
        'ego_highway_roads': [250, 251, 252],
        'other_highway_roads': [253, 254, 255],
        'ego_entry_boundary_x_m': -20, 'other_entry_boundary_y_m': -20,
        'official_device_governance_verified': False,
        'opposite_direction_left_turn_exclusion_resolved': False,
        'subsection_4_exception_resolved': False,
        'legal_verdict': None})
    trace, crossing, frames, evidence, graphs, native_frames = [], [], [], [], [], []
    for row in raw['rows']:
        i, t = row['frame'], row['time_s']
        ego, other = row['ego'], row['other']
        x, y, z = ego['center_xyz_m']
        trace.append({'frame': i, 'time_s': t,
            'position': {'x': x, 'y': y, 'z': z}, 'position_m': [x, y, z],
            'heading_deg': 0, 'speed_mps': ego['speed_mps'],
            'speed_mph': ego['speed_mps'] * 2.2369362920544,
            'velocity_mps': [ego['speed_mps'], 0, 0],
            'control': {'throttle': 0, 'brake': 0, 'hand_brake': False}})
        crossing.append({'frame': i, 'time_s': t,
            'ego_vertices_m': ego['body_xyz_m'],
            'other_vertices_m': other['body_xyz_m']})
        frames.append({'carla_frame': i, 'native_frame': i,
                       'time_s': t, 'video_frame': i})
        evidence.append({'original_frame': i, 'recording_time_s': t,
            'ego': {'body_vertices_m': ego['body_xyz_m'],
                    'position_m': ego['center_xyz_m'],
                    'heading_deg': 0, 'speed_mps': ego['speed_mps'],
                    'speed_provenance': 'synthetic_native_sample',
                    'synthetic_diagnostic': True},
            'other_actors': [{'actor_id': 11,
                'body_vertices_m': other['body_xyz_m'],
                'position_m': other['center_xyz_m']}],
            'replay_frame': i, 'replay_simulation_time_s': t,
            'actor_id': 10,
            'world': {'road_projection': {'road_id': 250, 'lane_id': -1}}})
        graph_path = f'graphs/base/{i:08d}.adapter.json'
        native_frames.append({'frame': i, 'simulation_time': t,
            'adapter_graph': graph_path, 'base': graph_path,
            'nodes': 2, 'edges': 0})
        graphs.append({'path': 'capture/native/' + graph_path,
            'attributes': {'frame': i, 'simulation_time_s': t,
                           'synthetic_diagnostic': True},
            'nodes': [{'id': 'ego', 'attributes': {'sem_class': 'ego',
                       'entity_id': 10, 'vertex': ego['center_xyz_m'],
                       'forward': [1, 0, 0],
                       'threedbbox': ego['body_xyz_m']}},
                      {'id': 'other', 'attributes': {'sem_class': 'vehicle',
                       'entity_id': 11, 'vertex': other['center_xyz_m'],
                       'forward': [0, 1, 0],
                       'threedbbox': other['body_xyz_m']} }], 'edges': []})
    lines(sources / 'trace.jsonl', trace)
    lines(sources / 'crossing_history.jsonl', crossing)
    lines(sources / 'video_frames.jsonl', frames)
    lines(sources / 'capture/evidence.jsonl', evidence)
    put(sources / 'capture/manifest.json', {'extraction_confirmed': True,
        'frames': 600, 'synthetic_diagnostic': True,
        'sources': {'road.xodr': sha(sources / 'road.xodr'),
                    'trace.jsonl': sha(sources / 'trace.jsonl')}})
    spec = {'files': {
        'capture/native/frames.jsonl': ''.join(json.dumps(r, separators=(',', ':')) + '\n'
                                                for r in native_frames),
        'capture/recorder_info.txt':
            'synthetic CPU diagnostic; no CARLA recorder\nCreate 10: vehicle.tesla.model3 (0)\nCreate 11: vehicle.audi.a2 (0)\n'},
        'graphs': graphs,
        'videos': [{'path': name + '.mkv', 'frames': 600,
            'width': 1920 if name == 'overview' else 1280,
            'height': 1080 if name == 'overview' else 720,
            'fps': 20, 'color': 'black'} for name in
            ('overview', 'approach', 'reference_corner', 'driver_reference')]}
    spec_path = root / 'fixture-spec.json'
    put(spec_path, spec)
    refs = [{'path': str(path.relative_to(sources)),
             'source': str(path.relative_to(REPO)), 'sha256': sha(path)}
            for path in sorted(sources.rglob('*')) if path.is_file()]
    recipe = root / 'fixture-recipe.json'
    put(recipe, {'format': 'worker-fixture-recipe', 'sources': refs,
                 'generator': {'source': str(spec_path.relative_to(REPO)),
                               'sha256': sha(spec_path)}})
    return {'case': suffix, 'candidate': candidate,
            'fixture_recipe_sha256': sha(recipe)}


if __name__ == '__main__':
    print(json.dumps([build(s, c) for s in CASES for c in CANDIDATES], indent=2))
