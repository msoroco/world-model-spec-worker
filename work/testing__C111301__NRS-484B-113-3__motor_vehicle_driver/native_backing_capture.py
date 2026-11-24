"""Source-side backing telemetry from two live Native actors and four images.

The caller owns synchronous world ticks, actor lifecycle and video encoding.
This adapter samples original actor readbacks and writes no synthetic motion.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

from backing_geometry import pedestrian_in_reverse_corridor
from saved_backing import CAMERAS


def _xy(vector):
    values = [float(vector.x), float(vector.y)]
    if not all(math.isfinite(value) for value in values):
        raise ValueError('finite original Native XY readback required')
    return values


class NativeBackingRecorder:
    def __init__(self, packet, vehicle, pedestrian):
        if vehicle.id == pedestrian.id:
            raise ValueError('distinct original Native actors required')
        self.packet = packet
        self.vehicle = vehicle
        self.pedestrian = pedestrian
        self.rows = []
        self.frame_map = []

    def append(self, world_frame, time_s, camera_images):
        index = len(self.rows)
        if index >= 900:
            raise ValueError('planned backing capture exceeds 900 frames')
        if type(world_frame) is not int or world_frame < 0:
            raise ValueError('original Native world frame required')
        if self.frame_map and world_frame <= self.frame_map[-1]['world_frame']:
            raise ValueError('Native world frame must increase')
        if type(time_s) not in (int, float) or not math.isfinite(time_s) or abs(time_s-index*.05) > .001:
            raise ValueError('original 20 Hz capture time differs')
        if not isinstance(camera_images, dict) or set(camera_images) != set(CAMERAS):
            raise ValueError('four original camera images required')
        if any(getattr(camera_images[name], 'frame', None) != world_frame for name in CAMERAS):
            raise ValueError('original camera and world tick differ')
        vehicle_transform = self.vehicle.get_transform()
        pedestrian_transform = self.pedestrian.get_transform()
        vehicle_xy = _xy(vehicle_transform.location)
        pedestrian_xy = _xy(pedestrian_transform.location)
        forward_xy = _xy(vehicle_transform.get_forward_vector())
        vehicle_velocity = _xy(self.vehicle.get_velocity())
        pedestrian_velocity = _xy(self.pedestrian.get_velocity())
        control = self.vehicle.get_control()
        brake = float(control.brake)
        if not math.isfinite(brake) or not 0 <= brake <= 1 or type(control.reverse) is not bool:
            raise ValueError('original Native brake and reverse readback required')
        corridor = pedestrian_in_reverse_corridor(self.packet, pedestrian_xy)
        row = {'frame': index, 'native_world_frame': world_frame,
               'time_s': float(time_s), 'vehicle_actor_id': self.vehicle.id,
               'pedestrian_actor_id': self.pedestrian.id,
               'vehicle_xy': vehicle_xy, 'pedestrian_xy': pedestrian_xy,
               'vehicle_velocity_xy': vehicle_velocity,
               'vehicle_forward_xy': forward_xy,
               'pedestrian_velocity_xy': pedestrian_velocity,
               'brake': brake, 'reverse_gear': control.reverse,
               'pedestrian_in_corridor': corridor['in_corridor']}
        mapping = {'frame': index, 'world_frame': world_frame,
                   'cameras': {name: index for name in CAMERAS},
                   'camera_world_frames': {name: world_frame for name in CAMERAS}}
        self.rows.append(row)
        self.frame_map.append(mapping)
        return mapping

    def write(self, directory):
        if len(self.rows) != 900:
            raise ValueError('complete 900-frame Native backing capture required')
        root = Path(directory)
        if not root.is_dir() or any((root / name).exists() for name in
                                    ('telemetry.json', 'frame-map.json')):
            raise ValueError('fresh Native source destination required')
        telemetry = root / 'telemetry.json'
        frame_map = root / 'frame-map.json'
        telemetry.write_text(json.dumps(self.rows, allow_nan=False) + '\n', encoding='utf-8')
        frame_map.write_text(json.dumps(self.frame_map, allow_nan=False) + '\n', encoding='utf-8')
        return {'telemetry': str(telemetry), 'frame_map': str(frame_map),
                'frame_count': 900,
                'camera_status': 'same_tick_frame_join_only; encoded pixels need saved audit'}
