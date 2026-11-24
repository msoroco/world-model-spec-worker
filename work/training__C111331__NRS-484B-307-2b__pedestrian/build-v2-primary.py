"""Author one unselected, source-hashed current v2 crossing diagnostic."""
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRATCH = ROOT / '.runtime-work/c111331-v2/witness_1'
OUT = HERE / 'v2-primary/witness_1'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_rows(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(row, separators=(',', ':')) + '\n' for row in rows))


def main():
    source = json.loads((HERE / 'draft-native-bundles/witness_1/construction.json').read_text())
    construction = copy.deepcopy(source)
    for name in ('finalize.py', 'signals.py'):
        if not any(item['path'] == name for item in construction['files']):
            construction['files'].append({'path': name, 'content': (HERE / 'native' / name).read_text()})
    for name in ('saved_source_bridge.py', 'saved_entry_measurement.py'):
        construction['files'].append({'path': name, 'content': (HERE / name).read_text()})
    config_file = next(item for item in construction['files'] if item['path'] == 'config.json')
    config = json.loads(config_file['content'])
    config['recording_description'] = {'channels': [
        {'name': 'pedestrian_entry_signal', 'unit': 'structured',
         'sampling_rate_hz': 20,
         'method': 'original Native pedestrian pose, signal actor readback and camera-frame join',
         'time_window': 'entire 30 s / 600-frame attempt',
         'reference_frame': 'Native OpenDRIVE head IDs and original frame map',
         'uncertainty': 'Pixel indication and governing direction require independent review'}],
         'context_inputs': [], 'limitations': ['CPU diagnostic has no original pixels or legal verdict']}
    construction['recording_description'] = config['recording_description']
    config_file['content'] = json.dumps(config, indent=2) + '\n'
    construction['status'] = 'unselected_current_v2_cpu_diagnostic'
    OUT.mkdir(parents=True, exist_ok=True)
    construction_path = OUT / 'construction.json'
    construction_path.write_text(json.dumps(construction, indent=2) + '\n')
    native = [json.loads(line) for line in (SCRATCH / 'c111331-native-samples.jsonl').read_text().splitlines()]
    mapping = [json.loads(line) for line in (SCRATCH / 'video_frames.jsonl').read_text().splitlines()]
    assert len(native) == len(mapping) == 600
    for row in native:
        row['pedestrian_xy_m'][0] -= 3.0
        row['observed_traffic_signal']['id'] = config['traffic_head_id']
        row['observed_pedestrian_signal']['id'] = config['pedestrian_head_id']
    for row in mapping:
        row['carla_frame'] = row['native_frame']
    trace = []
    evidence = []
    graphs = []
    graph_rows = []
    for index, (row, mapped) in enumerate(zip(native, mapping)):
        frame = mapped['native_frame']
        time_s = mapped['time_s']
        x, y = row['pedestrian_xy_m']
        speed_mps = 0 if index == 0 else 1.0
        trace.append({'frame': frame, 'time_s': time_s,
                      'position': {'x': x, 'y': y, 'z': .5},
                      'position_m': [x, y, .5], 'heading_deg': 90,
                      'speed_mps': speed_mps, 'speed_mph': speed_mps / .44704,
                      'speed_provenance': 'synthetic_native_sample',
                      'control': {'throttle': 0, 'brake': 0}})
        evidence.append({'original_frame': frame, 'recording_time_s': time_s,
                         'replay_frame': frame, 'replay_simulation_time_s': time_s,
                         'actor_id': 17,
                         'ego': {'position_m': [x, y, .5], 'heading_deg': 90,
                                 'body_vertices_m': [[x+dx, y+dy, z]
                                   for z in (0, 1.7) for dx in (-.25, .25)
                                   for dy in (-.25, .25)],
                                 'speed_mps': speed_mps,
                                 'speed_provenance': 'synthetic_native_sample'},
                         'world': {'weather': {'cloudiness': 0, 'precipitation': 0,
                                               'wetness': 0, 'fog_density': 0}}})
        graph_path = f'capture/native/graphs/base/{frame:08d}.adapter.json'
        graphs.append({'path': graph_path,
            'attributes': {'frame': frame, 'simulation_time_s': time_s,
                           'synthetic_diagnostic': True},
            'nodes': [{'id': 'ego', 'attributes': {'sem_class': 'ego', 'entity_id': 17,
                        'vertex': [x, y, .5], 'forward': [0, 1, 0],
                        'threedbbox': [[x-.25,y-.25,0],[x+.25,y-.25,0],
                                       [x-.25,y+.25,1.7],[x+.25,y+.25,1.7]]}}],
            'edges': []})
        graph_rows.append({'frame': frame, 'simulation_time': time_s,
            'adapter_graph': f'graphs/base/{frame:08d}.adapter.json',
            'base': f'graphs/base/{frame:08d}.adapter.json', 'nodes': 1, 'edges': 0})
    files = OUT / 'sources'
    write_rows(files / 'c111331-native-samples.jsonl', native)
    write_rows(files / 'video_frames.jsonl', mapping)
    write_rows(files / 'trace.jsonl', trace)
    write_rows(files / 'capture/evidence.jsonl', evidence)
    write_rows(files / 'capture/native/frames.jsonl', graph_rows)
    (files / 'road.xodr').unlink(missing_ok=True)
    (files / 'capture/recorder_info.txt').write_text('Create 17: walker.pedestrian.synthetic\n')
    capture = {'extraction_confirmed': True, 'frames': 600,
               'synthetic_diagnostic': True,
               'sources': {'trace.jsonl': sha(files / 'trace.jsonl'),
                           'road.xodr': sha(HERE / 'native/road.xodr')}}
    (files / 'capture/manifest.json').write_text(json.dumps(capture) + '\n')
    source_items = []
    for path in sorted(files.rglob('*')):
        if path.is_file():
            assert path.stat().st_size <= 2 * 1024 * 1024
            source_items.append({'path': str(path.relative_to(files)),
                                 'source': str(path.relative_to(ROOT)), 'sha256': sha(path)})
    videos = [{'path': name + '.mkv', 'frames': 600, 'width': width,
               'height': height, 'fps': 20, 'color': 'black'}
              for name, width, height in (('overview', 1920, 1080),
                ('approach', 1280, 720), ('reference_corner', 1280, 720),
                ('driver_reference', 1280, 720))]
    generator_path = OUT / 'generator.json'
    generator_path.write_text(json.dumps({'files': {}, 'graphs': graphs, 'videos': videos},
                                         separators=(',', ':')) + '\n')
    assert generator_path.stat().st_size <= 2 * 1024 * 1024
    recipe_path = OUT / 'recipe.json'
    recipe_path.write_text(json.dumps({'format': 'worker-fixture-recipe',
        'sources': source_items,
        'generator': {'source': str(generator_path.relative_to(ROOT)),
                      'sha256': sha(generator_path)}}, indent=2) + '\n')
    contract = {'format': 'worker-measurement-contract', 'case_id': config['case_id'],
        'requirements': [{'disposition_index': 0, 'requirement': 'NRS-484B-307-2b',
            'source': 'NRS 484B.307(2)(b)', 'output_key': 'pedestrian_entry_signal',
            'method': 'measure', 'value_type': 'object', 'kind': 'measured',
            'inputs': ['c111331-native-samples.jsonl', 'video_frames.jsonl']}],
        'negative': {'remove': ['c111331-native-samples.jsonl'],
                     'error_contains': 'Missing required source: c111331-native-samples.jsonl'}}
    (OUT / 'measurement-contract.json').write_text(json.dumps(contract, indent=2) + '\n')
    proposal_dir = HERE / 'proposals'
    proposal_dir.mkdir(exist_ok=True)
    plan = json.loads((HERE / 'case-plan.json').read_text())
    proposal = next(item for item in plan['cases'] if item['case_id'] == config['case_id'])
    (proposal_dir / 'cases.json').write_text(json.dumps({'cases': [proposal]}, indent=2) + '\n')
    runtime_sha = sha(ROOT / 'runtime/pipeline/SOURCE-MANIFEST.json')
    manifest = {'format': 'worker-execution-manifest', 'assignment_id': HERE.name,
        'runtime_manifest_sha256': runtime_sha,
        'status': 'unselected_current_v2_cpu_primary_proof',
        'cases': [{'case_id': config['case_id'], 'kind': 'unselected_cpu_diagnostic',
            'construction': str(construction_path.relative_to(HERE)),
            'construction_sha256': sha(construction_path), 'candidates': [],
            'measurement_contract': str((OUT / 'measurement-contract.json').relative_to(HERE)),
            'measurement_procedure': {'entrypoint': 'finalize.py',
                                      'output_schema': 'c111331-saved-analysis-v2'},
            'fixture_recipe': str(recipe_path.relative_to(ROOT))}]}
    manifest_path = HERE / 'v2-primary-manifest.json'
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'case': config['case_id'], 'construction_sha256': sha(construction_path),
                      'manifest_sha256': sha(manifest_path), 'recipe_sha256': sha(recipe_path),
                      'generator_sha256': sha(generator_path), 'sources': len(source_items),
                      'graphs': len(graphs)}))


if __name__ == '__main__':
    main()
