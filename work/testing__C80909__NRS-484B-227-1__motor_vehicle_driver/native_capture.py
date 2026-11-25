"""Retain original Native vehicle bodies and four synchronized camera sources.

The caller supplies a reviewed site and an image writer for each camera. This
module does not infer public authority or physical success from a route plan.
"""

from contextlib import contextmanager
import json
import math
from queue import Empty, Queue

from shapely.geometry import MultiPoint, Polygon

CAMERAS = {'overview': (1920, 1080), 'approach': (1280, 720),
           'reference_corner': (1280, 720), 'driver_reference': (1280, 720)}


def _finite(value, label):
    if type(value) not in (float, int) or not math.isfinite(value):
        raise ValueError('Finite original Native ' + label + ' required')
    return float(value)


def _body(actor, label):
    vertices = actor.bounding_box.get_world_vertices(actor.get_transform())
    if len(vertices) < 4:
        raise ValueError('Complete original Native ' + label + ' body required')
    points = [[_finite(v.x, label + ' body x'), _finite(v.y, label + ' body y')]
              for v in vertices]
    if MultiPoint(points).convex_hull.area <= 0:
        raise ValueError('Degenerate original Native ' + label + ' body')
    return points


def _validate_context(context):
    keys = ('native_map_id', 'divided_highway_source', 'roadway_boundaries_source',
            'opening_geometry_source', 'barrier_actors_source', 'other_vehicle_source')
    if any(not context.get(key) for key in keys):
        raise ValueError('Reviewed divided-road source context required')
    for key in ('right_hand_roadway_xy_m', 'destination_roadway_xy_m',
                'dividing_space_xy_m', 'opening_xy_m'):
        shape = Polygon(context[key])
        if not shape.is_valid or shape.area <= 0:
            raise ValueError('Invalid reviewed ' + key)
    if not Polygon(context['dividing_space_xy_m']).covers(Polygon(context['opening_xy_m'])):
        raise ValueError('Opening outside reviewed divider')


@contextmanager
def original_cameras(world, ego, transforms, timeout_s=10):
    """Create four real RGB sensors and yield exact-tick image readers."""
    if set(transforms) != set(CAMERAS) or timeout_s <= 0:
        raise ValueError('Four camera poses and positive timeout required')
    queues = {name: Queue() for name in CAMERAS}
    sensors = []
    try:
        for name, (width, height) in CAMERAS.items():
            blueprint = world.get_blueprint_library().find('sensor.camera.rgb')
            if blueprint is None:
                raise ValueError('Native RGB camera blueprint missing')
            for key, value in (('image_size_x', width), ('image_size_y', height),
                               ('fov', 90), ('sensor_tick', 0.05)):
                blueprint.set_attribute(key, str(value))
            kwargs = {'attach_to': ego} if name == 'driver_reference' else {}
            sensor = world.spawn_actor(blueprint, transforms[name], **kwargs)
            if sensor is None:
                raise ValueError('Native camera spawn failed: ' + name)
            sensors.append(sensor)
            sensor.listen(lambda image, source=name: queues[source].put(image))

        def read(frame):
            images = {}
            for name in CAMERAS:
                for _ in range(8):
                    try:
                        image = queues[name].get(timeout=timeout_s)
                    except Empty as error:
                        raise ValueError('Missing original camera frame: ' + name) from error
                    if image.frame == frame:
                        if (image.width, image.height) != CAMERAS[name]:
                            raise ValueError('Original camera dimensions differ: ' + name)
                        images[name] = image
                        break
                    if image.frame > frame:
                        raise ValueError('Original camera skipped Native frame: ' + name)
                else:
                    raise ValueError('Original camera backlog exceeded: ' + name)
            return images

        yield read
    finally:
        for sensor in reversed(sensors):
            sensor.stop()
            sensor.destroy()


class OriginalTickRecorder:
    """Write frame-bound measurement sources after all four images are retained."""

    def __init__(self, context, movement_stream, frame_stream, camera_writers):
        _validate_context(context)
        if set(camera_writers) != set(CAMERAS):
            raise ValueError('All four original camera writers required')
        self.context = context
        self.movement_stream = movement_stream
        self.frame_stream = frame_stream
        self.camera_writers = camera_writers
        self.index = 0
        self.last_frame = -1
        self.last_time = -math.inf

    def record(self, snapshot, ego, other, images):
        frame = snapshot.frame
        time_s = _finite(snapshot.timestamp.elapsed_seconds, 'time')
        if type(frame) is not int or frame <= self.last_frame or time_s <= self.last_time:
            raise ValueError('Nonmonotone original Native tick')
        if ego.id == other.id:
            raise ValueError('Distinct original Native participants required')
        if set(images) != set(CAMERAS) or any(
                image.frame != frame or (image.width, image.height) != CAMERAS[name]
                for name, image in images.items()):
            raise ValueError('Four original camera frames must join Native tick')
        pose = ego.get_transform()
        yaw = math.radians(_finite(pose.rotation.yaw, 'ego yaw'))
        row = {'frame': frame, 'time_s': time_s,
               'ego_actor_id': ego.id, 'other_actor_id': other.id,
               'ego_body_vertices_xy_m': _body(ego, 'ego'),
               'other_body_vertices_xy_m': _body(other, 'other'),
               'ego_forward_xy': [math.cos(yaw), math.sin(yaw)]}
        for name, image in images.items():
            self.camera_writers[name](image)
        self.movement_stream.write(json.dumps(row, allow_nan=False) + '\n')
        if hasattr(self.frame_stream, 'append'):
            mapped = self.frame_stream.append(frame, time_s)
            if mapped['video_frame'] != self.index or mapped['carla_frame'] != frame:
                raise ValueError('Canonical original frame map differs')
        else:
            self.frame_stream.write(json.dumps({'video_frame': self.index,
                                                'carla_frame': frame,
                                                'native_frame': frame,
                                                'time_s': time_s}, allow_nan=False) + '\n')
        self.index += 1
        self.last_frame, self.last_time = frame, time_s
        return row
