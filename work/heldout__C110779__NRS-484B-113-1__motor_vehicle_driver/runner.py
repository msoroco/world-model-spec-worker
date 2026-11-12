"""CARLA-lazy exact intersection backing capture for C110779."""
import argparse
import json
from math import atan2,hypot
import os
from pathlib import Path
import shutil

from backing_camera import BackingCameraCapture,CAMERAS,LosslessSourceSink
from backing_corridor import verify
from backing_source_capture import BackingSourceRecorder
from reverse_feedback import command

PREFIX='heldout__C110779__NRS-484B-113-1__motor_vehicle_driver__'
SUFFIXES={'backing_clear_vehicle','backing_near_vehicle'}

def check_traffic_placement(corridor,case):
    start=tuple(corridor['start_xy']);other=tuple(corridor['other_vehicle_xy'])
    distance=hypot(other[0]-start[0],other[1]-start[1])
    bounds={'backing_clear_vehicle':(11.0,15.0),'backing_near_vehicle':(7.0,11.0)}
    suffix=case[len(PREFIX):]
    if suffix in bounds and not bounds[suffix][0] <= distance < bounds[suffix][1]:
        raise ValueError('Reviewed other-vehicle initial distance differs from exact case')
    return distance

def check_config(config):
    case=config.get('selected_case_id','')
    if (config.get('law_id'),config.get('cell_id'),config.get('actor'))!=('NRS-484B-113-1','C110779','motor_vehicle_driver') or not case.startswith(PREFIX) or case[len(PREFIX):] not in SUFFIXES:
        raise ValueError('Wrong exact intersection backing case')
    if config.get('rate_hz')!=20 or config.get('frames')!=160 or config.get('duration_s')!=8 or [c.get('name') for c in config.get('cameras',[])]!=list(CAMERAS):
        raise ValueError('Exact 20 Hz four-camera capture contract differs')
    if config.get('case',{}).get('case_id')!=config['selected_case_id']:
        raise ValueError('Selected backing case/config identity differs')
    if config.get('target_reverse_speed_mps',2.0) not in (1.5,2.0,2.5):
        raise ValueError('Unsupported reverse target speed')
    if config.get('other_throttle',.15) not in (.15,.25):
        raise ValueError('Unsupported other-vehicle throttle')
    if config.get('overview_height_delta_m',0) not in (0,2):
        raise ValueError('Unsupported overview height change')
    return config

def _spawn(world,blueprint_id,position,carla):
    location=carla.Location(x=position[0],y=position[1],z=.5)
    waypoint=world.get_map().get_waypoint(location)
    if waypoint is None:
        raise ValueError('Reviewed backing actor position has no Native waypoint')
    transform=carla.Transform(location,waypoint.transform.rotation)
    actor=world.try_spawn_actor(world.get_blueprint_library().find(blueprint_id),transform)
    if actor is None:
        raise ValueError('Native backing actor spawn failed: '+blueprint_id)
    return actor

def run(output,host,port):
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap,seal_capture
    output=Path(output);config=check_config(json.loads((output/'config.json').read_text()))
    manifest=os.environ.get('BACKING_CORRIDOR_MANIFEST')
    if not manifest:
        raise ValueError('Set BACKING_CORRIDOR_MANIFEST to a reviewed Native source')
    target=output/'backing_corridor_original.json'
    if target.exists():raise ValueError('Retain prior original backing corridor source')
    shutil.copyfile(manifest,target)
    client=carla.Client(host,port);client.set_timeout(30)
    world=client.get_world();world_map=world.get_map();original=world.get_settings()
    owned=[];sinks={};cameras=None;pipeline=None;mapping=None;recorder=None;collision=None
    frames=[];completed=False;restored=False;errors=[]
    try:
        settings=world.get_settings();settings.synchronous_mode=True;settings.fixed_delta_seconds=.05;world.apply_settings(settings)
        source=json.loads(target.read_text())
        ego=_spawn(world,'vehicle.tesla.model3',source['start_xy'],carla);owned.append(ego)
        direction=ego.get_transform().get_forward_vector()
        corridor=verify(world_map,target,(direction.x,direction.y))
        check_traffic_placement(corridor,config['selected_case_id'])
        other=_spawn(world,'vehicle.audi.tt',source['other_vehicle_xy'],carla);owned.append(other)
        other_waypoint=world_map.get_waypoint(other.get_transform().location)
        if (other_waypoint.road_id,other_waypoint.lane_id)!=(corridor['other_vehicle_road_id'],corridor['other_vehicle_lane_id']):
            raise ValueError('Other traffic Native road/lane differs from reviewed corridor')
        for name in CAMERAS:sinks[name]=LosslessSourceSink(output,name)
        cameras=BackingCameraCapture(world,carla,ego,sinks,
                                     overview_height_delta_m=config.get('overview_height_delta_m',0))
        context={'format':'worker-native-backing-traffic-context-v1',
                 'corridor_source_sha256':corridor['source_sha256'],
                 'map_name':corridor['map_name'],
                 'participants':{str(other.id):{'kind':'vehicle',
                    'position_motion_purpose_source':'Reviewed corridor purpose, Native actor transform and 20 Hz velocity',
                    'highway_use_source':'Reviewed road/lane and original Native waypoint readback',
                    'purpose':corridor['other_vehicle_purpose'],
                    'road_id':other_waypoint.road_id,'lane_id':other_waypoint.lane_id}}}
        recorder=BackingSourceRecorder(output,ego,[other],context)
        blueprint=world.get_blueprint_library().find('sensor.other.collision')
        collision=world.spawn_actor(blueprint,carla.Transform(),attach_to=ego)
        owned.append(collision)
        collision.listen(lambda event:recorder.contact(event.frame,event.other_actor.id))
        pipeline=PipelineCapture(client,ego,output,config['selected_case_id'],required_observations=config.get('required_atoms',[]))
        mapping=FrameMap(output/'video_frames.jsonl')
        start=None
        for _ in range(config['frames']):
            transform=ego.get_transform();loc=transform.location;heading=transform.get_forward_vector();velocity=ego.get_velocity()
            signed_speed=velocity.x*heading.x+velocity.y*heading.y
            request=command((loc.x,loc.y),atan2(heading.y,heading.x),signed_speed,
                            corridor['end_xy'],config.get('target_reverse_speed_mps',2.0))
            ego.apply_control(carla.VehicleControl(throttle=request['throttle'],brake=request['brake'],
                                                    steer=request['steer'],reverse=True))
            other.apply_control(carla.VehicleControl(throttle=config.get('other_throttle',.15),steer=0))
            frame=world.tick();snapshot=world.get_snapshot()
            if snapshot.frame!=frame:raise ValueError('Native backing snapshot/frame mismatch')
            if start is None:start=snapshot.timestamp.elapsed_seconds
            time_s=snapshot.timestamp.elapsed_seconds-start
            cameras.wait_for_frame(frame)
            trace=pipeline.capture(frame,time_s)
            if trace.get('frame')!=frame or trace.get('time_s')!=time_s:
                raise ValueError('Native backing trace/frame differs')
            mapping.append(frame,time_s)
            recorder.append(frame,time_s)
            frames.append(frame)
        cameras.verify(frames);completed=True
    except BaseException as error:
        errors.append(str(error));raise
    finally:
        if collision is not None:collision.stop()
        if mapping is not None:mapping.close()
        if recorder is not None:recorder.close()
        if pipeline is not None:pipeline.close(confirmed=completed)
        if cameras is not None:cameras.close()
        for sink in sinks.values():sink.close()
        for actor in reversed(owned):actor.destroy()
        world.apply_settings(original)
        current=world.get_settings();restored=(current.synchronous_mode==original.synchronous_mode and current.fixed_delta_seconds==original.fixed_delta_seconds)
        if not restored:raise ValueError('Native backing settings restoration differs')
    (output/'acquisition-provenance.json').write_text(json.dumps({'provenance_kind':'native','diagnostic_fixture':False,'original_frames':len(frames)})+'\n')
    seal_capture(output,frames=len(frames),restoration={'restored':restored},errors=errors,
                 encoder_exit_codes={name:0 for name in CAMERAS},
                 context={'corridor_source_sha256':corridor['source_sha256'],'native_map_name':world_map.name})

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');parser.add_argument('--output-dir');parser.add_argument('--host',default='127.0.0.1');parser.add_argument('--port',type=int,default=2000);args=parser.parse_args()
    if args.check:
        check_config(json.loads(Path('config.json').read_text()));return
    if not args.output_dir:parser.error('--output-dir required')
    run(args.output_dir,args.host,args.port)
if __name__=='__main__':main()
