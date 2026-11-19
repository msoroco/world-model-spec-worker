"""Inventory a reproducible synthetic reference fixture for runtime diagnosis."""
import hashlib
import json
from pathlib import Path
import shutil


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SOURCES = ('acquisition-provenance.json', 'native-actors.jsonl',
           'native-map-readback.json', 'video_frames.jsonl')
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True)+'\n')


def build(source):
    source = Path(source).resolve()
    if '.runtime-work' not in source.parts:
        raise ValueError('Source must be an ignored diagnostic work directory')
    dest = HERE/'fixtures/reference-sources'
    dest.mkdir(parents=True, exist_ok=True)
    inventory = []
    for name in SOURCES:
        target = dest/name
        shutil.copyfile(source/name, target)
        inventory.append({'path': name, 'source': str(target.relative_to(ROOT)),
                          'sha256': sha(target)})
    road = dest/'road.xodr'
    road.write_text(
        '<OpenDRIVE><header revMajor="1" revMinor="4" name="synthetic_C179480_diagnostic" '
        'version="1" north="20" south="-20" east="100" west="-100" '
        'vendor="full-train-worker"/><road id="7" name="synthetic_diagnostic_road" '
        'length="200" junction="-1"><link/><planView><geometry s="0" x="-100" '
        'y="0" hdg="0" length="200"><line/></geometry></planView>'
        '<elevationProfile><elevation s="0" a="0" b="0" c="0" d="0"/>'
        '</elevationProfile><lanes><laneOffset s="0" a="0" b="0" c="0" d="0"/>'
        '<laneSection s="0"><left><lane id="1" type="driving" level="false">'
        '<width sOffset="0" a="3.7" b="0" c="0" d="0"/></lane></left>'
        '<center><lane id="0" type="none" level="false"/></center>'
        '<right><lane id="-1" type="driving" level="false"><width sOffset="0" '
        'a="3.7" b="0" c="0" d="0"/></lane><lane id="-2" type="shoulder" '
        'level="false"><width sOffset="0" a="3.0" b="0" c="0" d="0"/>'
        '</lane></right></laneSection></lanes><objects/><signals/></road></OpenDRIVE>\n')
    inventory.append({'path':'road.xodr','source':str(road.relative_to(ROOT)),
                      'sha256':sha(road)})
    recorder = dest/'capture/recorder_info.txt'
    recorder.parent.mkdir(parents=True,exist_ok=True)
    recorder.write_text('Synthetic C179480 diagnostic fixture; no CARLA recorder run.\n'
                        'Create 205: vehicle.tesla.model3 (0) at (0, 0, 0)\n')
    inventory.append({'path':'capture/recorder_info.txt',
                      'source':str(recorder.relative_to(ROOT)),
                      'sha256':sha(recorder)})
    rows = [json.loads(line) for line in (dest/'native-actors.jsonl').read_text().splitlines()]
    mapping = [json.loads(line) for line in (dest/'video_frames.jsonl').read_text().splitlines()]
    if len(rows) != 600 or len(mapping) != 600 or any(
            row['frame'] != frame['carla_frame'] for row, frame in zip(rows,mapping)):
        raise ValueError('Expected exact 600-frame diagnostic source join')
    camera_rows = [{'actor_id': 300+i, 'blueprint':'sensor.camera.rgb'}
                   for i in range(4)]
    graphs=[]
    evidence=[]
    native_frames=[]
    for row, frame in zip(rows,mapping):
        number=row['frame']
        relative=f'graphs/base/{number:08d}.adapter.json'
        observation={'frame':number,'time_s':frame['time_s'],
                     'map_context':{'declared_public_way_road_ids':[]},
                     'participants':[], 'rgb_sensors':camera_rows,
                     'world_settings':{'no_rendering_mode':False}}
        graphs.append({'path':'capture/native/'+relative,
                       'attributes':{'frame':number,
                                     'simulation_time_s':frame['time_s'],
                                     'observed_evidence':observation},
                       'nodes':[],'edges':[]})
        native_frames.append({'abstract':relative,'adapter_graph':relative,
                              'base':relative,'edges':0,'frame':number,
                              'nodes':0,'simulation_time':frame['time_s']})
        evidence.append({'original_frame':number,
                         'recording_time_s':frame['time_s'],
                         'replay_frame':number,
                         'replay_simulation_time_s':frame['time_s'],
                         'original_observations':observation,
                         'actor_id':205,
                         'ego':{'position_m':[row['ego_x_m'],row['ego_y_m'],0],
                                'heading_deg':row['ego_yaw_deg'],
                                'body_vertices_m':row['ego_body_vertices_xyz_m'],
                                'speed_mps':row['ego_speed_mps'],
                                'speed_provenance':'synthetic_native_sample'},
                         'world':{'weather':{'precipitation':0.,
                                             'wetness':0.,
                                             'sun_altitude_angle':45.}}})
    manifest={'acquisition':'synthetic_fixture',
              'case_id':HERE.name+'__reference','frames':600,
              'observation_contract_version':2,
              'status':'draft','extraction_confirmed':True,
              'complete_driving_lanes':False,
              'required_observations':[],
              'sources':{'native-actors.jsonl':sha(dest/'native-actors.jsonl'),
                         'video_frames.jsonl':sha(dest/'video_frames.jsonl'),
                         'road.xodr':sha(road),
                         'trace.jsonl':sha(source/'trace.jsonl')}}
    for name, content in (
            ('capture/manifest.json',json.dumps(manifest,sort_keys=True)+'\n'),
            ('capture/evidence.jsonl',''.join(json.dumps(x,sort_keys=True)+'\n'
                                              for x in evidence)),
            ('capture/native/frames.jsonl',''.join(json.dumps(x,sort_keys=True)+'\n'
                                                   for x in native_frames))):
        target=dest/name
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(content)
        inventory.append({'path':name,'source':str(target.relative_to(ROOT)),
                          'sha256':sha(target)})
    video_sizes=[(1920,1080),(1280,720),(1280,720),(1280,720)]
    spec={'files':{},'graphs':graphs,
          'videos':[{'path':name+'.mkv','frames':600,'fps':20,
                     'width':size[0],'height':size[1],'color':'black'}
                    for name,size in zip(CAMERAS,video_sizes)]}
    spec_path=HERE/'draft-reference-diagnostic-spec.json'
    write(spec_path,spec)
    recipe={'format':'worker-fixture-recipe','sources':inventory,
            'generator':{'source':str(spec_path.relative_to(ROOT)),
                         'sha256':sha(spec_path)}}
    recipe_path=HERE/'draft-reference-diagnostic-recipe.json'
    write(recipe_path,recipe)
    return {'source_files':len(inventory),'graphs':len(graphs),
            'videos':len(spec['videos']),'spec_sha256':sha(spec_path),
            'recipe_sha256':sha(recipe_path)}


if __name__ == '__main__':
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('source',type=Path)
    print(json.dumps(build(parser.parse_args().source),sort_keys=True))
