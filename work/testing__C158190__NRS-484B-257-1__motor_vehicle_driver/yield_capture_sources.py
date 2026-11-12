"""Retain same-frame Native sight rays for the nearest-view yield cases.

This module does not decide legal visibility or an immediate hazard. The target
is an authored point on the through-highway junction lane, independent of
whether a through vehicle was staged. The ray and actor-body checks are collision
mesh estimates for later source-camera review.
"""

import json
import math
from pathlib import Path

from yield_site import APPROACH, JUNCTION

TARGET_XY = (1.8, 0.0)
INTERSECTION_ENTRY_X = -8.0


def _xyz(point):
    return [float(point.x), float(point.y), float(point.z)]


def _finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def observe_sight(world, ego, through, frame, time_s, *, location_factory=None,
                  visible_relation=None):
    """Observe a single already-ticked frame; never advance the world."""
    if location_factory is None:
        import carla
        location_factory = carla.Location
    if type(frame) is not int or not _finite(time_s) or world.get_snapshot().frame != frame:
        raise ValueError('Sight observation needs the current Native frame')
    ego_transform = ego.get_transform()
    ego_point = ego_transform.location
    waypoint = world.get_map().get_waypoint(ego_point, project_to_road=False)
    if waypoint is None or (waypoint.road_id, waypoint.lane_id) != (APPROACH, -1):
        raise ValueError('Ego sight sample is outside the sign-governed approach')
    target = location_factory(x=TARGET_XY[0], y=TARGET_XY[1], z=1.5)
    target_waypoint = world.get_map().get_waypoint(target, project_to_road=False)
    if (target_waypoint is None or target_waypoint.road_id != 158195
            or target_waypoint.lane_id != -1 or target_waypoint.junction_id != JUNCTION):
        raise ValueError('Sight target is not the through-highway junction lane')
    distance = INTERSECTION_ENTRY_X - ego_point.x
    if not _finite(distance) or distance < 0:
        raise ValueError('Ego has passed the approach sight interval')
    eye = ego_transform.transform(location_factory(x=0.0, y=0.0, z=1.5))
    blockers = []
    for hit in world.cast_ray(eye, target):
        if ego.bounding_box.contains(hit.location, ego_transform):
            continue
        if hit.location.distance(eye) < .05 or hit.location.distance(target) < .02:
            continue
        blockers.append({'label': str(hit.label), 'location_m': _xyz(hit.location)})
    visible_ids = []
    if through is not None:
        if visible_relation is None:
            from runtime.python.original_observations import visible_relation
        relation = visible_relation(world, ego, through)
        if relation.get('a') != ego.id or relation.get('b') != through.id:
            raise ValueError('Through-vehicle relation has different actor IDs')
        if relation.get('visible') is True:
            visible_ids.append(through.id)
    if world.get_snapshot().frame != frame:
        raise ValueError('World advanced during sight observation')
    ray = {'frame': frame, 'time_s': float(time_s),
           'distance_to_intersection_m': float(distance),
           'observer_m': _xyz(eye), 'target_m': _xyz(target),
           'target_road_id': 158195, 'target_lane_id': -1,
           'method': 'native_collision_ray_to_authored_through_lane_point',
           'blockers': blockers, 'clear': not blockers,
           'visible_through_vehicle_ids': visible_ids}
    sample = {'frame': frame, 'distance_to_intersection_m': float(distance),
              'through_highway_visible': not blockers,
              'visible_through_vehicle_ids': visible_ids,
              'ray_source': 'visibility_rays.jsonl'}
    return ray, sample


class SightWriter:
    """Append ray rows and materialize their exactly joined sample index."""

    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        if (self.root / 'visibility_rays.jsonl').exists():
            raise ValueError('Sight source already exists; use a fresh capture directory')
        self.rays = []
        self.samples = []

    def add(self, ray, sample):
        frame = ray.get('frame')
        if type(frame) is not int or sample.get('frame') != frame:
            raise ValueError('Sight sample/frame mismatch')
        if self.rays and frame <= self.rays[-1]['frame']:
            raise ValueError('Sight frames must increase')
        self.rays.append(ray)
        self.samples.append(sample)
        with (self.root / 'visibility_rays.jsonl').open('a') as handle:
            handle.write(json.dumps(ray, sort_keys=True) + '\n')

    def close(self):
        (self.root / 'visibility_samples.json').write_text(
            json.dumps(self.samples, indent=2, sort_keys=True) + '\n')


class ApproachSourceWriter:
    """Join original approach telemetry to completed four-camera frame indices."""

    def __init__(self, root):
        self.sight = SightWriter(root)
        self.root = Path(root)
        self.frame_count = 0
        self.last_video_identity = None
        for name in ('approach_history.jsonl', 'video_frames.jsonl'):
            if (self.root / name).exists():
                raise ValueError('Approach source already exists; use a fresh capture directory')

    def add(self, world, ego, through, frame, time_s, video_frame, *,
            location_factory=None, visible_relation=None):
        """Call only after all four source cameras have returned this frame."""
        if type(video_frame) is not int or video_frame != self.frame_count:
            raise ValueError('Camera frame index must match original tick sequence')
        ray, sample = observe_sight(world, ego, through, frame, time_s,
                                    location_factory=location_factory,
                                    visible_relation=visible_relation)
        point = ego.get_transform().location
        waypoint = world.get_map().get_waypoint(point, project_to_road=False)
        velocity = ego.get_velocity()
        speed = math.sqrt(velocity.x**2 + velocity.y**2 + velocity.z**2)
        if not _finite(speed):
            raise ValueError('Missing finite original ego speed')
        history = {'frame': frame, 'time_s': float(time_s),
                   'road_id': waypoint.road_id, 'lane_id': waypoint.lane_id,
                   'ego_speed_mps': speed,
                   'distance_to_intersection_m': ray['distance_to_intersection_m']}
        frame_row = {'video_frame': video_frame, 'carla_frame': frame,
                     'time_s': float(time_s)}
        self.sight.add(ray, sample)
        for name, row in (('approach_history.jsonl', history),
                          ('video_frames.jsonl', frame_row)):
            with (self.root / name).open('a') as handle:
                handle.write(json.dumps(row, sort_keys=True) + '\n')
        self.last_video_identity = (frame, float(time_s))
        self.frame_count += 1

    def add_nonapproach_frame(self, frame, time_s, video_frame):
        if (type(frame) is not int or type(video_frame) is not int
                or video_frame != self.frame_count or not _finite(time_s)):
            raise ValueError('Invalid later video frame join')
        if self.last_video_identity and (frame <= self.last_video_identity[0]
                                         or time_s <= self.last_video_identity[1]):
            raise ValueError('Nonmonotone later video frame')
        with (self.root / 'video_frames.jsonl').open('a') as handle:
            handle.write(json.dumps({'video_frame': video_frame, 'carla_frame': frame,
                                     'time_s': float(time_s)}, sort_keys=True) + '\n')
        self.last_video_identity = (frame, float(time_s))
        self.frame_count += 1

    def close(self):
        self.sight.close()
