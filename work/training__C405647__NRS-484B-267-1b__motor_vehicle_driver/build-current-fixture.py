"""Build source-inventoried 600-frame synthetic fixtures for active runtime."""
import hashlib
import json
import os
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE / 'native'))
from prove_saved import packet, save


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_rows(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(row, separators=(',', ':')) + '\n' for row in rows))


def build(suffix):
    source = HERE / 'current-fixture' / suffix
    source.mkdir(parents=True, exist_ok=True)
    scope, actors = packet(suffix, 'primary')
    save(source, scope, actors)
    (source / 'source-scope.json').replace(source / 'context-scope.json')
    trace, mapping, evidence, frames, participants, graphs = [], [], [], [], [], []
    for index, actor in enumerate(actors):
        native_frame, time = actor['native_frame'], actor['time_s']
        subject, approach = actor['subject'], actor['approach']
        sx, sy = subject['center_xy_m'][0], -subject['center_xy_m'][1]
        ax, ay = approach['center_xy_m'][0], -approach['center_xy_m'][1]
        body = [[x, -y, z] for x, y in subject['body_xy_m'] for z in (0, 1.5)]
        approach_body = [[ax + dx, ay + dy, z] for dx in (-2.25, 2.25)
                         for dy in (-.9, .9) for z in (0, 1.5)]
        speed = subject['speed_mps']
        trace.append({'frame': native_frame, 'time_s': time,
                      'position': {'x': sx, 'y': sy, 'z': .5},
                      'position_m': [sx, sy, .5], 'heading_deg': 0,
                      'speed_mps': speed, 'speed_mph': speed / .44704,
                      'velocity_mps': [speed, 0, 0],
                      'control': {'throttle': .3, 'brake': 0, 'hand_brake': False}})
        mapping.append({'video_frame': index, 'carla_frame': native_frame,
                        'native_frame': native_frame, 'time_s': time})
        participants.append({'time_s': time, 'value': {
            'frame': native_frame, 'subject': {'actor_id': 107},
            'approach': {'actor_id': 108}}})
        evidence.append({'original_frame': native_frame, 'replay_frame': native_frame,
                         'actor_id': 107, 'recording_time_s': time,
                         'replay_simulation_time_s': time,
                         'ego': {'position_m': [sx, sy, .5], 'heading_deg': 0,
                                 'speed_mps': speed,
                                 'speed_provenance': 'synthetic_native_sample',
                                 'body_vertices_m': body},
                         'world': {'weather': {'cloudiness': 0, 'precipitation': 0,
                                               'wetness': 0, 'fog_density': 0},
                                   'road_projection': {'road_id': 1, 'section_id': 0,
                                                       'lane_id': -1, 's_m': sx + 40}}})
        name = f'{native_frame:08d}'
        graphs.append({'path': f'capture/native/graphs/base/{name}.adapter.json',
                       'attributes': {'frame': native_frame, 'simulation_time_s': time,
                                      'synthetic_diagnostic': True},
                       'nodes': [
                           {'id': 'ego', 'attributes': {'sem_class': 'ego', 'entity_id': 107,
                                                      'vertex': [sx, sy, .5],
                                                      'forward': [1, 0, 0], 'threedbbox': body}},
                           {'id': 'approach', 'attributes': {'sem_class': 'vehicle', 'entity_id': 108,
                                                           'vertex': [ax, ay, .5],
                                                           'forward': [1, 0, 0],
                                                           'threedbbox': approach_body}}],
                       'edges': []})
        frames.append({'frame': native_frame, 'simulation_time': time, 'time_s': time,
                       'base': f'graphs/base/{name}.adapter.json',
                       'abstract': f'graphs/abstract/{name}.pkl',
                       'adapter_graph': f'graphs/base/{name}.adapter.json',
                       'synthetic_diagnostic': True})
    assert len(actors) == len(trace) == len(evidence) == 600
    write_rows(source / 'trace.jsonl', trace)
    write_rows(source / 'video_frames.jsonl', mapping)
    write_rows(source / 'synchronized_motion_records.jsonl', participants)
    write_rows(source / 'capture/evidence.jsonl', evidence)
    write_rows(source / 'capture/native/frames.jsonl', frames)
    (source / 'road.xodr').write_bytes((HERE / 'native/drafts/road.xodr').read_bytes())
    (source / 'capture/recorder_info.txt').write_text('Create 107: vehicle.lincoln.mkz_2020\n')
    (source / 'capture/manifest.json').write_text(json.dumps({
        'extraction_confirmed': True, 'frames': 600,
        'acquisition': 'synthetic_diagnostic', 'observation_contract_version': 2,
        'required_observations': ['rel.same_direction', 'rel.surface_gap',
                                  'kin.position', 'rel.occupies'],
        'sources': {'road.xodr': sha(source / 'road.xodr'),
                    'trace.jsonl': sha(source / 'trace.jsonl')},
        'synthetic_diagnostic': True}, separators=(',', ':')) + '\n')
    (source / 'acquisition-provenance.json').write_text(json.dumps({
        'provenance_kind': 'synthetic_local_diagnostic',
        'diagnostic_fixture': True, 'native_executed': False}) + '\n')
    files = []
    for path in sorted(source.rglob('*')):
        if path.is_file() and path.name != 'road.xodr':
            rel = path.relative_to(source).as_posix()
            files.append({'path': rel, 'source': path.relative_to(ROOT).as_posix(),
                          'sha256': sha(path)})
    diagnostic = {'files': {}, 'graphs': graphs,
                  'videos': [{'path': name + '.mkv', 'frames': 600, 'width': width,
                              'height': height, 'fps': 20, 'color': color}
                             for name, width, height, color in (
                                 ('overview', 1920, 1080, 'blue'),
                                 ('approach', 1280, 720, 'red'),
                                 ('reference_corner', 1280, 720, 'green'),
                                 ('driver_reference', 1280, 720, 'white'))]}
    spec = HERE / f'current-{suffix}-diagnostic.json'
    spec.write_text(json.dumps(diagnostic, separators=(',', ':')) + '\n')
    recipe = {'format': 'worker-fixture-recipe', 'sources': files,
              'generator': {'source': spec.relative_to(ROOT).as_posix(),
                            'sha256': sha(spec)}}
    target = HERE / f'current-{suffix}-recipe.json'
    target.write_text(json.dumps(recipe, indent=2) + '\n')
    print(json.dumps({'case': suffix, 'sources': len(files), 'graphs': len(graphs),
                      'recipe_sha256': sha(target)}))


if __name__ == '__main__':
    output = Path(os.environ.get('SCENARIO_PIPELINE_OUTPUT_ROOT', '/'))
    if (ROOT / '.runtime-work') not in output.resolve().parents:
        raise SystemExit('Set SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work')
    for case in ('reference', 'contrast'):
        build(case)
