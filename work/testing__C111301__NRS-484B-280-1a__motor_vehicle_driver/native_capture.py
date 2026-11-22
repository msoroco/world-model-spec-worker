"""Original CARLA acquisition for the manual-wheelchair encounter cases.

CARLA is imported only for a Native run. Missing chair assets fail before capture.
"""
import hashlib
import json
import math
import queue
import subprocess
from pathlib import Path

from runner import encounter,control,load_scene


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(path,value):Path(path).write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')
def vertices(actor):return [[p.x,p.y,p.z] for p in actor.bounding_box.get_world_vertices(actor.get_transform())]
def speed(actor):
    velocity=actor.get_velocity()
    return math.sqrt(velocity.x**2+velocity.y**2+velocity.z**2)


def select_chair(library,pattern):
    matches=list(library.filter(pattern))
    matches=[bp for bp in matches if 'wheelchair' in bp.id.lower()]
    if not matches:raise ValueError('No distinct Native manual-wheelchair asset matches '+pattern)
    return matches[0]


def connected_route(start,end,limit=1200):
    """Require a forward Native waypoint chain from approach to exit."""
    target=end.transform.location
    pending=[start];seen=set();index=0
    while index<len(pending) and index<limit:
        waypoint=pending[index];index+=1
        location=waypoint.transform.location
        key=(getattr(waypoint,'road_id',None),getattr(waypoint,'lane_id',None),
             round(location.x,1),round(location.y,1))
        if key in seen:continue
        seen.add(key)
        if math.hypot(location.x-target.x,location.y-target.y)<=2.5:return True
        pending.extend(waypoint.next(2.0))
    return False


def pedestrian_station(scene,index):
    start=scene['pedestrian_path_start_xy_m'][1]
    if scene['wheelchair_path_setup']=='clear_path':return 5.0
    if type(index) is not int or index<0 or scene['pedestrian_target_speed_mps']<=0:
        raise ValueError('invalid authored pedestrian step')
    return min(scene['pedestrian_path_end_xy_m'][1],
               start+(index+1)*scene['pedestrian_target_speed_mps']/scene['rate_hz'])


def spawn_entities(world,scene,vehicle_bp,chair_bp,person_bp,transform):
    """Own three distinct actors or remove every partial spawn on failure."""
    actors=[]
    try:
        ego=world.spawn_actor(vehicle_bp,transform(*scene['ego_start_xy_m']))
        actors.append(ego)
        chair_x=scene['pedestrian_path_start_xy_m'][0]
        chair_y=scene['pedestrian_path_start_xy_m'][1] if scene['wheelchair_path_setup']=='crossing' else 5
        chair=world.spawn_actor(chair_bp,transform(chair_x,chair_y,90))
        actors.append(chair)
        person=world.spawn_actor(person_bp,transform(chair_x,chair_y,90))
        actors.append(person)
        if any(actor is None for actor in actors) or len({actor.id for actor in actors})!=3:
            raise ValueError('Native vehicle, person and chair actor identities are not distinct')
        return actors
    except BaseException:
        for actor in reversed(actors):
            if actor is not None:actor.destroy()
        raise


def placement(world,carla,scene):
    mapping=world.get_map()
    def checked(x,y,lane_type=None):
        point=carla.Location(x=x,y=y,z=0)
        waypoint=mapping.get_waypoint(point)
        if waypoint is None or math.hypot(waypoint.transform.location.x-x,waypoint.transform.location.y-y)>2:
            raise ValueError('Authored ego route or wheelchair crossing absent from Native map')
        return waypoint
    start=checked(*scene['ego_start_xy_m']);end=checked(*scene['ego_exit_xy_m'])
    center=checked(scene['pedestrian_path_start_xy_m'][0],0)
    if start.road_id!=center.road_id or center.road_id!=end.road_id:
        raise ValueError('Authored ego path is not on one connected Native road')
    if not connected_route(start,end):
        raise ValueError('No forward Native waypoint path connects ego approach and exit')
    waypoints=[]
    for name,wp in [('approach',start),('crossing',center),('exit',end)]:
        location=wp.transform.location
        waypoints.append({'role':name,'x_m':location.x,'y_m':location.y,
                          'road_id':wp.road_id,'lane_id':wp.lane_id})
    return {'map_name':mapping.name,'road_id':start.road_id,'start_lane_id':start.lane_id,
            'end_lane_id':end.lane_id,'crossing_road_id':center.road_id,
            'route_source':'Native CARLA waypoint map','ego_route_geometry':waypoints}


class Cameras:
    SPECS=(('overview',1920,1080,(0,0,45,-90)),
           ('approach',1280,720,(-15,-12,12,-25)),
           ('reference_corner',1280,720,(4,4,12,-45)),
           ('driver_reference',1280,720,(0,0,2,0)))
    def __init__(self,world,ego,output,carla):
        self.sensors=[];self.encoders={};self.queues={};self.errors=[]
        try:
            for name,width,height,pose in self.SPECS:
                bp=world.get_blueprint_library().find('sensor.camera.rgb')
                bp.set_attribute('image_size_x',str(width));bp.set_attribute('image_size_y',str(height));bp.set_attribute('fov','90')
                x,y,z,pitch=pose
                transform=carla.Transform(carla.Location(x=x,y=y,z=z),carla.Rotation(pitch=pitch))
                sensor=world.spawn_actor(bp,transform,attach_to=ego if name=='driver_reference' else None)
                self.sensors.append(sensor);frames=queue.Queue(maxsize=4);self.queues[name]=frames
                def receive(image,q=frames,label=name):
                    try:q.put_nowait(image)
                    except queue.Full:self.errors.append('camera queue overflow: '+label)
                sensor.listen(receive)
                command=['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-n',
                    '-f','rawvideo','-pixel_format','bgra','-video_size',f'{width}x{height}',
                    '-framerate','20','-i','pipe:0','-an','-c:v','ffv1','-pix_fmt','bgra',str(output/(name+'.mkv'))]
                self.encoders[name]=subprocess.Popen(command,stdin=subprocess.PIPE,stderr=subprocess.DEVNULL)
        except BaseException:
            self.close();raise
    def append(self,frame):
        if self.errors:raise RuntimeError('; '.join(self.errors))
        for name,_,_,_ in self.SPECS:
            image=self.queues[name].get(timeout=15)
            if image.frame!=frame:raise RuntimeError('camera frame differs from world frame: '+name)
            self.encoders[name].stdin.write(image.raw_data)
    def close(self):
        failures=[]
        for sensor in reversed(self.sensors):
            try:sensor.stop()
            except BaseException as error:failures.append(repr(error))
        for name,process in self.encoders.items():
            try:
                if process.stdin and not process.stdin.closed:process.stdin.close()
                if process.wait(timeout=180)!=0:failures.append('camera encoder failed: '+name)
            except BaseException as error:failures.append(repr(error))
        for sensor in reversed(self.sensors):
            try:sensor.destroy()
            except BaseException as error:failures.append(repr(error))
        if failures:raise RuntimeError('; '.join(failures))


def run_native(scene,output,host,port):
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap,seal_capture
    from worker_exchange.world_restore import fields,equal
    output=Path(output).resolve()
    if not output.is_dir():raise ValueError('Native attempt directory must already exist')
    client=carla.Client(host,port);client.set_timeout(30)
    world=client.get_world();original=world.get_settings();actors=[];cameras=None;capture=None;frame_map=None
    phase='initializing';errors=[];rows=[];restored=False
    try:
        context=placement(world,carla,scene)
        library=world.get_blueprint_library()
        chair_bp=select_chair(library,scene['manual_chair_blueprint_filter'])
        people=list(library.filter(scene['person_blueprint_filter']))
        vehicles=list(library.filter(scene['ego_blueprint_filter']))
        if not people or not vehicles:raise ValueError('Native person or ego blueprint unavailable')
        settings=world.get_settings();settings.synchronous_mode=True;settings.fixed_delta_seconds=.05
        world.apply_settings(settings)
        def transform(x,y,yaw=0):
            wp=world.get_map().get_waypoint(carla.Location(x=x,y=y,z=0))
            z=wp.transform.location.z+.5 if wp else .5
            return carla.Transform(carla.Location(x=x,y=y,z=z),carla.Rotation(yaw=yaw))
        actors=spawn_entities(world,scene,vehicles[0],chair_bp,people[0],transform)
        ego,chair,person=actors
        chair_x=scene['pedestrian_path_start_xy_m'][0]
        chair_y=scene['pedestrian_path_start_xy_m'][1] if scene['wheelchair_path_setup']=='crossing' else 5
        context.update({'manual_wheelchair_asset_source':chair_bp.id,'person_asset_source':people[0].id,
                        'ego_asset_source':vehicles[0].id,'wheelchair_path_setup':scene['wheelchair_path_setup']})
        write(output/'intersection-context.json',context)
        write(output/'acquisition-provenance.json',{'provenance_kind':'native','diagnostic_fixture':False,
            'method':'original CARLA live run'})
        cameras=Cameras(world,ego,output,carla)
        capture=PipelineCapture(client,ego,output,scene['case_id'])
        frame_map=FrameMap(output/'video_frames.jsonl')
        contact=[]
        collision_bp=library.find('sensor.other.collision')
        collision=world.spawn_actor(collision_bp,carla.Transform(),attach_to=ego);actors.append(collision)
        collision.listen(lambda event:contact.append((event.frame,event.other_actor.id)))
        phase='capturing'
        previous_person_center=None;previous_time=None;last_pedestrian_speed=0.0
        with (output/'encounter-history.jsonl').open('x',buffering=1) as stream:
            for index in range(round(scene['duration_s']*20)):
                person_body=vertices(person);chair_body=vertices(chair);ego_body=vertices(ego)
                pedestrian={'role':'person_in_manual_wheelchair','source_ref':people[0].id,
                            'body_vertices_m':person_body}
                manual_chair={'kind':'manual_wheelchair','source_ref':chair_bp.id,
                              'body_vertices_m':chair_body}
                observed=encounter(scene,ego_body,pedestrian,manual_chair,speed(ego),last_pedestrian_speed)
                command=control(scene,observed)
                ego.apply_control(carla.VehicleControl(throttle=command['throttle'],brake=command['brake'],steer=command['steer']))
                if scene['wheelchair_path_setup']=='crossing':
                    next_y=pedestrian_station(scene,index)
                    chair.set_transform(transform(chair_x,next_y,90));person.set_transform(transform(chair_x,next_y,90))
                frame=world.tick();snapshot=world.get_snapshot()
                if snapshot.frame!=frame:raise RuntimeError('Native frame identity changed')
                time_s=snapshot.timestamp.elapsed_seconds
                capture.capture(frame,time_s);cameras.append(frame);frame_map.append(frame,time_s)
                ego_body=vertices(ego);person_body=vertices(person);chair_body=vertices(chair)
                center=(sum(p[0] for p in person_body)/len(person_body),
                        sum(p[1] for p in person_body)/len(person_body))
                pedestrian_speed=(math.hypot(center[0]-previous_person_center[0],
                   center[1]-previous_person_center[1])/(time_s-previous_time)
                   if previous_person_center is not None else 0.0)
                previous_person_center=center;previous_time=time_s
                last_pedestrian_speed=pedestrian_speed
                pedestrian['body_vertices_m']=person_body;manual_chair['body_vertices_m']=chair_body
                observed=encounter(scene,ego_body,pedestrian,manual_chair,speed(ego),pedestrian_speed)
                row={'frame':frame,'time_s':time_s,'ego_body_vertices_m':ego_body,
                     'ego_speed_mps':speed(ego),'ego_brake':command['brake'],
                     'pedestrian_speed_mps':pedestrian_speed,
                     'person':pedestrian,'manual_wheelchair':manual_chair,
                     'surface_gap_m':observed['surface_gap_m'],
                     'contact_event':any(f==frame and a in (person.id,chair.id) for f,a in contact)}
                stream.write(json.dumps(row,allow_nan=False)+'\n');rows.append(row)
        phase='closing';capture.close();capture=None;frame_map.close();frame_map=None;cameras.close();cameras=None
        names=['trace.jsonl','video_frames.jsonl','encounter-history.jsonl','intersection-context.json',
               'road.xodr','carla_recorder.log',*[name+'.mkv' for name,*_ in Cameras.SPECS]]
        write(output/'acquisition.json',{name:{'kind':'original_native','sha256':sha(output/name)} for name in names})
        phase='sealed'
    except BaseException as error:
        errors.append(repr(error));raise
    finally:
        for resource in (capture,frame_map,cameras):
            if resource:
                try:resource.close()
                except BaseException as error:errors.append(repr(error))
        for actor in reversed(actors):
            try:actor.destroy()
            except BaseException as error:errors.append(repr(error))
        try:
            world.apply_settings(original)
            restored=all(equal(fields(world.get_settings()).get(key),value)
                         for key,value in fields(original).items())
        except BaseException as error:errors.append(repr(error))
        if phase=='sealed' and not errors and restored:
            seal_capture(output,frames=len(rows),restoration={'restored':True,
                'settings_readback':'synchronous mode and fixed delta restored'},errors=[],
                encoder_exit_codes={name:0 for name,*_ in Cameras.SPECS},context={'wheelchair':context})
        else:
            write(output/'native-run-status.json',{'phase':phase,'errors':errors,'settings_restored':restored})
            if phase=='sealed':raise RuntimeError('Native cleanup or restoration failed')
