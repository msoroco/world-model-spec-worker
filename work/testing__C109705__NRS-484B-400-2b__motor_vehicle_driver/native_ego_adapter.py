"""Lazy CARLA ego adapter for a source reviewed C109705 departure survey.

All positions, road identities, body vertices and clock values are live readback.
The survey supplies spawn, route and phase geometry; it cannot stand in for a
Native observation. Camera ownership is delegated to NativeCameraSource.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path


def _numbers(values, count, label):
    if not isinstance(values, list) or len(values) != count or any(
            type(value) not in (int, float) or not math.isfinite(value)
            for value in values):
        raise ValueError(f'finite {label} required')
    return [float(value) for value in values]


def _inside(point, polygon):
    if not isinstance(polygon, list) or len(polygon) < 3:
        raise ValueError('reviewed phase polygon missing')
    vertices = [_numbers(vertex, 2, 'phase polygon vertex') for vertex in polygon]
    x, y = point
    inside = False
    for a, b in zip(vertices, vertices[1:] + vertices[:1]):
        if ((a[1] > y) != (b[1] > y)) and x < (
                (b[0] - a[0]) * (y - a[1]) / (b[1] - a[1]) + a[0]):
            inside = not inside
    return inside


class NativeEgoAdapter:
    def __init__(self, world, carla, survey_path, survey_sha256, *, case_id):
        raw = Path(survey_path).read_bytes()
        if hashlib.sha256(raw).hexdigest() != survey_sha256:
            raise ValueError('reviewed ego survey packet hash differs')
        survey = json.loads(raw)
        if survey.get('cell_id') != 'C109705' or survey.get('maneuver') != 'left_turn':
            raise ValueError('reviewed ego survey context differs')
        actual_map = world.get_map()
        if actual_map.name != survey.get('map_name') or hashlib.sha256(
                actual_map.to_opendrive().encode('utf-8')).hexdigest() != survey.get('source_sha256'):
            raise ValueError('loaded Native map differs from reviewed ego survey')
        self.world, self.carla, self.survey, self.case_id = world, carla, survey, case_id
        self.map = actual_map
        self.ego = None
        self.last_control = None
        regions = survey.get('phase_regions')
        if not isinstance(regions, dict) or set(regions) != {
                'approach', 'intersection_entry', 'turning', 'departure'}:
            raise ValueError('four reviewed route phase regions required')
        for polygon in regions.values():
            _inside([float('inf'), float('inf')], polygon)
        self.regions = regions

    def spawn_ego(self, blueprint_id, map_name, case_id):
        if self.ego is not None or case_id != self.case_id or map_name != self.map.name:
            raise ValueError('Native ego identity or map differs')
        if blueprint_id != self.survey.get('ego_blueprint_id'):
            raise ValueError('reviewed Native ego blueprint differs')
        spawn = self.survey.get('ego_spawn')
        if not isinstance(spawn, dict):
            raise ValueError('reviewed Native ego spawn missing')
        xyz = _numbers(spawn.get('xyz_m'), 3, 'ego spawn')
        rotation = _numbers(spawn.get('rotation_deg'), 3, 'ego rotation')
        transform = self.carla.Transform(
            self.carla.Location(x=xyz[0], y=xyz[1], z=xyz[2]),
            self.carla.Rotation(pitch=rotation[0], yaw=rotation[1], roll=rotation[2]))
        blueprint = self.world.get_blueprint_library().find(blueprint_id)
        ego = self.world.try_spawn_actor(blueprint, transform)
        if ego is None:
            raise ValueError('reviewed Native ego spawn failed')
        ego.set_autopilot(False)
        self.ego = ego
        return ego

    def configure_cameras(self, ego, channels, fps):
        raise ValueError('original NativeCameraSource required for CARLA adapter')

    def resolve_waypoint(self, waypoint_id):
        points = self.survey.get('route_waypoint_xy_m')
        if not isinstance(points, dict) or str(waypoint_id) not in points:
            raise ValueError('reviewed route waypoint missing')
        xy = _numbers(points[str(waypoint_id)], 2, 'route waypoint')
        location = self.carla.Location(x=xy[0], y=xy[1], z=0)
        observed = self.map.get_waypoint(location, project_to_road=True)
        if observed is None or math.hypot(
                observed.transform.location.x - xy[0],
                observed.transform.location.y - xy[1]) > 1.5:
            raise ValueError('Native route waypoint readback differs')
        return xy

    def apply_control(self, ego, command):
        if ego is not self.ego or set(command) != {'throttle', 'brake', 'steer'}:
            raise ValueError('Native ego control differs')
        values = [command[name] for name in ('throttle', 'brake', 'steer')]
        if any(type(value) not in (int, float) or not math.isfinite(value)
               for value in values):
            raise ValueError('finite Native ego control required')
        ego.apply_control(self.carla.VehicleControl(
            throttle=values[0], brake=values[1], steer=values[2]))
        self.last_control = tuple(values)

    def tick(self):
        frame = self.world.tick()
        if type(frame) is not int:
            raise ValueError('Native world frame missing')
        return frame

    def ego_snapshot(self, ego, frame):
        if ego is not self.ego or self.last_control is None:
            raise ValueError('controlled Native ego missing')
        snapshot = self.world.get_snapshot()
        if snapshot.frame != frame:
            raise ValueError('Native snapshot frame differs')
        transform = ego.get_transform()
        location = transform.location
        xy = [float(location.x), float(location.y)]
        matches = [name for name, polygon in self.regions.items() if _inside(xy, polygon)]
        if len(matches) != 1:
            raise ValueError('Native route phase is ambiguous or missing')
        waypoint = self.map.get_waypoint(location, project_to_road=True)
        if waypoint is None:
            raise ValueError('Native ego road readback missing')
        vertices = ego.bounding_box.get_world_vertices(transform)
        corners = [[float(vertex.x), float(vertex.y)] for vertex in vertices]
        if len(corners) < 4:
            raise ValueError('Native ego body corners missing')
        velocity = ego.get_velocity()
        speed = math.sqrt(velocity.x ** 2 + velocity.y ** 2 + velocity.z ** 2)
        control = ego.get_control()
        observed_control = (control.throttle, control.brake, control.steer)
        if any(type(a) not in (int, float) or not math.isfinite(a) or
               abs(a - b) > 0.001 for a, b in zip(observed_control, self.last_control)):
            raise ValueError('Native driver control readback differs')
        return {'case_id': self.case_id, 'frame': frame, 'phase': matches[0],
                'road_id': waypoint.road_id, 'driver_control': True,
                'position_xy_m': xy, 'body_corners_xy_m': corners,
                'heading_rad': math.radians(transform.rotation.yaw),
                'speed_mps': speed, 'elapsed_seconds': snapshot.timestamp.elapsed_seconds}

    def camera_frame(self, channel, frame):
        raise ValueError('original NativeCameraSource required for CARLA adapter')

    def emergency_stop(self, ego):
        ego.apply_control(self.carla.VehicleControl(throttle=0, brake=1, steer=0))

    def destroy(self, ego):
        ego.destroy()
        if ego is self.ego:
            self.ego = None
