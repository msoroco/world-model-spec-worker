"""Exact marked-crosswalk stop case; Native capture requires a reviewed site.

The bundled site is a synthetic CPU schema fixture. Runtime refuses a map/sign
or crosswalk that does not match it. Physical and legal acceptance remain open.
"""
import argparse
import hashlib
import json
import queue
import subprocess
from pathlib import Path

CASE='testing__C331230__NRS-484A-450-2__motor_vehicle_driver__marked_crosswalk_stop_before'
CAMERAS={'overview':(1920,1080),'approach':(1280,720),
         'reference_corner':(1280,720),'driver_reference':(1280,720)}

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def rows(path,values):path.write_text(''.join(json.dumps(x,allow_nan=False)+'\n' for x in values))
def load_config(root):
 root=Path(root);cfg=json.loads((root/'config.json').read_text())
 if (cfg.get('assignment_id')!=CASE.rsplit('__',1)[0] or cfg.get('selected_case_id')!=CASE or
     cfg.get('law_id')!='NRS-484A-450-2' or cfg.get('cell_id')!='C331230' or
     cfg.get('actor')!='motor_vehicle_driver' or cfg.get('frames')!=900 or
     cfg.get('rate_hz')!=20 or cfg.get('duration_s')!=45):
  raise ValueError('Exact C331230 case/rate identity differs')
 ref=cfg.get('site_packet',{});site_path=root/ref.get('path','')
 if not site_path.is_file() or sha(site_path)!=ref.get('sha256'):
  raise ValueError('Sourced site packet changed')
 site=json.loads(site_path.read_text())
 if (site.get('review_basis')!='synthetic CPU schema fixture; physical site unreviewed' or
     site.get('near_side_crosswalk_exists') is not True or
     site.get('crosswalk_origin')!='marked' or
     site.get('stop_line_exists') is not False or
     set(site.get('camera_poses',{}))!=set(CAMERAS) or
     site.get('physical_acceptance_claimed') is not False):
  raise ValueError('Marked near-side crosswalk site contract differs')
 cross=site['crosswalk_polygon_xy_m'];junction=site['intersection_polygon_xy_m']
 if (len(cross)<4 or len(junction)<4 or
     max(x for x,y in cross)>=min(x for x,y in junction) or
     site['ego_spawn_pose'][0]>=min(x for x,y in cross)):
  raise ValueError('Crosswalk must precede junction and spawn')
 if cfg.get('physical_completion',{}).get('body_key')!='ego_body_vertices_xy_m':
  raise ValueError('Original complete-body motion criterion missing')
 return cfg,site

def _transform(carla,pose):
 x,y,z,yaw=pose
 return carla.Transform(carla.Location(x=x,y=y,z=z),carla.Rotation(yaw=yaw))

def _body(actor):
 return [[float(v.x),float(v.y)] for v in actor.bounding_box.get_world_vertices(actor.get_transform())]

def _source_context(site,sign):
 return {'native_map_id':site['native_map_name'],'intersection_id':site['intersection_id'],
  'approach_road_id':site['approach_road_id'],'approach_lane_id':site['approach_lane_id'],
  'native_stop_sign_id':sign.id,'sign_governance_source':'Native trigger plus unreviewed site packet',
  'crosswalk_source':'Native crosswalk waypoint plus unreviewed site polygon',
  'crosswalk_nearside_source':'unreviewed synthetic site geometry',
  'junction_source':'unreviewed synthetic site geometry',
  'near_side_crosswalk_exists':True,'crosswalk_origin':'marked',
  'crosswalk_polygon_xy_m':site['crosswalk_polygon_xy_m'],
  'intersection_polygon_xy_m':site['intersection_polygon_xy_m'],
  'approach_forward_xy':[1,0],'stop_line_exists':False,
  'physical_acceptance_claimed':False,'legal_conclusion':'unresolved'}

def _camera_process(path,width,height):
 cmd=['ffmpeg','-hide_banner','-loglevel','error','-f','rawvideo','-pixel_format','bgra',
      '-video_size',f'{width}x{height}','-framerate','20','-i','pipe:0',
      '-c:v','libx264','-preset','ultrafast','-pix_fmt','yuv420p','-y',str(path)]
 return subprocess.Popen(cmd,stdin=subprocess.PIPE)

def capture(root,host,port):
 import carla
 from stop_sign_control import find_governing_stop_sign
 from worker_exchange.native_output import physical_result,write_result,seal_capture
 root=Path(root);cfg,site=load_config(root)
 client=carla.Client(host,port);client.set_timeout(20)
 world=client.get_world();world_map=world.get_map()
 if site['native_map_name'] not in world_map.name:
  raise ValueError('Native map differs from unreviewed site fixture; select a reviewed site')
 point=carla.Location(x=site['sign_trigger_point_xy_m'][0],y=site['sign_trigger_point_xy_m'][1],z=0)
 waypoint=world_map.get_waypoint(point,project_to_road=False)
 if waypoint is None or (waypoint.road_id,waypoint.lane_id)!=(site['approach_road_id'],site['approach_lane_id']):
  raise ValueError('Native approach lane differs from site')
 sign=find_governing_stop_sign(world,waypoint)
 crosswalks=world_map.get_crosswalks()
 x0=min(p[0] for p in site['crosswalk_polygon_xy_m']);x1=max(p[0] for p in site['crosswalk_polygon_xy_m'])
 y0=min(p[1] for p in site['crosswalk_polygon_xy_m']);y1=max(p[1] for p in site['crosswalk_polygon_xy_m'])
 if not any(x0<=p.x<=x1 and y0<=p.y<=y1 for p in crosswalks):
  raise ValueError('Native near-side crosswalk differs from authored polygon')
 settings=world.get_settings();old_delta=settings.fixed_delta_seconds;old_sync=settings.synchronous_mode
 sensors=[];ego=None;encoders={};hist=[];frames=[];trace=[];evidence=[];queues={}
 try:
  settings.synchronous_mode=True;settings.fixed_delta_seconds=.05;world.apply_settings(settings)
  blueprint=world.get_blueprint_library().find('vehicle.tesla.model3')
  ego=world.try_spawn_actor(blueprint,_transform(carla,site['ego_spawn_pose']))
  if ego is None:raise ValueError('Native ego spawn failed')
  for name,(width,height) in CAMERAS.items():
   bp=world.get_blueprint_library().find('sensor.camera.rgb')
   for key,value in [('image_size_x',width),('image_size_y',height),('sensor_tick',.05)]:bp.set_attribute(key,str(value))
   sensor=world.spawn_actor(bp,_transform(carla,site['camera_poses'][name]),attach_to=ego if name=='driver_reference' else None)
   q=queue.Queue();sensor.listen(q.put);queues[name]=q;sensors.append(sensor)
   encoders[name]=_camera_process(root/(name+'.mkv'),width,height)
  (root/'approach_context.json').write_text(json.dumps(_source_context(site,sign),indent=2)+'\n')
  for i in range(cfg['frames']):
   # The first 20 frames command a full halt before the near-side crosswalk.
   # Later motion is measured, never assumed to match the authored intent.
   ego.apply_control(carla.VehicleControl(throttle=0.0 if i<20 else .25,brake=1.0 if i<20 else 0.0))
   fid=world.tick();snap=world.get_snapshot();time=float(snap.timestamp.elapsed_seconds)
   camera_frames={}
   for name in CAMERAS:
    image=queues[name].get(timeout=15)
    if image.frame!=fid:raise ValueError('Original camera/Native tick join differs')
    encoders[name].stdin.write(image.raw_data);camera_frames[name]=image.frame
   pose=ego.get_transform();vel=ego.get_velocity();speed=(vel.x*vel.x+vel.y*vel.y+vel.z*vel.z)**.5
   body=_body(ego);ego_waypoint=world_map.get_waypoint(pose.location,project_to_road=False)
   if ego_waypoint is None:raise ValueError('Original ego road position missing')
   row={'frame':fid,'time_s':time,'road_id':ego_waypoint.road_id,'lane_id':ego_waypoint.lane_id,
        'stop_sign_id':sign.id,'ego_speed_mps':speed,'ego_body_vertices_xy_m':body}
   hist.append(row);frames.append({'video_frame':i,'carla_frame':fid,'time_s':time})
   trace.append({'frame':fid,'time_s':time,'position':{'x':pose.location.x,'y':pose.location.y,'z':pose.location.z},
      'position_m':[pose.location.x,pose.location.y,pose.location.z],
      'heading_deg':pose.rotation.yaw,'speed_mps':speed})
   evidence.append({'original_frame':fid,'recording_time_s':time,'actor_id':ego.id,
       'ego':{'body_vertices_xy_m':body,'speed_mps':speed},'camera_frames':camera_frames,
       'supporting_only':True})
  rows(root/'stop_history.jsonl',hist);rows(root/'video_frames.jsonl',frames)
  rows(root/'trace.jsonl',trace)
  (root/'capture').mkdir(exist_ok=True);rows(root/'capture/evidence.jsonl',evidence)
 finally:
  for sensor in reversed(sensors):
   try:sensor.stop()
   finally:sensor.destroy()
  for process in encoders.values():
   if process.stdin:process.stdin.close()
  encoder_codes={name:process.wait(timeout=30) for name,process in encoders.items()}
  if ego is not None:ego.destroy()
  settings.synchronous_mode=old_sync;settings.fixed_delta_seconds=old_delta;world.apply_settings(settings)
 if len(hist)!=cfg['frames'] or any(code!=0 for code in encoder_codes.values()):
  raise ValueError('Native capture or encoder incomplete')
 seal_capture(root,frames=len(frames),restoration={'restored':True},errors=[],
      encoder_exit_codes=encoder_codes,context={'diagnostic_fixture':True})
 from crosswalk_stop_measurements import analyze
 try:
  observation=analyze(root)
  ordered=observation['full_halt_before_crosswalk_and_junction_observed']
  analysis_error=None
 except ValueError as error:
  ordered=False;analysis_error=str(error)
 channels=root/'channels';channels.mkdir()
 (channels/'stop_context.json').write_text(json.dumps({
    'case_id':CASE,'approach_context':_source_context(site,sign),
    'observed_halt_ordering':ordered,'analysis_error':analysis_error,
    'legal_conclusion':'unresolved'},allow_nan=False)+'\n')
 rows(channels/'halt_timing.jsonl',[{'time_s':row['time_s'],
    'value':{'frame':row['frame'],'speed_mps':row['ego_speed_mps'],
       'body_vertices_xy_m':row['ego_body_vertices_xy_m']}} for row in hist])
 result=physical_result(root,{'case_id':CASE,
    'measured_values':{'halt_before_crosswalk_observed':ordered},
    'target_checks':[{'target':'complete_halt_before_nearside_crosswalk',
       'requested':True,'measured':ordered,
       'method':'original complete-body speed and crosswalk geometry',
       'tolerance':0,'matched':ordered,'physical_cause_confirmed':False,
       'cause_evidence':['approach_context.json','stop_history.jsonl','video_frames.jsonl']}],
    'setup_confirmed':False,'behavior_attempted':False,'maneuver_completed':False,
    'physical_failure_flags':[] if ordered else ['crosswalk halt ordering unconfirmed'],
    'recording_description':cfg['recording_description'],
    'trace_reference':'trace.jsonl','video_frame_map_reference':'video_frames.jsonl',
    'video_references':[name+'.mkv' for name in CAMERAS],
    'recording_evidence':[{'name':'stop_context','unit':'structured record',
       'reference':'channels/stop_context.json'},
       {'name':'halt_timing','unit':'structured record',
       'reference':'channels/halt_timing.jsonl'}],
    'realized_observables':{},
    'termination_reason':'planned synchronized capture complete',
    'physical_acceptance_claimed':False,'legal_acceptance_claimed':False})
 write_result(root,result)

def main():
 p=argparse.ArgumentParser();p.add_argument('--check',action='store_true')
 p.add_argument('--output-dir',type=Path);p.add_argument('--host',default='127.0.0.1');p.add_argument('--port',type=int,default=2000)
 a=p.parse_args();root=Path(__file__).resolve().parent
 if a.check:load_config(root);print('C331230 exact marked-crosswalk CPU check passed');return
 if a.output_dir is None:raise ValueError('Supply --output-dir for Native capture')
 capture(a.output_dir,a.host,a.port)
if __name__=='__main__':main()
