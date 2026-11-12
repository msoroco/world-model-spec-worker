"""Native center-lane passing with nearby center traffic for the C304406 three-lane law package.

Physical lane markings and complete visual coverage remain review items.
"""

import argparse
import json
from math import atan2, hypot
from pathlib import Path

from three_lane_route import select_route, ordered_lanes
from three_lane_passing import passing_target, center_clearance
from three_lane_source_capture import ThreeLaneSourceRecorder
from three_lane_camera import CAMERAS, LosslessSourceSink, ThreeLaneCameraCapture


PREFIX = 'heldout__C304406__NRS-484B-223-2__motor_vehicle_driver__'
CASES = {'center_passing_near_traffic': 'center'}
CASE = PREFIX + 'center_passing_near_traffic'


def check_config(config):
    if (config.get('selected_case_id') not in {PREFIX + name for name in CASES} or
            config.get('law_id') != 'NRS-484B-223-2' or
            config.get('cell_id') != 'C304406' or
            config.get('actor') != 'motor_vehicle_driver' or
            config.get('lane_role') != CASES.get(config.get('selected_case_id', '').removeprefix(PREFIX))):
        raise ValueError('Wrong exact three-lane baseline identity')
    if config.get('rate_hz') != 20 or config.get('frames', 0) < 80 or (
            config.get('duration_s') != config.get('frames') / 20):
        raise ValueError('Three-lane baseline needs 20 Hz fixed duration')
    cameras = config.get('cameras')
    if not isinstance(cameras, list) or {
            camera.get('name') for camera in cameras} != set(CAMERAS):
        raise ValueError('Four named three-lane source cameras required')


def control_step(position_xy, heading_xy, velocity_xy, target_xy,
                 *, target_speed_mps=5):
    dx, dy = target_xy[0] - position_xy[0], target_xy[1] - position_xy[1]
    if hypot(dx, dy) < 0.2:
        raise ValueError('Three-lane route target too close')
    hx, hy = heading_xy
    norm = hypot(hx, hy)
    if norm < 1e-6:
        raise ValueError('Three-lane actor heading undefined')
    hx, hy = hx / norm, hy / norm
    error = atan2(hx * dy - hy * dx, hx * dx + hy * dy)
    speed = hypot(*velocity_xy)
    return {'throttle': max(0, min(0.45, 0.22 * (target_speed_mps - speed))),
            'steer': max(-0.55, min(0.55, 0.8 * error)),
            'brake': max(0, min(0.4, 0.16 * (speed - target_speed_mps)))}


def run(config, output, host, port):
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap

    check_config(config)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    (output / 'config.json').write_text(json.dumps(config, indent=2) + '\n')
    client = carla.Client(host, port)
    client.set_timeout(30)
    world = client.get_world()
    original = world.get_settings()
    owned = []
    recorder = cameras = pipeline = frame_map = None
    sinks = {}
    try:
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 0.05
        world.apply_settings(settings)
        right_route = select_route(world.get_map(), direction=config.get('travel_direction', 'east'),
                                   steps=config.get('route_steps', 40))
        route = [ordered_lanes(right)[config['lane_role']] for right in right_route]
        ego = world.try_spawn_actor(
            world.get_blueprint_library().find(config.get('ego_blueprint', 'vehicle.tesla.model3')),
            route[0].transform)
        if ego is None:
            raise ValueError('Native three-lane subject spawn failed')
        owned.append(ego)
        target_waypoint = passing_target(right_route,
            target_ahead_m=config.get('target_ahead_m', 18.0),
            route_clear_m=config.get('clear_target_m', 65.0))
        slower = world.try_spawn_actor(
            world.get_blueprint_library().find(config.get('target_blueprint', 'vehicle.audi.tt')),
            target_waypoint.transform)
        if slower is None:
            raise ValueError('Native right-lane passing target spawn failed')
        owned.append(slower)
        blocker_waypoint = ordered_lanes(right_route[25])['center']
        blocker = world.try_spawn_actor(
            world.get_blueprint_library().find(config.get('blocker_blueprint', 'vehicle.audi.tt')),
            blocker_waypoint.transform)
        if blocker is None:
            raise ValueError('Native center-lane near-traffic blocker spawn failed')
        owned.append(blocker)
        passing_path = output / 'passing_frames.jsonl'
        if passing_path.exists():
            raise FileExistsError('Original passing source already exists')
        recorder = ThreeLaneSourceRecorder(output, right_route[0], ego)
        pipeline = PipelineCapture(client, ego, output, config['selected_case_id'],
                                   required_observations=config.get('required_atoms', []))
        frame_map = FrameMap(output / 'video_frames.jsonl')
        for name in CAMERAS:
            sinks[name] = LosslessSourceSink(output, name)
        cameras = ThreeLaneCameraCapture(world, carla, ego, sinks)
        frames = []
        start = None
        for index in range(config['frames']):
            transform = ego.get_transform()
            position = transform.location
            forward = transform.get_forward_vector()
            velocity = ego.get_velocity()
            target = route[min(2 + index // 8, len(route) - 1)].transform.location
            command = control_step((position.x, position.y),
                                   (forward.x, forward.y),
                                   (velocity.x, velocity.y), (target.x, target.y),
                                   target_speed_mps=config.get('ego_target_speed_mps', 8.0))
            ego.apply_control(carla.VehicleControl(**command))
            slower.apply_control(carla.VehicleControl(throttle=0.04))
            blocker.apply_control(carla.VehicleControl(brake=1.0))
            frame = world.tick()
            cameras.wait_for_frame(frame)
            snapshot = world.get_snapshot()
            if snapshot.frame != frame:
                raise ValueError('Native three-lane snapshot/frame mismatch')
            if start is None:
                start = snapshot.timestamp.elapsed_seconds
            time_s = snapshot.timestamp.elapsed_seconds - start
            trace = pipeline.capture(frame, time_s)
            if trace.get('frame') != frame or trace.get('time_s') != time_s:
                raise ValueError('Native three-lane trace/frame mismatch')
            current = world.get_map().get_waypoint(ego.get_location())
            current_right = current if config['lane_role'] == 'right' else current.get_right_lane()
            if current_right is None:
                raise ValueError('Native center-lane body lost adjacent right lane')
            ordered_lanes(current_right)
            recorder.append(frame, time_s, current_right)
            lane = ordered_lanes(current_right)
            def xy(actor):
                location = actor.get_location()
                return [float(location.x), float(location.y)]
            vehicles = []
            for actor in world.get_actors().filter('vehicle.*'):
                if actor.id == ego.id:
                    continue
                extent = actor.bounding_box.extent
                vehicles.append({'actor_id': str(actor.id), 'center_xy': xy(actor),
                                 'half_length_m': float(extent.x),
                                 'half_width_m': float(extent.y)})
            right_xy = [
                float(current_right.transform.location.x),
                float(current_right.transform.location.y)]
            center_xy = [float(lane['center'].transform.location.x),
                         float(lane['center'].transform.location.y)]
            clear = center_clearance(right_xy,
                    [float(v) for v in (current_right.transform.get_forward_vector().x,
                                         current_right.transform.get_forward_vector().y)],
                    center_xy, vehicles, clear_m=config.get('clear_target_m', 65.0))
            if clear['engineering_interval_clear'] or not any(
                    row['actor_id'] == str(blocker.id) for row in clear['blocked_actors']):
                raise ValueError('Native center near-traffic blocker not in measured interval')
            vertices = slower.bounding_box.get_world_vertices(slower.get_transform())
            if len(vertices) < 4:
                raise ValueError('Original passing target body missing')
            source = {'frame': frame, 'time_s': time_s,
                      'ego_actor_id': str(ego.id), 'target_actor_id': str(slower.id),
                      'ego_center_xy': xy(ego), 'target_center_xy': xy(slower),
                      'target_corners_xy': [[float(v.x), float(v.y)] for v in vertices[:4]],
                      'right_lane_center_xy': right_xy,
                      'center_lane_center_xy': center_xy,
                      'other_vehicle_bodies': vehicles,
                      'clear_target_m': config.get('clear_target_m', 65.0)}
            with passing_path.open('a') as stream:
                stream.write(json.dumps(source, allow_nan=False) + '\n')
            frame_map.append(frame, time_s)
            frames.append(frame)
        cameras.verify(frames)
    finally:
        if frame_map is not None:
            frame_map.close()
        if pipeline is not None:
            pipeline.close(confirmed=False)
        if cameras is not None:
            cameras.close()
        for sink in sinks.values():
            sink.close()
        for actor in reversed(owned):
            actor.destroy()
        world.apply_settings(original)
        restored = world.get_settings()
        if (restored.synchronous_mode != original.synchronous_mode or
                restored.fixed_delta_seconds != original.fixed_delta_seconds):
            raise ValueError('Native three-lane world settings restore failed')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--run', action='store_true')
    parser.add_argument('--config', default='config.json')
    parser.add_argument('--output')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args()
    config = json.loads(Path(args.config).read_text())
    check_config(config)
    if args.run:
        if not args.output:
            raise ValueError('Fresh Native output directory required')
        run(config, args.output, args.host, args.port)


if __name__ == '__main__':
    main()
