"""Build source-inventoried, text-only 900-frame caravan software fixtures."""
import hashlib
import json
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
REPO = PACKAGE.parents[1]
STAGE = REPO / '.runtime-work/c160013-comparison-proof'


def encoded(value):
    return json.dumps(value, separators=(',', ':'), allow_nan=False)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def lines(rows):
    return ''.join(encoded(row) + '\n' for row in rows)


def build(label, suffix):
    construction = json.loads((PACKAGE / 'cases' / (suffix + '-construction.json')).read_text())
    embedded = {entry['path']: entry['content'] for entry in construction['files']}
    config = json.loads(embedded['config.json'])
    source = STAGE / label
    history = [json.loads(line) for line in (source / 'caravan_history.jsonl').read_text().splitlines()]
    frames = [json.loads(line) for line in (source / 'video_frames.jsonl').read_text().splitlines()]
    context = json.loads((source / 'road_context.json').read_text())
    for key in ('business_district_source', 'caravan_membership_source', 'route_source', 'lane_source'):
        name = key + '.txt'
        context[key]['sha256'] = hashlib.sha256(embedded[name].encode()).hexdigest()
    traces, evidence, native_frames, graphs = [], [], [], []
    for row, frame in zip(history, frames):
        rear, front = row['caravan_members'][:2]
        entrant = row['entering_vehicle']
        ey = sum(vertex[1] for vertex in entrant['body_vertices_xy_m']) / 4
        row['participants'] = {
            'rear': {'actor_id': rear['actor_id'], 'body_vertices_m': rear['body_vertices_xy_m']},
            'subject': {'actor_id': front['actor_id'], 'body_vertices_m': front['body_vertices_xy_m']},
            'entrant': {'actor_id': entrant['actor_id'], 'body_vertices_m': entrant['body_vertices_xy_m'],
                        'lane_id': -1 if ey > -1.5 else -2}}
        frame['native_frame'] = frame['carla_frame']
        x = sum(vertex[0] for vertex in front['body_vertices_xy_m']) / 4
        traces.append({'frame': row['frame'], 'time_s': row['time_s'],
                       'position': {'x': x, 'y': 0, 'z': .3},
                       'position_m': [x, 0, .3], 'heading_deg': 0, 'speed_mps': .2,
                       'speed_mph': .2 / .44704})
        packet = {'frame': row['frame'], 'time_s': row['time_s'], 'devices': [],
                  'participants': [{'actor_id': front['actor_id'], 'blueprint': front['blueprint_id'],
                                    'position_m': [x, 0, .3], 'heading_deg': 0, 'speed_mps': .2,
                                    'speed_provenance': 'synthetic_native_sample',
                                    'velocity_mps': [.2, 0, 0], 'body_vertices_m': front['body_vertices_xy_m']}],
                  'relations': [], 'map_context': {}}
        evidence.append({'original_frame': row['frame'], 'replay_frame': row['frame'],
                         'actor_id': front['actor_id'], 'recording_time_s': row['time_s'],
                         'replay_simulation_time_s': row['time_s'],
                         'ego': {'position_m': [x, 0, .3], 'heading_deg': 0, 'speed_mps': .2,
                                 'speed_provenance': 'synthetic_native_sample',
                                 'body_vertices_m': front['body_vertices_xy_m']},
                         'world': {}, 'original_observations': packet, 'timing': {},
                         'visibility': None, 'supporting_only': {}})
        base = 'graphs/base/%08d.adapter.json' % row['frame']
        abstract = 'graphs/abstract/%08d.adapter.json' % row['frame']
        native_frames.append({'frame': row['frame'], 'simulation_time': row['time_s'],
                              'base': base, 'abstract': abstract, 'nodes': 0, 'edges': 0,
                              'extraction_seconds': 0, 'capture_seconds': 0,
                              'adapter_graph': base})
        for kind in ('base', 'abstract'):
            graphs.append({'path': 'capture/native/graphs/%s/%08d.adapter.json' % (kind, row['frame']),
                           'attributes': {'frame': row['frame'], 'simulation_time_s': row['time_s'],
                                          'units': {'position': 'm'}, 'observed_evidence': packet},
                           'nodes': [], 'edges': []})
    files = {
        'road_context.json': encoded(context) + '\n',
        'caravan_context.json': encoded({'diagnostic': True, 'source': 'synthetic structural fixture'}) + '\n',
        'caravan_history.jsonl': lines(history), 'video_frames.jsonl': lines(frames),
        'trace.jsonl': lines(traces), 'capture/evidence.jsonl': lines(evidence),
        'capture/native/frames.jsonl': lines(native_frames),
        'capture/recorder_info.txt': 'Synthetic diagnostic recording; no CARLA execution.\n',
        'capture/manifest.json': encoded({'status': 'draft', 'acquisition': 'synthetic_diagnostic',
                                         'case_id': config['selected_case_id'], 'map': 'FixtureMap',
                                         'frames': 900, 'required_observations': config['required_atoms'],
                                         'extraction_confirmed': True, 'sources': {}}) + '\n',
    }
    videos = [{'path': camera['name'] + '.mkv', 'frames': 900,
               'width': camera['width'], 'height': camera['height'], 'fps': 20, 'color': 'blue'}
              for camera in config['cameras']]
    videos.extend([{'path': name + '.mkv', 'frames': 900,
                    'width': 1280, 'height': 720, 'fps': 20, 'color': 'blue'}
                   for name in ('approach', 'reference_corner')])
    fixture_sources = PACKAGE / 'cases' / 'fixtures' / label
    fixture_sources.mkdir(parents=True, exist_ok=True)
    sources = []
    for target, contents in files.items():
        source_path = fixture_sources / target
        source_path.parent.mkdir(parents=True, exist_ok=True)
        source_path.write_text(contents)
        if source_path.stat().st_size > 2 * 1024 * 1024:
            raise ValueError('Fixture source exceeds return file limit: ' + target)
        sources.append({'path': target, 'source': source_path.relative_to(REPO).as_posix(),
                        'sha256': sha(source_path)})
    spec_path = PACKAGE / 'cases' / (label + '-diagnostic.json')
    spec_path.write_text(json.dumps({'files': {}, 'graphs': graphs, 'videos': videos},
                                    separators=(',', ':')) + '\n')
    if spec_path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError('Diagnostic specification exceeds return file limit')
    relative = spec_path.relative_to(REPO).as_posix()
    recipe_path = PACKAGE / 'cases' / (label + '-recipe.json')
    recipe_path.write_text(json.dumps({'format': 'worker-fixture-recipe',
                                       'sources': sources,
                                       'generator': {'source': relative, 'sha256': sha(spec_path)}},
                                      indent=2) + '\n')
    return spec_path.stat().st_size


if __name__ == '__main__':
    print({'wide': build('wide', 'entrant_can_occupy_gap'),
           'narrow': build('narrow', 'entrant_cannot_occupy_gap')})
