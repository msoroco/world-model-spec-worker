"""Build an exact synthetic Native-shaped attempt and test saved/Core/render."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import pickle
import shutil
import subprocess
import sys
import tempfile

FOLDER=Path(__file__).resolve().parent
ROOT=FOLDER.parents[1]
sys.path.insert(0,str(ROOT/'runtime/pipeline/scenario_pipeline'))
from worker_exchange.runtime_cli import materialize,execution_env,process,render
from worker_exchange.media import audit
from traffic_spec_adapter.adapter import load_graph


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def rows(path):return [json.loads(x) for x in path.read_text().splitlines() if x.strip()]
def write_rows(path,values):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(''.join(json.dumps(v,allow_nan=False)+'\n' for v in values))


def make_attempt(destination,suffix,candidate='primary'):
    case=FOLDER.name+'__'+suffix
    materialize(FOLDER/'draft-execution-manifest.json',case,destination,candidate)
    source=FOLDER/'draft-u-turn-saved'/('straight' if suffix=='witness_1' else 'u_turn')
    for name in ('native_samples.jsonl','video_frames.jsonl','pixel_review.jsonl'):
        shutil.copyfile(source/name,destination/name)
    samples=rows(destination/'native_samples.jsonl')
    mapping=rows(destination/'video_frames.jsonl')
    if len(samples)!=480 or len(mapping)!=480:raise ValueError('Synthetic original sources incomplete')
    trace=[];evidence=[];history=[];frames=[]
    graph=load_graph(ROOT/'runtime/pipeline/fixtures/retained-speed/capture/native/graphs/base/00021714.pkl')
    graph_dir=destination/'capture/native/graphs/base';graph_dir.mkdir(parents=True)
    for index,(n,m) in enumerate(zip(samples,mapping)):
        frame=n['native_frame'];time=n['time_s'];x,y=n['native_center_xy_m']
        heading=math.degrees(math.atan2(n['native_forward_xy'][1],n['native_forward_xy'][0]))
        body=[[a,b,z] for a,b in n['native_body_xy_m'] for z in (0,1.5)]
        trace.append({'frame':frame,'time_s':time,'position':{'x':x,'y':y,'z':.5},
            'position_m':[x,y,.5],'heading_deg':heading,'speed_mps':5,
            'speed_mph':5/.44704,'control':{'throttle':0,'brake':0,'hand_brake':False}})
        evidence.append({'original_frame':frame,'recording_time_s':time,
            'replay_frame':frame,'replay_simulation_time_s':time,'actor_id':107,
            'ego':{'body_vertices_m':body,'position_m':[x,y,.5],
                   'heading_deg':heading,'speed_mps':5,
                   'speed_provenance':'original_trace_actor_get_velocity'},
            'world':{'weather':{'cloudiness':0,'precipitation':0,'wetness':0,'fog_density':0},
                     'road_projection':{'road_id':n['native_road_id'],'section_id':0,
                                        'lane_id':n['native_lane_id'],'s_m':x+80}}})
        history.append({'frame':frame,'time_s':time,'body_vertices_m':body})
        graph.graph['frame']=frame
        (graph_dir/f'{frame:08d}.pkl').write_bytes(pickle.dumps(graph,protocol=4))
        frames.append({'frame':frame,'simulation_time':time,'time_s':time,
            'base':f'graphs/base/{frame:08d}.pkl',
            'abstract':f'graphs/abstract/{frame:08d}.pkl','synthetic_diagnostic':True})
    write_rows(destination/'trace.jsonl',trace)
    write_rows(destination/'capture/evidence.jsonl',evidence)
    write_rows(destination/'body_history.jsonl',history)
    write_rows(destination/'capture/native/frames.jsonl',frames)
    sys.path.insert(0,str(destination))
    from geometry import open_drive
    (destination/'road.xodr').write_text(open_drive())
    (destination/'capture/recorder_info.txt').write_text('Create 107: vehicle.lincoln.mkz_2020\n')
    (destination/'capture/manifest.json').write_text(json.dumps({
        'extraction_confirmed':True,'frames':480,
        'sources':{'road.xodr':sha(destination/'road.xodr'),
                   'trace.jsonl':sha(destination/'trace.jsonl')},
        'synthetic_diagnostic':True}))
    (destination/'context.json').write_text(json.dumps({'signed_hill_crest':{
        'native_map_sha256':'a'*64,'official_sign_status':'synthetic_review_only'}}))
    (destination/'channels').mkdir()
    config=json.loads((destination/'config.json').read_text())
    for channel in config['recording_description']['channels']:
        name=channel['name'];values=[]
        for index,n in enumerate(samples):
            if name=='kin.heading':value=n['native_forward_xy']
            elif name=='rel.occupies':value=n['native_body_xy_m']
            elif name=='native_body_pose_control':value=n
            elif name=='camera_frame_join':value=mapping[index]
            elif name=='drv.u_turn':value={'requested':suffix=='witness_2','observed_from_saved_measurement':None}
            elif name=='dev.regulatory_sign':value={'code':'no_u_turn','synthetic_review_only':True}
            elif name=='dev.governs':value={'native_lane_id':-1,'synthetic_review_only':True}
            elif name=='dev.position':value={'native_xy_m':[-8,4],'synthetic_review_only':True}
            else:raise ValueError('Unknown channel '+name)
            values.append({'time_s':n['time_s'],'value':value})
        write_rows(destination/'channels'/(name+'.jsonl'),values)
    shutil.copytree(destination/'channels',destination/'source_channels')
    for name in ('overview','approach','sign_reference','driver_reference'):
        subprocess.run(['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-y',
            '-f','lavfi','-i','color=c=black:s=32x32:r=20:d=24',
            '-frames:v','480','-c:v','ffv1',str(destination/(name+'.mkv'))],
            check=True,timeout=120)
    review=json.loads((source/'sign-review.json').read_text())
    review['video_sha256']=sha(destination/'approach.mkv')
    (destination/'sign-review.json').write_text(json.dumps(review))
    return destination


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--case',choices=('witness_1','witness_2'),required=True)
    parser.add_argument('--candidate',choices=('primary','fallback1','fallback2','fallback3'),default='primary')
    args=parser.parse_args()
    scratch=Path(tempfile.mkdtemp(dir=ROOT/'.runtime-work',prefix='c104538-core-'))
    attempt=make_attempt(scratch/'attempt',args.case,args.candidate)
    subprocess.run([sys.executable,str(attempt/'finalize.py'),'--attempt',str(attempt),
        '--output',str(attempt/'analysis-report.json')],cwd=attempt,env=execution_env(),check=True,timeout=300)
    core=process(attempt,attempt/'converted',ROOT/'runtime/pipeline/library',
        ROOT/'.runtime-work/decoder-refresh-20261105/.lake/build/bin/adapterCheck')
    config=json.loads((attempt/'config.json').read_text())
    video=render(attempt,attempt/'converted',config['case'])
    decoded=audit(video['video'],480,mapping_sha256=video['frame_map_sha256'],
                  receipt=attempt/'final-decode.json')
    print(json.dumps({'scratch':str(scratch),'case':args.case,'candidate':args.candidate,
        'core':core,'render_frames':video['frames'],'final_decode_passed':decoded['passed'],
        'scope':'synthetic software integration only; no CARLA, official sign review or acceptance'},indent=2))


if __name__=='__main__':main()
