"""Native four-view officer-direction attempt for the fixed C10365 alley cell.

The captured gesture and response are observations. This runner supplies no
finding that the direction was lawful or that the subject acted willfully.
"""
from __future__ import annotations
import argparse,json,math
from pathlib import Path

PREFIX='heldout__C10365__NRS-484B-100__motor_vehicle_driver__'
CASES={
    'stop_responds':('stop',True),
    'stop_does_not_respond':('stop',False),
    'proceed_responds':('proceed',True),
    'proceed_does_not_respond':('proceed',False),
}

def check_config(config):
    if (config.get('law_id'),config.get('cell_id'),config.get('actor'))!=('NRS-484B-100','C10365','motor_vehicle_driver'):
        raise ValueError('Wrong frozen officer-direction scope')
    case=config.get('selected_case_id','')
    suffix=case.removeprefix(PREFIX)
    if case!=PREFIX+suffix or suffix not in CASES or config.get('case',{}).get('case_id')!=case:
        raise ValueError('Unknown exact officer-direction case')
    if config.get('rate_hz')!=20 or config.get('frames')!=160 or len(config.get('cameras',[]))!=4:
        raise ValueError('Four-view 20 Hz capture contract missing')
    if config.get('direction_frame')!=40:
        raise ValueError('Timed indication frame changed')
    return CASES[suffix]

def choose_alley_route(world_map,*,distance_m=18.0):
    """Select a connected, narrow, nonjunction lane with an officer sidewalk."""
    for spawn in world_map.get_spawn_points():
        lane=world_map.get_waypoint(spawn.location)
        if lane is None or lane.is_junction or not 2.3<=lane.lane_width<=3.5:
            continue
        ahead=lane.next(distance_m)
        if len(ahead)!=1 or ahead[0].is_junction or ahead[0].road_id!=lane.road_id or ahead[0].lane_id!=lane.lane_id:
            continue
        officer=lane.get_right_lane()
        if officer is None or str(officer.lane_type).lower().find('sidewalk')<0:
            continue
        return lane,ahead[0],officer
    raise ValueError('No connected Native alley lane with adjacent officer sidewalk')

def command_for(command,responds,frame,direction_frame):
    """Predeclared physical motion; observed response is measured after capture."""
    if frame<direction_frame:return {'throttle':0.16,'brake':0.0}
    if command=='stop':return {'throttle':0.0,'brake':0.7} if responds else {'throttle':0.16,'brake':0.0}
    return {'throttle':0.18,'brake':0.0} if responds else {'throttle':0.0,'brake':0.7}

def _arm_bone(bones):
    names=[name for name,_ in bones.bone_transforms]
    for marker in ('upperarm_r','upper_arm_r','rightupperarm','r_upperarm','r_arm'):
        matches=[name for name in names if marker in name.lower()]
        if len(matches)==1:return matches[0]
    raise ValueError('Native officer walker has no identifiable right upper-arm bone: '+str(names))

def pose_direction(carla,officer,command):
    """Use CARLA's walker bone pose API to create a distinct visible arm cue."""
    bones=officer.get_bones();arm=_arm_bone(bones)
    angle=95.0 if command=='stop' else 35.0
    transform=carla.Transform(carla.Location(),carla.Rotation(pitch=angle))
    officer.set_bones(carla.WalkerBoneControlIn([(arm,transform)]))
    officer.blend_pose(1.0)
    return {'bone':arm,'relative_pitch_deg':angle,'command':command}

def _spawn(world,blueprint,transform):
    actor=world.try_spawn_actor(blueprint,transform)
    if actor is None:raise ValueError('Native officer scene actor spawn failed: '+blueprint.id)
    return actor

def run(output,host,port):
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap,seal_capture
    from officer_camera_capture import CAMERAS,FFmpegSourceSink,OfficerCameraCapture
    output=Path(output);config=json.loads((output/'config.json').read_text());command,responds=check_config(config)
    client=carla.Client(host,port);client.set_timeout(30)
    world=client.get_world();original=world.get_settings();actors=[];sinks={};camera=None;pipeline=None;mapping=None
    frames=[];failed=False;restored=False
    try:
        settings=world.get_settings();settings.synchronous_mode=True;settings.fixed_delta_seconds=.05;world.apply_settings(settings)
        lane,front,sidewalk=choose_alley_route(world.get_map())
        library=world.get_blueprint_library();ego=_spawn(world,library.find('vehicle.tesla.model3'),lane.transform);actors.append(ego)
        walker_blueprints=library.filter('walker.pedestrian.*')
        if not walker_blueprints:raise ValueError('Native officer walker blueprint unavailable')
        officer=_spawn(world,walker_blueprints[0],sidewalk.transform);actors.append(officer)
        officer.apply_control(carla.WalkerControl(speed=0.0))
        for name in CAMERAS:sinks[name]=FFmpegSourceSink(output,name)
        camera=OfficerCameraCapture(world,carla,ego,sinks)
        pipeline=PipelineCapture(client,ego,output,config['selected_case_id'],required_observations=config.get('required_atoms',[]))
        mapping=FrameMap(output/'video_frames.jsonl')
        pose=None;motion=[];direction=None;start=None
        for index in range(config['frames']):
            if index==config['direction_frame']:pose=pose_direction(carla,officer,command)
            control=command_for(command,responds,index,config['direction_frame'])
            ego.apply_control(carla.VehicleControl(throttle=control['throttle'],brake=control['brake'],steer=0.0))
            frame=world.tick();snapshot=world.get_snapshot()
            if snapshot.frame!=frame:raise ValueError('Native officer snapshot/frame mismatch')
            if start is None:start=snapshot.timestamp.elapsed_seconds
            time_s=snapshot.timestamp.elapsed_seconds-start
            camera.wait_for_frame(frame)
            trace=pipeline.capture(frame,time_s)
            if trace.get('frame')!=frame or trace.get('time_s')!=time_s:raise ValueError('Original officer trace/frame join differs')
            mapping.append(frame,time_s)
            velocity=ego.get_velocity()
            motion.append({'frame':frame,'time_s':time_s,'subject_id':str(ego.id),'speed_mps':math.hypot(velocity.x,velocity.y),'position_m':[ego.get_location().x,ego.get_location().y,ego.get_location().z]})
            if index==config['direction_frame']:
                direction={'frame':frame,'officer_id':str(officer.id),'subject_id':str(ego.id),'command':command,'indication_source':'original four-view video and walker bone readback','pose':pose}
            frames.append(frame)
        camera.verify_frames(frames)
        if direction is None:raise ValueError('No original officer indication')
        (output/'officer_context.json').write_text(json.dumps({'actor_role':'motor_vehicle_driver','officer_role':'police_officer','officer_id':str(officer.id),'subject_id':str(ego.id),'duty_source':'scenario role assignment; legal review required','lawfulness_source':'original officer indication and independent legal review required','legal_conclusion':None,'willfulness_conclusion':None},indent=2)+'\n')
        (output/'officer_direction.json').write_text(json.dumps(direction,indent=2)+'\n')
        (output/'subject_motion.json').write_text(json.dumps({'frames':motion},indent=2)+'\n')
        (output/'subject_motion_history.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in motion))
    except BaseException:
        failed=True;raise
    finally:
        if mapping:mapping.close()
        if pipeline:pipeline.close(confirmed=not failed)
        if camera:camera.close()
        for sink in sinks.values():sink.close()
        for actor in reversed(actors):actor.destroy()
        world.apply_settings(original)
        current=world.get_settings();restored=current.synchronous_mode==original.synchronous_mode and current.fixed_delta_seconds==original.fixed_delta_seconds
        if not restored:raise ValueError('Native officer settings restoration readback differs')
    (output/'acquisition-provenance.json').write_text(json.dumps({'provenance_kind':'native','diagnostic_fixture':False,'original_frames':len(frames)})+'\n')
    seal_capture(output,frames=len(frames),restoration={'restored':restored},errors=[],encoder_exit_codes={name:0 for name in CAMERAS},context={'native_map_name':world.get_map().name,'road_id':lane.road_id,'officer_actor_id':officer.id})

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');parser.add_argument('--output-dir');parser.add_argument('--host',default='127.0.0.1');parser.add_argument('--port',type=int,default=2000);a=parser.parse_args()
    if a.check:
        check_config(json.loads(Path('config.json').read_text()));return
    if not a.output_dir:parser.error('--output-dir required')
    run(a.output_dir,a.host,a.port)
if __name__=='__main__':main()
