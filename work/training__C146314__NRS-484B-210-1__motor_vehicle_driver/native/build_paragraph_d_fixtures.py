"""Author source-bound full-view CPU fixture recipes for the paragraph (d) pair.

Every emitted scene fact is labelled synthetic. These fixtures are diagnostic
software inputs, never evidence that a CARLA world was executed.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
CASE = HERE.parent
ROOT = CASE.parents[1]
OUT = HERE / 'selected-paragraph-d'
MANIFEST = OUT / 'manifest.json'
MEDIA = [('overview', 1920, 1080, 'blue',
          '1cdd04df78e0012d5e9fb9a7e0a00671f5783ac43a07f1e491487c79663929bc'),
         ('approach', 1280, 720, 'green',
          '848bfb217a9f4da160047d02e49a608091a27c7aad2295ceb606bd52e9b20a55'),
         ('reference_corner', 1280, 720, 'white',
          '6a2b9cca57ef92a31494d1f299b708138f8aaf2b8f959d819013b5d830cbe3b2'),
         ('driver_reference', 1280, 720, 'red',
          'ce1aa5673980b002069ea27de2caccd0f987f88091e53a15851b32ed6675b5ce')]
sys.path.insert(0, str(HERE))
import prove_current_primary_saved
import prove_current_contrast_saved


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def lines(rows):
    return ''.join(encoded(row) + '\n' for row in rows)


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(encoded(value) + '\n')


def graph_node(name, actor, entity_id):
    return {'id': name, 'attributes': {'entity_id': entity_id,
        'sem_class': name, 'vertex': actor['center_native_xyz_m'],
        'forward': [1, 0, 0], 'threedbbox': actor['body_native_xyz_m']}}


def build_one(suffix, proof, media_root, scratch):
    case_id = CASE.name + '__' + suffix
    materialized = scratch / suffix
    env = dict(os.environ)
    env['PYTHONPATH'] = str(ROOT / 'runtime/scenario_pipeline')
    subprocess.run([str(ROOT / '.venv-cpu/bin/python'), str(ROOT / 'runtime.py'),
        'materialize', '--manifest', str(MANIFEST), '--case', case_id,
        '--output', str(materialized)], cwd=ROOT, env=env,
        capture_output=True, text=True, check=True, timeout=300)
    proof.BUNDLE = materialized
    proof.fixture(materialized)
    raw = [json.loads(row) for row in
           (materialized / 'native-raw-actors.jsonl').read_text().splitlines()]
    frame_map = [json.loads(row) for row in
                 (materialized / 'video_frames.jsonl').read_text().splitlines()]
    for row in frame_map:
        row['source_rgb_sha256'] = {name: digest for name, _, _, _, digest in MEDIA}
        row['views'] = [name for name, _, _, _, _ in MEDIA]
    video_text = lines(frame_map)
    video_sha = hashlib.sha256(video_text.encode()).hexdigest()
    review = json.loads((materialized / 'source-review.json').read_text())
    review['video_frames_sha256'] = video_sha
    review['media_sha256'] = {name + '.mkv': sha(media_root / (name + '.mkv'))
                               for name, _, _, _, _ in MEDIA}
    trace, evidence, native_frames, graphs = [], [], [], []
    for actor, frame in zip(raw, frame_map):
        index = actor['frame']
        native_frame = actor['native_frame']
        t = actor['time_s']
        ego = actor['ego']
        lead = actor['lead']
        position = ego['center_native_xyz_m']
        trace.append({'frame': native_frame, 'time_s': t,
            'position': {'x': position[0], 'y': position[1], 'z': position[2]},
            'position_m': position, 'heading_deg': ego['yaw_deg'],
            'speed_mps': ego['speed_mps'],
            'speed_mph': ego['speed_mps'] * 2.2369362921,
            'velocity_mps': ego['velocity_native_xyz_mps'],
            'control': {'throttle': .2, 'brake': 0, 'hand_brake': False}})
        participants = {'lead': {'actor_id': lead['actor_id'],
            'body_vertices_m': lead['body_native_xyz_m'],
            'position_m': lead['center_native_xyz_m']}}
        if actor.get('obstruction') is not None:
            cone = actor['obstruction']
            participants['obstruction'] = {'actor_id': cone['actor_id'],
                'body_vertices_m': cone['body_native_xyz_m'],
                'position_m': cone['center_native_xyz_m']}
        evidence.append({'actor_id': ego['actor_id'],
            'original_frame': native_frame, 'replay_frame': native_frame,
            'recording_time_s': t, 'replay_simulation_time_s': t,
            'ego': {'body_vertices_m': ego['body_native_xyz_m'],
                'position_m': position, 'heading_deg': ego['yaw_deg'],
                'speed_mps': ego['speed_mps'],
                'speed_provenance': 'synthetic_native_sample',
                'synthetic_diagnostic': True},
            'participants': participants,
            'world': {'road_projection': {'road_id': 210,
                'lane_id': actor['observed_ego_lane_id'],
                's_m': position[0], 'section_id': 0}}})
        graph_name = f'graphs/base/{native_frame:08d}.adapter.json'
        nodes = [graph_node('ego', ego, ego['actor_id']),
                 graph_node('lead', lead, lead['actor_id'])]
        if actor.get('obstruction') is not None:
            nodes.append(graph_node('obstruction', actor['obstruction'],
                                    actor['obstruction']['actor_id']))
        graphs.append({'path': 'capture/native/' + graph_name,
            'attributes': {'frame': native_frame, 'simulation_time_s': t,
                'synthetic_diagnostic': True},
            'nodes': nodes, 'edges': []})
        native_frames.append({'adapter_graph': graph_name, 'base': graph_name,
            'edges': 0, 'frame': native_frame, 'nodes': len(nodes),
            'simulation_time': t})
    trace_text = lines(trace)
    road_source = HERE / 'one-way-pass.xodr'
    raw_source = OUT / suffix / 'fixture-native-raw-actors.jsonl'
    raw_source.write_text((materialized / 'native-raw-actors.jsonl').read_text())
    files = {
        'video_frames.jsonl': video_text,
        'native-map-readback.json': (materialized / 'native-map-readback.json').read_text(),
        'native-capture-report.json': (materialized / 'native-capture-report.json').read_text(),
        'review-source.json': encoded(review) + '\n',
        'trace.jsonl': trace_text,
        'capture/evidence.jsonl': lines(evidence),
        'capture/native/frames.jsonl': lines(native_frames),
        'capture/manifest.json': encoded({'extraction_confirmed': True,
            'frames': 600, 'synthetic_diagnostic': True,
            'sources': {'road.xodr': sha(road_source), 'road-source.xodr': sha(road_source),
                'trace.jsonl': hashlib.sha256(trace_text.encode()).hexdigest()}}) + '\n',
        'capture/recorder_info.txt': 'Synthetic C146314 CPU diagnostic; no CARLA recorder\nCreate ' + str(raw[0]['ego']['actor_id']) + ': vehicle.tesla.model3 (0) at (0, 0, 0)\n',
    }
    videos = [{'path': name + '.mkv', 'frames': 600, 'width': width,
               'height': height, 'fps': 20, 'color': color}
              for name, width, height, color, _ in MEDIA]
    spec = {'files': files, 'graphs': graphs, 'videos': videos}
    spec_path = OUT / suffix / 'fixture-spec.json'
    put(spec_path, spec)
    if spec_path.stat().st_size > 2097152:
        raise ValueError('Fixture specification exceeds returned file size limit')
    recipe = {'format': 'worker-fixture-recipe',
        'sources': [{'path': 'road.xodr', 'source': str(road_source.relative_to(ROOT)), 'sha256': sha(road_source)}, {'path': 'road-source.xodr',
            'source': str(road_source.relative_to(ROOT)),
            'sha256': sha(road_source)},
            {'path': 'native-raw-actors.jsonl',
             'source': str(raw_source.relative_to(ROOT)),
             'sha256': sha(raw_source)}],
        'generator': {'source': str(spec_path.relative_to(ROOT)),
            'sha256': sha(spec_path)}}
    recipe_path = OUT / suffix / 'fixture-recipe.json'
    put(recipe_path, recipe)
    return {'case_id': case_id, 'fixture_spec_sha256': sha(spec_path),
            'fixture_recipe_sha256': sha(recipe_path),
            'fixture_spec_bytes': spec_path.stat().st_size}


def build(media_root):
    media_root = Path(media_root).resolve()
    for name, _, _, _, _ in MEDIA:
        if not (media_root / (name + '.mkv')).is_file():
            raise FileNotFoundError('Generate diagnostic media first: ' + name)
    scratch = Path(os.environ.get('TMPDIR', '')).resolve()
    if ROOT / '.runtime-work' not in scratch.parents:
        raise ValueError('TMPDIR must be under .runtime-work')
    with tempfile.TemporaryDirectory(dir=scratch, prefix='fixture-author-') as name:
        base = Path(name)
        return [build_one('witness_1', prove_current_primary_saved, media_root, base),
                build_one('witness_2', prove_current_contrast_saved, media_root, base)]


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('usage: build_paragraph_d_fixtures.py MEDIA_ROOT')
    print(json.dumps(build(sys.argv[1]), sort_keys=True))
