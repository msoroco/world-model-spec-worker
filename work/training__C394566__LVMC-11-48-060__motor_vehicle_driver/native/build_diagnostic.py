"""Build bounded textual source recipes for the two synthetic software diagnostics."""
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
REPO = ROOT.parents[1]
AID = ROOT.name
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
COUNT = 600


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def lines(values):
    return ''.join(json.dumps(v, separators=(',', ':'))+'\n' for v in values)


def build(case, hashes):
    example = json.loads((REPO/'runtime/fixtures/example.json').read_text())
    example_files = example['files']
    source = json.loads(example_files['capture/evidence.jsonl'].splitlines()[0])
    ego_graph = next(x for x in example['graphs'][0]['nodes'] if x['id'] == 'ego')
    ego_graph = copy.deepcopy(ego_graph)
    for key in list(ego_graph['attributes']):
        if key not in ('vertex', 'sem_class', 'entity_id', 'threedbbox', 'forward', 'special_class'):
            ego_graph['attributes'].pop(key)
    source['original_observations'] = {
        'world_settings': {'no_rendering_mode': False}, 'rgb_sensors': [],
        'frame': 0, 'time_s': 0.0, 'devices': [],
        'participants': [source['original_observations']['participants'][0]],
        'relations': [], 'participant_inventory': 'synthetic diagnostic',
        'map_context': {'declared_public_way_road_ids': []}}
    for key in list(source):
        if key not in ('original_frame', 'replay_frame', 'actor_id', 'recording_time_s',
                       'replay_simulation_time_s', 'ego', 'world', 'original_observations'):
            source.pop(key)
    for key in list(source['ego']):
        if key not in ('position_m', 'heading_deg', 'speed_mps', 'speed_provenance', 'body_vertices_m'):
            source['ego'].pop(key)
    keep_participant = ('actor_id', 'blueprint', 'position_m', 'heading_deg',
                        'velocity_mps', 'speed_mps', 'body_vertices_m')
    participant_template = source['original_observations']['participants'][0]
    source['original_observations']['participants'] = [
        {key: participant_template[key] for key in keep_participant}]
    evidence, frames, route, trace, mapping, graphs = [], [], [], [], [], []
    for i in range(COUNT):
        frame, t = 1000+i, round((i+1)*.05, 4)
        stop = case == 'probe_02' and 220 <= i < 320
        progress = i if case == 'probe_01' or i < 220 else 220 if i < 320 else i-100
        step_m = .14 if case == 'probe_01' else .168
        x = progress*step_m
        road = 100 if i < 150 else 200 if i < 450 else 300
        speed = 0.0 if stop else step_m*20
        body = [[round(x+dx, 4), dy, dz]
                for dx in (-2.0, 2.0) for dy in (-1.0, 1.0) for dz in (0.0, 2.0)]
        sample = {'frame': frame, 'time_s': t, 'position': {'x': x, 'y': 0.0, 'z': 0.0},
                  'position_m': [x, 0.0, 0.0], 'heading_deg': 0.0,
                  'speed_mps': speed, 'speed_mph': speed/.44704,
                  'velocity_mps': [speed, 0.0, 0.0], 'control': {}}
        trace.append(sample)
        mapping.append({'video_frame': i, 'native_frame': frame,
                        'carla_frame': frame, 'time_s': t})
        route.append({'video_frame': i, 'native_frame': frame,
                      'source_kind': 'synthetic_native_sample', 'ego_actor_id': 205,
                      'road_id': road, 'ego_x_m': x, 'ego_y_m': 0.0,
                      'ego_speed_mps': speed, 'service_stop_active': stop})
        event = copy.deepcopy(source)
        event.update(original_frame=frame, replay_frame=frame, actor_id=205,
                     recording_time_s=t, replay_simulation_time_s=t)
        event['ego'].update(position_m=[x, 0.0, 0.0], speed_mps=speed,
                            speed_provenance='synthetic_native_sample', body_vertices_m=body)
        event['original_observations'].update(frame=frame, time_s=t)
        participant = event['original_observations']['participants'][0]
        participant.update(position_m=[x, 0.0, 0.0], speed_mps=speed,
                           velocity_mps=[speed, 0.0, 0.0], body_vertices_m=body)
        evidence.append(event)
        frames.append({'frame': frame, 'simulation_time': t, 'abstract': None,
                       'base': None, 'nodes': 1, 'edges': 0,
                       'adapter_graph': f'graphs/base/{frame:08d}.adapter.json'})
        node = copy.deepcopy(ego_graph)
        node['attributes']['vertex'] = [x, 0.0, 0.0]
        node['attributes']['threedbbox'] = body
        graphs.append({'path': f'capture/native/graphs/base/{frame:08d}.adapter.json',
                       'attributes': {'frame': frame,
                                      'observed_evidence': copy.deepcopy(event['original_observations'])},
                       'nodes': [node], 'edges': []})
    context = {'assignment_id': AID, 'case_id': AID+'__'+case,
               'review_kind': 'synthetic_diagnostic', 'reviewer': 'synthetic-software-test',
               'camera_sha256': hashes, 'truck_blueprint_source': 'synthetic fixture',
               'truck_route_designation_source': 'synthetic fixture',
               'nontruck_street_designation_source': 'synthetic fixture',
               'route_connectivity_source': 'synthetic fixture',
               'enroute_purpose_source': 'synthetic fixture',
               'served_premises_source': 'synthetic fixture',
               'entry_truck_route_id': 100, 'intervening_street_id': 200,
               'exit_truck_route_id': 300, 'ego_actor_id': 205,
               'vehicle_is_truck': True, 'enroute_purpose': 'none' if case == 'probe_01' else 'delivery',
               'service_stop_complete': case == 'probe_02'}
    files = {'road.xodr': example_files['road.xodr'],
             'capture/recorder_info.txt': 'Version: 1\nMap: OpenDriveMap\nCreate 205: vehicle.carlamotors.carlacola (0) at (0, 0, 0)\n',
             'trace.jsonl': lines(trace), 'video_frames.jsonl': lines(mapping),
             'native_route_trace.jsonl': lines(route),
             'route_context.json': json.dumps(context, separators=(',', ':'))+'\n',
             'capture/evidence.jsonl': lines(evidence),
             'capture/native/frames.jsonl': lines(frames)}
    manifest = {'status': 'draft', 'acquisition': 'diagnostic_fixture',
                'case_id': AID+'__'+case, 'source_run': 'synthetic diagnostic only',
                'map': 'OpenDriveMap', 'frames': COUNT, 'required_observations': [],
                'extraction_confirmed': True,
                'sources': {name: hashlib.sha256(files[name].encode()).hexdigest()
                            for name in ('road.xodr', 'trace.jsonl')},
                'complete_driving_lanes': False}
    files['capture/manifest.json'] = json.dumps(manifest, separators=(',', ':'))+'\n'
    videos = [{'path': name+'.mkv', 'frames': COUNT,
               'width': 1920 if name == 'overview' else 1280,
               'height': 1080 if name == 'overview' else 720,
               'fps': 20, 'color': 'black'} for name in CAMERAS]
    spec = {'files': files, 'graphs': graphs, 'videos': videos}
    path = ROOT/f'diagnostic-{case}.json'
    path.write_text(json.dumps(spec, separators=(',', ':'))+'\n')
    relative = str(path.relative_to(REPO))
    source = REPO/'inputs'/AID/'assignment.json'
    recipe = {'format': 'worker-fixture-recipe',
              'sources': [{'path': 'fixture-assignment.json',
                           'source': str(source.relative_to(REPO)), 'sha256': sha(source)}],
              'generator': {'source': relative, 'sha256': sha(path)}}
    (ROOT/f'fixture-recipe-{case}.json').write_text(json.dumps(recipe, indent=2)+'\n')
    print(case, 'spec_bytes', path.stat().st_size, 'spec_sha256', sha(path))


def main():
    video_root = REPO/'.runtime-work/c394566-video-hashes'
    hashes = {name+'.mkv': sha(video_root/(name+'.mkv')) for name in CAMERAS}
    for case in ('probe_01', 'probe_02'):
        build(case, hashes)


if __name__ == '__main__':
    main()
