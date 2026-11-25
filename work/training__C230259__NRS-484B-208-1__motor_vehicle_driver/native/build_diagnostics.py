"""Create source-hashed synthetic lane diagnostics; never claim physical evidence."""
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
    if path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError('Returned diagnostic exceeds 2 MiB')


def body(x, y):
    return [[x-2,y-.9,0],[x+2,y-.9,0],[x+2,y+.9,0],[x-2,y+.9,0]]


def build(label, candidate):
    rear_x = -50 if candidate == 'primary' else -55
    cid = F.name + '__' + label
    actors, fmap, trace, evidence, frames, graphs = [], [], [], [], [], []
    for i in range(600):
        frame, time = 1000+i, i/20
        ex, rx = 20+i, rear_x+1.35*i
        ey = -1.75 if label == 'reference' or i < 100 else (
            -5.25 if i >= 140 else -1.75-3.5*(i-100)/40)
        lane = -1 if ey > -3.5 else -2
        actors.append({'frame':i,'native_frame':frame,'time_s':time,
            'source_kind':'synthetic_native_sample','ego_longitudinal_m':ex,
            'rear_longitudinal_m':rx,'ego_speed_mps':20.,'rear_speed_mps':27.,
            'ego_lane_id':lane,'rear_lane_id':-1,
            'ego_body_vertices_m':body(ex,ey),'rear_body_vertices_m':body(rx,-1.75)})
        fmap.append({'video_frame':i,'carla_frame':frame,'native_frame':frame,
            'time_s':time,'camera_native_frames':{name:frame for name in V},
            'source_rgb_sha256':{name:hashlib.sha256(
                f'{cid}:{candidate}:{frame}:{name}'.encode()).hexdigest() for name in V}})
        trace.append({'frame':frame,'time_s':time,
            'position':{'x':ex,'y':ey,'z':1},'position_m':[ex,ey,1],
            'heading_deg':0.,'speed_mps':20.,'speed_mph':20/.44704,
            'velocity_mps':[20.,0.,0.],
            'control':{'throttle':0,'steer':0,'brake':0,'hand_brake':False}})
        evidence.append({'original_frame':frame,'replay_frame':frame,
            'recording_time_s':time,'replay_simulation_time_s':time,'actor_id':71,
            'ego':{'position_m':[ex,ey,1],'heading_deg':0.,'speed_mps':20.,
                   'body_vertices_m':body(ex,ey),
                   'speed_provenance':'synthetic_native_sample'},
            'world':{'weather':{'cloudiness':0,'precipitation':0,
                'wetness':0,'fog_density':0},'road_projection':{
                'road_id':1,'section_id':0,'lane_id':lane,'s_m':ex+100}}})
        graph = f'graphs/base/{frame:08d}.adapter.json'
        frames.append({'abstract':graph,'adapter_graph':graph,'base':graph,
            'edges':0,'frame':frame,'nodes':0,'simulation_time':time,
            'time_s':time,'synthetic_diagnostic':True})
        graphs.append({'path':'capture/native/'+graph,
                       'attributes':{'frame':frame},'nodes':[],'edges':[]})
    road = {'source_kind':'synthetic_native_sample','capture_hz':20,'frames':600,
        'same_direction_marked_lane_count':2,'extreme_left_lane_id':-1,
        'right_lane_id':-2,'posted_speed_limit_mps':25.,
        'controlled_access_original_verified':False,
        'posted_limit_original_verified':False}
    map_readback = {'format':'c230259-left-lane-map-readback-v1',
        'same_direction_marked_lane_count':2,'extreme_left_lane_id':-1,
        'right_lane_id':-2,'waypoints':[{'lane_id':-1,'y_m':-1.75},
                                       {'lane_id':-2,'y_m':-5.25}]}
    context = {'source_kind':'synthetic_native_sample','law_id':'NRS-484B-208-1',
        'cell_id':'C230259','actor':'motor_vehicle_driver',
        'city_or_town_geography_verified':False,'hov_lane_present':False,
        'left_turn_requested':False,'maintenance_or_emergency_duty_verified':False,
        'subject_overtaking_other_vehicle_requested':False,
        'official_control_reviewed':False,
        'emergency_authorization_reviewed':False,
        'weather':'clear','legal_verdict':None,
        'fixed_conditions_id':'c230259-left-lane-v1'}
    suffix = label+'-'+candidate
    road_path = F/'native/road.xodr'
    road_path.write_text(open_drive()+'\n')
    source_rows = [('native-actors.jsonl',lines(actors)),
        ('native-road-context.json',json.dumps(road)+'\n'),
        ('native-map-readback.json',json.dumps(map_readback)+'\n'),
        ('context.json',json.dumps(context)+'\n')]
    paths = []
    for name, data in source_rows:
        path = F/('diagnostic-'+suffix+'-'+name)
        path.write_text(data)
        paths.append((name,path))
    paths.append(('road.xodr',road_path))
    spec = {'files':{'video_frames.jsonl':lines(fmap),
        'trace.jsonl':lines(trace),'capture/evidence.jsonl':lines(evidence),
        'capture/native/frames.jsonl':lines(frames),
        'capture/manifest.json':json.dumps({'frames':600,
            'extraction_confirmed':True,'synthetic_diagnostic':True,
            'case_id':cid,'required_observations':[],
            'sources':{'road.xodr':sha(road_path),
                       'trace.jsonl':hashlib.sha256(lines(trace).encode()).hexdigest()}}),
        'capture/recorder_info.txt':
            'Synthetic CPU diagnostic; no CARLA recording.\nCreate 71: vehicle.tesla.model3 (0)\n'},
        'graphs':graphs,
        'videos':[{'path':name+'.mkv','frames':600,
            'width':1920 if name=='overview' else 1280,
            'height':1080 if name=='overview' else 720,
            'fps':20,'color':'black'} for name in V]}
    spec_path = F/('diagnostic-'+suffix+'.json')
    write(spec_path,spec)
    recipe = {'format':'worker-fixture-recipe',
        'sources':[{'path':name,'source':str(path.relative_to(R)),
                    'sha256':sha(path)} for name,path in paths],
        'generator':{'source':str(spec_path.relative_to(R)),
                     'sha256':sha(spec_path)}}
    recipe_path = F/('diagnostic-'+suffix+'-recipe.json')
    write(recipe_path,recipe)
    return {'label':label,'candidate':candidate,
            'recipe_sha256':sha(recipe_path),'spec_bytes':spec_path.stat().st_size}


if __name__ == '__main__':
    print(json.dumps([build(label,candidate)
        for label in ('reference','contrast')
        for candidate in ('primary','fallback1')]))
