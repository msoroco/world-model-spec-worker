"""Case-specific saved diagnostic measurements; physical sources require Native capture."""
import argparse,hashlib,json
from pathlib import Path
from worker_exchange.native_output import write_result

def required(root,name):
    path=root/name
    if not path.is_file():raise ValueError("Missing required source: "+name)
    return path

def traffic_speed(p):
    rows=p['motion_rows'];return {'max_ego_speed_mps':max(r['ego_speed_mps'] for r in rows),'other_speed_mps':[r['other_speed_mps'] for r in rows],'separations_m':[r['separation_m'] for r in rows],'original_frames':[r['frame'] for r in rows]}

def road_conditions(p):
    return {'highway_width_m':p['highway_width_m'],'roadway_width_m':p['roadway_width_m'],'shoulder_each_m':p['shoulder_each_m'],'curvature_per_m':p['curvature_per_m'],'surface':p['surface'],'surface_provenance':p['surface_provenance']}

def environment_history(p):
    return {'weather_rows':p['weather_rows'],'target_visibility_samples_m':p['target_visibility_samples_m'],'sight_ray_samples':p['sight_ray_samples'],'stopping_event':p['stopping_event'],'no_adequacy_or_reasonableness_verdict':True}

def finalize(root,output):
    source=required(root,"case_observation.json")
    p=json.loads(source.read_text())
    if p.get("law_id")!='NRS-484B-600-1a':raise ValueError("Case observation law mismatch")
    h=hashlib.sha256(source.read_bytes()).hexdigest()
    measurements={}
    measurements['contemporaneous_speed_and_traffic']={"method":'traffic_speed',"value":traffic_speed(p),"sources":{"case_observation.json":h}}
    measurements['width_curvature_and_surface']={"method":'road_conditions',"value":road_conditions(p),"sources":{"case_observation.json":h}}
    measurements['weather_visibility_sight_and_stopping_context']={"method":'environment_history',"value":environment_history(p),"sources":{"case_observation.json":h}}
    report={"format":"worker-analysis-report-v1","measurements":measurements,"limitations":["Diagnostic fixture only; Native motion, source packets, four-view pixels and legal acceptance remain unverified."]}
    output.write_text(json.dumps(report,indent=2)+"\n")
    cfg=json.loads(required(root,"config.json").read_text())
    rows=[json.loads(line) for line in required(root,"trace.jsonl").read_text().splitlines() if line]
    (root/"channels").mkdir(exist_ok=True)
    channel_values={
      "original_motion":lambda row:{"position_m":row["position_m"],"velocity_mps":row["velocity_mps"],"speed_mps":row["speed_mps"]},
      "native_geometry":lambda row:{"road_id":1,"highway_width_m":p["highway_width_m"],"surface":p["surface"]},
      "device_inventory":lambda row:{"devices":[],"inventory_scope":"Native non-vehicle controls must be inspected"},
      "view_provenance":lambda row:{"four_view_receipt":"four-view-receipt.json","pixel_visibility_verified":False},
      "environment_history":lambda row:{"weather":p["weather_rows"],"target_visibility_samples_m":p["target_visibility_samples_m"],"sight_ray_samples":p["sight_ray_samples"]}}
    for name,fn in channel_values.items():
      (root/"channels"/(name+".jsonl")).write_text(''.join(json.dumps({"time_s":row["time_s"],"value":fn(row)})+"\n" for row in rows))
    measured=measurements["contemporaneous_speed_and_traffic"]["value"]["max_ego_speed_mps"]
    target=cfg["case"]["variable_assignments"]["requested_speed_mps"]["value"]
    result={"case_id":cfg["selected_case_id"],"measured_values":{"max_ego_speed_mps":measured},
      "target_checks":[{"target":"requested_speed_mps","requested":target,"measured":measured,
       "method":"maximum original Native velocity norm","tolerance":2,"matched":abs(measured-target)<=2,
       "physical_cause_confirmed":False,"cause_evidence":"trace.jsonl;case_observation.json"}],
      "setup_confirmed":False,"behavior_attempted":True,"maneuver_completed":False,
      "termination_reason":"saved capability analysis; physical conditions need local verification",
      "physical_failure_flags":{"detection_validated":False},"trace_reference":"trace.jsonl",
      "video_references":["raw.mkv"],"video_frame_map_reference":"video_frames.jsonl",
      "recording_description":cfg["case"]["recording_description"],
      "recording_evidence":[{"name":name,"unit":"structured record","reference":"channels/"+name+".jsonl"} for name in channel_values],
      "realized_observables":{}}
    write_result(root,result)
    return report

if __name__=="__main__":
    a=argparse.ArgumentParser();a.add_argument("--attempt",required=True);a.add_argument("--output",required=True);v=a.parse_args();finalize(Path(v.attempt),Path(v.output))
