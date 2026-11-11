"""Native one-way to two-way left-turn construction for fixed C109705.

All curb, centerline and body positions are retained as original measurements.
The runner makes no practicability or legal-compliance finding.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from xml.etree import ElementTree

PREFIX = 'heldout__C109705__NRS-484B-400-4__motor_vehicle_driver__'
CASES = {
    'approach_near_depart_right': (1.25, 1.80),
    'approach_far_depart_right': (2.20, 1.80),
    'approach_near_depart_left': (1.25, -1.00),
}


def check_config(config):
    if (config.get('law_id'), config.get('cell_id'), config.get('actor')) != (
            'NRS-484B-400-4', 'C109705', 'motor_vehicle_driver'):
        raise ValueError('Wrong frozen one-way left-turn scope')
    case = config.get('selected_case_id', '')
    slug = case.removeprefix(PREFIX)
    if case != PREFIX + slug or slug not in CASES or config.get('case', {}).get('case_id') != case:
        raise ValueError('Unknown exact one-way left-turn case')
    if config.get('rate_hz') != 20 or config.get('frames') != 160 or len(config.get('cameras', [])) != 4:
        raise ValueError('Four-view 20 Hz turn capture contract missing')
    if not 1.0 <= float(config.get('route_step_m', 2.0)) <= 3.0:
        raise ValueError('Unsupported Native route step')
    if not 0.0 <= float(config.get('overview_height_delta_m', 0.0)) <= 2.0:
        raise ValueError('Unsupported overview mount')
    return CASES[slug]


def road_directions(opendrive):
    """Return driving-lane signs for each authored OpenDRIVE road."""
    root = ElementTree.fromstring(opendrive)
    result = {}
    for road in root.findall('road'):
        signs = set()
        for side, sign in (('left', 1), ('right', -1)):
            for lane in road.findall(f'./lanes/laneSection/{side}/lane'):
                if lane.get('type') == 'driving':
                    signs.add(sign)
        result[int(road.attrib['id'])] = signs
    return result


def _yaw_left(start, end):
    a = math.radians(start.transform.rotation.yaw)
    b = math.radians(end.transform.rotation.yaw)
    return math.degrees(math.atan2(math.sin(b-a), math.cos(b-a)))


def choose_turn(world_map, *, step_m=2.0, max_steps=75):
    """Find a connected left route from a one-way road to a two-way road."""
    directions = road_directions(world_map.to_opendrive())
    for spawn in world_map.get_spawn_points():
        source = world_map.get_waypoint(spawn.location)
        if (source is None or source.is_junction or source.lane_id >= 0
                or directions.get(source.road_id) != {-1}):
            continue
        queue = [(source, [source], False)]
        seen = set()
        while queue:
            current, path, entered = queue.pop(0)
            key = (current.road_id, current.lane_id, round(float(current.s), 1), entered)
            if key in seen:
                continue
            seen.add(key)
            if len(path) > max_steps:
                continue
            if (entered and not current.is_junction and current.road_id != source.road_id
                    and current.lane_id < 0 and directions.get(current.road_id) == {-1, 1}
                    and 30 <= _yaw_left(source, current) <= 150):
                return source, current, path, directions
            for nxt in current.next(step_m):
                if not entered and not nxt.is_junction and nxt.road_id != source.road_id:
                    continue
                queue.append((nxt, path + [nxt], entered or nxt.is_junction))
    raise ValueError('No connected one-way to two-way Native left turn with right-side destination lane')


def left_boundary(waypoint):
    location = waypoint.transform.location
    right = waypoint.transform.get_right_vector()
    half = float(waypoint.lane_width) / 2
    return [float(location.x - right.x * half), float(location.y - right.y * half)]


def reference_line(waypoint):
    following = [item for item in waypoint.next(5.0)
                 if item.road_id == waypoint.road_id and item.lane_id == waypoint.lane_id]
    if len(following) != 1:
        raise ValueError('Original map line lacks connected same-lane continuation')
    return [left_boundary(waypoint), left_boundary(following[0])]


def center_offset_transform(carla, waypoint, distance_from_left_m):
    """Shift an original lane-center pose to a commanded curb/centerline offset."""
    shift_right = distance_from_left_m - float(waypoint.lane_width) / 2
    base = waypoint.transform
    right = base.get_right_vector()
    location = carla.Location(x=base.location.x + right.x * shift_right,
                              y=base.location.y + right.y * shift_right,
                              z=base.location.z)
    return carla.Transform(location, base.rotation)


def control_to(ego, target):
    pose = ego.get_transform()
    current = math.radians(pose.rotation.yaw)
    desired = math.atan2(target.y - pose.location.y, target.x - pose.location.x)
    error = math.atan2(math.sin(desired-current), math.cos(desired-current))
    return {'throttle': 0.23, 'brake': 0.0,
            'steer': max(-1.0, min(1.0, error / math.radians(45)))}


def ground_corners(actor):
    vertices = list(actor.bounding_box.get_world_vertices(actor.get_transform()))
    if len(vertices) != 8:
        raise ValueError('Original Native body lacks eight bounding-box vertices')
    lower = sorted(vertices, key=lambda point: point.z)[:4]
    cx = sum(point.x for point in lower) / 4
    cy = sum(point.y for point in lower) / 4
    lower.sort(key=lambda point: math.atan2(point.y-cy, point.x-cx))
    return [[float(point.x), float(point.y)] for point in lower]


def run(output, host, port):
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture
    from turn_camera_capture import CAMERAS, FFmpegSourceSink, TurnCameraCapture

    output = Path(output)
    config = json.loads((output / 'config.json').read_text())
    approach_offset, departure_offset = check_config(config)
    client = carla.Client(host, port)
    client.set_timeout(30)
    world = client.get_world()
    original = world.get_settings()
    actors = []
    sinks = {}
    camera = pipeline = mapping = None
    frames = []
    failed = False
    restored = False
    try:
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 0.05
        world.apply_settings(settings)
        world_map = world.get_map()
        source, destination, route, directions = choose_turn(
            world_map, step_m=float(config.get('route_step_m', 2.0)))
        spawn = center_offset_transform(carla, source, approach_offset)
        blueprint = world.get_blueprint_library().find('vehicle.tesla.model3')
        ego = world.try_spawn_actor(blueprint, spawn)
        if ego is None:
            raise ValueError('Original Native turn subject spawn failed')
        actors.append(ego)
        for name in CAMERAS:
            sinks[name] = FFmpegSourceSink(output, name)
        camera = TurnCameraCapture(world, carla, ego, sinks,
                                   overview_height_delta_m=float(config.get('overview_height_delta_m', 0.0)))
        pipeline = PipelineCapture(client, ego, output, config['selected_case_id'],
                                   required_observations=config.get('required_atoms', []))
        mapping = FrameMap(output / 'video_frames.jsonl')
        junction = next((waypoint.get_junction() for waypoint in route if waypoint.is_junction), None)
        if junction is None:
            raise ValueError('Original Native left turn lacks a junction reference')
        geometry = {'source_directionality': 'one_way', 'destination_directionality': 'two_directional',
                    'maneuver': 'left_turn', 'intersection_id': str(junction.id),
                    'map_source': {'name': world_map.name, 'opendrive_sha256': __import__('hashlib').sha256(world_map.to_opendrive().encode()).hexdigest()},
                    'source_left_curb': reference_line(source),
                    'destination_centerline': reference_line(destination),
                    'source_road_id': source.road_id, 'destination_road_id': destination.road_id,
                    'driving_lane_signs': {'source': sorted(directions[source.road_id]),
                                           'destination': sorted(directions[destination.road_id])}}
        (output / 'road_geometry.json').write_text(json.dumps(geometry, indent=2) + '\n')
        route_index = 1
        body_rows = []
        start = None
        for _ in range(config['frames']):
            ego_location = ego.get_location()
            while route_index + 1 < len(route) and ego_location.distance(route[route_index].transform.location) < 2.0:
                route_index += 1
            target_waypoint = route[route_index]
            offset = (departure_offset if target_waypoint.road_id == destination.road_id
                      and not target_waypoint.is_junction else approach_offset)
            target = center_offset_transform(carla, target_waypoint, offset).location
            control = control_to(ego, target)
            ego.apply_control(carla.VehicleControl(**control))
            frame = world.tick()
            snapshot = world.get_snapshot()
            if snapshot.frame != frame:
                raise ValueError('Original turn snapshot/frame mismatch')
            if start is None:
                start = snapshot.timestamp.elapsed_seconds
            time_s = snapshot.timestamp.elapsed_seconds - start
            camera.wait_for_frame(frame)
            trace = pipeline.capture(frame, time_s)
            if trace.get('frame') != frame or trace.get('time_s') != time_s:
                raise ValueError('Original turn trace/frame join differs')
            mapping.append(frame, time_s)
            current = world_map.get_waypoint(ego.get_location())
            phase = ('approach' if current.road_id == source.road_id and not current.is_junction
                     else 'leaving_intersection' if current.road_id == destination.road_id and not current.is_junction
                     else 'inside_intersection')
            body_rows.append({'frame': frame, 'time_s': time_s, 'subject_id': str(ego.id),
                              'phase': phase, 'ground_corners': ground_corners(ego)})
            frames.append(frame)
        camera.verify_frames(frames)
        (output / 'body_footprints.json').write_text(json.dumps({'subject_id': str(ego.id), 'frames': body_rows}, indent=2) + '\n')
        (output / 'body_footprints.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in body_rows))
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
        for actor in reversed(actors):
            actor.destroy()
        world.apply_settings(original)
        current = world.get_settings()
        restored = (current.synchronous_mode == original.synchronous_mode
                    and current.fixed_delta_seconds == original.fixed_delta_seconds)
        if not restored:
            raise ValueError('Native turn settings restoration readback differs')
    (output / 'acquisition-provenance.json').write_text(json.dumps({
        'provenance_kind': 'native', 'diagnostic_fixture': False,
        'original_frames': len(frames)}) + '\n')
    seal_capture(output, frames=len(frames), restoration={'restored': restored}, errors=[],
                 encoder_exit_codes={name: 0 for name in CAMERAS},
                 context={'native_map_name': world.get_map().name,
                          'source_road_id': source.road_id, 'destination_road_id': destination.road_id})


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
