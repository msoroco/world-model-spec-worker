"""Case-specific saved diagnostic measurements; physical sources require Native capture."""
import argparse,hashlib,json
from pathlib import Path
from worker_exchange.native_output import write_result

def required(root,name):
    path=root/name
    if not path.is_file():raise ValueError("Missing required source: "+name)
    return path

def traffic_speed(p):
    rows=p['motion_rows'];return {'max_ego_speed_mps':max(r['ego_speed_mps'] for r in rows),'other_speed_mps':[r['other_speed_mps'] for r in rows],'separations_m':[r['separation_m'] for r in rows],'original_frames':[r['frame'] for r in rows],'traffic_actor_inventory_by_frame':p.get('traffic_actor_inventory_by_frame',[]),'traffic_definition_not_exhausted_by_vehicle_inventory':True}

def road_conditions(p):
    return {'highway_width_m':p['highway_width_m'],'roadway_width_m':p['roadway_width_m'],'shoulder_each_m':p['shoulder_each_m'],'curvature_per_m':p['curvature_per_m'],'surface':p['surface'],'surface_provenance':p['surface_provenance']}

def environment_history(p):
    return {'visibility_calibration':p['visibility_calibration'],'weather_rows':p['weather_rows'],'target_visibility_samples_m':p['target_visibility_samples_m'],'sight_ray_samples':p['sight_ray_samples'],'stopping_event':p['stopping_event'],'no_adequacy_or_reasonableness_verdict':True}

def read_calibrated_visibility(root):
    source=required(root,'environment_calibration.json');cal=json.loads(source.read_text());sources={'environment_calibration.json':hashlib.sha256(source.read_bytes()).hexdigest()};samples=[]
    for sample in cal['samples']:
      for channel in ('rgb','instance'):
        path=required(root,sample[channel]['path']);digest=hashlib.sha256(path.read_bytes()).hexdigest()
        if digest!=sample[channel]['sha256']:raise ValueError('Calibration original image hash mismatch: '+sample[channel]['path'])
        sources[sample[channel]['path']]=digest
      samples.append({'calibration_native_frame':sample['frame'],'sample_range_m':sample['longitudinal_range_m'],'target_pixels':sample['target_pixels'],'weber_contrast':sample['weber_contrast'],'contrast_detected':sample['contrast_detected'],'rgb_source':sample['rgb'],'instance_source':sample['instance']})
    return {'visibility_m':cal['visibility_m'],'distance_kind':cal['distance_kind'],'method':cal['method'],'original_contrast_samples':samples,'calibration_weather':cal['weather'],'uncertainty':cal['uncertainty'],'not_geometric_sight_distance':True,'not_a_legal_visibility_threshold':True},sources

def statutory_observations(p):
    return {'traffic_speed':traffic_speed(p),'road_conditions':road_conditions(p),'environment_history':environment_history(p)}

def selected_scope_context(p):
    return {'authored_scope':p['scope_context'],'recorded_context':{k:v for k,v in p.items() if k not in ('motion_rows','trajectory','path_rows','indicator_rows','velocity_rows','scope_context')},'no_legal_scope_acceptance':True}

def finalize(root,output):
    source=required(root,"case_observation.json")
    p=json.loads(source.read_text())
    if p.get("law_id")!='NRS-484B-600-1a':raise ValueError("Case observation law mismatch")
    h=hashlib.sha256(source.read_bytes()).hexdigest()
    visibility,calibration_hashes=read_calibrated_visibility(root)
    p['visibility_calibration']=visibility
    measurements={}
    measurements['contemporaneous_speed_and_traffic']={"method":'traffic_speed',"value":traffic_speed(p),"sources":{"case_observation.json":h,**calibration_hashes}}
    measurements['width_curvature_and_surface']={"method":'road_conditions',"value":road_conditions(p),"sources":{"case_observation.json":h,**calibration_hashes}}
    measurements['weather_visibility_sight_and_stopping_context']={"method":'environment_history',"value":environment_history(p),"sources":{"case_observation.json":h,**calibration_hashes}}
    measurements['complete_statutory_observations']={'method':'statutory_observations','value':statutory_observations(p),'sources':{'case_observation.json':h,**calibration_hashes}}
    measurements['selected_scope_context']={'method':'selected_scope_context','value':selected_scope_context(p),'sources':{'case_observation.json':h,**calibration_hashes}}
    report={"case_id":json.loads(required(root,"config.json").read_text())["selected_case_id"],"format":"worker-analysis-report-v1","measurements":measurements,"limitations":["Diagnostic fixture only; Native motion, source packets, four-view pixels and legal acceptance remain unverified."]}
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
