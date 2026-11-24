"""Source-inventory a current-runtime synthetic witness diagnostic fixture."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    return [json.loads(x) for x in path.read_text().splitlines()]


def write_rows(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(x, separators=(',', ':')) + '\n' for x in data))


def build(suffix):
    prepared = HERE / 'synthetic-bridge' / suffix / 'prepared'
    source = HERE / 'current-fixture' / suffix
    source.mkdir(parents=True, exist_ok=True)
    actors = rows(prepared / 'observed-actors.jsonl')
    mappings = rows(prepared / 'video_frames.jsonl')
    assert len(actors) == len(mappings) == 480
    trace, evidence, frames, graphs = [], [], [], []
    for index, (actor, mapping) in enumerate(zip(actors, mappings)):
        frame = actor['native_frame']
        time = mapping['time_s']
        sx, sy = actor['actors']['subject']['native_center_xy_m']
        ax, ay = actor['actors']['approach']['native_center_xy_m']
        body = [[x, y, z] for x, y in actor['actors']['subject']['native_body_xy_m'] for z in (0, 1.5)]
        approach_body = [[ax + dx, ay + dy, z] for dx in (-2.25, 2.25) for dy in (-.9, .9) for z in (0, 1.5)]
        trace.append({'frame': frame, 'time_s': time, 'position': {'x': sx, 'y': sy, 'z': .5},
                      'position_m': [sx, sy, .5], 'heading_deg': 0, 'speed_mps': 4,
                      'speed_mph': 4 / .44704, 'velocity_mps': [4, 0, 0],
                      'control': {'throttle': .3, 'brake': 0, 'hand_brake': False}})
        evidence.append({'original_frame': frame, 'replay_frame': frame, 'actor_id': 107,
                         'recording_time_s': time, 'replay_simulation_time_s': time,
                         'ego': {'position_m': [sx, sy, .5], 'heading_deg': 0, 'speed_mps': 4,
                                 'speed_provenance': 'synthetic_native_sample', 'body_vertices_m': body},
                         'world': {'weather': {'cloudiness': 0, 'precipitation': 0, 'wetness': 0, 'fog_density': 0},
                                   'road_projection': {'road_id': 1, 'section_id': 0, 'lane_id': -1, 's_m': sx + 100}}})
        name = f'{frame:08d}'
        graphs.append({'path': f'capture/native/graphs/base/{name}.adapter.json',
                       'attributes': {'frame': frame, 'simulation_time_s': time, 'synthetic_diagnostic': True},
                       'nodes': [{'id': 'ego', 'attributes': {'sem_class': 'ego', 'entity_id': 107,
                                  'vertex': [sx, sy, .5], 'forward': [1, 0, 0], 'threedbbox': body}},
                                 {'id': 'approach', 'attributes': {'sem_class': 'vehicle', 'entity_id': 108,
                                  'vertex': [ax, ay, .5], 'forward': [1, 0, 0], 'threedbbox': approach_body}}],
                       'edges': []})
        frames.append({'frame': frame, 'simulation_time': time, 'time_s': time,
                       'base': f'graphs/base/{name}.adapter.json',
                       'abstract': f'graphs/abstract/{name}.pkl',
                       'adapter_graph': f'graphs/base/{name}.adapter.json',
                       'synthetic_diagnostic': True})
    write_rows(source / 'trace.jsonl', trace)
    write_rows(source / 'capture/evidence.jsonl', evidence)
    write_rows(source / 'capture/native/frames.jsonl', frames)
    (source / 'capture/recorder_info.txt').write_text('Create 107: vehicle.lincoln.mkz_2020\n')
    (source / 'capture/manifest.json').write_text(json.dumps({
        'extraction_confirmed': True, 'frames': 480, 'acquisition': 'synthetic_diagnostic',
        'observation_contract_version': 1,
        'required_observations': ['rel.same_direction', 'rel.surface_gap', 'kin.position', 'rel.occupies'],
        'sources': {'road.xodr': sha(HERE / 'draft-construction/scene.xodr'), 'trace.jsonl': sha(source / 'trace.jsonl')},
        'synthetic_diagnostic': True}, separators=(',', ':')) + '\n')
    (source / 'acquisition-provenance.json').write_text(json.dumps({
        'provenance_kind': 'synthetic_local_diagnostic', 'diagnostic_fixture': True,
        'native_executed': False}, separators=(',', ':')) + '\n')
    files = [{'path': 'road.xodr', 'source': (HERE / 'draft-construction/scene.xodr').relative_to(ROOT).as_posix(), 'sha256': sha(HERE / 'draft-construction/scene.xodr')}]
    for path in sorted(source.rglob('*')):
        if path.is_file():
            files.append({'path': path.relative_to(source).as_posix(),
                          'source': path.relative_to(ROOT).as_posix(), 'sha256': sha(path)})
    for name in ('source-scope.json', 'actor-frames.jsonl', 'observed-actors.jsonl',
                 'front-lamp-review.json', 'front_lamp.source', 'video_frames.jsonl'):
        path = prepared / name
        files.append({'path': name.replace('source-scope.json', 'context-scope.json'), 'source': path.relative_to(ROOT).as_posix(), 'sha256': sha(path)})
    spec = {'files': {}, 'graphs': graphs,
            'videos': [{'path': name + '.mkv', 'frames': 480, 'width': width, 'height': height,
                        'fps': 20, 'color': 'blue'}
                       for name, width, height in (('overview', 1920, 1080), ('front_lamp', 1280, 720),
                                                   ('rear_approach', 1280, 720), ('subject_reference', 1280, 720),
                                                   ('approach', 1280, 720), ('reference_corner', 1280, 720),
                                                   ('driver_reference', 1280, 720))]}
    spec_path = HERE / f'current-{suffix}-diagnostic.json'
    spec_path.write_text(json.dumps(spec, separators=(',', ':')) + '\n')
    recipe = {'format': 'worker-fixture-recipe', 'sources': files,
              'generator': {'source': spec_path.relative_to(ROOT).as_posix(), 'sha256': sha(spec_path)}}
    recipe_path = HERE / f'current-{suffix}-recipe.json'
    recipe_path.write_text(json.dumps(recipe, indent=2) + '\n')
    return {'case': suffix, 'source_count': len(files), 'recipe_sha256': sha(recipe_path)}


if __name__ == '__main__':
    for suffix in ('witness_1', 'witness_2'):
        print(json.dumps(build(suffix)))
