"""CARLA-lazy prospective parking capture with original source and actor readback."""
from __future__ import annotations
import hashlib
import json
import math
import queue
import shutil
import subprocess
from pathlib import Path
from parking_source import inside,sha

CAMERAS=(('overview',1920,1080),('approach',1280,720),('reference_corner',1280,720),('driver_reference',1280,720))


def write(path,payload):
    Path(path).write_text(json.dumps(payload,indent=2,allow_nan=False)+'\n')


def line_distance(position,vertices):
    x,y=position
    closest=float('inf')
    for a,b in zip(vertices,vertices[1:]):
        ax,ay=a;bx,by=b
        dx,dy=bx-ax,by-ay
        if dx*dx+dy*dy==0:raise ValueError('degenerate original boundary')
        t=max(0,min(1,((x-ax)*dx+(y-ay)*dy)/(dx*dx+dy*dy)))
        closest=min(closest,math.dist((x,y),(ax+t*dx,ay+t*dy)))
    return closest


def classify_observed_placement(position,records,site):
    half_width=records['device']['body_width_m']/2
    tolerance=site.get('engineering_contact_tolerance_m',.35)
    if tolerance<0 or tolerance>.5:raise ValueError('invalid engineering geometry tolerance')
    contact=half_width+tolerance
    if inside(position,records['sidewalk']['extent_polygon_xy']):
        if inside(position,records['rack']['rack_extent_polygon_xy']):return 'sidewalk_rack'
        if line_distance(position,records['building']['facade_line_xy'])<=contact:return 'sidewalk_building'
        if line_distance(position,records['curb']['curb_line_xy'])<=contact:return 'sidewalk_curb'
        return 'other_street_location'
    if inside(position,records['street']['roadway_polygon_xy']):
        if line_distance(position,records['curb']['curb_line_xy'])<=contact:return 'roadway_curb'
    return 'other_street_location'


class FourCameras:
    def __init__(self,world,carla,anchor,target,output,reference_pitch_deg=-40):
        self.sensors=[];self.queues={};self.encoders={};self.errors=[]
        try:
            poses=((-16,-14,27,-55),(-20,-5,11,-25),(3,-8,8,reference_pitch_deg),(0,0,2,0))
            for (name,width,height),(dx,dy,z,pitch) in zip(CAMERAS,poses):
                bp=world.get_blueprint_library().find('sensor.camera.rgb')
                for key,value in (('image_size_x',width),('image_size_y',height),('fov',90)):
                    bp.set_attribute(key,str(value))
                attached=name=='driver_reference'
                location=carla.Location(x=dx,y=dy,z=z) if attached else carla.Location(x=target[0]+dx,y=target[1]+dy,z=z)
                sensor=world.spawn_actor(bp,carla.Transform(location,carla.Rotation(pitch=pitch)),attach_to=anchor if attached else None)
                self.sensors.append(sensor)
                q=queue.Queue(maxsize=4);self.queues[name]=q
                def receive(image,bucket=q,label=name):
                    try:bucket.put_nowait(image)
                    except queue.Full:self.errors.append('camera queue overflow: '+label)
                sensor.listen(receive)
                self.encoders[name]=subprocess.Popen(['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-n','-f','rawvideo','-pixel_format','bgra','-video_size',f'{width}x{height}','-framerate','20','-i','pipe:0','-an','-c:v','ffv1','-pix_fmt','bgra',str(output/(name+'.mkv'))],stdin=subprocess.PIPE,stderr=subprocess.DEVNULL)
        except BaseException:
            self.close();raise
    def append(self,frame):
        if self.errors:raise RuntimeError('; '.join(self.errors))
        for name,_,_ in CAMERAS:
            image=self.queues[name].get(timeout=15)
            if image.frame!=frame:raise RuntimeError('original camera frame mismatch: '+name)
            self.encoders[name].stdin.write(image.raw_data)
    def close(self):
        errors=[]
        for sensor in reversed(self.sensors):
            try:sensor.stop()
            except BaseException as exc:errors.append(repr(exc))
        for name,process in self.encoders.items():
            try:
                if process.stdin and not process.stdin.closed:process.stdin.close()
                if process.wait(timeout=180):errors.append('ffmpeg failed: '+name)
            except BaseException as exc:errors.append(repr(exc))
        for sensor in reversed(self.sensors):
            try:sensor.destroy()
            except BaseException as exc:errors.append(repr(exc))
        self.sensors=[];self.encoders={}
        if errors:raise RuntimeError('; '.join(errors))


def run_native(cfg,site,records,site_path,output,host,port):
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap,seal_capture
    from worker_exchange.world_restore import snapshot,restore
    output=Path(output).resolve()
    if not output.is_dir():raise ValueError('Native attempt directory must already exist')
    client=carla.Client(host,port);client.set_timeout(30)
    original=snapshot(client)
    world=client.get_world();actors=[];cameras=capture=frame_map=None;phase='initializing';errors=[];restored=False;frames=0
    try:
        mapping=world.get_map()
        if mapping.name!=site['map_id'] or hashlib.sha256(mapping.to_opendrive().encode()).hexdigest()!=records['map']['opendrive_sha256']:
            raise ValueError('loaded OpenDRIVE differs from reviewed original map')
        settings=world.get_settings();settings.synchronous_mode=True;settings.fixed_delta_seconds=.05;world.apply_settings(settings)
        library=world.get_blueprint_library()
        target=site['target_xy']
        wp=mapping.get_waypoint(carla.Location(x=target[0],y=target[1],z=0))
        if not wp or wp.road_id!=site['road_id']:
            raise ValueError('Native street road identity differs from reviewed source')
        def spawn(bp_name,xy,yaw=0):
            bp=library.find(bp_name)
            actor=world.spawn_actor(bp,carla.Transform(carla.Location(x=xy[0],y=xy[1],z=wp.transform.location.z+.3),carla.Rotation(yaw=yaw)))
            actors.append(actor)
            if actor.type_id!=bp_name:raise ValueError('Native actor blueprint readback mismatch')
            return actor
        rack=spawn(site['rack_blueprint_id'],site['rack_xy'],site.get('rack_yaw_deg',0))
        device=spawn(site['device_blueprint_id'],target,site.get('device_yaw_deg',0))
        person=spawn(site['person_blueprint_id'],site['person_xy'],site.get('person_yaw_deg',0))
        pedestrian=spawn(site['pedestrian_blueprint_id'],site['pedestrian_start_xy'],site.get('pedestrian_yaw_deg',0))
        walker_controller=world.spawn_actor(library.find('controller.ai.walker'),carla.Transform(),attach_to=pedestrian)
        actors.append(walker_controller)
        walker_controller.start()
        walker_controller.set_max_speed(site.get('pedestrian_speed_mps',1.2))
        walker_controller.go_to_location(carla.Location(x=site['pedestrian_end_xy'][0],y=site['pedestrian_end_xy'][1],z=wp.transform.location.z))
        anchor=spawn(site['camera_anchor_blueprint_id'],site['camera_anchor_xy'],site.get('camera_anchor_yaw_deg',0))
        source_dir=output/'reviewed-site';source_dir.mkdir(exist_ok=False)
        shutil.copy2(site_path,source_dir/'site.json')
        for ref in site['sources'].values():
            src=(Path(site_path).parent/ref['path']).resolve();dst=source_dir/ref['path'];dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst)
        write(output/'acquisition-provenance.json',{'provenance_kind':'native','diagnostic_fixture':False,'method':'original source-gated parking episode with four synchronized cameras'})
        cameras=FourCameras(world,carla,anchor,target,output,cfg['engineering_camera_pitch_deg'])
        capture=PipelineCapture(client,anchor,output,cfg['selected_case_id'])
        frame_map=FrameMap(output/'video_frames.jsonl')
        phase='capturing'
        start_time=None
        with (output/'parking-events.jsonl').open('x',buffering=1) as event_file,(output/'pedestrian-tracks.jsonl').open('x',buffering=1) as track_file:
            for index in range(round(cfg['duration_s']*cfg['rate_hz'])):
                frame=world.tick();snap=world.get_snapshot()
                if snap.frame!=frame:raise RuntimeError('Native world frame mismatch')
                time_s=snap.timestamp.elapsed_seconds
                if start_time is None:start_time=time_s
                capture.capture(frame,time_s);cameras.append(frame);frame_map.append(frame,time_s)
                d=device.get_transform().location;p=pedestrian.get_transform().location
                position=[d.x,d.y];person_position=person.get_transform().location
                if math.dist((d.x,d.y),target)>site.get('engineering_position_tolerance_m',.4):
                    raise RuntimeError('parked device drifted from reviewed target')
                relation=classify_observed_placement(position,records,site)
                parked=(index>=cfg.get('parking_observation_start_frame',20))
                event={'frame':frame,'time_s':time_s,'device_xy':position,'person_xy':[person_position.x,person_position.y],
                       'person_id':records['person']['responsible_person_identity'],'device_id':records['device']['physical_identity'],
                       'device_actor_id':device.id,'rack_actor_id':rack.id,'parked':parked,'placement_relation':relation,
                       'rack_support_contact':relation=='sidewalk_rack' and records['rack']['supports_device'] is True,
                       'requested_placement':site['requested']['placement']}
                passage='passing' if math.dist((p.x,p.y),target)<site.get('pedestrian_passing_radius_m',4) else 'absent'
                track={'frame':frame,'time_s':time_s,'pedestrian_xy':[p.x,p.y],
                       'pedestrian_actor_id':pedestrian.id,'passage_status':passage}
                event_file.write(json.dumps(event,allow_nan=False)+'\n');track_file.write(json.dumps(track,allow_nan=False)+'\n')
                frames+=1
        phase='closing'
        capture.close();capture=None;frame_map.close();frame_map=None;cameras.close();cameras=None
        names=['trace.jsonl','video_frames.jsonl','parking-events.jsonl','pedestrian-tracks.jsonl','reviewed-site/site.json',
               *['reviewed-site/'+ref['path'] for ref in site['sources'].values()],*[name+'.mkv' for name,_,_ in CAMERAS]]
        write(output/'acquisition.json',{name:{'kind':'original_native','sha256':sha(output/name)} for name in names})
        phase='sealed'
    except BaseException as exc:
        errors.append(repr(exc));raise
    finally:
        for resource in (capture,frame_map,cameras):
            if resource:
                try:resource.close()
                except BaseException as exc:errors.append(repr(exc))
        for actor in reversed(actors):
            try:
                if getattr(actor,'type_id','')=='controller.ai.walker':actor.stop()
                actor.destroy()
            except BaseException as exc:errors.append(repr(exc))
        try:restored=restore(client,original)['restored']
        except BaseException as exc:errors.append(repr(exc))
        if phase=='sealed' and not errors and restored:
            seal_capture(output,frames=frames,restoration={'restored':True,'settings_readback':'original world snapshot restored'},errors=[],encoder_exit_codes={name:0 for name,_,_ in CAMERAS},context={'covered_device_parking':True,'source_review_pending':True})
        else:
            write(output/'native-run-status.json',{'phase':phase,'errors':errors,'settings_restored':restored})
            if phase=='sealed':raise RuntimeError('Native cleanup or restoration failed')
