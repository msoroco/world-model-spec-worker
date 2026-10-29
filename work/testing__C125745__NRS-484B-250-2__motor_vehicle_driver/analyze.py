"""Case-specific saved diagnostic measurements; physical sources require Native capture."""
import argparse,hashlib,json
from pathlib import Path
from worker_exchange.native_output import write_result

def required(root,name):
    path=root/name
    if not path.is_file():raise ValueError("Missing required source: "+name)
    return path

def crossing_side(p):
    e,o=p['ego_approach_xy'],p['other_approach_xy']; cross=e[0]*o[1]-e[1]*o[0]; return {'ego_approach_xy':e,'other_approach_xy':o,'signed_cross_product':cross,'crossing_id':p['crossing_id']}

def entry_time_difference(p):
    events=p['entry_events'];return {'ego_frame':events['ego']['frame'],'other_frame':events['other']['frame'],'absolute_time_difference_s':abs(events['ego']['time_s']-events['other']['time_s']),'resolution_s':p['resolution_s'],'threshold_selected':False}

def precedence_history(p):
    rows=p['motion_rows'];return {'rows':len(rows),'ego_speed_mps':[r['ego_speed_mps'] for r in rows],'other_speed_mps':[r['other_speed_mps'] for r in rows],'ego_clearance_frame':p['ego_clearance_frame'],'other_clearance_frame':p['other_clearance_frame']}

def governing_control(p):
    return {'native_inventory':p.get('official_control_inventory',[]),'context':p.get('control_context',{'governing_control':'none'}),'opposite_context':p.get('opposite_context',{'opposite_approach':False})}

def statutory_observations(p):
    return {'entry_time_difference':entry_time_difference(p),'crossing_side':crossing_side(p),'precedence_history':precedence_history(p),'governing_control':governing_control(p)}

def selected_scope_context(p):
    return {'authored_scope':p['scope_context'],'recorded_context':{k:v for k,v in p.items() if k not in ('motion_rows','trajectory','path_rows','indicator_rows','velocity_rows','scope_context')},'no_legal_scope_acceptance':True}

def finalize(root,output):
    source=required(root,"case_observation.json")
    p=json.loads(source.read_text())
    if p.get("law_id")!='NRS-484B-250-2':raise ValueError("Case observation law mismatch")
    h=hashlib.sha256(source.read_bytes()).hexdigest()
    measurements={'governing_control_and_opposite_context':{'method':'governing_control','value':governing_control(p),'sources':{'case_observation.json':h}}}
    measurements['left_right_approach_geometry']={"method":'crossing_side',"value":crossing_side(p),"sources":{"case_observation.json":h}}
    measurements['two_entry_timing']={"method":'entry_time_difference',"value":entry_time_difference(p),"sources":{"case_observation.json":h}}
    measurements['crossing_precedence_motion']={"method":'precedence_history',"value":precedence_history(p),"sources":{"case_observation.json":h}}
    measurements['complete_statutory_observations']={'method':'statutory_observations','value':statutory_observations(p),'sources':{'case_observation.json':h}}
    measurements['selected_scope_context']={'method':'selected_scope_context','value':selected_scope_context(p),'sources':{'case_observation.json':h}}
    report={"case_id":json.loads(required(root,"config.json").read_text())["selected_case_id"],"format":"worker-analysis-report-v1","measurements":measurements,"limitations":["Diagnostic fixture only; Native motion, source packets, four-view pixels and legal acceptance remain unverified."]}
    output.write_text(json.dumps(report,indent=2)+"\n")
    cfg=json.loads(required(root,"config.json").read_text())
    rows=[json.loads(line) for line in required(root,"trace.jsonl").read_text().splitlines() if line]
    (root/"channels").mkdir(exist_ok=True)
    channel_values={
      "original_motion":lambda row:{"position_m":row["position_m"],"velocity_mps":row["velocity_mps"],"speed_mps":row["speed_mps"]},
      "native_geometry":lambda row:{"crossing_id":p.get("crossing_id","road1-road3-opening"),"intersection_polygon":p["intersection_polygon"]},
      "device_inventory":lambda row:{"official_controls":p.get("official_control_inventory",[])},
      "view_provenance":lambda row:{"four_view_receipt":"four-view-receipt.json","pixel_visibility_verified":False}}
    for name,fn in channel_values.items():
      (root/"channels"/(name+".jsonl")).write_text(''.join(json.dumps({"time_s":row["time_s"],"value":fn(row)})+"\n" for row in rows))
    measured=max(r["ego_speed_mps"] for r in p["motion_rows"])
    target=cfg["case"]["variable_assignments"]["requested_speed_mps"]["value"]
    result={"case_id":cfg["selected_case_id"],"measured_values":{"max_ego_speed_mps":measured},
      "target_checks":[{"target":"requested_speed_mps","requested":target,"measured":measured,
       "method":"maximum original Native speed sample","tolerance":3,"matched":abs(measured-target)<=3,
       "physical_cause_confirmed":False,"cause_evidence":"trace.jsonl;case_observation.json"}],
      "setup_confirmed":False,"behavior_attempted":True,"maneuver_completed":False,
      "termination_reason":"saved capability analysis; Native crossing motion and legal right-of-way require review",
      "physical_failure_flags":{"detection_validated":False},"trace_reference":"trace.jsonl",
      "video_references":["raw.mkv"],"video_frame_map_reference":"video_frames.jsonl",
      "recording_description":cfg["case"]["recording_description"],
      "recording_evidence":[{"name":name,"unit":"structured record","reference":"channels/"+name+".jsonl"} for name in channel_values],
      "realized_observables":{}}
    write_result(root,result)
    return report

if __name__=="__main__":
    a=argparse.ArgumentParser();a.add_argument("--attempt",required=True);a.add_argument("--output",required=True);v=a.parse_args();finalize(Path(v.attempt),Path(v.output))
