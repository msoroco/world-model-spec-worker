"""Saved-source 400-2b finalizer; fixtures are diagnostic, not physical findings."""
import argparse, hashlib, json, math
from pathlib import Path
from worker_exchange.native_output import write_result

def source(root, name):
    path = root / name
    if not path.is_file():
        raise ValueError('Missing required source: ' + name)
    return json.loads(path.read_text()) if name.endswith('.json') else [json.loads(s) for s in path.read_text().splitlines() if s.strip()]

def hashes(root, names):
    return {n: hashlib.sha256((root / n).read_bytes()).hexdigest() for n in names}

def public_highway_context(context):
    return {k: context[k] for k in ('public_dedication', 'public_vehicle_access', 'non_alley')}

def bidirectional_intersection(road):
    return {k: road[k] for k in ('road_ids', 'directions_by_road', 'intersection_polygon_xy_m')}

def left_turn_control(route):
    return {k: route[k] for k in ('actor_role', 'control_mode', 'intended_route', 'recorded_frames')}

def exit_centerline_offset(road, rows):
    dx, dy = road['exit_direction_xy']
    cx, cy = road['exit_centerline_point_xy_m']
    norm = math.hypot(dx, dy)
    if norm <= 0 or not rows: raise ValueError('Directed exit centerline and body samples required')
    south = min(p[1] for p in road['intersection_polygon_xy_m'])
    candidates = [row for row in rows if max(v[1] for v in row['body_vertices_xy_m']) < south]
    if not candidates: raise ValueError('No full-body intersection exit observed')
    row = candidates[0]
    offsets = [(dx * (y-cy) - dy * (x-cx))/norm for x,y in row['body_vertices_xy_m']]
    return {'exit_frame':row['frame'],'exit_time_s':row['time_s'],'signed_vertex_distances_m':offsets,'minimum_m':min(offsets),'maximum_m':max(offsets),'exit_direction_xy':[dx,dy],'intersection_exit_y_m':south,'sampling_note':'first sampled full-body exit; legal right-of-centerline finding requires native direction and original-frame review'}

def main():
    p=argparse.ArgumentParser(); p.add_argument('--attempt',required=True); p.add_argument('--output',required=True); a=p.parse_args()
    root=Path(a.attempt)
    case=source(root,'config.json')['case']
    road=source(root,'road_geometry.json')
    context=source(root,'law_context.json')
    route=source(root,'route_control.json')
    vertices=source(root,'exit_body_vertices.jsonl')
    traces=source(root,'trace.jsonl')
    measurements={
        'public_highway_context': {'method':'public_highway_context','value':public_highway_context(context),'sources':hashes(root,['law_context.json'])},
        'two_directional_intersection': {'method':'bidirectional_intersection','value':bidirectional_intersection(road),'sources':hashes(root,['road_geometry.json'])},
        'driver_left_turn_control': {'method':'left_turn_control','value':left_turn_control(route),'sources':hashes(root,['route_control.json'])},
        'intersection_exit_centerline': {'method':'exit_centerline_offset','value':exit_centerline_offset(road,vertices),'sources':hashes(root,['road_geometry.json','exit_body_vertices.jsonl'])},
    }
    Path(a.output).write_text(json.dumps({'case_id':case['case_id'],'measurements':measurements,'limitations':['Diagnostic fixture only; actual native geometry, actor motion, pixels and public-way facts remain unverified.','No legal boundary or compliance finding.']},indent=2)+'\n')
    speed=[{'time_s':r['time_s'],'value':r['speed_mps']} for r in traces]
    (root/'speed.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in speed))
    for name,value in [('roadway_geometry',measurements['two_directional_intersection']['value']),('driver_control',measurements['driver_left_turn_control']['value']),('exit_position',measurements['intersection_exit_centerline']['value'])]:
        (root/(name+'.jsonl')).write_text(''.join(json.dumps({'time_s':r['time_s'],'value':value})+'\n' for r in traces))
    measured=speed[-1]['value'];requested=case['variable_assignments']['approach_speed_mps']['value']
    result={'case_id':case['case_id'],'measured_values':{'approach_speed_mps':measured},'target_checks':[{'target':'approach_speed_mps','requested':requested,'measured':measured,'method':'last saved original velocity sample','tolerance':.1,'matched':abs(measured-requested)<=.1,'physical_cause_confirmed':False,'cause_evidence':'trace.jsonl'}],'setup_confirmed':False,'behavior_attempted':True,'maneuver_completed':False,'termination_reason':'three-frame retained diagnostic fixture','physical_failure_flags':{'native_left_turn_verified':False},'trace_reference':'trace.jsonl','video_references':['raw.mkv'],'video_frame_map_reference':'video_frames.jsonl','recording_description':case['recording_description'],'recording_evidence':[{'name':name,'unit':unit,'reference':file} for name,unit,file in [('kin.speed','m/s','speed.jsonl'),('roadway_geometry','structured','roadway_geometry.jsonl'),('driver_control','structured','driver_control.jsonl'),('exit_position','structured','exit_position.jsonl')]],'realized_observables':{}}
    write_result(root,result)
if __name__=='__main__': main()
