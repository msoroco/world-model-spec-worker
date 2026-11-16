"""CARLA-lazy one-way capture from reviewed Native lanes and retained sources."""
import argparse
import json
import math
from contextlib import ExitStack
from pathlib import Path
from queue import Empty, Queue

from camera_encoder import FFV1Writer
from camera_setup import PROFILE, source_cameras
from direction_control import RouteFollower
from native_one_way import prepare_reviewed_route

ASSIGNMENT = 'testing__C147311__NRS-484B-220-1__motor_vehicle_driver'
WITH = ASSIGNMENT + '__source_verified_with_designation'
AGAINST = ASSIGNMENT + '__source_verified_against_designation'
CAMERAS = tuple(PROFILE)


def validate_config(config):
    if (config.get('law_id'), config.get('cell_id'), config.get('actor')) != (
            'NRS-484B-220-1', 'C147311', 'motor_vehicle_driver'):
        raise ValueError('Exact one-way law/cell/actor required')
    if config.get('selected_case_id') not in (WITH, AGAINST):
        raise ValueError('Exact selected direction case required')
    if set(config.get('supported_case_ids', [])) != {WITH, AGAINST}:
        raise ValueError('Both exact direction cases required')
    if config.get('rate_hz') != 20 or config.get('duration_s') != 45:
        raise ValueError('Pinned 20 Hz and 45-second capture required')
    if config.get('site_packet') != 'site_packet.json':
        raise ValueError('Exact site packet required')
    cameras = config.get('cameras')
    if not isinstance(cameras, list) or [r.get('name') for r in cameras] != list(CAMERAS):
        raise ValueError('Four ordered source cameras required')
    if any((r.get('width'), r.get('height')) != PROFILE[r['name']] or
           type(r.get('fov_deg')) not in (int, float) or not 30 <= r['fov_deg'] <= 120
           for r in cameras):
        raise ValueError('Camera size/FOV invalid')
    if not isinstance(config.get('required_atoms'), list):
        raise ValueError('Required atom inventory missing')
    return config


def prepare_site(world, packet, root, config):
    prepared = prepare_reviewed_route(world, packet, root,
                                      travel_lane_id=packet['travel_lane_id'])
    route = prepared['routes']['with_designation_xy_m' if config['selected_case_id'] == WITH
                               else 'against_designation_xy_m']
    if len(route) < 2:
        raise ValueError('Native travel route incomplete')
    return prepared, route


def _body(actor):
    points = [[float(v.x), float(v.y)] for v in
              actor.bounding_box.get_world_vertices(actor.get_transform())]
    if len(points) < 4 or any(not all(math.isfinite(c) for c in point) for point in points):
        raise ValueError('Incomplete Native complete body')
    return points


def _sensor_frame(queue, frame):
    for _ in range(6):
        try:
            image = queue.get(timeout=10)
        except Empty as error:
            raise ValueError('Source camera frame missing') from error
        if image.frame == frame:
            return image
        if image.frame > frame:
            raise ValueError('Source camera skipped Native frame')
    raise ValueError('Source camera frame join failed')


def _record(actor, snapshot, world, packet):
    transform = actor.get_transform(); yaw = float(transform.rotation.yaw)
    if not math.isfinite(yaw):
        raise ValueError('Nonfinite Native heading')
    waypoint = world.get_map().get_waypoint(transform.location, project_to_road=False)
    if waypoint is None or waypoint.road_id != packet['road_id']:
        raise ValueError('Native vehicle left selected road')
    velocity = actor.get_velocity()
    return {'frame': int(snapshot.frame), 'time_s': float(snapshot.timestamp.elapsed_seconds),
            'road_id': waypoint.road_id, 'lane_id': waypoint.lane_id,
            'ego_body_vertices_xy_m': _body(actor),
            'ego_forward_xy': [math.cos(math.radians(yaw)), math.sin(math.radians(yaw))],
            'body_vertices_m': _body(actor), 'heading_deg': yaw,
            'velocity_mps': [float(velocity.x), float(velocity.y)],
            'actor_id': int(actor.id)}


def _camera_transforms(carla, packet, first, yaw):
    x, y = first; z = packet['start_z_m']
    sign = packet['signs'][0]['location_xy_m']
    def pose(px, py, pz, heading, pitch):
        return carla.Transform(carla.Location(x=px, y=py, z=pz),
                               carla.Rotation(yaw=heading, pitch=pitch))
    return {'overview': pose(15, y, z+30, yaw, -75),
            'approach': pose(x-8, y, z+6, yaw, -15),
            'reference_corner': pose(sign[0]+6, sign[1]+6, z+8, yaw-135, -30),
            'driver_reference': pose(1, 0, 1.65, 0, -5)}


def capture(args, config):
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture
    from worker_exchange.world_restore import snapshot as snapshot_world, restore
    output = Path(args.output_dir).resolve()
    if not output.is_dir() or not (output/'construction.json').is_file():
        raise ValueError('Use runtime.py capture to materialize exact construction first')
    packet = json.loads((output/'site_packet.json').read_text())
    client = carla.Client(args.host, args.port); client.set_timeout(30)
    saved = snapshot_world(client); world = client.get_world(); actor = None; helper = None
    encoders = {}; frames = 0; error = None
    try:
        prepared, route = prepare_site(world, packet, output, config)
        settings = world.get_settings(); settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05; world.apply_settings(settings)
        direction = packet['designated_forward_xy']
        yaw = math.degrees(math.atan2(direction[1], direction[0]))
        if config['selected_case_id'] == AGAINST:
            yaw = (yaw + 180) % 360
        location = carla.Location(x=route[0][0], y=route[0][1], z=packet['start_z_m'])
        waypoint = world.get_map().get_waypoint(location, project_to_road=False)
        if waypoint is None or (waypoint.road_id, waypoint.lane_id) != (packet['road_id'], packet['travel_lane_id']):
            raise ValueError('Selected Native lane start differs')
        blueprint = world.get_blueprint_library().find(packet['vehicle_blueprint_id'])
        actor = world.try_spawn_actor(blueprint, carla.Transform(location, carla.Rotation(yaw=yaw)))
        if actor is None:
            raise ValueError('Native one-way vehicle spawn failed')
        follower = RouteFollower(route, target_speed_mps=config['requested_speed_mps'])
        (output/'road_context.json').write_text(json.dumps({
            'native_map_id': packet['native_map_id'], 'highway_id': packet['highway_id'],
            'road_id': packet['road_id'], 'driving_lane_ids': packet['driving_lane_ids'],
            'designated_forward_xy': packet['designated_forward_xy'],
            'one_way_roadway_polygon_xy_m': packet['one_way_roadway_polygon_xy_m'],
            'one_way_designation_source': packet['designation_source']['path'],
            'direction_sign_source': packet['signs'][0]['source']['path'],
            'lane_geometry_source': 'original Native waypoint chain',
            'travel_route_source': 'paired original Native waypoint route',
            'site_source_review': prepared['site_review']}, indent=2)+'\n')
        transforms = _camera_transforms(carla, packet, route[0], yaw)
        with source_cameras(world, actor, transforms, config['cameras']) as sensors:
            queues = {name: Queue() for name in CAMERAS}
            for name, sensor in sensors.items():
                sensor.listen(lambda image, name=name: queues[name].put(image))
            with ExitStack() as stack:
                for name, (width, height) in PROFILE.items():
                    encoders[name] = stack.enter_context(FFV1Writer(output/(name+'.mkv'), width, height))
                mapping = stack.enter_context(FrameMap(output/'video_frames.jsonl'))
                history = stack.enter_context((output/'travel_history.jsonl').open('x', buffering=1))
                helper = PipelineCapture(client, actor, output, config['selected_case_id'],
                                         required_observations=config['required_atoms'])
                try:
                    for _ in range(config['duration_s']*config['rate_hz']):
                        pose = actor.get_transform(); velocity = actor.get_velocity()
                        forward = [math.cos(math.radians(pose.rotation.yaw)),
                                   math.sin(math.radians(pose.rotation.yaw))]
                        command = follower.step([pose.location.x, pose.location.y], forward,
                                                math.hypot(float(velocity.x), float(velocity.y)))
                        actor.apply_control(carla.VehicleControl(throttle=command['throttle'],
                                          brake=command['brake'], steer=command['steer']))
                        world.tick(); snapshot = world.get_snapshot()
                        for name in CAMERAS:
                            encoders[name].write(bytes(_sensor_frame(queues[name], snapshot.frame).raw_data))
                        helper.capture(snapshot.frame, snapshot.timestamp.elapsed_seconds)
                        mapping.append(snapshot.frame, snapshot.timestamp.elapsed_seconds)
                        history.write(json.dumps(_record(actor, snapshot, world, packet),
                                                 separators=(',', ':'))+'\n')
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
                         context={'site_source_check': prepared['site_review'],
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
    if not args.output_dir: raise ValueError('--output-dir required for Native capture')
    capture(args, config)


if __name__ == '__main__': main()
