"""Exact selected-case native capture. CARLA is imported only on explicit capture."""
import argparse
import json
import math
import queue
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT=Path(__file__).resolve().parent


def check():
    cfg=json.loads((ROOT/'config.json').read_text())
    tree=ET.parse(ROOT/'scene.xodr')
    roads={int(r.attrib['id']):r for r in tree.findall('road')}
    assert cfg['duration_s']>=20
    assert cfg['camera']['width']>=960 and cfg['camera']['height']>=540
    assert cfg['recording_description']['channels']
    kind=cfg['scene_kind']
    if kind in ('following','alley_speed','posted_speed'):
        assert set(roads)=={1} and roads[1].find('planView/geometry/line') is not None
        assert float(roads[1].get('length'))>=900
        if kind=='following':
            assert roads[1].find("lanes/laneSection/right/lane[@id='-2']") is not None
            assert len(roads[1].findall('elevationProfile/elevation'))>=2
            assert cfg.get('other_start') and cfg.get('other_route')
        if kind=='alley_speed':
            assert roads[1].find("objects/object[@name='MarkedAccessAisle']") is not None
            assert cfg['target_speed_mps']>80/2.2369362921
        if kind=='posted_speed':
            assert roads[1].find("signals/signal[@id='9301']") is not None
            assert cfg['static_sources']['law_context.json']['posted_mph']==30
    else:
        assert {1,2,3,4,11,12}<=set(roads)
        assert tree.findall('junction/connection')
        assert len(roads[1].findall("signals/signal[@name='TrafficLight']"))>=2
        if kind=='yellow_signal':
            assert 'st.one_way_roadway' in cfg['required_atoms']
            assert 'scenario_geometry' in cfg['source_packets']
            assert not roads[1].findall('lanes/laneSection/left/lane')
            assert roads[1].find("signals/signal[@id='9403'][@name='PedestrianSignal']") is not None
        if kind=='inoperative_signal':
            assert roads[1].find("objects/object[@name='MarkedStopLine']") is not None
            assert roads[1].find("objects/object[@name='BlindCornerWall']") is not None
            assert cfg.get('other_start')
    print(json.dumps({'offline':'connected selected OpenDRIVE, configured camera/channels and conditional packets checked',
                      'scene_kind':kind,'roads':sorted(roads),'carla_contacted':False}))


def xy(actor):
    p=actor.get_transform().location
    return [p.x,p.y]


def speed(actor):
    v=actor.get_velocity()
    return math.hypot(v.x,v.y)


def body(actor):
    return [[v.x,v.y] for v in actor.bounding_box.get_world_vertices(actor.get_transform())]


def inside(point,polygon):
    x,y=point
    return min(p[0] for p in polygon)<=x<=max(p[0] for p in polygon) and min(p[1] for p in polygon)<=y<=max(p[1] for p in polygon)


def control_toward(actor, waypoints, desired_speed):
    import carla
    pos=actor.get_transform().location
    target=next((p for p in waypoints if math.hypot(p[0]-pos.x,p[1]-pos.y)>5),waypoints[-1])
    desired=math.degrees(math.atan2(target[1]-pos.y,target[0]-pos.x))
    error=(desired-actor.get_transform().rotation.yaw+180)%360-180
    v=speed(actor)
    actor.apply_control(carla.VehicleControl(throttle=.35 if v<desired_speed else .03,
                        brake=.25 if v>desired_speed+1 else 0, steer=max(-.7,min(.7,error/45))))


def run(args):
    import carla
    import numpy as np
    from worker_exchange.world_restore import snapshot,restore
    from worker_exchange.native_output import FrameMap
    from pipeline_capture import PipelineCapture
    cfg=json.loads((ROOT/'config.json').read_text())
    output=Path(args.output_dir).resolve()
    if output!=ROOT.resolve() and not (output/'config.json').is_file():raise ValueError('Materialized exact case required')
    client=carla.Client(args.host,args.port);client.set_timeout(60)
    saved=snapshot(client);owned=[];capture=None;encoder=None;frames=0
    try:
        world=client.generate_opendrive_world((ROOT/'scene.xodr').read_text(),carla.OpendriveGenerationParameters(
            vertex_distance=.25,max_road_length=30,wall_height=0,additional_width=0,
            smooth_junctions=False,enable_mesh_visibility=True,enable_pedestrian_navigation=False))
        setting=world.get_settings();setting.synchronous_mode=True;setting.fixed_delta_seconds=.05;world.apply_settings(setting)
        world.set_weather(carla.WeatherParameters.ClearNoon)
        world.tick();road=world.get_map()
        links=[(a.road_id,a.lane_id,b.road_id,b.lane_id) for a,b in road.get_topology()]
        if not links:raise ValueError('Native road topology absent')
        bp=world.get_blueprint_library().find('vehicle.lincoln.mkz_2020');bp.set_attribute('role_name','subject')
        ex,ey,eyaw=cfg['ego_start']
        ego=world.spawn_actor(bp,carla.Transform(carla.Location(x=ex,y=ey,z=.5),carla.Rotation(yaw=eyaw)))
        owned.append(ego)
        other=None
        if cfg.get('other_start'):
            obp=world.get_blueprint_library().find('vehicle.tesla.model3');obp.set_attribute('role_name','crossing_or_traffic_actor')
            ox,oy,oyaw=cfg['other_start']
            other=world.spawn_actor(obp,carla.Transform(carla.Location(x=ox,y=oy,z=.5),carla.Rotation(yaw=oyaw)))
            owned.append(other)
        third=None
        if cfg.get('third_start'):
            tbp=world.get_blueprint_library().find('vehicle.audi.a2');tbp.set_attribute('role_name','distinct_intersection_occupant')
            tx,ty,tyaw=cfg['third_start']
            third=world.spawn_actor(tbp,carla.Transform(carla.Location(x=tx,y=ty,z=.5),carla.Rotation(yaw=tyaw)))
            owned.append(third)
        for actor in [ego,other,third]:
            if actor:actor.apply_control(carla.VehicleControl(brake=1,hand_brake=True))
        for _ in range(20):world.tick()
        cam_bp=world.get_blueprint_library().find('sensor.camera.rgb')
        for k,v in [('image_size_x',cfg['camera']['width']),('image_size_y',cfg['camera']['height']),
                    ('fov',cfg['camera']['fov_deg']),('sensor_tick','0')]:cam_bp.set_attribute(k,str(v))
        camera=world.spawn_actor(cam_bp,carla.Transform(carla.Location(x=-15,y=0,z=35),carla.Rotation(pitch=-70)))
        owned.append(camera);images=queue.Queue();camera.listen(images.put)
        encoder=subprocess.Popen(['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-n','-f','rawvideo','-pix_fmt','rgb24',
            '-s',str(cfg['camera']['width'])+'x'+str(cfg['camera']['height']),'-r','20','-i','pipe:0','-an',
            '-c:v','ffv1','-pix_fmt','bgr0',str(output/'raw.mkv')],stdin=subprocess.PIPE)
        capture=PipelineCapture(client,ego,output,cfg['case_id'],required_observations=cfg['required_atoms'])
        static=cfg['static_sources']
        for name,value in static.items():
            if name=='road_geometry.json':value=dict(value,native_topology=links)
            (output/name).write_text(json.dumps(value,indent=2)+'\n')
        if 'scenario_geometry.json' in static:
            packet=dict(static['scenario_geometry.json'])
            packet['physical_verification']='Native OpenDRIVE topology readback; exact median/sign pixels still require operator review'
            (output/'scenario_geometry.json').write_text(json.dumps(packet,indent=2)+'\n')
        landmarks=road.get_all_landmarks()
        kind=cfg['scene_kind']
        if kind=='posted_speed' and not any(str(l.id)=='9301' for l in landmarks):
            raise ValueError('Native posted speed sign 9301 absent from generated map')
        lights=[actor for actor in world.get_actors() if actor.type_id.startswith('traffic.traffic_light')]
        def native_signal_id(actor):
            return str(actor.get_opendrive_id()) if hasattr(actor,'get_opendrive_id') else ''
        pedestrian_heads=[actor for actor in lights if native_signal_id(actor)=='9403' or 'pedestrian' in actor.type_id]
        vehicle_heads=[actor for actor in lights if actor not in pedestrian_heads]
        if kind in ('yellow_signal','inoperative_signal') and len(vehicle_heads)<2:
            raise ValueError('Two distinct native vehicular signal heads required')
        if kind=='yellow_signal' and not pedestrian_heads:
            raise ValueError('Distinct native pedestrian-head state inventory unavailable')
        (output/'native-device-inventory.json').write_text(json.dumps({
            'landmarks':[{'id':str(l.id),'name':l.name,'type':l.type} for l in landmarks],
            'lights':[{'id':int(light.id),'type_id':light.type_id,
                       'transform':str(light.get_transform())} for light in lights],
            'vehicle_head_ids':[str(light.id) for light in vehicle_heads],
            'pedestrian_head_ids':[str(light.id) for light in pedestrian_heads],
            'uncovered_pixel_review_pending':True},indent=2)+'\n')
        start=world.get_snapshot().timestamp.elapsed_seconds
        writers={name:(output/name).open('x') for name in cfg['dynamic_sources']}
        ego_stop_ticks=0;other_stop_ticks=0;other_stop_completed=False
        try:
            with FrameMap(output/'video_frames.jsonl') as fmap:
                for i in range(int(cfg['duration_s']*20)):
                    control_toward(ego,cfg['ego_route'],cfg['target_speed_mps'])
                    if other:control_toward(other,cfg['other_route'],cfg.get('other_speed_mps',4.0))
                    if third:control_toward(third,cfg['third_route'],cfg.get('third_speed_mps',4.0))
                    if kind=='yellow_signal':
                        state=carla.TrafficLightState.Green if i<100 else carla.TrafficLightState.Yellow if i<180 else carla.TrafficLightState.Red
                        for light in vehicle_heads:light.set_state(state)
                        if i<175:ego.apply_control(carla.VehicleControl(brake=1))
                    if kind=='inoperative_signal':
                        for light in vehicle_heads:light.set_state(carla.TrafficLightState.Off)
                        if other and other.get_transform().location.y>-17 and other_stop_ticks<20:
                            other.apply_control(carla.VehicleControl(brake=1));other_stop_ticks+=1
                        if ego.get_transform().location.x>-15 and ego_stop_ticks<20:
                            ego.apply_control(carla.VehicleControl(brake=1));ego_stop_ticks+=1
                    frame=world.tick();now=world.get_snapshot().timestamp.elapsed_seconds-start
                    image=images.get(timeout=30)
                    while image.frame<frame:image=images.get(timeout=30)
                    if image.frame!=frame:raise ValueError('Original camera frame mismatch')
                    rgb=np.frombuffer(image.raw_data,dtype=np.uint8).reshape(cfg['camera']['height'],cfg['camera']['width'],4)[:,:,:3][:,:,::-1]
                    encoder.stdin.write(rgb.tobytes());fmap.append(frame,now)
                    p=xy(ego);v=ego.get_velocity();heading=ego.get_transform().rotation.yaw
                    motion={'frame':frame,'time_s':now,'xy_m':p,'velocity_xy_mps':[v.x,v.y],
                            'speed_mps':speed(ego),'heading_deg':heading}
                    row={'frame':frame,'time_s':now,'ego_speed_mps':speed(ego)}
                    if kind=='following':
                        ego_front=max(vertex[0] for vertex in body(ego))
                        lead_rear=min(vertex[0] for vertex in body(other))
                        lead_y=other.get_transform().location.y
                        weather=world.get_weather();lead_acc=other.get_acceleration()
                        row.update(ego_front_x_m=ego_front,lead_rear_x_m=lead_rear,
                            lead_speed_mps=speed(other),same_lane=abs(p[1]-lead_y)<2,
                            before_lane_change=p[0]<750,weather={'precipitation':weather.precipitation,
                              'wetness':weather.wetness},road_surface='authored asphalt; original weather sampled',
                            traffic_count=len([a for a in world.get_actors() if a.type_id.startswith('vehicle.')]),
                            lead_deceleration_mps2=-lead_acc.x)
                    elif kind=='posted_speed':
                        sign=next(l for l in landmarks if str(l.id)=='9301')
                        polygon=static['road_geometry.json']['governed_polygon_xy_m']
                        row.update(within_governed_portion=inside(p,polygon),observed_landmark_id=str(sign.id))
                    elif kind=='yellow_signal':
                        polygon=static['road_geometry.json']['intersection_polygon_xy_m']
                        row.update(vehicle_head_id=str(vehicle_heads[0].id),
                            vehicle_indication=str(vehicle_heads[0].get_state()).split('.')[-1],
                            pedestrian_heads=[{'head_id':str(head.id),
                               'state':str(head.get_state()).split('.')[-1]} for head in pedestrian_heads],
                            ego_body_enters_intersection=any(inside(vertex,polygon) for vertex in body(ego)))
                    elif kind=='inoperative_signal':
                        polygon=static['road_geometry.json']['intersection_polygon_xy_m']
                        other_point=xy(other);third_body=body(third);third_point=xy(third)
                        view=ego.get_transform().transform(carla.Location(x=.5,y=0,z=1.5))
                        target_pos=third.get_transform().location
                        target=carla.Location(x=target_pos.x,y=target_pos.y,z=target_pos.z+1.3)
                        hits=world.cast_ray(view,target)
                        if other_stop_ticks>=20 and speed(other)<=.03:other_stop_completed=True
                        row.update(ego_front_x_m=max(vertex[0] for vertex in body(ego)),
                            ego_body_enters_intersection=any(inside(vertex,polygon) for vertex in body(ego)),
                            signal_heads=[{'head_id':str(light.id),'state':str(light.get_state()).split('.')[-1]} for light in vehicle_heads],
                            prior_vehicle_id=str(other.id),prior_vehicle_stop_completed=other_stop_completed,
                            occupant_vehicle_id=str(third.id),
                            occupant_vehicle_in_intersection=any(inside(vertex,polygon) for vertex in third_body),
                            ego_prior_gap_m=math.dist(p,other_point),ego_occupant_gap_m=math.dist(p,third_point),
                            driver_viewpoint_xyz_m=[view.x,view.y,view.z],
                            sight_ray_target_xyz_m=[target.x,target.y,target.z],
                            sight_ray_hits=[{'label':str(hit.label),
                                'position_xyz_m':[hit.location.x,hit.location.y,hit.location.z]} for hit in hits])
                    writers['case_observations.jsonl'].write(json.dumps(row)+'\n')
                    capture.capture(frame,now,extra={'selected_case':{'motion':motion,
                        'other_xy_m':xy(other) if other else None,
                        'measurements':row}})
                    frames+=1
        finally:
            for stream in writers.values():stream.close()
        capture.close(confirmed=True);capture=None
        encoder.stdin.close()
        if encoder.wait(timeout=120):raise ValueError('Original camera encoder failed')
        encoder=None
        subprocess.run([sys.executable,str(output/'analyze.py'),'--attempt',str(output),
                        '--output',str(output/'analysis-report.json')],check=True)
    finally:
        if capture:capture.close(confirmed=False)
        if encoder:
            encoder.stdin.close();encoder.wait(timeout=120)
        for actor in reversed(owned):
            try:
                if actor.type_id.startswith('sensor.'):actor.stop()
                actor.destroy()
            except Exception:pass
        receipt=restore(client,saved)
        (output/'world-restore.json').write_text(json.dumps(receipt,indent=2)+'\n')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');p.add_argument('--output-dir');p.add_argument('--host');p.add_argument('--port',type=int);a=p.parse_args()
    if a.check:check()
    else:
        if not all([a.output_dir,a.host,a.port]):p.error('Capture requires output, host and port')
        run(a)
