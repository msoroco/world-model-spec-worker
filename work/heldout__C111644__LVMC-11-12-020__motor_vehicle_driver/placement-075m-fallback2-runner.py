"""CARLA-lazy Native turn-course capture for one exact selected case.

The operator supplies a reviewed, hashed map/authority record. This runner
retains source images and motion; CPU --check cannot establish authorization,
visible pixels, realized route, or legal obedience.
"""
import argparse
import hashlib
import json
import os
from math import hypot
from pathlib import Path
import subprocess
from threading import Condition
from time import monotonic

from indication_native import load_source, place_indications
from turn_marking import control_to_target, native_route_plan

CAMERAS = {
    'overview': ((-7., 0., 8.), (0., -18., 0.), (1920, 1080), 95),
    'approach': ((1., 0., 2.), (0., 0., 0.), (1280, 720), 90),
    'reference_corner': ((-2., 2.5, 2.6), (0., -8., 20.), (1280, 720), 100),
    'driver_reference': ((.5, -.3, 1.6), (0., 0., 0.), (1280, 720), 85),
}


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _rows(path, rows):
    with Path(path).open('x') as stream:
        for row in rows:
            stream.write(json.dumps(row, allow_nan=False) + '\n')


class OriginalCameras:
    def __init__(self, world, carla, ego, output):
        self.output = Path(output)
        self.condition = Condition()
        self.sensors = []
        self.encoders = {}
        self.rows = {name: [] for name in CAMERAS}
        self.errors = []
        self.closed = False
        try:
            for name, (place, rotation, size, fov) in CAMERAS.items():
                blueprint = world.get_blueprint_library().find('sensor.camera.rgb')
                for key, value in (('image_size_x', size[0]), ('image_size_y', size[1]),
                                   ('fov', fov), ('sensor_tick', .05)):
                    blueprint.set_attribute(key, str(value))
                camera = world.spawn_actor(blueprint,
                    carla.Transform(carla.Location(*place), carla.Rotation(*rotation)),
                    attach_to=ego)
                if camera is None:
                    raise ValueError('Native source camera spawn failed: ' + name)
                self.sensors.append(camera)
                stderr = (self.output / (name + '-encoder.log')).open('xb')
                try:
                    encoder = subprocess.Popen(['ffmpeg', '-hide_banner', '-loglevel', 'error',
                        '-f', 'rawvideo', '-pixel_format', 'bgra',
                        '-video_size', f'{size[0]}x{size[1]}', '-framerate', '20',
                        '-i', 'pipe:0', '-an', '-c:v', 'ffv1', '-threads', '1',
                        str(self.output / (name + '.mkv'))], stdin=subprocess.PIPE,
                        stdout=subprocess.DEVNULL, stderr=stderr)
                except BaseException:
                    stderr.close()
                    raise
                self.encoders[name] = (encoder, stderr)
                camera.listen(lambda image, view=name: self._receive(view, image))
        except BaseException:
            self.close()
            raise

    def _receive(self, name, image):
        with self.condition:
            try:
                if self.closed or name not in self.encoders:
                    raise ValueError('Original source camera closed')
                size = CAMERAS[name][2]
                if (image.width, image.height) != size or len(image.raw_data) != size[0] * size[1] * 4:
                    raise ValueError('Original source image size differs: ' + name)
                rows = self.rows[name]
                if rows and image.frame <= rows[-1]['frame']:
                    raise ValueError('Original camera frame repeated or reordered: ' + name)
                encoder = self.encoders[name][0]
                if encoder.poll() is not None:
                    raise ValueError('Original camera encoder exited: ' + name)
                encoder.stdin.write(bytes(image.raw_data))
                rows.append({'frame': int(image.frame), 'time_s': float(image.timestamp)})
            except BaseException as error:
                self.errors.append(error)
            finally:
                self.condition.notify_all()

    def wait(self, frame, timeout_s=10.):
        deadline = monotonic() + timeout_s
        with self.condition:
            while True:
                if self.errors:
                    raise ValueError('Original source camera callback failed') from self.errors[0]
                if all(self.rows[name] and self.rows[name][-1]['frame'] == frame for name in CAMERAS):
                    return
                remaining = deadline - monotonic()
                if remaining <= 0:
                    raise ValueError('Missing synchronized original camera frame')
                self.condition.wait(remaining)

    def close(self):
        if self.closed:
            return
        self.closed = True
        for sensor in reversed(self.sensors):
            sensor.stop()
            sensor.destroy()
        errors = []
        for name, (encoder, stderr) in self.encoders.items():
            try:
                if encoder.stdin and not encoder.stdin.closed:
                    encoder.stdin.close()
                if encoder.wait(timeout=30) != 0:
                    errors.append(name)
            finally:
                stderr.close()
        if errors:
            raise ValueError('Original source camera encoder failed: ' + ', '.join(errors))


def _body(actor):
    transform = actor.get_transform()
    vertices = actor.bounding_box.get_world_vertices(transform)
    points = []
    for vertex in vertices:
        point = [float(vertex.x), float(vertex.y)]
        if not any(hypot(point[0]-old[0], point[1]-old[1]) < .0001 for old in points):
            points.append(point)
    if len(points) != 4:
        raise ValueError('Original vehicle footprint must have four corners')
    velocity = actor.get_velocity()
    return {'actor_id': int(actor.id), 'body_vertices_m': points,
            'center_xy_m': [sum(p[i] for p in points)/4 for i in (0, 1)],
            'velocity_xy_mps': [float(velocity.x), float(velocity.y)],
            'heading_deg': float(transform.rotation.yaw)}


def _check_config(config):
    selected = config['selected_case_id']
    if (config.get('law_id') != 'LVMC-11-12-020' or config.get('cell_id') != 'C111644'
            or config.get('actor') != 'motor_vehicle_driver'
            or config.get('rate_hz') != 20 or config.get('frames') != 160
            or config.get('duration_s') != 8 or selected not in config['supported_case_ids']):
        raise ValueError('Exact turn-course Native configuration changed')
    suffix = selected.rsplit('__', 1)[-1]
    form, response = suffix.rsplit('_', 1)
    if form not in ('marker', 'button', 'other_indication') or response not in ('follow', 'depart'):
        raise ValueError('Unknown exact turn-course variant')
    if [(name, *spec[2]) for name, spec in CAMERAS.items()] != [
            (camera['name'], camera['width'], camera['height']) for camera in config['cameras']]:
        raise ValueError('Four source camera profile changed')
    return form, response


def _native_source_args(indication_source, source_sha256, environ=None):
    """Accept the operator's reviewed source through the runtime capture handoff."""
    env = os.environ if environ is None else environ
    path = indication_source or env.get('TURN_INDICATION_SOURCE')
    checksum = source_sha256 or env.get('TURN_INDICATION_SHA256')
    if not path or not checksum or len(checksum) != 64 or any(c not in '0123456789abcdef' for c in checksum):
        raise ValueError('Native run requires TURN_INDICATION_SOURCE and TURN_INDICATION_SHA256')
    return path, checksum


def _check_attempt_dir(output):
    output = Path(output)
    if not output.is_dir() or not (output / 'construction.json').is_file():
        raise ValueError('Native run requires materialized construction directory')
    allowed = {'config.json', 'construction.json', 'candidate-selection.json',
               'runner.py', 'turn_marking.py', 'indication_native.py', 'tests'}
    if any(path.name not in allowed for path in output.iterdir()):
        raise ValueError('Native attempt already has acquisition or derived output')


def run(config, source_path, source_sha256, output, host='127.0.0.1', port=2000):
    # CARLA and pipeline capture are loaded only at the authorized Native run.
    _check_attempt_dir(output)
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import seal_capture
    form, response = _check_config(config)
    source = load_source(source_path, source_sha256, form)
    if config["selected_case_id"].endswith("__placement_075m__marker_follow"):
        if config.get("indication_placement_setpoint_m") != 0.75 or source.get("placement_shift_m") != 0.75 or not source.get("parent_source_sha256"):
            raise ValueError("Exact indication placement source or setpoint changed")
    route = native_route_plan(source, response)
    output = Path(output)
    client = carla.Client(host, int(port))
    client.set_timeout(30.)
    world = client.get_world()
    if world.get_map().name != source['map_name']:
        raise ValueError('Loaded Native map differs from source')
    start = route['target_route_xy_m'][0]
    waypoint = world.get_map().get_waypoint(carla.Location(x=start[0], y=start[1], z=.5),
                                            project_to_road=False,
                                            lane_type=carla.LaneType.Driving)
    if waypoint is None or hypot(waypoint.transform.location.x-start[0],
                                 waypoint.transform.location.y-start[1]) > 1.5:
        raise ValueError('Sourced turn approach lacks matching Native lane')
    old_settings = world.get_settings()
    ego = None
    indications = []
    cameras = None
    pipeline = None
    frames = []
    complete = False
    errors = []
    restored = False
    try:
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        world.apply_settings(settings)
        placement = place_indications(world, source_path, source_sha256, form,
            lambda x,y,z,yaw: carla.Transform(carla.Location(x=x,y=y,z=z),
                                               carla.Rotation(yaw=yaw)))
        indications = placement['actors']
        blueprint = world.get_blueprint_library().find('vehicle.tesla.model3')
        spawn = waypoint.transform
        spawn.location.z += .5
        ego = world.try_spawn_actor(blueprint, spawn)
        if ego is None:
            raise ValueError('Native turn subject spawn failed')
        (output / 'turn_indication_original.json').write_bytes(Path(source_path).read_bytes())
        (output / 'turn_indication_readback_original.json').write_text(json.dumps({
            'source_sha256': source_sha256,
            'physical_xy_m': placement['physical_xy_m'],
            'reference_xy_m': source['indicated_course_xy_m'][1],
            'reference_kind': 'unchanged_sourced_indicated_course_point_1',
        }, indent=2) + '\n')
        (output / 'turn_route_plan.json').write_text(json.dumps(route, indent=2) + '\n')
        cameras = OriginalCameras(world, carla, ego, output)
        pipeline = PipelineCapture(client, ego, output, config['selected_case_id'],
            required_observations=('kin.path_length', 'rel.occupies'))
        target_index = 1
        for _ in range(config['frames']):
            transform = ego.get_transform()
            velocity = ego.get_velocity()
            position = (float(transform.location.x), float(transform.location.y))
            target = route['target_route_xy_m'][target_index]
            if hypot(position[0]-target[0], position[1]-target[1]) < 2.8 and target_index < len(route['target_route_xy_m'])-1:
                target_index += 1
                target = route['target_route_xy_m'][target_index]
            forward = transform.get_forward_vector()
            action = control_to_target(position, (float(forward.x), float(forward.y)),
                (float(velocity.x), float(velocity.y)), target, 3.0)
            ego.apply_control(carla.VehicleControl(**action))
            frame = world.tick()
            cameras.wait(frame)
            snapshot = world.get_snapshot()
            if snapshot.frame != frame:
                raise ValueError('Original Native frame identity changed')
            time_s = float(snapshot.timestamp.elapsed_seconds)
            body = _body(ego)
            captured = pipeline.capture(frame, time_s)
            if captured['frame'] != frame or captured['time_s'] != time_s:
                raise ValueError('Original Native graph/body join changed')
            frames.append({'frame': frame, 'time_s': time_s, 'subject': body})
        complete = True
    except BaseException as error:
        errors.append(str(error))
        raise
    finally:
        if pipeline is not None:
            pipeline.close(confirmed=complete)
        if cameras is not None:
            cameras.close()
        if ego is not None:
            ego.destroy()
        for actor in reversed(indications):
            actor.destroy()
        world.apply_settings(old_settings)
        current = world.get_settings()
        restored = (current.synchronous_mode == old_settings.synchronous_mode
                    and current.fixed_delta_seconds == old_settings.fixed_delta_seconds)
        if not restored:
            raise ValueError('Native world settings restoration failed')
    if not complete or any([row['frame'] for row in cameras.rows[name]] !=
                           [row['frame'] for row in frames] for name in CAMERAS):
        raise ValueError('Original camera/body frame join incomplete')
    _rows(output / 'turn_body_original.jsonl', frames)
    _rows(output / 'video_frames.jsonl', [
        {'video_frame': index, 'carla_frame': row['frame'],
         'native_frame': row['frame'], 'time_s': row['time_s']}
        for index, row in enumerate(frames)])
    for name in CAMERAS:
        _rows(output / (name + '-frames.jsonl'), [
            {'video_frame': index, 'native_frame': row['frame'],
             'time_s': row['time_s']} for index, row in enumerate(cameras.rows[name])])
    originals = ['turn_indication_original.json',
                 'turn_indication_readback_original.json', 'turn_route_plan.json',
                 'turn_body_original.jsonl', 'trace.jsonl', 'video_frames.jsonl']
    originals += [name + '.mkv' for name in CAMERAS]
    originals += [name + '-frames.jsonl' for name in CAMERAS]
    (output / 'turn_source_receipt.json').write_text(json.dumps({
        'case_id': config['selected_case_id'], 'source_kind': 'original_native_capture',
        'source_sha256': {name: _sha(output / name) for name in originals},
        'authority_claim_verified_by_worker': False,
        'visible_pixels_verified': False, 'physical_outcome_verified': False}, indent=2) + '\n')
    (output / 'acquisition-provenance.json').write_text(json.dumps({
        'provenance_kind': 'native', 'diagnostic_fixture': False,
        'original_frames': len(frames)}) + '\n')
    seal_capture(output, frames=len(frames), restoration={'restored': restored},
                 errors=errors, encoder_exit_codes={name: 0 for name in CAMERAS},
                 context={'intersection_id': source['intersection_id'],
                          'indication_source_sha256': source_sha256})
    return {'frames': len(frames), 'cameras': list(CAMERAS),
            'physical_outcome_verified': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--indication-source')
    parser.add_argument('--source-sha256')
    parser.add_argument('--output-dir')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args()
    config = json.loads(Path(__file__).with_name('config.json').read_text())
    form, response = _check_config(config)
    if args.check:
        print(json.dumps({'case_id': config['selected_case_id'],
                          'form': form, 'response': response,
                          'native_launched': False, 'physical_verified': False}))
        return
    if not args.output_dir:
        raise ValueError('Native run requires materialized output directory')
    source_path, source_sha256 = _native_source_args(args.indication_source, args.source_sha256)
    print(json.dumps(run(config, source_path, source_sha256,
                         args.output_dir, args.host, args.port)))


if __name__ == '__main__':
    main()
