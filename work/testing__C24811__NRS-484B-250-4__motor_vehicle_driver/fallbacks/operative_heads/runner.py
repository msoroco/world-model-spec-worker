"""Four dark signal heads, physical stop lines, three complete vehicle histories."""
from worker_exchange.native_output import capture_context, seal_capture
import argparse, hashlib, json, queue, subprocess, traceback, xml.etree.ElementTree as ET
from pathlib import Path
from worker_exchange.native_output import FrameMap
from worker_exchange.world_restore import snapshot, restore
ROOT = Path(__file__).resolve().parent

def startup_settling_ticks():
    return 40

def check():
    cfg = json.loads((ROOT / 'config.json').read_text())
    root = ET.parse(ROOT / 'scene.xodr').getroot()
    assert root.find("junction[@id='100']") is not None
    assert len(root.findall('.//signal[@type="1000001"]')) == 4
    assert cfg['reference_kind'] in ('line', 'marked_crosswalk', 'unmarked_crosswalk', 'sight')
    assert len(root.findall('.//object[@type="building"]')) >= 2
    assert cfg['duration_s'] == 45 and cfg['rate_hz'] == 20
    assert [(c['name'], c['width'], c['height']) for c in cfg['cameras']] == [('overview', 1920, 1080), ('approach', 1280, 720), ('reference_corner', 1280, 720), ('driver_reference', 1280, 720)]
    generated = ET.fromstring(authored_scene(cfg))
    if cfg['reference_kind'] == 'unmarked_crosswalk':
        assert len(generated.findall('.//lane[@type="sidewalk"]')) >= 8
    if cfg.get('installed_heads', True) is False:
        assert not generated.findall('.//signal')
    return {'passed': True, 'authored_signal_heads': len(generated.findall('.//signal')), 'stop_line_objects': len(generated.findall('.//object[@name="StopLine"]')), 'corner_occluder_candidates': 2, 'carla_contacted': False}

def authored_scene(cfg):
    source_tree = ET.fromstring((ROOT / 'scene.xodr').read_text())
    if cfg['reference_kind'] == 'unmarked_crosswalk':
        for road in source_tree.findall('road'):
            if road.get('junction') == '-1':
                for section in road.findall('./lanes/laneSection'):
                    for side_name, lane_id in [('left', '3'), ('right', '-3')]:
                        side = section.find(side_name)
                        if side is not None:
                            lane = ET.SubElement(side, 'lane', {'id': lane_id, 'type': 'sidewalk', 'level': 'true'})
                            ET.SubElement(lane, 'link')
                            ET.SubElement(lane, 'width', {'sOffset': '0', 'a': '2', 'b': '0', 'c': '0', 'd': '0'})
                            ET.SubElement(lane, 'height', {'sOffset': '0', 'inner': '.15', 'outer': '.15'})
    if cfg.get('installed_heads', True) is False:
        for road in source_tree.findall('road'):
            for signals in road.findall('signals'):
                for obj in list(signals):
                    signals.remove(obj)
    if cfg['reference_kind'] != 'line':
        for road in source_tree.findall('road'):
            for objects in road.findall('objects'):
                for obj in list(objects):
                    if obj.get('name') == 'StopLine':
                        objects.remove(obj)
    return ET.tostring(source_tree, encoding='unicode')

def state(actor):
    t = actor.get_transform()
    v = actor.get_velocity()
    return {'actor_id': actor.id, 'position_m': [t.location.x, t.location.y, t.location.z], 'velocity_mps': [v.x, v.y, v.z], 'speed_mps': v.length(), 'body_vertices_m': [[p.x, p.y, p.z] for p in actor.bounding_box.get_world_vertices(t)]}

def approach_control(actor, target, axis, direction):
    s = state(actor)
    coord = s['position_m'][axis]
    remaining = direction * (target - coord)
    desired = min(5, max(0, remaining * 0.55))
    speed = s['speed_mps']
    actor.apply_control(__import__('carla').VehicleControl(throttle=max(0, min(0.55, 0.4 * (desired - speed))), brake=max(0, min(0.85, 0.45 * (speed - desired)))))
    return {'remaining_m': remaining, 'requested_speed_mps': desired, 'observed_speed_mps': speed}

def run(args):
    import carla
    from pipeline_capture import PipelineCapture
    from physical_stopline import spawn as spawn_lines, observe as observe_lines
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
    saved_context = {}
    try:
        world = client.generate_opendrive_world(authored_scene(cfg))
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 0.05
        world.apply_settings(settings)
        world.set_weather(carla.WeatherParameters.ClearNoon)
        map_ = world.get_map()
        heads = [a for a in world.get_actors() if a.type_id.startswith('traffic.traffic_light')]
        selected = [a for a in heads if str(a.get_opendrive_id()) in {str(25040 + i) for i in (1, 2, 3, 4)}]
        if len(selected) != (4 if cfg.get('installed_heads', True) else 0):
            raise ValueError('Four installed Native vehicular signal heads required')
        for head in selected:
            head.freeze(True)
            head.set_state(carla.TrafficLightState.Green if cfg.get('operative_at_entry', False) else carla.TrafficLightState.Off)
        covers = []
        if cfg.get('cover_heads', False):
            from physical_stopline import ASSET
            cb = world.get_blueprint_library().find('static.prop.mesh')
            cb.set_attribute('mesh_path', ASSET)
            cb.set_attribute('scale', '20')
            cb.set_attribute('mass', '0')
            for head in selected:
                tr = head.get_transform()
                tr.location.z += 2.5
                tr.rotation.pitch = 90
                cover = world.spawn_actor(cb, tr)
                cover.set_simulate_physics(False)
                cover.set_collisions(False)
                covers.append(cover)
                owned.append(cover)
        affected = {str(head.get_opendrive_id()): [[w.road_id, w.section_id, w.lane_id] for w in head.get_affected_lane_waypoints()] for head in selected}
        if any((not lanes for lanes in affected.values())):
            raise ValueError('Native installed signal head lacks governed lanes')
        markings = spawn_lines(carla, world)
        owned.extend(markings)
        for _ in range(3):
            world.tick()
        line_inventory = observe_lines(markings)
        waypoints = {'ego': map_.get_waypoint_xodr(1, -1, 365), 'earlier_stopped': map_.get_waypoint_xodr(4, 1, 35), 'inside_vehicle': map_.get_waypoint_xodr(2, 1, 35)}
        if any((v is None for v in waypoints.values())):
            raise ValueError('Missing connected ordinary-vehicle approach lane')
        actors = {}
        for role, wp in waypoints.items():
            bp = world.get_blueprint_library().find('vehicle.lincoln.mkz_2020')
            bp.set_attribute('role_name', 'signal2504_' + role)
            actor = world.spawn_actor(bp, wp.transform)
            owned.append(actor)
            actors[role] = actor
            actor.apply_control(carla.VehicleControl(brake=1, hand_brake=True))
        for _ in range(startup_settling_ticks()):
            world.tick()
        context = {'installed_heads': [{'actor_id': head.id, 'opendrive_id': head.get_opendrive_id(), 'type_id': head.type_id, 'affected_lanes': affected[str(head.get_opendrive_id())]} for head in selected], 'head_count': len(selected), 'covered_requested': cfg.get('cover_heads', False), 'native_covers': [{'actor_id': x.id, 'position_m': [x.get_location().x, x.get_location().y, x.get_location().z]} for x in covers], 'uncovered_source': 'physical head mesh and original RGB pixels; GPU check required', 'inoperative_request': 'all four Native vehicular heads frozen Off before approach and through entry; original readback retained', 'physical_stopline_tiles': line_inventory, 'reference_line_x_m': cfg['reference_x_m'], 'reference_kind': cfg['reference_kind'], 'crosswalk_present': cfg['reference_kind'] in ('marked_crosswalk', 'unmarked_crosswalk'), 'crosswalk_definition': cfg['crosswalk_definition'], 'intersection_polygon_xy_m': [[-7, -7], [7, -7], [7, 7], [-7, 7]], 'occluder_candidates': [{'object_id': x.id, 'name': x.name} for x in map_.get_all_landmarks() if 'CornerOccluder' in x.name], 'official_authority': 'Synthetic authored control; external official provenance unresolved'}
        (out / 'signal_context.json').write_text(json.dumps(context, indent=2) + '\n')
        for spec in cfg['cameras']:
            name, w, h = (spec['name'], spec['width'], spec['height'])
            cbp = world.get_blueprint_library().find('sensor.camera.rgb')
            for key, value in [('image_size_x', w), ('image_size_y', h), ('fov', spec['fov_deg']), ('sensor_tick', 0)]:
                cbp.set_attribute(key, str(value))
            if name == 'overview':
                pose = carla.Transform(carla.Location(x=-2, y=0, z=90), carla.Rotation(pitch=-90))
                attach = None
            elif name == 'approach':
                pose = carla.Transform(carla.Location(x=-9, y=0, z=8), carla.Rotation(pitch=-10))
                attach = actors['ego']
            elif name == 'reference_corner':
                pose = carla.Transform(carla.Location(x=-17, y=-14, z=22), carla.Rotation(pitch=-50))
                attach = None
            else:
                pose = carla.Transform(carla.Location(x=0, y=0, z=1.5), carla.Rotation())
                attach = actors['ego']
            camera = world.spawn_actor(cbp, pose, attach_to=attach)
            owned.append(camera)
            cameras[name] = camera
            queues[name] = queue.Queue()
            camera.listen(queues[name].put)
            stream = (out / (name + '.encoder.log')).open('x')
            streams[name] = stream
            encoders[name] = subprocess.Popen(['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-n', '-f', 'rawvideo', '-pix_fmt', 'bgra', '-s', f'{w}x{h}', '-r', '20', '-i', 'pipe:0', '-an', '-c:v', 'ffv1', '-pix_fmt', 'bgr0', str(out / (name + '.mkv'))], stdin=subprocess.PIPE, stderr=stream)
        capture = PipelineCapture(client, actors['ego'], out, cfg['selected_case_id'], visibility=True, required_observations=cfg['required_atoms'])
        start = world.get_snapshot().timestamp.elapsed_seconds
        blocked_samples = 0
        with FrameMap(out / 'video_frames.jsonl') as fmap, (out / 'interaction_history.jsonl').open('x') as history:
            for i in range(cfg['duration_s'] * 20):
                requests = {}
                requests['earlier_stopped'] = approach_control(actors['earlier_stopped'], 13 if i < cfg['earlier_release_tick'] else -30, 1, -1)
                requests['inside_vehicle'] = approach_control(actors['inside_vehicle'], 13 if i < cfg['occupant_release_tick'] else -30, 0, -1)
                requests['ego'] = approach_control(actors['ego'], cfg['reference_x_m'] - 2.5 if i < cfg['ego_release_tick'] and cfg['request_stop'] else 30, 0, 1)
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
                states = {role: state(actor) for role, actor in actors.items()}
                eye = carla.Location(x=states['ego']['position_m'][0], y=states['ego']['position_m'][1], z=states['ego']['position_m'][2] + 1.5)
                target = actors['earlier_stopped'].get_transform().location
                raw_hits = world.cast_ray(eye, target)
                hits = [h for h in raw_hits if not actors['earlier_stopped'].bounding_box.contains(h.location, actors['earlier_stopped'].get_transform()) and (not actors['ego'].bounding_box.contains(h.location, actors['ego'].get_transform()))]
                blocked_samples += bool(hits)
                sight_candidates = []
                for sx in range(-20, -6):
                    viewpoint = carla.Location(x=sx, y=eye.y, z=eye.z)
                    candidate_hits = world.cast_ray(viewpoint, target)
                    obstruction = [h for h in candidate_hits if not actors['earlier_stopped'].bounding_box.contains(h.location, actors['earlier_stopped'].get_transform()) and (not actors['ego'].bounding_box.contains(h.location, actors['ego'].get_transform()))]
                    sight_candidates.append({'eye_m': [sx, eye.y, eye.z], 'hit_count': len(obstruction), 'clear': not obstruction, 'distance_to_intersection_m': max(0, -7 - sx)})
                head_rows = [{'actor_id': head.id, 'opendrive_id': head.get_opendrive_id(), 'state': str(head.get_state()).split('.')[-1], 'affected_lanes': affected[str(head.get_opendrive_id())]} for head in selected]
                history.write(json.dumps({'frame': frame, 'time_s': now, 'states': states, 'head_states': head_rows, 'sight_candidates': sight_candidates, 'physical_stopline_tiles': len(line_inventory), 'sight_ray': {'eye_m': [eye.x, eye.y, eye.z], 'target_m': [target.x, target.y, target.z], 'hits': [{'label': str(h.label), 'location_m': [h.location.x, h.location.y, h.location.z]} for h in hits]}, 'control_requests': requests, 'camera_original_sha256': originals}) + '\n')
                capture.capture(frame, now)
                fmap.append(frame, now)
                frames += 1
        (out / 'sight_obstruction_report.json').write_text(json.dumps({'blocked_original_samples': blocked_samples, 'total_original_samples': frames, 'physical_obstruction_verified': blocked_samples > 0, 'pixel_visibility_verified': False}, indent=2) + '\n')
        if blocked_samples == 0:
            raise ValueError('No Native obstructed approach sight ray observed')
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
