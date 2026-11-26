"""Native graded-stand capture with explicit fail-closed instrument gaps.

CARLA provides brake command/readback and actor motion. This source does not
claim engine-off, actual wheel direction, or unattended occupancy from commands.
"""
import hashlib
import json
import math
from pathlib import Path
import queue
import subprocess
import xml.etree.ElementTree as ET

from grade import check as grade_check, open_drive
from instrumentation import InstrumentClient, wheel_angles

FRAMES = 600
RATE = 20
CASES = {'reference': {'brake': True, 'steer': -.55},
         'contrast': {'brake': False, 'steer': 0.0}}
CAMERAS = (('overview', -25, -15, 13, -45), ('curb', 2, -8, 5, -25),
           ('wheel', 4, -5, 2, -12), ('cabin', -3, 1, 3, -10))


def check():
    g = grade_check()
    if (FRAMES / RATE != 30 or len(CAMERAS) != 4 or
            len({row[0] for row in CAMERAS}) != 4 or
            CASES['reference'] == CASES['contrast']):
        raise ValueError('Graded stand capture design differs')
    return {'passed': True, 'cases': CASES, 'frames': FRAMES, 'rate_hz': RATE,
            'cameras': [x[0] for x in CAMERAS], 'geometry': g,
            'engine_wheel_occupancy_instrumentation': 'external_original_service_required',
            'native_executed': False}


def _survey(mapping, carla):
    root = ET.fromstring(mapping.to_opendrive())
    road = next((r for r in root.findall('road') if r.attrib.get('id') == '1'), None)
    if road is None:
        raise RuntimeError('Original graded road absent')
    profile = road.find('elevationProfile/elevation')
    lane = road.find('lanes/laneSection/right/lane')
    if (profile is None or lane is None or float(profile.attrib.get('b', 0)) != .04 or
            lane.attrib.get('id') != '-1' or float(lane.find('width').attrib.get('a', 0)) != 3.5):
        raise RuntimeError('Original grade/curb geometry readback differs')
    wp = mapping.get_waypoint(carla.Location(x=0, y=-1.75, z=6),
                              project_to_road=True, lane_type=carla.LaneType.Driving)
    if wp is None or wp.road_id != 1 or wp.lane_id != -1:
        raise RuntimeError('Original parking-lane waypoint differs')
    return {'format': 'c276263-grade-readback-v1', 'source_kind': 'native_map',
            'road_id': 1, 'slope_fraction': float(profile.attrib['b']),
            'right_curb_y_m': -3.5, 'parking_waypoint_xyz_m':
            [wp.transform.location.x, wp.transform.location.y, wp.transform.location.z],
            'opendrive_sha256': hashlib.sha256(mapping.to_opendrive().encode()).hexdigest()}


def execute(case, output_dir, host='127.0.0.1', port=2000,
            instrument_host=None, instrument_port=None):
    import carla
    from worker_exchange.native_output import FrameMap
    from worker_exchange.world_restore import snapshot, restore
    check()
    if case not in CASES:
        raise ValueError('Unknown exact case')
    if not instrument_host or type(instrument_port) is not int or not (1 <= instrument_port <= 65535):
        raise ValueError('Original engine, wheel calibration and attendance instrument endpoint required')
    output = Path(output_dir).resolve()
    if output.exists():
        raise ValueError('Use a fresh original Native attempt directory')
    client = carla.Client(host, port)
    client.set_timeout(180)
    saved = snapshot(client)
    initial = client.get_world()
    if saved['settings'].synchronous_mode or any(actor.type_id.startswith(
            ('vehicle.', 'walker.', 'sensor.', 'controller.')) for actor in initial.get_actors()):
        raise RuntimeError('Exclusive idle asynchronous Native world required')
    owned, encoders, camera_queues = [], {}, {}
    instruments = None
    changed = False
    try:
        world = client.generate_opendrive_world(open_drive(), carla.OpendriveGenerationParameters(
            vertex_distance=.5, max_road_length=40, wall_height=0, additional_width=0,
            smooth_junctions=False, enable_mesh_visibility=True,
            enable_pedestrian_navigation=False))
        changed = True
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 1 / RATE
        settings.substepping = True
        settings.max_substep_delta_time = .01
        settings.max_substeps = 10
        world.apply_settings(settings)
        survey = _survey(world.get_map(), carla)
        wp = world.get_map().get_waypoint(carla.Location(x=0, y=-1.75, z=6),
                                          project_to_road=True,
                                          lane_type=carla.LaneType.Driving)
        bp = world.get_blueprint_library()
        vehicle_bp = bp.find('vehicle.lincoln.mkz_2020')
        vehicle_bp.set_attribute('role_name', 'c276263_graded_standing_vehicle')
        spawn = carla.Transform(wp.transform.location + carla.Location(z=.5),
                                carla.Rotation(yaw=0))
        vehicle = world.spawn_actor(vehicle_bp, spawn)
        owned.append(vehicle)
        if vehicle.type_id != 'vehicle.lincoln.mkz_2020':
            raise RuntimeError('Original motor vehicle blueprint differs')
        instruments = InstrumentClient(instrument_host, instrument_port)
        output.mkdir(parents=True)
        (output / 'road.xodr').write_text(world.get_map().to_opendrive())
        (output / 'grade-readback.json').write_text(json.dumps(survey, indent=2) + '\n')
        for name, x, y, z, pitch in CAMERAS:
            camera_bp = bp.find('sensor.camera.rgb')
            camera_bp.set_attribute('image_size_x', '1280')
            camera_bp.set_attribute('image_size_y', '720')
            camera_bp.set_attribute('fov', '85')
            camera_bp.set_attribute('sensor_tick', str(1 / RATE))
            camera = world.spawn_actor(camera_bp, carla.Transform(
                carla.Location(x=x, y=y, z=z + survey['parking_waypoint_xyz_m'][2]),
                carla.Rotation(pitch=pitch)))
            owned.append(camera)
            q = queue.Queue()
            camera.listen(q.put)
            camera_queues[name] = q
            encoders[name] = subprocess.Popen([
                'ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-y',
                '-f', 'rawvideo', '-pix_fmt', 'bgra', '-s', '1280x720', '-r', str(RATE),
                '-i', '-', '-frames:v', str(FRAMES), '-c:v', 'ffv1', '-level', '1',
                str(output / (name + '.mkv'))], stdin=subprocess.PIPE,
                stderr=subprocess.PIPE)
        with FrameMap(output / 'video_frames.jsonl') as frame_map, (
                output / 'vehicle-frames.jsonl').open('x') as vehicle_rows, (
                output / 'occupancy-frames.jsonl').open('x') as occupancy_rows:
            first_elapsed = None
            for i in range(FRAMES):
                controls = CASES[case]
                vehicle.apply_control(carla.VehicleControl(throttle=0, brake=0,
                    hand_brake=controls['brake'], steer=controls['steer']))
                native_frame = world.tick()
                native_snapshot = world.get_snapshot()
                if native_snapshot.frame != native_frame:
                    raise RuntimeError('Original Native frame/snapshot join differs')
                elapsed = native_snapshot.timestamp.elapsed_seconds
                if first_elapsed is None:
                    first_elapsed = elapsed
                time_s = elapsed - first_elapsed
                cam_hashes, cam_frames = {}, {}
                for name, _, _, _, _ in CAMERAS:
                    image = camera_queues[name].get(timeout=30)
                    while image.frame < native_frame:
                        image = camera_queues[name].get(timeout=30)
                    if image.frame != native_frame:
                        raise RuntimeError('Original camera frame join differs: ' + name)
                    encoders[name].stdin.write(image.raw_data)
                    cam_hashes[name] = hashlib.sha256(image.raw_data).hexdigest()
                    cam_frames[name] = image.frame
                frame_map.append(native_frame, time_s,
                                 camera_native_frames=cam_frames,
                                 camera_raw_sha256=cam_hashes)
                v = vehicle.get_velocity()
                t = vehicle.get_transform()
                c = vehicle.get_control()
                wheels = wheel_angles(vehicle, carla)
                instrument = instruments.sample(native_frame, vehicle.id, wheels)
                common = {'frame': i, 'native_frame': native_frame, 'time_s': time_s}
                vehicle_rows.write(json.dumps(dict(common, source_kind='native_actor',
                    actor_id=vehicle.id, blueprint=vehicle.type_id,
                    engine_source='instrumented_engine_sensor',
                    engine_running=instrument['engine_running'],
                    engine_method=instrument['engine_method'],
                    instrument_id=instrument['instrument_id'],
                    brake_source='native_control_readback', parking_brake_set=bool(c.hand_brake),
                    wheel_source='instrumented_front_wheel_sensor',
                    front_wheel_heading_to_curb_deg=instrument['front_wheel_heading_to_curb_deg'],
                    front_wheel_angles_native_deg=wheels,
                    wheel_calibration_id=instrument['wheel_calibration_id'],
                    requested_steer=float(controls['steer']),
                    speed_mps=math.hypot(v.x, v.y), position_x_m=t.location.x)) + '\n')
                occupancy_rows.write(json.dumps(dict(common,
                    source_kind='occupancy_sensor',
                    occupant_count=instrument['occupant_count'],
                    responsible_person_outside=instrument['responsible_person_outside'],
                    attendance_method=instrument['attendance_method'],
                    responsible_person_id=instrument['responsible_person_id'],
                    instrument_id=instrument['instrument_id'])) + '\n')
        for name, process in encoders.items():
            process.stdin.close()
            errors = process.stderr.read()
            if process.wait(timeout=180) or not (output / (name + '.mkv')).is_file():
                raise RuntimeError('Original camera encoding failed ' + name + ': ' + errors.decode()[-400:])
        from measure import SOURCES, sha
        (output / 'source-hashes.json').write_text(json.dumps(
            {name: sha(output / name) for name in SOURCES}, indent=2) + '\n')
        (output / 'instrument-review-required.json').write_text(json.dumps({
            'format': 'c276263-instrument-review-v2', 'case': case,
            'instrument_endpoint': [instrument_host, instrument_port],
            'native_control_readback': ['parking_brake_set', 'requested_steer'],
            'original_instrument_fields': ['engine_running', 'front_wheel_heading_to_curb_deg',
                'occupant_count', 'responsible_person_outside'],
            'physical_calibration_and_attendance_review_required': True,
            'do_not_relabel_commands_as_original': True}, indent=2) + '\n')
        return {'case': case, 'frames': FRAMES,
                'native_brake_and_motion_captured': True,
                'engine_wheel_occupancy_instrumentation': 'original_service_packets_recorded',
                'saved_measurement_ready': True,
                'physical_acceptance_claimed': False}
    finally:
        if instruments is not None:
            instruments.close()
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
            restore(client, saved)
