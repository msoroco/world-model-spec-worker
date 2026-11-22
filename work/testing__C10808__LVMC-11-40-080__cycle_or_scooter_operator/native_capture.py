"""Lazy Native source capture for the two C10808 prohibited U-turn drafts.

The path controller moves the bicycle and operator as distinct actors. Physical
riding pose, sign authorization, alley status and pedestrian duties require local
review after capture; no legal status is inferred here.
"""
import hashlib
import json
import math
import queue
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace

from native_samples import sample
from runner import path_points, spawn_scene, trajectory

CAMERAS = (('overview',1920,1080,(-12,0,35,-70)),
           ('approach',1280,720,(-10,-4,8,-20)),
           ('reference_corner',1280,720,(0,-6,10,-35)),
           ('driver_reference',1280,720,(0,0,2,0)))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')


def local_transform(carla, origin, x, y, z=0., yaw=0.):
    angle = math.radians(origin.rotation.yaw)
    location = carla.Location(
        x=origin.location.x+x*math.cos(angle)-y*math.sin(angle),
        y=origin.location.y+x*math.sin(angle)+y*math.cos(angle),
        z=origin.location.z+z)
    return carla.Transform(location,carla.Rotation(yaw=origin.rotation.yaw+yaw))


def discover_origin(native_map, scene, carla):
    """Require connected Driving support along each authored turn segment.

    Lane-center proximity is an engineering map check; it does not establish an
    alley classification, authorized sign or physical riding pose.
    """
    candidates = native_map.get_spawn_points()
    route = path_points(scene)
    anchors = route['mounted']+route['afoot']
    points = []
    for start,end in zip(anchors, anchors[1:]):
        steps = max(1,math.ceil(math.dist(start,end)))
        points.extend((start[0]+(end[0]-start[0])*i/steps,
                       start[1]+(end[1]-start[1])*i/steps)
                      for i in range(steps))
    points.append(anchors[-1])
    for origin in candidates:
        positions = [local_transform(carla,origin,*point).location for point in points]
        waypoints = [native_map.get_waypoint(position) for position in positions]
        if any(w is None for w in waypoints):
            continue
        roads = {w.road_id for w in waypoints}
        if len(roads) != 1:
            continue
        if any(str(w.lane_type).split('.')[-1] != 'Driving' for w in waypoints):
            continue
        if any(math.dist((position.x,position.y),
                         (waypoint.transform.location.x,waypoint.transform.location.y))
               > max(1.5,float(waypoint.lane_width)/2)
               for position,waypoint in zip(positions,waypoints)):
            continue
        return origin, {'road_id': next(iter(roads)),
                        'waypoint_count': len(waypoints),
                        'maximum_map_support_spacing_m': 1.0,
                        'map_source': native_map.name,
                        'alley_classification': 'unresolved_requires_local_review'}
    raise ValueError('Native map lacks connected turn geometry for authored alley path')


class Cameras:
    def __init__(self, world, operator, output, carla):
        self.sensors=[];self.encoders={};self.queues={};self.errors=[];self.closed=False
        try:
            for name,width,height,(x,y,z,pitch) in CAMERAS:
                blueprint=world.get_blueprint_library().find('sensor.camera.rgb')
                blueprint.set_attribute('image_size_x',str(width))
                blueprint.set_attribute('image_size_y',str(height))
                blueprint.set_attribute('fov','90')
                pose=carla.Transform(carla.Location(x=x,y=y,z=z),
                                     carla.Rotation(pitch=pitch))
                sensor=world.spawn_actor(blueprint,pose,attach_to=operator)
                if sensor is None:
                    raise ValueError('Native camera spawn failed: '+name)
                self.sensors.append(sensor)
                frames=queue.Queue(maxsize=4);self.queues[name]=frames
                def receive(image,destination=frames,label=name):
                    try:destination.put_nowait(image)
                    except queue.Full:self.errors.append('camera queue overflow: '+label)
                sensor.listen(receive)
                self.encoders[name]=subprocess.Popen(
                    ['ffmpeg','-nostdin','-hide_banner','-loglevel','error',
                     '-n','-f','rawvideo','-pixel_format','bgra',
                     '-video_size',f'{width}x{height}','-framerate','20',
                     '-i','pipe:0','-an','-c:v','ffv1','-pix_fmt','bgra',
                     str(output/(name+'.mkv'))],stdin=subprocess.PIPE,
                     stderr=subprocess.DEVNULL)
        except BaseException:
            self.close()
            raise

    def append(self,frame):
        if self.errors:raise RuntimeError('; '.join(self.errors))
        for name,*_ in CAMERAS:
            image=self.queues[name].get(timeout=15)
            if image.frame!=frame:raise ValueError('Native camera/frame mismatch: '+name)
            self.encoders[name].stdin.write(image.raw_data)

    def close(self):
        if self.closed:return
        self.closed=True;errors=[]
        for sensor in reversed(self.sensors):
            try:sensor.stop()
            except BaseException as error:errors.append(repr(error))
        for name,process in self.encoders.items():
            try:
                if process.stdin and not process.stdin.closed:process.stdin.close()
                if process.wait(timeout=180):errors.append('encoder failed: '+name)
            except BaseException as error:errors.append('encoder '+name+': '+repr(error))
        for sensor in reversed(self.sensors):
            try:sensor.destroy()
            except BaseException as error:errors.append(repr(error))
        if errors:raise RuntimeError('; '.join(errors))


class WalkerCaptureProxy:
    """Expose neutral vehicle-control fields to the pinned graph collector.

    The actual subject remains the Native walker. These fields describe neither
    propulsion nor a legal bicycle operation; scripted transforms are recorded
    separately in the original phase stream.
    """
    def __init__(self, actor):self.actor=actor
    def __getattr__(self,name):return getattr(self.actor,name)
    def get_control(self):
        return SimpleNamespace(throttle=0.,steer=0.,brake=1.,hand_brake=True,
                               reverse=False,manual_gear_shift=False,gear=0)


def run_native(scene, output, host, port, authorization_file):
    """Record actual CARLA sources only on a dedicated supplied server."""
    output=Path(output).resolve();authorization_file=Path(authorization_file).resolve()
    if not output.is_dir() or not authorization_file.is_file():
        raise ValueError('attempt directory and sign-authorization source required')
    for required in ('construction.json','runner.py'):
        if not (output/required).is_file():
            raise ValueError('Native attempt missing sealed construction source: '+required)
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture
    from worker_exchange.world_restore import fields, equal
    client=carla.Client(host,port);client.set_timeout(30)
    world=client.get_world();native_map=world.get_map()
    origin,map_context=discover_origin(native_map,scene,carla)
    original_settings=world.get_settings();original_weather=world.get_weather()
    actors={};cameras=frame_map=pipeline=None;errors=[];phase='initializing';restored=False
    rows=0
    try:
        settings=world.get_settings();settings.synchronous_mode=True
        settings.fixed_delta_seconds=1/20;world.apply_settings(settings)
        transform=lambda x,y,z,yaw:local_transform(carla,origin,x,y,z,yaw)
        actors=spawn_scene(world,scene,transform)
        shutil.copyfile(authorization_file,output/'sign-authorization-source')
        fixed_scene={key:value for key,value in scene.items()
                     if key not in ('case_id','dismount_enabled')}
        fixed_scene_sha256=hashlib.sha256(json.dumps(
            fixed_scene,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        camera_contract_sha256=hashlib.sha256(json.dumps(
            CAMERAS,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        write(output/'sign-inventory.json',{
            'message':scene['sign']['message'],'erected':True,
            'sign_actor_id':actors['sign'].id,
            'sign_blueprint':actors['sign'].type_id,
            'bicycle_blueprint':actors['bicycle'].type_id,
            'operator_blueprint':actors['operator'].type_id,
            'fixed_scene_sha256':fixed_scene_sha256,
            'camera_contract_sha256':camera_contract_sha256,
            'authorization_source_sha256':sha(output/'sign-authorization-source'),
            'authorization_status':'unresolved_requires_independent_review',
            'map_context':map_context})
        write(output/'acquisition-provenance.json',{
            'provenance_kind':'native','diagnostic_fixture':False,
            'method':'original CARLA live run; scripted actor path'})
        cameras=Cameras(world,actors['operator'],output,carla)
        frame_map=FrameMap(output/'video_frames.jsonl')
        pipeline=PipelineCapture(client,WalkerCaptureProxy(actors['operator']),
                                 output,scene['case_id'])
        start=world.get_snapshot().timestamp.elapsed_seconds
        phase='capturing'
        with (output/'phase-events.jsonl').open('x',buffering=1) as events:
            for index in range(round(scene.get('duration_s',30)*20)):
                requested=trajectory(scene,(index+1)/20)
                for name in ('operator','bicycle'):
                    x,y,yaw=requested[name]
                    actors[name].set_transform(transform(x,y,0,yaw))
                frame=world.tick();snapshot=world.get_snapshot()
                if frame!=snapshot.frame:raise RuntimeError('Native frame mismatch')
                elapsed=snapshot.timestamp.elapsed_seconds-start
                pipeline.capture(frame,elapsed,extra={
                    'control_provenance':'neutral walker control adapter; authored motion uses scripted actor transforms'})
                cameras.append(frame);frame_map.append(frame,elapsed)
                row=sample(actors,frame=frame,time_s=elapsed,
                           phase=requested['phase'])
                events.write(json.dumps(row,allow_nan=False)+'\n')
                rows+=1
        phase='closing'
        frame_map.close();frame_map=None
        pipeline.close();pipeline=None
        cameras.close();cameras=None
        capture_manifest=json.loads((output/'capture/manifest.json').read_text())
        if (capture_manifest.get('frames')!=rows or
                capture_manifest.get('extraction_confirmed') is not True):
            raise ValueError('Pinned Native graph/evidence capture incomplete')
        names=['phase-events.jsonl','sign-inventory.json',
               'sign-authorization-source','video_frames.jsonl','trace.jsonl',
               'road.xodr','carla_recorder.log',
               *[name+'.mkv' for name,*_ in CAMERAS]]
        names += [str(path.relative_to(output)) for path in
                  (output/'capture').rglob('*') if path.is_file()]
        write(output/'acquisition.json',{name:{'kind':'original_native',
            'sha256':sha(output/name)} for name in names})
        phase='sealed'
    except BaseException as error:
        errors.append(repr(error));raise
    finally:
        for resource in (frame_map,pipeline,cameras):
            if resource:
                try:
                    if resource is pipeline:resource.close(confirmed=False)
                    else:resource.close()
                except BaseException as error:errors.append(repr(error))
        for actor in reversed(list(actors.values())):
            try:actor.destroy()
            except BaseException as error:errors.append(repr(error))
        try:
            world.apply_settings(original_settings);world.set_weather(original_weather)
            restored=all(equal(fields(world.get_settings()).get(k),v)
                         for k,v in fields(original_settings).items())
        except BaseException as error:errors.append(repr(error))
        if phase=='sealed' and not errors and restored:
            seal_capture(output,frames=rows,
                restoration={'restored':True,
                             'settings_readback':'original settings restored'},
                errors=[],encoder_exit_codes={name:0 for name,*_ in CAMERAS},
                context={'sign_inventory':'sign-inventory.json',
                         'alley_context':map_context})
        else:
            write(output/'native-run-status.json',{
                'phase':phase,'errors':errors,'settings_restored':restored,
                'common_capture_integration':'attempted through pinned PipelineCapture'})
            if phase=='sealed':raise RuntimeError('Native cleanup/restoration failed')
