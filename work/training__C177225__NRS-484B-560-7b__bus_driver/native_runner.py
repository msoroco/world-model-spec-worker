"""Original CARLA attempt for the directed officer-stop rail comparison.

The operator supplies an exclusively owned CARLA server and a verified installed
rail prop blueprint. This runner does not assign a legal outcome or claim that
the officer's gesture was understood by a driver.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

from camera_recorder import CameraRecorder
from measure_direction import derive_observation
from native_scene import SceneAssets, VIEWS, camera_plan, spawn_scene
from officer_direction import Crossing, OfficerStop, target_control
from officer_pose import step as pose_step
from rail_road import ROAD_ID, open_drive, validate_authored_road


RATE_HZ = 20
FRAMES = 600
CASE_SUFFIXES = ('reference', 'contrast')
ASSIGNMENT = 'training__C177225__NRS-484B-560-7b__bus_driver'


def _write_new(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def check(case_suffix, direction, config=None):
    validate_authored_road()
    if case_suffix not in CASE_SUFFIXES or direction not in (-1, 1):
        raise ValueError('Exact comparison case and approach direction required')
    layout = Crossing()
    layout.validate()
    if config is not None:
        if (config.get('case_id') != ASSIGNMENT + '__' + case_suffix or
                config.get('selected_case_id') != config.get('case_id') or
                config.get('case_suffix') != case_suffix or
                config.get('direction') != direction or
                config.get('law_id') != 'NRS-484B-560-7b' or
                config.get('cell_id') != 'C177225' or
                config.get('actor') != 'bus_driver' or
                config.get('rate_hz') != RATE_HZ or
                config.get('duration_s') != FRAMES / RATE_HZ or
                config.get('rail_asset_blueprint', '').startswith('static.prop.') is not True):
            raise ValueError('Materialized exact-case configuration differs')
    if layout.approach_station(direction) < -100 or layout.approach_station(direction) > 100:
        raise ValueError('Bus starts outside authored road')
    return {'case_id': ASSIGNMENT + '__' + case_suffix,
            'direction': direction, 'rate_hz': RATE_HZ, 'frames': FRAMES,
            'camera_names': list(VIEWS), 'native_imported': False,
            'physical_success_claimed': False}


def _native_map_readback(carla, world, layout, direction):
    mapping = world.get_map()
    lane_y = -1.75 * direction
    stations = [layout.approach_station(direction), layout.stop_station(direction),
                layout.exit_station(direction)]
    seen = []
    for station in stations:
        waypoint = mapping.get_waypoint(carla.Location(x=station, y=lane_y, z=0),
                                        project_to_road=False,
                                        lane_type=carla.LaneType.Driving)
        if waypoint is None or waypoint.road_id != ROAD_ID or waypoint.lane_id != -direction:
            raise ValueError('Native approach/stop/exit lane differs from authored road')
        forward = waypoint.transform.get_forward_vector()
        if forward.x * direction < 0.98 or abs(waypoint.lane_width - 3.5) > 0.15:
            raise ValueError('Native driving direction or width differs from authored road')
        seen.append({'station_m': station, 'road_id': waypoint.road_id,
                     'lane_id': waypoint.lane_id, 'lane_width_m': waypoint.lane_width,
                     'forward_native_xyz': [forward.x, forward.y, forward.z]})
    xml = mapping.to_opendrive()
    return {'source_kind': 'original_native_map_api',
            'opendrive_sha256': hashlib.sha256(xml.encode()).hexdigest(),
            'lane_readback': seen, 'physical_rail_placement_verified': False,
            'legal_verdict': None}


def _bus_row(bus, frame, direction):
    transform = bus.get_transform()
    velocity = bus.get_velocity()
    values = [velocity.x, velocity.y, velocity.z]
    if not all(math.isfinite(value) for value in values):
        raise ValueError('Native bus velocity is not finite')
    return {'native_frame': frame, 'actor_id': str(bus.id),
            'station_m': transform.location.x,
            'lane_y_native_m': transform.location.y,
            'heading_native_deg': transform.rotation.yaw,
            'velocity_native_xyz_mps': values,
            'approach_direction': direction,
            'source_kind': 'original_native_actor_api'}


def run(client, carla, output, *, case_suffix, direction, rail_asset_blueprint=None):
    """Capture one fresh attempt. An exception leaves an explicit failure report."""
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap
    from worker_exchange.world_restore import restore, snapshot

    output = Path(output).resolve()
    if not output.is_dir() or not (output / 'config.json').is_file():
        raise ValueError('A materialized exact-case attempt directory is required')
    config = json.loads((output / 'config.json').read_text())
    spec = check(case_suffix, direction, config)
    rail_asset_blueprint = rail_asset_blueprint or config['rail_asset_blueprint']
    if rail_asset_blueprint != config['rail_asset_blueprint']:
        raise ValueError('Runtime rail blueprint override differs from construction')
    if (output / 'attempt_report.json').exists() or (output / 'video_frames.jsonl').exists():
        raise ValueError('Retain prior attempt; materialize a fresh directory')
    assets = SceneAssets(rail_asset_blueprint=rail_asset_blueprint)
    assets.validate()
    saved = snapshot(client)
    prior = client.get_world()
    if saved['settings'].synchronous_mode or [actor for actor in prior.get_actors()
                                                if actor.type_id.startswith(
                                                    ('vehicle.', 'walker.', 'sensor.', 'controller.'))]:
        raise ValueError('Exclusive idle asynchronous CARLA world required')

    scene = None
    recorder = None
    capture = None
    frame_map = None
    bus_rows = []
    signal_rows = []
    map_rows = []
    error = None
    restored = None
    recorder_codes = {}
    changed = False
    try:
        world = client.generate_opendrive_world(open_drive(),
            carla.OpendriveGenerationParameters(vertex_distance=.25,
                max_road_length=50, wall_height=0, additional_width=0,
                smooth_junctions=False, enable_mesh_visibility=True,
                enable_pedestrian_navigation=False))
        changed = True
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 1 / RATE_HZ
        world.apply_settings(settings)
        world.set_weather(carla.WeatherParameters.ClearNoon)
        layout = Crossing()
        _write_new(output / 'native_map_readback.json',
                   _native_map_readback(carla, world, layout, direction))
        scene = spawn_scene(world, carla, layout, assets, direction=direction)
        bus = scene['bus']
        officer = scene['officer']
        signal = OfficerStop(officer_id=str(officer.id), bus_id=str(bus.id),
                             direction=direction, issued_frame=0,
                             first_governing_frame=1,
                             last_governing_frame=FRAMES + 100,
                             crossing_id='c177225_authored_rail_crossing',
                             authorized=True)
        first_next_frame = world.get_snapshot().frame + 1
        signal = OfficerStop(officer_id=signal.officer_id, bus_id=signal.bus_id,
                             direction=direction, issued_frame=first_next_frame,
                             first_governing_frame=first_next_frame + 1,
                             last_governing_frame=first_next_frame + FRAMES - 1,
                             crossing_id=signal.crossing_id, authorized=True)
        specs = {item['name']: item['size'] for item in camera_plan(direction)}
        recorder = CameraRecorder(output, scene['cameras'], specs)
        frame_map = FrameMap(output / 'video_frames.jsonl')
        capture = PipelineCapture(client, bus, output, spec['case_id'],
                                  required_observations=('kin.velocity', 'drv.stopped',
                                                         'dev.human_direction'))
        start_elapsed = world.get_snapshot().timestamp.elapsed_seconds
        for index in range(FRAMES):
            next_frame = world.get_snapshot().frame + 1
            current = _bus_row(bus, next_frame - 1, direction)
            speed = math.sqrt(sum(value * value for value in
                                  current['velocity_native_xyz_mps']))
            request = target_control(layout, signal, bus_id=signal.bus_id,
                                     crossing_id=signal.crossing_id,
                                     direction=direction, station_m=current['station_m'],
                                     speed_mps=speed, frame=next_frame,
                                     obey=case_suffix == 'reference')
            bus.apply_control(carla.VehicleControl(throttle=request['throttle'],
                                                    brake=request['brake']))
            pose = pose_step(officer, carla, signal, next_frame)
            frame = world.tick()
            if frame != next_frame:
                raise ValueError('Native frame advanced unexpectedly')
            time_s = world.get_snapshot().timestamp.elapsed_seconds - start_elapsed
            recorder.capture(frame)
            capture.capture(frame, time_s, extra={
                'directed_officer_signal_actor_id': signal.officer_id,
                'directed_officer_signal_governing': pose['governing'],
                'requested_direction_response': request['requested']})
            row = _bus_row(bus, frame, direction)
            bus_rows.append(row)
            signal_rows.append(pose)
            map_rows.append(frame_map.append(frame, time_s))
        observation = derive_observation(layout, signal, bus_rows, signal_rows,
                                         map_rows, source_kind='original_native')
        _write_new(output / 'direction_observation.json', observation)
        _write_new(output / 'officer_signal_definition.json', vars(signal))
        for name, rows in (('bus_native_rows.jsonl', bus_rows),
                           ('officer_signal_rows.jsonl', signal_rows)):
            with (output / name).open('x') as stream:
                for row in rows:
                    stream.write(json.dumps(row, allow_nan=False) + '\n')
    except BaseException as exc:
        error = {'type': type(exc).__name__, 'message': str(exc)}
    finally:
        if frame_map is not None:
            frame_map.close()
        if capture is not None:
            try:
                capture.close(confirmed=error is None)
            except BaseException as exc:
                error = error or {'type': type(exc).__name__, 'message': str(exc)}
        if recorder is not None:
            try:
                recorder_codes = recorder.close(check=error is None)
            except BaseException as exc:
                error = error or {'type': type(exc).__name__, 'message': str(exc)}
        if scene is not None:
            for actor in reversed(scene['owned']):
                try:
                    if actor.type_id.startswith('sensor.'):
                        actor.stop()
                    actor.destroy()
                except BaseException as exc:
                    error = error or {'type': type(exc).__name__, 'message': str(exc)}
        if changed:
            try:
                restored = restore(client, saved)
            except BaseException as exc:
                error = error or {'type': type(exc).__name__, 'message': str(exc)}
        _write_new(output / 'attempt_report.json', {
            'case_id': spec['case_id'], 'frames_observed': len(bus_rows),
            'restoration': restored, 'error': error,
            'physical_acceptance_claimed': False, 'legal_verdict': None})
        _write_new(output / 'native-run-status.json', {
            'case_id': spec['case_id'], 'errors': [] if error is None else [error],
            'frames_observed': len(bus_rows), 'restoration': restored,
            'encoder_exit_codes': recorder_codes,
            'physical_acceptance_claimed': False})
    if error:
        raise RuntimeError('C177225 original Native attempt failed: ' + error['message'])
    from worker_exchange.native_output import seal_capture
    seal_capture(output, frames=len(bus_rows), restoration=restored,
                 errors=[], encoder_exit_codes=recorder_codes,
                 context={'road_id': ROAD_ID, 'railway_identity_verified': False,
                          'officer_authority_verified': False})
    from finalize_direction import finalize_attempt, process_saved
    try:
        _write_new(output / 'saved_direction_observation.json',
                   process_saved(output, source_kind='original_native'))
    except BaseException as exc:
        _write_new(output / 'saved_processing_failure.json',
                   {'type': type(exc).__name__, 'message': str(exc),
                    'delivery_ready': False})
        raise
    try:
        finalize_attempt(output, output / 'analysis-report.json')
    except BaseException as exc:
        _write_new(output / 'saved_processing_failure.json',
                   {'type': type(exc).__name__, 'message': str(exc),
                    'delivery_ready': False})
        raise
    return output / 'attempt_report.json'


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--case-suffix', choices=CASE_SUFFIXES)
    parser.add_argument('--direction', type=int, choices=(-1, 1))
    parser.add_argument('--output-dir', type=Path)
    parser.add_argument('--rail-asset-blueprint')
    parser.add_argument('--host', default='localhost')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args()
    bundle = Path.cwd() if args.check else args.output_dir
    config_path = None if bundle is None else bundle / 'config.json'
    config = json.loads(config_path.read_text()) if config_path is not None and config_path.is_file() else None
    suffix = args.case_suffix or (config or {}).get('case_suffix', 'reference')
    direction = args.direction or (config or {}).get('direction', 1)
    if args.check:
        print(json.dumps(check(suffix, direction, config)))
    else:
        if args.output_dir is None:
            parser.error('--output-dir is required')
        import carla
        client = carla.Client(args.host, args.port)
        client.set_timeout(180)
        run(client, carla, args.output_dir, case_suffix=suffix,
            direction=direction,
            rail_asset_blueprint=args.rail_asset_blueprint)
