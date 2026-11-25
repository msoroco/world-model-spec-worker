"""Survey-gated same-direction emergency vehicle capture; --check is CPU-only."""
import argparse
import json
import math
import os
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
            or cfg.get('case_suffix') not in ('controlled_1','controlled_2','official_1','official_2','preparing_movement','preparing_hand_signal')
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
    if cfg['case_suffix'] in ('preparing_movement','preparing_hand_signal') and cfg.get('reference_motion_request')!={
            'stopped_frames':[0,79],'visible_preparation_frames':[80,119],
            'subsequent_moving_frames':[120,599]}:
        raise ValueError('Visible preparation phase contract differs')
    expected={'primary':(-20,0,90),'fallback1':(-25,0,90),'fallback2':(-20,1.0,105)}
    if (cfg['engineering_initial_ego_gap_m'],cfg['camera_height_offset_m'],cfg['camera_fov_deg'])!=expected[cfg['candidate_id']]:
        raise ValueError('Candidate engineering knobs differ')
    return cfg


def survey_check(s):
    suffix=config()['case_suffix']
    official=suffix.startswith('official_')
    authority_source=('regulatory_agency_vehicle_source' if official
                      else 'emergency_authorization_source')
    for key in ('map_name','map_source','lane_boundaries_source',authority_source,
                'qualifying_flash_equipment_source','officer_direction_review_source',
                'ego_blueprint','emergency_blueprint','ego_spawn_xyz_m',
                'emergency_spawn_xyz_m','camera_world_transforms'):
        if not s.get(key):raise ValueError('Missing reviewed Native survey source: '+key)
    authority_key=('official_regulatory_vehicle' if official else 'emergency_vehicle_authorized')
    if s.get(authority_key) is not True or s.get('qualifying_flash_equipment_reviewed') is not True:
        raise ValueError('Reference vehicle authority or light equipment not reviewed')
    if type(s.get('officer_directed_otherwise')) is not bool:
        raise ValueError('Officer direction exception missing')
    if suffix in ('preparing_movement','preparing_hand_signal') and (not s.get('preparing_to_move_source')
            or not s.get('visible_vehicle_movement_source' if suffix=='preparing_movement' else 'driver_hand_signal_visual_source')
            or s.get('preparing_to_move_reviewed') is not True):
        raise ValueError('Reviewed visible vehicle preparation source missing')
    if suffix=='preparing_hand_signal':
        for key in ('driver_signal_blueprint','driver_signal_blueprint_source',
                    'driver_signal_actor_identity_source','driver_signal_window_xyz_m',
                    'driver_signal_window_source','driver_signal_visual_review_source'):
            if not s.get(key):raise ValueError('Reviewed driver hand signal construction missing: '+key)
        if len(s['driver_signal_window_xyz_m'])!=3:
            raise ValueError('Original driver window signal geometry missing')
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


def reference_motion_request(frame,case_suffix):
    if type(frame) is not int or not 0<=frame<COUNT:
        raise ValueError('Exact source motion frame required')
    if case_suffix=='preparing_hand_signal':
        return 0.0 if frame<120 else 4.0
    if case_suffix in ('preparing_movement','preparing_hand_signal'):
        return 0.0 if frame<80 else 0.5 if frame<120 else 4.0
    return 4.0


def execute(output,survey,host,port):
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap,seal_capture
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
    actors=[];encoders={};queues={};capture_writer=None;restored=None;encoder_codes={}
    try:
        settings=world.get_settings();settings.synchronous_mode=True;settings.fixed_delta_seconds=1/RATE
        world.apply_settings(settings)
        lib=world.get_blueprint_library()
        heading=survey['travel_heading_deg']
        ego=world.try_spawn_actor(lib.find(survey['ego_blueprint']),transform(carla,survey['ego_spawn_xyz_m'],[0,heading,0]))
        emergency=world.try_spawn_actor(lib.find(survey['emergency_blueprint']),transform(carla,survey['emergency_spawn_xyz_m'],[0,heading,0]))
        if ego is None or emergency is None:raise RuntimeError('Reviewed vehicle blueprint spawn failed')
        actors.extend((ego,emergency));output.mkdir(parents=True,exist_ok=True)
        signal_actor=None
        if cfg['case_suffix']=='preparing_hand_signal':
            signal_actor=world.try_spawn_actor(lib.find(survey['driver_signal_blueprint']),
                transform(carla,survey['driver_signal_window_xyz_m'],[0,heading,0]))
            if signal_actor is None:raise RuntimeError('Reviewed driver hand signal actor spawn failed')
            actors.append(signal_actor)
        capture_writer=PipelineCapture(client,ego,output,cfg['case_id'],
                                       required_observations=cfg['required_atoms'])
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
                (output/'vehicle_poses.jsonl').open('x') as out:
            for i in range(COUNT):
                phase=(i//10)%2==0
                emergency.set_light_state(carla.VehicleLightState(special if phase else 0))
                travel_rad=math.radians(heading)
                travel_x,travel_y=math.cos(travel_rad),math.sin(travel_rad)
                if cfg['case_suffix'] in ('preparing_movement','preparing_hand_signal'):
                    reference_requested=reference_motion_request(i,cfg['case_suffix'])
                    ego_requested=reference_requested
                else:
                    reference_requested=reference_motion_request(i,cfg['case_suffix'])
                    ego_requested=5 if cfg['case_suffix'] in ('controlled_2','official_2') and i<380 else 4
                if signal_actor is not None:
                    # The surveyed arm mesh stays at the source driver's window.
                    # Its alternating orientation makes the gesture visible in pixels;
                    # original review must still establish driver identity and intent.
                    gesture_yaw=heading+(25 if 80<=i<120 and (i//5)%2 else -25 if 80<=i<120 else 0)
                    source_pose=emergency.get_transform().location
                    offset=[a-b for a,b in zip(survey['driver_signal_window_xyz_m'],
                                                 survey['emergency_spawn_xyz_m'])]
                    window_xyz=[source_pose.x+offset[0],source_pose.y+offset[1],
                                source_pose.z+offset[2]]
                    signal_actor.set_transform(transform(carla,window_xyz,[0,gesture_yaw,0]))
                emergency.set_target_velocity(carla.Vector3D(x=reference_requested*travel_x,
                    y=reference_requested*travel_y,z=0))
                ego.set_target_velocity(carla.Vector3D(x=ego_requested*travel_x,y=ego_requested*travel_y,z=0))
                native=world.tick();snap=world.get_snapshot()
                if snap.frame!=native:raise RuntimeError('Original Native frame mismatch')
                if first is None:first=snap.timestamp.elapsed_seconds
                t=snap.timestamp.elapsed_seconds-first
                capture_writer.capture(native,t,extra={'emergency_actor_id':emergency.id})
                mapped={}
                for name,q in queues.items():
                    image=q.get(timeout=30)
                    if image.frame!=native:raise RuntimeError('Original camera frame mismatch')
                    encoders[name].stdin.write(image.raw_data);mapped[name]=image.frame
                fmap.append(native,t,native_frame=native,camera_native_frames=mapped)
                records=[]
                for actor in (ego,emergency):
                    pose=actor.get_transform();vel=actor.get_velocity();bbox=actor.bounding_box.extent
                    records.append({'actor_id':actor.id,'x_m':pose.location.x,'y_m':pose.location.y,
                        'heading_rad':pose.rotation.yaw*math.pi/180,
                        'speed_mps':math.sqrt(vel.x*vel.x+vel.y*vel.y+vel.z*vel.z),
                        'half_length_m':bbox.x,'half_width_m':bbox.y})
                records[1]['flashing_light_phase_on']=bool(emergency.get_light_state() & special)
                if cfg['case_suffix']=='preparing_hand_signal':
                    records[1]['driver_hand_signal_visible']=bool(80<=i<120)
                    records[1]['driver_signal_actor_id']=signal_actor.id
                if cfg['case_suffix']=='preparing_movement':
                    records[1]['visible_vehicle_movement']=bool(80<=i<120 and records[1]['speed_mps']>0)
                out.write(json.dumps({'video_frame':i,'native_frame':native,
                    'source_kind':'original_native_pose','ego':records[0],
                    'emergency':records[1]})+'\n')
        for name,process in encoders.items():
            process.stdin.close();stderr=process.stderr.read()
            encoder_codes[name]=process.wait(timeout=180)
            if encoder_codes[name]:raise RuntimeError('Camera encode failed: '+name+' '+stderr.decode()[-300:])
        capture_writer.close(confirmed=True)
        (output/'emergency_context.template.json').write_text(json.dumps({'assignment_id':AID,
            'case_id':cfg['case_id'],
            'review_kind':'original_source_review','ego_actor_id':ego.id,
            'emergency_actor_id':emergency.id,'qualification_review_required':True,
            'reference_vehicle_kind':('official_regulatory_vehicle' if cfg['case_suffix'].startswith('official_')
                                      else 'authorized_emergency_vehicle'),
            'preparation_review_required':cfg['case_suffix'] in ('preparing_movement','preparing_hand_signal'),
            'driver_signal_review_required':cfg['case_suffix']=='preparing_hand_signal',
            'driver_signal_actor_id':signal_actor.id if signal_actor is not None else None,
            'native_lane_pair':native_lanes,
            'camera_sha256':{}},indent=2)+'\n')
    finally:
        if capture_writer is not None and not capture_writer.closed:
            capture_writer.close(confirmed=False)
        for process in encoders.values():
            if process.poll() is None:process.kill();process.wait()
        for actor in reversed(actors):
            try:
                if hasattr(actor,'stop'):actor.stop()
                actor.destroy()
            except Exception:pass
        restored=restore(client,saved)
    (output/'acquisition-provenance.json').write_text(json.dumps({
        'provenance_kind':'native','diagnostic_fixture':False,
        'native_executed':True},indent=2)+'\n')
    seal_capture(output,frames=COUNT,restoration=restored,errors=[],
                 encoder_exit_codes=encoder_codes,context={'native_lane_pair':native_lanes})
    return {'case_id':cfg['case_id'],'original_frames':COUNT,
            'capture_sealed':True,'physical_acceptance_claimed':False}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true')
    parser.add_argument('--survey',type=Path);parser.add_argument('--output-dir',type=Path)
    parser.add_argument('--host',default='127.0.0.1');parser.add_argument('--port',type=int,default=2000)
    args=parser.parse_args();cfg=config()
    if args.check:print(json.dumps({'passed':True,'case_id':cfg['case_id'],'frames':COUNT,
        'cameras':list(CAMERAS),'native_imported':False,'physical_acceptance_claimed':False}))
    else:
        survey_path=args.survey or (Path(os.environ['SCENARIO_NATIVE_SURVEY'])
                                    if os.environ.get('SCENARIO_NATIVE_SURVEY') else None)
        if survey_path is None or args.output_dir is None:
            parser.error('--output-dir and --survey or SCENARIO_NATIVE_SURVEY required')
        print(json.dumps(execute(args.output_dir,json.loads(survey_path.read_text()),args.host,args.port)))
