"""Build a 600-frame source-bound CPU diagnostic for the probe_a primary.

All observations here are synthetic_native_sample, never original CARLA evidence.
"""
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
from synthetic_proof import sample


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def lines(path, values):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(v, sort_keys=True, allow_nan=False) + '\n' for v in values))


def main():
    case_id = HERE.name + '__probe_a'
    fixture = HERE / 'current-v2-probe_a-fixture'
    fixture.mkdir(exist_ok=True)
    construction = HERE / 'duration-600-drafts/probe_a/primary/construction.json'
    bundle = json.loads(construction.read_text())
    config = json.loads(next(item['content'] for item in bundle['files'] if item['path'] == 'config.json'))
    motion, trace, frames, body, evidence, graphs, native_frames = [], [], [], [], [], [], []
    for i in range(600):
        row = sample('probe_a', i)
        corners = row['body_xy_m']
        center = [round(sum(v[0] for v in corners) / 4, 5), -1.75]
        vertices = [[x, y, z] for x, y in corners for z in (0.0, 1.5)]
        frame = row['native_frame']
        time_s = row['time_s']
        row.update(native_center_xy_m=center, native_body_xy_m=corners,
                   native_forward_xy=[1.0, 0.0], speed_mps=row['speed_m_s'])
        motion.append(row)
        trace.append({'frame': frame, 'time_s': time_s,
                      'position': {'x': center[0], 'y': center[1], 'z': 0.5},
                      'position_m': [*center, 0.5], 'heading_deg': 0.0,
                      'speed_mps': row['speed_m_s'], 'speed_mph': row['speed_m_s'] * 2.2369362921,
                      'control': {'throttle': 0, 'brake': int(row['speed_m_s'] == 0),
                                  'hand_brake': row['speed_m_s'] == 0}})
        frames.append({'video_frame': i, 'native_frame': frame,
                       'carla_frame': frame, 'time_s': time_s})
        body.append({'frame': frame, 'time_s': time_s, 'body_vertices_m': vertices})
        evidence.append({'actor_id': 107, 'original_frame': frame,
                         'replay_frame': frame, 'recording_time_s': time_s,
                         'replay_simulation_time_s': time_s,
                         'ego': {'body_vertices_m': vertices, 'position_m': [*center, 0.5],
                                 'heading_deg': 0.0, 'speed_mps': row['speed_m_s'],
                                 'speed_provenance': 'synthetic_native_sample',
                                 'synthetic_diagnostic': True},
                         'world': {'road_projection': {'road_id': 1, 'lane_id': -1,
                                                       'section_id': 0, 's_m': max(0, center[0] + 57)},
                                   'weather': {'cloudiness': 0, 'fog_density': 0,
                                               'precipitation': 0, 'wetness': 0}}})
        graph_path = f'capture/native/graphs/base/{frame:08d}.adapter.json'
        graphs.append({'path': graph_path,
                       'attributes': {'frame': frame, 'simulation_time_s': time_s,
                                      'source': 'C110454 synthetic parking diagnostic',
                                      'synthetic_diagnostic': True},
                       'nodes': [{'id': 'ego', 'attributes': {'entity_id': 107,
                                   'sem_class': 'ego', 'vertex': [*center, 0.5],
                                   'forward': [1.0, 0.0, 0.0], 'threedbbox': vertices}}],
                       'edges': []})
        native_frames.append({'frame': frame, 'simulation_time': time_s,
                              'adapter_graph': f'graphs/base/{frame:08d}.adapter.json',
                              'base': f'graphs/base/{frame:08d}.adapter.json',
                              'nodes': 1, 'edges': 0})
    source_rows = {'native_samples.jsonl': motion, 'trace.jsonl': trace,
                   'video_frames.jsonl': frames, 'body_history.jsonl': body,
                   'capture/evidence.jsonl': evidence}
    for name, values in source_rows.items():
        lines(fixture / name, values)
    survey = {'intersection_polygon_xy_m': [[-7,-7],[7,-7],[7,7],[-7,7]],
              'native_signal_count': 0, 'source_kind': 'synthetic_cpu_fixture'}
    write(fixture / 'road_geometry.json', survey)
    write(fixture / 'context.json', {'surveyed_intersection': survey})
    (fixture / 'road.xodr').write_text(next(item['content'] for item in bundle['files']
                                           if item['path'] == 'road.xodr'))
    write(fixture / 'capture/manifest.json',
          {'extraction_confirmed': True, 'frames': 600, 'synthetic_diagnostic': True,
           'sources': {'road.xodr': sha(fixture / 'road.xodr'),
                       'trace.jsonl': sha(fixture / 'trace.jsonl')}})
    write(fixture / 'native-capture-report.json',
          {'case_id': case_id, 'candidate_id': 'primary', 'requested_frames': 600,
           'observed_frames': 600, 'restoration': None, 'error': None,
           'accepted': False, 'source_kind': 'synthetic_cpu',
           'bundle_config_sha256': hashlib.sha256(next(item['content'] for item in bundle['files']
              if item['path'] == 'config.json').encode()).hexdigest()})
    write(fixture / 'native-map-readback.json',
          {'source_kind': 'synthetic_cpu', 'native_signal_count': 0,
           'intersection_polygon_xy_m': survey['intersection_polygon_xy_m']})
    spec = {'files': {'capture/native/frames.jsonl': ''.join(json.dumps(x) + '\n' for x in native_frames),
                      'capture/recorder_info.txt': 'synthetic CPU diagnostic; no CARLA recorder\nCreate 107: vehicle.lincoln.mkz_2020 (0)\n'},
            'graphs': graphs,
            'videos': [{'path': f'{name}.mkv', 'frames': 600, 'width': width,
                        'height': height, 'fps': 20, 'color': 'black'}
                       for name, width, height in [('overview',1920,1080), ('approach',1280,720),
                                                   ('reference_corner',1280,720), ('driver_reference',1280,720),
                                                   ('intersection',1280,720), ('parking',1280,720)]]}
    spec_path = HERE / 'current-v2-probe_a-fixture-spec.json'
    write(spec_path, spec)
    sources = []
    for path in sorted(fixture.rglob('*')):
        if path.is_file():
            relative = path.relative_to(fixture).as_posix()
            sources.append({'path': relative, 'source': path.relative_to(ROOT).as_posix(),
                            'sha256': sha(path)})
    recipe_path = HERE / 'current-v2-probe_a-fixture-recipe.json'
    write(recipe_path, {'format': 'worker-fixture-recipe', 'sources': sources,
                        'generator': {'source': spec_path.relative_to(ROOT).as_posix(),
                                      'sha256': sha(spec_path)}})
    contract = json.loads((HERE / 'draft-candidates/probe_a/measurement-contract.json').read_text())
    contract['format'] = 'worker-measurement-contract'
    contract_path = HERE / 'current-v2-probe_a-measurement-contract.json'
    write(contract_path, contract)
    manifest = json.loads((HERE / 'draft-execution-manifest-600.json').read_text())
    manifest['cases'] = [manifest['cases'][0]]
    manifest['cases'][0]['candidates'] = []
    manifest['cases'][0]['fixture_recipe'] = recipe_path.relative_to(ROOT).as_posix()
    manifest['cases'][0]['measurement_contract'] = contract_path.name
    manifest_path = HERE / 'current-v2-probe_a-primary-manifest.json'
    write(manifest_path, manifest)
    print(json.dumps({'manifest_sha256': sha(manifest_path), 'recipe_sha256': sha(recipe_path),
                      'spec_sha256': sha(spec_path), 'sources': len(sources)}))


if __name__ == '__main__':
    main()
