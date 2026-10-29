"""Saved-only law-specific measurements; diagnostic fixtures make no physical claim."""
import argparse, hashlib, json, math
from pathlib import Path
from worker_exchange.native_output import write_result

def read(root, name):
    p=root/name
    if not p.is_file(): raise ValueError('Missing required source: '+name)
    if name.endswith('.jsonl'): return [json.loads(s) for s in p.read_text().splitlines() if s.strip()]
    return json.loads(p.read_text())

def hashes(root, names):
    return {n:hashlib.sha256((root/n).read_bytes()).hexdigest() for n in names}

def sign_governance(c,r):
    return {'sign':c['sign'],'approach_road_id':c['approach_road_id'],'native_inventory':c['native_inventory'],'governance_basis':c['governance_basis']}

def reference_hierarchy(c,r):
    return {'stop_lines':c['stop_lines'],'near_crosswalks':c['near_crosswalks'],'sidewalk_crosswalk_survey':c['sidewalk_crosswalk_survey'],'intersection_polygon_xy_m':c['intersection_polygon_xy_m']}

def nearest_visible_point(c,r):
    samples=[x for x in r if 'distance_to_intersection_m' in x and 'clear_ray' in x]
    if len(samples)<2: raise ValueError('Multiple original driver viewpoint samples required')
    clear=[x for x in samples if x['clear_ray'] is True]
    if not clear: raise ValueError('No observed clear viewpoint')
    winner=min(clear,key=lambda x:x['distance_to_intersection_m'])
    gaps=[math.hypot(a['point_xy_m'][0]-b['point_xy_m'][0],a['point_xy_m'][1]-b['point_xy_m'][1]) for a,b in zip(samples,samples[1:])]
    return {'frame':winner['frame'],'point_xy_m':winner['point_xy_m'],'distance_to_intersection_m':winner['distance_to_intersection_m'],'clear_sample_count':len(clear),'observed_max_sample_spacing_m':max(gaps),'ray_target':c['ray_target'],'sampling_note':'Nearest among saved original samples; continuous nearest point and pixel visibility remain unverified'}

def initial_yield_response(c,r):
    return {'samples':[{'frame':x['frame'],'time_s':x['time_s'],'speed_mps':x['ego_speed_mps'],'distance_to_intersection_m':x.get('distance_to_intersection_m')} for x in r], 'reference_point':'nearest sampled clear viewpoint; no legal slowdown cutoff applied'}

def crossing_interaction(c,r):
    return {'samples':[{'frame':x['frame'],'ego_inside':x.get('ego_inside',False),'other_inside':x.get('other_inside',False),'other_distance_to_conflict_m':x.get('other_distance_to_conflict_m'),'other_speed_mps':x.get('other_speed_mps')} for x in r], 'hazard_conclusion':'requires local physical and legal review'}

def control_exception_inventory(c,r):
    return {'officers':c['native_inventory']['officers'],'traffic_signals':c['native_inventory']['traffic_signals'],'survey_scope':c['native_inventory']['survey_scope'],'unclassified_actor_types':c['native_inventory'].get('unclassified_actor_types',[]),'landmarks':c['native_inventory'].get('landmarks',[])}

def entrance_obligations(c,r):
    return {'entrances':c['entrances'],'through_highway_designation':c['through_highway_designation'],'native_inventory':c['native_inventory']}

def occupied_intersection_yield(c,r):
    return {'samples':[{'frame':x['frame'],'ego_inside':x.get('ego_inside',False),'other_inside':x.get('other_inside',False),'other_obligated':x.get('other_obligated',False),'ego_speed_mps':x['ego_speed_mps']} for x in r], 'judgment_note':'No automatic immediate-hazard or cautiousness verdict'}

def curved_turn_context(c,r):
    return {'road_type':c['road_type'],'curve_radius_m':c['curve_radius_m'],'turning_envelope_xy_m':c['turning_envelope_xy_m'],'highway_designation':c['highway_designation']}

def bidirectional_visibility(c,r):
    sides={side:[{'frame':x['frame'],'distance_m':x['approach_distance_m'],'clear_ray':x['clear_ray']} for x in r if x.get('approach_direction')==side] for side in ('forward','reverse')}
    if any(len(v)<2 for v in sides.values()):raise ValueError('Both approach directions need multiple original ray samples')
    return {'samples_by_direction':sides,'statutory_distance_m':152.4,'ray_origin':c['ray_origin'],'ray_target':c['ray_target'],'limitations':'Ray samples and terrain occlusion do not establish rendered pixel recognition or an unobserved continuum'}

def reversal_motion(c,r):
    return {'samples':[{'frame':x['frame'],'heading_deg':x.get('heading_deg'),'position_xy_m':x['point_xy_m'],'ego_speed_mps':x['ego_speed_mps']} for x in r], 'opposite_direction_goal_deg':c['opposite_direction_goal_deg']}

def truck_class_context(c,r):
    return {'ego_blueprint':c['ego_blueprint'],'leader_blueprint':c['leader_blueprint'],'nominal_min_width_m':2.032,'native_width_samples_m':[[x.get('ego_width_m'),x.get('other_width_m')] for x in r]}

def lane_availability(c,r):
    return {'one_way':c['one_way'],'same_direction_available_lanes':c['same_direction_available_lanes'],'road_ids':c['road_ids'],'overtake_segment':c['overtake_segment']}

def following_gap(c,r):
    return {'samples':[{'frame':x['frame'],'gap_m':x['body_gap_m'],'gap_ft':x['body_gap_m']/0.3048,'same_lane':x['same_lane'],'overtaking':x.get('overtaking',False)} for x in r], 'statutory_distance_ft':500,'measurement':'longitudinal separation between complete body footprints'}

def crosswalk_context(c,r):
    return {'crosswalk_polygon_xy_m':c['crosswalk_polygon_xy_m'],'marked':c['marked'],'residence_district':c['residence_district'],'public_highway':c['public_highway']}

def simultaneous_backing_overlap(c,r):
    return {'samples':[{'frame':x['frame'],'backing':x['backing'],'body_crosswalk_overlap_m2':x['body_crosswalk_overlap_m2'],'position_xy_m':x['point_xy_m'],'heading_deg':x.get('heading_deg')} for x in r], 'boundary_note':'Geometric overlap only; legal boundary contact unresolved'}

def main():
    p=argparse.ArgumentParser();p.add_argument('--attempt',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    root=Path(a.attempt);cfg=read(root,'config.json');case=cfg['case'];context=read(root,'case_context.json');rows=read(root,'case_observations.jsonl');trace=read(root,'trace.jsonl')
    measurements={}
    for item in cfg['measurement_specs']:
        names=item['inputs'];value=globals()[item['method']](context,rows)
        measurements[item['output_key']]={'method':item['method'],'value':value,'sources':hashes(root,names)}
    Path(a.output).write_text(json.dumps({'case_id':case['case_id'],'measurements':measurements,'limitations':['Diagnostic fixture measurements are software examples only. Native motion, original pixels, source observations and legal conclusions require GPU review.']},indent=2)+'\n')
    channels=cfg['recording_description']['channels'];evidence=[]
    for channel in channels:
        name=channel['name'];target=root/('recorded_'+name.replace('.','_')+'.jsonl')
        if name=='kin.speed': values=[{'time_s':x['time_s'],'value':x['speed_mps']} for x in trace]
        else: values=[{'time_s':x['time_s'],'value':{'context':context,'sample':rows[min(i,len(rows)-1)]}} for i,x in enumerate(trace)]
        target.write_text(''.join(json.dumps(v)+'\n' for v in values));evidence.append({'name':name,'unit':channel['unit'],'reference':target.name})
    requested=case['variable_assignments']['target_speed_mps']['value'];measured=trace[-1]['speed_mps']
    result={'case_id':case['case_id'],'measured_values':{'target_speed_mps':measured},'target_checks':[{'target':'target_speed_mps','requested':requested,'measured':measured,'method':'last saved original velocity sample','tolerance':.1,'matched':abs(measured-requested)<=.1,'physical_cause_confirmed':False,'cause_evidence':'trace.jsonl'}],'setup_confirmed':False,'behavior_attempted':True,'maneuver_completed':False,'termination_reason':'saved diagnostic fixture or unverified native attempt','physical_failure_flags':{'physical_case_unverified':True},'trace_reference':'trace.jsonl','video_references':['raw.mkv'],'video_frame_map_reference':'video_frames.jsonl','recording_description':case['recording_description'],'recording_evidence':evidence,'realized_observables':{}}
    write_result(root,result)
if __name__=='__main__':main()
