"""Survey-gated same-direction emergency vehicle capture; --check is CPU-only."""
import argparse
import json
import math
from pathlib import Path
import queue
import subprocess

AID='training__C404492__NRS-484B-267-2d__motor_vehicle_driver'
CAMERAS=('overview','approach','reference_corner','driver_reference')
COUNT=600
RATE=20


def config():
    cfg=json.loads((Path(__file__).resolve().parent/'config.json').read_text())
    case=AID+'__'+cfg.get('case_suffix','')
    if (cfg.get('assignment_id')!=AID or cfg.get('case_id')!=case or cfg.get('selected_case_id')!=case
            or cfg.get('case_suffix') not in ('controlled_1','controlled_2')
            or cfg.get('candidate_id') not in ('primary','fallback1','fallback2')
            or cfg.get('law_id')!='NRS-484B-267-2d' or cfg.get('cell_id')!='C404492'
            or cfg.get('actor')!='motor_vehicle_driver' or cfg.get('frames')!=COUNT
            or cfg.get('rate_hz')!=RATE or cfg.get('duration_s')!=30
            or [(c.get('name'),c.get('width'),c.get('height')) for c in cfg.get('cameras',[])]
               != [('overview',1920,1080),('approach',1280,720),
                   ('reference_corner',1280,720),('driver_reference',1280,720)]
            or any(c.get('pose_strategy')!='surveyed_world_transform' or c.get('fov_deg')!=90
                   for c in cfg.get('cameras',[]))
            or cfg.get('physical_acceptance_claimed') is not False
            or cfg.get('engineering_initial_ego_gap_m') not in (-20,-25)
            or cfg.get('camera_height_offset_m') not in (0,1.0)
            or cfg.get('camera_fov_deg') not in (90,105)):
        raise ValueError('Exact emergency construction contract differs')
    expected={'primary':(-20,0,90),'fallback1':(-25,0,90),'fallback2':(-20,1.0,105)}
    if (cfg['engineering_initial_ego_gap_m'],cfg['camera_height_offset_m'],cfg['camera_fov_deg'])!=expected[cfg['candidate_id']]:
        raise ValueError('Candidate engineering knobs differ')
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
    heading=s.get('travel_heading_deg')
    if type(heading) not in (int,float) or not math.isfinite(heading):
        raise ValueError('Reviewed same-direction road heading missing')
    angle=math.radians(heading)
    dx=s['ego_spawn_xyz_m'][0]-s['emergency_spawn_xyz_m'][0]
    dy=s['ego_spawn_xyz_m'][1]-s['emergency_spawn_xyz_m'][1]
    gap=dx*math.cos(angle)+dy*math.sin(angle)
    lateral=-dx*math.sin(angle)+dy*math.cos(angle)
    if abs(gap-config()['engineering_initial_ego_gap_m'])>0.5:
        raise ValueError('Selected engineering spawn gap differs')
    if abs(lateral)<2.5:
        raise ValueError('Separate adjacent-lane trajectories required')
    if set(s['camera_world_transforms'])!=set(CAMERAS):
        raise ValueError('Four camera transforms required')
    return s


def validate_native_lane_pair(ego_waypoint, emergency_waypoint, travel_heading_deg):
    """Require two adjacent, same-direction driving lanes on one Native road."""
    if ego_waypoint is None or emergency_waypoint is None:
        raise ValueError('Native spawn is outside a driving lane')
    ego_road, emergency_road = ego_waypoint.road_id, emergency_waypoint.road_id
    ego_lane, emergency_lane = ego_waypoint.lane_id, emergency_waypoint.lane_id
    if (type(ego_road) is not int or type(emergency_road) is not int
            or ego_road != emergency_road or type(ego_lane) is not int
            or type(emergency_lane) is not int or ego_lane * emergency_lane <= 0
            or abs(ego_lane - emergency_lane) != 1):
        raise ValueError('Native spawns are not adjacent same-direction lanes on one road')
    for waypoint in (ego_waypoint, emergency_waypoint):
        yaw = waypoint.transform.rotation.yaw
        if type(yaw) not in (int, float) or not math.isfinite(yaw):
            raise ValueError('Native lane heading absent')
        if math.cos(math.radians(yaw - travel_heading_deg)) < math.cos(math.radians(30)):
            raise ValueError('Native lane heading differs from reviewed travel axis')
    return {'road_id': ego_road, 'ego_lane_id': ego_lane,
            'emergency_lane_id': emergency_lane}


def transform(carla,xyz,rotation):
    return carla.Transform(carla.Location(x=xyz[0],y=xyz[1],z=xyz[2]),
                           carla.Rotation(pitch=rotation[0],yaw=rotation[1],roll=rotation[2]))


def execute(output,survey,host,port):
    import carla
    from worker_exchange.native_output import FrameMap
    from worker_exchange.world_restore import snapshot,restore
    cfg=config();survey_check(survey)
    output=Path(output).resolve()
    if any((output/name).exists() for name in ('video_frames.jsonl','vehicle_poses.jsonl','trace.jsonl')):
        raise ValueError('Original Native frame sources already exist')
    client=carla.Client(host,port);client.set_timeout(120)
    saved=snapshot(client);world=client.get_world()
    if world.get_map().name!=survey['map_name'] or saved['settings'].synchronous_mode:
        raise RuntimeError('Reviewed map and exclusive asynchronous world required')
    native_map=world.get_map()
    ego_xyz,emergency_xyz=survey['ego_spawn_xyz_m'],survey['emergency_spawn_xyz_m']
    ego_waypoint=native_map.get_waypoint(carla.Location(x=ego_xyz[0],y=ego_xyz[1],z=ego_xyz[2]),
        project_to_road=False,lane_type=carla.LaneType.Driving)
    emergency_waypoint=native_map.get_waypoint(carla.Location(x=emergency_xyz[0],y=emergency_xyz[1],z=emergency_xyz[2]),
        project_to_road=False,lane_type=carla.LaneType.Driving)
    native_lanes=validate_native_lane_pair(ego_waypoint,emergency_waypoint,survey['travel_heading_deg'])
    actors=[];encoders={};queues={}
    try:
        settings=world.get_settings();settings.synchronous_mode=True;settings.fixed_delta_seconds=1/RATE
        world.apply_settings(settings)
        lib=world.get_blueprint_library()
        heading=survey['travel_heading_deg']
        ego=world.try_spawn_actor(lib.find(survey['ego_blueprint']),transform(carla,survey['ego_spawn_xyz_m'],[0,heading,0]))
        emergency=world.try_spawn_actor(lib.find(survey['emergency_blueprint']),transform(carla,survey['emergency_spawn_xyz_m'],[0,heading,0]))
        if ego is None or emergency is None:raise RuntimeError('Reviewed vehicle blueprint spawn failed')
        actors.extend((ego,emergency));output.mkdir(parents=True,exist_ok=True)
        special=carla.VehicleLightState.Special1
        for c in cfg['cameras']:
            bp=lib.find('sensor.camera.rgb');bp.set_attribute('image_size_x',str(c['width']))
            bp.set_attribute('image_size_y',str(c['height']));bp.set_attribute('sensor_tick',str(1/RATE))
            bp.set_attribute('fov',str(cfg['camera_fov_deg']))
            pose=survey['camera_world_transforms'][c['name']]
            camera_xyz=list(pose['xyz_m'])
            camera_xyz[2]+=cfg['camera_height_offset_m']
            camera=world.spawn_actor(bp,transform(carla,camera_xyz,pose['rotation_deg']))
            actors.append(camera);q=queue.Queue();camera.listen(q.put);queues[c['name']]=q
            encoders[c['name']]=subprocess.Popen(['ffmpeg','-nostdin','-v','error','-y',
                '-f','rawvideo','-pix_fmt','bgra','-s',f"{c['width']}x{c['height']}",
                '-r',str(RATE),'-i','-','-frames:v',str(COUNT),'-c:v','ffv1',
                str(output/(c['name']+'.mkv'))],stdin=subprocess.PIPE,stderr=subprocess.PIPE)
        first=None
        with FrameMap(output/'video_frames.jsonl') as fmap,\
                (output/'vehicle_poses.jsonl').open('x') as out,\
                (output/'trace.jsonl').open('x') as trace_out:
            for i in range(COUNT):
                phase=(i//10)%2==0
                emergency.set_light_state(carla.VehicleLightState(special if phase else 0))
                travel_rad=math.radians(heading)
                travel_x,travel_y=math.cos(travel_rad),math.sin(travel_rad)
                emergency.set_target_velocity(carla.Vector3D(x=4*travel_x,y=4*travel_y,z=0))
                ego_requested=5 if cfg['case_suffix']=='controlled_2' and i<380 else 4
                ego.set_target_velocity(carla.Vector3D(x=ego_requested*travel_x,y=ego_requested*travel_y,z=0))
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
                ego_pose=ego.get_transform();ego_velocity=ego.get_velocity()
                trace_out.write(json.dumps({'frame':native,'time_s':t,
                    'position_m':[ego_pose.location.x,ego_pose.location.y,ego_pose.location.z],
                    'position':{'x':ego_pose.location.x,'y':ego_pose.location.y,'z':ego_pose.location.z},
                    'heading_deg':ego_pose.rotation.yaw,
                    'speed_mps':records[0]['speed_mps'],
                    'velocity_mps':[ego_velocity.x,ego_velocity.y,ego_velocity.z]})+'\n')
        for name,process in encoders.items():
            process.stdin.close();stderr=process.stderr.read()
            if process.wait(timeout=180):raise RuntimeError('Camera encode failed: '+name+' '+stderr.decode()[-300:])
        (output/'emergency_context.template.json').write_text(json.dumps({'assignment_id':AID,
            'case_id':cfg['case_id'],
            'review_kind':'original_source_review','ego_actor_id':ego.id,
            'emergency_actor_id':emergency.id,'qualification_review_required':True,
            'native_lane_pair':native_lanes,
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
