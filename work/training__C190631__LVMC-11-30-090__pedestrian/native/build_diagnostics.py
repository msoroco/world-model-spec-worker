"""Build bounded source-shaped CPU recipes for the two exact walking surfaces."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
CAMERAS = [('overview', 1920, 1080), ('approach', 1280, 720),
           ('reference_corner', 1280, 720), ('driver_reference', 1280, 720)]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, separators=(',', ':'), ensure_ascii=False) + '\n')


def line(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('\n'.join(json.dumps(row, separators=(',', ':')) for row in rows) + '\n')


def body(x, y):
    return [[round(x + dx, 5), y + dy, z]
            for dx in (-.2, .2) for dy in (-.2, .2) for z in (8, 9.8)]


def build(suffix, surface):
    folder = ROOT / 'diagnostic' / suffix
    sources = folder / 'sources'
    geometry = __import__('geometry')
    meter = __import__('measure')
    y = -5 if surface == 'sidewalk' else -1.75
    lane_id = -3 if surface == 'sidewalk' else -1
    context = geometry.geometry()
    context['native_readback'] = {
        'roadway': [{'native_xyz_m': [x, -1.75, 8], 'road_id': 1, 'lane_id': -1}
                    for x in (-30, 0, 30)],
        'sidewalk': [{'native_xyz_m': [x, -5, 8], 'road_id': 1, 'lane_id': -3}
                     for x in (-30, 0, 30)],
        'lower_road': [{'native_xyz_m': [1.75, v, 0], 'road_id': 2, 'lane_id': -1}
                       for v in (-20, 0, 20)]}
    write(sources / 'surface-geometry.json', context)
    (sources / 'road.xodr').write_text(geometry.open_drive() + '\n')
    poses, trace, mapped, evidence, frames, graphs = [], [], [], [], [], []
    for i in range(600):
        x = round(-30 + i * .1, 5)
        t = round(i / 20, 5)
        frame = 1000 + i
        corners = [[x + dx, y + dy] for dx, dy in
                   ((-.2, -.2), (-.2, .2), (.2, -.2), (.2, .2))]
        pose = {'video_frame': i, 'native_frame': frame, 'time_s': t,
                'pedestrian_xy_m': [x, y], 'pedestrian_z_m': 8.5,
                'pedestrian_footprint_xy_m': corners,
                'walker_actor_id': 14, 'walker_blueprint_id': 'walker.pedestrian.0001'}
        poses.append(pose)
        trace.append({'frame': frame, 'time_s': t,
                      'position': {'x': x, 'y': y, 'z': 8.5},
                      'position_m': [x, y, 8.5], 'heading_deg': 0,
                      'speed_mps': 2, 'speed_mph': 2 / .44704,
                      'velocity_mps': [2, 0, 0], 'control': {}})
        mapped.append({'video_frame': i, 'carla_frame': frame,
                       'native_frame': frame, 'time_s': t,
                       'camera_native_frames': {name: frame for name, _, _ in CAMERAS}})
        evidence.append({'actor_id': 14,
                         'ego': {'body_vertices_m': body(x, y), 'heading_deg': 0,
                                 'position_m': [x, y, 8.5], 'speed_mps': 2,
                                 'speed_provenance': 'synthetic_native_sample',
                                 'synthetic_diagnostic': True},
                         'original_frame': frame, 'other_actors': [],
                         'recording_time_s': t, 'replay_frame': frame,
                         'replay_simulation_time_s': t,
                         'world': {'road_projection': {'lane_id': lane_id, 'road_id': 1,
                                                       's_m': x + 50, 'section_id': 0},
                                   'weather': {'cloudiness': 0, 'fog_density': 0,
                                               'precipitation': 0, 'wetness': 0}}})
        graph_path = f'capture/native/graphs/base/{i:08d}.adapter.json'
        frames.append({'adapter_graph': f'graphs/base/{i:08d}.adapter.json',
                       'base': f'graphs/base/{i:08d}.adapter.json',
                       'edges': 0, 'frame': frame, 'nodes': 1,
                       'simulation_time': t})
        graphs.append({'path': graph_path,
                       'attributes': {'frame': frame, 'simulation_time_s': t,
                                      'source': 'C190631 walking-surface CPU diagnostic',
                                      'synthetic_diagnostic': True},
                       'edges': [],
                       'nodes': [{'id': 'ego',
                                  'attributes': {'entity_id': 14, 'forward': [1, 0, 0],
                                                 'sem_class': 'ego', 'threedbbox': body(x, y),
                                                 'vertex': [x, y, 8.5]}}]})
    for name, rows in [('pedestrian-poses.jsonl', poses), ('trace.jsonl', trace),
                       ('video_frames.jsonl', mapped), ('capture/evidence.jsonl', evidence)]:
        line(sources / name, rows)
    manifest = {'extraction_confirmed': True, 'frames': 600,
                'sources': {name: sha(sources / name)
                            for name in ('pedestrian-poses.jsonl', 'surface-geometry.json',
                                         'road.xodr', 'trace.jsonl')},
                'synthetic_diagnostic': True}
    write(sources / 'capture/manifest.json', manifest)
    specification = {'files': {
        'capture/native/frames.jsonl': '\n'.join(json.dumps(row, separators=(',', ':'))
                                                  for row in frames) + '\n',
        'capture/recorder_info.txt':
            'Synthetic diagnostic; no Native recording.\nCreate 14: walker.pedestrian.0001 (0)\n'},
        'graphs': graphs,
        'videos': [{'path': name + '.mkv', 'frames': 600, 'width': width,
                    'height': height, 'fps': 20, 'color': 'black'}
                   for name, width, height in CAMERAS]}
    write(folder / 'fixture-spec.json', specification)
    recipe = {'format': 'worker-fixture-recipe',
              'generator': {'source': str((folder / 'fixture-spec.json').relative_to(REPO)),
                            'sha256': sha(folder / 'fixture-spec.json')},
              'sources': [{'path': str(path.relative_to(sources)),
                           'source': str(path.relative_to(REPO)), 'sha256': sha(path)}
                          for path in sorted(sources.rglob('*')) if path.is_file()]}
    write(folder / 'fixture-recipe.json', recipe)
    measured = meter.measure(sources / 'pedestrian-poses.jsonl',
                             sources / 'surface-geometry.json')
    assert measured[surface + '_occupied_frames'] == 600
    return {'case': suffix, 'recipe_sha256': sha(folder / 'fixture-recipe.json'),
            'sources': len(recipe['sources']), 'frames': 600}


if __name__ == '__main__':
    print(json.dumps([build('probe_01', 'sidewalk'),
                      build('probe_02', 'roadway')], sort_keys=True))
