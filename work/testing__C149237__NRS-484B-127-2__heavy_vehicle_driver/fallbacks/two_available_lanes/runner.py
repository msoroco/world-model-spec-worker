"""Original Native two-truck following episode with four synchronized views."""
from worker_exchange.native_output import capture_context, seal_capture
import argparse, hashlib, json, queue, subprocess, traceback, xml.etree.ElementTree as ET
from pathlib import Path
from worker_exchange.native_output import FrameMap
from worker_exchange.world_restore import snapshot, restore
ROOT = Path(__file__).resolve().parent

def startup_settling_ticks():
    return 50

def check():
    cfg = json.loads((ROOT / 'config.json').read_text())
    road = ET.parse(ROOT / 'scene.xodr').getroot().find("road[@id='1']")
    assert road is not None and float(road.get('length')) >= 1500
    assert len(road.findall('.//lane[@type="driving"]')) == cfg['same_direction_lane_count']
    assert cfg['duration_s'] == 42 and cfg['rate_hz'] == 20
    assert [(c['name'], c['width'], c['height']) for c in cfg['cameras']] == [('overview', 1920, 1080), ('approach', 1280, 720), ('reference_corner', 1280, 720), ('driver_reference', 1280, 720)]
    assert cfg['required_atoms'] == ['kin.speed', 'st.one_way_roadway']
    return {'passed': True, 'two_opposed_driving_lanes': True, 'carla_contacted': False}

def state(actor):
    t = actor.get_transform()
    v = actor.get_velocity()
    c = actor.get_control()
    return {'actor_id': actor.id, 'position_m': [t.location.x, t.location.y, t.location.z], 'velocity_mps': [v.x, v.y, v.z], 'body_vertices_m': [[p.x, p.y, p.z] for p in actor.bounding_box.get_world_vertices(t)], 'applied_control': {'throttle': c.throttle, 'brake': c.brake}}

def run(args):
    import carla
    from pipeline_capture import PipelineCapture
    from following_controller import FollowingController, leader_requested_speed
    cfg = json.loads((ROOT / 'config.json').read_text())
    out = Path(args.output_dir)
    client = carla.Client(args.host, args.port)
    client.set_timeout(90)
    saved = snapshot(client)
    owned = []
    encoders = {}
    streams = {}
    queues = {}
    cameras = {}
    capture = None
    frames = 0
    errors = []
    road_name = None
    saved_context = {}
    try:
        world = client.generate_opendrive_world((ROOT / 'scene.xodr').read_text())
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 0.05
        world.apply_settings(settings)
        world.set_weather(carla.WeatherParameters.ClearNoon)
        road_name = world.get_map().name
        bp = world.get_blueprint_library().find(cfg['ego_blueprint'])
        bp.set_attribute('role_name', 'subject_heavy_truck')
        wp = world.get_map().get_waypoint_xodr(1, -1, 300)
        ego = world.spawn_actor(bp, wp.transform)
        owned.append(ego)
        bp2 = world.get_blueprint_library().find(cfg['lead_blueprint'])
        bp2.set_attribute('role_name', 'leading_heavy_truck')
        wp2 = world.get_map().get_waypoint_xodr(1, -1, 300 + cfg['requested_body_gap_m'] + 12)
        lead = world.spawn_actor(bp2, wp2.transform)
        owned.append(lead)
        from truck_extensions import spawn_extras, apply_hitches, extend_state
        trailers, entrant = spawn_extras(carla, world, cfg, ego, lead, owned)
        for truck in (ego, lead):
            truck.apply_control(carla.VehicleControl(brake=1, hand_brake=True))
        for _ in range(startup_settling_ticks()):
            world.tick()
        condition_actors = []
        if cfg['conditions_context']['authored_condition'] != 'available':
            options = list(world.get_blueprint_library().filter('static.prop.*container*'))
            if not options:
                raise ValueError('Native condition obstruction asset unavailable')
            pose = world.get_map().get_waypoint_xodr(1, -1, 390).transform
            ob = world.spawn_actor(options[0], pose)
            ob.set_simulate_physics(False)
            owned.append(ob)
            condition_actors.append(ob)
        cfg['conditions_context']['native_obstruction_bodies'] = [{'actor_id': ob.id, 'body_vertices_m': [[p.x, p.y, p.z] for p in ob.bounding_box.get_world_vertices(ob.get_transform())]} for ob in condition_actors]
        contexts = []
        for role, truck in [('ego', ego), ('lead', lead)]:
            vertices = extend_state(state(truck), trailers.get(role))['body_vertices_m']
            width = max((v[1] for v in vertices)) - min((v[1] for v in vertices))
            contexts.append({'role': role, 'native_actor_id': truck.id, 'blueprint': truck.type_id, 'measured_bbox_width_m': width, 'physical_width_at_least_80in': width >= 2.032})
        for row in contexts:
            row['class'] = cfg['ego_class'] if row['role'] == 'ego' else cfg['lead_class']
            row['drawn_vehicle_actor_id'] = trailers[row['role']].id if row['role'] in trailers else None
        (out / 'truck_context.json').write_text(json.dumps({'trucks': contexts, 'same_direction_lane_count': cfg['same_direction_lane_count'], 'conditions_context': cfg['conditions_context'], 'source': 'Original Native bounding boxes and OpenDRIVE road1 lane inventory; physical interpretation pending'}, indent=2) + '\n')
        (out / 'scenario_geometry.json').write_text(json.dumps({'source': 'Authored scene.xodr with original Native map inventory', 'physical_verification': 'Native lane and pixels unverified; authored declaration only', 'directed_roadways': [{'polygon': [[0, -14], [1500, -14], [1500, 0], [0, 0]], 'direction_xy': [1, 0], 'one_way': True}]}))
        for spec in cfg['cameras']:
            name, w, h = (spec['name'], spec['width'], spec['height'])
            camera_bp = world.get_blueprint_library().find('sensor.camera.rgb')
            for key, value in [('image_size_x', w), ('image_size_y', h), ('fov', spec['fov_deg']), ('sensor_tick', 0)]:
                camera_bp.set_attribute(key, str(value))
            if name == 'overview':
                pose = carla.Transform(carla.Location(x=0, y=0, z=100), carla.Rotation(pitch=-90))
                attach = ego
            elif name == 'approach':
                pose = carla.Transform(carla.Location(x=-15, y=0, z=9), carla.Rotation(pitch=-12))
                attach = ego
            elif name == 'reference_corner':
                pose = carla.Transform(carla.Location(x=0, y=-35, z=75), carla.Rotation(pitch=-75))
                attach = lead
            else:
                pose = carla.Transform(carla.Location(x=0, y=0, z=2.2), carla.Rotation())
                attach = ego
            camera = world.spawn_actor(camera_bp, pose, attach_to=attach)
            owned.append(camera)
            cameras[name] = camera
            queues[name] = queue.Queue()
            camera.listen(queues[name].put)
            stream = (out / (name + '.encoder.log')).open('x')
            streams[name] = stream
            encoders[name] = subprocess.Popen(['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-n', '-f', 'rawvideo', '-pix_fmt', 'bgra', '-s', f'{w}x{h}', '-r', '20', '-i', 'pipe:0', '-an', '-c:v', 'ffv1', '-pix_fmt', 'bgr0', str(out / (name + '.mkv'))], stdin=subprocess.PIPE, stderr=stream)
        capture = PipelineCapture(client, ego, out, cfg['selected_case_id'], required_observations=cfg['required_atoms'])
        start = world.get_snapshot().timestamp.elapsed_seconds
        controller = FollowingController(cfg['requested_body_gap_m'])
        with FrameMap(out / 'video_frames.jsonl') as fmap, (out / 'truck_history.jsonl').open('x') as history:
            for i in range(cfg['duration_s'] * 20):
                apply_hitches(carla, ego, lead, trailers)
                before_ego, before_lead = (extend_state(state(ego), trailers.get('ego')), extend_state(state(lead), trailers.get('lead')))
                now_before = i * 0.05
                requested = leader_requested_speed(now_before)
                lead_speed = lead.get_velocity().length()
                lead.apply_control(carla.VehicleControl(throttle=max(0, min(0.6, 0.4 * (requested - lead_speed))), brake=max(0, min(0.6, 0.3 * (lead_speed - requested)))))
                command = controller.step(i, now_before, before_ego, before_lead)
                if cfg['overtake'] and 100 < i < 650:
                    lateral_target = -2 if i < 400 else -6
                    error = lateral_target - ego.get_location().y
                    command['throttle'] = 0.55
                    command['brake'] = 0
                    command['hand_brake'] = False
                    steer = max(-0.4, min(0.4, error * 0.12))
                else:
                    steer = 0
                ego.apply_control(carla.VehicleControl(throttle=command['throttle'], brake=command['brake'], steer=steer, hand_brake=command['hand_brake']))
                entrant_speed = entrant.get_velocity().length()
                target_y = -6 if i > cfg['entrant_start_tick'] else -11
                entrant.apply_control(carla.VehicleControl(throttle=max(0, min(0.5, 0.3 * (9 - entrant_speed))), steer=max(-0.35, min(0.35, 0.1 * (target_y - entrant.get_location().y)))))
                frame = world.tick()
                now = world.get_snapshot().timestamp.elapsed_seconds - start
                originals = {}
                for spec in cfg['cameras']:
                    name = spec['name']
                    image = queues[name].get(timeout=30)
                    while image.frame < frame:
                        image = queues[name].get(timeout=30)
                    if image.frame != frame:
                        raise ValueError('Original camera tick mismatch: ' + name)
                    encoders[name].stdin.write(image.raw_data)
                    originals[name] = hashlib.sha256(image.raw_data).hexdigest()
                current_ego, current_lead = (extend_state(state(ego), trailers.get('ego')), extend_state(state(lead), trailers.get('lead')))
                history.write(json.dumps({'frame': frame, 'time_s': now, 'ego_vertices_m': current_ego['body_vertices_m'], 'lead_vertices_m': current_lead['body_vertices_m'], 'ego_actor_id': ego.id, 'lead_actor_id': lead.id, 'entrant_vertices_m': [[p.x, p.y, p.z] for p in entrant.bounding_box.get_world_vertices(entrant.get_transform())], 'requested_phase': 'overtaking' if cfg['overtake'] and 100 < i < 650 else 'following', 'requested_controls': command, 'original_camera_sha256': originals}) + '\n')
                capture.capture(frame, now)
                fmap.append(frame, now)
                frames += 1
        saved_context = capture_context(locals())
    except BaseException as error:
        errors.append({'message': str(error), 'traceback': traceback.format_exc()})
    finally:
        if capture:
            try:
                capture.close(confirmed=not errors and frames == cfg['duration_s'] * 20)
            except BaseException as error:
                errors.append({'capture_close': str(error)})
        for process in encoders.values():
            try:
                process.stdin.close()
                if process.wait(timeout=180):
                    errors.append({'encoder_exit': process.returncode})
            except BaseException as error:
                errors.append({'encoder': str(error)})
        for stream in streams.values():
            stream.close()
        for actor in reversed(owned):
            try:
                actor.destroy()
            except BaseException as error:
                errors.append({'destroy': str(error)})
        try:
            restoration = restore(client, saved)
        except BaseException as error:
            errors.append({'restore': str(error)})
            restoration = {'restored': False}
        (out / 'native-run-status.json').write_text(json.dumps({'frames': frames, 'errors': errors, 'restoration': restoration}, indent=2) + '\n')
    if errors:
        raise RuntimeError('Native capture failed: ' + str(errors))
    seal_capture(out, frames=frames, restoration=restoration, errors=errors, encoder_exit_codes={name: process.returncode for name, process in encoders.items()}, context=saved_context)
if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--check', action='store_true')
    p.add_argument('--output-dir', default='.')
    p.add_argument('--host', default='127.0.0.1')
    p.add_argument('--port', type=int, default=2000)
    a = p.parse_args()
    if a.check:
        print(json.dumps(check()))
    else:
        run(a)
