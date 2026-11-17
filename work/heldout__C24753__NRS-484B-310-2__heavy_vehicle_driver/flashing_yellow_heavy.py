"""Heavy-vehicle flashing-yellow scene request and source-shaped observation.

An adapter must implement these creation/readback operations in the Native runner.
The chosen speeds and blink period are engineering inputs, not legal thresholds.
"""
from __future__ import annotations
from dataclasses import dataclass
from math import hypot, cos, sin, radians

@dataclass(frozen=True)
class Case:
    name: str
    direction: str
    target_mps: float
    crossing_vehicle: bool

CASES={
    'east_cautious_proxy':Case('east_cautious_proxy','east',3.0,True),
    'east_faster_proxy':Case('east_faster_proxy','east',7.0,True),
    'east_no_crossing':Case('east_no_crossing','east',3.0,False),
    'west_cautious_proxy':Case('west_cautious_proxy','west',3.0,True),
}

def lamp_on(time_s,cycle_s=.5):
    if time_s<0 or cycle_s<=0:raise ValueError('invalid lamp timing')
    return time_s%cycle_s<cycle_s/2

def construct(adapter,case):
    if case.direction not in ('east','west'):raise ValueError('unsupported approach direction')
    intersection=adapter.intersection(layout='blind_intersection',through_lanes=2,cross_lanes=2)
    sign=-1 if case.direction=='east' else 1
    start,end=(sign*70.0,0.0),(-sign*70.0,0.0)
    head=adapter.signal_head(lens='yellow',illuminated=True,governs_approach=case.direction,
                             mounted_xy=(sign*12.0,-sign*3.0))
    device=adapter.official_control_device(type='flashing_yellow',linked_signal=head)
    ego=adapter.vehicle(role='ego',vehicle_class='heavy_vehicle',route=[start,end],target_mps=case.target_mps)
    crossing=None
    if case.crossing_vehicle:
        crossing=adapter.vehicle(role='crossing',vehicle_class='motor_vehicle',route=[(0,-65),(0,65)],target_mps=5)
    return {'intersection':intersection,'signal_head':head,'official_device':device,'ego':ego,'crossing':crossing}

def measure(samples):
    if len(samples)<10:raise ValueError('at least ten original 20 Hz samples required')
    rows=[]
    for i,s in enumerate(samples):
        if abs(s.get('time_s',-1)-i*.05)>.005:raise ValueError('non-20Hz original time')
        if s.get('signal_head_visible') is not True or type(s.get('yellow_lens_on')) is not bool:
            raise ValueError('missing physical yellow signal readback')
        if not s.get('official_device_source') or not s.get('signal_source') or not s.get('ego_source'):
            raise ValueError('original device, signal or heavy-vehicle source missing')
        if s.get('ego_vehicle_class')!='heavy_vehicle' or s.get('approach_direction') not in ('east','west'):
            raise ValueError('heavy subject or approach direction missing')
        if type(s.get('ego_speed_mps')) not in (int,float) or s['ego_speed_mps']<0:
            raise ValueError('original speed sample missing')
        xy=s.get('ego_center_xy')
        if not isinstance(xy,list) or len(xy)!=2:raise ValueError('original ego position missing')
        rows.append({'time_s':s['time_s'],'speed_mps':s['ego_speed_mps'],
                     'distance_to_conflict_m':hypot(*xy),'yellow_lens_on':s['yellow_lens_on'],
                     'approach_direction':s['approach_direction'],
                     'crossing_present':bool(s.get('crossing_source'))})
    if set(r['yellow_lens_on'] for r in rows)!={False,True}:
        raise ValueError('intermittent yellow illumination not observed')
    if len(set(r['approach_direction'] for r in rows))!=1:raise ValueError('approach direction changed within case')
    return {'samples':rows,'vehicle_class':'heavy_vehicle','approach_direction':rows[0]['approach_direction'],
            'min_speed_mps':min(r['speed_mps'] for r in rows),'max_speed_mps':max(r['speed_mps'] for r in rows),
            'crossing_present':any(r['crossing_present'] for r in rows),'legal_caution_judgment':None}

def audit_comparison(a,b,variable):
    if variable not in ('approach_speed','crossing_context','approach_direction'):
        raise ValueError('unknown comparison variable')
    if not a.get('samples') or not b.get('samples'):raise ValueError('original source measurements missing')
    for key in ('map_hash','signal_head_hash','official_device_source','blink_period_s','camera_plan_hash','duration_s','vehicle_class'):
        if not a.get(key) or a[key]!=b.get(key):raise ValueError('fixed condition changed: '+key)
    var={'approach_speed':'target_mps','crossing_context':'crossing_vehicle','approach_direction':'direction'}[variable]
    for key in ('target_mps','crossing_vehicle','direction'):
        if key!=var and a.get(key)!=b.get(key):raise ValueError('undeclared condition changed: '+key)
    if a.get(var)==b.get(var):raise ValueError('deliberate comparison variable did not change')
    return {'comparison_complete':True,'variable':variable,'legal_caution_judgment':None}


def _native_direction(waypoint):
    yaw = radians(float(waypoint.transform.rotation.yaw))
    dx, dy = cos(yaw), sin(yaw)
    if abs(dx) < .75 or abs(dy) > .66:
        return None
    return 'east' if dx > 0 else 'west'


def _native_junction(waypoint):
    cursor = waypoint
    for _ in range(16):
        junction = cursor.get_junction()
        if junction is not None:
            return int(junction.id)
        forward = cursor.next(2.0)
        if len(forward) != 1:
            return None
        cursor = forward[0]
    return None


def discover_native_control(world, official_control_source):
    """Find two distinct map-linked heads at one junction; official status is a premise."""
    if not str(official_control_source or '').strip():
        raise ValueError('missing official-control source premise')
    by_junction = {}
    for light in world.get_actors().filter('traffic.traffic_light*'):
        opendrive = str(light.get_opendrive_id() or '').strip()
        if not opendrive:
            continue
        for waypoint in light.get_affected_lane_waypoints():
            direction = _native_direction(waypoint)
            junction = _native_junction(waypoint)
            if direction and junction is not None:
                by_junction.setdefault(junction, {}).setdefault(direction, []).append(
                    {'light':light,'waypoint':waypoint,'junction_id':junction,
                     'direction':direction,'opendrive_id':opendrive})
    for junction in sorted(by_junction):
        group = by_junction[junction]
        if 'east' in group and 'west' in group:
            east, west = group['east'][0], group['west'][0]
            if east['light'].id != west['light'].id:
                return {'east':east,'west':west}
    raise ValueError('no distinct opposing Native signal heads at one junction')


def _native_route(waypoint, before_m, after_m):
    if before_m <= 0 or after_m <= 0:
        raise ValueError('route distances must be positive')
    before, after = waypoint.previous(before_m), waypoint.next(after_m)
    if len(before) != 1 or len(after) != 1:
        raise ValueError('ambiguous Native route at governed lane')
    return before[0].transform, after[0].transform


def _crossing_route(world_map, junction_id):
    options = []
    for waypoint in world_map.generate_waypoints(5.0):
        if _native_junction(waypoint) != junction_id:
            continue
        yaw = radians(float(waypoint.transform.rotation.yaw))
        if abs(sin(yaw)) < .75 or abs(cos(yaw)) > .66:
            continue
        try:
            start, end = _native_route(waypoint, 65.0, 65.0)
        except ValueError:
            continue
        if abs(float(end.location.y)-float(start.location.y)) < 32.5:
            continue
        options.append((int(waypoint.road_id),int(waypoint.lane_id),start,end))
    if not options:
        raise ValueError('no traversing perpendicular lane at selected junction')
    options.sort(key=lambda x:(x[0],x[1]))
    road,lane,start,end=options[0]
    return {'road_id':road,'lane_id':lane,'start':start,'end':end}


def construct_native(world, case, official_control_source, heavy_blueprint_id,
                     crossing_blueprint_id, *, before_m=70.0):
    """Spawn the actual map-linked actors; the caller owns and destroys returned actors."""
    if case.direction not in ('east','west') or case.target_mps <= 0:
        raise ValueError('invalid heavy-vehicle case')
    if not str(heavy_blueprint_id or '').startswith('vehicle.') or not str(crossing_blueprint_id or '').startswith('vehicle.'):
        raise ValueError('explicit vehicle blueprints required')
    controls = discover_native_control(world, official_control_source)
    selected = controls[case.direction]
    start,end = _native_route(selected['waypoint'],before_m,70.0)
    if (float(end.location.x)-float(start.location.x)) * (1 if case.direction=='east' else -1) <= 0:
        raise ValueError('governed route reverses requested direction')
    crossing_route = _crossing_route(world.get_map(),selected['junction_id']) if case.crossing_vehicle else None
    library = world.get_blueprint_library()
    heavy = library.find(heavy_blueprint_id)
    crossing_blueprint = library.find(crossing_blueprint_id) if crossing_route else None
    owned=[]
    try:
        ego=world.try_spawn_actor(heavy,start)
        if ego is None:
            raise ValueError('heavy Native actor spawn failed')
        owned.append(ego)
        cross=None
        if crossing_route:
            cross=world.try_spawn_actor(crossing_blueprint,crossing_route['start'])
            if cross is None:
                raise ValueError('crossing Native actor spawn failed')
            owned.append(cross)
        return {'controls':controls,'selected':selected,'ego':ego,'crossing':cross,
                'ego_route':(start,end),'crossing_route':crossing_route,'owned':owned,
                'heavy_blueprint_id':heavy_blueprint_id,
                'official_control_source':official_control_source}
    except BaseException:
        for actor in reversed(owned):
            actor.destroy()
        raise


class NativeYellowController:
    """Command and read back the selected physical signal head per capture frame."""
    def __init__(self, light, traffic_light_state, period_s=.5):
        if period_s <= 0:
            raise ValueError('invalid blink period')
        self.light,self.state,self.period_s=light,traffic_light_state,period_s
        self.initial=None

    def __enter__(self):
        self.initial=self.light.get_state()
        return self

    def set_at(self,time_s):
        if self.initial is None:
            raise RuntimeError('signal controller not entered')
        target=self.state.Yellow if lamp_on(time_s,self.period_s) else self.state.Off
        self.light.set_state(target)
        observed=self.light.get_state()
        if observed != target:
            raise ValueError('flashing-yellow Native readback differs')
        return {'frame_time_s':time_s,'yellow_lens_on':target==self.state.Yellow,
                'native_light_state':str(observed),'light_actor_id':int(self.light.id)}

    def __exit__(self,exc_type,exc,tb):
        if self.initial is not None:
            self.light.set_state(self.initial)
            if self.light.get_state()!=self.initial:
                raise ValueError('Native signal restoration readback differs')
            self.initial=None


class NativeSampleCollector:
    """Join post-tick signal/actor readbacks to a canonical original frame map."""
    def __init__(self, scene, case, official_control_source, cameras):
        if scene['selected']['direction'] != case.direction or scene['ego'] is None:
            raise ValueError('Native scene and selected case differ')
        if not str(official_control_source or '').strip():
            raise ValueError('official-control premise missing')
        if set(cameras.sensors)!=set(SOURCE_CAMERAS):
            raise ValueError('original four-camera source inventory differs')
        self.scene,self.case,self.official_control_source=scene,case,official_control_source
        self.cameras=cameras
        self.first_elapsed=None
        self.last_frame=None
        self.last_elapsed=None
        self.index=0

    def capture(self, snapshot, commanded):
        """Call only after world.tick and all four source cameras report this frame."""
        frame=int(snapshot.frame)
        elapsed=float(snapshot.timestamp.elapsed_seconds)
        if self.last_frame is not None and (frame != self.last_frame+1 or
                abs(elapsed-self.last_elapsed-.05)>.001):
            raise ValueError('Native source frames are not contiguous at 20 Hz')
        self.cameras.wait_for_frame(frame)
        if int(commanded['light_actor_id']) != int(self.scene['selected']['light'].id):
            raise ValueError('commanded light differs from governed head')
        observed=str(self.scene['selected']['light'].get_state())
        if observed!=commanded['native_light_state']:
            raise ValueError('post-tick Native signal state differs from command')
        if self.first_elapsed is None:self.first_elapsed=elapsed
        time_s=elapsed-self.first_elapsed
        if abs(time_s-self.index*.05)>.001:
            raise ValueError('Native source time differs from 20 Hz frame index')
        ego=self.scene['ego']
        pose=ego.get_transform().location
        velocity=ego.get_velocity()
        speed=hypot(float(velocity.x),float(velocity.y))
        if hasattr(velocity,'z'):
            speed=hypot(speed,float(velocity.z))
        crossing=self.scene['crossing']
        crossing_source=None
        if crossing is not None:
            cross_pose=crossing.get_transform().location
            cross_velocity=crossing.get_velocity()
            crossing_source={'actor_id':int(crossing.id),
                             'center_xy':[float(cross_pose.x),float(cross_pose.y)],
                             'speed_mps':hypot(float(cross_velocity.x),float(cross_velocity.y))}
        selected=self.scene['selected']
        row={'frame':frame,'time_s':time_s,
             'source_cameras':list(SOURCE_CAMERAS),
             'signal_head_visible':None,
             'yellow_lens_on':commanded['yellow_lens_on'],
             'official_device_source':self.official_control_source,
             'official_device_status':'premise_unverified',
             'signal_source':{'light_actor_id':int(selected['light'].id),
                              'opendrive_id':selected['opendrive_id'],
                              'native_state':observed,'junction_id':selected['junction_id']},
             'ego_source':{'actor_id':int(ego.id),'blueprint_id':self.scene['heavy_blueprint_id']},
             'ego_vehicle_class':'heavy_vehicle',
             'approach_direction':self.case.direction,
             'ego_speed_mps':speed,
             'ego_center_xy':[float(pose.x),float(pose.y)],
             'crossing_source':crossing_source,
             'legal_caution_judgment':None}
        frame_map={'video_frame':self.index,'carla_frame':frame,'time_s':time_s}
        self.last_frame,self.last_elapsed=frame,elapsed
        self.index+=1
        return row,frame_map


SOURCE_CAMERAS={
    'overview':((-12.0,0.0,10.0),(-12.0,0.0,0.0),(1920,1080),100),
    'approach':((2.0,0.0,2.8),(0.0,0.0,0.0),(1280,720),90),
    'reference_corner':((-6.0,3.0,4.5),(-8.0,0.0,0.0),(1280,720),100),
    'driver_reference':((1.0,-0.5,2.4),(0.0,0.0,0.0),(1280,720),85),
}


class FFV1SourceSink:
    """Retain original BGRA sensor pixels as one lossless camera stream."""
    def __init__(self, output, name, *, popen=None):
        import subprocess
        from pathlib import Path
        if name not in SOURCE_CAMERAS:raise ValueError('unknown source camera')
        path=Path(output)/(name+'.mkv')
        if path.exists():raise ValueError('source camera stream already exists')
        width,height=SOURCE_CAMERAS[name][2]
        self.expected_bytes=width*height*4
        launch=popen or subprocess.Popen
        self.process=launch(['ffmpeg','-nostdin','-loglevel','error','-y',
            '-f','rawvideo','-pixel_format','bgra','-video_size',f'{width}x{height}',
            '-framerate','20','-i','pipe:0','-an','-c:v','ffv1',str(path)],
            stdin=subprocess.PIPE)
        self.closed=False

    def write(self,image):
        if self.closed:raise ValueError('source camera sink closed')
        if len(image.raw_data)!=self.expected_bytes:
            raise ValueError('source camera raw byte count changed')
        self.process.stdin.write(image.raw_data)

    def close(self):
        if not self.closed:
            self.closed=True
            self.process.stdin.close()
            if self.process.wait()!=0:
                raise ValueError('source camera FFV1 encoder failed')


class NativeSourceCameras:
    """Attach the four original RGB sensors and join their frames before a tick is recorded."""
    def __init__(self,world,carla_module,subject,sinks):
        from threading import Condition
        if set(sinks)!=set(SOURCE_CAMERAS):
            raise ValueError('exactly four named source camera sinks required')
        self.sinks=sinks
        self.sensors={}
        self.frames={name:set() for name in SOURCE_CAMERAS}
        self.condition=Condition()
        self.errors=[]
        self.closed=False
        library=world.get_blueprint_library()
        try:
            for name,(location,rotation,size,fov) in SOURCE_CAMERAS.items():
                blueprint=library.find('sensor.camera.rgb')
                for key,value in (('image_size_x',size[0]),('image_size_y',size[1]),
                                  ('fov',fov),('sensor_tick',.05)):
                    blueprint.set_attribute(key,str(value))
                transform=carla_module.Transform(carla_module.Location(*location),
                    carla_module.Rotation(*rotation))
                sensor=world.spawn_actor(blueprint,transform,attach_to=subject)
                self.sensors[name]=sensor
                sensor.listen(lambda image,camera_name=name:self._on_frame(camera_name,image))
        except BaseException:
            self.close()
            raise

    def _on_frame(self,name,image):
        with self.condition:
            if self.closed:return
            try:
                if image.frame in self.frames[name]:
                    raise ValueError('duplicate original source camera frame: '+name)
                if (image.width,image.height)!=SOURCE_CAMERAS[name][2]:
                    raise ValueError('original source camera dimensions changed: '+name)
                self.sinks[name].write(image)
                self.frames[name].add(image.frame)
            except BaseException as error:
                self.errors.append(error)
                raise
            finally:
                self.condition.notify_all()

    def wait_for_frame(self,frame,timeout_s=10):
        from time import monotonic
        deadline=monotonic()+timeout_s
        with self.condition:
            while True:
                if self.errors:raise ValueError('original source camera callback failed') from self.errors[0]
                if all(frame in frames for frames in self.frames.values()):return
                remaining=deadline-monotonic()
                if remaining<=0:
                    missing=[name for name,frames in self.frames.items() if frame not in frames]
                    raise ValueError('missing original source camera frame '+str(frame)+': '+', '.join(missing))
                self.condition.wait(remaining)

    def verify_frames(self,ordered_frames):
        if self.errors:raise ValueError('original source camera callback failed') from self.errors[0]
        if not ordered_frames or len(set(ordered_frames))!=len(ordered_frames):
            raise ValueError('invalid expected original frame inventory')
        expected=set(ordered_frames)
        for name,observed in self.frames.items():
            if observed!=expected:
                raise ValueError('incomplete original source camera stream: '+name)
        return {name:len(ordered_frames) for name in SOURCE_CAMERAS}

    def close(self):
        if not self.closed:
            self.closed=True
            for sensor in self.sensors.values():
                sensor.stop();sensor.destroy()


def capture_native_ticks(output, world, scene, case, cameras, traffic_light_state,
                         drive, *, frames=160, pipeline=None):
    """Capture one exact case from post-tick Native sources and four camera streams.

    ``drive`` commands the two vehicles before each tick.  This function retains
    original readbacks; a later saved-only finalizer must decide what they show.
    It never calls a legal evaluator or substitutes a synthetic camera frame.
    """
    import json
    from pathlib import Path
    if case.name not in CASES or CASES[case.name] != case or frames != 160:
        raise ValueError('one exact 160-frame heavy-vehicle case required')
    output = Path(output)
    if not output.is_dir():
        raise ValueError('fresh capture output directory required')
    names = ('signal_context.json', 'signal_state.jsonl',
             'participant_state.jsonl', 'video_frames.jsonl')
    if any((output/name).exists() for name in names):
        raise ValueError('retained original source exists; choose fresh output')
    collector = NativeSampleCollector(scene, case, scene['official_control_source'], cameras)
    selected = scene['selected']
    context = {'official_control_source':scene['official_control_source'],
               'official_device_status':'premise_unverified',
               'selected_direction':case.direction,
               'opendrive_id':selected['opendrive_id'],
               'junction_id':selected['junction_id'],
               'light_actor_id':int(selected['light'].id),
               'heavy_blueprint_id':scene['heavy_blueprint_id'],
               'lens_pixel_visibility':'requires_original_source_review',
               'legal_caution_judgment':None}
    (output/names[0]).write_text(json.dumps(context,sort_keys=True)+'\n')
    completed=[]
    with (output/names[1]).open('x') as signal, \
         (output/names[2]).open('x') as participants, \
         (output/names[3]).open('x') as frame_map, \
         NativeYellowController(selected['light'],traffic_light_state) as flash:
        for index in range(frames):
            commanded=flash.set_at(index*.05)
            drive(scene,case,index)
            frame=world.tick()
            snapshot=world.get_snapshot()
            if int(snapshot.frame)!=int(frame):
                raise ValueError('Native world snapshot differs from tick')
            row,mapping=collector.capture(snapshot,commanded)
            if pipeline is not None:
                original=pipeline.capture(frame,row['time_s'])
                if (original.get('frame'),original.get('time_s')) != (frame,row['time_s']):
                    raise ValueError('pipeline original frame/time differs')
            signal_row={'frame':frame,'time_s':row['time_s'],
                        'light_actor_id':row['signal_source']['light_actor_id'],
                        'opendrive_id':row['signal_source']['opendrive_id'],
                        'native_light_state':row['signal_source']['native_state'],
                        'yellow_commanded':row['yellow_lens_on'],
                        'lens_pixel_visible':None}
            party_row={'frame':frame,'time_s':row['time_s'],
                       'ego':{'actor_id':row['ego_source']['actor_id'],
                              'blueprint_id':row['ego_source']['blueprint_id'],
                              'vehicle_class':'heavy_vehicle',
                              'center_xy':row['ego_center_xy'],
                              'speed_mps':row['ego_speed_mps']},
                       'crossing':row['crossing_source']}
            for stream,value in ((signal,signal_row),(participants,party_row),
                                 (frame_map,mapping)):
                stream.write(json.dumps(value,allow_nan=False)+'\n')
            completed.append(frame)
    cameras.verify_frames(completed)
    return {'case':case.name,'frames':len(completed),
            'source_cameras':list(SOURCE_CAMERAS),
            'official_device_status':'premise_unverified',
            'physical_acceptance_claimed':False}


def steer_through_lane(world_map, actor, target_mps, carla_module, desired_yaw,
                       *, speed_kp=.22):
    """Command motion on a mapped through lane, including a crossing actor."""
    from math import atan2
    if actor is None or not actor.is_alive or target_mps <= 0:
        raise ValueError('controlled Native participant missing')
    pose=actor.get_transform()
    waypoint=world_map.get_waypoint(pose.location)
    if waypoint is None:
        raise ValueError('controlled Native participant left mapped road')
    options=[]
    for successor in waypoint.next(6.0):
        heading=radians(float(successor.transform.rotation.yaw)-float(desired_yaw))
        alignment=cos(heading)
        if alignment>=.75:
            options.append((alignment,successor))
    if not options:
        raise ValueError('no heading-aligned through-lane successor')
    options.sort(key=lambda pair:pair[0],reverse=True)
    target=options[0][1].transform.location
    heading=atan2(float(target.y)-float(pose.location.y),
                  float(target.x)-float(pose.location.x))
    yaw=radians(float(pose.rotation.yaw))
    steering_error=atan2(sin(heading-yaw),cos(heading-yaw))
    velocity=actor.get_velocity()
    speed=hypot(float(velocity.x),float(velocity.y))
    error=target_mps-speed
    actor.apply_control(carla_module.VehicleControl(
        throttle=min(.6,max(0.,speed_kp*error)),
        brake=min(.8,max(0.,-.3*error)),
        steer=min(.45,max(-.45,steering_error/.6))))


def run_native_case(output, config, *, host='127.0.0.1', port=2000):
    """Execute the first exact heavy case using a separately supplied CARLA host."""
    import json
    from pathlib import Path
    check_native_config(config)
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import seal_capture
    case_id=config['selected_case_id'];branch=config['case_branch']
    output=Path(output)
    client=carla.Client(host,int(port));client.set_timeout(30.)
    world=client.get_world();original=world.get_settings()
    scene=None;cameras=None;pipeline=None;sinks={};errors=[];completed=None
    try:
        settings=world.get_settings()
        settings.synchronous_mode=True;settings.fixed_delta_seconds=.05
        world.apply_settings(settings)
        scene=construct_native(world,CASES[branch],config['official_control_source'],
            config['heavy_blueprint_id'],config['crossing_blueprint_id'],
            before_m=config.get('approach_before_m',70.0))
        sinks={name:FFV1SourceSink(output,name) for name in SOURCE_CAMERAS}
        cameras=NativeSourceCameras(world,carla,scene['ego'],sinks)
        pipeline=PipelineCapture(client,scene['ego'],output,case_id,
                                 required_observations=config.get('required_atoms',[]))
        ego_yaw=scene['selected']['waypoint'].transform.rotation.yaw
        crossing_yaw=scene['crossing_route']['start'].rotation.yaw
        def drive(current,selected,index):
            steer_through_lane(world.get_map(),current['ego'],selected.target_mps,
                               carla,ego_yaw,speed_kp=config.get('speed_kp',.22))
            steer_through_lane(world.get_map(),current['crossing'],5.0,
                               carla,crossing_yaw,speed_kp=config.get('speed_kp',.22))
        completed=capture_native_ticks(output,world,scene,CASES[branch],cameras,
                                       carla.TrafficLightState,drive,pipeline=pipeline)
    except BaseException as error:
        errors.append(str(error))
        raise
    finally:
        if pipeline is not None:pipeline.close(confirmed=not errors)
        if cameras is not None:cameras.close()
        for sink in sinks.values():sink.close()
        if scene is not None:
            for actor in reversed(scene['owned']):actor.destroy()
        world.apply_settings(original)
        restored=(world.get_settings().synchronous_mode==original.synchronous_mode and
                  world.get_settings().fixed_delta_seconds==original.fixed_delta_seconds)
        if not restored:raise ValueError('Native world settings restoration failed')
    if completed is None:raise ValueError('Native case did not finish')
    (output/'acquisition-provenance.json').write_text(json.dumps({
        'provenance_kind':'native','diagnostic_fixture':False,
        'original_frames':completed['frames']})+'\n')
    seal_capture(output,frames=completed['frames'],restoration={'restored':restored},
                 errors=[],encoder_exit_codes={name:0 for name in SOURCE_CAMERAS},
                 context={'native_map_name':world.get_map().name,
                          'junction_id':scene['selected']['junction_id'],
                          'opendrive_id':scene['selected']['opendrive_id'],
                          'light_actor_id':int(scene['selected']['light'].id)})
    return completed


def check_native_config(config):
    branch=config.get('case_branch')
    if (branch!='east_cautious_proxy' or
        config.get('selected_case_id')!='heldout__C24753__NRS-484B-310-2__heavy_vehicle_driver__'+branch or
        (config.get('law_id'),config.get('cell_id'),config.get('actor')) !=
        ('NRS-484B-310-2','C24753','heavy_vehicle_driver') or
        config.get('rate_hz')!=20 or config.get('frames')!=160 or
        config.get('duration_s')!=8 or
        set(config.get('camera_names',[]))!=set(SOURCE_CAMERAS) or
        len(config.get('camera_names',[]))!=4 or
        config.get('target_speed_mps')!=CASES[branch].target_mps):
        raise ValueError('first exact C24753 construction/config mismatch')
    if not config.get('official_control_source'):
        raise ValueError('official control source premise missing')
    for field in ('heavy_blueprint_id','crossing_blueprint_id'):
        if not str(config.get(field,'')).startswith('vehicle.'):
            raise ValueError('explicit Native vehicle blueprint missing: '+field)
    if not 40<=config.get('approach_before_m',70.)<=90:
        raise ValueError('Native governed route distance outside engineering bounds')
    if not 0<config.get('speed_kp',.22)<=.5:
        raise ValueError('Native speed controller gain outside engineering bounds')
    return True


if __name__=='__main__':
    import argparse,json
    from pathlib import Path
    parser=argparse.ArgumentParser()
    parser.add_argument('--check',action='store_true')
    parser.add_argument('--output-dir',default='.')
    parser.add_argument('--host',default='127.0.0.1')
    parser.add_argument('--port',type=int,default=2000)
    args=parser.parse_args()
    config=json.loads((Path(args.output_dir)/'config.json').read_text())
    if args.check:check_native_config(config)
    else:run_native_case(args.output_dir,config,host=args.host,port=args.port)
