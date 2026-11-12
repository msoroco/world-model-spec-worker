"""Native extreme-left counterflow case for the C304406 three-lane law package.

Physical lane markings and complete visual coverage remain review items.
"""

import argparse
import json
from math import atan2, hypot
from pathlib import Path

from three_lane_route import select_route, ordered_lanes
from three_lane_source_capture import ThreeLaneSourceRecorder
from three_lane_camera import CAMERAS, LosslessSourceSink, ThreeLaneCameraCapture


PREFIX = 'heldout__C304406__NRS-484B-223-2__motor_vehicle_driver__'
CASES = {'extreme_left': 'extreme_left'}
CASE = PREFIX + 'extreme_left'


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
        # Preserve the right-lane travel heading while placing the body in the extreme left.
        # A mapped opposite-direction far-left lane would otherwise rotate the actor westward.
        spawn = carla.Transform(route[0].transform.location, right_route[0].transform.rotation)
        ego = world.try_spawn_actor(
            world.get_blueprint_library().find(config.get('ego_blueprint', 'vehicle.tesla.model3')),
            spawn)
        if ego is None:
            raise ValueError('Native three-lane subject spawn failed')
        owned.append(ego)
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
                                   (velocity.x, velocity.y), (target.x, target.y))
            ego.apply_control(carla.VehicleControl(**command))
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
            # The extreme-left mapped lane may face against the subject. Resolve the
            # right reference from the original connected corridor by longitudinal
            # position, then retain the original body polygon separately.
            location = ego.get_location()
            current_right = min(right_route, key=lambda waypoint: hypot(
                waypoint.transform.location.x - location.x,
                waypoint.transform.location.y - right_route[0].transform.location.y))
            if hypot(current_right.transform.location.x - location.x,
                     current_right.transform.location.y - right_route[0].transform.location.y) > 2.5:
                raise ValueError('Native extreme-left body left selected corridor')
            ordered_lanes(current_right)
            recorder.append(frame, time_s, current_right)
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
