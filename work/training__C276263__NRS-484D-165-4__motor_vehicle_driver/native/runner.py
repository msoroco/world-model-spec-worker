"""Sloped-curb parked-headlamp Native acquisition; no legal classification."""
import argparse
import json
import math
import queue
import subprocess
from pathlib import Path
from parked_lamps import check_config,read_and_measure

def capture(cfg,output_dir,host='127.0.0.1',port=2000):
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap,seal_capture
    from worker_exchange.world_restore import snapshot,restore
    root=Path(__file__).resolve().parent
    check_config(cfg,(root/'sloped-curb-road.xodr').read_text())
    output=Path(output_dir).resolve()
    if not output.is_dir() or (output/'native-rows.jsonl').exists():
        raise ValueError('New empty attempt directory required')
    client=carla.Client(host,port);client.set_timeout(180)
    prior=snapshot(client);old=client.get_world()
    if prior['settings'].synchronous_mode or any(a.type_id.startswith(
            ('vehicle.','walker.','sensor.','controller.')) for a in old.get_actors()):
        raise RuntimeError('Exclusive idle Native world required')
    owned=[];encoders={};cameras={};pipeline=None;changed=False;complete=False
    try:
        world=client.generate_opendrive_world((root/'sloped-curb-road.xodr').read_text(),
            carla.OpendriveGenerationParameters(vertex_distance=.5,max_road_length=10,
                wall_height=0,additional_width=0,smooth_junctions=False,
                enable_mesh_visibility=True,enable_pedestrian_navigation=True))
        changed=True
        (output/'road.xodr').write_text(world.get_map().to_opendrive())
        settings=world.get_settings();settings.synchronous_mode=True
        settings.fixed_delta_seconds=.05;settings.substepping=True
        settings.max_substep_delta_time=.01;settings.max_substeps=10
        world.apply_settings(settings)
        waypoint=world.get_map().get_waypoint(carla.Location(x=4.85,y=0,z=2.4),
            project_to_road=True,lane_type=carla.LaneType.Parking)
        if waypoint is None or waypoint.lane_id!=-2:
            raise RuntimeError('Requested curb parking lane unavailable')
        library=world.get_blueprint_library()
        vehicles=sorted(library.filter('vehicle.*'),key=lambda b:b.id)
        if not vehicles:raise RuntimeError('Vehicle blueprint unavailable')
        bp=vehicles[0];bp.set_attribute('role_name','c276263_parked_lamp_subject')
        ego=world.spawn_actor(bp,carla.Transform(carla.Location(x=4.85,y=0,z=2.8),
            carla.Rotation(yaw=90)));owned.append(ego)
        low=int(carla.VehicleLightState.LowBeam);high=int(carla.VehicleLightState.HighBeam)
        selected=low if cfg['requested_beam_state']=='low_beam' else high
        ego.set_light_state(carla.VehicleLightState(selected))
        pipeline=PipelineCapture(client,ego,output,cfg['case_id'],visibility=False,
            required_observations=cfg.get('required_atoms',[]))
        (output/'review-pending.json').write_text(json.dumps({
            'beam_pixel_review':'pending','parking_activity_review':'pending',
            'vehicle_class_review':'pending','physical_completion':False,
            'legal_verdict':None},indent=2)+'\n')
        for spec in cfg['cameras']:
            name=spec['name'];camera_bp=library.find('sensor.camera.rgb')
            for key,value in [('image_size_x',spec['width']),
                    ('image_size_y',spec['height']),('sensor_tick','.05'),
                    ('fov',spec['fov_deg'])]:camera_bp.set_attribute(key,str(value))
            xyz=spec['location_xyz_m'];pyr=spec['rotation_pyr_deg']
            camera=world.spawn_actor(camera_bp,carla.Transform(
                carla.Location(x=xyz[0],y=xyz[1],z=xyz[2]),
                carla.Rotation(pitch=pyr[0],roll=pyr[1],yaw=pyr[2])),
                attach_to=ego if name=='driver_reference' else None)
            owned.append(camera);q=queue.Queue();camera.listen(q.put);cameras[name]=q
            encoders[name]=subprocess.Popen(['ffmpeg','-nostdin','-hide_banner',
                '-loglevel','error','-y','-f','rawvideo','-pix_fmt','bgra','-s',
                f"{spec['width']}x{spec['height']}",'-r','20','-i','-',
                '-frames:v','600','-c:v','ffv1','-level','1',str(output/(name+'.mkv'))],
                stdin=subprocess.PIPE,stderr=subprocess.PIPE)
        with FrameMap(output/'video_frames.jsonl') as frame_map, \
                (output/'native-rows.jsonl').open('x') as rows:
            for i in range(600):
                ego.apply_control(carla.VehicleControl(throttle=0,brake=1,hand_brake=True))
                frame=world.tick();snap=world.get_snapshot()
                if snap.frame!=frame:raise RuntimeError('Native frame/snapshot mismatch')
                t=(i+1)/20;pipeline.capture(frame,t);camera_frames={}
                for name,q in cameras.items():
                    image=q.get(timeout=30)
                    while image.frame<frame:image=q.get(timeout=30)
                    if image.frame!=frame:raise RuntimeError('Camera/frame mismatch: '+name)
                    encoders[name].stdin.write(image.raw_data);camera_frames[name]=image.frame
                frame_map.append(frame,t,camera_native_frames=camera_frames)
                pose=ego.get_transform();velocity=ego.get_velocity();center=pose.location
                corners=ego.bounding_box.get_world_vertices(pose)
                bits=int(ego.get_light_state())
                observed='high_beam' if bits & high else 'low_beam' if bits & low else 'off'
                lane=world.get_map().get_waypoint(center,project_to_road=True,
                    lane_type=carla.LaneType.Parking)
                row={'frame':i,'native_frame':frame,'time_s':t,
                    'source_kind':'original_native','ego_actor_id':ego.id,
                    'ego_blueprint_id':ego.type_id,
                    'ego_center_xyz_m':[center.x,center.y,center.z],
                    'ego_speed_mps':math.sqrt(velocity.x**2+velocity.y**2+velocity.z**2),
                    'observed_footprint_xyz_m':[[p.x,p.y,p.z] for p in corners],
                    'observed_curb_lane_id':lane.lane_id if lane else None,
                    'requested_headlamp_lit':True,
                    'requested_beam_state':cfg['requested_beam_state'],
                    'observed_light_state_bits':bits,'observed_beam_state':observed,
                    'observed_parking_activity':'unknown',
                    'beam_pixel_review':{'status':'pending'},
                    'source_cameras':camera_frames}
                rows.write(json.dumps(row)+'\n')
        for name,proc in encoders.items():
            proc.stdin.close();error=proc.stderr.read()
            if proc.wait(timeout=180) or not (output/(name+'.mkv')).is_file():
                raise RuntimeError('Camera encode failed: '+name+': '+error.decode()[-300:])
        complete=True
        return {'frames':600,'cameras':list(cameras),
            'beam_pixel_review':'pending','parking_activity_review':'pending',
            'physical_completion_claimed':False}
    finally:
        if pipeline is not None:pipeline.close(confirmed=complete)
        for proc in encoders.values():
            if proc.poll() is None:proc.kill();proc.wait()
        for actor in reversed(owned):
            try:
                if hasattr(actor,'stop'):actor.stop()
                actor.destroy()
            except Exception:pass
        restored=restore(client,prior) if changed else {'restored':True}
        if complete:
            seal_capture(output,frames=600,restoration=restored,errors=[],
                encoder_exit_codes={name:p.returncode for name,p in encoders.items()},
                context={'case_id':cfg['case_id'],
                    'candidate_id':cfg.get('candidate_id','primary'),
                    'original_beam_and_parking_review':'pending'})

def main():
    p=argparse.ArgumentParser();p.add_argument('--check',action='store_true')
    p.add_argument('--measure-request');p.add_argument('--capture')
    p.add_argument('--output-dir')
    p.add_argument('--host',default='127.0.0.1')
    p.add_argument('--port',type=int,default=2000);a=p.parse_args()
    root=Path(__file__).resolve().parent
    cfg=json.loads((root/'config.json').read_text())
    out=check_config(cfg,(root/'sloped-curb-road.xodr').read_text())
    if a.measure_request:
        out['request_meter']=read_and_measure(a.measure_request,'authored_native_request')
    if a.capture or a.output_dir:
        out=capture(cfg,a.capture or a.output_dir,a.host,a.port)
    elif not a.check and not a.measure_request:
        raise ValueError('Specify --check or --capture')
    print(json.dumps(out,sort_keys=True))

if __name__=='__main__':main()
