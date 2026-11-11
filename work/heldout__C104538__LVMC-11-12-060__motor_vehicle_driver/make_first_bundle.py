"""Build first exact station case as a CPU diagnostic construction draft.

Its site source is explicitly synthetic. Native run refuses this site until a
real source-bound fire-station survey replaces it.
"""
import hashlib
import json
from pathlib import Path

from fire_station_camera_capture import CAMERAS

root=Path(__file__).resolve().parent
repo=root.parents[1]
assignment=root.name
case_id=assignment+'__front_of_entrance'
site={'kind':'authored_diagnostic','asset_id':'cpu-station-schematic',
      'physical_site':False,'map_name':'CPUStationSchematic',
      'notes':'Textual geometry for software proof only; no Native station map is asserted.'}
site_path=root/'diagnostic-station-site.json'
site_path.write_text(json.dumps(site,indent=2)+'\n')
source={'kind':'authored_diagnostic','asset_id':site['asset_id'],
        'source_sha256':hashlib.sha256(site_path.read_bytes()).hexdigest()}
def ref(road,lane,s):return {'road_id':road,'lane_id':lane,'s':s}
survey={'map_name':site['map_name'],'station_source':source,
        'public_before':ref(7,1,0),'public_at':ref(7,1,8),
        'public_after':ref(7,1,16),'driveway_at':ref(8,2,6),
        'routes':{'front_of_entrance':[ref(7,1,0),ref(7,1,8),ref(7,-1,8)]}}
description={'channels':[
    {'name':name,'unit':unit,'method':method,'sampling_rate_hz':20,
     'time_window':'all original frames','reference_frame':'Native world ground plane',
     'uncertainty':'Map and actor geometry require independent physical review'}
    for name,unit,method in (
        ('subject_center_xy','m','saved original subject center'),
        ('subject_heading_rad','rad','saved original subject heading'),
        ('subject_body_vertices_xy','m','saved original CARLA body vertices'),
        ('subject_lane_id','structured','saved original OpenDRIVE road and lane identity'))],
    'context_inputs':[],
    'limitations':['Station asset and turning purpose unresolved; diagnostic site is synthetic.']}
config={'law_id':'LVMC-11-12-060','cell_id':'C104538','actor':'motor_vehicle_driver',
        'selected_case_id':case_id,'supported_case_ids':[assignment+'__'+branch for branch in (
          'front_of_entrance','front_of_approach','through_driveway','remote_reference')],
        'case_branch':'front_of_entrance','station_survey':survey,
        'target_speed_mps':3.0,'required_atoms':[],'source_packets':[],
        'rate_hz':20,'duration_s':12,'frames':240,
        'cameras':[{'name':name,'width':spec[2][0],'height':spec[2][1],
           'pose_strategy':'subject-mounted original RGB source','fov_deg':spec[3]}
           for name,spec in CAMERAS.items()],
        'case':{'case_id':case_id,'recording_description':description}}
(root/'config.json').write_text(json.dumps(config,indent=2)+'\n')
paths=['runner.py','fire_station_geometry.py','fire_station_camera_capture.py',
       'fire_station_capture_session.py','fire_station_finalizer.py','config.json',
       'tests/test_fire_station_geometry.py','tests/test_station_runner_finalizer.py']
files=[{'path':path,'source':str((root/path).relative_to(repo)),
        'content':(root/path).read_text()} for path in paths]
construction={'format':'worker-inline-construction','case_id':case_id,
  'law_id':'LVMC-11-12-060','cell_id':'C104538','actor':'motor_vehicle_driver',
  'entrypoint':'runner.py','files':files,
  'measurement_plan':{'finalizer':'fire_station_finalizer.py','retained_sources':[
     'station_context.json','participant_state.jsonl','video_frames.jsonl','trace.jsonl'],
     'reported_boundary':'measured original reversal, mapped lane and body overlap; no station-identity or purpose judgment'},
  'recording_description':description,
  'static_checks':['runner --check','source-shaped geometry and finalizer CPU tests'],
  'termination_rules':['240 original 20 Hz frames','reject missing original body or station source'],
  'mechanisms':['source-bound mapped entrance branch','waypoint reversal controller',
     'four original RGB cameras','saved-only body and heading analysis']}
(root/'construction.json').write_text(json.dumps(construction,indent=2)+'\n')
manifest={'format':'worker-execution-manifest','assignment_id':assignment,
  'runtime_manifest_sha256':hashlib.sha256((repo/'runtime/SOURCE-MANIFEST.json').read_bytes()).hexdigest(),
  'cases':[{'case_id':case_id,'kind':'delivery','construction':'construction.json',
     'construction_sha256':hashlib.sha256((root/'construction.json').read_bytes()).hexdigest(),
     'measurement_procedure':{'entrypoint':'fire_station_finalizer.py'},
     'candidate_risk':{'status':'physical','reason':'Surveyed station and body route may not realize in Native map'},
     'candidates':[],'native_handoff':{'python_env_var':'CARLA_PYTHON',
      'host_env_var':'CARLA_HOST','port_env_var':'CARLA_PORT'}}]}
(root/'execution-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(manifest['cases'][0]['construction_sha256'])
