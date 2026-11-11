"""CPU trajectory diagnostic for the proposed engineering following-gap grid.

This uses an explicit simple longitudinal response model. It is not CARLA
dynamics, does not model the crest or sight lines, and makes no legal judgment.
"""
import argparse
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

from following_controller import FollowingController
from sweep_probe import GRID_M

RATE_HZ = 20
FRAMES = 900
BODY_LENGTH_ASSUMPTION_M = 4.0


class Actor:
    def __init__(self, x, speed):
        self.x, self.speed, self.control = float(x), float(speed), None

    def get_location(self):
        return SimpleNamespace(x=self.x, y=0.0, z=0.0)

    def get_velocity(self):
        return SimpleNamespace(x=self.speed, y=0.0, z=0.0)

    def apply_control(self, control):
        self.control = control

    def advance(self):
        if self.control is None:
            raise ValueError('Controller did not command actor')
        acceleration = 2.5 * self.control.throttle - 5.0 * self.control.brake - 0.05 * self.speed
        self.speed = max(0.0, self.speed + acceleration / RATE_HZ)
        self.x += self.speed / RATE_HZ


def trajectory(config, requested_gap_m):
    ego, lead = Actor(0, 4.0), Actor(13.0, 3.5)
    controller = FollowingController(
        SimpleNamespace, target_speed_mps=config['ego_target_speed_mps'],
        target_center_spacing_m=requested_gap_m + BODY_LENGTH_ASSUMPTION_M,
        lane_change_start_m=55.0, lane_change_end_m=70.0,
        lead_speed_mps=config['lead_target_speed_mps'])
    samples = []
    for frame in range(FRAMES):
        state = controller.step(ego, lead,
            route_origin_xyz=(0.0, 0.0, 0.0), route_forward_xy=(1.0, 0.0),
            target_lane_center_xy=(0.0, 3.5))
        samples.append({'frame': frame, 'time_s': frame / RATE_HZ,
                        'center_spacing_m': state['measured_center_spacing_m'],
                        'assumed_body_gap_m': state['measured_center_spacing_m'] - BODY_LENGTH_ASSUMPTION_M,
                        'ego_speed_mps': state['measured_ego_speed_mps'],
                        'lead_speed_mps': state['measured_lead_speed_mps'],
                        'ego_progress_m': state['route_progress_m'],
                        'requested_speed_mps': state['requested_engineering_speed_mps']})
        ego.advance(); lead.advance()
    before_change = [row for row in samples if row['ego_progress_m'] < 55.0]
    if not before_change:
        raise ValueError('No pre-lane-change following samples')
    return {'requested_engineering_gap_m': requested_gap_m,
            'assumed_target_center_spacing_m': controller.target_spacing,
            'frames': len(samples), 'pre_change_frames': len(before_change),
            'min_assumed_body_gap_m': min(row['assumed_body_gap_m'] for row in before_change),
            'mean_assumed_body_gap_m': sum(row['assumed_body_gap_m'] for row in before_change) / len(before_change),
            'last_pre_change_body_gap_m': before_change[-1]['assumed_body_gap_m'],
            'first_pre_change_body_gap_m': before_change[0]['assumed_body_gap_m'],
            'final_ego_position_m': ego.x, 'final_lead_position_m': lead.x,
            'zero_command_frames_before_change': sum(row['requested_speed_mps'] == 0
                                                     for row in before_change)}


def probe(config):
    if (config.get('requested_engineering_gap_m') != 10.0 or
            config.get('ego_target_speed_mps') != 4.0 or
            config.get('lead_target_speed_mps') != 3.5 or
            config.get('rate_hz') != RATE_HZ or config.get('duration_s') != 45):
        raise ValueError('Reviewed base engineering configuration required')
    rows = [trajectory(config, gap) for gap in GRID_M]
    if any(row['min_assumed_body_gap_m'] <= 0 for row in rows):
        raise ValueError('Assumed body overlap in CPU trajectory diagnostic')
    return {'format': 'c101303-gap-grid-trajectory-diagnostic',
            'rate_hz': RATE_HZ, 'frames': FRAMES,
            'simple_dynamics': {'throttle_acceleration_mps2': 2.5,
                                'brake_deceleration_mps2': 5.0,
                                'speed_drag_per_s': 0.05,
                                'assumed_body_length_m': BODY_LENGTH_ASSUMPTION_M},
            'points': rows, 'diagnostic_only': True,
            'physical_feasibility_proven': False, 'legal_threshold_asserted': False,
            'limitations': ['No CARLA dynamics or hill-crest sight geometry.',
                            'Four-metre body length is an assumption, not original actor geometry.',
                            'Original accepted body traces are unavailable in this export.']}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    result = probe(json.loads(args.config.read_text()))
    result['sources'] = {name: {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
                         for name, path in (('config', args.config),
                            ('controller', Path(__file__).with_name('following_controller.py')),
                            ('grid', Path(__file__).with_name('sweep_probe.py')),
                            ('trajectory', Path(__file__)))}
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'format': result['format'], 'frames': FRAMES,
                      'points': result['points'],
                      'physical_feasibility_proven': False,
                      'output_sha256': hashlib.sha256(args.output.read_bytes()).hexdigest()}))


if __name__ == '__main__':
    main()
