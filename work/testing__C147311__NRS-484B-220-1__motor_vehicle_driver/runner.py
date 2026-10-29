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
    assert {1,2,3,4,11,12}<=set(roads)
    assert tree.findall('junction/connection')
    assert cfg['duration_s']>=20
    assert cfg['camera']['width']>=960 and cfg['camera']['height']>=540
    assert cfg['recording_description']['channels']
    kind=cfg['scene_kind']
    if kind in ('median_crossing','median_uturn'):
        assert 'st.median_or_divider' in cfg['required_atoms']
        assert 'scenario_geometry' in cfg['source_packets']
        assert len(tree.findall("road/objects/object[@name='MedianBarrier']"))>=2
    if kind=='one_way':
        assert 'st.one_way_roadway' in cfg['required_atoms']
        assert 'dev.regulatory_sign' in cfg['required_atoms']
        assert {'scenario_geometry','scenario_rule_evidence'}<=set(cfg['source_packets'])
        assert tree.findall("road/signals/signal[@id='8801']")
        assert len(roads[1].findall('lanes/laneSection/right/lane[@type="driving"]'))>=2
    if kind=='right_signal':
        assert 'sig.turn_indicator' in cfg['required_atoms']
        assert any(c.attrib.get('connectingRoad')=='13' for c in tree.findall('junction/connection'))
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
        for actor in [ego,other]:
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
        if cfg['scene_kind']=='speed' and other:
            from worker_exchange.environment_acquisition import calibrate,surface_receipt
            cal=calibrate(world,other,output,owned)
            surface_receipt(world,road,output,ROOT/'scene.xodr',[])
        landmarks=road.get_all_landmarks()
        official=[{'id':l.id,'name':l.name,'type':l.type} for l in landmarks if str(l.type).lower() in ('stop','yield','traffic_light')]
        if 'device_inventory.json' in static:
            (output/'device_inventory.json').write_text(json.dumps({'official_devices':official,
                'governance_scope':'native landmark inventory at generated junction; pixel and authority review pending',
                'inventory_method':'Map.get_all_landmarks original generated world','subsection_4_status':'separate unresolved qualification'},indent=2)+'\n')
        sign=None
        if cfg['scene_kind']=='one_way':
            sign=next((l for l in landmarks if str(l.id)=='8801'),None)
            if sign is None:raise ValueError('Original native one-way sign landmark 8801 missing')
        start=world.get_snapshot().timestamp.elapsed_seconds
        writers={name:(output/name).open('x') for name in cfg['dynamic_sources']}
        try:
            with FrameMap(output/'video_frames.jsonl') as fmap:
                for i in range(int(cfg['duration_s']*20)):
                    control_toward(ego,cfg['ego_route'],cfg['target_speed_mps'])
                    if other:control_toward(other,cfg['other_route'],cfg.get('other_speed_mps',4.0))
                    if cfg['scene_kind']=='right_signal':
                        state=ego.get_light_state()|carla.VehicleLightState.RightBlinker
                        ego.set_light_state(state)
                    frame=world.tick();now=world.get_snapshot().timestamp.elapsed_seconds-start
                    image=images.get(timeout=30)
                    while image.frame<frame:image=images.get(timeout=30)
                    if image.frame!=frame:raise ValueError('Original camera frame mismatch')
                    rgb=np.frombuffer(image.raw_data,dtype=np.uint8).reshape(cfg['camera']['height'],cfg['camera']['width'],4)[:,:,:3][:,:,::-1]
                    encoder.stdin.write(rgb.tobytes());fmap.append(frame,now)
                    p=xy(ego);v=ego.get_velocity();heading=ego.get_transform().rotation.yaw
                    motion={'frame':frame,'time_s':now,'xy_m':p,'velocity_xy_mps':[v.x,v.y],
                            'speed_mps':speed(ego),'heading_deg':heading}
                    if 'motion_samples.jsonl' in writers:writers['motion_samples.jsonl'].write(json.dumps(motion)+'\n')
                    if 'body_vertices.jsonl' in writers:writers['body_vertices.jsonl'].write(json.dumps(
                        {'frame':frame,'time_s':now,'body_vertices_xy_m':body(ego),'heading_deg':heading})+'\n')
                    if 'participant_motion.jsonl' in writers:
                        other_point=xy(other);polygon=static['road_geometry.json']['intersection_polygon_xy_m']
                        row={'frame':frame,'time_s':now,'ego_xy_m':p,'other_xy_m':other_point,
                             'ego_heading_xy':[math.cos(math.radians(heading)),math.sin(math.radians(heading))],
                             'ego_speed_mps':speed(ego),'other_speed_mps':speed(other),
                             'ego_in_intersection':inside(p,polygon),'other_in_intersection':inside(other_point,polygon)}
                        writers['participant_motion.jsonl'].write(json.dumps(row)+'\n')
                    if 'signal_samples.jsonl' in writers:
                        row={'frame':frame,'time_s':now,'distance_to_turn_ft':max(0,(-7-p[0])*3.28084),
                             'observed_right_indicator':bool(ego.get_light_state() & carla.VehicleLightState.RightBlinker)}
                        writers['signal_samples.jsonl'].write(json.dumps(row)+'\n')
                    if 'conditions.jsonl' in writers:
                        w=world.get_weather();row={'frame':frame,'time_s':now,'precipitation':w.precipitation,
                            'wetness':w.wetness,'surface':'authored paved road; native surface receipt retained',
                            'visibility_m':cal['visibility_m'],'traffic_actor_xy_m':xy(other)}
                        writers['conditions.jsonl'].write(json.dumps(row)+'\n')
                    if 'scenario_rule_evidence.jsonl' in writers:
                        loc=sign.transform.location
                        row={'frame':frame,'time_s':now,'value':{'devices':[{'actor_id':8801,
                            'native_name':sign.name,'position_m':[loc.x,loc.y]}]}}
                        writers['scenario_rule_evidence.jsonl'].write(json.dumps(row)+'\n')
                    capture.capture(frame,now,extra={'selected_case':{'motion':motion,
                        'other_xy_m':xy(other) if other else None,
                        'right_indicator':bool(ego.get_light_state() & carla.VehicleLightState.RightBlinker)}})
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
