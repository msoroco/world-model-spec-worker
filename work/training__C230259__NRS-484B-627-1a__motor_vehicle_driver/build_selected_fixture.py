"""Build deterministic 600-frame source-shaped diagnostics, never Native evidence."""
import hashlib
import json
from pathlib import Path

from native.geometry import open_drive

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ASSIGNMENT = HERE.name
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(folder, name, text):
    path = folder / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text if text.endswith('\n') else text + '\n')


def rows(items):
    return '\n'.join(json.dumps(item, allow_nan=False, separators=(',', ':'))
                     for item in items) + '\n'


def build(suffix, right):
    folder = HERE / 'selected-source' / suffix
    folder.mkdir(parents=True, exist_ok=True)
    road = open_drive()
    road_hash = hashlib.sha256((road + '\n').encode()).hexdigest()
    context = {'assignment_id': ASSIGNMENT, 'source_kind': 'synthetic_fixture',
        'map_source_sha256': road_hash,
        'native_survey': {'lanes': [{'name': 'forward', 'lane_id': -1},
            {'name': 'opposing', 'lane_id': 1},
            {'name': 'right_paved_margin', 'lane_id': -2}]},
        'forward_lane_id': -1, 'opposing_lane_id': 1,
        'right_shoulder_lane_id': -2, 'right_paved_edge_y_m': -6.5,
        'paved_width_m': 10.0, 'public_highway': None,
        'nrs_484b_630_applicability': None}
    slow, mapping, core, evidence, graph_frames, graphs = [], [], [], [], [], []
    for i in range(600):
        frame, time = 100 + i, i / 20
        x = -30 + 1.5 * time
        y = -4.9 if right and i >= 240 else -1.75
        other_x = x - 18
        camera_frames = {name: frame for name in CAMERAS}
        footprint = [[x-2,y-1],[x+2,y-1],[x+2,y+1],[x-2,y+1]]
        slow.append({'video_frame': i, 'native_frame': frame, 'time_s': time,
            'camera_native_frames': camera_frames, 'ego_id': 'synthetic-ego',
            'traffic_id': 'synthetic-follower', 'ego_road_id': '1',
            'traffic_road_id': '1', 'ego_lane_id': -2 if right and i >= 240 else -1,
            'traffic_lane_id': -1, 'ego_xy_m': [x,y],
            'traffic_xy_m': [other_x,-1.75], 'ego_footprint_xy_m': footprint,
            'ego_speed_mps': 1.5, 'traffic_speed_mps': 1.5,
            'ego_requested_speed_mps': 1.5,
            'follower_free_flow_request_mps': 5.0,
            'follower_command_mps': 1.5 if i >= 50 else 5.0})
        mapping.append({'video_frame': i, 'native_frame': frame,
                        'carla_frame': frame, 'time_s': time,
                        'camera_native_frames': camera_frames})
        core.append({'frame': frame, 'time_s': time,
            'position': {'x':x,'y':y,'z':1.0}, 'position_m':[x,y,1.0],
            'heading_deg':0.0, 'speed_mps':1.5, 'speed_mph':1.5/.44704,
            'control': {'throttle':0.0,'brake':0.0,'hand_brake':False},
            'synthetic_diagnostic':True, 'velocity_mps':[1.5,0,0],
            'speed_provenance':'synthetic_native_sample'})
        body = [[px,py,z] for px,py in footprint for z in (0.0,1.5)]
        evidence.append({'original_frame':frame,'replay_frame':frame,
            'actor_id':107,'recording_time_s':time,'replay_simulation_time_s':time,
            'ego':{'position_m':[x,y,1.0],'heading_deg':0.0,'speed_mps':1.5,
                'speed_provenance':'synthetic_native_sample','body_vertices_m':body},
            'world':{'weather':{'cloudiness':0,'precipitation':0,'wetness':0,
                                'fog_density':0},
                     'road_projection':{'road_id':1,'section_id':0,
                                        'lane_id':-2 if right and i>=240 else -1,
                                        's_m':x+80}}})
        name=f'{frame:08d}.adapter.json'
        graph_frames.append({'frame':frame,'time_s':time,'simulation_time':time,
            'synthetic_diagnostic':True,'adapter_graph':'graphs/base/'+name})
        graphs.append({'path':'capture/native/graphs/base/'+name,
                       'attributes':{'frame':frame},'nodes':[],'edges':[]})
    write(folder,'slow-traffic-trace.jsonl',rows(slow))
    write(folder,'video_frames.jsonl',rows(mapping))
    write(folder,'trace.jsonl',rows(core))
    write(folder,'capture/evidence.jsonl',rows(evidence))
    write(folder,'capture/native/frames.jsonl',rows(graph_frames))
    write(folder,'road.xodr',road)
    write(folder,'slow-traffic-context.json',json.dumps(context,indent=2))
    write(folder,'capture/recorder_info.txt','Create 107: vehicle.tesla.model3')
    write(folder,'acquisition-provenance.json',json.dumps({
        'provenance_kind':'synthetic_fixture','diagnostic_fixture':True,
        'native_executed':False},indent=2))
    manifest={'extraction_confirmed':True,'frames':600,
        'required_observations':[],'synthetic_diagnostic':True,
        'sources':{'road.xodr':sha(folder/'road.xodr'),
                   'trace.jsonl':sha(folder/'trace.jsonl')}}
    write(folder,'capture/manifest.json',json.dumps(manifest,indent=2))
    videos=[{'path':name+'.mkv','frames':600,
        'width':1920 if name=='overview' else 1280,
        'height':1080 if name=='overview' else 720,
        'fps':20,'color':color} for name,color in zip(CAMERAS,
                                                       ('blue','green','white','red'))]
    generator={'files':{},'graphs':graphs,'videos':videos}
    generator_path=HERE/('selected-generator-'+suffix+'.json')
    generator_path.write_text(json.dumps(generator,separators=(',',':'))+'\n')
    inventory=[]
    for path in sorted(folder.rglob('*')):
        if path.is_file():
            inventory.append({'path':str(path.relative_to(folder)),
                'source':str(path.relative_to(ROOT)),'sha256':sha(path)})
    recipe={'format':'worker-fixture-recipe','sources':inventory,
        'generator':{'source':str(generator_path.relative_to(ROOT)),
                     'sha256':sha(generator_path)}}
    recipe_path=HERE/('selected-recipe-'+suffix+'.json')
    recipe_path.write_text(json.dumps(recipe,indent=2)+'\n')
    return {'case':suffix,'sources':len(inventory),'generator_sha256':sha(generator_path),
            'recipe_sha256':sha(recipe_path)}


if __name__=='__main__':
    print(json.dumps([build('controlled_1',True),build('controlled_2',False)]))
