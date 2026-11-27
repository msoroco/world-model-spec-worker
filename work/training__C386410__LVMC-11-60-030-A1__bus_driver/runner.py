"""Exact two-location Native bus capture; `--check` stays CARLA-free.

Original velocity, control, pose, frame identities and pixels are retained. The
route designation and human operator require later independent source review.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import queue
import subprocess
import sys

from geometry import check as geometry_check, open_drive

ASSIGNMENT = 'training__C386410__LVMC-11-60-030-A1__bus_driver'
TARGET_X = {'designated_terminus': 5.0, 'undesignated_street': 40.0}
CAMERAS = (
    ('overview', 1920, 1080, 15, -12, 18, -45),
    ('approach', 1280, 720, -15, -12, 8, -25),
    ('reference_corner', 1280, 720, 5, -20, 7, -30),
    ('driver_reference', 1280, 720, 25, 1, 7, -30),
)
FRAMES = 600


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check():
    geometry = geometry_check()
    if (len(CAMERAS) != 4 or FRAMES / 20 != 30 or
            not geometry['zone_x_m'][0] < TARGET_X['designated_terminus'] < geometry['zone_x_m'][1] or
            not TARGET_X['undesignated_street'] > geometry['zone_x_m'][1]):
        raise ValueError('Two-location one-way capture geometry differs')
    return {'passed': True, 'geometry': geometry, 'cases': list(TARGET_X),
            'frames': FRAMES, 'native_imported': False, 'physical_acceptance_claimed': False}


def execute(case_id, output_dir, host, port):
    check()
    if not case_id.startswith(ASSIGNMENT + '__') or case_id.split('__')[-1] not in TARGET_X:
        raise ValueError('Unknown exact bus case')
    output = Path(output_dir).resolve()
    if not output.is_dir() or any((output / name).exists() for name in ('bus-history.jsonl', 'result.json')):
        raise ValueError('Fresh materialized Native attempt required')
    config = json.loads((output / 'config.json').read_text())
    selection = json.loads((output / 'candidate-selection.json').read_text())
    if (config.get('case_id') != case_id or config.get('selected_case_id') != case_id or
            config.get('case', {}).get('case_id') != case_id or
            selection.get('case_id') != case_id or selection.get('candidate_id') != 'primary'):
        raise ValueError('Materialized exact bus case identity differs')
    repo = next((p for p in Path(__file__).resolve().parents if (p / 'batch.json').is_file()), None)
    if repo is None:
        raise ValueError('Worker repository root absent')
    # Guard direct runtime imports so path defaults never point outside this attempt.
    os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT'] = str(output)
    sys.path.insert(0, str(repo / 'runtime' / 'scenario_pipeline'))
    sys.path.insert(1, str(repo / 'runtime' / 'python'))
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture
    from worker_exchange.world_restore import snapshot, restore

    client = carla.Client(host, port)
    client.set_timeout(180)
    saved = snapshot(client)
    old = client.get_world()
    if saved['settings'].synchronous_mode or any(a.type_id.startswith(('vehicle.', 'walker.', 'sensor.', 'controller.')) for a in old.get_actors()):
        raise RuntimeError('Exclusive idle asynchronous Native world required')
    owned, queues, encoders = [], {}, {}
    changed = False
    restoration = None
    try:
        world = client.generate_opendrive_world(open_drive(), carla.OpendriveGenerationParameters(
            vertex_distance=.5, max_road_length=25, wall_height=0,
            additional_width=0, smooth_junctions=False,
            enable_mesh_visibility=True, enable_pedestrian_navigation=False))
        changed = True
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        settings.substepping = True
        settings.max_substep_delta_time = .01
        settings.max_substeps = 10
        world.apply_settings(settings)
        world.set_weather(carla.WeatherParameters.ClearNoon)
        road = world.get_map().to_opendrive()
        (output / 'road.xodr').write_text(road)
        if 'BUS ROUTE TERMINUS' not in road:
            raise RuntimeError('Native terminus map marker readback absent')
        zone_kind = 'route_destination' if case_id.endswith('designated_terminus') else 'other_street'
        zone_id = 'route-destination-R1' if zone_kind == 'route_destination' else 'other-street-R1'
        zone = {'kind': zone_kind, 'id': zone_id, 'route_id': 'R1'}
        target = TARGET_X[case_id.split('__')[-1]]
        lane_readback = []
        for x in (target - 20, target):
            waypoint = world.get_map().get_waypoint(carla.Location(x=x, y=-5.25, z=1),
                project_to_road=True, lane_type=carla.LaneType.Parking)
            if waypoint is None or waypoint.road_id != 1 or waypoint.lane_id != -2:
                raise RuntimeError('Native one-way parking lane readback failed')
            lane_readback.append({'requested_x_m': x, 'road_id': waypoint.road_id,
                                  'lane_id': waypoint.lane_id,
                                  'native_xy_m': [waypoint.transform.location.x,
                                                  waypoint.transform.location.y]})
        if zone_kind != 'other_street':
            zone['designation_source'] = {'path': 'road.xodr', 'sha256': sha(output / 'road.xodr')}
        context = {'vehicle_class': 'route_bus_non_tour', 'vehicle_class_verified': False,
                   'route_id': 'R1', 'route_assignment_verified': False,
                   'street_id': 'native-road-1', 'street_status_verified': False,
                   'controller_policy': 'approach_then_stationary_brake_v1',
                   'weather_policy': 'ClearNoon',
                   'capture_profile': {'rate_hz': 20, 'frames': FRAMES,
                                       'cameras': {name: [width, height] for name, width, height, *_ in CAMERAS}},
                   'zone': zone, 'official_designation_verified': False,
                   'route_designation_source': {'candidate_reference': zone.get('designation_source'),
                                                'official_authority_verified': False},
                   'native_lane_readback': lane_readback,
                   'driver_presence_verified': False,
                   'source_note': 'Authored OpenDRIVE marker is only a source candidate, not administrative designation.'}
        (output / 'bus-context.json').write_text(json.dumps(context, indent=2) + '\n')
        bp = world.get_blueprint_library().find('vehicle.mitsubishi.fusorosa')
        bp.set_attribute('role_name', 'c386410_route_bus')
        bus = world.try_spawn_actor(bp, carla.Transform(carla.Location(x=target - 20, y=-5.25, z=1), carla.Rotation(yaw=0)))
        if bus is None:
            raise RuntimeError('Native route bus spawn failed')
        owned.append(bus)
        for name, width, height, x, y, z, pitch in CAMERAS:
            camera_bp = world.get_blueprint_library().find('sensor.camera.rgb')
            for key, value in (('image_size_x', width), ('image_size_y', height),
                               ('fov', 85), ('sensor_tick', .05)):
                camera_bp.set_attribute(key, str(value))
            camera = world.spawn_actor(camera_bp, carla.Transform(
                carla.Location(x=target + x - 5, y=y, z=z), carla.Rotation(pitch=pitch)))
            owned.append(camera)
            received = queue.Queue()
            camera.listen(received.put)
            queues[name] = received
            encoders[name] = subprocess.Popen(['ffmpeg', '-nostdin', '-hide_banner',
                '-loglevel', 'error', '-n', '-f', 'rawvideo', '-pix_fmt', 'bgra',
                '-s', f'{width}x{height}', '-r', '20', '-i', '-', '-frames:v',
                str(FRAMES), '-c:v', 'ffv1', str(output / (name + '.mkv'))],
                stdin=subprocess.PIPE, stderr=subprocess.PIPE)
        with PipelineCapture(client, bus, output, case_id, required_observations=[]) as capture, \
                FrameMap(output / 'video_frames.jsonl') as frame_map, \
                (output / 'bus-history.jsonl').open('x') as history:
            first = None
            for index in range(FRAMES):
                before = bus.get_transform().location.x
                speed_before = bus.get_velocity().length()
                remaining = target - before
                if remaining > 4:
                    control = carla.VehicleControl(throttle=.3, brake=0, hand_brake=False)
                elif remaining > .4 and speed_before > .2:
                    control = carla.VehicleControl(throttle=0, brake=.7, hand_brake=False)
                else:
                    control = carla.VehicleControl(throttle=0, brake=1,
                                                   hand_brake=speed_before < .2)
                bus.apply_control(control)
                native_frame = world.tick()
                snap = world.get_snapshot()
                if snap.frame != native_frame:
                    raise RuntimeError('Native frame/snapshot mismatch')
                if first is None:
                    first = snap.timestamp.elapsed_seconds
                time_s = snap.timestamp.elapsed_seconds - first
                camera_frames = {}
                for name, received in queues.items():
                    image = received.get(timeout=30)
                    while image.frame < native_frame:
                        image = received.get(timeout=30)
                    if image.frame != native_frame:
                        raise RuntimeError('Original camera/frame mismatch: ' + name)
                    encoders[name].stdin.write(image.raw_data)
                    camera_frames[name] = image.frame
                frame_map.append(native_frame, time_s, camera_native_frames=camera_frames)
                capture.capture(native_frame, time_s, extra={'video_frame': index,
                                'native_bus_actor_id': bus.id})
                pose, velocity = bus.get_transform(), bus.get_velocity()
                occupied = zone_id if abs(pose.location.x - target) < 5 and abs(pose.location.y + 5.25) < 2 else None
                history.write(json.dumps({'video_frame': index, 'native_frame': native_frame,
                    'time_s': time_s, 'bus_speed_mps': math.sqrt(velocity.x**2 + velocity.y**2 + velocity.z**2),
                    'parking_brake_applied': bool(control.hand_brake),
                    'driver_present': True, 'driver_presence_source': 'authored_controller_only',
                    'occupied_zone_id': occupied, 'position_xyz_m': [pose.location.x, pose.location.y, pose.location.z],
                    'actor_id': bus.id, 'blueprint_id': bus.type_id}) + '\n')
        for name, process in encoders.items():
            process.stdin.close()
            stderr = process.stderr.read()
            if process.wait(timeout=180):
                raise RuntimeError('Original camera encoder failed: ' + name + ': ' + stderr.decode()[-300:])
    except BaseException as error:
        (output / 'native-run-status.json').write_text(json.dumps({'errors': [str(error)]}) + '\n')
        raise
    finally:
        for process in encoders.values():
            if process.poll() is None:
                process.kill()
                process.wait()
        for actor in reversed(owned):
            try:
                if hasattr(actor, 'stop'):
                    actor.stop()
                actor.destroy()
            except Exception:
                pass
        if changed:
            restoration = restore(client, saved)
    (output / 'acquisition-provenance.json').write_text(json.dumps({
        'provenance_kind': 'native', 'diagnostic_fixture': False,
        'physical_acceptance_claimed': False}) + '\n')
    seal_capture(output, frames=FRAMES, restoration=restoration, errors=[],
                 encoder_exit_codes={name: process.returncode for name, process in encoders.items()},
                 context={'assignment_id': ASSIGNMENT, 'case_id': case_id})
    return {'case_id': case_id, 'frames': FRAMES, 'source_joins_retained': True,
            'official_designation_verified': False, 'physical_acceptance_claimed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--case-id')
    parser.add_argument('--output-dir')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args()
    if args.check:
        print(json.dumps(check(), sort_keys=True))
    else:
        if not args.output_dir:
            parser.error('--output-dir required')
        case_id = args.case_id or json.loads((Path(args.output_dir) / 'config.json').read_text())['case_id']
        print(json.dumps(execute(case_id, args.output_dir, args.host, args.port)))


if __name__ == '__main__':
    main()
