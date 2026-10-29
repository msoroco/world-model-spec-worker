"""Case-specific saved diagnostic measurements; physical sources require Native capture."""
import argparse,hashlib,json
from pathlib import Path
from worker_exchange.native_output import write_result

def required(root,name):
    path=root/name
    if not path.is_file():raise ValueError("Missing required source: "+name)
    return path

def median_geometry(p):
    return {'right_roadway_polygon':p['right_roadway_polygon'],'opposing_roadway_polygon':p['opposing_roadway_polygon'],'barrier_polygons':p['barrier_polygons'],'opening_polygon':p['opening_polygon'],'opening_width_m':p['opening_width_m']}

def turn_trajectory(p):
    from shapely.geometry import MultiPoint,Polygon
    rows=p['trajectory'];first,last=rows[0],rows[-1]
    blockers=[Polygon(x) for x in p['barrier_polygons']]
    opening=Polygon(p['opening_polygon']);right=Polygon(p['right_roadway_polygon']);opposite=Polygon(p['opposing_roadway_polygon'])
    samples=[]
    for r in rows:
      hull=MultiPoint([v[:2] for v in r['body_vertices_m']]).convex_hull
      samples.append({'frame':r['frame'],'prohibited_divider_overlap':any(hull.intersects(x) for x in blockers),'opening_overlap':hull.intersects(opening),'right_roadway_overlap':hull.intersects(right),'opposing_roadway_overlap':hull.intersects(opposite)})
    return {'frames':len(rows),'initial_velocity_xy':first['velocity_xy'],'final_velocity_xy':last['velocity_xy'],'direction_dot':sum(a*b for a,b in zip(first['velocity_xy'],last['velocity_xy'])),'velocity_history':[r['velocity_xy'] for r in rows],'full_body_occupancy':samples,'median_body_overlap_frames':[r['frame'] for r in samples if r['prohibited_divider_overlap']]}

def authority_context(p):
    return p['authority_context']

def divider_relations(p):
    from shapely.geometry import MultiPoint,Polygon
    regions=[Polygon(v) for v in p['barrier_polygons']];rows=p['trajectory'];samples=[]
    for r in rows:
      vertices=r['body_vertices_m'];hull=MultiPoint([v[:2] for v in vertices]).convex_hull
      samples.append({'frame':r['frame'],'partial_xy_overlap':any(hull.intersects(q) for q in regions),'whole_body_xy_within':any(q.covers(hull) for q in regions),'body_bottom_z_m':min(v[2] for v in vertices),'body_top_z_m':max(v[2] for v in vertices),'divider_top_z_m':p.get('divider_top_z_m',.8),'body_lateral_min_y_m':min(v[1] for v in vertices),'body_lateral_max_y_m':max(v[1] for v in vertices)})
    return {'samples':samples,'initial_lateral_body_interval_m':[samples[0]['body_lateral_min_y_m'],samples[0]['body_lateral_max_y_m']],'final_lateral_body_interval_m':[samples[-1]['body_lateral_min_y_m'],samples[-1]['body_lateral_max_y_m']],'opening_source_models':p['opening_source_models'],'legal_over_across_within_definitions_not_assumed':True}

def turn_shape(p):
    import math
    rows=p['trajectory'];moving=[r for r in rows if sum(v*v for v in r['velocity_xy'])>0]
    first,last=moving[0]['velocity_xy'],moving[-1]['velocity_xy'];dot=sum(x*y for x,y in zip(first,last));cross=first[0]*last[1]-first[1]*last[0]
    centers=[[sum(v[j] for v in r['body_vertices_m'])/len(r['body_vertices_m']) for j in [0,1]] for r in rows]
    return {'actual_velocity_direction_change_deg':math.degrees(math.atan2(cross,dot)),'original_body_center_path_xy_m':centers,'original_velocity_xy':[r['velocity_xy'] for r in rows],'movement_count_is_not_a_legal_definition':True}

def statutory_observations(p):
    return {'divider_relations':divider_relations(p),'turn_shape':turn_shape(p),'turn_trajectory':turn_trajectory(p),'median_geometry':median_geometry(p),'authority_context':authority_context(p)}

def selected_scope_context(p):
    return {'authored_scope':p['scope_context'],'recorded_context':{k:v for k,v in p.items() if k not in ('motion_rows','trajectory','path_rows','indicator_rows','velocity_rows','scope_context')},'no_legal_scope_acceptance':True}

def finalize(root,output):
    source=required(root,"case_observation.json")
    p=json.loads(source.read_text())
    if p.get("law_id")!='NRS-484B-227-1':raise ValueError("Case observation law mismatch")
    h=hashlib.sha256(source.read_bytes()).hexdigest()
    measurements={}
    measurements['right_roadway_and_opening']={"method":'median_geometry',"value":median_geometry(p),"sources":{"case_observation.json":h}}
    measurements['authority_establishment_context']={'method':'authority_context','value':authority_context(p),'sources':{'case_observation.json':h}}
    measurements['complete_uturn_movement']={"method":'turn_trajectory',"value":turn_trajectory(p),"sources":{"case_observation.json":h}}
    measurements['complete_statutory_observations']={'method':'statutory_observations','value':statutory_observations(p),'sources':{'case_observation.json':h}}
    measurements['selected_scope_context']={'method':'selected_scope_context','value':selected_scope_context(p),'sources':{'case_observation.json':h}}
    measurements['over_across_within_observations']={'method':'divider_relations','value':divider_relations(p),'sources':{'case_observation.json':h}}
    measurements['turn_shape_observations']={'method':'turn_shape','value':turn_shape(p),'sources':{'case_observation.json':h}}
    report={"case_id":json.loads(required(root,"config.json").read_text())["selected_case_id"],"format":"worker-analysis-report-v1","measurements":measurements,"limitations":["Diagnostic fixture only; Native motion, source packets, four-view pixels and legal acceptance remain unverified."]}
    output.write_text(json.dumps(report,indent=2)+"\n")
    cfg=json.loads(required(root,"config.json").read_text())
    rows=[json.loads(line) for line in required(root,"trace.jsonl").read_text().splitlines() if line]
    (root/"channels").mkdir(exist_ok=True)
    channel_values={
      "original_motion":lambda row:{"position_m":row["position_m"],"velocity_mps":row["velocity_mps"],"speed_mps":row["speed_mps"]},
      "native_geometry":lambda row:{"right_roadway_polygon":p["right_roadway_polygon"],"opposing_roadway_polygon":p["opposing_roadway_polygon"],"opening_polygon":p["opening_polygon"]},
      "device_inventory":lambda row:{"barrier_polygons":p["barrier_polygons"],"public_authority_established":False},
      "view_provenance":lambda row:{"four_view_receipt":"four-view-receipt.json","pixel_visibility_verified":False}}
    for name,fn in channel_values.items():
      (root/"channels"/(name+".jsonl")).write_text(''.join(json.dumps({"time_s":row["time_s"],"value":fn(row)})+"\n" for row in rows))
    measured=max(row["speed_mps"] for row in rows)
    target=cfg["case"]["variable_assignments"]["requested_speed_mps"]["value"]
    result={"case_id":cfg["selected_case_id"],"measured_values":{"max_sampled_speed_mps":measured},
      "target_checks":[{"target":"requested_speed_mps","requested":target,"measured":measured,
       "method":"maximum original Native speed sample","tolerance":5,"matched":abs(measured-target)<=5,
       "physical_cause_confirmed":False,"cause_evidence":"trace.jsonl;case_observation.json"}],
      "setup_confirmed":False,"behavior_attempted":True,"maneuver_completed":False,
      "termination_reason":"saved capability analysis; actual U-turn and authority exception need local review",
      "physical_failure_flags":{"detection_validated":False},"trace_reference":"trace.jsonl",
      "video_references":["raw.mkv"],"video_frame_map_reference":"video_frames.jsonl",
      "recording_description":cfg["case"]["recording_description"],
      "recording_evidence":[{"name":name,"unit":"structured record","reference":"channels/"+name+".jsonl"} for name in channel_values],
      "realized_observables":{}}
    write_result(root,result)
    return report

if __name__=="__main__":
    a=argparse.ArgumentParser();a.add_argument("--attempt",required=True);a.add_argument("--output",required=True);v=a.parse_args();finalize(Path(v.attempt),Path(v.output))
