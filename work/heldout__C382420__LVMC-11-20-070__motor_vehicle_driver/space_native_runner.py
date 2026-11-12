"""Native source capture for actual crosswalk or intersection entry.

This is a capture attempt, not a finding of sufficient space or obstruction.
The selected map must contain a connected junction and an actual marked
crosswalk.  A standing vehicle is physically spawned for blocked cases.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from space_construction import connected_entry_route, choose_region

PREFIX = 'heldout__C382420__LVMC-11-20-070__motor_vehicle_driver__'
CASES = {
    'crosswalk_clear_downstream': ('marked_crosswalk', False),
    'crosswalk_blocked_downstream': ('marked_crosswalk', True),
    'intersection_clear_downstream': ('intersection', False),
    'intersection_blocked_downstream': ('intersection', True),
}


def check_config(config):
    if (config.get('law_id'), config.get('cell_id'), config.get('actor')) != (
            'LVMC-11-20-070', 'C382420', 'motor_vehicle_driver'):
        raise ValueError('Wrong frozen crosswalk/intersection scope')
    case = config.get('selected_case_id', '')
    suffix = case.removeprefix(PREFIX)
    if case != PREFIX + suffix or suffix not in CASES or config.get('case', {}).get('case_id') != case:
        raise ValueError('Unknown exact entry case')
    if config.get('rate_hz') != 20 or config.get('frames') != 160 or len(config.get('cameras', [])) != 4:
        raise ValueError('Four-view 20 Hz entry capture contract missing')
    if not .1 <= float(config.get('ego_throttle', .22)) <= .35:
        raise ValueError('Unsafe or ineffective ego controller setting')
    if not 2 <= float(config.get('blocker_offset_m', 3.0)) <= 6:
        raise ValueError('Downstream physical blocker offset outside engineered range')
    return CASES[suffix]


def ground_corners(actor):
    vertices = list(actor.bounding_box.get_world_vertices(actor.get_transform()))
    if len(vertices) != 8:
        raise ValueError('Original Native actor body lacks eight vertices')
    lower = sorted(vertices, key=lambda point: point.z)[:4]
    cx = sum(point.x for point in lower) / 4
    cy = sum(point.y for point in lower) / 4
    lower.sort(key=lambda point: math.atan2(point.y - cy, point.x - cx))
    return [[float(point.x), float(point.y)] for point in lower]


def steer_to(ego, target, throttle):
    pose = ego.get_transform()
    current = math.radians(pose.rotation.yaw)
    desired = math.atan2(target.y - pose.location.y, target.x - pose.location.x)
    error = math.atan2(math.sin(desired - current), math.cos(desired - current))
    return {'throttle': throttle, 'brake': 0.0,
            'steer': max(-1.0, min(1.0, error / math.radians(45)))}


def _corridor(origin, direction, length, width):
    right = (-direction[1], direction[0])
    end = [origin[0] + direction[0] * length, origin[1] + direction[1] * length]
    return [[origin[0] + right[0] * width, origin[1] + right[1] * width],
            [end[0] + right[0] * width, end[1] + right[1] * width],
            [end[0] - right[0] * width, end[1] - right[1] * width],
            [origin[0] - right[0] * width, origin[1] - right[1] * width]]


def receiving_geometry(route, region):
    """Retain an original receiving-lane axis and map-boundary polygon."""
    from shapely.geometry import Point, Polygon
    boundary = Polygon(region)
    receiving = next((item for item in route if not item.is_junction
                      and not boundary.contains(Point(item.transform.location.x,
                                                          item.transform.location.y))
                      and item == route[-1]), None)
    if receiving is None:
        raise ValueError('Connected route has no receiving lane beyond entry region')
    location = receiving.transform.location
    forward = receiving.transform.get_forward_vector()
    origin = [float(location.x), float(location.y)]
    direction = (float(forward.x), float(forward.y))
    norm = math.hypot(*direction)
    if norm <= 0:
        raise ValueError('Receiving lane direction absent')
    direction = (direction[0] / norm, direction[1] / norm)
    length = 14.0
    end = [origin[0] + direction[0] * length, origin[1] + direction[1] * length]
    return origin, end, _corridor(origin, direction, length, max(1.0, receiving.lane_width / 2))


def run(output, host, port):
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture
    from space_camera_capture import CAMERAS, FFmpegSourceSink, SpaceCameraCapture

    output = Path(output)
    config = json.loads((output / 'config.json').read_text())
    kind, blocked = check_config(config)
    client = carla.Client(host, port)
    client.set_timeout(30)
    world = client.get_world()
    original_settings = world.get_settings()
    actors, sinks, frames = [], {}, []
    camera = pipeline = mapping = signal = None
    old_signal = None
    failed = False
    restored = False
    try:
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        world.apply_settings(settings)
        world_map = world.get_map()
        route = connected_entry_route(world_map)
        region = choose_region(world_map, route, kind)
        crossing = choose_region(world_map, route, 'marked_crosswalk')
        origin, end, corridor = receiving_geometry(route, region)
        ego_bp = world.get_blueprint_library().find('vehicle.tesla.model3')
        ego = world.try_spawn_actor(ego_bp, route[0].transform)
        if ego is None:
            raise ValueError('Original Native ego spawn failed')
        actors.append(ego)
        blocker = None
        if blocked:
            destination = route[-1].transform
            forward = destination.get_forward_vector()
            offset = float(config.get('blocker_offset_m', 3.0))
            position = carla.Location(x=destination.location.x + forward.x * offset,
                                      y=destination.location.y + forward.y * offset,
                                      z=destination.location.z)
            blocker = world.try_spawn_actor(ego_bp, carla.Transform(position, destination.rotation))
            if blocker is None:
                raise ValueError('Downstream standing vehicle did not spawn')
            actors.append(blocker)
            blocker.set_simulate_physics(False)
        walkers = sorted(world.get_blueprint_library().filter('walker.pedestrian.*'),
                         key=lambda blueprint: blueprint.id)
        if not walkers:
            raise ValueError('No Native pedestrian blueprint for passage audit')
        start_cross, end_cross = crossing[0], crossing[2]
        start_location = carla.Location(x=start_cross[0], y=start_cross[1],
                                        z=route[0].transform.location.z + .2)
        walker = world.try_spawn_actor(walkers[0], carla.Transform(start_location))
        if walker is None:
            raise ValueError('Original crossing pedestrian did not spawn')
        actors.append(walker)
        dx, dy = end_cross[0] - start_cross[0], end_cross[1] - start_cross[1]
        span = math.hypot(dx, dy)
        if span <= 0:
            raise ValueError('Native crossing has no pedestrian route')
        walker_direction = carla.Vector3D(dx / span, dy / span, 0)
        nearby_signals = sorted(world.get_actors().filter('traffic.traffic_light*'),
                                key=lambda item: item.get_location().distance(route[0].transform.location))
        if not nearby_signals or nearby_signals[0].get_location().distance(route[0].transform.location) > 50:
            raise ValueError('No applicable Native signal for the selected entry')
        signal = nearby_signals[0]
        old_signal = signal.get_state()
        for name in CAMERAS:
            sinks[name] = FFmpegSourceSink(output, name)
        camera = SpaceCameraCapture(world, carla, ego, sinks,
                                    overview_height_delta_m=float(config.get('overview_height_delta_m', 0.0)))
        pipeline = PipelineCapture(client, ego, output, config['selected_case_id'],
                                   required_observations=config.get('required_atoms', []))
        mapping = FrameMap(output / 'video_frames.jsonl')
        scene = {'case_id': config['selected_case_id'], 'region_kind': kind,
                 'entry_region': region, 'other_side_origin': origin,
                 'receiving_path_end': end, 'receiving_corridor': corridor,
                 'vehicle_length_m': float(ego.bounding_box.extent.x * 2),
                 'map_name': world_map.name,
                 'opendrive_sha256': hashlib.sha256(world_map.to_opendrive().encode()).hexdigest(),
                 'signal_actor_id': str(signal.id),
                 'ego_actor_id': str(ego.id),
                 'blocker_actor_id': str(blocker.id) if blocker else None,
                 'pedestrian_actor_id': str(walker.id), 'pedestrian_crossing_polygon': crossing,
                 'physical_acceptance_claimed': False}
        (output / 'space_scene.json').write_text(json.dumps(scene, indent=2) + '\n')
        source_rows = []
        start = None
        route_index = 1
        for video_frame in range(config['frames']):
            signal.set_state(carla.TrafficLightState.Green)
            walker.apply_control(carla.WalkerControl(direction=walker_direction, speed=1.2, jump=False))
            here = ego.get_location()
            while route_index + 1 < len(route) and here.distance(route[route_index].transform.location) < 2:
                route_index += 1
            control = steer_to(ego, route[route_index].transform.location,
                               float(config.get('ego_throttle', .22)))
            if blocker and here.distance(blocker.get_location()) < 5:
                control.update(throttle=0.0, brake=.9)
            ego.apply_control(carla.VehicleControl(**control))
            frame = world.tick()
            snapshot = world.get_snapshot()
            if snapshot.frame != frame:
                raise ValueError('Original Native snapshot/frame mismatch')
            if start is None:
                start = snapshot.timestamp.elapsed_seconds
            time_s = snapshot.timestamp.elapsed_seconds - start
            camera.wait_for_frame(frame)
            trace = pipeline.capture(frame, time_s)
            if trace.get('frame') != frame or trace.get('time_s') != time_s:
                raise ValueError('Original Native trace/frame join differs')
            mapping.append(frame, time_s)
            source_rows.append({'frame': video_frame, 'carla_frame': frame, 'time_s': time_s,
                                'ego_footprint': ground_corners(ego),
                                'downstream_occupants': ([{'id': str(blocker.id),
                                                          'footprint': ground_corners(blocker)}]
                                                         if blocker else []),
                                'passage_participants': [{'id': str(walker.id), 'kind': 'pedestrian',
                                                          'footprint': ground_corners(walker),
                                                          'passage_polygon': crossing,
                                                          'velocity_mps': math.hypot(walker.get_velocity().x,
                                                                                     walker.get_velocity().y)}],
                                'signal_state': 'proceed' if signal.get_state() == carla.TrafficLightState.Green else 'other'})
            frames.append(frame)
        camera.verify_frames(frames)
        (output / 'space_frames.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in source_rows))
    except BaseException:
        failed = True
        raise
    finally:
        if mapping:
            mapping.close()
        if pipeline:
            pipeline.close(confirmed=not failed)
        if camera:
            camera.close()
        for sink in sinks.values():
            sink.close()
        if signal is not None and old_signal is not None:
            signal.set_state(old_signal)
        for actor in reversed(actors):
            actor.destroy()
        world.apply_settings(original_settings)
        readback = world.get_settings()
        restored = (readback.synchronous_mode == original_settings.synchronous_mode
                    and readback.fixed_delta_seconds == original_settings.fixed_delta_seconds)
        if not restored:
            raise ValueError('Native world settings restoration readback differs')
    (output / 'acquisition-provenance.json').write_text(json.dumps({
        'provenance_kind': 'native', 'diagnostic_fixture': False,
        'original_frames': len(frames)}) + '\n')
    seal_capture(output, frames=len(frames), restoration={'restored': restored}, errors=[],
                 encoder_exit_codes={name: 0 for name in CAMERAS},
                 context={'native_map_name': world.get_map().name, 'region_kind': kind})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output-dir')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args()
    if args.check:
        check_config(json.loads(Path('config.json').read_text()))
        return
    if not args.output_dir:
        parser.error('--output-dir required')
    run(args.output_dir, args.host, args.port)


if __name__ == '__main__':
    main()
