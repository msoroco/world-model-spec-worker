"""Build source-hashed four-view diagnostic fixtures for selected stand candidates."""
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
sys.path.insert(0, str(ROOT/'native'))
import fixture_raw


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def encode(value):
    return json.dumps(value, separators=(',', ':'), allow_nan=False)+'\n'


def lines(rows):
    return ''.join(encode(row) for row in rows)


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(encode(value))


def build_candidate(witness, candidate):
    source = ROOT/'selected-all'/witness/candidate/'construction.json'
    construction = json.loads(source.read_text())
    with tempfile.TemporaryDirectory(dir=REPO/'.runtime-work',
                                     prefix='c135709-recipe-') as temp:
        base = Path(temp)
        bundle = base/'bundle'
        bundle.mkdir()
        for item in construction['files']:
            path = bundle/item['path']
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(item['content'])
        raw = base/'raw'
        fixture_raw.generate(bundle, raw)
        actors = [json.loads(s) for s in (raw/'native-raw-actors.jsonl').read_text().splitlines()]
        mapping = [json.loads(s) for s in (raw/'video_frames.jsonl').read_text().splitlines()]
        reviews = [json.loads(s) for s in (raw/'stand-review.jsonl').read_text().splitlines()]
        for i, (actor, frame, review) in enumerate(zip(actors, mapping, reviews)):
            actor['native_frame'] = i
            actor['time_s'] = i/20
            frame.update(carla_frame=i, native_frame=i, time_s=i/20,
                         synthetic_frame_only=True)
            review['native_frame'] = i
            review['time_s'] = i/20
        trace = []
        capture_evidence = []
        capture_frames = []
        graphs = []
        for i, actor in enumerate(actors):
            ego = actor['ego']
            position = ego['center_native_xyz_m']
            body = ego['body_native_xyz_m']
            speed = ego['speed_mps']
            participant = {'actor_id': ego['actor_id'],
                'blueprint': ego['blueprint'], 'body_vertices_m': body,
                'heading_deg': ego['yaw_deg'],
                'velocity_mps': ego['velocity_native_xyz_mps'],
                'speed_mps': speed, 'accel_longitudinal_mps2': 0.0}
            observation = {'frame': i, 'time_s': i/20,
                'participants': [participant],
                'world_settings': {'no_rendering_mode': False},
                'rgb_sensors': {name: {'frame': i} for name in
                    ('overview', 'approach', 'reference_corner', 'driver_reference')}}
            trace.append({'frame': i, 'time_s': i/20,
                'position': dict(zip(('x', 'y', 'z'), position)),
                'position_m': position, 'heading_deg': ego['yaw_deg'],
                'speed_mps': speed, 'speed_mph': speed*2.2369362921,
                'velocity_mps': ego['velocity_native_xyz_mps'],
                'control': {'throttle': 0.0, 'brake': 0.0, 'hand_brake': False}})
            capture_evidence.append({'original_frame': i, 'replay_frame': i,
                'actor_id': ego['actor_id'], 'recording_time_s': i/20,
                'replay_simulation_time_s': i/20,
                'ego': {'position_m': position, 'heading_deg': ego['yaw_deg'],
                    'speed_mps': speed, 'speed_provenance': 'synthetic_native_sample',
                    'body_vertices_m': body},
                'world': {'weather': {'cloudiness': 0, 'precipitation': 0,
                    'wetness': 0, 'fog_density': 0},
                    'road_projection': {'road_id': actor['observed_road_id'],
                        'section_id': 0, 'lane_id': actor['observed_lane_id'],
                        's_m': max(0, position[0])}},
                'original_observations': observation})
            graph_name = f'graphs/base/{i:08d}.pkl'
            capture_frames.append({'frame': i, 'time_s': i/20,
                'simulation_time': i/20, 'base': graph_name})
            graphs.append({'path': 'capture/native/'+graph_name,
                'attributes': {'frame': i, 'observed_evidence': observation},
                'nodes': [], 'edges': []})
        files = {
            'road.xodr': (bundle/'stand-road.xodr').read_text(),
            'trace.jsonl': lines(trace),
            'video_frames.jsonl': lines(mapping),
            'native-raw-actors.jsonl': lines(actors),
            'stand-review.jsonl': lines(reviews),
            'native-map-readback.json': (raw/'native-map-readback.json').read_text(),
            'native-capture-report.json': (raw/'native-capture-report.json').read_text(),
            'capture/evidence.jsonl': lines(capture_evidence),
            'capture/native/frames.jsonl': lines(capture_frames),
            'capture/recorder_info.txt': 'Synthetic CPU diagnostic; no CARLA recorder ran.\n',
            'acquisition-provenance.json': encode({
                'provenance_kind': 'synthetic_fixture',
                'diagnostic_fixture': True, 'native_executed': False}),
        }
        files['capture/manifest.json'] = encode({
            'extraction_confirmed': True, 'frames': 240,
            'acquisition': 'synthetic_cpu_fixture',
            'observation_contract_version': 2,
            'required_observations': ['kin.position', 'kin.heading', 'rel.occupies'],
            'sources': {'road.xodr': sha(bundle/'stand-road.xodr'),
                        'trace.jsonl': hashlib.sha256(files['trace.jsonl'].encode()).hexdigest()}})
        videos = [{'path': name+'.mkv', 'frames': 240,
            'width': 1920 if name == 'overview' else 1280,
            'height': 1080 if name == 'overview' else 720,
            'fps': 20, 'color': color}
            for name, color in (('overview', 'blue'), ('approach', 'green'),
                                ('reference_corner', 'white'),
                                ('driver_reference', 'red'))]
        spec = {'files': files, 'graphs': graphs, 'videos': videos}
        spec_path = ROOT/'selected-diagnostics'/witness/(candidate+'.json')
        write(spec_path, spec)
        relative = spec_path.relative_to(REPO).as_posix()
        recipe = {'format': 'worker-fixture-recipe',
            'sources': [{'path': 'diagnostic-source.json',
                         'source': relative, 'sha256': sha(spec_path)}],
            'generator': {'source': relative, 'sha256': sha(spec_path)}}
        recipe_path = ROOT/'selected-diagnostics'/witness/(candidate+'-recipe.json')
        write(recipe_path, recipe)
        return {'case': witness, 'candidate': candidate,
                'spec_bytes': spec_path.stat().st_size,
                'spec_sha256': sha(spec_path), 'recipe_sha256': sha(recipe_path)}


def build_manifest():
    source = json.loads((ROOT/'selected-all/draft-manifest.json').read_text())
    for entry in source['cases']:
        witness = entry['case_id'].split('__')[-1]
        entry['construction'] = 'selected-all/'+entry['construction']
        for candidate in entry['candidates']:
            candidate['construction'] = 'selected-all/'+candidate['construction']
        entry['measurement_contract'] = 'selected-measurement-contracts/'+witness+'.json'
        entry['measurement_procedure'] = {
            'entrypoint': 'finalize_selected.py',
            'output_schema': 'c135709-selected-saved-diagnostic-v1'}
        entry['fixture_recipe'] = ('work/'+ROOT.name+
            '/selected-diagnostics/'+witness+'/primary-recipe.json')
    path = ROOT/'execution-manifest-draft.json'
    write(path, source)
    return sha(path)


if __name__ == '__main__':
    items = [build_candidate(w, c) for w in ('reference', 'contrast')
             for c in ('primary', 'fallback1', 'fallback2', 'fallback3')]
    print(json.dumps({'diagnostics': items,
                      'draft_manifest_sha256': build_manifest()}, indent=2))
