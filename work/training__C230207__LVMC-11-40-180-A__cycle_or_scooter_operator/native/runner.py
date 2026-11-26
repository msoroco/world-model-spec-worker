"""Survey-gated original Native bicycle capture for Fremont sidewalk restriction."""
import argparse
import json
from pathlib import Path
import queue
import subprocess
import xml.etree.ElementTree as ET

from geometry import check as geometry_check, open_drive, SIGN_NAME

FRAMES = 600
RATE = 20
CAMERAS = (
    ('overview', 1920, 1080, 0, -18, 16, -40),
    ('approach', 1280, 720, -65, -9, 7, -18),
    ('reference_corner', 1280, 720, -55, -8, 5, -10),
    ('driver_reference', 1280, 720, 20, -12, 10, -30),
)


def behavior_plan(behavior):
    if behavior not in {'mounted_sidewalk', 'walk_cycle'}:
        raise ValueError('unknown controlled behavior')
    return {'behavior': behavior, 'cycle_start_xy_m': [-65, -5],
            'operator_start_xy_m': [-65, -4.2] if behavior == 'walk_cycle' else None,
            'target_speed_mps': 2.3, 'operator_cycle_max_separation_m':
                1.5 if behavior == 'walk_cycle' else None}


def check():
    g = geometry_check()
    if FRAMES / RATE != 30 or len(CAMERAS) != 4 or len({c[0] for c in CAMERAS}) != 4:
        raise ValueError('four cameras and 30-second capture required')
    return {'passed': True, 'geometry': g, 'frames': FRAMES, 'rate_hz': RATE,
            'cameras': [c[0] for c in CAMERAS], 'native_imported': False,
            'physical_acceptance_claimed': False}


def bicycle_blueprint(config):
    choice = config.get('bicycle_blueprint_id', 'vehicle.bh.crossbike')
    if choice not in ('vehicle.bh.crossbike', 'vehicle.diamondback.century'):
        raise ValueError('selected bicycle blueprint is not a source-listed ordinary bicycle')
    return choice


def survey(world, carla):
    mapping = world.get_map()
    root = ET.fromstring(mapping.to_opendrive())
    signals = [s for s in root.findall('.//signal') if s.attrib.get('id') == '100']
    if len(signals) != 1 or signals[0].attrib.get('name') != SIGN_NAME or signals[0].attrib.get('orientation') != '+':
        raise RuntimeError('Native signed bicycle restriction readback failed')
    lane_rows = []
    for x in (-40, 0, 40):
        wp = mapping.get_waypoint(carla.Location(x=x, y=-5, z=1),
                                  project_to_road=True, lane_type=carla.LaneType.Sidewalk)
        if wp is None or wp.road_id != 1 or wp.lane_id != -2:
            raise RuntimeError(f'Native governed roadway readback failed at x={x}')
        position = wp.transform.location
        if abs(position.x-x) > 1 or abs(position.y+5) > 1:
            raise RuntimeError(f'Native governed roadway position readback failed at x={x}')
        lane_rows.append({'requested_x_m': x, 'native_xyz_m': [position.x, position.y, position.z],
                          'road_id': wp.road_id, 'lane_id': wp.lane_id})
    return {'sign': dict(signals[0].attrib), 'sidewalk': lane_rows,
            'sign_pixels_confirmed': False, 'geographic_identity_confirmed': False}


def execute(output_dir, host, port, behavior):
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture
    from worker_exchange.world_restore import snapshot, restore
    check()
    plan = behavior_plan(behavior)
    output = Path(output_dir).resolve()
    if not output.is_dir() or (output / 'bicycle-poses.jsonl').exists():
        raise ValueError('new materialized original Native attempt required')
    config = json.loads((output / 'config.json').read_text())
    if config.get('controlled_behavior') != behavior:
        raise ValueError('selected construction behavior differs')
    blueprint_id = bicycle_blueprint(config)
    client = carla.Client(host, port)
    client.set_timeout(180)
    saved = snapshot(client)
    old = client.get_world()
    if saved['settings'].synchronous_mode or any(a.type_id.startswith(
            ('vehicle.', 'walker.', 'sensor.', 'controller.')) for a in old.get_actors()):
        raise RuntimeError('requires an exclusive idle asynchronous Native world')
    owned, encoders, queues = [], {}, {}
    encoder_exits = {}
    capture = None
    changed = False
    completed = False
    try:
        world = client.generate_opendrive_world(open_drive(), carla.OpendriveGenerationParameters(
            vertex_distance=.5, max_road_length=25, wall_height=0, additional_width=0,
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
        readback = survey(world, carla)
        (output / 'road.xodr').write_text(world.get_map().to_opendrive())
        blueprints = world.get_blueprint_library()
        bicycle_bp = blueprints.find(blueprint_id)
        bicycle_bp.set_attribute('role_name', 'c230207_human_bicycle_subject')
        bicycle = world.spawn_actor(bicycle_bp, carla.Transform(
            carla.Location(x=plan['cycle_start_xy_m'][0], y=plan['cycle_start_xy_m'][1], z=1),
            carla.Rotation(yaw=0)))
        owned.append(bicycle)
        operator = None
        if behavior == 'walk_cycle':
            walker_bp = blueprints.find('walker.pedestrian.0001')
            walker_bp.set_attribute('role_name', 'c230207_dismounted_operator')
            operator = world.spawn_actor(walker_bp, carla.Transform(
                carla.Location(x=plan['operator_start_xy_m'][0], y=plan['operator_start_xy_m'][1], z=1),
                carla.Rotation(yaw=0)))
            owned.append(operator)
        (output / 'restriction-context.json').write_text(json.dumps({
            'rider_class': 'human_propelled_bicycle', 'blueprint_id': bicycle.type_id,
            'wheel_characteristics_reviewed': False,
            'sign_id': '100', 'sign_text': SIGN_NAME, 'sign_x_m': -55,
            'sign_orientation': 'positive_s',
            'native_sign_survey': readback['sign'], 'native_sidewalk_survey': readback['sidewalk'],
            'sidewalk_xy_m': [[-60, -6.5], [60, -6.5], [60, -3.5], [-60, -3.5]],
            'street_name': 'Fremont Street', 'west_boundary': 'Main Street',
            'east_boundary': 'Seventh Street', 'geographic_identity_verified': False,
            'posture_visual_review_required': True,
            'controlled_behavior': behavior,
            'operator_actor_id': operator.id if operator is not None else None,
            'operator_blueprint_id': operator.type_id if operator is not None else None,
            'dismounted_association_max_separation_m': plan['operator_cycle_max_separation_m'],
            'physical_sign_pixels_verified': False}, indent=2) + '\n')
        for name, width, height, x, y, z, pitch in CAMERAS:
            bp = blueprints.find('sensor.camera.rgb')
            bp.set_attribute('image_size_x', str(width))
            bp.set_attribute('image_size_y', str(height))
            bp.set_attribute('fov', '85')
            bp.set_attribute('sensor_tick', str(1 / RATE))
            camera = world.spawn_actor(bp, carla.Transform(
                carla.Location(x=x, y=y, z=z), carla.Rotation(pitch=pitch)))
            owned.append(camera)
            q = queue.Queue()
            camera.listen(q.put)
            queues[name] = q
            encoders[name] = subprocess.Popen([
                'ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-y',
                '-f', 'rawvideo', '-pix_fmt', 'bgra', '-s', f'{width}x{height}',
                '-r', str(RATE), '-i', '-', '-frames:v', str(FRAMES),
                '-c:v', 'ffv1', '-level', '1', str(output / (name + '.mkv'))],
                stdin=subprocess.PIPE, stderr=subprocess.PIPE)
        capture = PipelineCapture(client, bicycle, output, config['case_id'],
                                  required_observations=[])
        with FrameMap(output / 'video_frames.jsonl') as frame_map, \
                (output / 'bicycle-poses.jsonl').open('x') as poses:
            first_elapsed = None
            for index in range(FRAMES):
                bicycle.set_target_velocity(carla.Vector3D(x=plan['target_speed_mps'], y=0, z=0))
                if operator is not None:
                    operator.apply_control(carla.WalkerControl(direction=carla.Vector3D(x=1, y=0, z=0),
                                                              speed=plan['target_speed_mps'], jump=False))
                native_frame = world.tick()
                native_snapshot = world.get_snapshot()
                if native_snapshot.frame != native_frame:
                    raise RuntimeError('Native frame/snapshot identity differs')
                absolute_time = native_snapshot.timestamp.elapsed_seconds
                if first_elapsed is None:
                    first_elapsed = absolute_time
                relative_time = absolute_time - first_elapsed
                transform = bicycle.get_transform()
                velocity = bicycle.get_velocity()
                operator_transform = operator.get_transform() if operator is not None else None
                operator_velocity = operator.get_velocity() if operator is not None else None
                mapped = {}
                for name in queues:
                    image = queues[name].get(timeout=30)
                    while image.frame < native_frame:
                        image = queues[name].get(timeout=30)
                    if image.frame != native_frame:
                        raise RuntimeError(f'Original camera frame join failed: {name}')
                    encoders[name].stdin.write(image.raw_data)
                    mapped[name] = image.frame
                frame_map.append(native_frame, relative_time, camera_native_frames=mapped)
                poses.write(json.dumps({'video_frame': index, 'native_frame': native_frame,
                    'time_s': relative_time, 'native_elapsed_seconds': absolute_time,
                    'rider_xy_m': [transform.location.x, transform.location.y],
                    'rider_z_m': transform.location.z,
                    'velocity_xy_mps': [velocity.x, velocity.y],
                    'rider_actor_id': bicycle.id, 'rider_blueprint_id': bicycle.type_id,
                    'mounted_posture': 'unverified', 'machine_class': 'human_propelled_bicycle',
                    'controlled_behavior': behavior,
                    'operator_actor_id': operator.id if operator is not None else None,
                    'operator_blueprint_id': operator.type_id if operator is not None else None,
                    'operator_xy_m': [operator_transform.location.x, operator_transform.location.y]
                    if operator_transform is not None else None,
                    'operator_velocity_xy_mps': [operator_velocity.x, operator_velocity.y]
                    if operator_velocity is not None else None}) + '\n')
                capture.capture(native_frame, relative_time, extra={
                    'c230207_sidewalk': {'cycle_actor_id': bicycle.id,
                                         'operator_actor_id': operator.id if operator else None,
                                         'camera_native_frames': mapped}})
        for name, process in encoders.items():
            process.stdin.close()
            stderr = process.stderr.read()
            encoder_exits[name] = process.wait(timeout=180)
            if encoder_exits[name] or not (output / (name + '.mkv')).is_file():
                raise RuntimeError(f'Original camera encoding failed: {name}: {stderr.decode()[-400:]}')
        capture.close(confirmed=True)
        capture = None
        (output / 'acquisition-provenance.json').write_text(json.dumps({
            'provenance_kind': 'native', 'diagnostic_fixture': False,
            'case_id': config['case_id'], 'controlled_behavior': behavior,
            'physical_acceptance_claimed': False}, indent=2) + '\n')
        completed = True
        return {'frames': FRAMES, 'camera_names': list(queues),
                'native_survey': readback, 'physical_acceptance_claimed': False}
    finally:
        if capture is not None:
            capture.close(confirmed=False)
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
            restored = restore(client, saved)
            if completed and capture is None and len(encoder_exits) == len(CAMERAS):
                seal_capture(output, frames=FRAMES, restoration=restored, errors=[],
                             encoder_exit_codes=encoder_exits,
                             context={'case_id': config['case_id'],
                                      'controlled_behavior': behavior})


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--check', action='store_true')
    p.add_argument('--execute', action='store_true')
    p.add_argument('--output-dir')
    p.add_argument('--host', default='127.0.0.1')
    p.add_argument('--port', type=int, default=2000)
    p.add_argument('--behavior', choices=('mounted_sidewalk', 'walk_cycle'), default='mounted_sidewalk')
    a = p.parse_args()
    if a.check:
        print(json.dumps(check()))
    else:
        if not a.output_dir:
            raise SystemExit('--output-dir required for Native execution')
        config = json.loads((Path(a.output_dir) / 'config.json').read_text())
        behavior = config['controlled_behavior']
        if a.execute and a.behavior != 'mounted_sidewalk' and a.behavior != behavior:
            raise SystemExit('explicit behavior differs from selected construction')
        print(json.dumps(execute(a.output_dir, a.host, a.port, behavior)))
