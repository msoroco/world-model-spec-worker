"""Original CARLA acquisition for the two NRS 484B.217(2) turn cases.

This module is imported only for Native runs. It never starts or stops a server.
An authored coordinate is accepted only when the operator's map supports it.
"""
import hashlib
import json
import math
import os
import queue
import subprocess
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def clamp(value, low, high):
    return max(low, min(high, value))


def body_vertices(actor):
    return [[v.x, v.y, v.z] for v in actor.bounding_box.get_world_vertices(actor.get_transform())]


def body_gap(first, second):
    """Minimum separation of measured horizontal body envelopes, in meters."""
    a, b = body_vertices(first), body_vertices(second)
    dx = max(min(p[0] for p in b)-max(p[0] for p in a),
             min(p[0] for p in a)-max(p[0] for p in b), 0)
    dy = max(min(p[1] for p in b)-max(p[1] for p in a),
             min(p[1] for p in a)-max(p[1] for p in b), 0)
    return math.hypot(dx, dy)


def velocity_xy(actor):
    value=actor.get_velocity()
    return [float(value.x),float(value.y)]


def apply_traffic_policy(actors,policy,carla):
    from traffic_sweep import commanded_velocities
    commands=commanded_velocities(policy)
    for role,velocity in commands.items():
        actors[role].set_target_velocity(carla.Vector3D(x=velocity,y=0,z=0))
    return commands


def connected_turn(start, destination, stripe_y, *, limit=1200):
    """Require a forward waypoint path that crosses the stripe and reaches exit."""
    target=destination.transform.location
    queue=[(start,False)];seen=set();index=0
    while index<len(queue) and index<limit:
        waypoint,crossed=queue[index];index+=1
        location=waypoint.transform.location
        key=(getattr(waypoint,'road_id',None),getattr(waypoint,'lane_id',None),
             round(location.x,1),round(location.y,1),crossed)
        if key in seen:continue
        seen.add(key)
        if crossed and math.hypot(location.x-target.x,location.y-target.y)<=2.5:
            return True
        for following in waypoint.next(2.0):
            next_y=following.transform.location.y
            crossed_next=crossed or location.y<stripe_y<=next_y
            queue.append((following,crossed_next))
    return False


def check_map(mapping, scene, carla):
    """Reject an authored placement without its approach and exit geometry."""
    from runner import require_marking
    def location(x, y):
        return carla.Location(x=float(x), y=float(y), z=0)
    approach = require_marking(mapping, location(scene['crossing_x_m']-3,
                                                  scene['approach_lane_center_y_m']))
    if abs(approach.transform.location.y-scene['approach_lane_center_y_m']) > 1.25:
        raise ValueError('approach lane is too far from authored stripe')
    waypoints=[]
    for x, y in ((scene['start_x_m'], scene['approach_lane_center_y_m']),
                 (scene['crossing_x_m'], scene['opposing_lane_center_y_m']),
                 (scene['crossing_x_m'], scene['exit_y_m'])):
        wp = mapping.get_waypoint(location(x, y))
        if wp is None or math.hypot(wp.transform.location.x-x,
                                    wp.transform.location.y-y) > 1.25:
            raise ValueError('authored turn has no matching driving waypoint')
        waypoints.append(wp)
    if not connected_turn(waypoints[0],waypoints[-1],scene['stripe_y_m']):
        raise ValueError('no connected left-turn waypoint path crosses stripe and reaches exit')
    marking = approach.left_lane_marking
    samples=[]
    start=scene['start_x_m'];end=scene['crossing_x_m']-3
    count=math.ceil((end-start)/5)
    for index in range(count+1):
        requested=start+(end-start)*index/count
        wp=mapping.get_waypoint(location(requested,scene['approach_lane_center_y_m']))
        if wp is None:
            raise ValueError('marked approach has a missing waypoint sample')
        sample_marking=getattr(wp,'left_lane_marking',None)
        samples.append({'requested_x_m':requested,
                        'mapped_x_m':float(wp.transform.location.x),
                        'mapped_y_m':float(wp.transform.location.y),
                        'road_id':int(wp.road_id),'lane_id':int(wp.lane_id),
                        'marking_type':str(sample_marking.type) if sample_marking else None,
                        'marking_color':str(sample_marking.color) if sample_marking else None})
    if not all(item['road_id']==approach.road_id and item['lane_id']==approach.lane_id
               and item['marking_type'] and 'solid' in item['marking_type'].lower()
               for item in samples):
        raise ValueError('solid striping does not cover the sampled approach')
    return {'zone_kind': scene['zone_kind'], 'striping_source': 'native_map',
            'stripe_y_m': scene['stripe_y_m'],
            'crossing_x_m': scene['crossing_x_m'],
            'approach_road_id': approach.road_id,
            'approach_lane_id': approach.lane_id,
            'destination_road_id': waypoints[-1].road_id,
            'destination_lane_id': waypoints[-1].lane_id,
            'destination_xy_m': [float(waypoints[-1].transform.location.x),
                                 float(waypoints[-1].transform.location.y)],
            'marking_type': str(marking.type),
            'marking_color': str(marking.color),
            'marking_lane_change': str(marking.lane_change),
            'approach_marking_samples':samples,
            'sample_interval_max_m':5,
            'zone_extent_verified': False,
            'statutory_exceptions_verified': False,
            'limitation': 'A Native lane marking does not establish statutory zone extent or subsection 3/4 applicability.'}


def steering(ego, scene):
    """Pure pursuit toward the authored bend, with a bounded control output."""
    transform = ego.get_transform()
    x, y = transform.location.x, transform.location.y
    target = (scene['crossing_x_m']+2, scene['approach_lane_center_y_m']) if x < -4 else (scene['crossing_x_m'], scene['exit_y_m'])
    desired = math.degrees(math.atan2(target[1]-y, target[0]-x))
    error = (desired-transform.rotation.yaw+180) % 360-180
    return clamp(error/35, -0.7, 0.7)


class CameraBank:
    """Four original frame streams; every tick consumes matching camera IDs."""
    SPECS = (('overview',1920,1080,(0,0,45,-90)),
             ('approach',1280,720,(-15,-12,12,-25)),
             ('reference_corner',1280,720,(4,4,12,-45)),
             ('driver_reference',1280,720,(0,0,2,0)))

    def __init__(self, world, ego, output, carla):
        self.sensors=[]; self.encoders={}; self.queues={}; self.errors=[]
        try:self._start(world,ego,output,carla)
        except BaseException:
            try:self.close()
            except BaseException:pass
            raise

    def _start(self, world, ego, output, carla):
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
            def receive(image, q=frames, label=name):
                try:q.put_nowait(image)
                except queue.Full:self.errors.append('camera queue overflow: '+label)
            sensor.listen(receive)
            command=['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-n',
                     '-f','rawvideo','-pixel_format','bgra','-video_size',f'{width}x{height}',
                     '-framerate','20','-i','pipe:0','-an','-c:v','ffv1',
                     '-pix_fmt','bgra',str(output/(name+'.mkv'))]
            self.encoders[name]=subprocess.Popen(command,stdin=subprocess.PIPE,stderr=subprocess.DEVNULL)

    def append(self, frame):
        if self.errors:raise RuntimeError('; '.join(self.errors))
        for name,_,_,_ in self.SPECS:
            image=self.queues[name].get(timeout=15)
            if image.frame != frame:
                raise RuntimeError(f'{name} camera frame {image.frame} differs from world frame {frame}')
            self.encoders[name].stdin.write(image.raw_data)

    def close(self):
        for sensor in reversed(self.sensors):
            sensor.stop()
        for name,process in self.encoders.items():
            if process.stdin and not process.stdin.closed:process.stdin.close()
            if process.wait(timeout=180) != 0:
                raise RuntimeError('camera encoder failed: '+name)
        for sensor in reversed(self.sensors):sensor.destroy()


def run_native(scene, output, host, port):
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, write_result, seal_capture
    from worker_exchange.world_restore import fields, equal
    from runner import spawn_scene
    from traffic_sweep import select as select_traffic

    output=Path(output).resolve()
    if not output.is_dir():raise ValueError('Native attempt directory must already exist')
    scene,traffic_policy,_=select_traffic(
        scene,os.environ.get('C109755_TRAFFIC_SWEEP_ID','baseline'))
    write(output/'traffic-policy.json',traffic_policy)
    write(output/'acquisition-provenance.json',{'provenance_kind':'native','diagnostic_fixture':False,
          'method':'original CARLA live run; no replay or synthetic evidence',
          'traffic_sweep_variant_id':traffic_policy['variant_id'],
          'traffic_policy_sha256':sha(output/'traffic-policy.json')})
    client=carla.Client(host,port);client.set_timeout(30)
    world=client.get_world();original_settings=world.get_settings()
    actors={}; cameras=None; capture=None; frame_map=None
    phase='initializing'; error=None; restored=False
    try:
        zone=check_map(world.get_map(),scene,carla)
        zone['traffic_sweep_variant_id']=traffic_policy['variant_id']
        zone['traffic_policy_sha256']=sha(output/'traffic-policy.json')
        zone_packet=os.environ.get('ZONE_REVIEW_PACKET')
        if zone_packet:
            from zone_source import copy_review
            zone.update(copy_review(zone_packet,zone,output))
        settings=world.get_settings();settings.synchronous_mode=True;settings.fixed_delta_seconds=.05
        world.apply_settings(settings)
        def transform(x,y,_,yaw):
            wp=world.get_map().get_waypoint(carla.Location(x=x,y=y,z=0))
            return carla.Transform(carla.Location(x=x,y=y,z=wp.transform.location.z+.5),
                                   carla.Rotation(yaw=yaw))
        actors=spawn_scene(world,scene,transform)
        ego=actors['ego']
        cameras=CameraBank(world,ego,output,carla)
        write(output/'zone-context.json',zone)
        capture=PipelineCapture(client,ego,output,scene['case_id'])
        frame_map=FrameMap(output/'video_frames.jsonl')
        phase='capturing'
        rows=[];count=round(scene['duration_s']*20)
        with (output/'turn-history.jsonl').open('x',buffering=1) as history:
            for index in range(count):
                position=ego.get_location();turn=position.x >= scene['crossing_x_m']-4
                signal=bool(scene['signal_enabled'] and position.x>=scene['signal_start_x_m'])
                ego.set_light_state(carla.VehicleLightState.LeftBlinker if signal else carla.VehicleLightState.NONE)
                ego.apply_control(carla.VehicleControl(throttle=.3 if position.y<scene['exit_y_m']-2 else 0,
                    steer=steering(ego,scene),brake=0 if position.y<scene['exit_y_m']-2 else .5))
                traffic_commands=apply_traffic_policy(actors,traffic_policy,carla)
                frame=world.tick();snapshot=world.get_snapshot();time_s=snapshot.timestamp.elapsed_seconds
                if snapshot.frame!=frame:raise RuntimeError('world tick identity differs')
                trace=capture.capture(frame,time_s)
                cameras.append(frame)
                frame_map.append(frame,time_s)
                row={'frame':frame,'time_s':time_s,
                     'ego_center_x_m':trace['position_m'][0],
                     'ego_center_y_m':trace['position_m'][1],
                     'ego_body_vertices_m':body_vertices(ego),
                     'left_signal':bool(ego.get_light_state() & carla.VehicleLightState.LeftBlinker),
                     'oncoming_body_gap_m':body_gap(ego,actors['oncoming']),
                     'following_body_gap_m':body_gap(ego,actors['following']),
                     'oncoming_body_vertices_m':body_vertices(actors['oncoming']),
                     'following_body_vertices_m':body_vertices(actors['following']),
                     'oncoming_velocity_xy_mps':velocity_xy(actors['oncoming']),
                     'following_velocity_xy_mps':velocity_xy(actors['following'])}
                row['traffic_command_velocity_x_mps']=traffic_commands
                history.write(json.dumps(row,allow_nan=False)+'\n');rows.append(row)
        phase='closing'
        capture.close();capture=None
        frame_map.close();frame_map=None
        cameras.close();cameras=None
        source_names=['trace.jsonl','video_frames.jsonl','turn-history.jsonl','zone-context.json',
                      'traffic-policy.json','road.xodr','carla_recorder.log',
                      *[name+'.mkv' for name,*_ in CameraBank.SPECS]]
        if zone_packet:
            source_names.extend(('zone-review-source.json','zone-authority-source.txt'))
        write(output/'acquisition.json',{name:{'kind':'original_native','sha256':sha(output/name)} for name in source_names})
        crossed=any(a['ego_center_y_m']<scene['stripe_y_m']<=b['ego_center_y_m'] for a,b in zip(rows,rows[1:]))
        completed=crossed and rows[-1]['ego_center_y_m']>=scene['exit_y_m']-2
        checks=[{'target':'observed stripe crossing','requested':True,'measured':crossed,
                 'method':'original turn-history body center samples','tolerance':0,
                 'matched':crossed,'physical_cause_confirmed':False,
                 'cause_evidence':'Native map marking and original body history; statutory extent pending'}]
        reviewed=zone['zone_extent_verified'] and zone['statutory_exceptions_verified']
        write_result(output,{'case_id':scene['case_id'],'measured_values':{'crossed_stripe':crossed},
            'target_checks':checks,'setup_confirmed':reviewed,'behavior_attempted':crossed,
            'maneuver_completed':completed,'termination_reason':'planned_duration',
            'physical_failure_flags':([] if completed else ['turn_not_observed_complete']),
            'trace_reference':'trace.jsonl','video_references':[name+'.mkv' for name,*_ in CameraBank.SPECS],
            'video_frame_map_reference':'video_frames.jsonl',
            'recording_description':{'summary':'Original left-turn crossing attempt with source-bound zone review when supplied; safety and impediment unresolved'},
            'recording_evidence':{'acquisition':'acquisition.json'},
            'realized_observables':{'frame_count':len(rows),'crossed_stripe':crossed,
                                    'zone_extent_verified':zone['zone_extent_verified'],
                                    'destination_kind':zone.get('destination_kind')}})
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
                encoder_exit_codes={name:0 for name,*_ in CameraBank.SPECS},context={'zone':zone})
        else:
            write(output/'native-run-status.json',{'phase':phase,'errors':[v for v in [error,*cleanup] if v],
                                                   'settings_restored':restored})
            if phase=='sealed':raise RuntimeError('Native cleanup or settings restoration failed')
