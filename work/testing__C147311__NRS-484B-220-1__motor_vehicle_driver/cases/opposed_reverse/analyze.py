"""Case-specific saved diagnostic measurements; physical sources require Native capture."""
import argparse,hashlib,json
from pathlib import Path
from worker_exchange.native_output import write_result

def required(root,name):
    path=root/name
    if not path.is_file():raise ValueError("Missing required source: "+name)
    return path

def sign_scope(p):
    s=p['direction_sign'];return {'native_id':s['native_id'],'text':s['text'],'orientation_deg':s['orientation_deg'],'governs_roadway_indices':s['governs_roadway_indices'],'original_frames':s['original_frames'],'one_way_lanes':p['one_way_lanes']}

def direction_projection(p):
    d=p['designated_direction_xy'];rows=p['velocity_rows'];return {'designated_direction_xy':d,'signed_projections_mps':[sum(a*b for a,b in zip(d,r['velocity_xy'])) for r in rows],'original_frames':[r['frame'] for r in rows]}

def statutory_observations(p):
    return {'direction_projection':direction_projection(p),'sign_scope':sign_scope(p)}

def selected_scope_context(p):
    return {'authored_scope':p['scope_context'],'recorded_context':{k:v for k,v in p.items() if k not in ('motion_rows','trajectory','path_rows','indicator_rows','velocity_rows','scope_context')},'no_legal_scope_acceptance':True}

def finalize(root,output):
    source=required(root,"case_observation.json")
    p=json.loads(source.read_text())
    if p.get("law_id")!='NRS-484B-220-1':raise ValueError("Case observation law mismatch")
    h=hashlib.sha256(source.read_bytes()).hexdigest()
    measurements={}
    measurements['governing_direction_sign']={"method":'sign_scope',"value":sign_scope(p),"sources":{"case_observation.json":h}}
    measurements['actual_travel_direction']={"method":'direction_projection',"value":direction_projection(p),"sources":{"case_observation.json":h}}
    measurements['complete_statutory_observations']={'method':'statutory_observations','value':statutory_observations(p),'sources':{'case_observation.json':h}}
    measurements['selected_scope_context']={'method':'selected_scope_context','value':selected_scope_context(p),'sources':{'case_observation.json':h}}
    report={"case_id":json.loads(required(root,"config.json").read_text())["selected_case_id"],"format":"worker-analysis-report-v1","measurements":measurements,"limitations":["Diagnostic fixture only; Native motion, source packets, four-view pixels and legal acceptance remain unverified."]}
    output.write_text(json.dumps(report,indent=2)+"\n")
    cfg=json.loads(required(root,"config.json").read_text())
    rows=[json.loads(line) for line in required(root,"trace.jsonl").read_text().splitlines() if line]
    (root/"channels").mkdir(exist_ok=True)
    channel_values={
      "original_motion":lambda row:{"position_m":row["position_m"],"velocity_mps":row["velocity_mps"],"heading_deg":row["heading_deg"]},
      "native_geometry":lambda row:{"road_id":1,"one_way_lanes":p["one_way_lanes"]},
      "device_inventory":lambda row:p["direction_sign"],
      "view_provenance":lambda row:{"four_view_receipt":"four-view-receipt.json","pixel_visibility_verified":False}}
    for name,fn in channel_values.items():
      (root/"channels"/(name+".jsonl")).write_text(''.join(json.dumps({"time_s":row["time_s"],"value":fn(row)})+"\n" for row in rows))
    projection=measurements["actual_travel_direction"]["value"]["signed_projections_mps"]
    result={"case_id":cfg["selected_case_id"],"measured_values":{"signed_velocity_projection_mps":projection},
      "target_checks":[{"target":"designated_direction_projection","requested":cfg["case"]["variable_assignments"]["requested_speed_mps"]["value"],"measured":max(projection),
       "method":"maximum original velocity projection onto designated direction","tolerance":2,"matched":abs(max(projection)-cfg["case"]["variable_assignments"]["requested_speed_mps"]["value"])<=2,
       "physical_cause_confirmed":False,"cause_evidence":"trace.jsonl;case_observation.json"}],
      "setup_confirmed":False,"behavior_attempted":True,"maneuver_completed":False,
      "termination_reason":"saved diagnostic analysis; Native and pixel checks pending",
      "physical_failure_flags":{"detection_validated":False},"trace_reference":"trace.jsonl",
      "video_references":["raw.mkv"],"video_frame_map_reference":"video_frames.jsonl",
      "recording_description":cfg["case"]["recording_description"],
      "recording_evidence":[{"name":name,"unit":"structured record","reference":"channels/"+name+".jsonl"} for name in channel_values],
      "realized_observables":{}}
    write_result(root,result)
    return report

if __name__=="__main__":
    a=argparse.ArgumentParser();a.add_argument("--attempt",required=True);a.add_argument("--output",required=True);v=a.parse_args();finalize(Path(v.attempt),Path(v.output))
