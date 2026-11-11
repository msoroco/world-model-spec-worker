"""CARLA-lazy exact left-turn source capture for C109705.

The supplied route survey must identify real Native XODR waypoints. The first
Native run verifies them against the loaded map and records observed bodies.
"""

import argparse
import json
from math import atan2, cos, pi, sin
from pathlib import Path

from turn_camera import CAMERAS, LosslessSourceSink, TurnCameraCapture


PREFIX = 'heldout__C109705__NRS-484B-400-3__motor_vehicle_driver__'
CASES = {'centerline_approach_left_curb_departure',
         'farther_approach_left_curb_departure',
         'centerline_approach_farther_departure'}


def check_config(config):
    case = config.get('selected_case_id', '')
    if (not case.startswith(PREFIX) or case[len(PREFIX):] not in CASES
            or config.get('law_id') != 'NRS-484B-400-3'
            or config.get('cell_id') != 'C109705'
            or config.get('actor') != 'motor_vehicle_driver'
            or config.get('rate_hz') != 20 or config.get('frames') != 160
            or config.get('duration_s') != 8):
        raise ValueError('Exact C109705 left-turn configuration differs')
    survey = config.get('route_survey', {})
    if (not survey.get('map_name') or len(survey.get('waypoints', [])) < 3
            or survey.get('approach_directions') != 2
            or survey.get('destination_directions') != 1
            or survey.get('intersection_kind') != 'public_highway_non_alley'
            or not survey.get('source_sha256')):
        raise ValueError('Source-bound two-directional/one-way route survey required')
    if config.get('cameras') != list(CAMERAS):
        raise ValueError('Four named source cameras required')
    if config.get('lookahead_steps', 2) not in (1, 2):
        raise ValueError('Unsupported turn controller lookahead')
    if config.get('overview_height_delta_m', 0) not in (0, 2):
        raise ValueError('Unsupported overview camera elevation')
    if config.get('target_speed_mps') not in (2.0, 3.0):
        raise ValueError('Unsupported engineering turn speed')
    return survey


def _route(world_map, survey, carla):
    if world_map.name != survey['map_name']:
        raise ValueError('Native map differs from source survey')
    route = []
    for item in survey['waypoints']:
        waypoint = world_map.get_waypoint_xodr(item['road_id'], item['lane_id'], item['s'])
        if waypoint is None or waypoint.lane_type != carla.LaneType.Driving:
            raise ValueError('Surveyed Native turning waypoint unavailable')
        expected = item.get('xy_m')
        actual = waypoint.transform.location
        if (not isinstance(expected, list) or len(expected) != 2
                or (actual.x - expected[0]) ** 2 + (actual.y - expected[1]) ** 2 > .25):
            raise ValueError('Native route differs from surveyed coordinates')
        route.append(waypoint)
    if not any(wp.is_junction for wp in route):
        raise ValueError('Surveyed route lacks an actual intersection')
    return route


def _feedback(ego, target, speed_mps):
    pose = ego.get_transform()
    velocity = ego.get_velocity()
    dx = target.x - pose.location.x
    dy = target.y - pose.location.y
    yaw = pose.rotation.yaw * pi / 180
    error = (atan2(dy, dx) - yaw + pi) % (2 * pi) - pi
    speed = velocity.x * cos(yaw) + velocity.y * sin(yaw)
    gap = speed_mps - speed
    return {'steer': max(-.75, min(.75, 1.2 * error)),
            'throttle': max(0, min(.55, .23 * gap)),
            'brake': max(0, min(.7, -.27 * gap))}


def run(config, output, host, port):
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture

    survey = check_config(config)
    output = Path(output)
    if json.loads((output / 'config.json').read_text()) != config:
        raise ValueError('Materialized exact turn config differs')
    source = output / 'turn-route-survey.json'
    from hashlib import sha256
    if not source.is_file() or sha256(source.read_bytes()).hexdigest() != survey['source_sha256']:
        raise ValueError('Native route survey source changed')
    client = carla.Client(host, int(port)); client.set_timeout(30)
    world = client.get_world(); original_settings = world.get_settings()
    actors = []; sinks = {}; camera = pipeline = frame_map = None
    complete = False; frames = []
    try:
        settings = world.get_settings(); settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05; world.apply_settings(settings)
        route = _route(world.get_map(), survey, carla)
        blueprint = world.get_blueprint_library().find('vehicle.tesla.model3')
        ego = world.try_spawn_actor(blueprint, route[0].transform)
        if ego is None:raise ValueError('Native subject turn spawn failed')
        actors.append(ego)
        pipeline = PipelineCapture(client, ego, output, config['selected_case_id'],
                                   required_observations=config.get('required_atoms', []))
        frame_map = FrameMap(output / 'video_frames.jsonl')
        for name in CAMERAS:sinks[name] = LosslessSourceSink(output, name)
        camera = TurnCameraCapture(world, carla, ego, sinks,
            overview_height_delta_m=config.get('overview_height_delta_m', 0))
        geometry = {'case_id': config['selected_case_id'], 'ego_actor_id': ego.id,
                    'approach_directions': 2, 'destination_directions': 1,
                    'maneuver': 'left_turn', 'intersection_kind': 'public_highway_non_alley',
                    'approach_centerline_xy_m': survey['approach_centerline_xy_m'],
                    'destination_left_curb_xy_m': survey['destination_left_curb_xy_m'],
                    'intersection_entry_xy_m': survey['intersection_entry_xy_m'],
                    'survey_source_sha256': survey['source_sha256']}
        (output / 'turn_road_geometry.json').write_text(json.dumps(geometry) + '\n')
        body_path = output / 'body_footprints.jsonl'
        if body_path.exists():raise ValueError('Retain prior original turn bodies')
        with body_path.open('w') as body:
            start = None
            for index in range(config['frames']):
                target = route[min(len(route)-1, index // 4 +
                    config.get('lookahead_steps', 2))].transform.location
                ego.apply_control(carla.VehicleControl(**_feedback(ego, target,
                                      config['target_speed_mps'])))
                frame = world.tick(); camera.wait_for_frame(frame)
                snapshot = world.get_snapshot()
                if snapshot.frame != frame:raise ValueError('Native turn snapshot differs')
                if start is None:start = snapshot.timestamp.elapsed_seconds
                time_s = snapshot.timestamp.elapsed_seconds - start
                trace = pipeline.capture(frame, time_s)
                if trace.get('frame') != frame:raise ValueError('Native turn trace differs')
                vertices = ego.bounding_box.get_world_vertices(ego.get_transform())
                corners = [[vertex.x, vertex.y] for vertex in sorted(vertices, key=lambda v: v.z)[:4]]
                current = world.get_map().get_waypoint(ego.get_location(),
                    project_to_road=False, lane_type=carla.LaneType.Driving)
                if current is None:raise ValueError('Original vehicle left surveyed roadway')
                phase = ('entry' if current.is_junction else
                         'departure' if current.road_id == route[-1].road_id else 'approach')
                body.write(json.dumps({'frame': frame, 'time_s': time_s,
                    'actor_id': ego.id, 'phase': phase, 'body_corners_xy_m': corners}) + '\n')
                frame_map.append(frame, time_s); frames.append(frame)
        camera.verify(frames); complete = True
    finally:
        if frame_map is not None:frame_map.close()
        if pipeline is not None:pipeline.close(confirmed=complete)
        if camera is not None:camera.close()
        for sink in sinks.values():sink.close()
        for actor in reversed(actors):actor.destroy()
        world.apply_settings(original_settings)
        restored = world.get_settings()
        if (restored.synchronous_mode != original_settings.synchronous_mode
                or restored.fixed_delta_seconds != original_settings.fixed_delta_seconds):
            raise ValueError('Native turn settings restoration failed')
        if complete:
            seal_capture(output, frames=frames,
                         restoration={'restored': True}, errors=[],
                         encoder_exit_codes={name: 0 for name in sinks},
                         context={'route_survey_sha256': survey['source_sha256']})


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--check', action='store_true')
    parser.add_argument('--config', default='config.json')
    parser.add_argument('--output-dir'); parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000); args = parser.parse_args()
    config = json.loads(Path(args.config).read_text()); check_config(config)
    if args.output_dir:run(config, args.output_dir, args.host, args.port)


if __name__ == '__main__':main()
