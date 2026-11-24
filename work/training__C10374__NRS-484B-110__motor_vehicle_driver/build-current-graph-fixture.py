"""Inventory retained zone sources and generate live 600-frame adapter graphs.

The output is a synthetic software fixture and never establishes a designated
safety zone, original CARLA motion, or a legal result.
"""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ZONE = HERE / 'native' / 'zone'
COUNT = 600


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def main():
    outputs = []
    for condition in ('condition_a', 'condition_b'):
      for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
        suffix = 'selected_c5852cfd__' + condition
        raw = ZONE / 'offline' / 'raw-fixtures' / suffix / candidate
        bundle = ZONE / 'drafts' / suffix / candidate
        actors = rows(raw / 'native-raw-actors.jsonl')
        frames = rows(raw / 'video_frames.jsonl')
        request = rows(bundle / 'requested-tracks.jsonl')
        if not len(actors) == len(frames) == len(request) == COUNT:
            raise ValueError('Exact 600-frame retained zone source missing')
        source_names = ('native-map-readback.json', 'native-raw-actors.jsonl',
                        'video_frames.jsonl', 'frame-review.jsonl',
                        'native-capture-report.json')
        source_items = [{'path': name,
                         'source': (raw / name).relative_to(ROOT).as_posix(),
                         'sha256': sha(raw / name)} for name in source_names]
        generator = {'files': {}, 'graphs': [], 'videos': []}
        native_frames = []
        trace = []
        evidence = []
        for index, (actor, frame, requested) in enumerate(zip(actors, frames, request)):
            if (actor['frame'] != index or frame['video_frame'] != index or
                    actor['native_frame'] != frame['native_frame'] or
                    actor['requested_ego_x_m'] != requested['requested_ego_x_m'] or
                    actor['requested_ego_y_m'] != requested['requested_ego_y_m']):
                raise ValueError('Retained zone actor/video/request join changed')
            native = actor['native_frame']
            graph_ref = f'graphs/base/{native:08d}.adapter.json'
            native_frames.append({'frame': native, 'time_s': actor['time_s'],
                                  'simulation_time': actor['time_s'],
                                  'adapter_graph': graph_ref,
                                  'synthetic_diagnostic': True})
            ego = actor['ego']
            trace.append({'frame': native, 'time_s': actor['time_s'],
                          'ego_x_m': ego['center_native_xyz_m'][0],
                          'ego_y_m': ego['center_native_xyz_m'][1],
                          'synthetic_diagnostic': True})
            evidence.append({'original_frame': native, 'replay_frame': native,
                             'actor_id': ego['actor_id'],
                             'recording_time_s': actor['time_s'],
                             'replay_simulation_time_s': actor['time_s'],
                             'ego': {'position_m': ego['center_native_xyz_m'],
                                     'speed_mps': ego['speed_mps'],
                                     'body_vertices_m': ego['body_native_xyz_m']},
                             'synthetic_diagnostic': True})
            generator['graphs'].append({
                'path': 'capture/native/' + graph_ref,
                'attributes': {'frame': native, 'time_s': actor['time_s'],
                               'synthetic_diagnostic': True,
                               'source': 'C10374 retained raw actor row'},
                'nodes': [{'id': 'ego', 'attributes': {
                    'sem_class': 'ego', 'entity_id': ego['actor_id'],
                    'vertex': ego['center_native_xyz_m'],
                    'forward': [1.0, 0.0, 0.0],
                    'threedbbox': ego['body_native_xyz_m'],
                    'carla_speed': ego['speed_mps']}}], 'edges': []})
        def as_jsonl(values):
            return ''.join(json.dumps(value, separators=(',', ':')) + '\n' for value in values)
        generator['files']['capture/native/frames.jsonl'] = as_jsonl(native_frames)
        generator['files']['trace.jsonl'] = as_jsonl(trace)
        generator['files']['capture/evidence.jsonl'] = as_jsonl(evidence)
        generator['files']['capture/manifest.json'] = json.dumps({
            'source_kind': 'synthetic_diagnostic', 'frames': COUNT,
            'rate_hz': 20, 'extraction_confirmed': True,
            'original_native_observed': False}) + '\n'
        generator['videos'] = [{'path': name + '.mkv', 'frames': COUNT,
                                'width': 32, 'height': 32, 'fps': 20,
                                'color': 'black'} for name in
                               ('forward', 'overview', 'reference_corner',
                                'driver_reference')]
        target = HERE / 'current-graph-fixture'
        target.mkdir(exist_ok=True)
        label = condition if candidate == 'primary' else condition + '-' + candidate
        spec = target / (label + '-generator.json')
        spec.write_text(json.dumps(generator, separators=(',', ':')) + '\n')
        if spec.stat().st_size > 2 * 1024 * 1024:
            raise ValueError('Generator specification exceeds returned-file limit')
        recipe = {'format': 'worker-fixture-recipe', 'sources': source_items,
                  'generator': {'source': spec.relative_to(ROOT).as_posix(),
                                'sha256': sha(spec)}}
        recipe_path = target / (label + '-recipe.json')
        recipe_path.write_text(json.dumps(recipe, indent=2) + '\n')
        outputs.append({'condition': condition, 'candidate': candidate,
                        'recipe_sha256': sha(recipe_path),
                        'generator_sha256': sha(spec), 'generator_bytes': spec.stat().st_size,
                        'source_count': len(source_items), 'graph_count': len(generator['graphs'])})
    receipt = {'format': 'c10374-live-graph-diagnostic-fixture-v1',
               'outputs': outputs, 'physical_acceptance_claimed': False,
               'legal_verdict_claimed': False}
    path = HERE / 'current-graph-fixture' / 'build-receipt.json'
    path.write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'receipt_sha256': sha(path), 'outputs': outputs}))


if __name__ == '__main__':
    main()
