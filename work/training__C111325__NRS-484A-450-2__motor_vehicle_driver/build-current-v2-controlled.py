"""Build source-hashed current v2 synthetic crosswalk-stop diagnostic."""
import hashlib
import json
from pathlib import Path
import runpy

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CASE = HERE.name + '__probe_2'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def lines(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(row, allow_nan=False) + '\n' for row in rows))


def main():
    source = HERE / 'current-v2-probe-2-fixture'
    source.mkdir(exist_ok=True)
    native = runpy.run_path(str(HERE / 'prove-crosswalk-stop.py'))['rows'](False)
    lines(source / 'native_samples.jsonl', native)
    (source / 'road.xodr').write_bytes((HERE / 'native/road.xodr').read_bytes())
    write(source / 'diagnostic-source-manifest.json', {
        'case_id': CASE, 'source_kind': 'synthetic_native_sample',
        'sha256': {name: sha(source / name) for name in ('road.xodr', 'native_samples.jsonl')}})
    mapping, trace, evidence, frames, graphs = [], [], [], [], []
    for row in native:
        index = row['video_frame']
        frame = row['native_frame']
        time = row['time_s']
        speed = row['speed_mps']
        body = row['body_vertices_m']
        x = sum(v[0] for v in body) / len(body)
        y = sum(v[1] for v in body) / len(body)
        mapping.append({'video_frame': index, 'native_frame': frame,
                        'carla_frame': frame, 'time_s': time})
        trace.append({'frame': frame, 'time_s': time,
                      'position': {'x': x, 'y': y, 'z': 0.5},
                      'position_m': [x, y, 0.5], 'heading_deg': 90.0,
                      'speed_mps': speed, 'speed_mph': speed / .44704,
                      'control': {'throttle': 0, 'brake': 0, 'hand_brake': False}})
        evidence.append({'original_frame': frame, 'recording_time_s': time,
                         'replay_frame': frame, 'replay_simulation_time_s': time,
                         'actor_id': 107,
                         'ego': {'body_vertices_m': body, 'position_m': [x, y, 0.5],
                                 'heading_deg': 90.0, 'speed_mps': speed,
                                 'speed_provenance': 'synthetic_native_sample'},
                         'world': {'weather': {}, 'road_projection': {
                             'road_id': row['road_id'], 'section_id': 0,
                             'lane_id': -1, 's_m': float(index) / 10}}})
        frames.append({'frame': frame, 'simulation_time': time, 'time_s': time,
                       'adapter_graph': f'graphs/base/{frame:08d}.adapter.json',
                       'synthetic_diagnostic': True})
        graphs.append({'path': f'capture/native/graphs/base/{frame:08d}.adapter.json',
                       'attributes': {'frame': frame, 'simulation_time_s': time},
                       'nodes': [{'id': 'ego', 'attributes': {
                           'vertex': [x, y, 0.5], 'sem_class': 'ego',
                           'forward': [0.0, 1.0, 0.0], 'entity_id': 107,
                           'carla_speed': speed, 'special_class': 'ego'}}],
                       'edges': []})
    lines(source / 'video_frames.jsonl', mapping)
    lines(source / 'trace.jsonl', trace)
    lines(source / 'capture/evidence.jsonl', evidence)
    lines(source / 'capture/native/frames.jsonl', frames)
    (source / 'capture/recorder_info.txt').write_text(
        'Create 107: vehicle.tesla.model3\nSynthetic diagnostic source frames: 600\n')
    write(source / 'capture/manifest.json', {
        'extraction_confirmed': True, 'frames': 600, 'synthetic_diagnostic': True,
        'sources': {'road.xodr': sha(source / 'road.xodr'),
                    'trace.jsonl': sha(source / 'trace.jsonl')}})
    spec = HERE / 'current-v2-probe-2-fixture-spec.json'
    write(spec, {'files': {}, 'graphs': graphs,
                 'videos': [{'path': name + '.mkv', 'frames': 600, 'width': width,
                             'height': height, 'fps': 20, 'color': 'black'}
                            for name, width, height in
                            [('overview', 1920, 1080), ('approach', 1280, 720),
                             ('reference_corner', 1280, 720), ('driver_reference', 1280, 720)]]})
    recipe = HERE / 'current-v2-probe-2-fixture-recipe.json'
    write(recipe, {'format': 'worker-fixture-recipe',
                   'sources': [{'path': p.relative_to(source).as_posix(),
                                'source': p.relative_to(ROOT).as_posix(), 'sha256': sha(p)}
                               for p in sorted(source.rglob('*')) if p.is_file()],
                   'generator': {'source': spec.relative_to(ROOT).as_posix(),
                                 'sha256': sha(spec)}})
    contract = HERE / 'current-v2-probe-2-measurement-contract.json'
    write(contract, {'format': 'worker-measurement-contract', 'case_id': CASE,
                     'requirements': [{'disposition_index': 0, 'requirement': 'NRS-484A-450-2',
                                       'source': 'NRS 484A.450(2)',
                                       'output_key': 'crosswalk_stop',
                                       'method': 'measure_crosswalk_stop',
                                       'value_type': 'object', 'kind': 'measured',
                                       'inputs': ['native_samples.jsonl', 'road.xodr']}],
                     'negative': {'remove': ['road.xodr'],
                                  'error_contains': 'Missing required source: road.xodr'}})
    manifest = json.loads((HERE / 'draft-manifest.json').read_text())
    entry = manifest['cases'][1]
    entry['fixture_recipe'] = recipe.relative_to(ROOT).as_posix()
    entry['measurement_contract'] = contract.name
    entry['measurement_procedure'] = {'entrypoint': 'finalize.py',
                                      'output_schema': 'c111325-saved-analysis-v1'}
    manifest['cases'] = [entry]
    destination = HERE / 'current-v2-probe-2-primary-manifest.json'
    write(destination, manifest)
    plan = json.loads((HERE / 'case-plan.json').read_text())
    write(HERE / 'proposals/cases.json',
          {'cases': [c for c in plan['cases'] if c['case_id'].endswith(('__probe_1', '__probe_2'))]})
    print(json.dumps({'manifest': sha(destination), 'recipe': sha(recipe),
                      'spec': sha(spec), 'sources': len(json.loads(recipe.read_text())['sources'])}))


if __name__ == '__main__':
    main()
