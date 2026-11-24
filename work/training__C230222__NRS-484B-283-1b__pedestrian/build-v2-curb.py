"""Build two source-bound current-runtime curb diagnostics, without Native claims."""
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def rows(path, values):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(value, separators=(',', ':')) + '\n' for value in values))


def build(suffix):
    case_id = HERE.name + '__' + suffix
    out = HERE / 'v2-primary' / suffix
    source = out / 'sources'
    source.mkdir(parents=True, exist_ok=True)
    construction = copy.deepcopy(json.loads((HERE / 'duration-probes' / suffix / 'construction.json').read_text()))
    replacement = {'vehicle_approach': 'approach', 'curb_side': 'reference_corner',
                   'curb_close': 'driver_reference'}
    for item in construction['files']:
        if item['path'] == 'runner.py':
            text = item['content']
            for old, new in replacement.items():
                text = text.replace(old, new)
            item['content'] = text
        if item['path'] == 'finalize.py':
            text = item['content']
            helper = '''def rebuild_channels(attempt, config):
    """Derive diagnostic channel rows from immutable original curb samples."""
    samples = rows(attempt, 'curb-samples.jsonl')
    mapping = rows(attempt, 'video_frames.jsonl')
    channels = {channel['name']: [] for channel in config['recording_description']['channels']}
    previous_speed = None
    for sample, frame_map in zip(samples, mapping):
        time = sample['time_s']
        speed = sample['pedestrian_speed_mps']
        accel = 0 if previous_speed is None else (speed - previous_speed) / .05
        previous_speed = speed
        values = {'kin.position': sample['pedestrian_xy_m'],
                  'kin.speed': {'pedestrian_mps': speed,
                                'vehicle_mps': sample['vehicle_speed_mps']},
                  'kin.accel_longitudinal': accel,
                  'rel.occupies': {'original_footprint_xy_m': sample['pedestrian_footprint_xy_m'],
                                  'curb_edge_x_m': -3.5},
                  'drv.time_to_conflict': -sample['vehicle_xy_m'][1] / sample['vehicle_speed_mps'],
                  'drv.stopping_distance': {'conditional_assumption_only': True,
                                            'reaction_s': [.8, 1.2],
                                            'deceleration_mps2': [3, 5]},
                  'curb_camera_frame_join': frame_map}
        for name in channels:
            channels[name].append({'time_s': time, 'value': values[name]})
    directory = attempt / 'channels'
    directory.mkdir(exist_ok=True)
    for name, values in channels.items():
        path = directory / (name + '.jsonl')
        if path.exists():
            raise ValueError('Derived curb channel already exists: ' + name)
        path.write_text(''.join(json.dumps(value, allow_nan=False) + '\\n' for value in values))


'''
            if text.count('def finalize(attempt, output):') != 1 or text.count('    evidence = []') != 1:
                raise ValueError('Unexpected source finalizer')
            text = text.replace('def finalize(attempt, output):', helper + 'def finalize(attempt, output):')
            text = text.replace('    evidence = []', '    rebuild_channels(attempt, config)\n    evidence = []')
            item['content'] = text
        if item['path'] == 'config.json':
            config = json.loads(item['content'])
            for camera in config['cameras']:
                camera['name'] = replacement.get(camera['name'], camera['name'])
                camera['pose_strategy'] = 'authored curb and approaching vehicle in same 30-second frame sequence'
                camera['fov_deg'] = 90
            config['supported_case_ids'] = [HERE.name + '__probe_1', HERE.name + '__probe_2']
            item['content'] = json.dumps(config, indent=2) + '\n'
    construction['status'] = 'unselected_current_runtime_cpu_diagnostic'
    construction_path = out / 'construction.json'
    write(construction_path, construction)
    context = {
        'source_kind': 'synthetic_scene_request',
        'frozen_cell': {'layout': 'road', 'maneuver': 'travel', 'control': 'curb'},
        'authored_road_sha256': sha(HERE / 'native/road.xodr'),
        'pedestrian_id': 'proposed-pedestrian', 'vehicle_id': 'proposed-vehicle',
        'curb_edge_xy_m': [-3.5, 0], 'pedestrian_crossing_forward_xy': [1, 0],
        'road_width_m': 7, 'vehicle_conflict_y_m': 0,
        'vehicle_lane_center_x_m': -1.75, 'vehicle_body_half_width_m': 1,
        'assumed_driver_reaction_s': [0.8, 1.2],
        'assumed_deceleration_mps2': [3.0, 5.0],
        'introductory_exceptions': 'unreviewed_synthetic_context',
    }
    write(source / 'curb-context.json', context)
    departure = .5 if suffix == 'probe_1' else 3.5
    samples, trace, evidence, mapping, native, graphs = [], [], [], [], [], []
    channels = {channel['name']: [] for channel in config['recording_description']['channels']}
    prior_speed = None
    for index in range(600):
        time = index / 20
        frame = 100 + index
        x = -4.5 + (3 * (time - departure) if time >= departure else 0)
        y = 0
        speed = 3 if time >= departure else 0
        body = [[x-.12,-.12],[x+.12,-.12],[x+.12,.12],[x-.12,.12]]
        body3 = [[p[0],p[1],z] for p in body for z in (0,1.8)]
        sample = {'native_frame': frame, 'time_s': time,
                  'pedestrian_id': context['pedestrian_id'], 'vehicle_id': context['vehicle_id'],
                  'pedestrian_xy_m': [x,y], 'pedestrian_footprint_xy_m': body,
                  'pedestrian_speed_mps': speed,
                  'vehicle_xy_m': [-1.75,-18+4*time], 'vehicle_speed_mps': 4}
        samples.append(sample)
        trace.append({'frame': frame, 'time_s': time, 'position': {'x':x,'y':y,'z':.5},
                      'position_m': [x,y,.5], 'heading_deg': 0,
                      'velocity_mps': [speed,0,0], 'speed_mps': speed,
                      'speed_mph': speed/.44704, 'speed_provenance': 'synthetic_request_not_native',
                      'control': {'throttle':0,'brake':0,'hand_brake':False},
                      'synthetic_diagnostic': True})
        evidence.append({'original_frame':frame,'recording_time_s':time,
                         'replay_frame':frame,'replay_simulation_time_s':time,
                         'actor_id':17,'synthetic_diagnostic':True,
                         'ego':{'position_m':[x,y,.5],'heading_deg':0,
                                'body_vertices_m':body3,'speed_mps':speed,
                                'speed_provenance':'synthetic_request_not_native'},
                         'world':{'weather':{'cloudiness':0,'precipitation':0,
                                             'wetness':0,'fog_density':0}}})
        mapping.append({'video_frame':index,'native_frame':frame,'carla_frame':frame,'time_s':time})
        graph_path = f'capture/native/graphs/base/{frame:08d}.adapter.json'
        native.append({'frame':frame,'time_s':time,'simulation_time':time,
                       'adapter_graph':f'graphs/base/{frame:08d}.adapter.json',
                       'base':f'graphs/base/{frame:08d}.adapter.json',
                       'nodes':1,'edges':0,'synthetic_diagnostic':True})
        graphs.append({'path':graph_path,
                       'attributes':{'frame':frame,'simulation_time_s':time,'synthetic_diagnostic':True},
                       'nodes':[{'id':'ego','attributes':{'sem_class':'ego','entity_id':17,
                                  'vertex':[x,y,.5],'forward':[1,0,0],
                                  'threedbbox':body3}}], 'edges':[]})
        accel = 0 if prior_speed is None else (speed-prior_speed)/.05
        prior_speed = speed
        values = {'kin.position':[x,y],
                  'kin.speed':{'pedestrian_mps':speed,'vehicle_mps':4},
                  'kin.accel_longitudinal':accel,
                  'rel.occupies':{'original_footprint_xy_m':body,'curb_edge_x_m':-3.5},
                  'drv.time_to_conflict':(-sample['vehicle_xy_m'][1])/4,
                  'drv.stopping_distance':{'conditional_assumption_only':True,
                                           'reaction_s':[.8,1.2],'deceleration_mps2':[3,5]},
                  'curb_camera_frame_join':mapping[-1]}
        for name in channels:
            channels[name].append({'time_s':time,'value':values[name]})
    for name, data in [('curb-samples.jsonl',samples),('trace.jsonl',trace),
                       ('capture/evidence.jsonl',evidence),('video_frames.jsonl',mapping),
                       ('capture/native/frames.jsonl',native)]:
        rows(source/name,data)
    for name,data in channels.items():
        rows(source/'channels'/(name+'.jsonl'),data)
    (source/'capture/recorder_info.txt').write_text('Create 17: walker.pedestrian.synthetic\n')
    capture = {'extraction_confirmed':True,'frames':600,'synthetic_diagnostic':True,
               'sources':{'trace.jsonl':sha(source/'trace.jsonl'),
                          'road.xodr':sha(HERE/'native/road.xodr')}}
    write(source/'capture/manifest.json',capture)
    source_items = [{'path':str(p.relative_to(source)),
                     'source':str(p.relative_to(ROOT)),'sha256':sha(p)}
                    for p in sorted(source.rglob('*')) if p.is_file() and 'channels' not in p.parts]
    videos = [{'path':camera['name']+'.mkv','frames':600,'width':camera['width'],
               'height':camera['height'],'fps':20,'color':'black'}
              for camera in config['cameras']]
    generator = out/'generator.json'
    write(generator,{'files':{},'graphs':graphs,'videos':videos})
    recipe = out/'recipe.json'
    write(recipe,{'format':'worker-fixture-recipe','sources':source_items,
                  'generator':{'source':str(generator.relative_to(ROOT)),
                               'sha256':sha(generator)}})
    contract = {'format':'worker-measurement-contract','case_id':case_id,
                'requirements':[{'disposition_index':0,'requirement':'NRS-484B-283-1b',
                                 'source':'NRS 484B.283(1)(b)',
                                 'output_key':'curb_departure_conditional_margin',
                                 'method':'curb_departure','value_type':'object','kind':'measured',
                                 'inputs':['curb-samples.jsonl','curb-context.json','road.xodr']}],
                'negative':{'remove':['curb-samples.jsonl'],
                            'error_contains':'Missing required source: curb-samples.jsonl'}}
    write(out/'measurement-contract.json',contract)
    return {'case_id':case_id,'kind':'unselected_cpu_diagnostic',
            'construction':str(construction_path.relative_to(HERE)),
            'construction_sha256':sha(construction_path),'candidates':[],
            'measurement_contract':str((out/'measurement-contract.json').relative_to(HERE)),
            'measurement_procedure':{'entrypoint':'finalize.py',
                                     'output_schema':'worker-analysis-report-v1'},
            'fixture_recipe':str(recipe.relative_to(ROOT))}


def main():
    cases = [build(s) for s in ('probe_1','probe_2')]
    manifest = {'format':'worker-execution-manifest','assignment_id':HERE.name,
                'runtime_manifest_sha256':sha(ROOT/'runtime/SOURCE-MANIFEST.json'),
                'status':'unselected_current_runtime_cpu_diagnostic','cases':cases}
    write(HERE/'v2-primary-manifest.json',manifest)
    print(json.dumps({'cases':len(cases),'source_files':len(list((HERE/'v2-primary').rglob('*')))}))


if __name__ == '__main__':
    main()
