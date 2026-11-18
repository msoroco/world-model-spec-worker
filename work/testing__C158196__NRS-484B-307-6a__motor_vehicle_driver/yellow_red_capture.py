"""Retain same-tick Native yellow/red observations beside four source videos."""
import json
import math
from pathlib import Path

from signal_control import NativeSignalCapture
from yellow_red_policy import DURATION_FRAMES, RATE_HZ, apply_step, signal_state


class YellowRedCapture(NativeSignalCapture):
    def __enter__(self):
        super().__enter__()
        self.history_path = self.root / 'signal_vehicle_history.jsonl'
        self.context_path = self.root / 'junction_context.json'
        if self.history_path.exists() or self.context_path.exists():
            self._close(True)
            raise ValueError('Original yellow/red source already exists')
        context = self.context
        source = {'native_map_id': context['native_map_id'],
                  'intersection_id': context['intersection_id'],
                  'native_signal_id': context['native_signal_id'],
                  'governed_road_id': context['ego_road_id'],
                  'governed_lane_id': context['ego_lane_id'],
                  'signal_head_video_source': context['signal_head_video_source'],
                  'lane_governance_source': context['affected_lane_source'],
                  'intersection_polygon_xy_m': context['intersection_polygon_xy_m']}
        self.context_path.write_text(json.dumps(source, sort_keys=True, allow_nan=False) + '\n')
        self.yellow_red_count = 0
        return self

    def capture_tick(self):
        original, video_frame = super().capture_tick()
        if video_frame['video_frame'] != self.yellow_red_count:
            raise ValueError('Original yellow/red source frame join differs')
        row = {'frame': original['frame'], 'time_s': original['time_s'],
               'native_signal_id': original['native_signal_id'],
               'road_id': original['ego_road_id'], 'lane_id': original['ego_lane_id'],
               'signal_state': original['signal_state'],
               'ego_body_vertices_xy_m': original['ego_body_vertices_xy_m'],
               'ego_speed_mps': original['ego_speed_mps']}
        with self.history_path.open('a') as stream:
            stream.write(json.dumps(row, sort_keys=True, allow_nan=False) + '\n')
        self.yellow_red_count += 1
        return row, video_frame


def front_distance_to_boundary(ego, boundary_x):
    transform = ego.get_transform()
    vertices = ego.bounding_box.get_world_vertices(transform)
    if len(vertices) < 4:
        raise ValueError('Complete live ego body required for approach control')
    front = max(point.x for point in vertices)
    if not math.isfinite(front) or not math.isfinite(boundary_x):
        raise ValueError('Finite live body and boundary geometry required')
    return max(0.0, boundary_x - front)


def live_speed(ego):
    velocity = ego.get_velocity()
    values = [getattr(velocity, axis) for axis in ('x', 'y', 'z')]
    if any(not isinstance(value, (int, float)) or not math.isfinite(value) for value in values):
        raise ValueError('Finite live ego velocity required')
    return math.sqrt(sum(value * value for value in values))


def run(world, client, output, built, context, camera_blueprints, mounts,
        carla, case_id, required_atoms):
    case = case_id.rsplit('__', 1)[-1]
    polygon = context['intersection_polygon_xy_m']
    boundary_x = min(point[0] for point in polygon)
    ego, through, light = built['actors']['ego'], built['actors']['through'], built['signal']
    with YellowRedCapture(world, output, built['actors'], light, context, True,
                          camera_blueprints, mounts, client, case_id,
                          required_atoms) as capture:
        for index in range(DURATION_FRAMES):
            command = apply_step(light, ego, carla, case, index,
                                 front_distance_to_boundary(ego, boundary_x), live_speed(ego))
            through.apply_control(carla.VehicleControl(throttle=0.0, brake=1.0, steer=0.0))
            row, _ = capture.capture_tick()
            if row['signal_state'] != command['signal_state'] or row['signal_state'] != signal_state(index):
                raise ValueError('Native signal readback differs from authored phase schedule')
        if capture.yellow_red_count != DURATION_FRAMES or capture.encoder.count != DURATION_FRAMES:
            raise ValueError('Original yellow/red or video frame count incomplete')
    return {'case_id': case_id, 'source_frames': DURATION_FRAMES,
            'source_videos': [name + '.mkv' for name in ('overview', 'approach',
                              'reference_corner', 'driver_reference')],
            'encoder_exit_codes': dict(capture.encoder.exit_codes),
            'physical_or_legal_acceptance_claimed': False}
