"""Native fire-station reversal attempt; imports CARLA only at execution."""
import argparse
import json
from math import atan2, cos, hypot, radians, sin
from pathlib import Path

from fire_station_geometry import validate_entrance
from fire_station_camera_capture import CAMERAS, FFmpegSourceSink, FireStationCameraCapture
from fire_station_capture_session import FireStationCaptureSession

BRANCHES = {'front_of_entrance', 'front_of_approach',
            'through_driveway', 'remote_reference'}


def check_config(config):
    branch = config.get('case_branch')
    if branch not in BRANCHES or not config.get('selected_case_id', '').endswith('__'+branch):
        raise ValueError('exact fire-station case required')
    if (config.get('law_id'), config.get('cell_id'), config.get('actor')) != (
            'LVMC-11-12-060', 'C104538', 'motor_vehicle_driver'):
        raise ValueError('fire-station law/cell/actor identity differs')
    if (config.get('rate_hz'), config.get('frames'), config.get('duration_s')) != (20, 240, 12):
        raise ValueError('240 original 20 Hz frames required')
    if {v.get('name') for v in config.get('cameras', [])} != set(CAMERAS):
        raise ValueError('four named original cameras required')
    survey = config.get('station_survey')
    if not isinstance(survey, dict) or not survey.get('map_name'):
        raise ValueError('source-bound station map survey required')
    for key in ('public_before', 'public_at', 'public_after', 'driveway_at'):
        point = survey.get(key)
        if not isinstance(point, dict) or not all(k in point for k in ('road_id', 'lane_id', 's')):
            raise ValueError('station map survey lacks '+key)
    route = survey.get('routes', {}).get(branch)
    if not isinstance(route, list) or len(route) < 3:
        raise ValueError('exact mapped reversal route required')
    if branch == 'through_driveway' and not any(p.get('road_id') == survey['driveway_at']['road_id'] for p in route):
        raise ValueError('driveway-use route never enters the driveway road')
    if config.get('target_speed_mps', 0) <= 0:
        raise ValueError('positive engineering route speed required')
    return True


def _waypoint(world_map, ref):
    wp = world_map.get_waypoint_xodr(int(ref['road_id']), int(ref['lane_id']), float(ref['s']))
    if wp is None:
        raise ValueError('survey waypoint absent from Native map')
    return wp


def resolve_survey(world_map, survey, branch):
    if world_map.name != survey['map_name']:
        raise ValueError('Native map differs from source-bound station survey')
    anchors = {key: _waypoint(world_map, survey[key]) for key in (
        'public_before', 'public_at', 'public_after', 'driveway_at')}
    geometry = validate_entrance(anchors['public_before'], anchors['public_at'],
                                 anchors['public_after'], anchors['driveway_at'],
                                 source=survey['station_source'])
    route = [_waypoint(world_map, ref) for ref in survey['routes'][branch]]
    if len({_waypoint_id(wp) for wp in route}) < 3:
        raise ValueError('reversal route lacks distinct physical waypoints')
    return geometry, route


def _waypoint_id(wp):
    return (wp.road_id, wp.lane_id, round(wp.s, 2))


def steer_toward(actor, target, speed_mps, carla, *, gain=.22):
    transform = actor.get_transform()
    p = transform.location
    q = target.transform.location
    desired = atan2(q.y-p.y, q.x-p.x)
    yaw = radians(transform.rotation.yaw)
    error_angle = atan2(sin(desired-yaw), cos(desired-yaw))
    velocity = actor.get_velocity()
    speed = hypot(velocity.x, velocity.y)
    error_speed = speed_mps-speed
    actor.apply_control(carla.VehicleControl(
        throttle=min(.55, max(0., gain*error_speed)),
        brake=min(.7, max(0., -.3*error_speed)),
        steer=min(.6, max(-.6, error_angle/.8))))


def run(output, host, port):
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import seal_capture
    output = Path(output)
    config = json.loads((output/'config.json').read_text())
    check_config(config)
    client = carla.Client(host, port); client.set_timeout(30.)
    world = client.get_world(); original = world.get_settings()
    ego = camera = pipeline = session = None
    sinks = {}; frames = []; errors = []; restored = False
    try:
        settings = world.get_settings()
        settings.synchronous_mode = True; settings.fixed_delta_seconds = .05
        world.apply_settings(settings)
        world_map = world.get_map()
        geometry, route = resolve_survey(world_map, config['station_survey'], config['case_branch'])
        blueprint = world.get_blueprint_library().find(config.get('vehicle_blueprint', 'vehicle.tesla.model3'))
        spawn = route[0].transform
        spawn.location.z += .3
        ego = world.try_spawn_actor(blueprint, spawn)
        if ego is None:
            raise ValueError('subject spawn failed at surveyed station route')
        for name in CAMERAS: sinks[name] = FFmpegSourceSink(output, name)
        camera = FireStationCameraCapture(world, carla, ego, sinks)
        pipeline = PipelineCapture(client, ego, output, config['selected_case_id'],
                                   required_observations=config.get('required_atoms', []))
        session = FireStationCaptureSession(output, pipeline, world_map, ego, geometry)
        index = 1; start = None
        for _ in range(config['frames']):
            target = route[index]
            p = ego.get_transform().location; q = target.transform.location
            if hypot(p.x-q.x, p.y-q.y) < config.get('waypoint_arrival_m', 2.0) and index < len(route)-1:
                index += 1; target = route[index]
            steer_toward(ego, target, config['target_speed_mps'], carla,
                         gain=config.get('speed_gain', .22))
            frame = world.tick(); snapshot = world.get_snapshot()
            if snapshot.frame != frame: raise ValueError('Native frame differs from completed tick')
            if start is None: start = snapshot.timestamp.elapsed_seconds
            time_s = snapshot.timestamp.elapsed_seconds-start
            camera.wait_for_frame(frame)
            session.capture(frame, time_s)
            frames.append(frame)
        camera.verify_frames(frames)
        if index != len(route)-1:
            raise ValueError('subject did not reach final surveyed reversal segment')
    except BaseException as error:
        errors.append(str(error)); raise
    finally:
        if session is not None: session.close()
        if pipeline is not None: pipeline.close(confirmed=not errors)
        if camera is not None: camera.close()
        for sink in sinks.values(): sink.close()
        if ego is not None: ego.destroy()
        world.apply_settings(original)
        current = world.get_settings()
        restored = (current.synchronous_mode == original.synchronous_mode and
                    current.fixed_delta_seconds == original.fixed_delta_seconds)
        if not restored: raise ValueError('Native world settings restoration readback differs')
    if errors or not frames: raise ValueError('Native station capture did not finish')
    (output/'acquisition-provenance.json').write_text(json.dumps({
        'provenance_kind': 'native', 'diagnostic_fixture': False,
        'original_frames': len(frames)})+'\n')
    seal_capture(output, frames=len(frames), restoration={'restored': restored},
                 errors=[], encoder_exit_codes={name: 0 for name in CAMERAS},
                 context={'native_map_name': world.get_map().name,
                          'station_source': config['station_survey']['station_source']})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output-dir')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args()
    if args.check:
        candidate = Path('config.json')
        if candidate.exists(): check_config(json.loads(candidate.read_text()))
        return
    if not args.output_dir: parser.error('--output-dir required')
    run(args.output_dir, args.host, args.port)


if __name__ == '__main__': main()
