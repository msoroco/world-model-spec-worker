"""Case-specific saved diagnostic measurements; physical sources require Native capture."""
import argparse,hashlib,json
from pathlib import Path
from worker_exchange.native_output import write_result

def required(root,name):
    path=root/name
    if not path.is_file():raise ValueError("Missing required source: "+name)
    return path

def crossing_geometry(p):
    assert len(p['highway_ids']) == 2 and p['intersection_polygon']; return {'highway_ids':p['highway_ids'],'intersection_polygon':p['intersection_polygon'],'separate_crossing_spacing_m':p['separate_crossing_spacing_m']}

def earlier_entry(p):
    events=p['entry_events']; return {'other':events['other'],'ego':events['ego'],'time_difference_s':events['ego']['time_s']-events['other']['time_s']}

def precedence_history(p):
    rows=p['motion_rows']; assert rows; return {'rows':len(rows),'minimum_ego_speed_mps':min(r['ego_speed_mps'] for r in rows),'other_clearance_time_s':p['other_clearance_time_s'],'ego_entry_time_s':p['entry_events']['ego']['time_s']}

def governing_control(p):
    return {'native_inventory':p.get('official_control_inventory',[]),'context':p.get('control_context',{'governing_control':'none'}),'opposite_context':p.get('opposite_context',{'opposite_approach':False})}

def statutory_observations(p):
    return {'earlier_entry':earlier_entry(p),'crossing_geometry':crossing_geometry(p),'precedence_history':precedence_history(p),'governing_control':governing_control(p)}

def selected_scope_context(p):
    return {'authored_scope':p['scope_context'],'recorded_context':{k:v for k,v in p.items() if k not in ('motion_rows','trajectory','path_rows','indicator_rows','velocity_rows','scope_context')},'no_legal_scope_acceptance':True}

def finalize(root,output):
    source=required(root,"case_observation.json")
    p=json.loads(source.read_text())
    if p.get("law_id")!='NRS-484B-250-1':raise ValueError("Case observation law mismatch")
    h=hashlib.sha256(source.read_bytes()).hexdigest()
    measurements={'governing_control_and_opposite_context':{'method':'governing_control','value':governing_control(p),'sources':{'case_observation.json':h}}}
    measurements['same_crossing_geometry']={"method":'crossing_geometry',"value":crossing_geometry(p),"sources":{"case_observation.json":h}}
    measurements['other_entered_first']={"method":'earlier_entry',"value":earlier_entry(p),"sources":{"case_observation.json":h}}
    measurements['ego_yield_motion']={"method":'precedence_history',"value":precedence_history(p),"sources":{"case_observation.json":h}}
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
