"""Check exact C131364 requests on CPU or attempt connected Native capture."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import queue
import subprocess
import sys
import traceback
import xml.etree.ElementTree as ET

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def check(bundle):
    bundle=Path(bundle)
    config=json.loads((bundle/'config.json').read_text())
    source=json.loads((bundle/'assignment-source.json').read_text())
    plan=json.loads((bundle/'case-plan.json').read_text())
    witness=config.get('case_id','').removeprefix(config.get('assignment_id','')+'__')
    candidate=config.get('candidate_id')
    if (config.get('format')!='c131364-roundabout-lane-request-v1' or
        source.get('assignment_id')!=config.get('assignment_id') or
        plan.get('assignment_id')!=config.get('assignment_id') or
        config['case_id'] not in {row['case_id'] for row in plan['cases']} or
        witness not in ('witness_1','witness_2') or
        candidate not in ('primary','fallback1','fallback2','fallback3') or
        config.get('law_id')!='LVMC-11-43-010-C1' or
        config.get('cell_id')!='C131364' or
        config.get('rate_hz')!=20 or config.get('frames')!=240 or
        config.get('actual_left_exit_observed') is not False or
        config.get('exit_connector_verified') is not False or
        config.get('roundabout_verified') is not False or
        config.get('status')!='unselected_native_request'):
        raise ValueError('C131364 exact request scope differs')
    for key,name in {'assignment_sha256':'assignment-source.json',
                     'case_plan_sha256':'case-plan.json',
                     'road_sha256':'road.xodr',
                     'tracks_sha256':'requested-tracks.jsonl'}.items():
        if config.get(key)!=sha(bundle/name):
            raise ValueError('C131364 exact source hash differs')
    xml=ET.parse(bundle/'road.xodr').getroot()
    lanes={int(row.attrib['id']):row.attrib['type'] for row in xml.findall('.//lane')}
    if lanes!={0:'none',-1:'driving',-2:'driving'}:
        raise ValueError('C131364 two-lane map differs')
    lane,radius=(-1,23.75) if witness=='witness_1' else (-2,27.25)
    speed=6.5 if candidate=='fallback1' else 3 if candidate=='fallback3' else 8
    camera='elevated_overview_plus_four' if candidate=='fallback2' else 'four_views'
    if (config['requested_lane_id']!=lane or config['requested_lane_radius_m']!=radius or
        config['camera_policy']!=camera):
        raise ValueError('C131364 lane or camera policy differs')
    rows=[json.loads(line) for line in (bundle/'requested-tracks.jsonl').read_text().splitlines()]
    if len(rows)!=240:raise ValueError('C131364 frame count differs')
    for i,row in enumerate(rows):
        time_s=(i+1)/20
        travel=min(12,speed*time_s) if candidate=='fallback3' else speed*time_s
        theta=-math.pi/2+travel/radius
        if (row.get('frame')!=i or abs(row.get('time_s',-1)-time_s)>1e-6 or
            row.get('witness')!=witness or row.get('candidate_id')!=candidate or
            row.get('lane_id')!=lane or row.get('requested_radius_m')!=radius or
            abs(row.get('ego_x_m',1e9)-radius*math.cos(theta))>1e-5 or
            abs(row.get('ego_y_m',1e9)-radius*math.sin(theta))>1e-5 or
            abs(row.get('ego_heading_deg',1e9)-round(math.degrees(theta+math.pi/2)%360,6))>1e-5 or
            row.get('ego_speed_mps')!=(0 if candidate=='fallback3' and speed*time_s>12 else speed) or
            row.get('actual_exit_observed') is not False):
            raise ValueError(f'C131364 copied request row differs at {i}')
    connected=json.loads((bundle/'connected-config.json').read_text())
    if (connected.get('format')!='c131364-connected-left-exit-request-v1' or
        connected.get('assignment_id')!=config['assignment_id'] or
        connected.get('case_id')!=config['case_id'] or
        connected.get('candidate_id')!=candidate or
        connected.get('requested_lane_id')!=lane or
        connected.get('camera_policy')!=camera or
        connected.get('connected_exit_authored') is not True or
        connected.get('actual_exit_observed') is not False or
        connected.get('original_native_observed') is not False or
        connected.get('roundabout_verified') is not False or
        connected.get('status')!='unselected_native_request'):
        raise ValueError('C131364 connected request scope differs')
    for key,name in {'assignment_sha256':'assignment-source.json',
                     'case_plan_sha256':'case-plan.json',
                     'road_sha256':'connected-road.xodr',
                     'tracks_sha256':'connected-requested-tracks.jsonl'}.items():
        if connected.get(key)!=sha(bundle/name):
            raise ValueError('C131364 connected source hash differs')
    connected_roads={int(r.attrib['id']):r for r in ET.parse(bundle/'connected-road.xodr').getroot().findall('road')}
    if set(connected_roads)!={10,11,12}:
        raise ValueError('C131364 connected roads differ')
    for ident,previous,next_ in ((10,None,11),(11,10,12),(12,11,None)):
        road=connected_roads[ident]
        for relation,target in (('predecessor',previous),('successor',next_)):
            link=road.find('./link/'+relation)
            if (link is None)!=(target is None) or (target is not None and int(link.attrib['elementId'])!=target):
                raise ValueError('C131364 connected road link differs')
        if {int(x.attrib['id']):x.attrib['type'] for x in road.findall('./lanes/laneSection/right/lane')}!={-1:'driving',-2:'driving'}:
            raise ValueError('C131364 connected driving lanes differ')
    connected_rows=[json.loads(line) for line in (bundle/'connected-requested-tracks.jsonl').read_text().splitlines()]
    if len(connected_rows)!=240:raise ValueError('C131364 connected frame count differs')
    phases=set()
    for i,row in enumerate(connected_rows):
        time_s=(i+1)/20
        travel=min(12,speed*time_s) if candidate=='fallback3' else speed*time_s
        if travel<30:
            phase='entry';road_id=10;x=-30+travel;y=-radius;heading=0
        elif travel<30+radius*math.pi/2:
            phase='circulation';road_id=11;theta=-math.pi/2+(travel-30)/radius
            x=radius*math.cos(theta);y=radius*math.sin(theta);heading=math.degrees(theta+math.pi/2)
        else:
            phase='exit';road_id=12;x=radius;y=travel-30-radius*math.pi/2;heading=90
        if (row.get('frame')!=i or abs(row.get('time_s',-1)-time_s)>1e-6 or
            row.get('witness')!=witness or row.get('candidate_id')!=candidate or
            row.get('phase')!=phase or row.get('road_id')!=road_id or
            row.get('lane_id')!=lane or
            abs(row.get('ego_x_m',1e9)-x)>1e-5 or
            abs(row.get('ego_y_m',1e9)-y)>1e-5 or
            abs(row.get('ego_heading_deg',1e9)-heading)>1e-5 or
            row.get('actual_exit_observed') is not False or
            row.get('roundabout_verified') is not False):
            raise ValueError(f'C131364 connected request row differs at {i}')
        phases.add(phase)
    if phases!=({'entry'} if candidate=='fallback3' else {'entry','circulation','exit'}):
        raise ValueError('C131364 connected route phases differ')
    return {'format':'c131364-copied-runner-check-v1','case_id':config['case_id'],
            'candidate_id':candidate,'requested_frames':240,
            'connected_requested_frames':240,'connected_phases':sorted(phases),
            'carla_imported':False,'actual_exit_observed':False,
            'delivery_ready':False}

def repository():
    for parent in (Path(__file__).resolve().parent,*Path(__file__).resolve().parents):
        if (parent/'batch.json').is_file() and (parent/'runtime').is_dir():
            return parent
    override=os.environ.get('SCENARIO_REPO_ROOT')
    if override and (Path(override)/'runtime').is_dir():return Path(override).resolve()
    raise ValueError('Pinned runtime repository unavailable')

def write_new(path,value):
    with Path(path).open('x') as stream:
        json.dump(value,stream,indent=2,allow_nan=False)
        stream.write('\n')

def actor_pose(actor):
    pose=actor.get_transform();velocity=actor.get_velocity()
    body=actor.bounding_box.get_world_vertices(pose)
    return {'actor_id':actor.id,'blueprint':actor.type_id,
            'center_native_xyz_m':[pose.location.x,pose.location.y,pose.location.z],
            'yaw_deg':pose.rotation.yaw,
            'velocity_native_xyz_mps':[velocity.x,velocity.y,velocity.z],
            'speed_mps':math.sqrt(velocity.x**2+velocity.y**2+velocity.z**2),
            'body_native_xyz_m':[[v.x,v.y,v.z] for v in body]}

def control_to(carla,actor,target,speed_request):
    transform=actor.get_transform();velocity=actor.get_velocity()
    speed=math.sqrt(velocity.x**2+velocity.y**2+velocity.z**2)
    error=math.atan2(target['ego_y_m']-transform.location.y,
                     target['ego_x_m']-transform.location.x)-math.radians(transform.rotation.yaw)
    error=math.atan2(math.sin(error),math.cos(error))
    steer=max(-.75,min(.75,1.6*error))
    throttle=max(0,min(1,.22+.22*(speed_request-speed)))
    brake=max(0,min(1,.4*(speed-speed_request)))
    return carla.VehicleControl(throttle=throttle,brake=brake,steer=steer)

def execute(bundle,output,host,port):
    checked=check(bundle)
    bundle=Path(bundle).resolve();output=Path(output).resolve()
    if output.exists():raise ValueError('Native output must be a fresh directory')
    output.mkdir(parents=True)
    root=repository()
    sys.path.insert(0,str(root/'runtime/pipeline/scenario_pipeline'))
    sys.path.insert(0,str(root/'runtime/pipeline/python'))
    import carla
    import numpy as np
    from pipeline_capture import PipelineCapture
    from worker_exchange.world_restore import snapshot,restore
    requests=[json.loads(line) for line in (bundle/'connected-requested-tracks.jsonl').read_text().splitlines()]
    config=json.loads((bundle/'connected-config.json').read_text())
    client=carla.Client(host,int(port));client.set_timeout(180)
    saved=snapshot(client)
    old=client.get_world()
    if saved['settings'].synchronous_mode or any(
        actor.type_id.startswith(('vehicle.','walker.','sensor.')) for actor in old.get_actors()):
        raise RuntimeError('Exclusive idle asynchronous CARLA world required')
    owned=[];video={};logs={};camera_queues={}
    capture=None;changed=False;frames=0;restored=None;error=None
    try:
        world=client.generate_opendrive_world((bundle/'connected-road.xodr').read_text(),
            carla.OpendriveGenerationParameters(vertex_distance=.25,max_road_length=50,
                wall_height=0,additional_width=0,smooth_junctions=False,
                enable_mesh_visibility=True,enable_pedestrian_navigation=False))
        changed=True
        settings=world.get_settings();settings.synchronous_mode=True
        settings.fixed_delta_seconds=.05;settings.substepping=True
        settings.max_substep_delta_time=.01;settings.max_substeps=10
        world.apply_settings(settings)
        world.set_weather(carla.WeatherParameters.ClearNoon)
        mapping=world.get_map()
        native_lanes={}
        arc_lane_readback={}
        for lane_id,radius in ((-1,23.75),(-2,27.25)):
            point=carla.Location(x=radius/math.sqrt(2),y=-radius/math.sqrt(2),z=1)
            waypoint=mapping.get_waypoint(point,project_to_road=False,
                                          lane_type=carla.LaneType.Driving)
            arc_lane_readback[str(lane_id)]=None if waypoint is None else {
                'road_id':waypoint.road_id,'lane_id':waypoint.lane_id}
            if waypoint is None or waypoint.road_id!=11 or waypoint.lane_id!=lane_id:
                raise RuntimeError('Generated Native inner/outer arc lane readback differs')
        for phase in ('entry','circulation','exit'):
            phase_rows=[row for row in requests if row['phase']==phase]
            if not phase_rows:continue
            sample=phase_rows[len(phase_rows)//2]
            waypoint=mapping.get_waypoint(carla.Location(x=sample['ego_x_m'],y=sample['ego_y_m'],z=1),
                                          project_to_road=False,lane_type=carla.LaneType.Driving)
            native_lanes[phase]=None if waypoint is None else {
                'road_id':waypoint.road_id,'lane_id':waypoint.lane_id}
            if (waypoint is None or waypoint.road_id!=sample['road_id'] or
                waypoint.lane_id!=sample['lane_id']):
                raise RuntimeError('Generated Native road/lane readback differs at '+phase)
        first=requests[0]
        library=world.get_blueprint_library()
        blueprint=library.find('vehicle.tesla.model3')
        blueprint.set_attribute('role_name','c131364_ego')
        ego=world.try_spawn_actor(blueprint,carla.Transform(
            carla.Location(x=first['ego_x_m'],y=first['ego_y_m'],z=1.5),
            carla.Rotation(yaw=first['ego_heading_deg'])))
        if ego is None:raise RuntimeError('C131364 ego spawn failed')
        owned.append(ego)
        for _ in range(20):world.tick()
        write_new(output/'native-map-readback.json',{
            'road_sha256':sha(bundle/'connected-road.xodr'),
            'native_map_sha256':hashlib.sha256(mapping.to_opendrive().encode()).hexdigest(),
            'phase_lane_readback':native_lanes,'arc_lane_readback':arc_lane_readback,
            'ego_actor_id':ego.id,
            'physical_roundabout_verified':False,'lane_allocation_reviewed':False,
            'actual_left_exit_verified':False,'legal_verdict':None})
        cameras=(('overview',1280,720,85,(10,-15,35)),
                 ('forward',1280,720,90,(0,0,0)))
        for name,width,height,fov,location in cameras:
            bp=library.find('sensor.camera.rgb')
            for key,value in (('image_size_x',width),('image_size_y',height),
                              ('fov',fov),('sensor_tick',0)):
                bp.set_attribute(key,str(value))
            transform=(carla.Transform(carla.Location(x=location[0],y=location[1],z=location[2]),
                                       carla.Rotation(pitch=-55)) if name=='overview'
                       else carla.Transform(carla.Location(x=1,y=0,z=1.5)))
            sensor=world.spawn_actor(bp,transform,attach_to=None if name=='overview' else ego)
            owned.append(sensor);camera_queues[name]=queue.Queue()
            logs[name]=(output/(name+'.encoder.log')).open('x')
            video[name]=subprocess.Popen([
                'ffmpeg','-nostdin','-hide_banner','-loglevel','error','-n',
                '-f','rawvideo','-pix_fmt','rgb24','-s',f'{width}x{height}',
                '-r','20','-i','pipe:0','-an','-c:v','ffv1','-level','1',
                str(output/(name+'.mkv'))],stdin=subprocess.PIPE,stderr=logs[name])
            sensor.listen(camera_queues[name].put)
        capture=PipelineCapture(client,ego,output,config['case_id'],
                                visibility=False,required_observations=[])
        start=world.get_snapshot().timestamp.elapsed_seconds
        with (output/'native-raw-actors.jsonl').open('x') as observed, \
             (output/'video_frames.jsonl').open('x') as frame_map:
            for i,request in enumerate(requests):
                lookahead=requests[min(239,i+12)]
                ego.apply_control(control_to(carla,ego,lookahead,request['ego_speed_mps']))
                frame=world.tick()
                time_s=world.get_snapshot().timestamp.elapsed_seconds-start
                transform=ego.get_transform()
                waypoint=mapping.get_waypoint(transform.location,project_to_road=False,
                                              lane_type=carla.LaneType.Driving)
                row={'frame':i,'native_frame':frame,'time_s':time_s,
                     'source_kind':'original_native','requested_phase':request['phase'],
                     'requested_road_id':request['road_id'],
                     'requested_lane_id':request['lane_id'],
                     'observed_road_id':None if waypoint is None else waypoint.road_id,
                     'observed_lane_id':None if waypoint is None else waypoint.lane_id,
                     'ego':actor_pose(ego),'physical_roundabout_verified':False,
                     'actual_left_exit_verified':False,'legal_verdict':None}
                capture.capture(frame,time_s,extra={'c131364_connected_exit':row})
                observed.write(json.dumps(row,allow_nan=False)+'\n')
                for name,width,height,_,_ in cameras:
                    image=camera_queues[name].get(timeout=30)
                    while image.frame<frame:image=camera_queues[name].get(timeout=30)
                    if image.frame!=frame:raise RuntimeError('Camera/Native frame join differs')
                    rgb=np.frombuffer(image.raw_data,dtype=np.uint8).reshape(
                        height,width,4)[:,:,:3][:,:,::-1]
                    video[name].stdin.write(rgb.tobytes())
                frame_map.write(json.dumps({'video_frame':i,'native_frame':frame,
                                            'time_s':time_s},allow_nan=False)+'\n')
                frames+=1
    except BaseException as exc:
        error={'type':type(exc).__name__,'message':str(exc),'traceback':traceback.format_exc()}
    finally:
        if capture is not None:
            try:capture.close(confirmed=error is None)
            except BaseException as exc:error=error or {'capture_close_error':str(exc)}
        for name,process in video.items():
            try:
                process.stdin.close()
                if process.wait(timeout=180)!=0:raise RuntimeError('Lossless encoder failed: '+name)
            except BaseException as exc:error=error or {'encoder_error':str(exc)}
            logs[name].close()
        for actor in reversed(owned):
            try:
                if actor.type_id.startswith('sensor.') and actor.is_listening:actor.stop()
                actor.destroy()
            except BaseException as exc:error=error or {'cleanup_error':str(exc)}
        if changed:
            try:restored=restore(client,saved)
            except BaseException as exc:error=error or {'restore_error':str(exc)}
        write_new(output/'native-capture-report.json',{
            'case_id':checked['case_id'],'candidate_id':checked['candidate_id'],
            'connected_config_sha256':sha(bundle/'connected-config.json'),
            'requested_frames':240,'observed_frames':frames,
            'restoration':restored,'error':error,'accepted':False,
            'physical_roundabout_verified':False,'lane_allocation_reviewed':False,
            'actual_left_exit_verified':False,'legal_verdict':None,
            'delivery_ready':False})
    if error:raise RuntimeError('Native attempt failed; see native-capture-report.json')

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--check',action='store_true')
    parser.add_argument('--bundle',type=Path,required=True)
    parser.add_argument('--output-dir',type=Path)
    parser.add_argument('--host')
    parser.add_argument('--port',type=int)
    args=parser.parse_args()
    if args.check:print(json.dumps(check(args.bundle)))
    else:
        if not args.output_dir or not args.host or not args.port:
            parser.error('Native capture requires --output-dir, --host and --port')
        execute(args.bundle,args.output_dir,args.host,args.port)
