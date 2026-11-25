"""Survey-gated Native signed-speed-zone attempt for exact probe_03.

`--check` is CPU only. Physical capture requires local CARLA ownership and a
reviewed speed-zone survey; requested speed is never an observed velocity.
"""
import argparse
import json
import math
import queue
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
AID = 'training__C179819__NRS-484B-620-2__motor_vehicle_driver'
CASE = AID + '__probe_02'
CAMERAS = ('forward', 'rear', 'left', 'right')
COUNT = 600
MPS_PER_MPH = 0.44704


def config_check():
    config = json.loads((HERE/'config.json').read_text())
    if (config.get('case_id') != CASE or config.get('selected_case_id') != CASE or
            config.get('cell_id') != 'C179819' or config.get('law_id') != 'NRS-484B-620-2' or
            config.get('actor') != 'motor_vehicle_driver' or config.get('candidate_id') != 'primary' or
            config.get('rate_hz') != 20 or config.get('duration_s') != 30 or
            config.get('frames') != COUNT or [c.get('name') for c in config.get('cameras', [])] != list(CAMERAS) or
            [(c.get('width'), c.get('height')) for c in config['cameras']] !=
            [(1920, 1080), (1280, 720), (1280, 720), (1280, 720)] or
            config.get('physical_acceptance_claimed') is not False or config.get('legal_verdict') is not None):
        raise ValueError('Exact signed-zone case identity or capture contract differs')
    return {'case_id': CASE, 'frames': COUNT, 'cameras': list(CAMERAS),
            'carla_imported': False, 'physical_acceptance_claimed': False}


def survey_check(survey):
    keys = ('map_name', 'survey_source', 'zone_establishment_source', 'installed_sign_source',
            'authorized_value_source', 'zone_boundary_source', 'governing_road_direction_source',
            'ego_blueprint', 'spawn_xyz_m', 'spawn_yaw_deg', 'camera_world_transforms',
            'road_axis_xy', 'zone_station_bounds_m', 'authorized_mph', 'road_id',
            'travel_direction_id')
    for key in keys:
        if key not in survey or survey[key] is None or survey[key] == '':
            raise ValueError('Missing reviewed Native survey source: ' + key)
    if len(survey['spawn_xyz_m']) != 3 or not all(type(v) in (int, float) and math.isfinite(v) for v in survey['spawn_xyz_m']):
        raise ValueError('Invalid surveyed spawn')
    axis = survey['road_axis_xy']
    if len(axis) != 2 or not all(type(v) in (int, float) and math.isfinite(v) for v in axis) or abs(math.hypot(*axis)-1) > .01:
        raise ValueError('Surveyed road axis must be unit length')
    bounds = survey['zone_station_bounds_m']
    if len(bounds) != 2 or not all(type(v) in (int, float) and math.isfinite(v) for v in bounds) or bounds[0] >= bounds[1]:
        raise ValueError('Invalid surveyed zone bounds')
    if type(survey['authorized_mph']) not in (int, float) or not math.isfinite(survey['authorized_mph']) or survey['authorized_mph'] <= 0:
        raise ValueError('Invalid surveyed authorized speed')
    if set(survey['camera_world_transforms']) != set(CAMERAS):
        raise ValueError('Four surveyed source cameras required')
    for item in survey['camera_world_transforms'].values():
        if len(item.get('xyz_m', [])) != 3 or len(item.get('rotation_deg', [])) != 3:
            raise ValueError('Invalid surveyed camera transform')
    return survey


def transform(carla, xyz, rotation):
    return carla.Transform(carla.Location(x=xyz[0], y=xyz[1], z=xyz[2]),
                           carla.Rotation(pitch=rotation[0], yaw=rotation[1], roll=rotation[2]))


def capture(survey, output, host, port):
    import carla
    survey_check(survey)
    output.mkdir(parents=True, exist_ok=True)
    if (output/'video_frames.jsonl').exists() or (output/'native_motion.jsonl').exists():
        raise ValueError('Retain prior Native source attempt; use a new directory')
    client = carla.Client(host, port)
    client.set_timeout(120)
    world = client.get_world()
    if world.get_map().name != survey['map_name']:
        raise ValueError('Live CARLA map differs from reviewed survey')
    settings = world.get_settings()
    old_sync, old_step = settings.synchronous_mode, settings.fixed_delta_seconds
    actors, encoders = [], {}
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
            raise ValueError('Live ego road differs from reviewed zone road')
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
            encoders[spec['name']] = subprocess.Popen(
                ['ffmpeg', '-v', 'error', '-f', 'rawvideo', '-pixel_format', 'bgra',
                 '-video_size', f"{spec['width']}x{spec['height']}", '-framerate', '20',
                 '-i', '-', '-frames:v', str(COUNT), '-c:v', 'ffv1',
                 str(output/('camera_'+spec['name']+'.mkv'))], stdin=subprocess.PIPE)
        target_mps = (survey['authorized_mph']+0.0)*MPS_PER_MPH
        first_elapsed = None
        with (output/'video_frames.jsonl').open('w') as frame_file, (output/'native_motion.jsonl').open('w') as motion_file:
            for i in range(COUNT):
                velocity = ego.get_velocity()
                speed = math.sqrt(velocity.x**2 + velocity.y**2 + velocity.z**2)
                error = target_mps-speed
                ego.apply_control(carla.VehicleControl(throttle=max(0.0, min(.8, .25+.2*error)),
                                                       brake=max(0.0, min(1.0, -.2*error)), steer=0.0))
                native_frame = world.tick()
                snapshot = world.get_snapshot()
                if snapshot.frame != native_frame:
                    raise RuntimeError('Native world frame mismatch')
                if first_elapsed is None:
                    first_elapsed = snapshot.timestamp.elapsed_seconds
                pose = ego.get_transform()
                velocity = ego.get_velocity()
                observed_waypoint = world.get_map().get_waypoint(pose.location, project_to_road=True,
                                                                  lane_type=carla.LaneType.Driving)
                if observed_waypoint is None:
                    raise RuntimeError('Native ego has no measured driving road')
                if velocity.x*survey['road_axis_xy'][0]+velocity.y*survey['road_axis_xy'][1] < -.1:
                    raise RuntimeError('Native ego motion opposes surveyed sign direction')
                frame_file.write(json.dumps({'video_frame': i, 'native_frame': native_frame,
                                             'time_s': snapshot.timestamp.elapsed_seconds-first_elapsed})+'\n')
                motion_file.write(json.dumps({'video_frame': i, 'native_frame': native_frame,
                                              'source_kind': 'original_native_velocity',
                                              'road_id': observed_waypoint.road_id,
                                              'travel_direction_id': survey['travel_direction_id'],
                                              'ego_x_m': pose.location.x, 'ego_y_m': pose.location.y,
                                              'velocity_x_mps': velocity.x,
                                              'velocity_y_mps': velocity.y,
                                              'velocity_z_mps': velocity.z})+'\n')
                for camera_name, q in queues.items():
                    image = q.get(timeout=30)
                    if image.frame != native_frame:
                        raise RuntimeError('Camera frame does not join Native frame')
                    encoders[camera_name].stdin.write(image.raw_data)
        for proc in encoders.values():
            proc.stdin.close()
            if proc.wait(timeout=120) != 0:
                raise RuntimeError('Source camera encoding failed')
        (output/'speed_zone_context.template.json').write_text(json.dumps({
            'assignment_id': AID, 'review_kind': 'original_source_review',
            'zone_station_bounds_m': survey['zone_station_bounds_m'],
            'road_axis_xy': survey['road_axis_xy'], 'road_id': survey['road_id'],
            'travel_direction_id': survey['travel_direction_id'],
            'authorized_mph': survey['authorized_mph'],
            'camera_sha256': {}, 'review_required': True}, indent=2)+'\n')
        return {'case_id': CASE, 'source_frames': COUNT,
                'requested_target_mps': target_mps, 'physical_acceptance_claimed': False}
    finally:
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
