"""CARLA-lazy two-directional left-turn capture for one exact destination exit."""
import argparse
import json
import math
from contextlib import ExitStack
from pathlib import Path
from queue import Empty, Queue

from camera_encoder import FFV1Writer
from camera_setup import PROFILE, source_cameras
from departure_route import plan
from turn_control import RouteFollower

ASSIGNMENT = 'testing__C109705__NRS-484B-400-2b__motor_vehicle_driver'
CASES = tuple(ASSIGNMENT + '__source_verified_' + suffix for suffix in (
    'near_centerline', 'farther_from_centerline',
    'imaginary_near_centerline', 'imaginary_farther_from_centerline'))
CAMERAS = tuple(PROFILE)


def validate_config(config):
    if (config.get('law_id'), config.get('cell_id'), config.get('actor')) != (
            'NRS-484B-400-2b', 'C109705', 'motor_vehicle_driver'):
        raise ValueError('Exact law, cell and actor required')
    case_id = config.get('selected_case_id')
    if case_id not in CASES or set(config.get('supported_case_ids', [])) != set(CASES):
        raise ValueError('Four exact destination exit cases required')
    if config.get('rate_hz') != 20 or config.get('duration_s') != 45:
        raise ValueError('Pinned 20 Hz, 45 second capture required')
    if config.get('site_packet') != 'site_packet.json':
        raise ValueError('Exact site packet required')
    if not isinstance(config.get('required_atoms'), list):
        raise ValueError('Required observation atoms missing')
    if (type(config.get('requested_speed_mps')) not in (int, float) or
            not 0 < config['requested_speed_mps'] <= 8):
        raise ValueError('Bounded turn speed required')
    cameras = config.get('cameras')
    if not isinstance(cameras, list) or [row.get('name') for row in cameras] != list(CAMERAS):
        raise ValueError('Four ordered original cameras required')
    if any((row.get('width'), row.get('height')) != PROFILE[row['name']] or
           type(row.get('fov_deg')) not in (int, float) or
           not 30 <= row['fov_deg'] <= 120 for row in cameras):
        raise ValueError('Camera dimensions or field of view invalid')
    return config


def prepare_site(world, packet, root, config):
    case_id = config['selected_case_id']
    expected_kind = 'imaginary' if 'imaginary_' in case_id else 'marked'
    if packet.get('centerline_kind') != expected_kind:
        raise ValueError('Selected case centerline kind differs from sourced site')
    connector = packet.get('connector_road_id')
    roads = (packet.get('approach_road_id'), connector, packet.get('outgoing_road_id'))
    if type(connector) is not int or len(set(roads)) != 3:
        raise ValueError('Distinct sourced connector road identity required')
    if connector not in {int(w.road_id) for w in world.get_map().generate_waypoints(2.0)}:
        raise ValueError('Native connector road missing from selected map')
    direction = packet.get('departure_direction_xy')
    if (not isinstance(direction, list) or len(direction) != 2 or
            any(type(v) not in (int, float) or not math.isfinite(v) for v in direction) or
            math.hypot(*direction) <= 0):
        raise ValueError('Sourced finite departure direction required')
    return plan(world, packet, root, farther=('farther_' in case_id))


def _body(actor):
    vertices = [[float(v.x), float(v.y)] for v in
                actor.bounding_box.get_world_vertices(actor.get_transform())]
    if len(vertices) < 4 or any(not all(math.isfinite(v) for v in pair) for pair in vertices):
        raise ValueError('Incomplete Native vehicle body')
    return vertices


def _body_3d(actor):
    vertices = [[float(v.x), float(v.y), float(v.z)] for v in
                actor.bounding_box.get_world_vertices(actor.get_transform())]
    if len(vertices) < 4 or any(not all(math.isfinite(n) for n in v) for v in vertices):
        raise ValueError('Incomplete original full-body vertices')
    return vertices


def _sensor_frame(queue, frame):
    for _ in range(6):
        try:
            image = queue.get(timeout=10)
        except Empty as error:
            raise ValueError('Original source camera frame missing') from error
        if image.frame == frame:
            return image
        if image.frame > frame:
            raise ValueError('Original source camera skipped Native frame')
    raise ValueError('Original camera frame join failed')


def _record(actor, snapshot, world):
    pose = actor.get_transform()
    waypoint = world.get_map().get_waypoint(pose.location, project_to_road=False)
    if waypoint is None:
        raise ValueError('Native road identity missing for vehicle body')
    velocity = actor.get_velocity()
    return {'frame': int(snapshot.frame), 'time_s': float(snapshot.timestamp.elapsed_seconds),
            'road_id': int(waypoint.road_id), 'lane_id': int(waypoint.lane_id),
            'ego_body_vertices_xy_m': _body(actor),
            'heading_deg': float(pose.rotation.yaw),
            'velocity_mps': [float(velocity.x), float(velocity.y)],
            'actor_id': int(actor.id)}


def _camera_transforms(carla, packet, route, yaw):
    start, corner, exit_point = route[0], route[3], route[-1]
    z = packet['start_z_m']
    def pose(x, y, height, heading, pitch):
        return carla.Transform(carla.Location(x=x, y=y, z=z+height),
                               carla.Rotation(yaw=heading, pitch=pitch))
    return {'overview': pose(corner[0]+12, corner[1]+12, 30, yaw-135, -75),
            'approach': pose(start[0]-6, start[1]+4, 7, yaw, -20),
            'reference_corner': pose(exit_point[0]+8, corner[1]+5, 8, yaw+120, -35),
            'driver_reference': pose(1, 0, 1.65-z, 0, -5)}


def capture(args, config):
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture
    from worker_exchange.world_restore import snapshot as snapshot_world, restore
    output = Path(args.output_dir).resolve()
    if not output.is_dir() or not (output/'construction.json').is_file():
        raise ValueError('Materialize the exact construction with runtime.py capture')
    packet = json.loads((output/'site_packet.json').read_text())
    client = carla.Client(args.host, args.port); client.set_timeout(30)
    saved = snapshot_world(client); world = client.get_world(); actor = None; helper = None
    encoders = {}; frames = 0; error = None; prepared = None
    try:
        prepared = prepare_site(world, packet, output, config)
        route = prepared['route_xy_m']
        settings = world.get_settings(); settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05; world.apply_settings(settings)
        direction = [route[1][i]-route[0][i] for i in (0, 1)]
        yaw = math.degrees(math.atan2(direction[1], direction[0]))
        location = carla.Location(x=route[0][0], y=route[0][1], z=packet['start_z_m'])
        waypoint = world.get_map().get_waypoint(location, project_to_road=False)
        if waypoint is None or (waypoint.road_id, waypoint.lane_id) != (
                packet['approach_road_id'], packet['approach_lane_id']):
            raise ValueError('Native approach spawn lane differs from selected turn lane')
        blueprint = world.get_blueprint_library().find(packet['vehicle_blueprint_id'])
        actor = world.try_spawn_actor(blueprint, carla.Transform(location, carla.Rotation(yaw=yaw)))
        if actor is None:
            raise ValueError('Native left-turn vehicle spawn failed')
        follower = RouteFollower(route, target_speed_mps=config['requested_speed_mps'])
        review = prepared['source_review']
        (output/'road_context.json').write_text(json.dumps({
            'native_map_id': packet['native_map_id'], 'intersection_id': packet['intersection_id'],
            'approach_road_id': packet['approach_road_id'],
            'outgoing_road_id': packet['outgoing_road_id'],
            'opposing_lane_source': 'original Native waypoint inventory',
            'destination_centerline_source': review['sources']['destination_centerline_source']['path'],
            'destination_right_half_source': review['sources']['destination_right_half_source']['path'],
            'junction_source': review['sources']['junction_source']['path'],
            'left_turn_route_source': 'reviewed authored Native waypoint route',
            'both_highways_two_directional': True,
            'two_directional_basis': 'opposing original Native driving lanes on both roads; legal road status unresolved',
            'intended_turn': 'left',
            'destination_centerline_xy_m': packet['destination_centerline_xy_m'],
            'destination_right_half_polygon_xy_m': packet['destination_right_half_polygon_xy_m'],
            'junction_polygon_xy_m': packet['junction_polygon_xy_m'],
            'site_source_review': review}, indent=2)+'\n')
        (output/'road_geometry.json').write_text(json.dumps({
            'intersection_xy_m': packet['junction_polygon_xy_m'],
            'approach_road_id': packet['approach_road_id'],
            'connector_road_id': packet['connector_road_id'],
            'departure_road_id': packet['outgoing_road_id'],
            'departure_direction_xy': packet['departure_direction_xy'],
            'two_way': True, 'site_source_review': review}, indent=2)+'\n')
        transforms = _camera_transforms(carla, packet, route, yaw)
        with source_cameras(world, actor, transforms, config['cameras']) as sensors:
            queues = {name: Queue() for name in CAMERAS}
            for name, sensor in sensors.items():
                sensor.listen(lambda image, name=name: queues[name].put(image))
            with ExitStack() as stack:
                for name, (width, height) in PROFILE.items():
                    encoders[name] = stack.enter_context(FFV1Writer(output/(name+'.mkv'), width, height))
                mapping = stack.enter_context(FrameMap(output/'video_frames.jsonl'))
                history = stack.enter_context((output/'turn_history.jsonl').open('x', buffering=1))
                body_history = stack.enter_context((output/'body_history.jsonl').open('x', buffering=1))
                helper = PipelineCapture(client, actor, output, config['selected_case_id'],
                                         required_observations=config['required_atoms'])
                try:
                    for _ in range(config['duration_s']*config['rate_hz']):
                        pose = actor.get_transform(); velocity = actor.get_velocity()
                        heading = [math.cos(math.radians(pose.rotation.yaw)),
                                   math.sin(math.radians(pose.rotation.yaw))]
                        command = follower.step([pose.location.x, pose.location.y], heading,
                                                math.hypot(float(velocity.x), float(velocity.y)))
                        actor.apply_control(carla.VehicleControl(throttle=command['throttle'],
                                            brake=command['brake'], steer=command['steer']))
                        world.tick(); snapshot = world.get_snapshot()
                        for name in CAMERAS:
                            encoders[name].write(bytes(_sensor_frame(queues[name], snapshot.frame).raw_data))
                        helper.capture(snapshot.frame, snapshot.timestamp.elapsed_seconds)
                        mapping.append(snapshot.frame, snapshot.timestamp.elapsed_seconds)
                        record = _record(actor, snapshot, world)
                        history.write(json.dumps(record, separators=(',', ':'))+'\n')
                        body_history.write(json.dumps({
                            'frame': record['frame'], 'time_s': record['time_s'],
                            'road_id': record['road_id'], 'lane_id': record['lane_id'],
                            'body_vertices_m': _body_3d(actor)}, separators=(',', ':'))+'\n')
                        frames += 1
                finally:
                    helper.close(); helper = None
    except BaseException as caught:
        error = caught; raise
    finally:
        cleanup = []
        if helper is not None:
            try: helper.close(confirmed=False)
            except BaseException as caught: cleanup.append(str(caught))
        if actor is not None:
            try: actor.destroy()
            except BaseException as caught: cleanup.append(str(caught))
        restoration = restore(client, saved)
        if error is None and not cleanup:
            seal_capture(output, frames=frames, restoration=restoration, errors=[],
                         encoder_exit_codes={name: e.exit_code for name, e in encoders.items()},
                         context={'site_source_check': prepared['source_review'],
                                  'physical_acceptance_claimed': False})
        if error is None and cleanup:
            raise ValueError('Native cleanup failed: '+'; '.join(cleanup))


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--check', action='store_true')
    parser.add_argument('--output-dir'); parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000); args = parser.parse_args()
    config = validate_config(json.loads(Path(__file__).with_name('config.json').read_text()))
    if args.check:
        print(json.dumps({'case_id': config['selected_case_id'], 'cpu_check_passed': True,
                          'carla_started': False})); return
    if not args.output_dir:
        raise ValueError('--output-dir required for Native capture')
    capture(args, config)


if __name__ == '__main__': main()
