"""Live CARLA bridge for original center-turn-lane acquisition.

The caller owns reviewed spawn, four sensors, and world restoration. This bridge
records post-tick actor/map observations and never substitutes target stations
for traveled distance or a statutory finding.
"""
from __future__ import annotations

import math
import hashlib
import json
from pathlib import Path
from queue import Empty, Queue

from center_lane_site import validate_site
from native_capture import VIEWS, capture_original, sensor_frame_reader
from turn_merge_controller import TurnMergeController


class CarlaFrameReader:
    def __init__(self, *, world, ego, receiving_vehicle, cameras, site,
                 route_xy_m, control_factory, timeout_seconds=5.0):
        self.ids = validate_site(site)
        if set(cameras) != set(VIEWS):
            raise ValueError('four original camera sensors required')
        settings = world.get_settings()
        if settings.synchronous_mode is not True or abs(settings.fixed_delta_seconds - .05) > 1e-8:
            raise ValueError('Native world requires synchronous 20 Hz settings')
        self.world, self.ego, self.receiving_vehicle = world, ego, receiving_vehicle
        self.cameras = cameras
        self.control_factory = control_factory
        self.timeout_seconds = timeout_seconds
        self.controller = TurnMergeController(route_xy_m)
        self.queues = {view: Queue(maxsize=4) for view in VIEWS}
        self.listening = []
        self.first_time = None
        self.prior_frame = None
        self.prior_lane = None
        self.turn_seen = False
        self.merge_seen = False
        try:
            for view, sensor in cameras.items():
                sensor.listen(lambda image, key=view: self.queues[key].put(image))
                self.listening.append(sensor)
        except Exception:
            self.close()
            raise

    @staticmethod
    def _centre(actor):
        vertices = actor.bounding_box.get_world_vertices(actor.get_transform())
        if len(vertices) != 8:
            raise ValueError('original body needs eight Native vertices')
        points = [(float(v.x), float(v.y)) for v in vertices]
        if not all(math.isfinite(x) and math.isfinite(y) for x, y in points):
            raise ValueError('original body vertices nonfinite')
        return [sum(p[0] for p in points) / 8, sum(p[1] for p in points) / 8]

    def __call__(self, index):
        transform = self.ego.get_transform()
        location = transform.location
        forward = transform.get_forward_vector()
        speed = float(self.ego.get_velocity().length())
        if not all(math.isfinite(value) for value in (location.x, location.y, forward.x, forward.y, speed)):
            raise ValueError('original actor position/speed invalid')
        self.controller.apply(self.ego, location.x, location.y,
                              math.atan2(forward.y, forward.x), speed,
                              control_factory=self.control_factory)
        frame = self.world.tick()
        snapshot = self.world.get_snapshot()
        if snapshot.frame != frame or (self.prior_frame is not None and frame != self.prior_frame + 1):
            raise ValueError('Native world frame drift')
        self.prior_frame = frame
        timestamp = float(snapshot.timestamp.elapsed_seconds)
        if not math.isfinite(timestamp):
            raise ValueError('Native snapshot time invalid')
        if self.first_time is None:
            self.first_time = timestamp
        elapsed = timestamp - self.first_time
        if abs(elapsed - index / 20) > .001:
            raise ValueError('Native world clock drift')
        ego_waypoint = self.world.get_map().get_waypoint(self.ego.get_location(), project_to_road=False)
        other_waypoint = self.world.get_map().get_waypoint(self.receiving_vehicle.get_location(), project_to_road=False)
        if ego_waypoint is None or other_waypoint is None:
            raise ValueError('original actor outside Native road')
        lane = ego_waypoint.lane_id
        if other_waypoint.lane_id != self.ids['receiving_lane_id']:
            raise ValueError('receiving traffic left reviewed through lane')
        turn = lane == self.ids['center_lane_id'] and self.prior_lane not in (
            None, self.ids['center_lane_id']) and not self.turn_seen
        if turn:
            self.turn_seen = True
        merge = lane == self.ids['receiving_lane_id'] and self.prior_lane == self.ids['center_lane_id'] and not self.merge_seen
        if merge:
            self.merge_seen = True
        self.prior_lane = lane
        images = {}
        for view in VIEWS:
            try:
                image = self.queues[view].get(timeout=self.timeout_seconds)
            except Empty as exc:
                raise ValueError('original camera callback missing: ' + view) from exc
            if image.frame != frame:
                raise ValueError('original camera frame drift: ' + view)
            images[view] = image
        return {'frame': frame, 'elapsed_seconds': elapsed,
                'body_centre_xy_m': self._centre(self.ego),
                'lane_id': lane, 'approach_lane': lane not in (
                    self.ids['center_lane_id'], self.ids['receiving_lane_id'], self.ids['opposing_lane_id']),
                'left_turn_onto_highway_complete': turn,
                'merged_into_through_lane': merge, 'camera_images': images,
                'receiving_vehicle_actor_id': self.receiving_vehicle.id}

    def close(self):
        for sensor in self.listening:
            sensor.stop()
        self.listening.clear()


def run_capture(*, attempt_root, case_id, site, world, ego, receiving_vehicle,
                cameras, route_xy_m, control_factory, count=900, dimensions=None):
    """Drive and seal one exact case; caller owns actor/world lease."""
    if case_id.rsplit('__', 1)[-1] not in {
            'below_50ft', 'at_50ft', 'above_50ft', 'no_merge'}:
        raise ValueError('unknown exact center-lane case')
    source = site.get('native_map_source', {})
    relative = source.get('path')
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute() or '..' in Path(relative).parts:
        raise ValueError('reviewed Native map source path invalid')
    root = Path(attempt_root).resolve()
    path = (root / relative).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError('reviewed Native map source missing')
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != source.get('sha256'):
        raise ValueError('reviewed Native map source hash mismatch')
    expected = json.loads(raw).get('opendrive_sha256')
    current = hashlib.sha256(world.get_map().to_opendrive().encode()).hexdigest()
    if not expected or expected != current:
        raise ValueError('live OpenDRIVE differs from reviewed Native map source')
    reader = CarlaFrameReader(world=world, ego=ego, receiving_vehicle=receiving_vehicle,
                              cameras=cameras, site=site, route_xy_m=route_xy_m,
                              control_factory=control_factory)
    try:
        pixels = sensor_frame_reader(attempt_root, reader, dimensions)
        return capture_original(attempt_root, case_id, site, pixels, count)
    finally:
        reader.close()
