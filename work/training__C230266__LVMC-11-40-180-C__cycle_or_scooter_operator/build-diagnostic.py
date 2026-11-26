"""Build explicit synthetic source recipes for saved sidewalk CPU checks."""
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]
sys.path.insert(0,str(HERE/'native'/'tests'))
sys.path.insert(0,str(HERE/'native'))
from test_saved import write_fixture

CAMERAS=('overview','approach','reference_corner','driver_reference')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,indent=2,ensure_ascii=False)+'\n')


def rows(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(''.join(json.dumps(row,separators=(',',':'),allow_nan=False)+'\n'
                            for row in data))


def build(suffix,signal,pause):
    case=HERE.name+'__'+suffix
    source=HERE/'diagnostic-source'/suffix
    source.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=REPO/'.runtime-work') as tmp:
        tmp=Path(tmp)
        write_fixture(tmp,signal_frame=signal,pause_requested=pause)
        raw=(tmp/'pedestrian-microphone.s16le').read_bytes()
        encoded=source/'pedestrian-microphone.hex'
        encoded.write_text(raw.hex()+'\n')
        metadata=json.loads((tmp/'pedestrian-microphone.json').read_text())
        metadata.update(source_kind='synthetic_cpu',pcm_path=encoded.name,
                        pcm_encoding='hex_s16le_diagnostic')
        dump(source/'pedestrian-microphone.json',metadata)
        for name in ('sidewalk-actors.jsonl','video_frames.jsonl','camera-frames.jsonl',
                     'pedestrian-microphone-frames.jsonl'):
            shutil.copyfile(tmp/name,source/name)
    dump(source/'acquisition-provenance.json',{
        'provenance_kind':'synthetic_fixture','diagnostic_fixture':True,
        'native_executed':False,'microphone_placement_verified':False})
    shutil.copyfile(HERE/'native'/'road.xodr',source/'road.xodr')
    dump(source/'sidewalk-map-readback.json',{
        'source_kind':'synthetic_cpu','road_id':1,'lane_id':-2,
        'lane_type':'Sidewalk','rider_device_class_verified':False,
        'municipal_applicability_verified':False})
    recorder=source/'capture'/'recorder_info.txt'
    recorder.parent.mkdir(parents=True,exist_ok=True)
    recorder.write_text('Create 17: vehicle.synthetic.bicycle\nCreate 19: walker.synthetic.pedestrian\n')
    source_actors=[json.loads(line) for line in (source/'sidewalk-actors.jsonl').read_text().splitlines()]
    trace=[];evidence=[];native_frames=[]
    for i,actor in enumerate(source_actors):
        frame=actor['native_frame'];time=i/20
        position=actor['rider_xyz_m']
        speed=actor['rider_velocity_xyz_mps'][0]
        trace.append({'frame':frame,'time_s':time,
            'position':{'x':position[0],'y':position[1],'z':position[2]},
            'position_m':position,'heading_deg':0,'speed_mps':speed,
            'speed_mph':speed*2.2369362921,
            'velocity_mps':[speed,0,0],
            'control':{'throttle':.2 if speed else 0,'brake':0 if speed else 1,
                       'hand_brake':False},
            'synthetic_diagnostic':True,
            'speed_provenance':'synthetic_native_sample'})
        evidence.append({'original_frame':frame,'replay_frame':frame,
            'actor_id':17,'recording_time_s':time,
            'replay_simulation_time_s':time,
            'ego':{'position_m':position,'heading_deg':0,'speed_mps':speed,
                   'speed_provenance':'synthetic_native_sample',
                   'body_vertices_m':[[position[0]+dx,position[1]+dy,z]
                       for dx in (-.45,.45) for dy in (-.3,.3) for z in (0,.8)]},
            'world':{'weather':{'cloudiness':0,'precipitation':0,
                                'wetness':0,'fog_density':0},
                     'road_projection':{'road_id':1,'section_id':0,
                                        'lane_id':-2,'s_m':position[0]+15}}})
        native_frames.append({'frame':frame,'time_s':time,'simulation_time':time,
            'synthetic_diagnostic':True,
            'adapter_graph':f'graphs/base/{frame:08d}.adapter.json'})
    for name,data in (('trace.jsonl',trace),('capture/evidence.jsonl',evidence),
                      ('capture/native/frames.jsonl',native_frames)):
        rows(source/name,data)
    dump(source/'capture/manifest.json',{
        'extraction_confirmed':True,'frames':600,'required_observations':[],
        'synthetic_diagnostic':True,
        'sources':{'road.xodr':sha(source/'road.xodr'),
                   'trace.jsonl':sha(source/'trace.jsonl')}})
    generator={'files':{},'graphs':[
        {'path':f'capture/native/graphs/base/{10000+i:08d}.adapter.json',
         'attributes':{'frame':10000+i},'nodes':[],'edges':[]}
        for i in range(600)],
        'videos':[{'path':name+'.mkv','frames':600,'width':1920 if j==0 else 1280,
                   'height':1080 if j==0 else 720,'fps':20,'color':'blue'}
                  for j,name in enumerate(CAMERAS)]}
    generator_path=HERE/('diagnostic-generator-'+suffix+'.json')
    dump(generator_path,generator)
    names=('acquisition-provenance.json','capture/evidence.jsonl',
           'capture/manifest.json','capture/native/frames.jsonl',
           'capture/recorder_info.txt','trace.jsonl','video_frames.jsonl',
           'road.xodr','sidewalk-map-readback.json','sidewalk-actors.jsonl',
           'camera-frames.jsonl','pedestrian-microphone.json',
           'pedestrian-microphone-frames.jsonl','pedestrian-microphone.hex')
    recipe={'format':'worker-fixture-recipe',
            'sources':[{'path':name,'source':str((source/name).relative_to(REPO)),
                        'sha256':sha(source/name)} for name in names],
            'generator':{'source':str(generator_path.relative_to(REPO)),
                         'sha256':sha(generator_path)}}
    recipe_path=HERE/('diagnostic-recipe-'+suffix+'.json')
    dump(recipe_path,recipe)
    return {'case_id':case,'fixture_recipe':str(recipe_path.relative_to(REPO)),
            'fixture_recipe_sha256':sha(recipe_path)}


if __name__=='__main__':
    print(json.dumps([build(*entry) for entry in (
        ('probe_a',80,True),('probe_b',None,True),('probe_c',80,False))],indent=2))
