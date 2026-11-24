"""Survey-gated same-direction emergency vehicle capture; --check is CPU-only."""
import argparse
import json
import math
from pathlib import Path
import queue
import subprocess

AID='training__C404492__NRS-484B-267-2d__motor_vehicle_driver'
CAMERAS=('overview','approach','side','rear')
COUNT=600
RATE=20


def config():
    cfg=json.loads((Path(__file__).resolve().parent/'config.json').read_text())
    case=AID+'__'+cfg.get('case_suffix','')
    if (cfg.get('assignment_id')!=AID or cfg.get('case_id')!=case or cfg.get('selected_case_id')!=case
            or cfg.get('case_suffix') not in ('controlled_1','controlled_2') or cfg.get('candidate_id')!='primary'
            or cfg.get('law_id')!='NRS-484B-267-2d' or cfg.get('cell_id')!='C404492'
            or cfg.get('actor')!='motor_vehicle_driver' or cfg.get('frames')!=COUNT
            or cfg.get('rate_hz')!=RATE or cfg.get('duration_s')!=30
            or [c.get('name') for c in cfg.get('cameras',[])]!=list(CAMERAS)
            or cfg.get('physical_acceptance_claimed') is not False):
        raise ValueError('Exact emergency construction contract differs')
    return cfg


def survey_check(s):
    for key in ('map_name','map_source','lane_boundaries_source','emergency_authorization_source',
                'qualifying_flash_equipment_source','officer_direction_review_source',
                'ego_blueprint','emergency_blueprint','ego_spawn_xyz_m',
                'emergency_spawn_xyz_m','camera_world_transforms'):
        if not s.get(key):raise ValueError('Missing reviewed Native survey source: '+key)
    if s.get('emergency_vehicle_authorized') is not True or s.get('qualifying_flash_equipment_reviewed') is not True:
        raise ValueError('Emergency authorization or light equipment not reviewed')
    if type(s.get('officer_directed_otherwise')) is not bool:
        raise ValueError('Officer direction exception missing')
    if len(s['ego_spawn_xyz_m'])!=3 or len(s['emergency_spawn_xyz_m'])!=3:
        raise ValueError('Original vehicle transforms missing')
    gap=s['ego_spawn_xyz_m'][0]-s['emergency_spawn_xyz_m'][0]
    suffix=config()['case_suffix']
    if gap>-10:
        raise ValueError('Selected engineering spawn gap differs')
    if abs(s['ego_spawn_xyz_m'][1]-s['emergency_spawn_xyz_m'][1])<2.5:
        raise ValueError('Separate adjacent-lane trajectories required')
    if set(s['camera_world_transforms'])!=set(CAMERAS):
        raise ValueError('Four camera transforms required')
    return s


def transform(carla,xyz,rotation):
    return carla.Transform(carla.Location(x=xyz[0],y=xyz[1],z=xyz[2]),
                           carla.Rotation(pitch=rotation[0],yaw=rotation[1],roll=rotation[2]))


def execute(output,survey,host,port):
    import carla
    from worker_exchange.native_output import FrameMap
    from worker_exchange.world_restore import snapshot,restore
    cfg=config();survey_check(survey)
    output=Path(output).resolve()
    if any((output/name).exists() for name in ('video_frames.jsonl','vehicle_poses.jsonl')):
        raise ValueError('Original Native frame sources already exist')
    client=carla.Client(host,port);client.set_timeout(120)
    saved=snapshot(client);world=client.get_world()
    if world.get_map().name!=survey['map_name'] or saved['settings'].synchronous_mode:
        raise RuntimeError('Reviewed map and exclusive asynchronous world required')
    actors=[];encoders={};queues={}
    try:
        settings=world.get_settings();settings.synchronous_mode=True;settings.fixed_delta_seconds=1/RATE
        world.apply_settings(settings)
        lib=world.get_blueprint_library()
        ego=world.try_spawn_actor(lib.find(survey['ego_blueprint']),transform(carla,survey['ego_spawn_xyz_m'],[0,0,0]))
        emergency=world.try_spawn_actor(lib.find(survey['emergency_blueprint']),transform(carla,survey['emergency_spawn_xyz_m'],[0,0,0]))
        if ego is None or emergency is None:raise RuntimeError('Reviewed vehicle blueprint spawn failed')
        actors.extend((ego,emergency));output.mkdir(parents=True,exist_ok=True)
        special=carla.VehicleLightState.Special1
        for c in cfg['cameras']:
            bp=lib.find('sensor.camera.rgb');bp.set_attribute('image_size_x',str(c['width']))
            bp.set_attribute('image_size_y',str(c['height']));bp.set_attribute('sensor_tick',str(1/RATE))
            pose=survey['camera_world_transforms'][c['name']]
            camera=world.spawn_actor(bp,transform(carla,pose['xyz_m'],pose['rotation_deg']))
            actors.append(camera);q=queue.Queue();camera.listen(q.put);queues[c['name']]=q
            encoders[c['name']]=subprocess.Popen(['ffmpeg','-nostdin','-v','error','-y',
                '-f','rawvideo','-pix_fmt','bgra','-s',f"{c['width']}x{c['height']}",
                '-r',str(RATE),'-i','-','-frames:v',str(COUNT),'-c:v','ffv1',
                str(output/(c['name']+'.mkv'))],stdin=subprocess.PIPE,stderr=subprocess.PIPE)
        first=None
        with FrameMap(output/'video_frames.jsonl') as fmap,(output/'vehicle_poses.jsonl').open('x') as out:
            for i in range(COUNT):
                phase=(i//10)%2==0
                emergency.set_light_state(carla.VehicleLightState(special if phase else 0))
                emergency.set_target_velocity(carla.Vector3D(x=4,y=0,z=0))
                ego_requested=5 if cfg['case_suffix']=='controlled_2' and i<380 else 4
                ego.set_target_velocity(carla.Vector3D(x=ego_requested,y=0,z=0))
                native=world.tick();snap=world.get_snapshot()
                if snap.frame!=native:raise RuntimeError('Original Native frame mismatch')
                if first is None:first=snap.timestamp.elapsed_seconds
                t=snap.timestamp.elapsed_seconds-first
                mapped={}
                for name,q in queues.items():
                    image=q.get(timeout=30)
                    if image.frame!=native:raise RuntimeError('Original camera frame mismatch')
                    encoders[name].stdin.write(image.raw_data);mapped[name]=image.frame
                fmap.append(native,t,camera_native_frames=mapped)
                records=[]
                for actor in (ego,emergency):
                    pose=actor.get_transform();vel=actor.get_velocity();bbox=actor.bounding_box.extent
                    records.append({'actor_id':actor.id,'x_m':pose.location.x,'y_m':pose.location.y,
                        'heading_rad':pose.rotation.yaw*math.pi/180,
                        'speed_mps':math.sqrt(vel.x*vel.x+vel.y*vel.y+vel.z*vel.z),
                        'half_length_m':bbox.x,'half_width_m':bbox.y})
                records[1]['flashing_light_phase_on']=bool(emergency.get_light_state() & special)
                out.write(json.dumps({'video_frame':i,'native_frame':native,
                    'source_kind':'original_native_pose','ego':records[0],
                    'emergency':records[1]})+'\n')
        for name,process in encoders.items():
            process.stdin.close();stderr=process.stderr.read()
            if process.wait(timeout=180):raise RuntimeError('Camera encode failed: '+name+' '+stderr.decode()[-300:])
        (output/'emergency_context.template.json').write_text(json.dumps({'assignment_id':AID,
            'review_kind':'original_source_review','ego_actor_id':ego.id,
            'emergency_actor_id':emergency.id,'qualification_review_required':True,
            'camera_sha256':{}},indent=2)+'\n')
        return {'case_id':cfg['case_id'],'original_frames':COUNT,'physical_acceptance_claimed':False}
    finally:
        for process in encoders.values():
            if process.poll() is None:process.kill();process.wait()
        for actor in reversed(actors):
            try:
                if hasattr(actor,'stop'):actor.stop()
                actor.destroy()
            except Exception:pass
        restore(client,saved)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true')
    parser.add_argument('--survey',type=Path);parser.add_argument('--output-dir',type=Path)
    parser.add_argument('--host',default='127.0.0.1');parser.add_argument('--port',type=int,default=2000)
    args=parser.parse_args();cfg=config()
    if args.check:print(json.dumps({'passed':True,'case_id':cfg['case_id'],'frames':COUNT,
        'cameras':list(CAMERAS),'native_imported':False,'physical_acceptance_claimed':False}))
    else:
        if args.survey is None or args.output_dir is None:parser.error('--survey and --output-dir required')
        print(json.dumps(execute(args.output_dir,json.loads(args.survey.read_text()),args.host,args.port)))
