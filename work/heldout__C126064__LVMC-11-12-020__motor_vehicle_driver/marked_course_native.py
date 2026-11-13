"""CARLA-lazy placement of sourced turn-course indicators in a junction.

The source record documents claimed authorization. Placement and the Native
readback establish only physical construction, never municipal authority.
"""

from hashlib import sha256
import json
from math import atan2, hypot, isfinite
from pathlib import Path
from threading import Condition
from time import monotonic


CAMERAS = {
    'overview': ((-8, 0, 8), (-12, 0, 0), (1920, 1080), 95),
    'approach': ((1.2, 0, 2), (0, 0, 0), (1280, 720), 90),
    'reference_corner': ((-3, 2.5, 2.6), (-7, 0, 0), (1280, 720), 100),
    'driver_reference': ((0.6, -0.35, 1.6), (0, 0, 0), (1280, 720), 85),
}


def _xy(location):
    return [float(location.x), float(location.y)]


def place_markers(world, source_path, expected_sha256, make_transform):
    """Spawn and read back every indicated marker; caller owns returned actors.

    `make_transform(x, y, z, yaw)` is supplied by the Native runner so this
    module can be imported and tested without importing CARLA.
    """
    source_path = Path(source_path)
    raw = source_path.read_bytes()
    if sha256(raw).hexdigest() != expected_sha256:
        raise ValueError('Authorized marker source hash changed')
    record = json.loads(raw)
    if (not record.get('authority_document') or not record.get('intersection_id')
            or record.get('median_opening_with_intersecting_road') is not True):
        raise ValueError('Marker authority or intersection identity missing')
    markers = record.get('markers')
    if not isinstance(markers, list) or not markers:
        raise ValueError('No physical turn-course markers specified')
    library = world.get_blueprint_library()
    road_map = world.get_map()
    actors = []
    try:
        for item in markers:
            if not all(k in item for k in ('x', 'y', 'z', 'yaw', 'blueprint_id')):
                raise ValueError('Marker placement incomplete')
            wp = road_map.get_waypoint(make_transform(item['x'], item['y'], item['z'], item['yaw']).location)
            if wp is None or not wp.is_junction:
                raise ValueError('Marker does not occupy a Native junction')
            blueprint = library.find(item['blueprint_id'])
            transform = make_transform(item['x'], item['y'], item['z'], item['yaw'])
            actor = world.try_spawn_actor(blueprint, transform)
            if actor is None:
                raise ValueError('Native marker spawn failed')
            actors.append(actor)
            actual = _xy(actor.get_transform().location)
            if max(abs(actual[i] - float(item[k])) for i, k in enumerate(('x', 'y'))) > 0.05:
                raise ValueError('Native marker location readback differs')
        return {'actors': actors, 'source_sha256': expected_sha256,
                'intersection_id': record['intersection_id'],
                'physical_marker_xy_m': [_xy(a.get_transform().location) for a in actors]}
    except Exception:
        for actor in reversed(actors):
            actor.destroy()
        raise


def place_course_indications(world, source_path, expected_sha256, form, make_transform):
    """Place sourced buttons or other indications with map and pose readback.

    The caller retains ownership of the returned actors. A source authorization
    claim and successful spawn do not verify municipal authorization or pixels.
    """
    if form not in ('button', 'other_indication'):
        raise ValueError('Unsupported non-marker indication form')
    raw = Path(source_path).read_bytes()
    if sha256(raw).hexdigest() != expected_sha256:
        raise ValueError('Indication source hash changed')
    record = json.loads(raw)
    if (not record.get('authority_document') or not record.get('intersection_id')
            or record.get('median_opening_with_intersecting_road') is not True
            or record.get('indication_form') != form or not record.get('map_name')):
        raise ValueError('Indication authority, intersection, form or map missing')
    polygon = record.get('intersection_polygon_xy_m')
    if (not isinstance(polygon, list) or len(polygon) < 3
            or any(not isinstance(point, list) or len(point) != 2
                   or any(isinstance(v, bool) or not isinstance(v, (int, float))
                          or not isfinite(v) for v in point) for point in polygon)):
        raise ValueError('Sourced indication intersection polygon missing')
    indications = record.get('indications')
    allowed = record.get('form_blueprints', {}).get(form)
    if not isinstance(indications, list) or not indications or not isinstance(allowed, list) or not allowed:
        raise ValueError('Physical indication form or blueprint inventory missing')
    road_map = world.get_map()
    if road_map.name != record['map_name']:
        raise ValueError('Native indication map differs from source')
    actors = []
    try:
        for item in indications:
            if item.get('form') != form or item.get('blueprint_id') not in allowed:
                raise ValueError('Physical indication form or blueprint differs from source')
            if any(key not in item or isinstance(item[key], bool)
                   or not isinstance(item[key], (int, float)) or not isfinite(item[key])
                   for key in ('x', 'y', 'z', 'yaw')):
                raise ValueError('Nonfinite physical indication placement')
            if not _inside([item['x'], item['y']], polygon):
                raise ValueError('Physical indication outside sourced intersection')
            transform = make_transform(*(item[key] for key in ('x', 'y', 'z', 'yaw')))
            waypoint = road_map.get_waypoint(transform.location)
            if waypoint is None or not waypoint.is_junction:
                raise ValueError('Physical indication does not occupy a Native junction')
            actor = world.try_spawn_actor(world.get_blueprint_library().find(item['blueprint_id']), transform)
            if actor is None:
                raise ValueError('Native indication spawn failed')
            actors.append(actor)
            actual = actor.get_transform().location
            if max(abs(float(getattr(actual, axis)) - float(item[axis]))
                   for axis in ('x', 'y')) > .05:
                raise ValueError('Native indication position readback differs')
        return {'actors': actors, 'intersection_id': record['intersection_id'],
                'indication_form': form, 'source_sha256': expected_sha256,
                'physical_xy_m': [_xy(actor.get_transform().location) for actor in actors],
                'authorization_verified_by_worker': False,
                'visible_pixels_verified': False}
    except BaseException:
        for actor in reversed(actors):
            actor.destroy()
        raise


def _inside(point, polygon):
    x, y = point
    result = False
    for a, b in zip(polygon, polygon[1:] + polygon[:1]):
        if (a[1] > y) != (b[1] > y):
            crossing = a[0] + (y-a[1])*(b[0]-a[0])/(b[1]-a[1])
            if x < crossing:
                result = not result
    return result


def turn_targets(world, source_path, expected_sha256, variant, make_transform):
    """Map-check a sourced turn course before a Native feedback controller uses it.

    The returned points are construction targets. The eventual recorded body
    footprints, rather than the requested targets, determine the actual course.
    """
    if variant not in ('indicated_course', 'divergent_course'):
        raise ValueError('Unknown marked turn variant')
    raw = Path(source_path).read_bytes()
    if sha256(raw).hexdigest() != expected_sha256:
        raise ValueError('Turn-course source hash changed')
    record = json.loads(raw)
    if (not record.get('authority_document') or not record.get('intersection_id')
            or record.get('median_opening_with_intersecting_road') is not True):
        raise ValueError('Turn-course source identity incomplete')
    polygon = record.get('intersection_polygon_xy_m')
    indicated = record.get('indicated_course_xy_m')
    targets = record.get(variant + '_xy_m')
    if not isinstance(polygon, list) or len(polygon) < 3:
        raise ValueError('Sourced intersection polygon missing')
    for route in (indicated, targets):
        if (not isinstance(route, list) or len(route) < 3
                or any(not isinstance(p, list) or len(p) != 2
                       or not all(isinstance(v, (int, float)) and isfinite(v) for v in p)
                       for p in route)
                or any(hypot(b[0]-a[0], b[1]-a[1]) < .2
                       for a, b in zip(route, route[1:]))):
            raise ValueError('Turn course lacks finite distinct targets')
        if (_inside(route[0], polygon) or _inside(route[-1], polygon)
                or not any(_inside(p, polygon) for p in route[1:-1])):
            raise ValueError('Turn course does not cross sourced intersection')
    if targets[0] != indicated[0] or targets[-1] != indicated[-1]:
        raise ValueError('Compared turn must retain approach and exit')
    if variant == 'divergent_course' and targets == indicated:
        raise ValueError('Divergent turn has no different target')
    road_map = world.get_map()
    for point in targets[1:-1]:
        if not _inside(point, polygon):
            continue
        wp = road_map.get_waypoint(make_transform(point[0], point[1], 0., 0.).location)
        if wp is None or not wp.is_junction:
            raise ValueError('Native map does not identify turn target as junction')
    return {'intersection_id': record['intersection_id'], 'variant': variant,
            'targets_xy_m': targets, 'source_sha256': expected_sha256,
            'actual_turn_observed': False}


def control_step(position_xy, heading_xy, velocity_xy, target_xy, *, target_speed_mps=4.):
    """Bounded feedback for one authored target, never a motion receipt."""
    values = (*position_xy, *heading_xy, *velocity_xy, *target_xy, target_speed_mps)
    if not all(isfinite(v) for v in values):
        raise ValueError('Nonfinite Native turn feedback')
    dx, dy = target_xy[0]-position_xy[0], target_xy[1]-position_xy[1]
    length = hypot(dx, dy)
    heading_length = hypot(*heading_xy)
    if length < .2 or heading_length < .1 or not 0 < target_speed_mps <= 10:
        raise ValueError('Invalid Native turn target or engineering speed')
    hx, hy = heading_xy[0]/heading_length, heading_xy[1]/heading_length
    error = atan2(hx*dy-hy*dx, hx*dx+hy*dy)
    speed = hypot(*velocity_xy)
    return {'steer': max(-.5, min(.5, .8*error)),
            'throttle': max(0., min(.4, .22*(target_speed_mps-speed))),
            'brake': max(0., min(.4, .16*(speed-target_speed_mps)))}


class FourCameraCapture:
    """Native camera lifecycle with frame-joined original-image callbacks.

    `on_frame(name, image)` must retain the raw source image for every callback;
    it is supplied by the eventual recorder and is not inferred from a fixture.
    """

    def __init__(self, world, carla_module, ego, on_frame):
        self.condition = Condition()
        self.frames = {name: set() for name in CAMERAS}
        self.errors = []
        self.sensors = []
        self.closed = False
        try:
            for name, (location, rotation, size, fov) in CAMERAS.items():
                blueprint = world.get_blueprint_library().find('sensor.camera.rgb')
                for key, value in (('image_size_x', size[0]), ('image_size_y', size[1]),
                                   ('fov', fov), ('sensor_tick', .05)):
                    blueprint.set_attribute(key, str(value))
                transform = carla_module.Transform(carla_module.Location(*location),
                                                   carla_module.Rotation(*rotation))
                sensor = world.spawn_actor(blueprint, transform, attach_to=ego)
                self.sensors.append(sensor)
                sensor.listen(lambda image, source=name: self._receive(source, image, on_frame))
        except BaseException:
            self.close()
            raise

    def _receive(self, name, image, on_frame):
        with self.condition:
            if self.closed:
                return
            try:
                if image.frame in self.frames[name]:
                    raise ValueError('Duplicate original turn-camera frame')
                if (image.width, image.height) != CAMERAS[name][2]:
                    raise ValueError('Original turn-camera dimensions changed')
                on_frame(name, image)
                self.frames[name].add(image.frame)
            except BaseException as error:
                self.errors.append(error)
            finally:
                self.condition.notify_all()

    def wait_for_frame(self, frame, *, timeout_s=10):
        deadline = monotonic() + timeout_s
        with self.condition:
            while True:
                if self.errors:
                    raise ValueError('Original turn-camera callback failed') from self.errors[0]
                if all(frame in observed for observed in self.frames.values()):
                    return
                remaining = deadline-monotonic()
                if remaining <= 0:
                    raise ValueError('Missing original turn-camera frame')
                self.condition.wait(remaining)

    def verify(self, frames):
        expected = set(frames)
        if not expected or any(observed != expected for observed in self.frames.values()):
            raise ValueError('Missing or extra original turn-camera frames')
        return {name: len(expected) for name in CAMERAS}

    def close(self):
        if not self.closed:
            self.closed = True
            for sensor in reversed(self.sensors):
                sensor.stop()
                sensor.destroy()


def drive_turn(world, carla_module, ego, plan, cameras, record_sample,
               *, max_ticks_per_target=120, capture_frames=160):
    """Drive sourced targets and retain original frame/body observations.

    The recorder receives raw Native frame identity, time and body vertices;
    it must persist them with the four camera sources for saved processing.
    """
    settings = world.get_settings()
    if (not settings.synchronous_mode
            or abs(float(settings.fixed_delta_seconds)-.05) > 1e-6):
        raise ValueError('Original turn capture requires synchronous 20 Hz Native world')
    targets = plan['targets_xy_m']
    if len(targets) < 3 or plan.get('actual_turn_observed') is not False:
        raise ValueError('Unreviewed marked turn plan')
    if type(max_ticks_per_target) is not int or max_ticks_per_target < 1:
        raise ValueError('Invalid turn tick budget')
    if type(capture_frames) is not int or capture_frames < 1:
        raise ValueError('Invalid fixed turn capture duration')
    frames = []

    def record_tick():
        if len(frames) >= capture_frames:
            raise ValueError('Marked turn exceeded fixed capture duration')
        frame = world.tick()
        cameras.wait_for_frame(frame)
        snapshot = world.get_snapshot()
        if snapshot.frame != frame:
            raise ValueError('Original Native snapshot frame mismatch')
        body_transform = ego.get_transform()
        vertices = ego.bounding_box.get_world_vertices(body_transform)
        if len(vertices) != 8:
            raise ValueError('Original Native body vertices incomplete')
        corners = []
        for vertex in vertices:
            point = [float(vertex.x), float(vertex.y)]
            if not any(hypot(point[0]-old[0], point[1]-old[1]) < 1e-4
                       for old in corners):
                corners.append(point)
        if len(corners) != 4:
            raise ValueError('Original Native footprint corners incomplete')
        record_sample({'frame': frame, 'time_s': float(snapshot.timestamp.elapsed_seconds),
                       'actor_id': ego.id, 'corners_xy_m': corners})
        frames.append(frame)
    for target in targets[1:]:
        reached = False
        for _ in range(max_ticks_per_target):
            transform = ego.get_transform()
            loc = transform.location
            position = (float(loc.x), float(loc.y))
            if hypot(target[0]-position[0], target[1]-position[1]) < .8:
                reached = True
                break
            forward = transform.get_forward_vector()
            velocity = ego.get_velocity()
            controls = control_step(position, (float(forward.x), float(forward.y)),
                                    (float(velocity.x), float(velocity.y)), target)
            ego.apply_control(carla_module.VehicleControl(**controls))
            record_tick()
        if not reached:
            loc = ego.get_transform().location
            reached = hypot(target[0]-float(loc.x), target[1]-float(loc.y)) < .8
        if not reached:
            ego.apply_control(carla_module.VehicleControl(throttle=0., steer=0., brake=1.))
            raise ValueError('Ego did not reach marked turn target within tick budget')
    ego.apply_control(carla_module.VehicleControl(throttle=0., steer=0., brake=1.))
    while len(frames) < capture_frames:
        record_tick()
    cameras.verify(frames)
    return {'frames': frames, 'targets_reached': len(targets)-1,
            'actual_turn_observed': bool(frames), 'capture_frames': capture_frames}


def execute_marked_turn(world, carla_module, ego, case_id, source_path, source_sha256,
                        variant, make_transform, recorder, *,
                        camera_factory=FourCameraCapture, drive=drive_turn):
    """Join physical markers, selected targets, cameras and original recorder.

    The caller supplies a reviewed authority/site source and an already owned ego.
    This routine owns only its spawned markers and cameras. A source-shaped CPU
    call proves orchestration; it cannot establish municipal authorization.
    """
    markers = None
    cameras = None
    try:
        markers = place_markers(world, source_path, source_sha256, make_transform)
        plan = turn_targets(world, source_path, source_sha256, variant, make_transform)
        if plan['intersection_id'] != markers['intersection_id']:
            raise ValueError('Marker and turn plan intersection identities differ')
        recorder.record_scene(case_id, source_path, source_sha256, markers, ego.id)
        cameras = camera_factory(world, carla_module, ego, recorder.on_frame)
        motion = drive(world, carla_module, ego, plan, cameras, recorder.record_sample)
        sources = recorder.seal()
        if sources['frames'] != len(motion['frames']):
            raise ValueError('Original source count differs from Native turn')
        return {'source_sha256': source_sha256,
                'intersection_id': plan['intersection_id'],
                'variant': variant,
                'physical_marker_xy_m': markers['physical_marker_xy_m'],
                'motion': motion, 'sources': sources,
                'authority_verified': False,
                'legal_conformance_assessed': False}
    finally:
        if cameras is not None:
            cameras.close()
        recorder.close()
        if markers is not None:
            for actor in reversed(markers['actors']):
                actor.destroy()
