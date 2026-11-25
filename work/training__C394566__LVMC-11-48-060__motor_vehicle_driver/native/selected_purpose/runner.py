"""Survey-gated Native through-route truck attempt; --check is CPU only."""
import argparse
import json
import math
import os
import queue
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
AID = 'training__C394566__LVMC-11-48-060__motor_vehicle_driver'
CASE = AID + '__probe_02'
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
COUNT = 600


def config_check():
    cfg = json.loads((HERE/'config.json').read_text())
    if (cfg.get('assignment_id') != AID or cfg.get('case_id') != CASE or cfg.get('selected_case_id') != CASE or
            cfg.get('cell_id') != 'C394566' or cfg.get('law_id') != 'LVMC-11-48-060' or
            cfg.get('actor') != 'motor_vehicle_driver' or cfg.get('candidate_id') != 'primary' or
            cfg.get('rate_hz') != 20 or cfg.get('duration_s') != 30 or cfg.get('frames') != COUNT or
            [c.get('name') for c in cfg.get('cameras', [])] != list(CAMERAS) or
            [(c.get('width'), c.get('height')) for c in cfg['cameras']] !=
            [(1920, 1080), (1280, 720), (1280, 720), (1280, 720)] or
            cfg.get('service_stop_frames') != 100 or
            cfg.get('physical_acceptance_claimed') is not False or cfg.get('legal_verdict') is not None):
        raise ValueError('Exact through-route capture contract differs')
    return cfg


def survey_check(survey):
    for key in ('map_name', 'survey_source', 'truck_blueprint_source',
                'truck_route_designation_source', 'nontruck_street_designation_source',
                'route_connectivity_source', 'vehicle_blueprint', 'entry_truck_route_id',
                'intervening_street_id', 'exit_truck_route_id', 'spawn_xyz_m',
                'spawn_yaw_deg', 'route_waypoints_xyz_m', 'camera_mounts',
                'enroute_service_waypoint_index', 'served_premises_source'):
        if key not in survey or survey[key] is None or survey[key] == '':
            raise ValueError('Missing reviewed Native survey source: '+key)
    ids = [survey[k] for k in ('entry_truck_route_id', 'intervening_street_id', 'exit_truck_route_id')]
    if any(type(value) is not int for value in ids) or len(set(ids)) != 3:
        raise ValueError('Invalid distinct surveyed route IDs')
    route = survey['route_waypoints_xyz_m']
    if len(route) < 3 or any(len(p) != 3 or any(type(v) not in (int, float) or not math.isfinite(v) for v in p)
                             for p in route):
        raise ValueError('Invalid surveyed route waypoints')
    if (type(survey['enroute_service_waypoint_index']) is not int or
            not 1 <= survey['enroute_service_waypoint_index'] < len(route)-1):
        raise ValueError('Invalid surveyed service waypoint')
    if len(survey['spawn_xyz_m']) != 3 or set(survey['camera_mounts']) != set(CAMERAS):
        raise ValueError('Invalid spawn or camera mounts')
    for item in survey['camera_mounts'].values():
        if len(item.get('xyz_m', [])) != 3 or len(item.get('rotation_deg', [])) != 3:
            raise ValueError('Invalid surveyed camera mount')
    return survey


def transform(carla, xyz, rotation):
    return carla.Transform(carla.Location(x=xyz[0], y=xyz[1], z=xyz[2]),
                           carla.Rotation(pitch=rotation[0], yaw=rotation[1], roll=rotation[2]))


def steering(ego, target):
    pose = ego.get_transform()
    dx, dy = target[0]-pose.location.x, target[1]-pose.location.y
    desired = math.atan2(dy, dx)
    yaw = math.radians(pose.rotation.yaw)
    error = (desired-yaw+math.pi)%(2*math.pi)-math.pi
    return max(-.6, min(.6, 1.2*error))


def capture(survey, output, host, port):
    import carla
    from pipeline_capture import PipelineCapture
    cfg = config_check()
    survey_check(survey)
    output.mkdir(parents=True, exist_ok=True)
    materialized = output/'config.json'
    if not materialized.is_file() or json.loads(materialized.read_text()) != cfg:
        raise ValueError('Native attempt needs exact materialized configuration')
    if any((output/name).exists() for name in ('video_frames.jsonl', 'native_route_trace.jsonl', 'result.json')):
        raise ValueError('Retain prior Native attempt; use a fresh materialization')
    client = carla.Client(host, port)
    client.set_timeout(120)
    world = client.get_world()
    if world.get_map().name != survey['map_name']:
        raise ValueError('Live CARLA map differs from reviewed survey')
    settings = world.get_settings()
    old_sync, old_step = settings.synchronous_mode, settings.fixed_delta_seconds
    actors, encoders = [], {}
    pipeline_capture = None
    completed = False
    try:
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        world.apply_settings(settings)
        lib = world.get_blueprint_library()
        ego = world.try_spawn_actor(lib.find(survey['vehicle_blueprint']),
                                    transform(carla, survey['spawn_xyz_m'], [0, survey['spawn_yaw_deg'], 0]))
        if ego is None:
            raise RuntimeError('Surveyed truck spawn failed')
        actors.append(ego)
        pipeline_capture = PipelineCapture(client, ego, output, CASE, visibility=False,
                                           required_observations=[])
        queues = {}
        for spec in cfg['cameras']:
            camera = lib.find('sensor.camera.rgb')
            camera.set_attribute('image_size_x', str(spec['width']))
            camera.set_attribute('image_size_y', str(spec['height']))
            camera.set_attribute('fov', '80')
            mount = survey['camera_mounts'][spec['name']]
            sensor = world.spawn_actor(camera, transform(carla, mount['xyz_m'], mount['rotation_deg']), attach_to=ego)
            actors.append(sensor)
            q = queue.Queue()
            sensor.listen(q.put)
            queues[spec['name']] = q
            encoders[spec['name']] = subprocess.Popen(
                ['ffmpeg', '-v', 'error', '-f', 'rawvideo', '-pixel_format', 'bgra',
                 '-video_size', f"{spec['width']}x{spec['height']}", '-framerate', '20',
                 '-i', '-', '-frames:v', str(COUNT), '-c:v', 'ffv1',
                 str(output/(spec['name']+'.mkv'))], stdin=subprocess.PIPE)
        route = survey['route_waypoints_xyz_m']
        waypoint_index, first_elapsed = 1, None
        service_stop_count = 0
        service_stop_complete = False
        with (output/'video_frames.jsonl').open('w') as frame_file, (output/'native_route_trace.jsonl').open('w') as trace_file:
            for i in range(COUNT):
                pose = ego.get_transform()
                while waypoint_index < len(route)-1 and math.dist(
                        [pose.location.x, pose.location.y], route[waypoint_index][:2]) < 3.0:
                    if (waypoint_index == survey['enroute_service_waypoint_index'] and
                            not service_stop_complete):
                        break
                    waypoint_index += 1
                velocity = ego.get_velocity()
                speed = math.sqrt(velocity.x**2+velocity.y**2+velocity.z**2)
                at_service = (waypoint_index == survey['enroute_service_waypoint_index'] and
                              not service_stop_complete and
                              math.dist([pose.location.x, pose.location.y], route[waypoint_index][:2]) < 3.0)
                if at_service:
                    service_road = world.get_map().get_waypoint(pose.location, project_to_road=True,
                                                                lane_type=carla.LaneType.Driving)
                    if service_road is None or service_road.road_id != survey['intervening_street_id']:
                        raise RuntimeError('Surveyed service stop is not on intervening street')
                    service_stop_count += 1 if speed <= .1 else 0
                    if service_stop_count >= cfg['service_stop_frames']:
                        service_stop_complete = True
                        waypoint_index += 1
                ego.apply_control(carla.VehicleControl(
                    throttle=0.0 if at_service else max(0.0, min(.7, .35+.15*(6.0-speed))),
                    brake=min(1.0, max(.5, speed*.4)) if at_service else max(0.0, min(.5, .2*(speed-6.0))),
                    steer=0.0 if at_service else steering(ego, route[waypoint_index])))
                native_frame = world.tick()
                snapshot = world.get_snapshot()
                if snapshot.frame != native_frame:
                    raise RuntimeError('Native world frame mismatch')
                if first_elapsed is None:
                    first_elapsed = snapshot.timestamp.elapsed_seconds
                pose = ego.get_transform()
                velocity = ego.get_velocity()
                road = world.get_map().get_waypoint(pose.location, project_to_road=True,
                                                    lane_type=carla.LaneType.Driving)
                if road is None:
                    raise RuntimeError('Native vehicle left reviewed roadway')
                time_s = snapshot.timestamp.elapsed_seconds-first_elapsed
                pipeline_capture.capture(native_frame, time_s, extra={'truck_route_native_frame': native_frame})
                frame_file.write(json.dumps({'video_frame': i, 'native_frame': native_frame,
                                             'carla_frame': native_frame, 'time_s': time_s})+'\n')
                trace_file.write(json.dumps({'video_frame': i, 'native_frame': native_frame,
                                             'source_kind': 'original_native_pose',
                                             'ego_actor_id': ego.id, 'road_id': road.road_id,
                                             'ego_x_m': pose.location.x, 'ego_y_m': pose.location.y,
                                             'ego_speed_mps': math.sqrt(velocity.x**2+velocity.y**2+velocity.z**2),
                                             'service_stop_active': at_service})+'\n')
                for name, q in queues.items():
                    image = q.get(timeout=30)
                    if image.frame != native_frame:
                        raise RuntimeError('Camera frame does not join Native frame')
                    encoders[name].stdin.write(image.raw_data)
        if not service_stop_complete:
            raise RuntimeError('Original capture did not complete surveyed service stop')
        for proc in encoders.values():
            proc.stdin.close()
            if proc.wait(timeout=120):
                raise RuntimeError('Source camera encoding failed')
        completed = True
        (output/'route_context.template.json').write_text(json.dumps({
            'assignment_id': AID, 'case_id': CASE, 'review_kind': 'original_source_review',
            'entry_truck_route_id': survey['entry_truck_route_id'],
            'intervening_street_id': survey['intervening_street_id'],
            'exit_truck_route_id': survey['exit_truck_route_id'],
            'ego_actor_id': ego.id, 'vehicle_is_truck': None,
            'enroute_purpose': None, 'served_premises_source': survey['served_premises_source'],
            'service_stop_complete': service_stop_complete, 'service_stop_frames': service_stop_count,
            'camera_sha256': {}, 'review_required': True}, indent=2)+'\n')
        return {'case_id': CASE, 'source_frames': COUNT, 'physical_acceptance_claimed': False}
    finally:
        close_error = None
        if pipeline_capture is not None:
            try:
                pipeline_capture.close(confirmed=completed)
            except Exception as exc:
                close_error = exc
        for actor in reversed(actors):
            try:
                actor.destroy()
            except Exception:
                pass
        for proc in encoders.values():
            if proc.poll() is None:
                proc.kill()
                proc.wait()
        settings.synchronous_mode = old_sync
        settings.fixed_delta_seconds = old_step
        world.apply_settings(settings)
        if close_error is not None:
            raise close_error


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--survey', type=Path)
    parser.add_argument('--output-dir', type=Path)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args()
    cfg = config_check()
    if args.check:
        print(json.dumps({'case_id': CASE, 'frames': COUNT, 'cameras': list(CAMERAS),
                          'carla_imported': False, 'physical_acceptance_claimed': False}, sort_keys=True))
    else:
        if args.output_dir is None:
            parser.error('Supply --output-dir')
        survey_path = args.survey or (Path(os.environ['TRUCK_ROUTE_SURVEY']) if os.environ.get('TRUCK_ROUTE_SURVEY') else None)
        if survey_path is None:
            parser.error('Supply reviewed --survey or TRUCK_ROUTE_SURVEY')
        print(json.dumps(capture(json.loads(survey_path.read_text()), args.output_dir, args.host, args.port)))
