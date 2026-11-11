"""CARLA-lazy two-vehicle ending-road construction and original capture."""

import argparse
import json
from math import atan2, hypot, isfinite
from pathlib import Path

from ending_road_camera import CAMERAS, EndingRoadCameraCapture, LosslessSourceSink
from ending_road_device import devices_at_junction
from ending_road_route import select_t_routes
from ending_road_source_capture import EndingRoadSourceRecorder, topology_from_native, _body

ASSIGNMENT = 'heldout__C111294__NRS-484B-250-3__motor_vehicle_driver'
CASE = ASSIGNMENT + '__same_arrival_ending_yields'


def check_config(config):
    if (config.get('selected_case_id'), config.get('law_id'),
            config.get('cell_id'), config.get('actor')) != (
            CASE, 'NRS-484B-250-3', 'C111294', 'motor_vehicle_driver'):
        raise ValueError('Ending-road exact identity differs')
    if config.get('rate_hz') != 20 or config.get('frames', 0) < 80:
        raise ValueError('Ending-road capture requires at least four seconds at 20 Hz')
    cameras = config.get('cameras', [])
    if [camera.get('name') for camera in cameras] != list(CAMERAS) or any(
            [camera.get('width'), camera.get('height')] != list(CAMERAS[camera['name']][2])
            for camera in cameras):
        raise ValueError('Ending-road source cameras differ from capture profile')
    if config.get('yield_clearance_m', 0) <= 0:
        raise ValueError('Ending-road yield clearance must be positive')


def control_to_waypoint(actor, waypoint, speed_mps):
    """Simple bounded speed/heading controller; requested speed is not realized motion."""
    position = actor.get_transform().location
    heading = actor.get_transform().get_forward_vector()
    velocity = actor.get_velocity()
    target = waypoint.transform.location
    dx, dy = target.x - position.x, target.y - position.y
    norm = hypot(heading.x, heading.y)
    if hypot(dx, dy) < .2 or norm < 1e-6 or not all(map(isfinite,
            (dx, dy, heading.x, heading.y, velocity.x, velocity.y, speed_mps))):
        raise ValueError('Ending-road control has invalid target or Native state')
    angle = atan2((heading.x * dy - heading.y * dx) / norm,
                  (heading.x * dx + heading.y * dy) / norm)
    speed = hypot(velocity.x, velocity.y)
    return {'steer': max(-.5, min(.5, .8 * angle)),
            'throttle': max(0., min(.5, .22 * (speed_mps - speed))),
            'brake': max(0., min(.7, .25 * (speed - speed_mps)))}


def choose_control_targets(subject, other, routes, subject_started, clearance_m):
    """Hold the ending approach until the through vehicle has moved clear."""
    zone = routes['conflict_polygon_xy']
    xs, ys = [p[0] for p in zone], [p[1] for p in zone]
    body = _body(other)
    body_x, body_y = [p[0] for p in body], [p[1] for p in body]
    other_clear = (max(body_x) < min(xs) - clearance_m or
                   min(body_x) > max(xs) + clearance_m or
                   max(body_y) < min(ys) - clearance_m or
                   min(body_y) > max(ys) + clearance_m)
    # The through actor must first reach the intersection before clearance can
    # release the ending actor; the state is latched by the caller.
    go = subject_started or routes.get('other_seen_in_zone', False) and other_clear
    return routes['subject'][-1], routes['other'][-1], go


def conflict_polygon(subject_path, other_path, *, margin_m=3):
    points = [p.transform.location for p in subject_path + other_path if p.is_junction]
    if not points:
        raise ValueError('Ending-road Native routes lack junction geometry')
    xs, ys = [p.x for p in points], [p.y for p in points]
    return [[min(xs)-margin_m, min(ys)-margin_m],
            [max(xs)+margin_m, min(ys)-margin_m],
            [max(xs)+margin_m, max(ys)+margin_m],
            [min(xs)-margin_m, max(ys)+margin_m]]


def extend_exit(path, *, steps=12):
    """Give the controller a connected target beyond the junction conflict zone."""
    extended = list(path)
    for _ in range(steps):
        choices = [p for p in extended[-1].next(2.0)
                   if not p.is_junction and p.road_id == extended[-1].road_id]
        if not choices:
            raise ValueError('Native exit lane cannot be followed beyond intersection')
        extended.append(choices[0])
    return extended


def run(config, output, host='127.0.0.1', port=2000):
    check_config(config)
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap

    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    if any((output / name).exists() for name in
           ('intersection_topology.json', 'intersection_participants.jsonl',
            'trace.jsonl', 'video_frames.jsonl')):
        raise FileExistsError('Retain prior original ending-road acquisition')
    config_path = output / 'config.json'
    if config_path.exists():
        if json.loads(config_path.read_text()) != config:
            raise ValueError('Materialized ending-road config differs from selected case')
    else:
        config_path.write_text(json.dumps(config, indent=2) + '\n')
    client = carla.Client(host, port)
    client.set_timeout(30.)
    world = client.get_world()
    original = world.get_settings()
    actors, sinks = [], {}
    cameras = recorder = pipeline = frame_map = None
    try:
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        world.apply_settings(settings)
        lights = list(world.get_actors().filter('traffic.traffic_light*'))
        routes = select_t_routes(world.get_map(), route_accept=lambda ending, through:
                                 not devices_at_junction(lights, ending['junction_id']))
        subject_path = extend_exit(routes['subject'])
        other_path = extend_exit(routes['other'])
        routes['subject'], routes['other'] = subject_path, other_path
        blueprint = world.get_blueprint_library().find('vehicle.tesla.model3')
        subject = world.try_spawn_actor(blueprint, subject_path[0].transform)
        if subject is None:
            raise ValueError('Ending-road subject spawn failed')
        actors.append(subject)
        other = world.try_spawn_actor(blueprint, other_path[0].transform)
        if other is None:
            raise ValueError('Through-road actor spawn failed')
        actors.append(other)
        polygon = conflict_polygon(subject_path, other_path)
        routes['conflict_polygon_xy'] = polygon
        junction = next(point for point in subject_path if point.is_junction).get_junction()
        topology = topology_from_native(subject_path, other_path, subject,
                                        other, junction, polygon)
        recorder = EndingRoadSourceRecorder(output, topology, subject, other)
        pipeline = PipelineCapture(client, subject, output, CASE,
                                   required_observations=config.get('required_atoms', []))
        frame_map = FrameMap(output / 'video_frames.jsonl')
        for name in CAMERAS:
            sinks[name] = LosslessSourceSink(output, name)
        cameras = EndingRoadCameraCapture(world, carla, subject, sinks)
        frames, start = [], None
        subject_started = False
        for _ in range(config['frames']):
            subject_target, other_target, go = choose_control_targets(
                subject, other, routes, subject_started, config['yield_clearance_m'])
            subject_started = go
            subject.apply_control(carla.VehicleControl(**control_to_waypoint(
                subject, subject_target, 5 if go else 0)))
            other.apply_control(carla.VehicleControl(**control_to_waypoint(
                other, other_target, 5)))
            frame = world.tick()
            cameras.wait_for_frame(frame)
            snapshot = world.get_snapshot()
            if snapshot.frame != frame:
                raise ValueError('Ending-road Native frame mismatch')
            if start is None:
                start = snapshot.timestamp.elapsed_seconds
            time_s = snapshot.timestamp.elapsed_seconds - start
            trace = pipeline.capture(frame, time_s)
            if trace.get('frame') != frame or trace.get('time_s') != time_s:
                raise ValueError('Ending-road trace/frame mismatch')
            recorder.append(frame, time_s)
            x, y = other.get_transform().location.x, other.get_transform().location.y
            xs, ys = [p[0] for p in polygon], [p[1] for p in polygon]
            routes['other_seen_in_zone'] = routes.get('other_seen_in_zone', False) or (
                min(xs) <= x <= max(xs) and min(ys) <= y <= max(ys))
            frame_map.append(frame, time_s)
            frames.append(frame)
        cameras.verify(frames)
        (output / 'construction-observation.json').write_text(json.dumps({
            'format': 'worker-ending-road-construction-observation',
            'case_id': CASE, 'map_name': routes['map_name'], 'frames': frames,
            'through_seen_in_zone': routes.get('other_seen_in_zone', False),
            'ending_released': subject_started, 'physical_completion_claimed': False},
            indent=2) + '\n')
    finally:
        if frame_map is not None: frame_map.close()
        if recorder is not None: recorder.close()
        if pipeline is not None: pipeline.close(confirmed=False)
        if cameras is not None: cameras.close()
        for sink in sinks.values(): sink.close()
        for actor in reversed(actors): actor.destroy()
        world.apply_settings(original)
        restored = world.get_settings()
        if (restored.synchronous_mode != original.synchronous_mode or
                restored.fixed_delta_seconds != original.fixed_delta_seconds):
            raise ValueError('Ending-road world settings restore failed')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', default='config.json')
    parser.add_argument('--output-dir')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    parser.add_argument('--run', action='store_true')
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    config = json.loads(Path(args.config).read_text())
    check_config(config)
    if not args.check:
        if not args.output_dir: raise ValueError('Fresh Native output directory required')
        run(config, args.output_dir, args.host, args.port)


if __name__ == '__main__':
    main()
