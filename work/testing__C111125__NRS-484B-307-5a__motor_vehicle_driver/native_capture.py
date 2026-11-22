"""Original CARLA capture for the straight-arrow cases.

CARLA's generic traffic-light state is retained as a source observation. It is
never promoted to a sole-arrow or lawful-presence fact without another source.
"""
import hashlib
import json
import os
import queue
import shutil
import subprocess
from pathlib import Path

from arrow_source import aspect as reviewed_aspect, bind_actor, load_binding


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def vertices(actor):
    return [[point.x, point.y, point.z] for point in
            actor.bounding_box.get_world_vertices(actor.get_transform())]


def signal_snapshot(lights, frame, bindings=None, slot=0):
    """Retain raw actor states; a generic Green state proves no arrow shape."""
    observed=[]
    for light in lights:
        transform=light.get_transform()
        observed.append({'actor_id':int(light.id),
                         'state':str(light.get_state()),
                         'blueprint_id':str(light.type_id),
                         'position_m':[transform.location.x,transform.location.y,transform.location.z],
                         'yaw_deg':transform.rotation.yaw})
    observed.sort(key=lambda item:item['actor_id'])
    if len({item['actor_id'] for item in observed})!=len(observed):
        raise ValueError('duplicate Native traffic-light actor ID')
    if bindings:
        bound=[]
        for binding in bindings:
            match=[light for light in lights if int(light.id)==binding['packet']['actor_id']]
            if len(match)!=1:raise ValueError('reviewed arrow actor absent or duplicated')
            bind_actor(binding,match[0])
            bound.append((int(match[0].id),binding,match[0]))
        bound.sort(key=lambda row:row[0])
        if type(slot) is not int or slot<0 or slot>=len(bound):
            raise ValueError('predeclared facing head slot lacks reviewed source')
        head_id,binding,actor=bound[slot]
        return {'frame':frame,'candidate_lights':observed,'facing_head_id':head_id,
                'aspect':reviewed_aspect(binding,actor,frame),
                'reviewed_candidate_head_ids':[row[0] for row in bound]}
    return {'frame':frame,'candidate_lights':observed,
            'facing_head_id':None,
            'aspect':{'source_verified':False,'source_ref':'original CARLA actor state only',
                      'head_id':None,'observed_frame':frame,
                      'illuminated_indications':[]},
            'limitation':'CARLA actor state and blueprint ID do not establish a sole straight arrow or facing head'}


def retain_reviewed_sources(source_dir, output):
    """Copy exact reviewed packets and original assets into the attempt."""
    if not source_dir:return [],[]
    source_dir=Path(source_dir)
    if not source_dir.is_dir():raise ValueError('arrow review source directory absent')
    packets=sorted(source_dir.glob('*.json'))
    if not packets:raise ValueError('arrow review source directory contains no packets')
    destination=Path(output)/'reviewed-arrow-sources'
    destination.mkdir()
    bindings=[];names=[]
    for index,packet_path in enumerate(packets):
        packet=json.loads(packet_path.read_text())
        filename=packet.get('asset_file')
        if not isinstance(filename,str) or Path(filename).name!=filename or filename in ('','.','..'):
            raise ValueError('reviewed arrow asset filename must be local basename')
        binding=load_binding(packet_path,source_dir/filename)
        packet_copy=destination/f'head-{index}.json'
        asset_copy=destination/f'head-{index}{Path(filename).suffix}'
        shutil.copy2(packet_path,packet_copy);shutil.copy2(source_dir/filename,asset_copy)
        if sha(packet_copy)!=binding['packet_sha256'] or sha(asset_copy)!=binding['asset_sha256']:
            raise ValueError('reviewed arrow source changed during retention')
        binding['packet_path']=packet_copy;binding['asset_path']=asset_copy
        bindings.append(binding)
        names.extend([str(packet_copy.relative_to(output)),str(asset_copy.relative_to(output))])
    if len({item['packet']['actor_id'] for item in bindings})!=len(bindings):
        raise ValueError('duplicate reviewed arrow actor ID')
    return bindings,names


def map_context(mapping, scene, carla):
    """Check the authored straight route against actual driving waypoints."""
    points=[]
    for x in (scene['approach_x_m'],scene['stop_line_x_m'],scene['exit_x_m']):
        waypoint=mapping.get_waypoint(carla.Location(x=x,y=0,z=0))
        if waypoint is None or abs(waypoint.transform.location.x-x)>1.5 or abs(waypoint.transform.location.y)>1.5:
            raise ValueError('authored straight route lacks matching Native driving waypoint')
        points.append(waypoint)
    if len({(point.road_id,point.lane_id) for point in points})!=1:
        raise ValueError('authored straight route changes road or lane')
    return {'source':'native_map','road_id':points[0].road_id,'lane_id':points[0].lane_id,
            'stop_line_x_m':scene['stop_line_x_m'],
            'intersection_bounds_m':scene['intersection_bounds_m'],
            'adjacent_crosswalk_bounds_m':scene['adjacent_crosswalk_bounds_m'],
            'facing_head_id':None,
            'geometry_limitation':'Authored region coordinates require Native map and visible asset review',
            'lawful_presence_source_verified':False}


def participant_inventory(world, ego):
    """Include all live vehicles and walkers, not only actors owned here."""
    candidates=[('vehicle',actor) for actor in world.get_actors().filter('vehicle.*')]
    candidates += [('pedestrian',actor) for actor in world.get_actors().filter('walker.pedestrian.*')]
    rows=[]
    for role,actor in candidates:
        if int(actor.id)==int(ego.id):continue
        rows.append({'id':int(actor.id),'role':role,'body_vertices_m':vertices(actor),
                     'lawfully_present':None,'lawful_presence_source':None})
    rows.sort(key=lambda item:item['id'])
    if len({item['id'] for item in rows})!=len(rows):
        raise ValueError('duplicate Native participant actor ID')
    return rows


class CameraBank:
    SPECS=(('overview',1920,1080,(0,0,45,-90)),
           ('approach',1280,720,(-15,-12,12,-25)),
           ('reference_corner',1280,720,(4,4,12,-45)),
           ('driver_reference',1280,720,(0,0,2,0)))

    def __init__(self,world,ego,output,carla):
        self.sensors=[];self.encoders={};self.queues={};self.errors=[]
        try:self._start(world,ego,output,carla)
        except BaseException:
            try:self.close()
            except BaseException:pass
            raise

    def _start(self,world,ego,output,carla):
        library=world.get_blueprint_library()
        for name,width,height,pose in self.SPECS:
            blueprint=library.find('sensor.camera.rgb')
            blueprint.set_attribute('image_size_x',str(width))
            blueprint.set_attribute('image_size_y',str(height))
            blueprint.set_attribute('fov','90')
            x,y,z,pitch=pose
            transform=carla.Transform(carla.Location(x=x,y=y,z=z),carla.Rotation(pitch=pitch))
            sensor=world.spawn_actor(blueprint,transform,attach_to=ego if name=='driver_reference' else None)
            self.sensors.append(sensor)
            frames=queue.Queue(maxsize=4);self.queues[name]=frames
            def receive(image,q=frames,label=name):
                try:q.put_nowait(image)
                except queue.Full:self.errors.append('camera queue overflow: '+label)
            sensor.listen(receive)
            command=['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-n',
                     '-f','rawvideo','-pixel_format','bgra','-video_size',f'{width}x{height}',
                     '-framerate','20','-i','pipe:0','-an','-c:v','ffv1','-pix_fmt','bgra',
                     str(output/(name+'.mkv'))]
            self.encoders[name]=subprocess.Popen(command,stdin=subprocess.PIPE,stderr=subprocess.DEVNULL)

    def append(self,frame):
        if self.errors:raise RuntimeError('; '.join(self.errors))
        for name,_,_,_ in self.SPECS:
            image=self.queues[name].get(timeout=15)
            if image.frame!=frame:raise RuntimeError(f'{name} camera frame differs from world frame')
            self.encoders[name].stdin.write(image.raw_data)

    def close(self):
        failures=[]
        for sensor in reversed(self.sensors):
            try:sensor.stop()
            except BaseException as exc:failures.append(repr(exc))
        for name,process in self.encoders.items():
            try:
                if process.stdin and not process.stdin.closed:process.stdin.close()
                if process.wait(timeout=180)!=0:failures.append('camera encoder failed: '+name)
            except BaseException as exc:failures.append(repr(exc))
        for sensor in reversed(self.sensors):
            try:sensor.destroy()
            except BaseException as exc:failures.append(repr(exc))
        if failures:raise RuntimeError('; '.join(failures))


def run_native(scene,output,host,port):
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap,physical_result,write_result,seal_capture
    from worker_exchange.world_restore import fields,equal
    from runner import apply_participant_motion,control_step,spawn_scene

    output=Path(output).resolve()
    if not output.is_dir():raise ValueError('Native attempt directory must already exist')
    bindings,reviewed_names=retain_reviewed_sources(os.environ.get('C111125_ARROW_SOURCE_DIR'),output)
    write(output/'acquisition-provenance.json',{'provenance_kind':'native','diagnostic_fixture':False,
          'method':'original CARLA live capture; reviewed arrow source required for arrow inference',
          'reviewed_arrow_sources':reviewed_names})
    client=carla.Client(host,port);client.set_timeout(30)
    world=client.get_world();original_settings=world.get_settings()
    actors={};cameras=None;capture=None;frame_map=None
    phase='initializing';error=None;restored=False;rows=[];verified_arrow_frames=[]
    move_commands=0;pending={'throttle':0.0,'brake':1.0,'steer':0.0}
    first_arrow_frame=None;exhibition_occupants=None
    try:
        context=map_context(world.get_map(),scene,carla)
        settings=world.get_settings();settings.synchronous_mode=True;settings.fixed_delta_seconds=.05
        world.apply_settings(settings)
        def transform(x,y,_,yaw):
            wp=world.get_map().get_waypoint(carla.Location(x=x,y=y,z=0))
            if wp is None:raise ValueError('Native spawn lacks map waypoint')
            return carla.Transform(carla.Location(x=x,y=y,z=wp.transform.location.z+.5),
                                   carla.Rotation(yaw=yaw))
        actors=spawn_scene(world,scene,transform)
        ego=actors['ego']
        lights=list(world.get_actors().filter('traffic.traffic_light*'))
        context['candidate_light_actor_ids']=sorted(int(light.id) for light in lights)
        if bindings:
            first=signal_snapshot(lights,0,bindings,scene.get('candidate_head_slot',0))
            context['facing_head_id']=first['facing_head_id']
            context['arrow_review_packet_sha256']=first['aspect']['packet_sha256']
            context['arrow_review_asset_sha256']=first['aspect']['asset_sha256']
        write(output/'intersection-context.json',context)
        cameras=CameraBank(world,ego,output,carla)
        capture=PipelineCapture(client,ego,output,scene['case_id'])
        frame_map=FrameMap(output/'video_frames.jsonl')
        phase='capturing'
        count=round(scene['duration_s']*scene['capture_rate_hz'])
        with (output/'signal-head-history.jsonl').open('x',buffering=1) as signals, \
             (output/'ego-body-history.jsonl').open('x',buffering=1) as bodies, \
             (output/'participant-history.jsonl').open('x',buffering=1) as participants, \
             (output/'controller-history.jsonl').open('x',buffering=1) as controller:
            for index in range(count):
                ego.apply_control(carla.VehicleControl(throttle=pending['throttle'],
                                                       brake=pending['brake'],steer=pending['steer']))
                apply_participant_motion(scene,actors,carla,index/scene['capture_rate_hz'])
                frame=world.tick();snapshot=world.get_snapshot()
                if snapshot.frame!=frame:raise RuntimeError('world tick identity differs')
                time_s=snapshot.timestamp.elapsed_seconds
                capture.capture(frame,time_s);cameras.append(frame);frame_map.append(frame,time_s)
                signal=signal_snapshot(lights,frame,bindings,scene.get('candidate_head_slot',0))
                if signal['aspect']['source_verified']:verified_arrow_frames.append(frame)
                signal.update(time_s=time_s)
                ego_row={'frame':frame,'time_s':time_s,'body_vertices_m':vertices(ego),
                         'heading_deg':ego.get_transform().rotation.yaw}
                people=participant_inventory(world,ego)
                people_row={'frame':frame,'time_s':time_s,'participants':people}
                decision=control_step(scene,signal,people,ego_row['body_vertices_m'],
                                      first_arrow_frame=first_arrow_frame,
                                      exhibition_occupants=exhibition_occupants)
                first_arrow_frame=decision['first_arrow_frame']
                exhibition_occupants=decision['exhibition_occupants']
                pending=decision['control']
                if pending['throttle']>0:move_commands+=1
                signals.write(json.dumps(signal,allow_nan=False)+'\n')
                bodies.write(json.dumps(ego_row,allow_nan=False)+'\n')
                participants.write(json.dumps(people_row,allow_nan=False)+'\n')
                controller.write(json.dumps({'frame':frame,'time_s':time_s,**decision},allow_nan=False)+'\n')
                rows.append(frame)
        phase='closing'
        capture.close();capture=None
        frame_map.close();frame_map=None
        cameras.close();cameras=None
        source_names=['trace.jsonl','video_frames.jsonl','signal-head-history.jsonl',
                      'ego-body-history.jsonl','participant-history.jsonl','controller-history.jsonl',
                      'intersection-context.json',
                      'road.xodr','carla_recorder.log',*[name+'.mkv' for name,*_ in CameraBank.SPECS],
                      *reviewed_names]
        write(output/'acquisition.json',{name:{'kind':'original_native','sha256':sha(output/name)} for name in source_names})
        planned=json.loads((output/'config.json').read_text())['case']['recording_description']
        result={'case_id':scene['case_id'],
          'measured_values':{'sole_arrow_verified':bool(verified_arrow_frames),
                             'verified_arrow_frames':verified_arrow_frames,
                             'lawful_presence_verified':False,
                             'straight_move_commands':move_commands},
          'target_checks':[{'target':'original straight-arrow source acquisition','requested':True,
                            'measured':bool(verified_arrow_frames),
                            'method':'reviewed asset inventory bound to original CARLA actor state',
                            'tolerance':0,'matched':bool(verified_arrow_frames),
                            'physical_cause_confirmed':False,
                            'cause_evidence':'reviewed source retained' if verified_arrow_frames else
                              'generic CARLA traffic light state does not identify arrow shape'}],
          'setup_confirmed':False,'behavior_attempted':False,'maneuver_completed':False,
          'termination_reason':'planned_duration_pending_independent_physical_review',
          'physical_failure_flags':
            (['sole_arrow_source_unverified'] if not verified_arrow_frames else [])+
            (['lawful_presence_source_unverified'] if scene['participant_occupancy_setup']=='lawfully_present' else []),
          'trace_reference':'trace.jsonl',
          'video_references':[name+'.mkv' for name,*_ in CameraBank.SPECS],
          'video_frame_map_reference':'video_frames.jsonl',
          'recording_description':planned,
          'recording_evidence':{'acquisition':'acquisition.json'},
          'realized_observables':{'frame_count':len(rows),'candidate_lights':len(lights),
                                  'reviewed_arrow_source_count':len(bindings),
                                  'straight_move_commands':move_commands}}
        write_result(output,physical_result(output,result))
        phase='sealed'
    except BaseException as exc:
        error=repr(exc)
        raise
    finally:
        cleanup=[]
        for resource in (capture,frame_map,cameras):
            if resource:
                try:resource.close()
                except BaseException as exc:cleanup.append(repr(exc))
        for actor in reversed(list(actors.values())):
            try:actor.destroy()
            except BaseException as exc:cleanup.append(repr(exc))
        try:
            world.apply_settings(original_settings)
            restored=all(equal(fields(world.get_settings()).get(key),value)
                         for key,value in fields(original_settings).items())
        except BaseException as exc:cleanup.append(repr(exc))
        if phase=='sealed' and not cleanup and restored:
            seal_capture(output,frames=len(rows),restoration={'restored':True,
                'settings_readback':'synchronous_mode and fixed_delta_seconds restored'},errors=[],
                encoder_exit_codes={name:0 for name,*_ in CameraBank.SPECS},
                context={'arrow':bool(verified_arrow_frames),'lawful_presence':False})
        else:
            write(output/'native-run-status.json',{'phase':phase,
                  'errors':[value for value in [error,*cleanup] if value],
                  'settings_restored':restored})
            if phase=='sealed':raise RuntimeError('Native cleanup or settings restoration failed')
