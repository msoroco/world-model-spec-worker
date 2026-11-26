"""Survey-gated Native driveway parking attempt for one exact selected case.

`--check` is CPU only. Running the capture needs a local CARLA owner and a
surveyed, source-reviewed straight one-way road with a real driveway opening.
"""
import argparse
import hashlib
import json
import math
import queue
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
AID = 'training__C150094__LVMC-11-52-130-A7__motor_vehicle_driver'
CASE = AID + '__probe_06'
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
COUNT = 600


def config_check():
    config = json.loads((HERE / 'config.json').read_text())
    if (config.get('case_id') != CASE or config.get('selected_case_id') != CASE or
            config.get('cell_id') != 'C150094' or config.get('law_id') != 'LVMC-11-52-130-A7' or
            config.get('actor') != 'motor_vehicle_driver' or config.get('candidate_id') != 'primary' or
            config.get('rate_hz') != 20 or config.get('duration_s') != 30 or
            config.get('frames') != COUNT or [c.get('name') for c in config.get('cameras', [])] != list(CAMERAS) or
            [(c.get('width'), c.get('height')) for c in config['cameras']] !=
            [(1920, 1080), (1280, 720), (1280, 720), (1280, 720)] or
            config.get('physical_acceptance_claimed') is not False or config.get('legal_verdict') is not None):
        raise ValueError('Exact driveway case identity or capture contract differs')
    return {'case_id': CASE, 'frames': COUNT, 'cameras': list(CAMERAS),
            'carla_imported': False, 'physical_acceptance_claimed': False}


def survey_check(survey):
    keys = ('map_name', 'survey_source', 'driveway_boundary_source', 'ego_blueprint',
            'spawn_xyz_m', 'spawn_yaw_deg', 'camera_world_transforms',
            'road_axis_xy', 'stop_centre_xyz_m', 'driveway_curb_interval_m',
            'ego_half_length_m', 'road_id')
    for key in keys:
        if key not in survey or survey[key] is None or survey[key] == '':
            raise ValueError('Missing Native survey source: ' + key)
    for key in ('spawn_xyz_m', 'stop_centre_xyz_m'):
        if len(survey[key]) != 3 or not all(type(v) in (int, float) and math.isfinite(v) for v in survey[key]):
            raise ValueError('Invalid surveyed position: ' + key)
    axis = survey['road_axis_xy']
    if len(axis) != 2 or not all(type(v) in (int, float) and math.isfinite(v) for v in axis) or abs(math.hypot(*axis)-1) > .01:
        raise ValueError('Surveyed road axis must be unit length')
    if set(survey['camera_world_transforms']) != set(CAMERAS):
        raise ValueError('Four surveyed source cameras required')
    for item in survey['camera_world_transforms'].values():
        if len(item.get('xyz_m', [])) != 3 or len(item.get('rotation_deg', [])) != 3:
            raise ValueError('Invalid surveyed camera transform')
    if len(survey['driveway_curb_interval_m']) != 2 or survey['driveway_curb_interval_m'][0] >= survey['driveway_curb_interval_m'][1]:
        raise ValueError('Invalid surveyed driveway opening')
    if survey['ego_half_length_m'] <= 0:
        raise ValueError('Invalid surveyed ego extent')
    if survey.get('driveway_kind') != 'public' or not survey.get('driveway_kind_source'):
        raise ValueError('Exact public driveway survey source required')
    config = json.loads((HERE / 'config.json').read_text())
    station = (survey['stop_centre_xyz_m'][0] * axis[0] +
               survey['stop_centre_xyz_m'][1] * axis[1])
    low, high = station - survey['ego_half_length_m'], station + survey['ego_half_length_m']
    opening = survey['driveway_curb_interval_m']
    planned_gap = max(opening[0] - high, low - opening[1], 0.0)
    if abs(planned_gap - config['target_gap_m']) > .25:
        raise ValueError('Surveyed stop point does not target this exact driveway gap')
    return survey


def transform(carla, xyz, rotation):
    return carla.Transform(carla.Location(x=xyz[0], y=xyz[1], z=xyz[2]),
                           carla.Rotation(pitch=rotation[0], yaw=rotation[1], roll=rotation[2]))


def capture(survey, output, host, port):
    import carla
    from pipeline_capture import PipelineCapture
    survey_check(survey)
    output.mkdir(parents=True, exist_ok=True)
    if (output/'video_frames.jsonl').exists() or (output/'native_parking_trace.jsonl').exists():
        raise ValueError('Retain prior Native source attempt; use a new output directory')
    client = carla.Client(host, port)
    client.set_timeout(120)
    world = client.get_world()
    if world.get_map().name != survey['map_name']:
        raise ValueError('Live CARLA map differs from reviewed survey')
    settings = world.get_settings()
    old_sync, old_step = settings.synchronous_mode, settings.fixed_delta_seconds
    actors, encoders = [], {}
    core_capture = None
    try:
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        world.apply_settings(settings)
        blueprint = world.get_blueprint_library().find(survey['ego_blueprint'])
        ego = world.try_spawn_actor(blueprint, transform(carla, survey['spawn_xyz_m'], [0, survey['spawn_yaw_deg'], 0]))
        if ego is None:
            raise RuntimeError('Surveyed ego spawn failed')
        actors.append(ego)
        waypoint = world.get_map().get_waypoint(ego.get_location(), project_to_road=True,
                                               lane_type=carla.LaneType.Driving)
        if waypoint is None or waypoint.road_id != survey['road_id']:
            raise ValueError('Live ego road differs from reviewed one-way survey')
        queues = {}
        for spec in json.loads((HERE/'config.json').read_text())['cameras']:
            camera = world.get_blueprint_library().find('sensor.camera.rgb')
            camera.set_attribute('image_size_x', str(spec['width']))
            camera.set_attribute('image_size_y', str(spec['height']))
            camera.set_attribute('fov', '80')
            loc = survey['camera_world_transforms'][spec['name']]
            sensor = world.spawn_actor(camera, transform(carla, loc['xyz_m'], loc['rotation_deg']))
            actors.append(sensor)
            q = queue.Queue()
            sensor.listen(q.put)
            queues[spec['name']] = q
            proc = subprocess.Popen(['ffmpeg', '-v', 'error', '-f', 'rawvideo', '-pixel_format', 'bgra',
                                     '-video_size', f"{spec['width']}x{spec['height']}", '-framerate', '20',
                                     '-i', '-', '-frames:v', str(COUNT), '-c:v', 'ffv1',
                                     str(output / (spec['name']+'.mkv'))], stdin=subprocess.PIPE)
            encoders[spec['name']] = proc
        core_capture = PipelineCapture(client, ego, output, CASE, required_observations=[])
        axis = survey['road_axis_xy']
        target = survey['stop_centre_xyz_m']
        first_elapsed = None
        with (output/'video_frames.jsonl').open('w') as frame_file, (output/'native_parking_trace.jsonl').open('w') as trace_file:
            for i in range(COUNT):
                pose = ego.get_transform()
                velocity = ego.get_velocity()
                speed = math.sqrt(velocity.x**2 + velocity.y**2 + velocity.z**2)
                distance = ((target[0]-pose.location.x)*axis[0] +
                            (target[1]-pose.location.y)*axis[1])
                braking = distance <= max(3.0, speed**2/4.0)
                ego.apply_control(carla.VehicleControl(throttle=0.0 if braking else .27,
                                                       brake=1.0 if braking else 0.0,
                                                       hand_brake=braking and speed < .05))
                native_frame = world.tick()
                snapshot = world.get_snapshot()
                if snapshot.frame != native_frame:
                    raise RuntimeError('Native world frame mismatch')
                if first_elapsed is None:
                    first_elapsed = snapshot.timestamp.elapsed_seconds
                pose = ego.get_transform()
                velocity = ego.get_velocity()
                speed = math.sqrt(velocity.x**2 + velocity.y**2 + velocity.z**2)
                vertices = ego.bounding_box.get_world_vertices(pose)
                stations = [v.x*axis[0]+v.y*axis[1] for v in vertices]
                station_center = (min(stations)+max(stations))/2
                half_extent = (max(stations)-min(stations))/2
                if half_extent <= 0:
                    raise RuntimeError('Native body footprint has zero road extent')
                core_capture.capture(native_frame, i/20,
                                     extra={'driveway_source': {
                                         'road_id': waypoint.road_id,
                                         'driveway_boundary_source': survey['driveway_boundary_source'],
                                         'curb_station_interval_m': survey['driveway_curb_interval_m']}})
                frame_file.write(json.dumps({'video_frame': i, 'native_frame': native_frame,
                                             'carla_frame': native_frame,
                                             'time_s': snapshot.timestamp.elapsed_seconds-first_elapsed})+'\n')
                trace_file.write(json.dumps({'video_frame': i, 'native_frame': native_frame,
                                             'source_kind': 'original_native_pose',
                                             'ego_curb_station_m': station_center,
                                             'ego_half_length_m': half_extent,
                                             'ego_speed_mps': speed,
                                             'park_brake_engaged': bool(ego.get_control().hand_brake)})+'\n')
                for camera_name, q in queues.items():
                    image = q.get(timeout=30)
                    if image.frame != native_frame:
                        raise RuntimeError('Camera frame does not join Native frame')
                    encoders[camera_name].stdin.write(image.raw_data)
        for proc in encoders.values():
            proc.stdin.close()
            if proc.wait(timeout=120) != 0:
                raise RuntimeError('Source camera encoding failed')
        core_capture.close(confirmed=True)
        core_capture = None
        camera_hashes = {name + '.mkv': hashlib.sha256((output/(name+'.mkv')).read_bytes()).hexdigest()
                         for name in CAMERAS}
        (output/'driveway_context.template.json').write_text(json.dumps({
            'assignment_id': AID, 'case_id': CASE,
            'review_kind': 'original_source_review', 'reviewer': None,
            'driveway_curb_interval_m': survey['driveway_curb_interval_m'],
            'driveway_boundary_source': survey['driveway_boundary_source'],
            'vehicle_extent_source': 'native_parking_trace.jsonl',
            'parking_state_source': 'native_parking_trace.jsonl',
            'camera_sha256': camera_hashes, 'review_required': True,
            'driveway_kind': None, 'owner_controller_family_invitee': None,
            'private_driveway_authority_role': None,
            'usps_vehicle': None, 'usps_official_business': None,
            'necessary_to_avoid_traffic_conflict': None,
            'complying_with_law': None, 'officer_direction': None,
            'traffic_device_direction': None,
            'private_driveway_authority_source': None,
            'usps_official_business_source': None,
            'traffic_conflict_source': None,
            'lawful_direction_source': None}, indent=2)+'\n')
        return {'case_id': CASE, 'source_frames': COUNT, 'physical_acceptance_claimed': False}
    finally:
        if core_capture is not None:
            core_capture.close(confirmed=False)
        for actor in reversed(actors):
            try:
                actor.destroy()
            except Exception:
                pass
        for proc in encoders.values():
            if proc.poll() is None:
                proc.kill()
                proc.wait()
        settings.synchronous_mode = old_sync
        settings.fixed_delta_seconds = old_step
        world.apply_settings(settings)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--survey', type=Path)
    parser.add_argument('--output-dir', type=Path)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args()
    checked = config_check()
    if args.check:
        print(json.dumps(checked, sort_keys=True))
    else:
        if args.survey is None or args.output_dir is None:
            parser.error('Supply reviewed --survey and --output-dir')
        print(json.dumps(capture(json.loads(args.survey.read_text()), args.output_dir, args.host, args.port)))
