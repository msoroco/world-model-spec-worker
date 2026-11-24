"""Source-gated Native actor and camera construction for C10301 speed probes.

The caller supplies an original site packet and CARLA transform factory. This
module does not certify that the source packet describes a lawful public way.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from delivery_audit import CAMERAS
from native_motion import CASE_PREFIX

MIN_ROUTE_M = 1800.0
SENSOR_ID = 'sensor.camera.rgb'


class NativeSite:
    def __init__(self, actor, cameras, packet_sha256):
        self.actor = actor
        self.cameras = cameras
        self.packet_sha256 = packet_sha256

    def close(self):
        for spawned in reversed([self.actor, *self.cameras.values()]):
            spawned.destroy()


def _finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def construct(world, packet_path, case_id, transform_factory):
    """Spawn source-bound ego and four cameras, cleaning up failed spawns."""
    if case_id not in {CASE_PREFIX + suffix for suffix in ('below', 'equal', 'above')}:
        raise ValueError('unknown exact speed case')
    packet_path = Path(packet_path)
    raw = packet_path.read_bytes()
    packet = json.loads(raw)
    if (packet.get('format') != 'c10301-native-site-v1' or
            packet.get('case_id') != case_id or
            packet.get('cell_id') != 'C10301' or
            packet.get('layout') != 'alley' or
            packet.get('control') != 'access_aisle' or
            packet.get('actor') != 'motor_vehicle_driver' or
            packet.get('maneuver') != 'travel' or
            type(packet.get('diagnostic_fixture')) is not bool or
            not packet.get('access_aisle_source_ref') or
            not packet.get('route_source_ref')):
        raise ValueError('exact site identity or provenance missing')
    original_map = world.get_map()
    if (not packet.get('map_name') or packet['map_name'] != original_map.name or
            hashlib.sha256(original_map.to_opendrive().encode()).hexdigest() !=
            packet.get('opendrive_sha256')):
        raise ValueError('loaded Native map source differs')
    route = packet.get('route')
    if not isinstance(route, list) or len(route) < 2:
        raise ValueError('original route missing')
    prior_s = None
    road_lane = None
    for point in route:
        if (not isinstance(point, dict) or
                any(not _finite(point.get(key)) for key in ('s_m', 'x_m', 'y_m', 'z_m'))):
            raise ValueError('original route coordinates invalid')
        if prior_s is not None and not 0 < point['s_m'] - prior_s <= 10:
            raise ValueError('original route has a gap or reversal')
        prior_s = point['s_m']
        waypoint = original_map.get_waypoint(transform_factory(point).location)
        if waypoint is None:
            raise ValueError('original route has no loaded-map waypoint')
        location = waypoint.transform.location
        if (any(not _finite(value) for value in (location.x, location.y, location.z)) or
                math.dist((point['x_m'], point['y_m'], point['z_m']),
                          (location.x, location.y, location.z)) > 2.0):
            raise ValueError('original route leaves loaded-map centerline')
        lane = (waypoint.road_id, waypoint.lane_id)
        if road_lane is None:
            road_lane = lane
        if lane != road_lane:
            raise ValueError('original route leaves reviewed lane')
    if route[-1]['s_m'] - route[0]['s_m'] < MIN_ROUTE_M:
        raise ValueError('original route too short for 45-second speed probe')
    vehicle_id = packet.get('vehicle_blueprint_id')
    camera_plan = packet.get('cameras')
    if (not isinstance(vehicle_id, str) or not vehicle_id.startswith('vehicle.') or
            not isinstance(camera_plan, dict) or set(camera_plan) != set(CAMERAS)):
        raise ValueError('vehicle or four-camera construction plan missing')
    library = world.get_blueprint_library()
    spawned = []
    try:
        actor = world.spawn_actor(library.find(vehicle_id),
                                  transform_factory(route[0]))
        if actor is None:
            raise ValueError('Native vehicle spawn failed')
        spawned.append(actor)
        cameras = {}
        for camera in CAMERAS:
            spec = camera_plan[camera]
            if (not isinstance(spec, dict) or spec.get('blueprint_id') != SENSOR_ID or
                    not all(_finite(spec.get(key)) for key in
                            ('x_m', 'y_m', 'z_m', 'pitch_deg', 'yaw_deg', 'roll_deg')) or
                    spec['z_m'] <= 0):
                raise ValueError('original camera construction spec invalid')
            sensor = world.spawn_actor(library.find(SENSOR_ID),
                                       transform_factory(spec), attach_to=actor)
            if sensor is None:
                raise ValueError('Native camera spawn failed')
            spawned.append(sensor)
            cameras[camera] = sensor
        return NativeSite(actor, cameras, hashlib.sha256(raw).hexdigest())
    except Exception:
        for item in reversed(spawned):
            item.destroy()
        raise
