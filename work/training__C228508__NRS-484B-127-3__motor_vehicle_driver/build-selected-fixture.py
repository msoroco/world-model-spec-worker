"""Create explicit, synthetic source files for one public compatibility diagnostic."""

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
sys.path.insert(0, str(ROOT / 'native'))
from engineering import CANDIDATES, commanded_centers
from geometry import open_drive

AID = 'training__C228508__NRS-484B-127-3__motor_vehicle_driver'
CASE = AID + '__probe_a'
SOURCE = ROOT / 'compat-source' / 'probe_a'
SOURCE.mkdir(parents=True, exist_ok=True)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, separators=(',', ':'), allow_nan=False) + '\n')


def jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(row, separators=(',', ':'), allow_nan=False) + '\n' for row in rows))


def rectangle(x, y, half):
    return [[x-half,y-1],[x-half,y+1],[x+half,y+1],[x+half,y-1]]


context = {'case_id': CASE, 'candidate_id': 'primary',
           'synthetic_diagnostic': True, 'public_highway_status_verified': False,
           'outside_business_district_verified': False, 'caravan_membership_verified': False,
           'trailer_coupling_verified': False, 'potential_entrant_safety_verified': False}
write(SOURCE / 'authored-context.json', context)
write(SOURCE / 'caravan_context.json', context)
samples, mapping, history, trace, evidence, frame_rows, graphs = [], [], [], [], [], [], []
for index in range(600):
    frame = 70000 + index
    time_s = index / 20
    centers = commanded_centers('probe_a', 'primary', index)
    actors = {}
    for name in ('lead', 'ego_combination', 'trailer_proxy', 'rear', 'potential_entrant'):
        x = (centers['ego_combination'] + 2.25 if name == 'ego_combination' else
             centers['ego_combination'] - 2.25 if name == 'trailer_proxy' else centers[name])
        lane = -2 if name == 'potential_entrant' and index < 120 else -1
        y = -5.25 if lane == -2 else -1.75
        half = 3 if name == 'potential_entrant' else 2.25
        actors[name] = {'native_road_id': 1, 'native_lane_id': lane,
                        'native_body_xy_m': rectangle(x,y,half),
                        'native_center_xy_m': [x,y],
                        'native_velocity_xy_mps': [6,0], 'speed_mps': 6}
    samples.append({'native_frame': frame, 'time_s': time_s, 'actors': actors,
                    'requested_group_speed_mps': 6})
    mapping.append({'video_frame': index, 'carla_frame': frame,
                    'native_frame': frame, 'time_s': time_s})
    subject = actors['ego_combination']
    trace.append({'frame': frame, 'time_s': time_s,
                  'position': {'x': subject['native_center_xy_m'][0],
                               'y': -1.75, 'z': .5},
                  'position_m': [subject['native_center_xy_m'][0], -1.75, .5],
                  'heading_deg': 0, 'speed_mps': 6, 'speed_mph': 6/.44704,
                  'velocity_mps':[6,0,0], 'control':{}, 'synthetic_diagnostic':True})
    history.append({'frame': frame, 'time_s': time_s, 'participants': {
        'subject': {'body_vertices_m': actors['lead']['native_body_xy_m'], 'lane_id': -1},
        'rear': {'body_vertices_m': rectangle(centers['ego_combination'],-1.75,4.5), 'lane_id': -1},
        'entrant': {'body_vertices_m': actors['potential_entrant']['native_body_xy_m'],
                    'lane_id': actors['potential_entrant']['native_lane_id']}}})
    evidence.append({'original_frame': frame, 'replay_frame': frame, 'actor_id': 101,
                     'recording_time_s': time_s, 'replay_simulation_time_s': time_s,
                     'ego': {'position_m': [subject['native_center_xy_m'][0],-1.75,.5],
                             'speed_mps': 6, 'speed_provenance': 'synthetic_native_sample',
                             'heading_deg': 0}, 'synthetic_diagnostic': True})
    relative = f'capture/native/graphs/base/{frame:08d}.adapter.json'
    frame_rows.append({'frame': frame, 'simulation_time': time_s,
                       'adapter_graph': f'graphs/base/{frame:08d}.adapter.json',
                       'base': f'graphs/base/{frame:08d}.adapter.json',
                       'nodes': 1, 'edges': 0})
    x = subject['native_center_xy_m'][0]
    box = [[a,b,c] for a in (x-2.25,x+2.25) for b in (-2.75,-.75) for c in (0,1.5)]
    graphs.append({'path': relative,
                   'attributes': {'frame': frame, 'simulation_time_s': time_s,
                                  'source': 'C228508 caravan CPU diagnostic',
                                  'synthetic_diagnostic': True},
                   'nodes': [{'id':'ego','attributes':{'entity_id':101,'sem_class':'ego',
                               'vertex':[x,-1.75,.5],'forward':[1,0,0],
                               'threedbbox':box,'carla_speed':6}}], 'edges':[]})

for name, rows in (('native_samples.jsonl',samples),('video_frames.jsonl',mapping),
                   ('caravan_history.jsonl',history),('trace.jsonl',trace),
                   ('capture/evidence.jsonl',evidence)):
    jsonl(SOURCE / name, rows)
write(SOURCE / 'native-source-inventory.json', {'format':'c228508-original-native-draft-sources-v1',
    'case_id':CASE,'candidate_id':'primary',
    'sha256':{name:sha(SOURCE/name) for name in ('authored-context.json','native_samples.jsonl')}})
(SOURCE / 'capture').mkdir(exist_ok=True)
write(SOURCE / 'capture/manifest.json', {'source_kind':'synthetic_diagnostic','frames':600,
    'rate_hz':20,'extraction_confirmed':True,'original_native_observed':False,
    'sources':{'trace.jsonl':sha(SOURCE/'trace.jsonl')}})
spec = {'files': {'road.xodr':open_drive(),
                  'capture/native/frames.jsonl': ''.join(json.dumps(row,separators=(',',':'))+'\n' for row in frame_rows),
                  'capture/recorder_info.txt':'C228508 synthetic CPU diagnostic; no Native observation.\n'},
        'graphs':graphs,
        'videos':[{'path':name+'.mkv','frames':600,'width':w,'height':h,'fps':20,'color':'black'}
                  for name,w,h in (('overview',1920,1080),('approach',1280,720),
                                   ('reference_corner',1280,720),('driver_reference',1280,720))]}
spec_path=ROOT/'selected-probe_a-fixture-spec.json'
write(spec_path,spec)
sources=[]
for file in sorted(f for f in SOURCE.rglob('*') if f.is_file()):
    sources.append({'path':str(file.relative_to(SOURCE)), 'source':str(file.relative_to(REPO)),
                    'sha256':sha(file)})
recipe={'format':'worker-fixture-recipe',
        'generator':{'source':str(spec_path.relative_to(REPO)),'sha256':sha(spec_path)},
        'sources':sources}
recipe_path=ROOT/'selected-probe_a-fixture-recipe.json'
write(recipe_path,recipe)
print(json.dumps({'source_count':len(sources),'spec_sha256':sha(spec_path),
                  'recipe_sha256':sha(recipe_path)}))
