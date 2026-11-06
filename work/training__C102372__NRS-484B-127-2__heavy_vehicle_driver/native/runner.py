"""Proposed owned-endpoint CARLA capture for C102372; CPU preflight imports no CARLA."""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
import queue
import subprocess
import traceback

from engineering import CANDIDATES,parameters,speed_requests
from geometry import (FRAMES,LANE_Y_M,RATE_HZ,ROAD_LENGTH_M,
                      check as check_geometry,open_drive)

HERE=Path(__file__).resolve().parent
ASSIGNMENT='training__C102372__NRS-484B-127-2__heavy_vehicle_driver'
BLUEPRINT='vehicle.carlamotors.carlacola'


def plan_for(case,candidate):
    if case in ('conditions_steady','conditions_lead_brake'):
        from conditions_engineering import construction
        return construction(case,candidate)
    if case=='passing_hold':
        from passing_hold_engineering import construction
        return construction(candidate)
    if case=='passing_overtake':
        from passing_engineering import construction
        return construction(candidate)
    if case=='two_lane_exception':
        from two_lane_engineering import construction
        return construction(candidate)
    return parameters(case,candidate)


def authored_road(case):
    if case=='two_lane_exception':
        from two_lane_exception import two_lane_open_drive
        return two_lane_open_drive()
    return open_drive()


def cameras(candidate):
    plan=parameters('probe_1',candidate)['knobs']
    return [
        {'name':'overview','width':1920,'height':1080,
         'fov_deg':plan['overview_fov_deg'],'xyz_m':[-16.,0.,plan['overview_height_m']],
         'yaw_deg':0.,'pitch_deg':-12.},
        {'name':'ego_forward','width':1280,'height':720,'fov_deg':85.,
         'xyz_m':[3.,0.,3.5],'yaw_deg':0.,'pitch_deg':-2.},
        {'name':'lead_gap','width':1280,'height':720,'fov_deg':75.,
         'xyz_m':[-3.,0.,5.],'yaw_deg':0.,'pitch_deg':-5.},
        {'name':'crest_context','width':1280,'height':720,'fov_deg':100.,
         'xyz_m':[-8.,0.,6.],'yaw_deg':0.,'pitch_deg':-8.},
    ]


def check(config):
    if config.get('case_id')!=ASSIGNMENT+'__'+str(config.get('case_suffix')):
        raise ValueError('Exact C102372 case identity differs')
    if (config.get('law_id'),config.get('cell_id'),config.get('actor'))!=(
            'NRS-484B-127-2','C102372','heavy_vehicle_driver'):
        raise ValueError('Frozen C102372 identity differs')
    case=config['case_suffix'];candidate=config['candidate_id']
    if candidate not in CANDIDATES or config.get('knobs')!=plan_for(case,candidate)['knobs']:
        raise ValueError('Exact truck candidate knobs differ')
    if config.get('rate_hz')!=RATE_HZ or config.get('duration_s')!=FRAMES/RATE_HZ:
        raise ValueError('Full 480-frame Native window differs')
    expected=cameras(candidate)
    identities=[{key:camera[key] for key in ('name','width','height')} for camera in expected]
    if config.get('cameras')!=identities:
        raise ValueError('Declared four-camera profile differs')
    if len(config.get('recording_description',{}).get('channels',[]))<4:
        raise ValueError('Truck measurement channels absent')
    if case=='two_lane_exception':
        from two_lane_exception import geometry_check
        geometry=geometry_check()
    else:geometry=check_geometry()
    return {'passed':True,'authored_geometry':geometry,
            'case':case,'candidate':candidate,'camera_names':[c['name'] for c in expected],
            'native_imported':False,'physical_success_claimed':False}


def write_new(path,value):
    with Path(path).open('x') as stream:
        json.dump(value,stream,indent=2,allow_nan=False);stream.write('\n')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def body(actor):
    points={(round(v.x,5),round(v.y,5)) for v in
            actor.bounding_box.get_world_vertices(actor.get_transform())}
    if len(points)!=4:raise RuntimeError('Original truck footprint is not four corners')
    return [list(p) for p in sorted(points)]


def sample(actor,mapping,allowed_lanes=(-1,)):
    pose=actor.get_transform();waypoint=mapping.get_waypoint(pose.location,project_to_road=False)
    if waypoint is None or waypoint.road_id!=1 or waypoint.lane_id not in allowed_lanes:
        raise RuntimeError('Original truck leaves allowed passing road/lane')
    extent=actor.bounding_box.extent
    if 2*extent.y<80*.0254:
        raise RuntimeError('Original truck body below statutory 80-inch width')
    velocity=actor.get_velocity()
    vertices=actor.bounding_box.get_world_vertices(pose)
    return {'actor_id':actor.id,'blueprint_id':actor.type_id,
            'actor_class':'truck_or_combination','road_id':waypoint.road_id,
            'lane_id':waypoint.lane_id,'speed_mps':math.hypot(velocity.x,velocity.y),
            'center_xy_m':[pose.location.x,pose.location.y],
            'body_xy_m':body(actor),'body_width_m':2*extent.y,
            'body_vertices_m':[[v.x,v.y,v.z] for v in vertices]}


def execute(config,output,host,port):
    import carla
    import numpy as np
    from pipeline_capture import PipelineCapture
    from scenario_pipeline.worker_exchange.world_restore import snapshot,restore
    from measure_gap import measure as measure_single_lane

    check(config)
    output=Path(output).resolve()
    if not output.is_dir() or not (output/'config.json').is_file() or (output/'road.xodr').exists():
        raise ValueError('Fresh exact materialization required; acquisition owns road.xodr')
    client=carla.Client(host,int(port));client.set_timeout(180)
    old=client.get_world();saved=snapshot(client)
    if saved['settings'].synchronous_mode or any(a.type_id.startswith((
            'vehicle.','walker.','sensor.','controller.')) for a in old.get_actors()):
        raise RuntimeError('Exclusive idle asynchronous Native world required')
    owned=[];encoders={};encoder_logs={};queues={};channels={};overview_sensor=None
    capture=None;changed=False;error=None;restored=None;count=0
    try:
        world=client.generate_opendrive_world(authored_road(config['case_suffix']),carla.OpendriveGenerationParameters(
            vertex_distance=.25,max_road_length=50,wall_height=0,additional_width=0,
            smooth_junctions=False,enable_mesh_visibility=True,
            enable_pedestrian_navigation=False))
        changed=True
        settings=world.get_settings();settings.synchronous_mode=True
        settings.fixed_delta_seconds=1/RATE_HZ;settings.substepping=True
        settings.max_substep_delta_time=.01;settings.max_substeps=10
        world.apply_settings(settings);world.set_weather(carla.WeatherParameters.ClearNoon)
        mapping=world.get_map()
        road=mapping.to_opendrive()
        (output/'road.xodr').write_text(road)
        survey=[]
        for x in (50.,150.,250.,500.):
            waypoint=mapping.get_waypoint(carla.Location(x=x,y=LANE_Y_M,z=10),
                project_to_road=True,lane_type=carla.LaneType.Driving)
            if waypoint is None or (waypoint.road_id,waypoint.lane_id)!=(1,-1):
                raise RuntimeError('Native hill-crest road/lane survey differs')
            survey.append({'x_m':x,'road_id':waypoint.road_id,'lane_id':waypoint.lane_id,
                'surface_z_m':waypoint.transform.location.z})
        if survey[1]['surface_z_m']<survey[0]['surface_z_m']+3:
            raise RuntimeError('Native hill crest not realized')
        if config['case_suffix']=='two_lane_exception':
            adjacent=[]
            for x in (50.,150.,250.,500.):
                waypoint=mapping.get_waypoint(carla.Location(x=x,y=-6,z=10),
                    project_to_road=True,lane_type=carla.LaneType.Driving)
                if waypoint is None or (waypoint.road_id,waypoint.lane_id)!=(1,-2):
                    raise RuntimeError('Native second same-direction lane survey differs')
                adjacent.append({'x_m':x,'road_id':waypoint.road_id,
                                 'lane_id':waypoint.lane_id,
                                 'surface_z_m':waypoint.transform.location.z})
            survey+=adjacent
        library=world.get_blueprint_library();blueprint=library.find(BLUEPRINT)
        if blueprint.has_attribute('base_type') and blueprint.get_attribute('base_type').as_string()!='truck':
            raise RuntimeError('Selected Native blueprint is not truck base type')
        plan=plan_for(config['case_suffix'],config['candidate_id'])
        ego=world.spawn_actor(blueprint,carla.Transform(carla.Location(x=20,y=LANE_Y_M,z=1)))
        owned.append(ego)
        passing=config['case_suffix']=='passing_overtake'
        hold=config['case_suffix']=='passing_hold'
        passing_family=passing or hold
        conditions=config['case_suffix'] in ('conditions_steady','conditions_lead_brake')
        condition_event=config['case_suffix']=='conditions_lead_brake'
        target_gap=(38. if passing else plan['knobs']['target_gap_m'] if hold else
                    plan['knobs']['initial_horizontal_gap_m'] if conditions else plan['target_gap_m'])
        lead=world.spawn_actor(blueprint,carla.Transform(carla.Location(
            x=20+target_gap+15,y=LANE_Y_M,z=1)))
        owned.append(lead)
        ego_front=max(p[0] for p in body(ego));lead_rear=min(p[0] for p in body(lead))
        lead_pose=lead.get_transform();lead_pose.location.x+=target_gap-(lead_rear-ego_front)
        lead.set_transform(lead_pose)
        if not 0<min(p[0] for p in body(lead))-ego_front<ROAD_LENGTH_M:
            raise RuntimeError('Original truck bodies cannot realize positive lead gap')
        for actor in (ego,lead):
            if 2*actor.bounding_box.extent.y<80*.0254:
                raise RuntimeError('Native truck body below statutory width')
        obstacle=None
        if condition_event:
            obstacle=world.spawn_actor(blueprint,carla.Transform(carla.Location(
                x=plan['knobs']['obstacle_x_m'],y=LANE_Y_M,z=1)))
            owned.append(obstacle)
            obstacle.set_target_velocity(carla.Vector3D(x=0.,y=0.,z=0.))
        write_new(output/'native-construction-context.json',{
            'case_id':config['case_id'],'candidate_id':config['candidate_id'],
            'native_map_sha256':sha(output/'road.xodr'),'survey':survey,
            'ego_blueprint':ego.type_id,'lead_blueprint':lead.type_id,
            'requested_plan':plan,'conditions_permit_physically_verified':False,
            'legal_verdict_claimed':False})
        for spec in cameras(config['candidate_id']):
            bp=library.find('sensor.camera.rgb')
            for key,value in (('image_size_x',spec['width']),('image_size_y',spec['height']),
                              ('fov',spec['fov_deg']),('sensor_tick',0)):
                bp.set_attribute(key,str(value))
            x,y,z=spec['xyz_m']
            camera=world.spawn_actor(bp,carla.Transform(carla.Location(x=x,y=y,z=z),
                carla.Rotation(yaw=spec['yaw_deg'],pitch=spec['pitch_deg'])),attach_to=ego)
            owned.append(camera);queues[spec['name']]=queue.Queue()
            if spec['name']=='overview':
                overview_sensor=camera
                write_new(output/'camera_context.json',{'name':'overview',
                    'width':int(camera.attributes['image_size_x']),
                    'height':int(camera.attributes['image_size_y']),
                    'fov_deg':float(camera.attributes['fov']),
                    'source_kind':'original_native_camera_readback'})
            camera.listen(queues[spec['name']].put)
            encoder_logs[spec['name']]=(output/(spec['name']+'.encoder.log')).open('x')
            encoders[spec['name']]=subprocess.Popen(['ffmpeg','-nostdin','-hide_banner',
                '-loglevel','error','-n','-f','rawvideo','-pix_fmt','rgb24',
                '-s',f"{spec['width']}x{spec['height']}",'-r',str(RATE_HZ),'-i','pipe:0',
                '-an','-c:v','ffv1',str(output/(spec['name']+'.mkv'))],
                stdin=subprocess.PIPE,stderr=encoder_logs[spec['name']])
        capture=PipelineCapture(client,ego,output,config['case_id'],visibility=False,
            required_observations=config.get('required_atoms',[]))
        (output/'channels').mkdir()
        for item in config['recording_description']['channels']:
            channels[item['name']]=(output/'channels'/(item['name']+'.jsonl')).open('x')
        start=world.get_snapshot().timestamp.elapsed_seconds
        with (output/'native_samples.jsonl').open('x') as samples,\
             (output/'video_frames.jsonl').open('x') as joins:
            for index in range(FRAMES):
                gap=min(p[0] for p in body(lead))-max(p[0] for p in body(ego))
                if passing:
                    from passing_engineering import request
                    desired=request(config['candidate_id'],index)
                    ego_request=desired['ego_speed_mps']
                    lead_request=desired['lead_speed_mps']
                    lateral=max(-2.5,min(2.5,2.*(desired['ego_target_y_m']-
                                                ego.get_transform().location.y)))
                    ego.set_target_velocity(carla.Vector3D(x=ego_request,y=lateral))
                elif hold:
                    from passing_hold_engineering import speed_requests as hold_speed_requests
                    ego_request,lead_request=hold_speed_requests(config['candidate_id'],gap)
                    lateral=max(-1.,min(1.,plan['knobs']['lane_center_gain']*(-2.-
                                                ego.get_transform().location.y)))
                    ego.set_target_velocity(carla.Vector3D(x=ego_request,y=lateral))
                elif conditions:
                    from conditions_engineering import request
                    desired=request(config['case_suffix'],config['candidate_id'],index)
                    ego_request=desired['ego_speed_mps']
                    lead_request=desired['lead_speed_mps']
                    ego.set_target_velocity(carla.Vector3D(x=ego_request))
                else:
                    ego_request,lead_request=speed_requests(plan,gap)
                    ego.set_target_velocity(carla.Vector3D(x=ego_request))
                lead.set_target_velocity(carla.Vector3D(x=lead_request))
                frame=world.tick();elapsed=world.get_snapshot().timestamp.elapsed_seconds-start
                row={'native_frame':index,'carla_frame':frame,'time_s':index/RATE_HZ,
                    'elapsed_s':elapsed,
                    'ego':sample(ego,mapping,(-1,1) if passing else (-1,)),
                    'lead':sample(lead,mapping),
                    'requested_speed_mps':{'ego':ego_request,'lead':lead_request}}
                if conditions:
                    row['obstacle']=None
                    if obstacle is not None:
                        row['obstacle']=sample(obstacle,mapping)
                        row['obstacle']['actor_class']='stopped_vehicle'
                if passing_family:
                    present=[]
                    for actor in world.get_actors().filter('vehicle.*'):
                        if actor.id in (ego.id,lead.id):continue
                        waypoint=mapping.get_waypoint(actor.get_location(),project_to_road=False)
                        if waypoint is not None and (waypoint.road_id,waypoint.lane_id)==(1,1):
                            present.append({'id':actor.id,'blueprint_id':actor.type_id})
                    row['opposing_lane_actors']=present
                camera_pose=overview_sensor.get_transform()
                row['overview_camera_pose']={'xyz_m':[camera_pose.location.x,
                    camera_pose.location.y,camera_pose.location.z],
                    'yaw_deg':camera_pose.rotation.yaw,'pitch_deg':camera_pose.rotation.pitch}
                samples.write(json.dumps(row,allow_nan=False)+'\n')
                capture.capture(frame,elapsed,extra={'c102372_native':row})
                for name,stream in channels.items():
                    value={'ego_body_pose':row['ego'],'lead_body_pose':row['lead'],
                        'surface_gap_m':gap,'body_clearance_m':gap,
                        'camera_frame_join':{'native_frame':index,
                            'carla_frame':frame,'video_frame':index}}[name]
                    stream.write(json.dumps({'time_s':index/RATE_HZ,'value':value},
                        allow_nan=False)+'\n')
                for spec in cameras(config['candidate_id']):
                    image=queues[spec['name']].get(timeout=30)
                    while image.frame<frame:image=queues[spec['name']].get(timeout=30)
                    if image.frame!=frame:raise RuntimeError('Original camera/frame join differs')
                    rgb=np.frombuffer(image.raw_data,dtype=np.uint8).reshape(
                        spec['height'],spec['width'],4)[:,:,:3][:,:,::-1]
                    encoders[spec['name']].stdin.write(rgb.tobytes())
                joins.write(json.dumps({'video_frame':index,'native_frame':index,
                    'carla_frame':frame,'time_s':index/RATE_HZ})+'\n')
                count+=1
        write_new(output/'following_context.json',{
            'case_id':config['case_id'],'source_kind':'native_observation','road_id':1,'lane_id':-1,
            'same_direction_lane_count':2 if config['case_suffix']=='two_lane_exception' else 1,
            'overtaking':passing,'passing_attempt':passing,
            'opposing_traffic_source':'original_observation' if passing_family else None,
            'event':'lead_brake_with_obstacle' if condition_event else
                    'steady' if conditions else None,
            'conditions_permit_source':'synthetic_assertion',
            'conditions_permit':{'source':'original_weather_and_road_readback',
                'status':'requires_independent_physical_review'},
            'physical_conditions_verified':False})
    except BaseException as exc:
        error={'type':type(exc).__name__,'message':str(exc),'traceback':traceback.format_exc()}
    finally:
        for stream in channels.values():stream.close()
        if capture is not None:
            try:capture.close(confirmed=error is None)
            except BaseException as exc:error=error or {'capture_close_error':str(exc)}
        for name,encoder in encoders.items():
            try:
                encoder.stdin.close()
                if encoder.wait(timeout=180):raise RuntimeError('Lossless encoder failed: '+name)
            except BaseException as exc:error=error or {'encoder_error':str(exc)}
            encoder_logs[name].close()
        if error is None:
            try:
                sources=('native_samples.jsonl','following_context.json','road.xodr')
                write_new(output/'source-manifest.json',{
                    'format':'c102372-conditions-source-v1' if conditions else
                             'c102372-passing-source-v1' if passing_family else
                             'c102372-truck-follow-source-v1',
                    'sha256':{name:sha(output/name) for name in sources}})
                if conditions:
                    from conditions_qualifier import measure as measure_conditions
                    measured=measure_conditions(output)
                elif passing_family:
                    from passing_carveout import measure as measure_passing
                    measured=measure_passing(output)
                elif config['case_suffix']=='two_lane_exception':
                    from two_lane_exception import measure as measure_two_lane
                    measured=measure_two_lane(output)
                else:measured=measure_single_lane(output)
                write_new(output/'gap-measurement.json',measured)
                if conditions:
                    from conditions_trigger import extract
                    write_new(output/'fallback-metrics.json',extract(output,config['case_suffix']))
                elif passing_family:
                    if passing:from passing_trigger import extract
                    else:from passing_hold_trigger import extract
                    write_new(output/'fallback-metrics.json',extract(output))
                else:
                    from trigger_measure import SOURCES,extract
                    write_new(output/'trigger-source-manifest.json',{
                        'format':'c102372-truck-trigger-sources-v1',
                        'sha256':{name:sha(output/name) for name in SOURCES}})
                    write_new(output/'fallback-metrics.json',extract(output,config['case_suffix']))
            except BaseException as exc:error={'saved_gap_measurement_error':str(exc)}
        for actor in reversed(owned):
            try:
                if actor.type_id.startswith('sensor.') and actor.is_listening:actor.stop()
                actor.destroy()
            except BaseException as exc:error=error or {'owned_actor_cleanup_error':str(exc)}
        if changed:
            try:restored=restore(client,saved)
            except BaseException as exc:error=error or {'world_restore_error':str(exc)}
        write_new(output/'native-capture-report.json',{
            'case_id':config['case_id'],'candidate_id':config['candidate_id'],
            'frames':count,'expected_frames':FRAMES,'restoration':restored,
            'error':error,'accepted':False,'physical_conditions_verified':False})
    if error:raise RuntimeError('Native capture failed; see native-capture-report.json: '+str(error))
    return {'case_id':config['case_id'],'frames':count,'accepted':False}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true')
    parser.add_argument('--config',type=Path,default=HERE/'config.json')
    parser.add_argument('--output-dir',type=Path);parser.add_argument('--host')
    parser.add_argument('--port',type=int);args=parser.parse_args()
    config=json.loads(args.config.read_text())
    if args.check:print(json.dumps(check(config),sort_keys=True))
    else:
        if not args.output_dir or not args.host or not args.port:
            raise ValueError('Explicit materialized output and owned Native endpoint required')
        print(json.dumps(execute(config,args.output_dir,args.host,args.port),sort_keys=True))


if __name__=='__main__':main()
