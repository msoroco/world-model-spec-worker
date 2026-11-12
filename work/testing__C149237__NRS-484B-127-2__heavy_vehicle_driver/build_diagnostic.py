"""Create a truck-specific textual compatibility fixture; no physical evidence."""
import hashlib
import json
import argparse
from pathlib import Path

FOLDER = Path(__file__).resolve().parent
REPO = FOLDER.parents[1]
TEMPLATE = REPO/'work/testing__C101303__NRS-484B-127-1__motor_vehicle_driver/diagnostic.json'
GAPS = {'gap_below_500ft':150.0,'gap_at_500ft':152.4,'gap_above_500ft':155.0}
WIDTH_CASES={'ego_width_below_80in':('ego',2.0),
             'ego_width_at_80in':('ego',2.032),
             'ego_width_above_80in':('ego',2.1),
             'lead_width_below_80in':('lead',2.0),
             'lead_width_at_80in':('lead',2.032),
             'lead_width_above_80in':('lead',2.1)}


def lines(items):
    return ''.join(json.dumps(item, separators=(',', ':'))+'\n' for item in items)


def body(x, y=1.75, width=2.2):
    half=width/2
    return [[x-5, y-half, 0], [x-5, y+half, 0],
            [x+5, y-half, 0], [x+5, y+half, 0],
            [x-5, y-half, 2.8], [x-5, y+half, 2.8],
            [x+5, y-half, 2.8], [x+5, y+half, 2.8]]


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--gap',choices=tuple(GAPS)+tuple(WIDTH_CASES)+('two_same_direction_lanes','overtaking'),default='gap_below_500ft')
    args=parser.parse_args()
    suffix=args.gap
    case=FOLDER.name+'__'+suffix
    lead_offset=(150.0 if suffix=='two_same_direction_lanes' else GAPS.get(suffix,152.4))+10.0
    spec = json.loads(TEMPLATE.read_text())
    evidence = [json.loads(line) for line in spec['files']['capture/evidence.jsonl'].splitlines()]
    trace = [json.loads(line) for line in spec['files']['trace.jsonl'].splitlines()]
    history = []
    for i, row in enumerate(evidence):
        x = ([100,120,140,160,240,280,300,320,340][i]
             if suffix=='overtaking' else 100.0 + i*.6)
        lead_x = ([260,264,268,272,276,280,284,288,292][i]
                  if suffix=='overtaking' else x+lead_offset)
        ego_lane = (1 if i in (2,3,4,5,6) else -1) if suffix=='overtaking' else -1
        ego_y = (1.9 if ego_lane==1 else -1.9) if suffix=='overtaking' else 1.75
        lead_y = -1.9 if suffix=='overtaking' else 1.75
        ego = row['original_observations']['participants'][0]
        ego['blueprint'] = 'vehicle.carlamotors.european_hgv'
        ego['blueprint_attributes']['base_type'] = 'truck'
        ego['blueprint_attributes']['ros_name'] = ego['blueprint']
        ego['position_m'] = [x, ego_y, 0]
        ego_width=WIDTH_CASES[suffix][1] if suffix in WIDTH_CASES and WIDTH_CASES[suffix][0]=='ego' else 2.2
        lead_width=WIDTH_CASES[suffix][1] if suffix in WIDTH_CASES and WIDTH_CASES[suffix][0]=='lead' else 2.2
        ego['body_vertices_m'] = body(x,y=ego_y,width=ego_width)
        ego['velocity_mps'] = [12, 0, 0]
        ego['speed_mps'] = 12
        row['ego'].update(position_m=ego['position_m'], speed_mps=12,
                          speed_provenance='synthetic_native_sample',
                          body_vertices_m=ego['body_vertices_m'])
        trace[i].update(position_m=ego['position_m'],
                        position={'x':x,'y':ego_y,'z':0},
                        speed_mps=12, speed_mph=12/.44704,
                        velocity_mps=[12,0,0])
        row['world']['road_projection'].update(s_m=x)
        if suffix=='overtaking':row['world']['road_projection']['lane_id']=ego_lane
        lead = json.loads(json.dumps(ego))
        lead['actor_id'] = 206
        lead['blueprint'] = 'vehicle.carlamotors.carlacola'
        lead['blueprint_attributes']['ros_name'] = lead['blueprint']
        lead['position_m'] = [lead_x, lead_y, 0]
        lead['body_vertices_m'] = body(lead_x,y=lead_y,width=lead_width)
        row['original_observations']['participants'] = [ego, lead]
        row['original_observations']['map_context']['core_assumptions'] = [['asm.public_highway', True]]
        def actor(a):
            return {'actor_id':a['actor_id'],'blueprint_id':a['blueprint'],
                    'road_id':1,'lane_id':ego_lane if a['actor_id']==ego['actor_id'] else -1,
                    'overall_width_m':ego_width if a['actor_id']==ego['actor_id'] else lead_width,
                    'is_truck_or_combination':True,
                    'body_vertices_xy_m':[[p[0],p[1]] for p in a['body_vertices_m'][:4]],
                    'velocity_mps':a['velocity_mps']}
        history.append({'frame':row['original_frame'],'time_s':row['recording_time_s'],
                        'ego':actor(ego),'lead':actor(lead)})
    spec['files']['capture/evidence.jsonl'] = lines(evidence)
    spec['files']['trace.jsonl'] = lines(trace)
    spec['files']['truck_history.jsonl'] = lines(history)
    road_context = {
        'native_map_id':'synthetic-truck-diagnostic-template','road_id':1,'lane_id':-1,
        'same_direction_lane_count':2 if suffix=='two_same_direction_lanes' else 1,
        'lane_forward_xy':[1,0],
        'lane_count_source':'synthetic diagnostic template; not a physical lane-count claim'}
    if suffix=='overtaking':road_context['passing_lane_id']=1
    spec['files']['road_context.json'] = json.dumps(road_context)+'\n'
    spec['files']['fixture-provenance.json'] = json.dumps({
        'scope':'synthetic software compatibility only', 'case_id':case,
        'template':str(TEMPLATE.relative_to(REPO)),
        'limitations':['template road is not the authored truck road',
                       'color video does not establish visibility or physical following']},indent=2)+'\n'
    manifest = json.loads(spec['files']['capture/manifest.json'])
    manifest.update(case_id=case, source_run='synthetic:truck-diagnostic',
                    required_observations=['ru.subject','ru.truck','kin.position','kin.velocity',
                                           'kin.speed','st.lane','rel.surface_gap',
                                           'rel.ahead_behind_in_lane'])
    manifest['sources'] = {name:hashlib.sha256(spec['files'][name].encode()).hexdigest()
                           for name in ('road.xodr','trace.jsonl')}
    spec['files']['capture/manifest.json'] = json.dumps(manifest,indent=2)+'\n'
    for graph in spec['graphs']:
        index = next(i for i,row in enumerate(evidence) if str(row['original_frame']) in graph['path'])
        graph['attributes']['observed_evidence'] = evidence[index]['original_observations']
        if '/base/' not in graph['path']:
            continue
        ego = evidence[index]['original_observations']['participants'][0]
        node = next(n for n in graph['nodes'] if n['id']=='ego')
        attrs = node['attributes']
        attrs['vertex'] = ego['position_m']
        attrs['threedbbox'] = ego['body_vertices_m']
        attrs['carla_vel_x'],attrs['carla_vel_y'],attrs['carla_vel_z'] = ego['velocity_mps']
        attrs['carla_speed'] = ego['speed_mps']
        attrs['original_observation'] = ego
        if isinstance(graph['attributes'].get('bbox'),dict):
            graph['attributes']['bbox']['ego'] = [[p[0],p[1]] for p in ego['body_vertices_m'][:4]]
    path = FOLDER/('diagnostic.json' if suffix=='gap_below_500ft' else 'diagnostic-'+suffix+'.json')
    path.write_text(json.dumps(spec,separators=(',',':'))+'\n')
    recipe = {'format':'worker-fixture-recipe','sources':[
        {'path':'diagnostic-source.txt','source':str((FOLDER/'site-proof.json').relative_to(REPO)),
         'sha256':hashlib.sha256((FOLDER/'site-proof.json').read_bytes()).hexdigest()}],
        'generator':{'source':str(path.relative_to(REPO)),
                     'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}}
    recipe_path=FOLDER/('fixture-recipe.json' if suffix=='gap_below_500ft' else 'fixture-recipe-'+suffix+'.json')
    recipe_path.write_text(json.dumps(recipe,indent=2)+'\n')
    print(json.dumps({'case_id':case,'diagnostic_bytes':path.stat().st_size,'frames':len(evidence)}))


if __name__ == '__main__':
    main()
