"""Prospective original truck-route capture; --check uses no CARLA import.

An operator must provide a reviewed map route and independent factual documents.
The runner records motion and seals cited bytes; it does not establish a legal or
administrative conclusion.
"""
import argparse
import hashlib
import json
import math
import queue
import shutil
import subprocess
from pathlib import Path

AID = 'training__C394566__LVMC-11-48-050__heavy_vehicle_driver'
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
RATE = 20
FRAMES = 600


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check(config):
    require((config.get('assignment_id'),config.get('law_id'),config.get('cell_id'),config.get('actor')) ==
            (AID,'LVMC-11-48-050','C394566','heavy_vehicle_driver'), 'Exact restriction identity differs')
    require(config.get('case_id','').startswith(AID+'__'), 'Unknown exact case identity')
    require(config.get('rate_hz') == RATE and config.get('duration_s') == 30 and
            config.get('frames') == FRAMES, 'Capture timing differs')
    cameras = config.get('cameras')
    require(isinstance(cameras,list) and [(c.get('name'),c.get('width'),c.get('height')) for c in cameras] ==
            [('overview',1920,1080),('approach',1280,720),('reference_corner',1280,720),('driver_reference',1280,720)],
            'Four synchronized cameras required')
    require(config.get('physical_acceptance_claimed') is False and config.get('legal_verdict') is None,
            'Prospective run claims acceptance')
    return {'case_id':config['case_id'],'frames':FRAMES,'simulation_started':False,
            'original_authority_review_required':True}


def survey_check(survey):
    keys=('map_name','map_source','vehicle_blueprint','vehicle_blueprint_source','spawn_xyz_m',
          'spawn_yaw_deg','route_waypoints_xyz_m','camera_mounts','road_authority_source')
    for key in keys: require(survey.get(key) is not None, 'Missing reviewed Native survey source: '+key)
    route=survey['route_waypoints_xyz_m']
    require(isinstance(route,list) and len(route)>=2 and all(len(point)==3 and
            all(type(v) in (int,float) and math.isfinite(v) for v in point) for point in route),
            'Invalid original route waypoints')
    require(set(survey['camera_mounts'])==set(CAMERAS), 'Missing surveyed camera mounts')
    return survey


def _transform(carla,xyz,rotation):
    return carla.Transform(carla.Location(x=xyz[0],y=xyz[1],z=xyz[2]),
                           carla.Rotation(pitch=rotation[0],yaw=rotation[1],roll=rotation[2]))


def _steer(ego,target):
    pose=ego.get_transform();dx=target[0]-pose.location.x;dy=target[1]-pose.location.y
    desired=math.atan2(dy,dx);yaw=math.radians(pose.rotation.y)
    error=(desired-yaw+math.pi)%(2*math.pi)-math.pi
    return max(-.6,min(.6,1.2*error))


def _copy_context(source,output,case_id):
    source=Path(source).resolve();context=json.loads(source.read_text())
    require(context.get('case_id')==case_id and context.get('source_kind')=='original_review_packet',
            'Original independent context required')
    terms=('ru.truck','ru.commercial_motor_vehicle','kin.extent','st.roadway','dev.regulatory_sign','env.civil_time','drv.condition_in_effect','kin.velocity')
    require(all(isinstance(context.get(term),dict) and context[term] for term in terms),
            'Missing authored original instance context')
    refs=context.get('authority_refs')
    require(isinstance(refs,dict) and set(refs)=={'weight','district','truck_route','civil_clock','permit'},
            'Five independent authority source references required')
    for key,ref in refs.items():
        name=ref.get('path');require(isinstance(name,str) and Path(name).name==name,
                                'Authority source must be a flat, exact file: '+key)
        original=source.parent/name
        require(original.is_file() and sha(original)==ref.get('sha256'),
                'Changed authority source: '+key)
        shutil.copyfile(original,output/name)
    (output/'authority-context.json').write_text(json.dumps(context,indent=2)+'\n')


def capture(config,output,survey,context_source,host,port):
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap,seal_capture
    from worker_exchange.world_restore import snapshot,restore
    check(config);survey_check(survey)
    output=Path(output).resolve();require(output.is_dir() and not (output/'original-route-rows.jsonl').exists(),
                                       'Fresh materialized exact attempt required')
    require(json.loads((output/'config.json').read_text())==config,'Materialized config differs')
    _copy_context(context_source,output,config['case_id'])
    client=carla.Client(host,int(port));client.set_timeout(180)
    saved=snapshot(client);world=client.get_world()
    require(world.get_map().name==survey['map_name'],'Live Native map differs from reviewed survey')
    settings=world.get_settings();settings.synchronous_mode=True;settings.fixed_delta_seconds=1/RATE
    settings.substepping=True;settings.max_substep_delta_time=.01;settings.max_substeps=10
    owned=[];encoders={};streams={};capture_tool=None;changed=finished=False;codes={}
    try:
        world.apply_settings(settings);changed=True
        library=world.get_blueprint_library();blueprint=library.find(survey['vehicle_blueprint'])
        blueprint.set_attribute('role_name','restriction_subject')
        ego=world.spawn_actor(blueprint,_transform(carla,survey['spawn_xyz_m'],[0,survey['spawn_yaw_deg'],0]))
        require(ego is not None,'Original heavy vehicle spawn failed');owned.append(ego)
        capture_tool=PipelineCapture(client,ego,output,config['case_id'],
                                     required_observations=['kin.velocity','kin.extent'])
        for spec in config['cameras']:
            name=spec['name'];bp=library.find('sensor.camera.rgb')
            bp.set_attribute('image_size_x',str(spec['width']));bp.set_attribute('image_size_y',str(spec['height']))
            bp.set_attribute('fov',str(spec.get('fov_deg',80)));bp.set_attribute('sensor_tick','.05')
            mount=survey['camera_mounts'][name]
            sensor=world.spawn_actor(bp,_transform(carla,mount['xyz_m'],mount['rotation_deg']),attach_to=ego)
            owned.append(sensor);stream=queue.Queue();sensor.listen(stream.put);streams[name]=stream
            encoders[name]=subprocess.Popen(['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-y',
                '-f','rawvideo','-pix_fmt','bgra','-s',f"{spec['width']}x{spec['height']}",'-r',str(RATE),
                '-i','-','-frames:v',str(FRAMES),'-c:v','ffv1',str(output/(name+'.mkv'))],
                stdin=subprocess.PIPE,stderr=subprocess.PIPE)
        route=survey['route_waypoints_xyz_m'];target=1;first_elapsed=None
        with FrameMap(output/'video_frames.jsonl') as frame_map, (output/'original-route-rows.jsonl').open('x') as rows:
            for index in range(FRAMES):
                pose=ego.get_transform()
                if target<len(route)-1 and math.dist([pose.location.x,pose.location.y],route[target][:2])<3:
                    target+=1
                velocity=ego.get_velocity();speed=math.sqrt(velocity.x**2+velocity.y**2+velocity.z**2)
                if config.get('requested_motion')=='stationary':
                    ego.apply_control(carla.VehicleControl(throttle=0,brake=1,hand_brake=True))
                else:
                    target_speed=config.get('target_speed_mps',5.0)
                    ego.apply_control(carla.VehicleControl(throttle=max(0,min(.7,.35+.15*(target_speed-speed))),
                        brake=max(0,min(.5,.2*(speed-target_speed))),steer=_steer(ego,route[target])))
                native_frame=world.tick();snap=world.get_snapshot()
                require(snap.frame==native_frame,'Native frame differs from snapshot')
                if first_elapsed is None:first_elapsed=snap.timestamp.elapsed_seconds
                time_s=snap.timestamp.elapsed_seconds-first_elapsed
                capture_tool.capture(native_frame,time_s)
                camera_frames={}
                for name,stream in streams.items():
                    image=stream.get(timeout=30)
                    while image.frame<native_frame:image=stream.get(timeout=30)
                    require(image.frame==native_frame,'Original camera frame join differs')
                    encoders[name].stdin.write(image.raw_data);camera_frames[name]=native_frame
                frame_map.append(native_frame,time_s,camera_native_frames=camera_frames)
                pose=ego.get_transform();velocity=ego.get_velocity()
                road=world.get_map().get_waypoint(pose.location,project_to_road=True,lane_type=carla.LaneType.Driving)
                require(road is not None,'Native vehicle left roadway')
                rows.write(json.dumps({'case_id':config['case_id'],'source_kind':'original_native_pose',
                    'video_frame':index,'native_frame':native_frame,'time_s':time_s,'road_id':road.road_id,
                    'ego_actor_id':ego.id,'ego_x_m':pose.location.x,'ego_y_m':pose.location.y,
                    'ego_speed_mps':math.sqrt(velocity.x**2+velocity.y**2+velocity.z**2),
                    'vehicle_half_extent_m':[ego.bounding_box.extent.x,ego.bounding_box.extent.y]},allow_nan=False)+'\n')
        for name,process in encoders.items():
            process.stdin.close();error=process.stderr.read();codes[name]=process.wait(timeout=180)
            require(codes[name]==0,'Camera encoding failed: '+name+' '+error.decode()[-200:])
        capture_tool.close(confirmed=True);capture_tool=None
        names=('authority-context.json','original-route-rows.jsonl','video_frames.jsonl')
        (output/'capture-seal.json').write_text(json.dumps({'case_id':config['case_id'],
            'sha256':{name:sha(output/name) for name in names},'legal_verdict':None},indent=2)+'\n')
        finished=True
    finally:
        if capture_tool is not None:capture_tool.close(confirmed=False)
        for process in encoders.values():
            if process.poll() is None:process.kill();process.wait()
        for actor in reversed(owned):
            try:
                if hasattr(actor,'stop'):actor.stop()
                actor.destroy()
            except Exception:pass
        restored=restore(client,saved) if changed else {'restored':True}
        if finished:
            require(restored.get('restored') is True,'Original world restoration unverified')
            seal_capture(output,frames=FRAMES,restoration=restored,errors=[],encoder_exit_codes=codes,
                         context={'administrative_authority_reviewed':False,'legal_outcome_claimed':False})
    return {'case_id':config['case_id'],'frames':FRAMES,'original_authority_review_required':True,
            'physical_or_legal_outcome_claimed':False}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true')
    parser.add_argument('--config',type=Path,default=Path(__file__).resolve().with_name('config.json'))
    parser.add_argument('--survey',type=Path);parser.add_argument('--context',type=Path)
    parser.add_argument('--output-dir',type=Path);parser.add_argument('--host',default='127.0.0.1')
    parser.add_argument('--port',type=int,default=2000);args=parser.parse_args()
    cfg=json.loads(args.config.read_text())
    if args.check:print(json.dumps(check(cfg),sort_keys=True))
    else:
        if args.survey is None or args.context is None or args.output_dir is None:
            parser.error('Supply reviewed --survey, --context and --output-dir')
        print(json.dumps(capture(cfg,args.output_dir,json.loads(args.survey.read_text()),args.context,args.host,args.port)))
