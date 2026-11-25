"""Create source-hashed synthetic diagnostics, without physical or legal claims."""
import hashlib
import json
from pathlib import Path
from geometry import open_drive

F = Path(__file__).resolve().parent.parent
R = F.parents[1]
V = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def lines(rows):
    return ''.join(json.dumps(row, separators=(',', ':')) + '\n' for row in rows)


def write(path, obj):
    path.write_text(json.dumps(obj, separators=(',', ':')) + '\n')
    assert path.stat().st_size <= 2*1024*1024


def rect(x0, x1, y0, y1):
    return [[x0,y0],[x1,y0],[x1,y1],[x0,y1]]


def build(label, candidate):
    y = (-2.65 if label == 'reference' else -1.45) + (0 if candidate == 'primary' else (.15 if label == 'reference' else -.15))
    cid = F.name + '__' + label
    tracks, fmap, trace, evidence, frames, graphs = [], [], [], [], [], []
    standing = rect(53,57,-5.8,-4.2)
    for i in range(600):
        frame, t, x = 1000+i, i/20, 10+i*.15
        body = rect(round(x-.3,4),round(x+.3,4),round(y-.22,4),round(y+.22,4))
        tracks.append({'frame':i,'native_frame':frame,'time_s':t,'source_kind':'synthetic_native_sample',
                       'actor_id':71,'blueprint':'vehicle.bh.crossbike','body_native_xy_m':body,
                       'standing_body_native_xy_m':standing})
        fmap.append({'video_frame':i,'carla_frame':frame,'native_frame':frame,'time_s':t,
                     'camera_native_frames':{name:frame for name in V},
                     'source_rgb_sha256':{name:hashlib.sha256(f'{cid}:{candidate}:{frame}:{name}'.encode()).hexdigest() for name in V}})
        trace.append({'frame':frame,'time_s':t,'position':{'x':x,'y':y,'z':.7},
                      'position_m':[x,y,.7],'heading_deg':0.,'speed_mps':3.,
                      'speed_mph':3/.44704,'velocity_mps':[3.,0.,0.],
                      'control':{'throttle':0,'steer':0,'brake':0,'hand_brake':False}})
        evidence.append({'original_frame':frame,'replay_frame':frame,'recording_time_s':t,
                         'replay_simulation_time_s':t,'actor_id':71,
                         'ego':{'position_m':[x,y,.7],'heading_deg':0.,'speed_mps':3.,
                                'body_vertices_m':[[a,b,0] for a,b in body],
                                'speed_provenance':'synthetic_native_sample'},
                         'world':{'weather':{'cloudiness':0,'precipitation':0,'wetness':0,'fog_density':0},
                                  'road_projection':{'road_id':1,'section_id':0,'lane_id':-1,'s_m':x+50}}})
        graph=f'graphs/base/{frame:08d}.adapter.json'
        frames.append({'abstract':graph,'adapter_graph':graph,'base':graph,'edges':0,'frame':frame,'nodes':0,
                       'simulation_time':t,'time_s':t,'synthetic_diagnostic':True})
        graphs.append({'path':'capture/native/'+graph,'attributes':{'frame':frame},'nodes':[],'edges':[]})
    road={'format':'c230259-road-edge-v1','right_edge_source':'synthetic_cpu',
          'right_side':'lower_y','right_roadway_edge_y_m':-3.5,'driving_lane_width_m':3.5}
    standing_obj={'format':'c230259-standing-vehicle-v1','source_kind':'synthetic_cpu',
                  'body_native_xy_m':standing,'actor_id':72}
    context={'source_kind':'synthetic_cpu','law_id':'NRS-484B-777-1','cell_id':'C230259',
             'actor':'cycle_or_scooter_operator','nearby_moving_traffic_count':0,
             'left_turn_requested':False,'other_hazard_inventory':[],
             'driving_lane_width_m':3.5,'legal_verdict':None,
             'fixed_conditions_id':'c230259-standing-vehicle-v1'}
    suffix=label+'-'+candidate
    source_rows=[('native-cycle-frames.jsonl',lines(tracks)),('native-map-readback.json',json.dumps(road)+'\n'),
                 ('standing-vehicle.json',json.dumps(standing_obj)+'\n'),('context.json',json.dumps(context)+'\n')]
    road_path=F/'native/road.xodr'
    road_path.write_text(open_drive()+'\n')
    source_paths=[]
    for name,data in source_rows:
        p=F/('diagnostic-'+suffix+'-'+name)
        p.write_text(data)
        source_paths.append((name,p))
    source_paths.append(('road.xodr',road_path))
    spec={'files':{'video_frames.jsonl':lines(fmap),'trace.jsonl':lines(trace),
                   'capture/evidence.jsonl':lines(evidence),'capture/native/frames.jsonl':lines(frames),
                   'capture/manifest.json':json.dumps({'frames':600,'extraction_confirmed':True,
                       'synthetic_diagnostic':True,'case_id':cid,'required_observations':[],
                       'sources':{'road.xodr':sha(road_path),
                                  'trace.jsonl':hashlib.sha256(lines(trace).encode()).hexdigest()}}),
                   'capture/recorder_info.txt':'Synthetic CPU diagnostic; no CARLA recording.\nCreate 71: vehicle.bh.crossbike (0)\n'},
          'graphs':graphs,
          'videos':[{'path':name+'.mkv','frames':600,'width':1920 if name=='overview' else 1280,
                     'height':1080 if name=='overview' else 720,'fps':20,'color':'black'} for name in V]}
    spec_path=F/('diagnostic-'+suffix+'.json'); write(spec_path,spec)
    recipe={'format':'worker-fixture-recipe','sources':[{'path':name,'source':str(p.relative_to(R)),'sha256':sha(p)} for name,p in source_paths],
            'generator':{'source':str(spec_path.relative_to(R)),'sha256':sha(spec_path)}}
    recipe_path=F/('diagnostic-'+suffix+'-recipe.json'); write(recipe_path,recipe)
    return {'label':label,'candidate':candidate,'recipe_sha256':sha(recipe_path),'spec_bytes':spec_path.stat().st_size}


if __name__=='__main__':
    print(json.dumps([build(label,candidate) for label in ('reference','contrast') for candidate in ('primary','fallback1')]))
