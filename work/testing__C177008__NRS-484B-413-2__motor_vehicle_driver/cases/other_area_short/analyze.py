"""Case-specific saved diagnostic measurements; physical sources require Native capture."""
import argparse,hashlib,json
from pathlib import Path
from worker_exchange.native_output import write_result

def required(root,name):
    path=root/name
    if not path.is_file():raise ValueError("Missing required source: "+name)
    return path

def district_frontage(p):
    return {'frontage_m':p['frontage_m'],'business_use_frontage_m':p['business_use_frontage_m'],'residence_use_frontage_m':p.get('residence_use_frontage_m',0),'road_id':p['road_id'],'source':p['district_source'],'district_class':p.get('district_class','business'),'weather_context':p.get('weather_context',{})}

def approach_path(p):
    rows=p['path_rows'];segments=[((b['x_m']-a['x_m'])**2+(b['y_m']-a['y_m'])**2)**.5 for a,b in zip(rows,rows[1:])];distance=sum(segments);remaining=0;start=len(rows)-1
    for i in range(len(segments)-1,-1,-1):
        remaining+=segments[i];start=i
        if remaining>=p.get('threshold_ft',100)*.3048:
            if remaining>p.get('threshold_ft',100)*.3048:start=min(start+1,len(rows)-1)
            break
    return {'path_distance_m':distance,'last_100ft_start_index':start,'last_100ft_sampled_distance_m':remaining,'reference_is_engineering_onset':True,'distance_window_bracket_m':[max(0,remaining-(segments[start-1] if start else 0)),remaining],'turn_onset_frame':p['turn_onset_frame'],'sample_count':len(rows),'threshold_ft':p.get('threshold_ft',100),'threshold_m':p.get('threshold_ft',100)*.3048}

def indicator_continuity(p):
    start=approach_path(p)['last_100ft_start_index'];rows=p['indicator_rows'][start:];return {'original_frames':[r['frame'] for r in rows],'lamp_bits':[r['lamp_bits'] for r in rows],'body_roi_luminance_samples':[r['pixel_luminance'] for r in rows if isinstance(r['pixel_luminance'],(int,float))],'continuous_api_on':all(r['lamp_bits'] for r in rows),'pixel_visibility_verified':False,'body_roi_is_not_lamp_mask':True}

def loading_zone(p):
    return {'zone_polygon':p['zone_polygon'],'route_distance_m':p['zone_route_distance_m'],'designation_source':p['zone_designation_source']}

def statutory_observations(p):
    return {'approach_path':approach_path(p),'indicator_continuity':indicator_continuity(p),'district_frontage':district_frontage(p)}

def selected_scope_context(p):
    return {'authored_scope':p['scope_context'],'recorded_context':{k:v for k,v in p.items() if k not in ('motion_rows','trajectory','path_rows','indicator_rows','velocity_rows','scope_context')},'no_legal_scope_acceptance':True}

def finalize(root,output):
    source=required(root,"case_observation.json")
    p=json.loads(source.read_text())
    if p.get("law_id")!='NRS-484B-413-2':raise ValueError("Case observation law mismatch")
    h=hashlib.sha256(source.read_bytes()).hexdigest()
    measurements={}
    measurements['business_district_context']={"method":'district_frontage',"value":district_frontage(p),"sources":{"case_observation.json":h}}
    measurements['last_100ft_traveled_path']={"method":'approach_path',"value":approach_path(p),"sources":{"case_observation.json":h}}
    measurements['original_lamp_display_history']={"method":'indicator_continuity',"value":indicator_continuity(p),"sources":{"case_observation.json":h}}
    measurements['designated_zone_location']={"method":'loading_zone',"value":loading_zone(p),"sources":{"case_observation.json":h}}
    measurements['complete_statutory_observations']={'method':'statutory_observations','value':statutory_observations(p),'sources':{'case_observation.json':h}}
    measurements['selected_scope_context']={'method':'selected_scope_context','value':selected_scope_context(p),'sources':{'case_observation.json':h}}
    report={"case_id":json.loads(required(root,"config.json").read_text())["selected_case_id"],"format":"worker-analysis-report-v1","measurements":measurements,"limitations":["Diagnostic fixture only; Native motion, source packets, four-view pixels and legal acceptance remain unverified."]}
    output.write_text(json.dumps(report,indent=2)+"\n")
    cfg=json.loads(required(root,"config.json").read_text())
    rows=[json.loads(line) for line in required(root,"trace.jsonl").read_text().splitlines() if line]
    (root/"channels").mkdir(exist_ok=True)
    channel_values={
      "original_motion":lambda row:{"position_m":row["position_m"],"velocity_mps":row["velocity_mps"],"speed_mps":row["speed_mps"]},
      "native_geometry":lambda row:{"road_id":p["road_id"],"turn_onset_frame":p["turn_onset_frame"],"frontage_m":p["frontage_m"],"zone_polygon":p["zone_polygon"]},
      "device_inventory":lambda row:{"indicator_rows":p["indicator_rows"],"zone_designation_source":p["zone_designation_source"]},
      "view_provenance":lambda row:{"four_view_receipt":"four-view-receipt.json","pixel_visibility_verified":False}}
    for name,fn in channel_values.items():
      (root/"channels"/(name+".jsonl")).write_text(''.join(json.dumps({"time_s":row["time_s"],"value":fn(row)})+"\n" for row in rows))
    measured=max(row["speed_mps"] for row in rows)
    target=cfg["case"]["variable_assignments"]["requested_speed_mps"]["value"]
    result={"case_id":cfg["selected_case_id"],"measured_values":{"max_sampled_speed_mps":measured},
      "target_checks":[{"target":"requested_speed_mps","requested":target,"measured":measured,
       "method":"maximum original Native speed sample","tolerance":6,"matched":abs(measured-target)<=6,
       "physical_cause_confirmed":False,"cause_evidence":"trace.jsonl;case_observation.json"}],
      "setup_confirmed":False,"behavior_attempted":True,"maneuver_completed":False,
      "termination_reason":"saved capability analysis; emitted signal pixels and district status need local review",
      "physical_failure_flags":{"detection_validated":False},"trace_reference":"trace.jsonl",
      "video_references":["raw.mkv"],"video_frame_map_reference":"video_frames.jsonl",
      "recording_description":cfg["case"]["recording_description"],
      "recording_evidence":[{"name":name,"unit":"structured record","reference":"channels/"+name+".jsonl"} for name in channel_values],
      "realized_observables":{}}
    write_result(root,result)
    return report

if __name__=="__main__":
    a=argparse.ArgumentParser();a.add_argument("--attempt",required=True);a.add_argument("--output",required=True);v=a.parse_args();finalize(Path(v.attempt),Path(v.output))
