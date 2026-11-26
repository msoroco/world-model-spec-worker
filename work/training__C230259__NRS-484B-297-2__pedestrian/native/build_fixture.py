"""Build bounded, source-hashed 600-frame diagnostics for the two exact cases."""

import hashlib
import json
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parents[1]
TEMPLATE = ROOT / 'work/training__C230222__LVMC-11-30-050__pedestrian/diagnostic/condition_a/generator.json'
CAMERAS = (('overview', 1920, 1080), ('approach', 1280, 720),
           ('reference_corner', 1280, 720), ('driver_reference', 1280, 720))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(value, str):
        path.write_text(value)
    else:
        path.write_text(json.dumps(value, indent=2) + '\n')


def line(rows):
    return ''.join(json.dumps(row, separators=(',', ':')) + '\n' for row in rows)


def build(side):
    directory = BASE / 'diagnostic' / side
    source = directory / 'sources'
    y = 4.0 if side == 'a' else -4.0
    context = {'source_kind': 'synthetic_diagnostic',
               'highway_authority_source': 'fixture:public-highway-context-only',
               'highway_boundary_source': 'fixture:survey-boundary-only',
               'sidewalk_inventory_source': 'fixture:no-sidewalk-only',
               'subsection_6_obstruction_source': 'fixture:no-sidewalk-traveler-obstruction-only',
               'traffic_route_source': 'fixture:eastbound-vehicle-only',
               'sidewalk_present': False, 'subsection_6_obstruction': False,
               'highway_half_width_m': 6.0, 'highway_centerline_anchor_xy_m': [0.0, 0.0],
               'traffic_direction_xy': [1.0, 0.0]}
    write(source / 'reviewed-road-source.json', context)
    write(source / 'road.xodr', '<OpenDRIVE><header revMajor="1" revMinor="4" name="C230259-synthetic-diagnostic-road" version="1" north="50" south="-50" east="50" west="-50"/><road id="1" name="diagnostic-highway" length="100" junction="-1"><link/><planView><geometry s="0" x="-50" y="0" hdg="0" length="100"><line/></geometry></planView><elevationProfile><elevation s="0" a="0" b="0" c="0" d="0"/></elevationProfile><lanes><laneOffset s="0" a="0" b="0" c="0" d="0"/><laneSection s="0"><left><lane id="1" type="driving" level="false"><width sOffset="0" a="3.5" b="0" c="0" d="0"/></lane></left><center><lane id="0" type="none" level="false"/></center><right><lane id="-1" type="driving" level="false"><width sOffset="0" a="3.5" b="0" c="0" d="0"/></lane></right></laneSection></lanes><objects/><signals/></road></OpenDRIVE>\n')
    write(source / 'acquisition-provenance.json', {
        'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True,
        'scope': 'Source-shaped software test; no original Native capture or physical verification'})
    graph_template = json.loads(TEMPLATE.read_text())['graphs'][0]
    graphs = []
    traces, frames, walking, evidence, graph_frames = [], [], [], [], []
    positions, speeds = [], []
    for index in range(600):
        frame = 100 + index
        time_s = index / 20
        x = 20.0 - index * .02
        position = [x, y, .5]
        velocity = [-.4, 0.0, 0.0]
        body = [[x + dx, y + dy, z] for dx, dy, z in
                ((-.12, -.12, 0), (-.12, -.12, 1.8), (.12, -.12, 0), (.12, -.12, 1.8),
                 (.12, .12, 0), (.12, .12, 1.8), (-.12, .12, 0), (-.12, .12, 1.8))]
        trace = {'frame': frame, 'time_s': time_s, 'position': dict(zip(('x', 'y', 'z'), position)),
                 'position_m': position, 'heading_deg': 180, 'velocity_mps': velocity,
                 'speed_mps': .4, 'speed_mph': .4 / .44704,
                 'speed_provenance': 'synthetic_fixture', 'control': {}, 'synthetic_diagnostic': True}
        traces.append(trace)
        frames.append({'video_frame': index, 'native_frame': frame, 'carla_frame': frame, 'time_s': time_s})
        walking.append({'source_kind': 'synthetic_diagnostic', 'video_frame': index,
                        'native_frame': frame, 'time_s': time_s, 'pedestrian_id': 17,
                        'vehicle_id': 18, 'pedestrian_xy_m': [x, y],
                        'vehicle_xy_m': [-30.0 + index * .04, -1.75],
                        'pedestrian_heading_xy': [-1.0, 0.0]})
        evidence.append({'original_frame': frame, 'recording_time_s': time_s,
                         'replay_frame': frame, 'replay_simulation_time_s': time_s,
                         'actor_id': 17, 'synthetic_diagnostic': True,
                         'ego': {'position_m': position, 'heading_deg': 180,
                                 'body_vertices_m': body, 'speed_mps': .4,
                         'speed_provenance': 'synthetic_native_sample'},
                         'world': {'weather': {'cloudiness': 0, 'precipitation': 0,
                                               'wetness': 0, 'fog_density': 0}}})
        graph = json.loads(json.dumps(graph_template))
        graph['path'] = f'capture/native/graphs/base/{frame:08d}.adapter.json'
        graph['attributes']['frame'] = frame
        graph['attributes']['simulation_time_s'] = time_s
        graph['nodes'][0]['attributes'].update(vertex=position, forward=[-1, 0, 0], threedbbox=body)
        graphs.append(graph)
        graph_frames.append({'frame': frame, 'time_s': time_s, 'simulation_time': time_s,
                             'adapter_graph': f'graphs/base/{frame:08d}.adapter.json',
                             'base': f'graphs/base/{frame:08d}.adapter.json', 'nodes': 1,
                             'edges': 0, 'synthetic_diagnostic': True})
        positions.append({'time_s': time_s, 'value': position})
        speeds.append({'time_s': time_s, 'value': .4})
    for name, rows in [('trace.jsonl', traces), ('video_frames.jsonl', frames),
                       ('walking-source.jsonl', walking), ('capture/evidence.jsonl', evidence),
                       ('capture/native/frames.jsonl', graph_frames),
                       ('channels/kin.position.jsonl', positions),
                       ('channels/kin.speed.jsonl', speeds)]:
        write(source / name, line(rows))
    write(source / 'capture/manifest.json', {
        'extraction_confirmed': True, 'frames': 600, 'synthetic_diagnostic': True,
        'sources': {'trace.jsonl': sha(source / 'trace.jsonl'),
                    'road.xodr': sha(source / 'road.xodr')}})
    write(source / 'capture/recorder_info.txt', 'Create 17: walker.pedestrian.synthetic\nSynthetic diagnostic recorder metadata only.\n')
    generator = {'files': {}, 'graphs': graphs,
                 'videos': [{'path': name + '.mkv', 'frames': 600, 'width': width,
                             'height': height, 'fps': 20, 'color': 'black'}
                            for name, width, height in CAMERAS]}
    write(directory / 'generator.json', generator)
    paths = sorted(path for path in source.rglob('*') if path.is_file())
    recipe = {'format': 'worker-fixture-recipe',
              'sources': [{'path': str(path.relative_to(source)),
                           'source': str(path.relative_to(ROOT)), 'sha256': sha(path)}
                          for path in paths],
              'generator': {'source': str((directory / 'generator.json').relative_to(ROOT)),
                            'sha256': sha(directory / 'generator.json')}}
    write(directory / 'recipe.json', recipe)
    return {'condition': side, 'sources': len(paths), 'generator_bytes': (directory / 'generator.json').stat().st_size,
            'recipe_sha256': sha(directory / 'recipe.json')}


if __name__ == '__main__':
    print(json.dumps([build(side) for side in 'ab']))
