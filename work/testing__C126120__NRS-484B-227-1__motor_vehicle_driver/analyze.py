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
    rows=p['trajectory'];first,last=rows[0],rows[-1];dot=sum(a*b for a,b in zip(first['velocity_xy'],last['velocity_xy']));return {'frames':len(rows),'initial_velocity_xy':first['velocity_xy'],'final_velocity_xy':last['velocity_xy'],'direction_dot':dot,'median_body_overlap_frames':[r['frame'] for r in rows if r['body_overlaps_median']]}

def finalize(root,output):
    source=required(root,"case_observation.json")
    p=json.loads(source.read_text())
    if p.get("law_id")!='NRS-484B-227-1':raise ValueError("Case observation law mismatch")
    h=hashlib.sha256(source.read_bytes()).hexdigest()
    measurements={}
    measurements['right_roadway_and_opening']={"method":'median_geometry',"value":median_geometry(p),"sources":{"case_observation.json":h}}
    measurements['complete_uturn_movement']={"method":'turn_trajectory',"value":turn_trajectory(p),"sources":{"case_observation.json":h}}
    report={"format":"worker-analysis-report-v1","measurements":measurements,"limitations":["Diagnostic fixture only; Native motion, source packets, four-view pixels and legal acceptance remain unverified."]}
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
