"""Unaccepted original CARLA U-turn attempt; no district or legal verdict."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import queue
import subprocess
import traceback

from build import FRAMES, RATE
from check import check


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def xyz(value):
    return [value.x,value.y,value.z]


def actor_row(actor):
    transform=actor.get_transform();velocity=actor.get_velocity()
    return {'actor_id':actor.id,'blueprint':actor.type_id,
            'center_native_xyz_m':xyz(transform.location),'yaw_deg':transform.rotation.yaw,
            'velocity_native_xyz_mps':xyz(velocity),
            'speed_mps':math.sqrt(velocity.x**2+velocity.y**2+velocity.z**2),
            'body_native_xyz_m':[xyz(p) for p in actor.bounding_box.get_world_vertices(transform)]}


def control(actor,target,carla):
    current=actor.get_transform();velocity=actor.get_velocity()
    speed=math.sqrt(velocity.x**2+velocity.y**2+velocity.z**2)
    desired=target['requested_speed_mps']
    heading=math.degrees(target['requested_heading_rad'])
    error=(heading-current.rotation.yaw+180)%360-180
    point=target['requested_ego_xyz_m']
    lateral=(point[1]-current.location.y)*math.cos(math.radians(current.rotation.yaw))-(point[0]-current.location.x)*math.sin(math.radians(current.rotation.yaw))
    steer=max(-1,min(1,.022*error+.06*lateral))
    if desired<.05:
        return carla.VehicleControl(throttle=0,brake=min(1,.4+speed/5),steer=steer)
    return carla.VehicleControl(throttle=max(.08,min(.7,.25+.11*(desired-speed))),brake=0,steer=steer)


def capture(bundle,output,host,port):
    import carla
    import numpy as np
    from scenario_pipeline.worker_exchange.world_restore import snapshot,restore

    bundle,output=Path(bundle).resolve(),Path(output).resolve()
    check(bundle)
    cfg=json.loads((bundle/'config.json').read_text())
    requests=[json.loads(line) for line in (bundle/'requested-tracks.jsonl').read_text().splitlines()]
    client=carla.Client(host,int(port));client.set_timeout(180)
    previous=client.get_world();saved_world=snapshot(client)
    if previous.get_settings().synchronous_mode or any(a.type_id.startswith(('vehicle.','walker.','sensor.')) for a in previous.get_actors()):
        raise RuntimeError('Exclusive idle asynchronous CARLA world required')
    output.mkdir(parents=True,exist_ok=False)
    owned=[];sensors={};encoders={};logs={};changed=False;frames=0;error=None;restoration=None
    try:
        world=client.generate_opendrive_world((bundle/'district-crossroads.xodr').read_text(),
            carla.OpendriveGenerationParameters(vertex_distance=.25,max_road_length=100,
                wall_height=0,additional_width=0,smooth_junctions=False,
                enable_mesh_visibility=True,enable_pedestrian_navigation=False))
        changed=True
        settings=world.get_settings();settings.synchronous_mode=True;settings.fixed_delta_seconds=1/RATE
        world.apply_settings(settings);world.set_weather(carla.WeatherParameters.ClearNoon)
        mapping=world.get_map();lanes={}
        for name,road_id,lane_id,station in (
            ('west_eastbound_outer',403,-3,20),('west_westbound_outer',403,3,20),
            ('junction_eastbound_outer',404,-3,20),('junction_westbound_outer',404,3,20),
            ('east_eastbound_outer',405,-3,20),('south_crossroad',406,-3,20),
            ('junction_crossroad',407,-3,20),('north_crossroad',408,-3,20)):
            wp=mapping.get_waypoint_xodr(road_id,lane_id,station)
            if wp is None or wp.road_id!=road_id or wp.lane_id!=lane_id or wp.lane_type!=carla.LaneType.Driving:
                raise RuntimeError('Generated driving lane missing: '+name)
            lanes[name]={'road_id':road_id,'lane_id':lane_id,
                         'native_xyz_m':xyz(wp.transform.location),'lane_type':str(wp.lane_type)}
        if lanes['junction_eastbound_outer']['road_id']!=404 or \
                mapping.get_waypoint_xodr(404,-3,20).get_junction().id!=1:
            raise RuntimeError('Generated intersection missing')
        ego=world.try_spawn_actor(world.get_blueprint_library().find(cfg['ego_blueprint']),
                                  carla.Transform(carla.Location(x=-80,y=-6,z=1.5),carla.Rotation(yaw=0)))
        if ego is None:raise RuntimeError('Physical ego vehicle did not spawn')
        owned.append(ego)
        height=55 if cfg['camera_policy']=='elevated_overview' else 38
        specs=(('ego_view',1280,720,(-65,-10,4),0,-8),
               ('turn_view',1280,720,(10,15,12),-135,-35),
               ('overview',1280,720,(-20,0,height),-45,-90))
        for name,width,pixels,position,yaw,pitch in specs:
            bp=world.get_blueprint_library().find('sensor.camera.rgb')
            for key,value in (('image_size_x',width),('image_size_y',pixels),('fov',80),('sensor_tick',0)):
                bp.set_attribute(key,str(value))
            sensor=world.spawn_actor(bp,carla.Transform(carla.Location(*position),
                                                         carla.Rotation(yaw=yaw,pitch=pitch)))
            owned.append(sensor);sensors[name]=queue.Queue();sensor.listen(sensors[name].put)
            logs[name]=(output/(name+'.encoder.log')).open('x')
            encoders[name]=subprocess.Popen(['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-n',
                '-f','rawvideo','-pix_fmt','rgb24','-s',f'{width}x{pixels}','-r',str(RATE),'-i','pipe:0',
                '-an','-c:v','ffv1',str(output/(name+'.mkv'))],stdin=subprocess.PIPE,stderr=logs[name])
        (output/'native-map-readback.json').write_text(json.dumps({
            'source_kind':'original_native','road_sha256':sha(bundle/'district-crossroads.xodr'),
            'native_map_sha256':hashlib.sha256(mapping.to_opendrive().encode()).hexdigest(),
            'lane_readback':lanes,'junction_id':1,'ego_actor_id':ego.id,
            'authored_business_district':True,'district_designation_verified':False,
            'legal_verdict':None},indent=2)+'\n')
        for _ in range(20):world.tick()
        start=world.get_snapshot().timestamp.elapsed_seconds
        with (output/'native-raw-actors.jsonl').open('x') as actor_file, \
             (output/'video_frames.jsonl').open('x') as video_file:
            for i,request in enumerate(requests):
                ego.apply_control(control(ego,requests[min(i+4,FRAMES-1)],carla))
                native_frame=world.tick();t=world.get_snapshot().timestamp.elapsed_seconds-start
                wp=mapping.get_waypoint(ego.get_location(),project_to_road=False,lane_type=carla.LaneType.Any)
                actor_file.write(json.dumps({'frame':i,'native_frame':native_frame,'time_s':t,
                    'source_kind':'original_native','request_frame':request['frame'],'ego':actor_row(ego),
                    'ego_road_id':None if wp is None else wp.road_id,
                    'requested_phase':request['requested_phase'],
                    'authored_business_district':True,'district_designation_verified':False,
                    'legal_verdict':None},allow_nan=False)+'\n')
                for name,width,pixels,*_ in specs:
                    image=sensors[name].get(timeout=30)
                    while image.frame<native_frame:image=sensors[name].get(timeout=30)
                    if image.frame!=native_frame:raise RuntimeError('Camera/native frame join failed')
                    rgb=np.frombuffer(image.raw_data,dtype=np.uint8).reshape(pixels,width,4)[:,:,:3][:,:,::-1]
                    encoders[name].stdin.write(rgb.tobytes())
                video_file.write(json.dumps({'video_frame':i,'native_frame':native_frame,'time_s':t})+'\n')
                frames+=1
    except BaseException as exc:
        error={'type':type(exc).__name__,'message':str(exc),'traceback':traceback.format_exc()}
    finally:
        for name,encoder in encoders.items():
            try:
                encoder.stdin.close()
                if encoder.wait(timeout=180)!=0:raise RuntimeError('FFV1 encoder failed')
            except BaseException as exc:error=error or {'encoder_error':str(exc)}
            logs[name].close()
        for actor in reversed(owned):
            try:
                if actor.type_id.startswith('sensor.') and actor.is_listening:actor.stop()
                actor.destroy()
            except BaseException as exc:error=error or {'cleanup_error':str(exc)}
        if changed:
            try:restoration=restore(client,saved_world)
            except BaseException as exc:error=error or {'restore_error':str(exc)}
        (output/'native-capture-report.json').write_text(json.dumps({
            'case_id':cfg['case_id'],'candidate_id':cfg['candidate_id'],
            'config_sha256':sha(bundle/'config.json'),'requested_frames':FRAMES,
            'observed_frames':frames,'restoration':restoration,'error':error,
            'accepted':False,'delivery_ready':False,'legal_verdict':None},indent=2)+'\n')
    if error:raise RuntimeError('C111662 original Native attempt failed; inspect capture report')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true')
    parser.add_argument('--bundle',type=Path,default=Path.cwd())
    parser.add_argument('--output-dir',type=Path);parser.add_argument('--host',default='localhost')
    parser.add_argument('--port',type=int,default=2000);args=parser.parse_args()
    if args.check:print(json.dumps(check(args.bundle)))
    else:
        if args.output_dir is None:parser.error('Original output directory required')
        capture(args.bundle,args.output_dir,args.host,args.port)
