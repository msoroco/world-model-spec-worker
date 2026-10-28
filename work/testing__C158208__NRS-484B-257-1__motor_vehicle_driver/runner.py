"""Partition-03 native capability episodes; exact case is frozen in config.json.

Offline checks use only local files. Live execution connects only when an
operator supplies an existing CARLA endpoint. The shared PipelineCapture owns
original frame, state, actor, graph and recorder acquisition.
"""
import argparse
import json
import math
import queue
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def selected():
    cfg = json.loads((ROOT / 'config.json').read_text())
    case = cfg['case']
    assert cfg['selected_case_id'] == case['case_id']
    assert case['target_law_id'] == cfg['law_id']
    assert case['target_type'] != 'baseline'
    return cfg, case


def setting(case, key, default=None):
    return case['variable_assignments'].get(key, {}).get('value', default)


def path_for(cfg, case):
    mechanism = cfg['mechanism']
    if mechanism == 'yield':
        return [(-70 + i, -1.75) for i in range(130)]
    if mechanism == 'reverse':
        suffix = case['case_id'].rsplit('__', 1)[-1]
        target = {'outside_crosswalk_reverse': 24.0, 'over_crosswalk_reverse': 15.5,
                  'outside_intersection_reverse': 22.0, 'into_intersection_reverse': 0.0}[suffix]
        return [(35.0 - i * 0.5, -1.75) for i in range(int((35-target)*2)+1)]
    if mechanism == 'uturn':
        station = float(setting(case, 'maneuver_station_m'))
        approach = [(station - 35 + i * 0.5, -6.0) for i in range(71)]
        turn = [(station + 6*math.sin(math.pi*i/80), -6*math.cos(math.pi*i/80)) for i in range(1, 81)]
        exit_path = [(station - i * 0.5, 6.0) for i in range(1, 71)]
        return approach + turn + exit_path
    if mechanism == 'following':
        return [(100 + i, -6.0) for i in range(900)]
    raise ValueError('Unknown scenario mechanism')


def check():
    cfg, case = selected()
    root = ET.parse(ROOT / 'scene.xodr').getroot()
    assert root.tag == 'OpenDRIVE'
    roads = root.findall('road')
    assert roads and len({r.get('id') for r in roads}) == len(roads)
    assert all(float(r.get('length')) > 0 and r.find('planView/geometry') is not None for r in roads)
    path = path_for(cfg, case)
    assert len(path) > 20
    assert max(math.dist(a,b) for a,b in zip(path,path[1:])) < 1.1
    assert len(cfg['cameras']) == 4 and (cfg['cameras'][0]['width'],cfg['cameras'][0]['height']) == (1920,1080)
    assert all((c['width'],c['height']) == (1280,720) for c in cfg['cameras'][1:])
    required = {o['name'] for o in cfg['observations'] if o.get('mandatory',True)}
    assert required <= {c['name'] for c in case['recording_description']['channels']}
    if cfg['mechanism'] == 'yield':
        signs = root.findall('.//signals/signal')
        assert len(signs) == 1 and signs[0].get('type') == '205'
        assert not root.findall('.//objects/object')
    if cfg['mechanism'] == 'reverse':
        assert root.findall('.//objects/object[@type="crosswalk"]')
    if cfg['mechanism'] == 'uturn':
        assert len(roads) == 1 and len(roads[0].findall('elevationProfile/elevation')) >= 3
        assert 0 < float(setting(case,'maneuver_station_m')) < float(roads[0].get('length'))
    if cfg['mechanism'] == 'following':
        assert len(roads) == 1 and len(roads[0].findall('lanes/laneSection/right/lane[@type="driving"]')) == 1
        assert float(setting(case,'commanded_surface_gap')) > 100
    print(json.dumps({'offline_check':'passed','case_id':case['case_id'],'mechanism':cfg['mechanism'],
                      'path_points':len(path),'simulator_connected':False}))


def native_state(actor):
    transform = actor.get_transform()
    velocity = actor.get_velocity()
    control = actor.get_control()
    return {'actor_id':actor.id,'type_id':actor.type_id,
            'position_m':[transform.location.x,transform.location.y,transform.location.z],
            'heading_deg':transform.rotation.yaw,'speed_mps':velocity.length(),
            'body_vertices_m':[[v.x,v.y,v.z] for v in actor.bounding_box.get_world_vertices(transform)],
            'applied_control':{k:getattr(control,k) for k in ('throttle','brake','steer','reverse')}}


def visibility_profile(carla,world,ego):
    """Potential approaching-driver eyes toward actual ego body from both sides.

    A potential vehicle is sampled geometrically on native road waypoints;
    this does not assert a human driver's perception or a legal visibility
    predicate. Every first occluder and all body-ray outcomes are retained.
    """
    from carla_sgg.law_evidence import ray_evidence
    ego_pose=ego.get_transform()
    ego_center=ego_pose.location
    ego_body=ego.bounding_box.get_world_vertices(ego_pose)
    mapping=world.get_map()
    result={}
    for direction in (-1,1):
        side=[]
        for distance in range(20,231,5):
            x=ego_center.x+direction*distance
            y=6.0 if direction<0 else -6.0
            wp=mapping.get_waypoint(carla.Location(x=x,y=y,z=ego_center.z),project_to_road=True)
            if wp is None:
                side.append({'requested_distance_m':distance,'native_waypoint':None});continue
            base=wp.transform.location
            eye=carla.Location(x=base.x,y=base.y,z=base.z+1.5)
            samples=[]
            for target in list(ego_body)+[carla.Location(x=ego_center.x,y=ego_center.y,z=ego_center.z+2.4)]:
                ray=ray_evidence(world,ego,eye,target)
                samples.append({'target_m':[target.x,target.y,target.z],
                    'unoccluded':ray['clear'],
                    'first_occluder':ray['blockers'][0] if ray['blockers'] else None})
            side.append({'requested_distance_m':distance,'observer_eye_m':[eye.x,eye.y,eye.z],
                'native_waypoint':{'road_id':wp.road_id,
                'lane_id':wp.lane_id,'s_m':wp.s,'position_m':[base.x,base.y,base.z]},
                'body_samples':samples,'visible_sample_count':sum(s['unoccluded'] for s in samples)})
        result[str(direction)]=side
    return result


def actual_counterpart_visibility(carla,world,ego,other):
    from carla_sgg.law_evidence import ray_evidence
    eye=ego.get_transform().location+carla.Location(z=1.5)
    targets=other.bounding_box.get_world_vertices(other.get_transform())
    rays=[]
    for target in targets:
        ray=ray_evidence(world,other,eye,target)
        rays.append({'target_m':[target.x,target.y,target.z],
                     'unoccluded':ray['clear'],
                     'first_occluder':ray['blockers'][0] if ray['blockers'] else None})
    return {'observer_eye_m':[eye.x,eye.y,eye.z],
            'visible_body_samples':sum(r['unoccluded'] for r in rays),'rays':rays}


def command(carla, actor, path, index, desired_speed, reverse=False):
    state = native_state(actor)
    x,y = state['position_m'][:2]
    near = min(range(max(0,index-8),min(len(path),index+30)),
               key=lambda i:(path[i][0]-x)**2+(path[i][1]-y)**2)
    look = path[min(near+8,len(path)-1)]
    target_angle = math.atan2(look[1]-y,look[0]-x)
    heading = math.radians(state['heading_deg']) + (math.pi if reverse else 0)
    error = (target_angle-heading+math.pi)%(2*math.pi)-math.pi
    steer = max(-0.8,min(0.8,1.6*error)) * (-1 if reverse else 1)
    speed = state['speed_mps']
    throttle = max(0,min(0.55,0.28*(desired_speed-speed)))
    brake = max(0,min(0.7,0.35*(speed-desired_speed)))
    return carla.VehicleControl(throttle=throttle,brake=brake,steer=steer,reverse=reverse),near


def run(args):
    import carla  # lazy by design
    from pipeline_capture import PipelineCapture
    cfg, case = selected()
    out = Path(args.output_dir).resolve()
    out.mkdir(parents=True,exist_ok=True)
    if (out/'physical_samples.jsonl').exists():
        raise ValueError('Retain previous attempt and choose a fresh output directory')
    if not (out/'config.json').exists():
        (out/'config.json').write_text(json.dumps(cfg,indent=2)+'\n')
    (out/'context.json').write_text(json.dumps({'authored_test_context':cfg['authored_test_context']},indent=2)+'\n')
    client = carla.Client(args.host,args.port)
    client.set_timeout(120)
    previous = client.get_world()
    previous_map = previous.get_map().name
    previous_settings = previous.get_settings()
    previous_weather = previous.get_weather()
    world = None
    actors = []
    capture = None
    encoders = {}
    logs = {}
    channels = {}
    count = 0
    try:
        world = client.generate_opendrive_world((ROOT/'scene.xodr').read_text())
        ws = world.get_settings()
        ws.synchronous_mode = True
        ws.fixed_delta_seconds = 0.05
        world.apply_settings(ws)
        world.set_weather(carla.WeatherParameters.ClearNoon)
        path = path_for(cfg,case)
        mechanism = cfg['mechanism']
        bp = world.get_blueprint_library().find(cfg['vehicle_blueprint'])
        bp.set_attribute('role_name','ego')
        yaw = 0
        z = 0.5
        ego = world.spawn_actor(bp,carla.Transform(carla.Location(x=path[0][0],y=path[0][1],z=z),carla.Rotation(yaw=yaw)))
        actors.append(ego)
        others = []
        if mechanism in ('yield','following'):
            other_bp = world.get_blueprint_library().find(cfg.get('counterpart_blueprint',cfg['vehicle_blueprint']))
            other_bp.set_attribute('role_name','counterpart')
            if mechanism == 'yield':
                start_y=float(setting(case,'counterpart_start_y_m',12.0))
                pose = carla.Transform(carla.Location(x=1.75,y=start_y,z=.5),carla.Rotation(yaw=-90))
            else:
                target = float(setting(case,'commanded_surface_gap'))
                pose = carla.Transform(carla.Location(x=100+target+12,y=-6,z=.5))
            other = world.spawn_actor(other_bp,pose)
            actors.append(other)
            others.append(other)
        queues = {}
        for i,spec in enumerate(cfg['cameras']):
            camera_bp = world.get_blueprint_library().find('sensor.camera.rgb')
            camera_bp.set_attribute('image_size_x',str(spec['width']))
            camera_bp.set_attribute('image_size_y',str(spec['height']))
            camera_bp.set_attribute('sensor_tick','0')
            camera = world.spawn_actor(camera_bp,carla.Transform(carla.Location(x=spec['x'],y=spec.get('y',0),z=spec['z']),
                carla.Rotation(pitch=spec['pitch'])),attach_to=ego)
            actors.append(camera)
            name='view%d'%i
            queues[name]=queue.Queue()
            camera.listen(queues[name].put)
            logs[name]=(out/(name+'.encoder.log')).open('x')
            encoders[name]=subprocess.Popen(['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-n',
                '-f','rawvideo','-pix_fmt','bgra','-s','%dx%d'%(spec['width'],spec['height']),'-r','20','-i','pipe:0',
                '-an','-c:v','ffv1','-pix_fmt','bgr0','-level','1','-threads','2',str(out/(name+'.mkv'))],stdin=subprocess.PIPE,stderr=logs[name])
        for _ in range(5):
            world.tick()
        capture=PipelineCapture(client,ego,out,case['case_id'],required_observations=cfg['required_atoms'])
        evidence=(out/'capture/evidence.jsonl').open()
        (out/'channels').mkdir()
        channels={c['name']:(out/'channels'/(c['name']+'.jsonl')).open('x') for c in case['recording_description']['channels']}
        start=world.get_snapshot().timestamp.elapsed_seconds
        index=0
        hold_start=None
        with (out/'physical_samples.jsonl').open('x') as physical,(out/'video_frames.jsonl').open('x') as frame_map:
            for tick in range(cfg['max_ticks']):
                ego_state=native_state(ego)
                if mechanism=='yield':
                    other=others[0]
                    other_state=native_state(other)
                    # Counterpart enters and then occupies the junction; both
                    # paired attempts use the same counterpart controller.
                    moving_sweep=case['target_type']=='judgment_sweep'
                    if moving_sweep or other_state['position_m'][1]>1.5:
                        other.apply_control(carla.VehicleControl(throttle=.28,steer=0))
                    else:
                        other.apply_control(carla.VehicleControl(brake=1))
                    hold=float(setting(case,'yield_hold_s'))
                    if hold>0 and hold_start is None and ego_state['position_m'][0]>-20:
                        hold_start=tick*.05
                    desired=0 if hold_start is not None and tick*.05<hold_start+hold else 4.0
                elif mechanism=='following':
                    other=others[0]
                    other_state=native_state(other)
                    lead_index=max(0,min(899,int(other_state['position_m'][0]-100)))
                    other.apply_control(command(carla,other,[(100+i,-6.0) for i in range(900)],lead_index,8.0)[0])
                    gap=min(v[0] for v in other_state['body_vertices_m'])-max(v[0] for v in ego_state['body_vertices_m'])
                    desired=max(0,min(9.0,8.0+.07*(gap-float(setting(case,'commanded_surface_gap')))))
                elif mechanism=='reverse':
                    desired=2.0
                else:
                    desired=3.0
                control,index=command(carla,ego,path,index,desired,mechanism=='reverse')
                ego.apply_control(control)
                frame=world.tick()
                now=world.get_snapshot().timestamp.elapsed_seconds-start
                row=capture.capture(frame,now)
                captured=json.loads(evidence.readline())
                if captured['original_frame']!=frame:
                    raise RuntimeError('Original evidence/source frame mismatch')
                sample={'time_s':now,'frame':frame,'ego':native_state(ego),'others':[native_state(a) for a in others],
                        'route_index':index,'mechanism':mechanism,'target':{k:v.get('value') for k,v in case['variable_assignments'].items() if v['kind']=='controller'}}
                if mechanism=='yield':
                    sample['counterpart_visibility']=actual_counterpart_visibility(carla,world,ego,others[0])
                if mechanism=='uturn':
                    # Restrict expensive full two-sided ray scans to sampled
                    # actual maneuver positions, retaining frame/time joins.
                    if 65<=index<=155 and tick%10==0:
                        sample['visibility_profile']=visibility_profile(carla,world,ego)
                physical.write(json.dumps(sample)+'\n')
                for name,stream in channels.items():
                    if name=='counterpart_initial_gap_m':
                        value=min(v[1] for v in sample['others'][0]['body_vertices_m'])-7.0
                    elif name=='kin.position':
                        value=sample['ego']['position_m']
                    elif name=='kin.speed':
                        value=sample['ego']['speed_mps']
                    elif name=='kin.heading':
                        value=sample['ego']['heading_deg']
                    elif name=='kin.extent':
                        body=sample['ego']['body_vertices_m']
                        value=max(v[1] for v in body)-min(v[1] for v in body)
                    elif name=='rel.surface_gap':
                        other_body=sample['others'][0]['body_vertices_m']
                        ego_body=sample['ego']['body_vertices_m']
                        value=min(v[0] for v in other_body)-max(v[0] for v in ego_body)
                    elif name=='st.sight_distance':
                        visibility=captured.get('visibility') or {}
                        approaches=visibility.get('approaches',[])
                        if mechanism=='uturn' and (not {-1,1}<={a.get('direction_sign') for a in approaches} or
                                any(a.get('unknown_reason') or a.get('any_body_sight_horizon',{}).get('unknown') for a in approaches)):
                            raise RuntimeError('Both native approach visibility routes are required')
                        horizons=[a.get('any_body_sight_horizon',{}).get('distance_m')
                                  for a in approaches
                                  if not a.get('unknown_reason')]
                        if not horizons or any(v is None for v in horizons):
                            raise RuntimeError('Missing supplied actual-body sight-distance measurement')
                        value=min(horizons)
                    else:
                        value={'original_observations':captured['original_observations'],
                               'native_scenario_sample':sample}
                    stream.write(json.dumps({'time_s':now,'value':value})+'\n')
                for name,q in queues.items():
                    image=q.get(timeout=20)
                    while image.frame<frame:
                        image=q.get(timeout=20)
                    if image.frame!=frame:raise RuntimeError('Camera frame mismatch')
                    encoders[name].stdin.write(bytes(image.raw_data))
                frame_map.write(json.dumps({'video_frame':tick,'native_frame':frame,'carla_frame':frame,'time_s':now})+'\n')
                count+=1
                pos=sample['ego']['position_m']
                if index>=len(path)-2 and math.dist(pos[:2],path[-1])<=2.0 and sample['ego']['speed_mps']<2.0:break
        (out/'capability-report.json').write_text(json.dumps({'case_id':case['case_id'],'frames':count,
            'motion_completed':index>=len(path)-2 and math.dist(sample['ego']['position_m'][:2],path[-1])<=2.0,
            'physical_acceptance':False,
            'needs_analysis':'Run analyze.py on original physical_samples.jsonl and inspect source cameras'},indent=2)+'\n')
    finally:
        if 'evidence' in locals():evidence.close()
        for stream in channels.values():stream.close()
        if capture:capture.close(confirmed=count>0)
        for name,encoder in encoders.items():
            encoder.stdin.close()
            encoder.wait(timeout=120)
            logs[name].close()
        for actor in reversed(actors):actor.destroy()
        if world:
            client.load_world(previous_map)
            restored=client.get_world()
            restored.apply_settings(previous_settings)
            restored.set_weather(previous_weather)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--check',action='store_true')
    parser.add_argument('--output-dir')
    parser.add_argument('--host')
    parser.add_argument('--port',type=int)
    args=parser.parse_args()
    if args.check:check()
    else:
        if not all((args.output_dir,args.host,args.port)):parser.error('Live execution requires output-dir, host and port')
        run(args)
