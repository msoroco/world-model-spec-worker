"""Source-side backing telemetry from two live Native actors and four images.

The caller owns synchronous world ticks, actor lifecycle and video encoding.
This adapter samples original actor readbacks and writes no synthetic motion.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

from traffic_geometry import traffic_in_reverse_corridor
from traffic_saved import CAMERAS


def _xy(vector):
    values = [float(vector.x), float(vector.y)]
    if not all(math.isfinite(value) for value in values):
        raise ValueError('finite original Native XY readback required')
    return values


class NativeTrafficRecorder:
    def __init__(self, packet, vehicle, traffic):
        if vehicle.id == traffic.id:
            raise ValueError('distinct original Native actors required')
        self.packet = packet
        self.vehicle = vehicle
        self.traffic = traffic
        self.rows = []
        self.frame_map = []

    def append(self, world_frame, time_s, camera_images):
        index = len(self.rows)
        if index >= 900:
            raise ValueError('planned backing capture exceeds 900 frames')
        if type(world_frame) is not int or world_frame < 0:
            raise ValueError('original Native world frame required')
        if self.frame_map and world_frame != self.frame_map[-1]['world_frame'] + 1:
            raise ValueError('Native world frame must be consecutive')
        if type(time_s) not in (int, float) or not math.isfinite(time_s) or abs(time_s-index*.05) > .001:
            raise ValueError('original 20 Hz capture time differs')
        if not isinstance(camera_images, dict) or set(camera_images) != set(CAMERAS):
            raise ValueError('four original camera images required')
        if any(getattr(camera_images[name], 'frame', None) != world_frame for name in CAMERAS):
            raise ValueError('original camera and world tick differ')
        for name in CAMERAS:
            stamp = getattr(camera_images[name], 'timestamp', None)
            if type(stamp) not in (int, float) or not math.isfinite(stamp) or abs(stamp - time_s) > .001:
                raise ValueError('original camera timestamp and world tick differ: ' + name)
        vehicle_transform = self.vehicle.get_transform()
        traffic_transform = self.traffic.get_transform()
        vehicle_xy = _xy(vehicle_transform.location)
        traffic_xy = _xy(traffic_transform.location)
        forward_xy = _xy(vehicle_transform.get_forward_vector())
        vehicle_velocity = _xy(self.vehicle.get_velocity())
        traffic_velocity = _xy(self.traffic.get_velocity())
        control = self.vehicle.get_control()
        brake = float(control.brake)
        if not math.isfinite(brake) or not 0 <= brake <= 1 or type(control.reverse) is not bool:
            raise ValueError('original Native brake and reverse readback required')
        corridor = traffic_in_reverse_corridor(self.packet, traffic_xy)
        row = {'frame': index, 'native_world_frame': world_frame,
               'time_s': float(time_s), 'vehicle_actor_id': self.vehicle.id,
               'traffic_actor_id': self.traffic.id,
               'vehicle_xy': vehicle_xy, 'traffic_xy': traffic_xy,
               'vehicle_velocity_xy': vehicle_velocity,
               'vehicle_forward_xy': forward_xy,
               'traffic_velocity_xy': traffic_velocity,
               'brake': brake, 'reverse_gear': control.reverse,
               'traffic_in_corridor': corridor['in_corridor']}
        mapping = {'frame': index, 'world_frame': world_frame,
                   'cameras': {name: index for name in CAMERAS},
                   'camera_world_frames': {name: world_frame for name in CAMERAS}}
        self.rows.append(row)
        self.frame_map.append(mapping)
        return mapping

    def write(self, directory, *, external_trace=False):
        if len(self.rows) != 900:
            raise ValueError('complete 900-frame Native backing capture required')
        root = Path(directory)
        owned = ('telemetry.json', 'frame-map.json', 'video_frames.jsonl')
        if not external_trace:
            owned += ('trace.jsonl',)
        if not root.is_dir() or any((root / name).exists() for name in owned):
            raise ValueError('fresh Native source destination required')
        trace = root / 'trace.jsonl'
        if external_trace:
            if not trace.is_file():
                raise ValueError('original Native pipeline trace missing')
            original = [json.loads(line) for line in trace.read_text().splitlines()]
            if (len(original) != 900 or any(
                    point.get('frame') != row['native_world_frame'] or
                    abs(point.get('time_s', -1) - row['time_s']) > 1e-6 or
                    not isinstance(point.get('position_m'), list) or
                    len(point['position_m']) != 3 or
                    any(abs(point['position_m'][axis] - row['vehicle_xy'][axis]) > .001
                        for axis in (0, 1))
                    for point, row in zip(original, self.rows))):
                raise ValueError('original Native pipeline trace/frame join differs')
        telemetry = root / 'telemetry.json'
        frame_map = root / 'frame-map.json'
        telemetry.write_text(json.dumps(self.rows, allow_nan=False) + '\n', encoding='utf-8')
        frame_map.write_text(json.dumps(self.frame_map, allow_nan=False) + '\n', encoding='utf-8')
        video_map = root / 'video_frames.jsonl'
        with video_map.open('x', encoding='utf-8') as map_stream:
            for row, mapping in zip(self.rows, self.frame_map):
                map_stream.write(json.dumps({
                    'video_frame': mapping['frame'],
                    'carla_frame': mapping['world_frame'],
                    'native_frame': mapping['world_frame'],
                    'time_s': row['time_s'],
                    'camera_world_frames': mapping['camera_world_frames']},
                    allow_nan=False) + '\n')
        if not external_trace:
            with trace.open('x', encoding='utf-8') as trace_stream:
                for row in self.rows:
                    trace_stream.write(json.dumps({
                        'frame': row['native_world_frame'], 'time_s': row['time_s'],
                        'position_m': row['vehicle_xy'],
                        'vehicle_velocity_xy_mps': row['vehicle_velocity_xy'],
                        'traffic_position_m': row['traffic_xy'],
                        'traffic_velocity_xy_mps': row['traffic_velocity_xy'],
                        'reverse_gear': row['reverse_gear'], 'brake': row['brake'],
                        'traffic_in_corridor': row['traffic_in_corridor']},
                        allow_nan=False) + '\n')
        return {'telemetry': str(telemetry), 'frame_map': str(frame_map),
                'trace': str(trace), 'video_frame_map': str(video_map),
                'frame_count': 900,
                'camera_status': 'same_tick_frame_join_only; encoded pixels need saved audit'}
