"""Build text-only synthetic diagnostic sources for exact probe 1."""
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE / 'native'))
from geometry import open_drive
from prove_crossing import context as proof_context

CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def lines(path, values):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(v, allow_nan=False) + '\n' for v in values))


def main():
    suffix = sys.argv[1] if len(sys.argv) > 1 else 'probe1'
    if suffix not in ('probe1', 'probe2'):
        raise ValueError('Exact probe1/probe2 diagnostic only')
    x_position = 0.0 if suffix == 'probe1' else 12.0
    case = HERE.name + ('__probe_1' if suffix == 'probe1' else '__probe_2')
    fixture = HERE / ('v2-' + suffix + '-fixture')
    fixture.mkdir(exist_ok=True)
    road = fixture / 'road.xodr'
    road.write_text(open_drive() + '\n')
    context = proof_context()
    context['native_map_sha256'] = sha(road)
    context['crosswalk_survey_sha256'] = sha(road)
    context['overpass_geometry_sha256'] = sha(road)
    context['pedestrian_identity_sha256'] = hashlib.sha256(b'walker.pedestrian synthetic diagnostic').hexdigest()
    context['business_district_evidence_sha256'] = hashlib.sha256(b'synthetic business district diagnostic only').hexdigest()
    context['intersection_inventory'] = [{'crosswalk_kind': 'marked', 'x_m': 0},
                                         {'crosswalk_kind': 'unmarked', 'x_m': 21}]
    write(fixture / 'crossing-context.json', context)
    poses, trace, mapping, evidence, graph_rows, graphs = [], [], [], [], [], []
    for i in range(600):
        frame = 12000 + i
        time = i / 20
        y = -6.0 if i < 100 else -6.0 + 12.0 * min(i - 100, 240) / 240
        speed = 1.0 if 100 <= i < 340 else 0.0
        vertices = [[x, yy, z] for x in (x_position - 0.2, x_position + 0.2)
                    for yy in (y - 0.2, y + 0.2) for z in (0.0, 1.8)]
        poses.append({'video_frame': i, 'native_frame': frame, 'time_s': time,
                      'pedestrian_id': 107, 'pedestrian_x_m': x_position, 'pedestrian_y_m': y,
                      'pedestrian_z_m': 0.5, 'pedestrian_on_overpass_deck': False,
                      'requested_path': {'x_m': x_position, 'y_m': y, 'target_speed_mps': speed},
                      'camera_native_frames': {name: frame for name in CAMERAS}})
        trace.append({'frame': frame, 'time_s': time,
                      'position': {'x': x_position, 'y': y, 'z': 0.5},
                      'position_m': [x_position, y, 0.5], 'heading_deg': 90.0,
                      'speed_mps': speed, 'speed_mph': speed * 2.2369362921,
                      'velocity_mps': [0.0, speed, 0.0],
                      'control': {'walker_speed_mps': speed}})
        mapping.append({'video_frame': i, 'native_frame': frame,
                        'carla_frame': frame, 'time_s': time})
        evidence.append({'actor_id': 107, 'original_frame': frame, 'replay_frame': frame,
                         'recording_time_s': time, 'replay_simulation_time_s': time,
                         'ego': {'body_vertices_m': vertices, 'position_m': [x_position, y, 0.5],
                                 'heading_deg': 90.0, 'speed_mps': speed,
                                 'speed_provenance': 'synthetic_native_sample',
                                 'synthetic_diagnostic': True},
                         'world': {'road_projection': {'road_id': 1, 'lane_id': -1 if y < 0 else 1,
                                                       'section_id': 0, 's_m': 100 + x_position},
                                   'weather': {'cloudiness': 0, 'fog_density': 0,
                                               'precipitation': 0, 'wetness': 0}}})
        graph_path = f'capture/native/graphs/base/{frame:08d}.adapter.json'
        graphs.append({'path': graph_path,
                       'attributes': {'frame': frame, 'simulation_time_s': time,
                                      'source': 'C188094 synthetic crossing diagnostic',
                                      'synthetic_diagnostic': True},
                       'nodes': [{'id': 'ego', 'attributes': {'entity_id': 107,
                                   'sem_class': 'ego', 'vertex': [x_position, y, 0.5],
                                   'forward': [0.0, 1.0, 0.0], 'threedbbox': vertices}}],
                       'edges': []})
        graph_rows.append({'frame': frame, 'simulation_time': time,
                           'adapter_graph': f'graphs/base/{frame:08d}.adapter.json',
                           'base': f'graphs/base/{frame:08d}.adapter.json', 'nodes': 1, 'edges': 0})
    for name, values in (('actor-poses.jsonl', poses), ('trace.jsonl', trace),
                         ('video_frames.jsonl', mapping), ('capture/evidence.jsonl', evidence)):
        lines(fixture / name, values)
    write(fixture / 'capture/manifest.json',
          {'extraction_confirmed': True, 'frames': 600, 'synthetic_diagnostic': True,
           'sources': {'road.xodr': sha(road), 'trace.jsonl': sha(fixture / 'trace.jsonl')}})
    write(fixture / 'native-capture-report.json',
          {'case_id': case, 'candidate_id': 'primary', 'requested_frames': 600,
           'observed_frames': 600, 'restoration': None, 'error': None,
           'accepted': False, 'source_kind': 'synthetic_cpu'})
    write(fixture / 'native-map-readback.json',
          {'source_kind': 'synthetic_cpu', 'road_id': 1,
           'crosswalks': context['crosswalks']})
    spec = {'files': {'capture/native/frames.jsonl': ''.join(json.dumps(row) + '\n' for row in graph_rows),
                      'capture/recorder_info.txt': 'synthetic CPU diagnostic; no CARLA recorder\nCreate 107: walker.pedestrian.0001 (0)\n'},
            'graphs': graphs,
            'videos': [{'path': name + '.mkv', 'frames': 600,
                        'width': 1920 if name == 'overview' else 1280,
                        'height': 1080 if name == 'overview' else 720,
                        'fps': 20, 'color': 'black'}
                       for name in CAMERAS]}
    spec_path = HERE / ('v2-' + suffix + '-fixture-spec.json')
    write(spec_path, spec)
    sources = [{'path': path.relative_to(fixture).as_posix(),
                'source': path.relative_to(ROOT).as_posix(), 'sha256': sha(path)}
               for path in sorted(fixture.rglob('*')) if path.is_file()]
    recipe = {'format': 'worker-fixture-recipe', 'sources': sources,
              'generator': {'source': spec_path.relative_to(ROOT).as_posix(),
                            'sha256': sha(spec_path)}}
    write(HERE / ('v2-' + suffix + '-fixture-recipe.json'), recipe)
    print(json.dumps({'source_count': len(sources), 'fixture_spec_sha256': sha(spec_path),
                      'recipe_sha256': sha(HERE / ('v2-' + suffix + '-fixture-recipe.json'))}))


if __name__ == '__main__':
    main()
