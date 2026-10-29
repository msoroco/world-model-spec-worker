"""Single original Native episode on a connected straight roadway."""
from worker_exchange.native_output import capture_context, seal_capture
import argparse, hashlib, json, queue, subprocess, traceback, xml.etree.ElementTree as ET
from pathlib import Path
from worker_exchange.native_output import FrameMap
from worker_exchange.world_restore import snapshot, restore
ROOT = Path(__file__).resolve().parent

def check():
    cfg = json.loads((ROOT / 'config.json').read_text())
    road = ET.parse(ROOT / 'scene.xodr').getroot().find("road[@id='1']")
    assert road is not None and float(road.attrib['length']) >= 1800
    assert len(road.findall('.//lane[@type="driving"]')) >= 2
    assert cfg['duration_s'] == 45 and cfg['rate_hz'] == 20
    assert [c['name'] for c in cfg['cameras']] == ['overview', 'approach', 'reference_corner', 'driver_reference']
    assert [(c['width'], c['height']) for c in cfg['cameras']] == [(1920, 1080), (1280, 720), (1280, 720), (1280, 720)]
    assert {'kin.speed', 'kin.velocity', 'env.visibility', 'env.ice_or_snow'} <= set(cfg['required_atoms'])
    return {'passed': True, 'road_length_m': float(road.attrib['length']), 'cameras': 4, 'carla_contacted': False}

def run(args):
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.environment_acquisition import calibrate, fields
    client = carla.Client(args.host, args.port)
    client.set_timeout(60)
    saved = snapshot(client)
    world = None
    owned = []
    cameras = {}
    queues = {}
    encoders = {}
    streams = {}
    capture = None
    out = Path(args.output_dir)
    cfg = json.loads((ROOT / 'config.json').read_text())
    frames = 0
    errors = []
    saved_context = {}
    try:
        world = client.generate_opendrive_world((ROOT / 'scene.xodr').read_text())
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 0.05
        world.apply_settings(settings)
        world.set_weather(carla.WeatherParameters(precipitation=cfg.get('precipitation', 0), wetness=cfg.get('wetness', 0), fog_density=cfg.get('fog_density', 2), sun_altitude_angle=45))
        mapping = world.get_map()
        wp = mapping.get_waypoint_xodr(1, -1, 100)
        if wp is None:
            raise ValueError('Native lane 1/-1 is missing')
        blueprint = world.get_blueprint_library().find('vehicle.lincoln.mkz_2020')
        blueprint.set_attribute('role_name', 'subject_speed_600_1e')
        ego = world.spawn_actor(blueprint, wp.transform)
        owned.append(ego)
        ego.apply_control(carla.VehicleControl(brake=1, hand_brake=True))
        other_bp = world.get_blueprint_library().find('vehicle.tesla.model3')
        other_bp.set_attribute('role_name', 'other_traffic_600_1a')
        other_wp = mapping.get_waypoint_xodr(1, 1, cfg.get('other_station_m', 250))
        if other_wp is None:
            raise ValueError('Opposite roadway lane missing')
        other = world.spawn_actor(other_bp, other_wp.transform)
        owned.append(other)
        other.apply_control(carla.VehicleControl(brake=1, hand_brake=True))
        for _ in range(20):
            world.tick()
        for spec in cfg['cameras']:
            name, w, h = (spec['name'], spec['width'], spec['height'])
            bp = world.get_blueprint_library().find('sensor.camera.rgb')
            for key, value in [('image_size_x', w), ('image_size_y', h), ('fov', spec['fov_deg']), ('sensor_tick', 0)]:
                bp.set_attribute(key, str(value))
            if name == 'overview':
                pose = carla.Transform(carla.Location(x=150, y=0, z=220), carla.Rotation(pitch=-90))
            elif name == 'approach':
                pose = carla.Transform(carla.Location(x=-12, y=0, z=8), carla.Rotation(pitch=-15))
            elif name == 'reference_corner':
                pose = carla.Transform(carla.Location(x=150, y=-15, z=45), carla.Rotation(pitch=-65))
            else:
                pose = carla.Transform(carla.Location(x=0, y=0, z=1.5), carla.Rotation())
            camera = world.spawn_actor(bp, pose, attach_to=ego if name in ('approach', 'driver_reference') else None)
            owned.append(camera)
            cameras[name] = camera
            queues[name] = queue.Queue()
            camera.listen(queues[name].put)
            stream = (out / (name + '.encoder.log')).open('x')
            streams[name] = stream
            encoders[name] = subprocess.Popen(['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-n', '-f', 'rawvideo', '-pix_fmt', 'bgra', '-s', f'{w}x{h}', '-r', '20', '-i', 'pipe:0', '-an', '-c:v', 'ffv1', '-pix_fmt', 'bgr0', str(out / (name + '.mkv'))], stdin=subprocess.PIPE, stderr=stream)
        cal = calibrate(world, other, out, owned, distances=(25, 50, 100, 200, 400))
        road_file = out / 'road.xodr'
        road_file.write_text(mapping.to_opendrive())
        road_hash = hashlib.sha256(road_file.read_bytes()).hexdigest()
        surface = {'schema': 'authored-native-road-surface-v1', 'ice_or_snow': False, 'map_sha256': road_hash, 'source_assets': [{'path': str(road_file.resolve()), 'sha256': road_hash}], 'authorship': 'Explicit synthetic OpenDRIVE asphalt authoring; Native surface/physical status remains local review'}
        (out / 'surface_provenance.json').write_text(json.dumps(surface, indent=2) + '\n')
        surface_hash = hashlib.sha256((out / 'surface_provenance.json').read_bytes()).hexdigest()
        calibration_hash = hashlib.sha256((out / 'environment_calibration.json').read_bytes()).hexdigest()
        capture = PipelineCapture(client, ego, out, cfg['selected_case_id'], required_observations=cfg['required_atoms'])
        started = world.get_snapshot().timestamp.elapsed_seconds
        with FrameMap(out / 'video_frames.jsonl') as fmap, (out / 'body_history.jsonl').open('x') as body, (out / 'other_motion.jsonl').open('x') as other_motion:
            for index in range(cfg['duration_s'] * cfg['rate_hz']):
                speed = ego.get_velocity().length()
                effort = max(0, min(0.6, 0.3 * (cfg['requested_speed_mps'] - speed)))
                ego.apply_control(carla.VehicleControl(throttle=effort, brake=max(0, min(0.5, 0.2 * (speed - cfg['requested_speed_mps'])))))
                other.apply_control(carla.VehicleControl(throttle=cfg.get('other_throttle', 0.25), brake=0))
                frame = world.tick()
                now = world.get_snapshot().timestamp.elapsed_seconds - started
                native_images = {}
                for spec in cfg['cameras']:
                    name = spec['name']
                    image = queues[name].get(timeout=30)
                    while image.frame < frame:
                        image = queues[name].get(timeout=30)
                    if image.frame != frame:
                        raise ValueError('Camera original tick mismatch: ' + name)
                    encoders[name].stdin.write(image.raw_data)
                    native_images[name] = {'frame': image.frame, 'sha256': hashlib.sha256(image.raw_data).hexdigest()}
                transform = ego.get_transform()
                vertices = [[v.x, v.y, v.z] for v in ego.bounding_box.get_world_vertices(transform)]
                body.write(json.dumps({'frame': frame, 'time_s': now, 'vertices_m': vertices, 'camera_originals': native_images}) + '\n')
                ov = other.get_velocity()
                op = other.get_transform().location
                ep = ego.get_transform().location
                ray_start = carla.Location(x=ep.x, y=ep.y, z=ep.z + 1.4)
                ray_end = carla.Location(x=op.x, y=op.y, z=op.z + 1.4)
                ray_hits = world.cast_ray(ray_start, ray_end)
                other_motion.write(json.dumps({'frame': frame, 'time_s': now, 'other_speed_mps': ov.length(), 'separation_m': ep.distance(op), 'sight_ray_hit_count': len(ray_hits), 'other_position_m': [op.x, op.y, op.z], 'traffic_actor_inventory': [{'id': actor.id, 'type_id': actor.type_id, 'position_m': [actor.get_location().x, actor.get_location().y, actor.get_location().z]} for actor in world.get_actors() if actor.type_id.startswith(('vehicle.', 'walker.'))], 'weather': fields(world.get_weather())}) + '\n')
                env = {'frame': frame, 'time_s': now, 'weather': cal['weather'], 'visibility_m': cal['visibility_m'], 'ice_or_snow': False, 'calibration_sha256': calibration_hash, 'surface_sha256': surface_hash}
                capture.capture(frame, now, extra={'environment_measurements': env})
                fmap.append(frame, now)
                frames += 1
        if frames != cfg['duration_s'] * cfg['rate_hz']:
            raise ValueError('Incomplete original duration')
        saved_context = capture_context(locals())
    except BaseException as error:
        errors.append({'message': str(error), 'traceback': traceback.format_exc()})
    finally:
        if capture:
            try:
                capture.close(confirmed=not errors and frames == cfg['duration_s'] * cfg['rate_hz'])
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
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output-dir', default='.')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args()
    if args.check:
        print(json.dumps(check()))
    else:
        run(args)
