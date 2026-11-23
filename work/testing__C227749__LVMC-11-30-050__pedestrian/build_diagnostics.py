"""Generate source-hashed synthetic diagnostics for each exact crossing case.

The candidate OpenDRIVE has road lanes only; curb/crosswalk physical readback and
municipal applicability remain unverified. These fixtures prove software shape.
"""
from __future__ import annotations
import hashlib
import json
import math
from pathlib import Path

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]
CAMERAS=('overview','approach','reference_corner','driver_reference')

def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def dump(path,obj): path.write_text(json.dumps(obj,indent=2,allow_nan=False)+'\n')
def lines(rows): return ''.join(json.dumps(row,allow_nan=False)+'\n' for row in rows)

def path_at(route, fraction):
    points=[tuple(map(float,p)) for p in route]
    spans=[math.dist(a,b) for a,b in zip(points,points[1:])]
    remaining=fraction*sum(spans)
    for a,b,span in zip(points,points[1:],spans):
        if remaining<=span:
            t=remaining/span;return [a[0]+t*(b[0]-a[0]),a[1]+t*(b[1]-a[1])]
        remaining-=span
    return list(points[-1])

def build_one(case):
    name=case['case_id'].rsplit('__',1)[-1]
    folder=ROOT/'cases'/name
    scene=json.loads((folder/'scene.json').read_text())
    case_id=scene['case_id']
    body=[];trace=[];mapping=[];joins=[];evidence=[];native=[];graphs=[]
    for i in range(5):
        x,y=path_at(scene['route_xy_m'],i/4);t=round(i*.05,6)
        box=[[x-.2,y-.2],[x+.2,y-.2],[x+.2,y+.2],[x-.2,y+.2]]
        vertices=[[p[0],p[1],z] for p in box for z in (0,1.8)]
        body.append({'case_id':case_id,'frame':i,'time_s':t,'source':'original_native',
                     'actor_id':7,'body_center_xy_m':[x,y],'body_xy_m':box})
        trace.append({'frame':i,'time_s':t,'actor_id':7,'position_m':[x,y,0],
                      'position':{'x':x,'y':y,'z':0},'heading_deg':90,'velocity_mps':[0,1.2,0],
                      'speed_mps':1.2,'speed_mph':1.2/.44704,'control':{}})
        mapping.append({'carla_frame':i,'native_frame':i,'time_s':t,'video_frame':i})
        joins.append({'case_id':case_id,'frame':i,'time_s':t,
                      'cameras':{name2:{'frame':i,'width':1920 if name2=='overview' else 1280,
                                       'height':1080 if name2=='overview' else 720,
                                       'pixel_format':'bgra','bytes':(1920*1080 if name2=='overview' else 1280*720)*4}
                                 for name2 in CAMERAS}})
        original={'frame':i,'time_s':t,'map_context':{'declared_public_way_road_ids':[]},'participants':[]}
        evidence.append({'actor_id':7,'ego':{'body_vertices_m':vertices,'heading_deg':90,
                      'position_m':[x,y,0],'speed_mps':1.2,'speed_provenance':'synthetic_native_sample'},
                      'original_frame':i,'original_observations':original,'recording_time_s':t,
                      'replay_frame':i,'replay_simulation_time_s':t,'world':{'weather':{}}})
        native.append({'adapter_graph':f'graphs/base/{i:08d}.adapter.json','frame':i,'simulation_time':t})
        graphs.append({'path':f'capture/native/graphs/base/{i:08d}.adapter.json',
                       'attributes':{'frame':i,'time_s':t,'observed_evidence':original},
                       'nodes':[],'edges':[]})
    files={'acquisition-provenance.json':json.dumps({'diagnostic_fixture':True,'provenance_kind':'synthetic_fixture','scope':'software-only; no physical or legal acceptance'})+'\n',
           'walker-body-history.jsonl':lines(body),'trace.jsonl':lines(trace),
           'video_frames.jsonl':lines(mapping),'camera-frame-joins.jsonl':lines(joins),
           'capture/evidence.jsonl':lines(evidence),'capture/native/frames.jsonl':lines(native),
           'capture/recorder_info.txt':'Create 7: walker.pedestrian (synthetic diagnostic)\n'}
    road=ROOT/'candidate-crossing.xodr'
    files['capture/manifest.json']=json.dumps({'acquisition':'original_live_run','case_id':case_id,
           'complete_driving_lanes':False,'extraction_confirmed':True,'frames':5,
           'sources':{'road.xodr':sha(road),'trace.jsonl':hashlib.sha256(files['trace.jsonl'].encode()).hexdigest()},
           'status':'draft'})+'\n'
    files['acquisition.json']=json.dumps({'scene.json':{'kind':'diagnostic_fixture','sha256':sha(folder/'scene.json')},
                                         **{name2:{'kind':'diagnostic_fixture','sha256':hashlib.sha256(files[name2].encode()).hexdigest()}
                                         for name2 in ('walker-body-history.jsonl','camera-frame-joins.jsonl')}
                                        ,**{name2+'.mkv':{'kind':'diagnostic_fixture'} for name2 in CAMERAS}})+'\n'
    videos=[{'path':name2+'.mkv','frames':5,'width':1920 if name2=='overview' else 1280,
             'height':1080 if name2=='overview' else 720,'fps':20,'color':'black'} for name2 in CAMERAS]
    spec={'files':files,'graphs':graphs,'videos':videos}
    dump(folder/'diagnostic.json',spec)
    note={'case_id':case_id,'provenance':'synthetic_fixture','physical_realization':'unconfirmed',
          'road_source':'authored candidate OpenDRIVE lanes only; curb and crosswalk physical surfaces unconfirmed',
          'jurisdiction':'unverified','purpose':'source-shaped software compatibility'}
    dump(folder/'diagnostic-source-note.json',note)
    recipe={'format':'worker-fixture-recipe','sources':[{'path':'road.xodr','source':str(road.relative_to(REPO)),'sha256':sha(road)},
       {'path':'diagnostic-source-note.json','source':str((folder/'diagnostic-source-note.json').relative_to(REPO)),
        'sha256':sha(folder/'diagnostic-source-note.json')}],
       'generator':{'source':str((folder/'diagnostic.json').relative_to(REPO)),
                    'sha256':sha(folder/'diagnostic.json')}}
    dump(folder/'fixture-recipe.json',recipe)
    return {'case_id':case_id,'recipe':str((folder/'fixture-recipe.json').relative_to(REPO)),'sha256':sha(folder/'fixture-recipe.json')}

if __name__=='__main__':
    plan=json.loads((ROOT/'case-plan.json').read_text())
    print(json.dumps([build_one(case) for case in plan['cases']],indent=2))
